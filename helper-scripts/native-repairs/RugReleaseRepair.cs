using System;
using System.Collections.Generic;
using System.Reflection;
using StoryGenerator.CharInteraction;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class RugReleaseRepair
    {
        static readonly FieldInfo OriginalParent = typeof(HandInteraction).GetField("m_tsfm_parent", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        static bool Matches(GameObject payload, GameObject destination, bool inside)
        {
            return NativeRepairFeatures.Enabled("manipulation-actions") && !inside && RugFold.Supports(payload) && destination.name == "PRE_FLO_Wood_01_03";
        }

        static Bounds Bounds(GameObject payload, Quaternion rotation)
        {
            var fold = payload.GetComponent<RugFold>() ?? payload.AddComponent<RugFold>();
            var points = fold.PlannedPoints(false);
            var matrix = Matrix4x4.TRS(Vector3.zero, rotation, payload.transform.lossyScale);
            var bounds = new Bounds(matrix.MultiplyPoint3x4(points[0]), Vector3.zero);
            foreach (var point in points)
                bounds.Encapsulate(matrix.MultiplyPoint3x4(point));
            return bounds;
        }

        public static List<Vector3> Positions(Vector3 ip, GameObject payload, GameObject destination, bool inside, bool ignore, Vector2? explicitPosition, float y, State current)
        {
            if (!Matches(payload, destination, inside))
                return null;
            var result = new List<Vector3>();
            var fold = payload.GetComponent<RugFold>();
            var planned = current.GetObject("AP_FOLDED_" + payload.GetInstanceID());
            if ((planned is bool ? (bool)planned : fold != null && fold.Folded) || explicitPosition != null || y != -1)
                return result;
            var bounds = Bounds(payload, destination.transform.rotation * Quaternion.Euler(0, 90, 0));
            var floor = GameObjectUtils.GetBounds(destination);
            var candidates = GameObjectUtils.CalculatePutPositions(ip, bounds, Vector3.zero, destination, false, ignore, explicitPosition, y);
            Debug.Log("AP rug release candidates=" + candidates.Count + " ip=" + ip + " release=" + bounds + " floor=" + floor);
            foreach (var position in candidates)
            {
                var min = bounds.min + position;
                var max = bounds.max + position;
                Debug.Log("AP rug candidate=" + position + " min=" + min + " max=" + max);
                if (min.x >= floor.min.x + .002f && min.z >= floor.min.z + .002f && max.x <= floor.max.x - .002f && max.z <= floor.max.z - .002f && Mathf.Abs(min.y - floor.max.y) < .003f)
                    result.Add(position + Vector3.up * .001f);
            }

            return result;
        }

        public static void PreparePut(State state)
        {
            var action = state.Action as PutAction;
            if (action == null)
                return;
            var payload = state.GetScriptGameObject(action.Name);
            var destination = state.GetScriptGameObject(action.DestName);
            if (!Matches(payload, destination, action.PutInside))
                return;
            var fold = payload.GetComponent<RugFold>();
            if (fold == null || !fold.Completed || fold.Folded)
                throw new InvalidOperationException("The washed rug must be unfolded before floor placement.");
            var position = (Vector3)state.GetObject("PUT_POSITION");
            var rotation = destination.transform.rotation * Quaternion.Euler(0, 90, 0);
            var bounds = Bounds(payload, rotation);
            var floor = GameObjectUtils.GetBounds(destination);
            var min = bounds.min + position;
            var max = bounds.max + position;
            if (min.x < floor.min.x || min.z < floor.min.z || max.x > floor.max.x || max.z > floor.max.z || Mathf.Abs(min.y - floor.max.y) > .003f)
                throw new InvalidOperationException("The full rug must rest on the physical floor surface.");
            var interaction = payload.GetComponent<HandInteraction>();
            if (interaction == null || interaction.invisibleCpy == null || OriginalParent == null)
                throw new InvalidOperationException("Native rug release target is unavailable.");
            var parent = (Transform)OriginalParent.GetValue(interaction);
            var local = parent == null ? rotation : Quaternion.Inverse(parent.rotation) * rotation;
            interaction.invisibleCpy.transform.localRotation = local;
            FolderPaperRepair.RegisterRelease(interaction.invisibleCpy, local);
        }
    }
}
