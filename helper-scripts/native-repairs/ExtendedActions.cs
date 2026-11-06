using System;
using System.Collections;
using System.Collections.Generic;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public sealed class ManipulationAction : IAction
    {
        public ScriptObjectName Name { get; private set; }
        public int ScriptLine { get; private set; }
        public int Kind { get; private set; }

        public ManipulationAction(ScriptLine line)
        {
            Kind = (int)line.Interaction;
            ScriptLine = line.LineNumber;
            Name = new ScriptObjectName(line.Parameters[0].Item1, line.Parameters[0].Item2);
        }
    }

    public static class ExtendedActions
    {
        public static bool TryAdd(ScriptExecutor executor, int index, IList<ScriptLine> lines)
        {
            var line = lines[index];
            var kind = (int)line.Interaction;
            if (kind < 32 || kind > 33)
                return false;
            if (!NativeRepairFeatures.Enabled("manipulation-actions"))
                throw new InvalidOperationException("The custom manipulation vocabulary is disabled.");
            if (line.Parameters.Count != 1)
                throw new ArgumentException("Incorrect number of manipulation arguments.");
            var action = new ManipulationAction(line);
            executor.script.Add(new ScriptPair { Action = action, ProcessMethod = (a, state) => Process(executor, (ManipulationAction)a, state) });
            return true;
        }

        static IEnumerable<IStateGroup> Process(ScriptExecutor executor, ManipulationAction action, State current)
        {
            var payload = current.GetScriptGameObject(action.Name);
            var held = payload != null && (current.GetGameObject("RIGHT_HAND_OBJECT") == payload || current.GetGameObject("LEFT_HAND_OBJECT") == payload);
            var fold = payload == null ? null : payload.GetComponent<RugFold>();
            var planned = payload == null ? null : current.GetObject("AP_FOLDED_" + payload.GetInstanceID());
            var folded = planned is bool ? (bool)planned : fold != null && fold.Folded;
            var fullHands = current.GetGameObject("RIGHT_HAND_OBJECT") != null && current.GetGameObject("LEFT_HAND_OBJECT") != null;
            if (!held || fullHands || !RugFold.Supports(payload) || action.Kind > 33 || folded == (action.Kind == 32))
            {
                executor.report.AddItem("PROCESS MANIPULATION", "Unsupported object, unheld object, or invalid physical state.");
                yield break;
            }

            var next = new State(current, action, current.InteractionPosition, Execute);
            next.AddObject("AP_FOLDED_" + payload.GetInstanceID(), action.Kind == 32);
            yield return next;
        }

        static IEnumerator Execute(State state)
        {
            var action = (ManipulationAction)state.Action;
            var payload = state.GetScriptGameObject(action.Name);
            var fold = payload.GetComponent<RugFold>() ?? payload.AddComponent<RugFold>();
            yield return fold.Animate(action.Kind == 32);
        }

        public static void CaptureEffects(object value, Transform root, EnvironmentGraphCreator creator)
        {
            var graph = (EnvironmentGraph)value;
            RefreshGraph(graph);
            foreach (var node in graph.nodes)
            {
                var fold = node.transform == null ? null : node.transform.GetComponent<RugFold>();
                if (fold == null || !fold.Completed || fold.Folded)
                    continue;
                var held = false;
                foreach (var edge in graph.edges)
                    if (edge.to_id == node.id && (edge.relation_type == ObjectRelation.HOLDS_LH || edge.relation_type == ObjectRelation.HOLDS_RH))
                        held = true;
                if (held)
                    continue;
                var bounds = node.bounding_box.bounds;
                foreach (var surface in graph.nodes)
                {
                    if (surface.class_name != "floor" || surface.transform == null)
                        continue;
                    var floor = surface.bounding_box.bounds;
                    if (bounds.min.x < floor.min.x || bounds.max.x > floor.max.x || bounds.min.z < floor.min.z || bounds.max.z > floor.max.z || Mathf.Abs(bounds.min.y - floor.max.y) > .003f)
                        continue;
                    if (FloorContact(node.transform.gameObject, surface.transform.gameObject, bounds))
                        creator.On(node, surface);
                }
            }

            AdaptPolicies.NativeDiagnostics.SceneAssetDiagnostics.Capture(value, root);
        }

        static bool FloorContact(GameObject payload, GameObject floor, Bounds bounds)
        {
            foreach (var x in new[]
            {
                bounds.min.x + .001f,
                bounds.max.x - .001f
            }

            )
                foreach (var z in new[]
                {
                    bounds.min.z + .001f,
                    bounds.max.z - .001f
                }

                )
                {
                    RaycastHit? nearest = null;
                    foreach (var hit in Physics.RaycastAll(new Vector3(x, bounds.min.y + .03f, z), Vector3.down, .04f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                    {
                        if (GameObjectUtils.IsInPath(payload, hit.transform))
                            continue;
                        if (!nearest.HasValue || hit.distance < nearest.Value.distance)
                            nearest = hit;
                    }

                    if (!nearest.HasValue || !GameObjectUtils.IsInPath(floor, nearest.Value.transform) || Mathf.Abs(bounds.min.y - nearest.Value.point.y) > .003f)
                        return false;
                }

            return true;
        }

        public static void RefreshBeforeEdges(EnvironmentGraphCreator creator)
        {
            RefreshGraph(creator.GetGraph());
        }

        static void RefreshGraph(EnvironmentGraph graph)
        {
            foreach (var node in graph.nodes)
            {
                var fold = node.transform == null ? null : node.transform.GetComponent<RugFold>();
                if (fold == null || !fold.Completed)
                    continue;
                node.states.Remove((ObjectState)(fold.Folded ? 11 : 10));
                node.states.Add((ObjectState)(fold.Folded ? 10 : 11));
                node.bounding_box = ObjectBounds.FromGameObject(node.transform.gameObject);
                node.obj_transform = new ObjectTransform(node.transform);
            }
        }
    }
}
