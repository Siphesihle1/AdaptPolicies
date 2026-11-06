using System;
using System.Collections.Generic;
using System.Reflection;
using StoryGenerator.CharInteraction;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class FolderPaperRepair
    {
        static readonly Dictionary<GameObject, Quaternion> PendingRelease = new Dictionary<GameObject, Quaternion>();
        static readonly FieldInfo OriginalParent = typeof(HandInteraction).GetField("m_tsfm_parent",
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        public static void RegisterRelease(GameObject ghost, Quaternion rotation) { PendingRelease[ghost] = rotation; }
        public static void ClearPending() { PendingRelease.Clear(); }
        public static void RestoreReleasePose(HandInteraction interaction)
        {
            // The original ghost interaction factory replaces pitch and roll with yaw.
            // Restore only the registered release target before native IK begins.
            Quaternion rotation;
            if (!PendingRelease.TryGetValue(interaction.gameObject, out rotation)) return;
            interaction.transform.localRotation = rotation;
            PendingRelease.Remove(interaction.gameObject);
        }
        static Transform Frame(GameObject folder)
        {
            foreach (var filter in folder.GetComponentsInChildren<MeshFilter>())
                if (filter.sharedMesh.name == "low_poly_Body") return filter.transform;
            throw new InvalidOperationException("Prepared binder body is missing.");
        }
        static bool TryPose(GameObject paper, GameObject folder, out Vector3 position, out Quaternion rotation)
        {
            position = Vector3.zero;
            rotation = Quaternion.identity;
            if (!paper.name.StartsWith("Paper", StringComparison.OrdinalIgnoreCase)) return false;
            var points = new List<Vector3>();
            foreach (var filter in paper.GetComponentsInChildren<MeshFilter>())
            {
                var renderer = filter.GetComponent<Renderer>();
                if (renderer == null || !renderer.enabled || filter.sharedMesh == null) continue;
                if (!filter.sharedMesh.isReadable) return false;
                var matrix = paper.transform.worldToLocalMatrix * filter.transform.localToWorldMatrix;
                foreach (var vertex in filter.sharedMesh.vertices) points.Add(matrix.MultiplyPoint3x4(vertex));
            }
            if (points.Count == 0) return false;
            var frame = Frame(folder);
            var min = new Vector3(-0.1379f, -0.0321f, 0.0021f);
            var max = new Vector3(0.1287f, 0.0321f, 0.3176f);
            for (var x = 0; x < 360; x += 90)
                for (var y = 0; y < 360; y += 90)
                    for (var z = 0; z < 360; z += 90)
                    {
                        var candidate = frame.rotation * Quaternion.Euler(x, y, z);
                        var matrix = frame.worldToLocalMatrix * Matrix4x4.TRS(Vector3.zero, candidate, paper.transform.lossyScale);
                        var bounds = new Bounds(matrix.MultiplyPoint3x4(points[0]), Vector3.zero);
                        foreach (var point in points) bounds.Encapsulate(matrix.MultiplyPoint3x4(point));
                        if (bounds.size.x > max.x-min.x || bounds.size.y > max.y-min.y || bounds.size.z > max.z-min.z) continue;
                        var offset = (min + max) * 0.5f - bounds.center;
                        position = frame.TransformVector(offset);
                        rotation = candidate;
                        return true;
                    }
            return false;
        }
        static void MatchPaperCollider(GameObject paper)
        {
            // This asset's root box is offset from its visible mesh. Keep geometry
            // and native containment queries together after the held paper is filed.
            var collider = paper.GetComponent<BoxCollider>();
            if (collider == null) throw new InvalidOperationException("Expected the original paper box collider.");
            var bounds = new Bounds();
            var first = true;
            foreach (var filter in paper.GetComponentsInChildren<MeshFilter>())
            {
                var renderer = filter.GetComponent<Renderer>();
                if (renderer == null || !renderer.enabled || filter.sharedMesh == null) continue;
                var matrix = paper.transform.worldToLocalMatrix * filter.transform.localToWorldMatrix;
                foreach (var vertex in filter.sharedMesh.vertices)
                {
                    var point = matrix.MultiplyPoint3x4(vertex);
                    if (first) { bounds = new Bounds(point, Vector3.zero); first = false; }
                    else bounds.Encapsulate(point);
                }
            }
            if (first) throw new InvalidOperationException("No visible paper geometry for its collider.");
            collider.center = bounds.center;
            collider.size = Vector3.Max(bounds.size, Vector3.one * 0.001f);
        }
        public static List<Vector3> Positions(Vector3 interactionPosition, GameObject payload, GameObject destination,
            bool inside, bool unused, Vector2? explicitPosition, float y, State current, PutAction action)
        {
            var washerPositions = WasherContainmentRepair.Positions(interactionPosition, payload, destination, inside, unused, explicitPosition, y, current, action);
            if (washerPositions != null) return washerPositions;
            if (!FolderOpeningRepair.IsFolder(destination))
                return SinkReleaseRepair.Positions(interactionPosition, payload, destination, inside, unused, explicitPosition, y);
            var result = new List<Vector3>();
            if (!inside || explicitPosition != null || y != -1) return result;
            ScriptObjectData data;
            if (!current.GetScriptGameObjectData(action.DestName, out data)) return result;
            var cover = Frame(destination).Find("AP_BinderCover");
            var open = data.OpenStatus == OpenStatus.OPEN || (data.OpenStatus == OpenStatus.UNKNOWN &&
                Quaternion.Angle(cover.localRotation, Quaternion.identity) >= 100f);
            if (!open) return result;
            Vector3 position;
            Quaternion rotation;
            if (TryPose(payload, destination, out position, out rotation)) result.Add(position);
            return result;
        }
        public static void PreparePut(State state)
        {
            WasherContainmentRepair.PreparePut(state);
            SinkReleaseRepair.PreparePut(state);
            var action = state.Action as PutAction;
            if (action == null) return;
            var destination = state.GetScriptGameObject(action.DestName);
            if (!FolderOpeningRepair.IsFolder(destination)) return;
            var payload = state.GetScriptGameObject(action.Name);
            Vector3 position;
            Quaternion rotation;
            if (!action.PutInside || !TryPose(payload, destination, out position, out rotation))
                throw new InvalidOperationException("Paper does not physically fit the binder interior.");
            var interaction = payload.GetComponent<HandInteraction>();
            if (interaction == null || interaction.invisibleCpy == null || OriginalParent == null)
                throw new InvalidOperationException("Native held-paper release pose is unavailable.");
            var parent = (Transform)OriginalParent.GetValue(interaction);
            var localRotation = parent == null ? rotation : Quaternion.Inverse(parent.rotation) * rotation;
            MatchPaperCollider(payload);
            interaction.invisibleCpy.transform.localRotation = localRotation;
            PendingRelease[interaction.invisibleCpy] = localRotation;
            state.AddObject("PUT_POSITION", position);
            state.AddScriptGameObject(action.Name, payload, position, state.InteractionPosition, false);
        }
    }
}
