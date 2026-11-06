using System.Collections.Generic;
using StoryGenerator.Utilities;
using StoryGenerator.DoorProperties;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class BinCarryRepair
    {
        static bool IsBin(GameObject target)
        {
            return NativeRepairFeatures.Enabled("bin-carry") && target != null && target.name == "Garbage_can_8";
        }
        public static bool IsDoorway(GameObject target)
        {
            if (!NativeRepairFeatures.Enabled("bin-carry") || target == null || target.name != "PRE_DOO_Door_01_03") return false;
            var room = GameObjectUtils.GetRoomTransform(target.transform);
            return room != null && room.name == "PRE_ROO_Kitchen_00";
        }
        public static Vector3 DoorwayFront(GameObject target)
        {
            var room = GameObjectUtils.GetRoomTransform(target.transform);
            var door = target.GetComponent<Properties_door>();
            var axis = door.doorwayB - door.doorwayA;
            var front = new Vector3(axis.y, 0, -axis.x).normalized;
            if (Vector3.Dot(front, GameObjectUtils.GetBounds(room.gameObject).center - target.transform.position) < 0) front = -front;
            return front;
        }
        public static Vector3 DoorwayAnchor(Vector3 original, GameObject target)
        {
            if (!IsDoorway(target)) return original;
            var door = target.GetComponent<Properties_door>();
            var center = (door.doorwayA + door.doorwayB) * 0.5f;
            return new Vector3(center.x, original.y, center.y);
        }
        public static float ApproachDistance(GameObject target) { return IsDoorway(target) ? 0.4f : 0.75f; }
        public static bool CanCarry(GameObject target)
        {
            if (!IsBin(target)) return false;
            var filters = target.GetComponentsInChildren<MeshFilter>();
            if (filters.Length != 1 || filters[0].sharedMesh == null || filters[0].sharedMesh.name != "Mesh1" ||
                filters[0].sharedMesh.vertexCount != 1320) return false;
            var bounds = GameObjectUtils.GetBounds(target);
            if (bounds.size.x <= 0 || bounds.size.x > 0.4f || bounds.size.y > 0.5f || bounds.size.z > 0.4f) return false;
            Physics.SyncTransforms();
            foreach (var collider in Physics.OverlapBox(bounds.center, bounds.extents - Vector3.one * 0.002f,
                Quaternion.identity, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                if (!GameObjectUtils.IsInPath(target, collider.transform) && bounds.Contains(collider.bounds.center)) return false;
            return true;
        }
        public static bool AllowsGrab(List<string> properties, string property, GrabAction action, State current)
        {
            if (properties.Contains(property)) return true;
            if (!NativeRepairFeatures.Enabled("bin-carry") || action.Name.Name != "garbagecan") return false;
            ScriptObjectData data;
            return current.GetScriptGameObjectData(action.Name, out data) && CanCarry(data.GameObject);
        }
        public static IEnumerable<IStateGroup> FilterGrab(IEnumerable<IStateGroup> original, GrabAction action, State current)
        {
            if (!NativeRepairFeatures.Enabled("bin-carry") || action.Name.Name != "garbagecan") return original;
            ScriptObjectData data;
            if (!current.GetScriptGameObjectData(action.Name, out data)) return original;
            var target = data.GameObject;
            if (!IsBin(target)) return original;
            if (current.GetGameObject("RIGHT_HAND_OBJECT") == target || current.GetGameObject("LEFT_HAND_OBJECT") == target || !CanCarry(target))
                return new List<IStateGroup>();
            var delta = GameObjectUtils.GetBounds(target).ClosestPoint(current.InteractionPosition) - current.InteractionPosition;
            delta.y = 0;
            return delta.magnitude <= 1.5f ? original : new List<IStateGroup>();
        }
    }
}
