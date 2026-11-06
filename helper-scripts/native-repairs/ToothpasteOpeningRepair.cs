using System;
using System.Collections.Generic;
using StoryGenerator.CharInteraction;
using StoryGenerator.SceneState;
using StoryGenerator.Utilities;
using UnityEngine;
using Property = StoryGenerator.CharInteraction.HandInteraction.ChangeVector.TargetProperty;
using Interrupt = StoryGenerator.CharInteraction.HandInteraction.TransitionBase.InterruptBehavior;
using Link = StoryGenerator.CharInteraction.HandInteraction.TransitionSequence.TransitionType;

namespace AdaptPolicies.NativeRepairs
{
    public static class ToothpasteOpeningRepair
    {
        public static bool IsTube(GameObject go)
        {
            return NativeRepairFeatures.Enabled("tool-manipulation") && go != null && go.name == "SHP_PRE_Toothpaste";
        }
        public static Vector3 Front(GameObject go)
        {
            var room = GameObjectUtils.GetRoomTransform(go.transform);
            var direction = room == null ? Vector3.forward : GameObjectUtils.GetBounds(room.gameObject).center - go.transform.position;
            direction.y = 0;
            return direction.normalized;
        }
        public static Transform Cap(GameObject go) { return go.transform.Find("AP_ToothpasteHinge/AP_ToothpasteCap"); }
        static Mesh Part(Mesh source, List<int> indices, Vector3 pivot, string suffix, Quaternion frame)
        {
            var mesh = UnityEngine.Object.Instantiate(source);
            mesh.name = source.name + suffix;
            var points = mesh.vertices;
            for (var i = 0; i < points.Length; i++) points[i] = Quaternion.Inverse(frame) * (points[i] - pivot);
            mesh.vertices = points;
            mesh.SetTriangles(indices, 0, false);
            var b = new Bounds(points[indices[0]], Vector3.zero);
            foreach (var index in indices) b.Encapsulate(points[index]);
            mesh.bounds = b;
            return mesh;
        }
        public static void Prepare(Transform home)
        {
            if (!NativeRepairFeatures.Enabled("tool-manipulation")) return;
            foreach (var filter in home.GetComponentsInChildren<MeshFilter>(true))
            {
                var go = filter.gameObject;
                if (!IsTube(go) || Cap(go) != null) continue;
                var source = filter.sharedMesh;
                if (source == null || source.name != "SHP_MOD_Toothpaste" || source.vertexCount != 384 || source.subMeshCount != 1 || !source.isReadable)
                    throw new InvalidOperationException("Unexpected toothpaste geometry.");
                var body = new List<int>(); var cap = new List<int>();
                var points = source.vertices; var triangles = source.triangles;
                for (var i = 0; i < triangles.Length; i += 3)
                {
                    var moving = true;
                    for (var j = 0; j < 3; j++) moving &= points[triangles[i+j]].z >= .0599f;
                    var destination = moving ? cap : body;
                    for (var j = 0; j < 3; j++) destination.Add(triangles[i+j]);
                }
                if (cap.Count == 0 || body.Count == 0 || cap.Count + body.Count != 1386)
                    throw new InvalidOperationException("Toothpaste cap partition did not preserve every original triangle.");
                var pivot = new Vector3(0,.033f,.06014f);
                var frame = Quaternion.Euler(0,0,90);
                var hinge = new GameObject("AP_ToothpasteHinge");hinge.layer=go.layer;
                hinge.transform.SetParent(go.transform,false);hinge.transform.localPosition=pivot;hinge.transform.localRotation=frame;
                var leaf = new GameObject("AP_ToothpasteCap"); leaf.layer = go.layer;
                leaf.transform.SetParent(hinge.transform,false);
                var mesh = Part(source,cap,pivot,"_Cap",frame);
                leaf.AddComponent<MeshFilter>().sharedMesh = mesh;
                var originalRenderer = go.GetComponent<MeshRenderer>();
                var renderer = leaf.AddComponent<MeshRenderer>(); renderer.sharedMaterials = originalRenderer.sharedMaterials;
                renderer.shadowCastingMode = originalRenderer.shadowCastingMode; renderer.receiveShadows = originalRenderer.receiveShadows;
                var properties = new MaterialPropertyBlock(); originalRenderer.GetPropertyBlock(properties); renderer.SetPropertyBlock(properties);
                leaf.AddComponent<MeshCollider>().sharedMesh = mesh;
                filter.sharedMesh = Part(source,body,Vector3.zero,"_Body",Quaternion.identity);
                filter.sharedMesh.bounds = source.bounds;
                foreach (var collider in go.GetComponents<BoxCollider>()) collider.isTrigger = true;
                go.AddComponent<MeshCollider>().sharedMesh = filter.sharedMesh;
                var delta = Vector3.up * 140;
                var targets = new List<GameObject> { leaf };
                var opening = new HandInteraction.ChangeVector(targets,0,1,Property.Rotation,false,Vector3.zero,delta,.7f,Interrupt.Ignore,Interrupt.Revert);
                var closing = new HandInteraction.ChangeVector(targets,0,1,Property.Rotation,false,Vector3.zero,-delta,.7f,Interrupt.Ignore,Interrupt.Revert);
                var sequence = new HandInteraction.TransitionSequence(new List<HandInteraction.TransitionBase> { opening,closing },new List<Link> { Link.Manual });
                var state = go.GetComponent<State_object>() ?? go.AddComponent<State_object>(); state.Initialize(false,false);
                var interaction = go.AddComponent<HandInteraction>();
                interaction.allowPickUp = true; interaction.objectToBePickedUp = go.transform;
                interaction.grabHandPose = HandInteraction.HandPose.GrabHorizontal;
                interaction.handPosition = new Vector3(0,.0168f,-.02f);
                interaction.switches = new List<HandInteraction.ActivationSwitch> {
                    new HandInteraction.ActivationSwitch(HandInteraction.HandPose.GrabHorizontal,HandInteraction.ActivationAction.Open,leaf.transform.InverseTransformPoint(go.transform.TransformPoint(new Vector3(0,.0168f,.077f))),new List<HandInteraction.TransitionSequence> { sequence },leaf.transform)
                };
                interaction.Initialize();
                state.Prepare(new SceneStateSequence());
                Debug.Log("AP toothpaste triangles: body=" + body.Count/3 + " cap=" + cap.Count/3);
            }
            Physics.SyncTransforms();
        }
    }
}
