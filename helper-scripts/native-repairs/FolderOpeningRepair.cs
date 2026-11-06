using System;
using System.Collections.Generic;
using StoryGenerator.CharInteraction;
using StoryGenerator.SceneState;
using StoryGenerator.Utilities;
using UnityEngine;
using TargetProperty = StoryGenerator.CharInteraction.HandInteraction.ChangeVector.TargetProperty;
using Interrupt = StoryGenerator.CharInteraction.HandInteraction.TransitionBase.InterruptBehavior;
using Link = StoryGenerator.CharInteraction.HandInteraction.TransitionSequence.TransitionType;

namespace AdaptPolicies.NativeRepairs
{
    public static class FolderOpeningRepair
    {
        public static bool IsFolder(GameObject target)
        {
            return NativeRepairFeatures.Enabled("folder-opening") && target != null &&
                (target.name == "Folder_1" || target.name == "Folder_2" || target.name == "Folder_3" || target.name == "Folder_4");
        }
        public static Vector3 GetFront(GameObject target)
        {
            var room = GameObjectUtils.GetRoomTransform(target.transform);
            var direction = room == null ? Vector3.forward : GameObjectUtils.GetBounds(room.gameObject).center - target.transform.position;
            direction.y = 0;
            return Mathf.Abs(direction.x) > Mathf.Abs(direction.z) ? Vector3.right * Mathf.Sign(direction.x) : Vector3.forward * Mathf.Sign(direction.z);
        }
        static Mesh Partition(Mesh original, List<int> triangles, Vector3 pivot, string suffix)
        {
            var mesh = UnityEngine.Object.Instantiate(original);
            mesh.name = original.name + suffix;
            var vertices = mesh.vertices;
            for (var i = 0; i < vertices.Length; i++) vertices[i] -= pivot;
            mesh.vertices = vertices;
            mesh.SetTriangles(triangles, 0, false);
            var bounds = new Bounds(vertices[triangles[0]], Vector3.zero);
            foreach (var index in triangles) bounds.Encapsulate(vertices[index]);
            mesh.bounds = bounds;
            return mesh;
        }
        public static void Prepare(Transform home)
        {
            if (!NativeRepairFeatures.Enabled("folder-opening")) return;
            FolderPaperRepair.ClearPending();
            foreach (var transform in home.GetComponentsInChildren<Transform>(true))
            {
                var target = transform.gameObject;
                if (!IsFolder(target) || target.GetComponent<HandInteraction>() != null) continue;
                var filters = target.GetComponentsInChildren<MeshFilter>(true);
                if (filters.Length != 1) throw new InvalidOperationException("Unexpected binder mesh count.");
                var filter = filters[0];
                var original = filter.sharedMesh;
                if (original == null || original.name != "low_poly" || !original.isReadable || original.vertexCount != 260 || original.subMeshCount != 1)
                    throw new InvalidOperationException("Unexpected binder geometry.");
                var sign = Vector3.Dot(filter.transform.up, Vector3.up);
                if (Mathf.Abs(sign) < 0.5f) sign = Vector3.Dot(filter.transform.up, GetFront(target));
                sign = sign >= 0 ? 1 : -1;
                var fixedTriangles = new List<int>();
                var movingTriangles = new List<int>();
                var vertices = original.vertices;
                var indices = original.triangles;
                for (var i = 0; i < indices.Length; i += 3)
                {
                    var moving = true;
                    for (var j = 0; j < 3; j++)
                    {
                        var point = vertices[indices[i + j]];
                        moving &= point.y * sign >= 0.0341f && point.x <= 0.1313f;
                    }
                    var destination = moving ? movingTriangles : fixedTriangles;
                    destination.Add(indices[i]); destination.Add(indices[i + 1]); destination.Add(indices[i + 2]);
                }
                if (movingTriangles.Count != 30 || fixedTriangles.Count + movingTriangles.Count != 900)
                    throw new InvalidOperationException("Binder cover partition did not preserve every triangle.");
                var pivot = new Vector3(0.1311f, sign * 0.0342f, original.bounds.center.z);
                var cover = new GameObject("AP_BinderCover");
                cover.layer = target.layer;
                cover.transform.SetParent(filter.transform, false);
                cover.transform.localPosition = pivot;
                var coverMesh = Partition(original, movingTriangles, pivot, "_Cover");
                cover.AddComponent<MeshFilter>().sharedMesh = coverMesh;
                cover.AddComponent<MeshCollider>().sharedMesh = coverMesh;
                var sourceRenderer = filter.GetComponent<MeshRenderer>();
                var renderer = cover.AddComponent<MeshRenderer>();
                renderer.sharedMaterials = sourceRenderer.sharedMaterials;
                renderer.shadowCastingMode = sourceRenderer.shadowCastingMode;
                renderer.receiveShadows = sourceRenderer.receiveShadows;
                var properties = new MaterialPropertyBlock();
                sourceRenderer.GetPropertyBlock(properties);
                renderer.SetPropertyBlock(properties);
                filter.sharedMesh = Partition(original, fixedTriangles, Vector3.zero, "_Body");
                filter.gameObject.AddComponent<MeshCollider>().sharedMesh = filter.sharedMesh;
                foreach (var collider in target.GetComponentsInChildren<BoxCollider>()) collider.isTrigger = true;
                var delta = Vector3.forward * (-sign * 110f);
                var targets = new List<GameObject> { cover };
                var opening = new HandInteraction.ChangeVector(targets, 0, 1, TargetProperty.Rotation, false, Vector3.zero, delta, 0.9f, Interrupt.Ignore, Interrupt.Revert);
                var closing = new HandInteraction.ChangeVector(targets, 0, 1, TargetProperty.Rotation, false, Vector3.zero, -delta, 0.9f, Interrupt.Ignore, Interrupt.Revert);
                var sequence = new HandInteraction.TransitionSequence(new List<HandInteraction.TransitionBase> { opening, closing }, new List<Link> { Link.Manual });
                var state = target.GetComponent<State_object>();
                if (state == null) { state = target.AddComponent<State_object>(); state.Initialize(false, false); }
                var interaction = target.AddComponent<HandInteraction>();
                var contact = new Vector3(-0.03f, sign * 0.0375f, original.bounds.center.z);
                interaction.switches = new List<HandInteraction.ActivationSwitch> {
                    new HandInteraction.ActivationSwitch(HandInteraction.HandPose.GrabHorizontal,
                        HandInteraction.ActivationAction.Open, cover.transform.InverseTransformPoint(filter.transform.TransformPoint(contact)),
                        new List<HandInteraction.TransitionSequence> { sequence }, cover.transform)
                };
                interaction.Initialize();
            }
            Physics.SyncTransforms();
        }
    }
}
