using System;
using System.Collections.Generic;
using System.Reflection;
using StoryGenerator.CharInteraction;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class LidlessBinRepair
    {
        static readonly FieldInfo OriginalParent = typeof(HandInteraction).GetField("m_tsfm_parent",
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        static bool IsBin(GameObject target)
        {
            return target != null && (target.name == "Garbage_can_2" || target.name == "Garbage_can_6" || target.name == "Garbage_can_8");
        }
        static List<Vector3> Points(GameObject payload, Vector3 position, Quaternion rotation)
        {
            var final = Matrix4x4.TRS(position, rotation, payload.transform.lossyScale);
            var points = new List<Vector3>();
            foreach (var filter in payload.GetComponentsInChildren<MeshFilter>())
            {
                var renderer = filter.GetComponent<Renderer>();
                if (renderer == null || !renderer.enabled || filter.sharedMesh == null) continue;
                if (!filter.sharedMesh.isReadable) throw new InvalidOperationException("Payload geometry must be readable.");
                var matrix = final * payload.transform.worldToLocalMatrix * filter.transform.localToWorldMatrix;
                foreach (var vertex in filter.sharedMesh.vertices) points.Add(matrix.MultiplyPoint3x4(vertex));
            }
            if (points.Count == 0) throw new InvalidOperationException("No visible payload geometry.");
            return points;
        }
        public static void PreparePut(State state)
        {
            if (!NativeRepairFeatures.Enabled("lidless-bin-colliders")) return;
            var action = state.Action as PutAction;
            if (action == null || !action.PutInside || action.DestPos != null || action.Y != -1) return;
            var destination = state.GetScriptGameObject(action.DestName);
            if (!IsBin(destination)) return;
            var payload = state.GetScriptGameObject(action.Name);
            if (OriginalParent == null) throw new InvalidOperationException("Original native parent field is unavailable.");
            var interaction = payload.GetComponent<HandInteraction>();
            var parent = (Transform)OriginalParent.GetValue(interaction);
            var copy = interaction.invisibleCpy.transform;
            var parentRotation = parent == null ? Quaternion.identity : parent.rotation;
            var bin = GameObjectUtils.GetBounds(destination);
            var floor = float.NegativeInfinity;
            foreach (var hit in Physics.RaycastAll(new Vector3(bin.center.x, bin.max.y - 0.001f, bin.center.z),
                Vector3.down, bin.size.y + 0.02f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                if (GameObjectUtils.IsInPath(destination, hit.transform) && hit.normal.y > 0.95f)
                    floor = Mathf.Max(floor, hit.point.y);
            if (float.IsNegativeInfinity(floor)) throw new InvalidOperationException("No physical bin floor found.");
            var preferred = copy.localRotation;
            var rotations = new[] { preferred, preferred * Quaternion.Euler(90, 0, 0), preferred * Quaternion.Euler(-90, 0, 0),
                preferred * Quaternion.Euler(0, 0, 90), preferred * Quaternion.Euler(0, 0, -90) };
            foreach (var rotation in rotations)
            {
                var points = Points(payload, Vector3.zero, parentRotation * rotation);
                var bounds = new Bounds(points[0], Vector3.zero);
                foreach (var point in points) bounds.Encapsulate(point);
                var position = new Vector3(bin.center.x - bounds.center.x, floor + 0.002f - bounds.min.y, bin.center.z - bounds.center.z);
                var fits = true;
                var radius = Mathf.Min(bin.extents.x, bin.extents.z) - 0.006f;
                foreach (var point in points)
                {
                    var world = point + position;
                    fits &= world.y >= bin.min.y && world.y < bin.max.y - 0.006f;
                    if (destination.name == "Garbage_can_2")
                        fits &= Mathf.Abs(world.x - bin.center.x) < bin.extents.x - 0.006f &&
                            Mathf.Abs(world.z - bin.center.z) < bin.extents.z - 0.006f;
                    else
                        fits &= new Vector2(world.x - bin.center.x, world.z - bin.center.z).sqrMagnitude < radius * radius;
                }
                if (!fits) continue;
                state.AddObject("PUT_POSITION", position);
                copy.localRotation = rotation;
                state.AddScriptGameObject(action.Name, payload, position, state.InteractionPosition, false);
                return;
            }
            throw new InvalidOperationException("Visible payload does not fit inside the lidless bin.");
        }
        public static void Prepare(Transform home)
        {
            if (!NativeRepairFeatures.Enabled("lidless-bin-colliders")) return;
            foreach (var node in home.GetComponentsInChildren<Transform>(true))
            {
                if (!IsBin(node.gameObject)) continue;
                var filters = node.GetComponentsInChildren<MeshFilter>(true);
                if (filters.Length != 1 || filters[0].sharedMesh == null || filters[0].sharedMesh.name != "Mesh1")
                    throw new InvalidOperationException("Unexpected lidless bin hierarchy.");
                var filter = filters[0];
                var mesh = filter.sharedMesh;
                var expected = node.name == "Garbage_can_2" ? 1078 : 1320;
                if (!mesh.isReadable || mesh.vertexCount != expected)
                    throw new InvalidOperationException("Unexpected lidless bin mesh.");
                var collider = filter.GetComponent<MeshCollider>();
                if (collider == null) collider = filter.gameObject.AddComponent<MeshCollider>();
                collider.sharedMesh = mesh;
                collider.convex = false;
                collider.isTrigger = false;
                foreach (var box in node.GetComponentsInChildren<BoxCollider>(true)) box.isTrigger = true;
            }
            Physics.SyncTransforms();
        }
    }
}
