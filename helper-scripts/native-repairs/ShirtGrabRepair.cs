using System;
using StoryGenerator.CharInteraction;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class ShirtGrabRepair
    {
        public static bool HasMeshOnlyShirt(GameObject gameObject)
        {
            if (Environment.GetEnvironmentVariable("ADAPTPOLICIES_NATIVE_REPAIRS") != "shirt-grab" ||
                gameObject == null || !gameObject.name.StartsWith("MOD_PRO_Shirt_", StringComparison.Ordinal) ||
                GameObjectUtils.GetCollider(gameObject) != null) return false;
            var filter = gameObject.GetComponent<MeshFilter>();
            var renderer = gameObject.GetComponent<Renderer>();
            return filter != null && filter.sharedMesh != null && renderer != null && renderer.bounds.size != Vector3.zero;
        }

        public static HandInteraction.HandPose? GetPose()
        {
            return HandInteraction.HandPose.GrabHorizontal;
        }
    }
}
