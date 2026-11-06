using System;
using System.Collections;
using System.Reflection;
using StoryGenerator.CharInteraction;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class NativeOpeningRepair
    {
        static readonly FieldInfo InTransition = typeof(HandInteraction.TransitionBase).GetField(
            "inTransition", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);

        public static bool IsRepairedInteraction(GameObject target)
        {
            return ToothpasteOpeningRepair.IsTube(target) || WasherOpeningRepair.IsWasher(target) || WindowCurtainRepair.IsWindowCurtain(target) || WindowOpeningRepair.IsWindow(target) || FolderOpeningRepair.IsFolder(target);
        }
        public static bool HasFrontOverride(GameObject target)
        {
            return IsRepairedInteraction(target) || BinCarryRepair.IsDoorway(target);
        }
        public static Vector3 GetFront(GameObject target)
        {
            if (ToothpasteOpeningRepair.IsTube(target)) return ToothpasteOpeningRepair.Front(target);
            if (WasherOpeningRepair.IsWasher(target)) return WasherOpeningRepair.GetFront(target);
            if (BinCarryRepair.IsDoorway(target)) return BinCarryRepair.DoorwayFront(target);
            if (FolderOpeningRepair.IsFolder(target)) return FolderOpeningRepair.GetFront(target);
            return WindowOpeningRepair.IsWindow(target) ? WindowOpeningRepair.GetFront(target) : WindowCurtainRepair.GetFront(target);
        }
        public static void Prepare(Transform home)
        {
            ToothpasteOpeningRepair.Prepare(home);
            WasherOpeningRepair.Prepare(home);
            LidlessBinRepair.Prepare(home);
            FolderOpeningRepair.Prepare(home);
            WindowCurtainRepair.Prepare(home);
            WindowOpeningRepair.Prepare(home);
        }
        public static IEnumerator AwaitInteraction(IEnumerator original, GameObject target)
        {
            var door = DoorClosureRepair.RestoreDuration(target);
            if (door) return DoorClosureRepair.Await(AwaitOpening(original, target), target);
            return IsRepairedInteraction(target) ? AwaitOpening(original, target) : original;
        }
        static IEnumerator AwaitOpening(IEnumerator original, GameObject target)
        {
            yield return original;
            // Legacy IK can finish between physics ticks while a switch transition is pending.
            yield return new WaitForFixedUpdate();
            if (InTransition == null) throw new InvalidOperationException("Native transition completion field is unavailable.");
            var interaction = target.GetComponent<HandInteraction>();
            var deadline = Time.realtimeSinceStartup + 5f;
            while (true)
            {
                var pending = false;
                foreach (var control in interaction.switches)
                    if (control.transitionSequences != null)
                        foreach (var sequence in control.transitionSequences)
                            foreach (var transition in sequence.transitions)
                                pending |= (bool)InTransition.GetValue(transition);
                if (!pending) yield break;
                if (Time.realtimeSinceStartup > deadline) throw new InvalidOperationException("Native opening transition did not finish.");
                yield return new WaitForFixedUpdate();
            }
        }
    }
}
