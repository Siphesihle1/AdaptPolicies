using System;
using System.Collections.Generic;
using StoryGenerator.CharInteraction;
using StoryGenerator.SceneState;
using StoryGenerator.Utilities;
using UnityEngine;
using TargetProperty = StoryGenerator.CharInteraction.HandInteraction.ChangeVector.TargetProperty;
using Interrupt = StoryGenerator.CharInteraction.HandInteraction.TransitionBase.InterruptBehavior;
using Link = StoryGenerator.CharInteraction.HandInteraction.TransitionSequence.TransitionType;

namespace AdaptPolicies.NativeRepairs
{
    public static class WindowCurtainRepair
    {
        static bool IsPanel(MeshFilter filter)
        {
            return filter.sharedMesh != null && filter.name.StartsWith("PRE_DEC_Curtains_", StringComparison.Ordinal);
        }
        public static bool IsWindowCurtain(GameObject gameObject)
        {
            return NativeRepairFeatures.Enabled("window-curtains") && gameObject != null &&
                gameObject.name.StartsWith("PRE_DEC_Curtains_", StringComparison.Ordinal);
        }
        static Vector3 WidthAxis(MeshFilter filter)
        {
            return filter.sharedMesh.bounds.size.x >= filter.sharedMesh.bounds.size.z ? Vector3.right : Vector3.forward;
        }
        public static Vector3 GetFront(GameObject gameObject)
        {
            foreach (var filter in gameObject.GetComponentsInChildren<MeshFilter>(true))
            {
                if (!IsPanel(filter)) continue;
                var width = filter.transform.TransformVector(WidthAxis(filter));
                var normal = Vector3.Cross(Vector3.up, width).normalized;
                var room = GameObjectUtils.GetRoomTransform(gameObject.transform);
                if (room != null)
                {
                    var center = GameObjectUtils.GetBounds(room.gameObject).center;
                    if (Vector3.Dot(normal, center - filter.transform.position) < 0) normal = -normal;
                }
                return normal;
            }
            return gameObject.transform.right;
        }
        static HandInteraction.TransitionSequence Transition(GameObject target, TargetProperty property, Vector3 delta)
        {
            var targets = new List<GameObject> { target };
            var opening = new HandInteraction.ChangeVector(targets, 0, 1, property, false, Vector3.zero, delta, 0.9f, Interrupt.Ignore, Interrupt.Revert);
            var closing = new HandInteraction.ChangeVector(targets, 0, 1, property, false, Vector3.zero, -delta, 0.9f, Interrupt.Ignore, Interrupt.Revert);
            return new HandInteraction.TransitionSequence(
                new List<HandInteraction.TransitionBase> { opening, closing }, new List<Link> { Link.Manual });
        }
        public static void Prepare(Transform home)
        {
            if (!NativeRepairFeatures.Enabled("window-curtains")) return;
            var objects = home.GetComponentsInChildren<Transform>(true);
            foreach (var node in objects)
            {
                if (!IsWindowCurtain(node.gameObject) || node.GetComponent<HandInteraction>() != null) continue;
                var panels = new List<MeshFilter>();
                foreach (var filter in node.GetComponentsInChildren<MeshFilter>(true)) if (IsPanel(filter)) panels.Add(filter);
                if (panels.Count == 0) continue;
                var group = node;
                if (panels.Count == 1 && node.parent != null && node.parent.name.StartsWith("PRE_DEC_Curtains_", StringComparison.Ordinal)) group = node.parent;
                var center = Vector3.zero;
                var count = 0;
                foreach (var filter in group.GetComponentsInChildren<MeshFilter>(true))
                    if (IsPanel(filter)) { center += filter.transform.TransformPoint(filter.sharedMesh.bounds.center); count++; }
                center /= count;
                var transitions = new List<HandInteraction.TransitionSequence>();
                foreach (var filter in panels)
                {
                    var axis = WidthAxis(filter);
                    var meshBounds = filter.sharedMesh.bounds;
                    var width = filter.transform.TransformVector(Vector3.Scale(meshBounds.size, axis));
                    var panelCenter = filter.transform.TransformPoint(meshBounds.center);
                    var sign = Vector3.Dot(panelCenter - center, width) < 0 ? -1f : 1f;
                    var deltaScale = Vector3.Scale(filter.transform.localScale, axis) * -0.8f;
                    var desiredShift = width * (sign * 0.4f);
                    var localShift = filter.transform.parent.InverseTransformVector(desiredShift) -
                        filter.transform.localRotation * Vector3.Scale(meshBounds.center, deltaScale);
                    transitions.Add(Transition(filter.gameObject, TargetProperty.Scale, deltaScale));
                    transitions.Add(Transition(filter.gameObject, TargetProperty.Position, localShift));
                }
                var first = panels[0];
                var contact = first.transform.TransformPoint(first.sharedMesh.bounds.center);
                contact.y = Mathf.Clamp(contact.y, home.position.y + 0.8f, home.position.y + 1.5f);
                var state = node.GetComponent<State_object>();
                if (state == null) { state = node.gameObject.AddComponent<State_object>(); state.Initialize(false, false); }
                var interaction = node.gameObject.AddComponent<HandInteraction>();
                interaction.switches = new List<HandInteraction.ActivationSwitch> {
                    new HandInteraction.ActivationSwitch(HandInteraction.HandPose.GrabVerticalSmall,
                        HandInteraction.ActivationAction.Open, first.transform.InverseTransformPoint(contact), transitions, first.transform)
                };
                interaction.Initialize();
            }
        }
    }
}
