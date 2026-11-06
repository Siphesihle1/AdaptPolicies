using System;
using System.Collections.Generic;
using StoryGenerator.CharInteraction;
using StoryGenerator.SceneState;
using UnityEngine;
using TargetProperty = StoryGenerator.CharInteraction.HandInteraction.ChangeVector.TargetProperty;
using Interrupt = StoryGenerator.CharInteraction.HandInteraction.TransitionBase.InterruptBehavior;
using Link = StoryGenerator.CharInteraction.HandInteraction.TransitionSequence.TransitionType;

namespace AdaptPolicies.NativeRepairs
{
    public static class WasherOpeningRepair
    {
        const float CenterY = 0.37f;
        const float Radius = 0.245f;
        const int Sides = 64;
        struct Vertex
        {
            public Vector3 p, normal;
            public Vector2 uv;
            public static Vertex Mix(Vertex a, Vertex b, float t)
            {
                return new Vertex
                {
                    p = Vector3.Lerp(a.p, b.p, t),
                    normal = Vector3.Lerp(a.normal, b.normal, t),
                    uv = Vector2.Lerp(a.uv, b.uv, t)
                };
            }
        }

        class Builder
        {
            readonly List<Vector3> vertices = new List<Vector3>();
            readonly List<Vector3> normals = new List<Vector3>();
            readonly List<Vector2> uv = new List<Vector2>();
            readonly List<int> triangles = new List<int>();
            public float area;
            public void Add(List<Vertex> polygon)
            {
                for (var j = 1; j + 1 < polygon.Count; j++)
                {
                    var a = polygon[0];
                    var b = polygon[j];
                    var c = polygon[j + 1];
                    var size = Vector3.Cross(b.p - a.p, c.p - a.p).magnitude * 0.5f;
                    if (size < 1e-10f)
                        continue;
                    area += size;
                    foreach (var point in new[]
                    {
                        a,
                        b,
                        c
                    }

                    )
                    {
                        triangles.Add(vertices.Count);
                        vertices.Add(point.p);
                        normals.Add(point.normal);
                        uv.Add(point.uv);
                    }
                }
            }

            public Mesh Finish(string name, Vector3 pivot)
            {
                var mesh = new Mesh
                {
                    name = name
                };
                for (var i = 0; i < vertices.Count; i++)
                    vertices[i] -= pivot;
                mesh.SetVertices(vertices);
                mesh.SetNormals(normals);
                mesh.SetUVs(0, uv);
                mesh.SetTriangles(triangles, 0);
                mesh.RecalculateBounds();
                return mesh;
            }
        }

        static float Side(Vector3 point, Vector2 a, Vector2 b)
        {
            return (b.x - a.x) * (point.y - a.y) - (b.y - a.y) * (point.x - a.x);
        }

        static void Split(List<Vertex> input, Vector2 a, Vector2 b, out List<Vertex> inside, out List<Vertex> outside)
        {
            inside = new List<Vertex>();
            outside = new List<Vertex>();
            for (var i = 0; i < input.Count; i++)
            {
                var from = input[i];
                var to = input[(i + 1) % input.Count];
                var d = Side(from.p, a, b);
                var e = Side(to.p, a, b);
                if (d >= 0)
                    inside.Add(from);
                else
                    outside.Add(from);
                if ((d >= 0) != (e >= 0))
                {
                    var cross = Vertex.Mix(from, to, d / (d - e));
                    inside.Add(cross);
                    outside.Add(cross);
                }
            }
        }

        public static bool IsWasher(GameObject target)
        {
            return NativeRepairFeatures.Enabled("washer-opening") && target != null && target.name == "Dark_Grey_Washing_Machine";
        }

        public static Vector3 GetFront(GameObject target)
        {
            return -target.transform.forward;
        }

        static GameObject Part(Transform parent, string name, Mesh mesh, Material[] materials, Vector3 pivot)
        {
            var part = new GameObject(name);
            part.layer = parent.gameObject.layer;
            part.transform.SetParent(parent, false);
            part.transform.localPosition = pivot;
            part.AddComponent<MeshFilter>().sharedMesh = mesh;
            part.AddComponent<MeshRenderer>().sharedMaterials = materials;
            part.AddComponent<MeshCollider>().sharedMesh = mesh;
            return part;
        }

