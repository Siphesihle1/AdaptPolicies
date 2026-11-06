using System;
using System.Collections.Generic;
using System.Reflection;
using StoryGenerator.CharInteraction;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class WasherContainmentRepair
    {
        static readonly FieldInfo OriginalParent = typeof(HandInteraction).GetField("m_tsfm_parent", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        static bool TryPose(GameObject payload, GameObject washer, out Vector3 position, out Quaternion rotation, bool? plannedFold = null)
        {
            position = Vector3.zero;
            rotation = Quaternion.identity;
            var rug = RugFold.Supports(payload);
            if (payload.name != "MOD_PRO_Clothes_pile_05" && !rug)
                return false;
            var points = new List<Vector3>();
            if (rug)
            {
                var folding = payload.GetComponent<RugFold>() ?? payload.AddComponent<RugFold>();
                if (!(plannedFold ?? folding.Folded)) return false;
                points.AddRange(folding.PlannedPoints(true));
            }
            else foreach (var filter in payload.GetComponentsInChildren<MeshFilter>())
            {
                var mesh = filter.sharedMesh;
                if (mesh == null || !mesh.isReadable)
                    return false;
                var matrix = payload.transform.worldToLocalMatrix * filter.transform.localToWorldMatrix;
                foreach (var v in mesh.vertices)
                    points.Add(matrix.MultiplyPoint3x4(v));
            }

            if (points.Count == 0)
                return false;
            var frame = washer.transform;
            const float radius = .233f, center = .37f, front = -.245f, back = .19f;
            for (var yaw = 0; yaw < 360; yaw += 45)
            {
                var candidate = frame.rotation * Quaternion.Euler(0, yaw, 0);
                var local = new List<Vector3>();
                var first = true;
                var bounds = new Bounds();
                foreach (var p in points)
                {
                    var v = frame.InverseTransformVector(candidate * Vector3.Scale(p, payload.transform.lossyScale));
                    local.Add(v);
                    if (first)
                    {
                        bounds = new Bounds(v, Vector3.zero);
                        first = false;
                    }
                    else
                        bounds.Encapsulate(v);
                }

                if (bounds.size.x >= 2 * radius - .008f || bounds.size.z > back - front - .008f)
                    continue;
                var offset = new Vector3(-bounds.center.x, 0, (front + back) * .5f - bounds.center.z);
                var bottom = float.NegativeInfinity;
                foreach (var p in local)
                {
                    var x = p.x + offset.x;
                    bottom = Mathf.Max(bottom, center - Mathf.Sqrt(radius * radius - x * x) - p.y);
                }

                offset.y = bottom + .002f;
                var fits = true;
                foreach (var p in local)
                {
                    var v = p + offset;
                    fits &= v.x * v.x + (v.y - center) * (v.y - center) < radius * radius && v.z > front && v.z < back;
                }

                if (!fits)
                    continue;
                position = frame.TransformPoint(offset);
                rotation = candidate;
                var world = new Bounds(position + candidate * Vector3.Scale(points[0], payload.transform.lossyScale), Vector3.zero);
                foreach (var p in points)
                    world.Encapsulate(position + candidate * Vector3.Scale(p, payload.transform.lossyScale));
                Physics.SyncTransforms();
                foreach (var co in Physics.OverlapBox(world.center, world.extents, Quaternion.identity, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                    if (!GameObjectUtils.IsInPath(washer, co.transform) && !GameObjectUtils.IsInPath(payload, co.transform))
                        fits = false;
                if (fits)
                    return true;
            }

            return false;
        }

        public static List<Vector3> Positions(Vector3 interactionPosition, GameObject payload, GameObject destination, bool inside, bool unused, Vector2? explicitPosition, float y, State current, PutAction action)
        {
            if (!WasherOpeningRepair.IsWasher(destination))
                return null;
            var result = new List<Vector3>();
            if (!inside || explicitPosition != null || y != -1)
                return result;
            ScriptObjectData data;
            if (!current.GetScriptGameObjectData(action.DestName, out data))
                return result;
            var door = destination.transform.Find("AP_WasherDoor");
            if (data.OpenStatus != OpenStatus.OPEN && (data.OpenStatus != OpenStatus.UNKNOWN || door == null || Quaternion.Angle(door.localRotation, Quaternion.identity) < 95))
                return result;
            Vector3 position;
            Quaternion rotation;
            if (TryPose(payload, destination, out position, out rotation, current.GetObject("AP_FOLDED_" + payload.GetInstanceID()) as bool?))
                result.Add(position);
            return result;
        }

        public static void PreparePut(State state)
        {
            var action = state.Action as PutAction;
            if (action == null)
                return;
            var destination = state.GetScriptGameObject(action.DestName);
            if (!WasherOpeningRepair.IsWasher(destination))
                return;
            var payload = state.GetScriptGameObject(action.Name);
            Vector3 position;
            Quaternion rotation;
            if (!action.PutInside || !TryPose(payload, destination, out position, out rotation))
                throw new InvalidOperationException("Payload does not fit the physical washer drum.");
            if (Vector3.Distance(position, (Vector3)state.GetObject("PUT_POSITION")) > .003f)
                throw new InvalidOperationException("Washer planned release pose changed.");
            var interaction = payload.GetComponent<HandInteraction>();
            if (interaction == null || interaction.invisibleCpy == null)
                throw new InvalidOperationException("Native washer release target is unavailable.");
            if (OriginalParent == null)
                throw new InvalidOperationException("Native original-parent field is unavailable.");
            var parent = (Transform)OriginalParent.GetValue(interaction);
            var copy = interaction.invisibleCpy.transform;
            var local = parent == null ? rotation : Quaternion.Inverse(parent.rotation) * rotation;
            copy.localRotation = local;
            FolderPaperRepair.RegisterRelease(copy.gameObject, local);
        }
    }
}
