using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using StoryGenerator.CharInteraction;
using StoryGenerator.DoorProperties;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class DoorClosureRepair
    {
        static readonly FieldInfo Duration = typeof(HandInteraction.TransitionBase).GetField("duration", BindingFlags.Instance | BindingFlags.NonPublic);

        public static IEnumerator Await(IEnumerator original, GameObject target)
        {
            var body = target.GetComponent<Rigidbody>();
            var hinge = target.GetComponent<HingeJoint>();
            var limits = hinge.limits;
            var useLimits = hinge.useLimits;
            var closedYaw = target.GetComponent<Properties_door>().yRotClose;
            var ignored = new List<KeyValuePair<Collider, Collider>>();
            var fixture = target.GetComponent<Properties_door>().offMeshLink.transform;
            try
            {
                var closingLimits = limits;
                closingLimits.min = hinge.angle + Mathf.DeltaAngle(target.transform.eulerAngles.y, closedYaw);
                closingLimits.max = hinge.angle;
                hinge.limits = closingLimits;
                hinge.useLimits = true;
                // The pinned leaf overlaps its fixed housing. Keep the real hinge,
                // stopper and payload collisions, excluding only its own housing.
                foreach (var nearby in Physics.OverlapSphere(target.transform.position, 1.5f))
                {
                    if (nearby.GetComponent<DoorStopper>() != null) continue;
                    var fixedFixture = nearby.transform.IsChildOf(fixture);
                    for (var parent = nearby.transform; parent != null; parent = parent.parent)
                        fixedFixture |= parent.name.StartsWith("PRE_FLO_Wood_") || parent.name.StartsWith("PRE_WAL_PAI_Doorway_");
                    if (!fixedFixture) continue;
                    foreach (var leaf in target.GetComponentsInChildren<Collider>())
                        if (leaf != nearby && !Physics.GetIgnoreCollision(leaf, nearby))
                        {
                            Physics.IgnoreCollision(leaf, nearby, true);
                            ignored.Add(new KeyValuePair<Collider, Collider>(leaf, nearby));
                        }
                }
                yield return original;
                Debug.Log("AP door closing: yaw=" + target.transform.eulerAngles.y + " closedYaw=" + closedYaw);
                if (Mathf.Abs(Mathf.DeltaAngle(target.transform.eulerAngles.y, closedYaw)) < 5f)
                {
                    body.angularVelocity = Vector3.zero;
                    body.isKinematic = true;
                }
            }
            finally
            {
                foreach (var pair in ignored) Physics.IgnoreCollision(pair.Key, pair.Value, false);
                hinge.limits = limits;
                hinge.useLimits = useLimits;
                Physics.SyncTransforms();
            }
        }

        public static bool Handles(GameObject target, bool close)
        {
            return close && NativeRepairFeatures.Enabled("door-closing") && BinCarryRepair.IsDoorway(target);
        }

        public static bool Positions(Vector3 position, GameObject target, out IList<Vector3> positions, bool usePosition, bool close)
        {
            var door = target.GetComponent<Properties_door>();
            var center = (door.doorwayA + door.doorwayB) * .5f;
            var approach = new Vector3(center.x, 0, center.y) + .4f * BinCarryRepair.DoorwayFront(target);
            approach.y = 0;
            positions = new List<Vector3>();
            if (!usePosition || (approach - new Vector3(position.x, 0, position.z)).magnitude < 1.5f)
                positions.Add(approach);
            return positions.Count > 0;
        }

        public static bool RestoreDuration(GameObject target)
        {
            if (!Handles(target, true)) return false;
            if (Duration == null) throw new InvalidOperationException("Native transition duration field is unavailable.");
            var mesh = target.GetComponent<MeshFilter>().sharedMesh;
            if (mesh.name != "HSHP_MOD_Door" || mesh.vertexCount != 410 || target.GetComponentsInChildren<Collider>().Length != 2
                || target.GetComponent<HingeJoint>() == null)
                throw new InvalidOperationException("Unexpected kitchen door geometry or hinge.");
            foreach (var control in target.GetComponent<HandInteraction>().switches)
                foreach (var sequence in control.transitionSequences)
                    foreach (var transition in sequence.transitions)
                        if (transition is HandInteraction.ApplyTorque)
                        // Fast-mode duration (1e-5s) supplies no useful torque.
                        // Restore the pinned native physics interval, not its pose.
                            Duration.SetValue(transition, 3f);
            return true;
        }
    }
}