        static Mesh Drum()
        {
            var b = new Builder();
            var radius = Radius - .012f;
            const float front = -.255f, back = .20f;
            for (var i = 0; i < Sides; i++)
            {
                var a = 2 * Mathf.PI * i / Sides;
                var c = 2 * Mathf.PI * (i + 1) / Sides;
                var n0 = new Vector3(-Mathf.Cos(a), -Mathf.Sin(a), 0);
                var n1 = new Vector3(-Mathf.Cos(c), -Mathf.Sin(c), 0);
                var p0 = new Vector3(radius * Mathf.Cos(a), CenterY + radius * Mathf.Sin(a), front);
                var p1 = new Vector3(radius * Mathf.Cos(c), CenterY + radius * Mathf.Sin(c), front);
                var p2 = new Vector3(p1.x, p1.y, back);
                var p3 = new Vector3(p0.x, p0.y, back);
                b.Add(new List<Vertex> { new Vertex { p = p0, normal = n0 }, new Vertex { p = p3, normal = n0 }, new Vertex { p = p2, normal = n1 }, new Vertex { p = p1, normal = n1 } });
                b.Add(new List<Vertex> { new Vertex { p = new Vector3(0, CenterY, back), normal = Vector3.back }, new Vertex { p = p2, normal = Vector3.back }, new Vertex { p = p3, normal = Vector3.back } });
            }

            return b.Finish("AP_WasherDrum", new Vector3(0, CenterY, 0));
        }

        static Mesh DoorBack(Mesh front)
        {
            var vertices = front.vertices;
            var indices = front.triangles;
            var b = new Builder();
            for (var i = 0; i < indices.Length; i += 3)
            {
                var polygon = new List<Vertex>();
                for (var j = 2; j >= 0; j--)
                    polygon.Add(new Vertex { p = vertices[indices[i + j]] + Vector3.forward * .006f, normal = Vector3.forward });
                b.Add(polygon);
            }

            return b.Finish("AP_WasherDoorBack", Vector3.zero);
        }

