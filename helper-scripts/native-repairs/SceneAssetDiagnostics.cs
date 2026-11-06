using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEngine;
using Newtonsoft.Json;

namespace AdaptPolicies.NativeDiagnostics
{
    public static class SceneAssetDiagnostics
    {
        static int sequence;
        static readonly HashSet<string> Classes = new HashSet<string> {
            "clothespile", "dishwashingliquid", "paper", "curtains", "window", "closet", "clothesshirt", "clothespants", "garbagecan",
            "folder", "washingmachine", "fryingpan", "sink", "toothbrush", "toothpaste", "rug", "lime", "apple", "plum", "bananas"
        };
        [Serializable] class Switch
        {
            public string action;
            public string target;
            public float[] position;
            public int transitions;
        }
        [Serializable] class Mesh
        {
            public string objectName;
            public string name;
            public int vertices;
            public int subMeshes;
            public float[] position;
            public float[] rotation;
            public float[] worldRotation;
            public float[] worldScale;
            public float[][] worldVertices;
        }
        [Serializable] class Item
        {
            public int id;
            public string className;
            public string name;
            public string hierarchy;
            public float[] position;
            public string[] components;
            public float[] localScale;
            public float[] worldScale;
            public float[] rendererBoundsCenter;
            public float[] rendererBoundsSize;
            public bool handInteraction;
            public List<Switch> switches = new List<Switch>();
            public List<Mesh> meshes = new List<Mesh>();
            public int colliders;
        }
        [Serializable] class Report
        {
            public string root;
            public string unityVersion;
            public string scope = "Read-only diagnostics; original player scene objects and graph IDs retained";
            public List<Item> items = new List<Item>();
        }
        static object Value(object instance, string name)
        {
            if (instance == null) return null;
            const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
            var type = instance.GetType();
            var field = type.GetField(name, flags);
            if (field != null) return field.GetValue(instance);
            var property = type.GetProperty(name, flags);
            return property == null ? null : property.GetValue(instance, null);
        }
        static float[] Coordinates(Vector3 vector) { return new[] { vector.x, vector.y, vector.z }; }
        public static void Capture(object graph, Transform root)
        {
            try
            {
                var directory = Environment.GetEnvironmentVariable("ADAPTPOLICIES_NATIVE_DIAGNOSTICS");
                if (String.IsNullOrEmpty(directory)) return;
                var report = new Report { root = root.name, unityVersion = Application.unityVersion };
                var interactionType = graph.GetType().Assembly.GetType("StoryGenerator.CharInteraction.HandInteraction");
                foreach (var node in (IEnumerable)Value(graph, "nodes"))
                {
                    var className = (string)Value(node, "class_name");
                    if (!Classes.Contains(className)) continue;
                    var transform = (Transform)Value(node, "transform");
                    var item = new Item { id = (int)Value(node, "id"), className = className, name = transform.name, position = Coordinates(transform.position), hierarchy = transform.name };
                    item.localScale = Coordinates(transform.localScale);
                    item.worldScale = Coordinates(transform.lossyScale);
                    var liveBounds = new Bounds();
                    var hasRenderer = false;
                    foreach (var renderer in transform.GetComponentsInChildren<Renderer>())
                    {
                        if (!renderer.enabled) continue;
                        if (hasRenderer) liveBounds.Encapsulate(renderer.bounds);
                        else { liveBounds = renderer.bounds; hasRenderer = true; }
                    }
                    if (hasRenderer) {
                        item.rendererBoundsCenter = Coordinates(liveBounds.center);
                        item.rendererBoundsSize = Coordinates(liveBounds.size);
                    }
                    for (var parent = transform.parent; parent != null; parent = parent.parent) item.hierarchy = parent.name + "/" + item.hierarchy;
                    var components = transform.GetComponents<Component>();
                    item.components = new string[components.Length];
                    for (var i = 0; i < components.Length; i++) item.components[i] = components[i] == null ? "Missing" : components[i].GetType().FullName;
                    item.colliders = transform.GetComponentsInChildren<Collider>(true).Length;
                    var interaction = interactionType == null ? null : transform.GetComponent(interactionType);
                    item.handInteraction = interaction != null;
                    var switches = Value(interaction, "switches") as IEnumerable;
                    if (switches != null) foreach (var control in switches)
                    {
                        var target = Value(control, "switchTransform") as Transform;
                        var transitions = Value(control, "transitionSequences") as ICollection;
                        item.switches.Add(new Switch { action = Convert.ToString(Value(control, "action")), target = target == null ? null : target.name, position = Coordinates((Vector3)Value(control, "switchPosition")), transitions = transitions == null ? 0 : transitions.Count });
                    }
                    foreach (var filter in transform.GetComponentsInChildren<MeshFilter>(true))
                    {
                        var mesh = filter.sharedMesh;
                        var rotation = filter.transform.rotation;
                        float[][] worldVertices = null;
                        if ((className == "paper" || className == "fryingpan" || className == "dishwashingliquid" || className == "washingmachine" || className == "clothespile") && mesh != null && mesh.isReadable)
                        {
                            var vertices = mesh.vertices;
                            worldVertices = new float[vertices.Length][];
                            for (var i = 0; i < vertices.Length; i++) worldVertices[i] = Coordinates(filter.transform.TransformPoint(vertices[i]));
                        }
                        item.meshes.Add(new Mesh { objectName = filter.name, name = mesh == null ? null : mesh.name, vertices = mesh == null ? 0 : mesh.vertexCount, subMeshes = mesh == null ? 0 : mesh.subMeshCount, position = Coordinates(filter.transform.position), rotation = Coordinates(filter.transform.localEulerAngles), worldRotation = new[] { rotation.x, rotation.y, rotation.z, rotation.w }, worldScale = Coordinates(filter.transform.lossyScale), worldVertices = worldVertices });
                    }
                    report.items.Add(item);
                }
                Directory.CreateDirectory(directory);
                File.WriteAllText(Path.Combine(directory, "snapshot-" + (++sequence).ToString("D3") + ".json"), JsonConvert.SerializeObject(report, Formatting.Indented));
            }
            catch (Exception exception) { Debug.LogWarning("AdaptPolicies read-only diagnostic failed: " + exception); }
        }
    }
}
