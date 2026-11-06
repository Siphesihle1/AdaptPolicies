using System;
using System.Collections.Generic;
using StoryGenerator.CharInteraction;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class SinkReleaseRepair
    {
        static bool Matches(GameObject payload, GameObject destination, bool inside)
        {
            return NativeRepairFeatures.Enabled("sink-release-pose") && !inside && (payload.name == "PRE_PRO_Frying_pan_01" || payload.name == "PRE_PRO_Washing_liquid") && destination.name == "Sink";
        }
        static Bounds ReleaseBounds(GameObject payload, Quaternion rotation)
        {
            var final = Matrix4x4.TRS(Vector3.zero, rotation, payload.transform.lossyScale);
            var bounds = new Bounds();
            var first = true;
            var filters = payload.GetComponentsInChildren<MeshFilter>();
            if (filters.Length != 1) throw new InvalidOperationException("Unexpected sink payload mesh count.");
            foreach (var filter in filters)
            {
                var mesh = filter.sharedMesh;
                if (mesh == null || !mesh.isReadable || (payload.name == "PRE_PRO_Frying_pan_01" && (mesh.name != "HSHP_MOD_Frying_pan_01" || mesh.vertexCount != 367)))
                    throw new InvalidOperationException("Unexpected sink payload release geometry.");
                var matrix = final * payload.transform.worldToLocalMatrix * filter.transform.localToWorldMatrix;
                foreach (var vertex in mesh.vertices) {
                    var point = matrix.MultiplyPoint3x4(vertex);
                    if (first) { bounds = new Bounds(point, Vector3.zero); first = false; }
                    else bounds.Encapsulate(point);
                }
            }
            return bounds;
        }
        static Quaternion Rotation(GameObject destination) { return Quaternion.Euler(0, destination.transform.eulerAngles.y + 90, 0); }
        public static List<Vector3> Positions(Vector3 interactionPosition, GameObject payload, GameObject destination,
            bool inside, bool ignoreObstacles, Vector2? explicitPosition, float y)
        {
            if (!Matches(payload, destination, inside))
                return GameObjectUtils.CalculatePutPositions(interactionPosition, payload, destination, inside, ignoreObstacles, explicitPosition, y);
            var bounds = ReleaseBounds(payload, Rotation(destination));
            var sink = GameObjectUtils.GetBounds(destination);
            var result = new List<Vector3>();
            foreach (var position in GameObjectUtils.CalculatePutPositions(interactionPosition, bounds, Vector3.zero, destination, inside, ignoreObstacles, explicitPosition, y))
            {
                var min = bounds.min + position;
                var max = bounds.max + position;
                if (min.x >= sink.min.x + 0.002f && min.z >= sink.min.z + 0.002f && max.x <= sink.max.x - 0.002f && max.z <= sink.max.z - 0.002f)
                    result.Add(position);
            }
            Debug.Log("AdaptPolicies sink release: held=" + GameObjectUtils.GetBounds(payload).size + " release=" + bounds.size + " positions=" + result.Count);
            return result;
        }
        public static void PreparePut(State state)
        {
            var action = state.Action as PutAction;
            if (action == null) return;
            var payload = state.GetScriptGameObject(action.Name);
            var destination = state.GetScriptGameObject(action.DestName);
            if (!Matches(payload, destination, action.PutInside)) return;
            var position = (Vector3)state.GetObject("PUT_POSITION");
            var bounds = ReleaseBounds(payload, Rotation(destination));
            var sink = GameObjectUtils.GetBounds(destination);
            if (bounds.min.x + position.x < sink.min.x || bounds.max.x + position.x > sink.max.x ||
                bounds.min.z + position.z < sink.min.z || bounds.max.z + position.z > sink.max.z ||
                Mathf.Abs(bounds.min.y + position.y - sink.max.y) > 0.003f)
                throw new InvalidOperationException("Payload release pose does not fit the physical sink surface.");
            var interaction = payload.GetComponent<HandInteraction>();
            if (interaction == null || interaction.invisibleCpy == null) throw new InvalidOperationException("Native held-payload release target is unavailable.");
            var copy = interaction.invisibleCpy.transform;
            var rotation = copy.parent == null ? Rotation(destination) : Quaternion.Inverse(copy.parent.rotation) * Rotation(destination);
            copy.localRotation = rotation;
            FolderPaperRepair.RegisterRelease(copy.gameObject, rotation);
        }
    }
}