        public static void Prepare(Transform home)
        {
            if (!NativeRepairFeatures.Enabled("washer-opening"))
                return;
            foreach (var transform in home.GetComponentsInChildren<Transform>(true))
            {
                var target = transform.gameObject;
                if (!IsWasher(target) || target.GetComponent<HandInteraction>() != null)
                    continue;
                var filters = target.GetComponentsInChildren<MeshFilter>(true);
                if (filters.Length != 1)
                    throw new InvalidOperationException("Unexpected washer mesh hierarchy.");
                var filter = filters[0];
                var original = filter.sharedMesh;
                if (original == null || !original.isReadable || original.name != "Washing Machine" || original.vertexCount != 32 || original.triangles.Length != 72 || original.subMeshCount != 1)
                    throw new InvalidOperationException("Unexpected washer housing geometry.");
                var body = new Builder();
                var door = new Builder();
                var points = original.vertices;
                var uv = original.uv;
                var normals = original.normals;
                var indices = original.triangles;
                var total = 0f;
                for (var i = 0; i < indices.Length; i += 3)
                {
                    var polygon = new List<Vertex>();
                    for (var j = 0; j < 3; j++)
                    {
                        var id = indices[i + j];
                        polygon.Add(new Vertex { p = points[id], normal = normals[id], uv = uv[id] });
                    }

                    var cross = Vector3.Cross(polygon[1].p - polygon[0].p, polygon[2].p - polygon[0].p);
                    total += cross.magnitude * .5f;
                    if (cross.normalized.z > -.95f)
                    {
                        body.Add(polygon);
                        continue;
                    }

                    for (var edge = 0; edge < Sides && polygon.Count > 0; edge++)
                    {
                        var a = 2 * Mathf.PI * edge / Sides;
                        var c = 2 * Mathf.PI * (edge + 1) / Sides;
                        List<Vertex> inside, outside;
                        Split(polygon, new Vector2(Radius * Mathf.Cos(a), CenterY + Radius * Mathf.Sin(a)), new Vector2(Radius * Mathf.Cos(c), CenterY + Radius * Mathf.Sin(c)), out inside, out outside);
                        body.Add(outside);
                        polygon = inside;
                    }

                    door.Add(polygon);
                }

                if (door.area < .15f || Mathf.Abs(body.area + door.area - total) > .0001f)
                    throw new InvalidOperationException("Washer door split did not preserve the original surface area.");
                var source = filter.GetComponent<MeshRenderer>();
                var pivot = new Vector3(-Radius, CenterY, -.256f);
                var leaf = Part(filter.transform, "AP_WasherDoor", door.Finish("Washing Machine_Door", pivot), source.sharedMaterials, pivot);
                var props = new MaterialPropertyBlock();
                source.GetPropertyBlock(props);
                leaf.GetComponent<MeshRenderer>().SetPropertyBlock(props);
                filter.sharedMesh = body.Finish("Washing Machine_Body", Vector3.zero);
                var bodyCollider = filter.GetComponent<MeshCollider>();
                if (bodyCollider == null)
                    bodyCollider = filter.gameObject.AddComponent<MeshCollider>();
                bodyCollider.sharedMesh = filter.sharedMesh;
                foreach (var box in target.GetComponentsInChildren<BoxCollider>(true))
                    box.isTrigger = true;
                var metal = new Material(Shader.Find("Standard"));
                metal.color = new Color(.18f, .19f, .20f);
                metal.SetFloat("_Metallic", .7f);
                metal.SetFloat("_Glossiness", .5f);
                Part(leaf.transform, "AP_WasherDoorBack", DoorBack(leaf.GetComponent<MeshFilter>().sharedMesh), new[] { metal }, Vector3.zero);
                var drum = Part(filter.transform, "AP_WasherDrum", Drum(), new[] { metal }, new Vector3(0, CenterY, 0));
                var indicator = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                indicator.name = "AP_WasherPower";
                indicator.transform.SetParent(filter.transform, false);
                indicator.transform.localPosition = new Vector3(.2f, .735f, -.27f);
                indicator.transform.localScale = Vector3.one * .009f;
                UnityEngine.Object.Destroy(indicator.GetComponent<Collider>());
                indicator.GetComponent<Renderer>().material.color = Color.green;
                indicator.SetActive(false);
                var motion = target.AddComponent<WasherDrumMotion>();
                motion.drum = drum.transform;
                motion.power = indicator;
                var delta = Vector3.up * 100;
                var opening = new HandInteraction.ChangeVector(new List<GameObject> { leaf }, 0, 1, TargetProperty.Rotation, false, Vector3.zero, delta, .9f, Interrupt.Ignore, Interrupt.Revert);
                var closing = new HandInteraction.ChangeVector(new List<GameObject> { leaf }, 0, 1, TargetProperty.Rotation, false, Vector3.zero, -delta, .9f, Interrupt.Ignore, Interrupt.Revert);
                var sequence = new HandInteraction.TransitionSequence(new List<HandInteraction.TransitionBase> { opening, closing }, new List<Link> { Link.Manual });
                var toggle = new HandInteraction.Toggle(new List<GameObject> { indicator }, 0, Interrupt.Ignore);
                var power = new HandInteraction.TransitionSequence(new List<HandInteraction.TransitionBase> { toggle }, null);
                var state = target.GetComponent<State_object>();
                if (state == null)
                {
                    state = target.AddComponent<State_object>();
                    state.Initialize(false, false);
                }

                var contact = new Vector3(.18f, CenterY, -.27f);
                var interaction = target.AddComponent<HandInteraction>();
                interaction.switches = new List<HandInteraction.ActivationSwitch>
                {
                    new HandInteraction.ActivationSwitch(HandInteraction.HandPose.GrabHorizontal, HandInteraction.ActivationAction.Open, leaf.transform.InverseTransformPoint(filter.transform.TransformPoint(contact)), new List<HandInteraction.TransitionSequence> { sequence }, leaf.transform),
                    new HandInteraction.ActivationSwitch(HandInteraction.HandPose.Button, HandInteraction.ActivationAction.SwitchOn, new Vector3(.2f, .735f, -.27f), new List<HandInteraction.TransitionSequence> { power }, filter.transform)
                };
                interaction.Initialize();
                Debug.Log("AdaptPolicies washer partition: originalArea=" + total + " bodyArea=" + body.area + " doorArea=" + door.area);
            }

            Physics.SyncTransforms();
        }
    }

    public class WasherDrumMotion : MonoBehaviour
    {
        public Transform drum;
        public GameObject power;
        void FixedUpdate()
        {
            if (power != null && power.activeSelf)
                drum.Rotate(0, 0, 90 * Time.fixedDeltaTime, Space.Self);
        }
    }
}
