using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEngine;
using Newtonsoft.Json;
using RootMotion.FinalIK;

namespace AdaptPolicies.NativeDiagnostics
{
    public static class SceneAssetDiagnostics
    {
        static int sequence;
        static readonly HashSet<string> Classes = new HashSet<string> {
            "character", "clothespile", "dishwashingliquid", "paper", "curtains", "window", "closet", "clothesshirt", "clothespants", "garbagecan",
            "folder", "washingmachine", "fryingpan", "sink", "toothbrush", "toothpaste", "rug", "lime", "apple", "plum", "bananas", "door"
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
            public int[] triangles;
            public float[][] localVertices;
            public int[][] subMeshTriangles;
            public string[] materials;
        }
        [Serializable] class Bone { public string name; public float[] position; public float[] rotation; }
        [Serializable] class CollisionShape { public string name, type; public float[] center, size; public bool trigger; }
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
            public float[] rotation;
            public float? doorClosedYaw;
            public bool? isKinematic;
            public List<CollisionShape> collisionShapes = new List<CollisionShape>();
            public List<Bone> bones = new List<Bone>();
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
                    item.rotation = Coordinates(transform.eulerAngles);
                    var door = transform.GetComponent<StoryGenerator.DoorProperties.Properties_door>();
                    if (door != null) item.doorClosedYaw = door.yRotClose;
                    if (door != null && transform.name == "PRE_DOO_Door_01_03" && transform.GetComponent<DoorContactDiagnostics>() == null)
                        transform.gameObject.AddComponent<DoorContactDiagnostics>();
                    var body = transform.GetComponent<Rigidbody>();
                    if (body != null) item.isKinematic = body.isKinematic;
                    var ik = transform.GetComponentInChildren<FullBodyBipedIK>();
                    if (className == "character" && ik != null) {
                        var refs = ik.references;
                        foreach (var bone in new[] { refs.head, refs.leftHand, refs.rightHand, refs.leftUpperArm, refs.rightUpperArm }) if (bone != null) {
                            var q = bone.rotation;
                            item.bones.Add(new Bone { name = bone.name, position = Coordinates(bone.position), rotation = new[] { q.x, q.y, q.z, q.w } });
                        }
                        foreach (var eye in refs.eyes) if (eye != null) {
                            var q=eye.rotation;
                            item.bones.Add(new Bone { name=eye.name, position=Coordinates(eye.position), rotation=new[] { q.x,q.y,q.z,q.w } });
                        }
                    }
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
                    if (door != null) foreach (var collider in transform.GetComponentsInChildren<Collider>(true))
                        item.collisionShapes.Add(new CollisionShape { name = collider.name, type = collider.GetType().Name, center = Coordinates(collider.bounds.center), size = Coordinates(collider.bounds.size), trigger = collider.isTrigger });
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
                        if ((className == "rug" || className == "toothpaste" || className == "toothbrush" || className == "paper" || className == "fryingpan" || className == "dishwashingliquid" || className == "washingmachine" || className == "clothespile") && mesh != null && mesh.isReadable)
                        {
                            var vertices = mesh.vertices;
                            worldVertices = new float[vertices.Length][];
                            for (var i = 0; i < vertices.Length; i++) worldVertices[i] = Coordinates(filter.transform.TransformPoint(vertices[i]));
                        }
                        var geometry = className == "rug" || className == "toothpaste" || className == "toothbrush";
                        float[][] localVertices = null; int[][] subs = null; string[] materials = null;
                        if (geometry && mesh != null && mesh.isReadable) {
                            var vertices=mesh.vertices;
                            localVertices=new float[vertices.Length][];
                            for (var i=0;i<vertices.Length;i++) localVertices[i]=Coordinates(vertices[i]);
                            subs=new int[mesh.subMeshCount][];
                            for (var i=0;i<subs.Length;i++) subs[i]=mesh.GetTriangles(i);
                            var renderer=filter.GetComponent<Renderer>();
                            if (renderer != null) {
                                materials=new string[renderer.sharedMaterials.Length];
                                for (var i=0;i<materials.Length;i++) materials[i]=renderer.sharedMaterials[i].name;
                            }
                        }
                        item.meshes.Add(new Mesh { objectName=filter.name, name=mesh == null ? null : mesh.name, vertices=mesh == null ? 0 : mesh.vertexCount, subMeshes=mesh == null ? 0 : mesh.subMeshCount, position=Coordinates(filter.transform.position), rotation=Coordinates(filter.transform.localEulerAngles), worldRotation=new[] { rotation.x,rotation.y,rotation.z,rotation.w }, worldScale=Coordinates(filter.transform.lossyScale), worldVertices=worldVertices, localVertices=localVertices, subMeshTriangles=subs, materials=materials, triangles=geometry && mesh != null && mesh.isReadable ? mesh.triangles : null });
                    }
                    report.items.Add(item);
                }
                Directory.CreateDirectory(directory);
                File.WriteAllText(Path.Combine(directory, "snapshot-" + (++sequence).ToString("D3") + ".json"), JsonConvert.SerializeObject(report, Formatting.Indented));
            }
            catch (Exception exception) { Debug.LogWarning("AdaptPolicies read-only diagnostic failed: " + exception); }
        }
    }

    public class DoorContactDiagnostics : MonoBehaviour
    {
        readonly Dictionary<int, int> seen = new Dictionary<int, int>();
        void OnCollisionStay(Collision collision)
        {
            var band = (int)(transform.eulerAngles.y / 5);
            var id = collision.collider.GetInstanceID();
            int previous;
            if (seen.TryGetValue(id, out previous) && previous == band) return;
            seen[id] = band;
            var path = collision.collider.name;
            for (var parent = collision.collider.transform.parent; parent != null; parent = parent.parent) path = parent.name + "/" + path;
            Debug.Log("AP door contact: yaw=" + transform.eulerAngles.y + " other=" + path + " point=" + collision.contacts[0].point + " normal=" + collision.contacts[0].normal);
        }
    }
}
