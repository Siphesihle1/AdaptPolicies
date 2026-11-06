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
    public static class WindowOpeningRepair
    {
        public static bool IsWindow(GameObject target)
        {
            if (!NativeRepairFeatures.Enabled("window-opening") || target == null ||
                !target.name.StartsWith("PRE_Window_", StringComparison.Ordinal)) return false;
            var filter = target.GetComponent<MeshFilter>();
            return filter != null && filter.sharedMesh != null &&
                (filter.sharedMesh.name.StartsWith("HSHP_MOD_Window_01", StringComparison.Ordinal) ||
                 filter.sharedMesh.name.StartsWith("HSHP_MOD_Window_02", StringComparison.Ordinal));
        }
        public static Vector3 GetFront(GameObject target)
        {
            var normal = target.transform.right;
            var room = GameObjectUtils.GetRoomTransform(target.transform);
            if (room != null && Vector3.Dot(normal, GameObjectUtils.GetBounds(room.gameObject).center - target.transform.position) < 0)
                normal = -normal;
            return normal;
        }
        static Mesh Partition(Mesh original, List<int>[] triangles, Vector3 pivot, string suffix)
        {
            var mesh = UnityEngine.Object.Instantiate(original);
            mesh.name = original.name + suffix;
            var vertices = mesh.vertices;
            for (var i = 0; i < vertices.Length; i++) vertices[i] -= pivot;
            mesh.vertices = vertices;
            var bounds = new Bounds();
            var first = true;
            for (var submesh = 0; submesh < triangles.Length; submesh++)
            {
                mesh.SetTriangles(triangles[submesh], submesh, false);
                foreach (var index in triangles[submesh])
                    if (first) { bounds = new Bounds(vertices[index], Vector3.zero); first = false; }
                    else bounds.Encapsulate(vertices[index]);
            }
            mesh.bounds = bounds;
            return mesh;
        }
        public static void Prepare(Transform home)
        {
            if (!NativeRepairFeatures.Enabled("window-opening")) return;
            foreach (var filter in home.GetComponentsInChildren<MeshFilter>(true))
            {
                var target = filter.gameObject;
                if (!IsWindow(target) || target.GetComponent<HandInteraction>() != null) continue;
                var original = filter.sharedMesh;
                if (!original.isReadable || original.subMeshCount != 2 ||
                    (original.vertexCount != 240 && original.vertexCount != 224))
                    throw new InvalidOperationException("Unexpected native window geometry: " + original.name);
                var vertices = original.vertices;
                var glassIndices = original.GetTriangles(1);
                var glass = new Bounds(vertices[glassIndices[0]], Vector3.zero);
                foreach (var index in glassIndices) glass.Encapsulate(vertices[index]);
                var fixedTriangles = new[] { new List<int>(), new List<int>() };
                var movingTriangles = new[] { new List<int>(), new List<int>() };
                for (var submesh = 0; submesh < 2; submesh++)
                {
                    var indices = original.GetTriangles(submesh);
                    for (var i = 0; i < indices.Length; i += 3)
                    {
                        var moving = true;
                        for (var j = 0; j < 3; j++)
                        {
                            var point = vertices[indices[i + j]];
                            moving &= point.y >= glass.min.y - 0.0001f && point.y <= glass.max.y + 0.0001f &&
                                point.z >= glass.min.z - 0.0001f && point.z <= glass.max.z + 0.0001f &&
                                Mathf.Abs(point.x - original.bounds.center.x) < original.bounds.size.x * 0.4f;
                        }
                        var destination = moving ? movingTriangles[submesh] : fixedTriangles[submesh];
                        destination.Add(indices[i]); destination.Add(indices[i + 1]); destination.Add(indices[i + 2]);
                    }
                }
                if (movingTriangles[0].Count == 0 || movingTriangles[1].Count != glassIndices.Length || fixedTriangles[0].Count == 0)
                    throw new InvalidOperationException("Native window partition failed.");
                var pivot = new Vector3(glass.center.x, glass.center.y, glass.min.z);
                var leaf = new GameObject("AP_MovingLeaf");
                leaf.layer = target.layer;
                leaf.transform.SetParent(target.transform, false);
                leaf.transform.localPosition = pivot;
                leaf.AddComponent<MeshFilter>().sharedMesh = Partition(original, movingTriangles, pivot, "_MovingLeaf");
                var sourceRenderer = target.GetComponent<MeshRenderer>();
                var renderer = leaf.AddComponent<MeshRenderer>();
                renderer.sharedMaterials = sourceRenderer.sharedMaterials;
                renderer.shadowCastingMode = sourceRenderer.shadowCastingMode;
                renderer.receiveShadows = sourceRenderer.receiveShadows;
                renderer.lightmapIndex = sourceRenderer.lightmapIndex;
                renderer.lightmapScaleOffset = sourceRenderer.lightmapScaleOffset;
                var properties = new MaterialPropertyBlock();
                sourceRenderer.GetPropertyBlock(properties);
                renderer.SetPropertyBlock(properties);
                filter.sharedMesh = Partition(original, fixedTriangles, Vector3.zero, "_FixedFrame");
                var delta = Vector3.up * (Vector3.Dot(GetFront(target), target.transform.right) > 0 ? 70f : -70f);
                var targets = new List<GameObject> { leaf };
                var opening = new HandInteraction.ChangeVector(targets, 0, 1, TargetProperty.Rotation, false, Vector3.zero, delta, 0.9f, Interrupt.Ignore, Interrupt.Revert);
                var closing = new HandInteraction.ChangeVector(targets, 0, 1, TargetProperty.Rotation, false, Vector3.zero, -delta, 0.9f, Interrupt.Ignore, Interrupt.Revert);
                var sequence = new HandInteraction.TransitionSequence(new List<HandInteraction.TransitionBase> { opening, closing }, new List<Link> { Link.Manual });
                var state = target.GetComponent<State_object>();
                if (state == null) { state = target.AddComponent<State_object>(); state.Initialize(false, false); }
                var contact = new Vector3(glass.center.x, glass.center.y, glass.min.z + Mathf.Min(0.2f, glass.size.z * 0.25f));
                var interaction = target.AddComponent<HandInteraction>();
                interaction.switches = new List<HandInteraction.ActivationSwitch> {
                    new HandInteraction.ActivationSwitch(HandInteraction.HandPose.GrabVerticalSmall,
                        HandInteraction.ActivationAction.Open, leaf.transform.InverseTransformPoint(target.transform.TransformPoint(contact)),
                        new List<HandInteraction.TransitionSequence> { sequence }, leaf.transform)
                };
                interaction.Initialize();
            }
        }
    }
}
