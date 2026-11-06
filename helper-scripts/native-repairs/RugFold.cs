using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public sealed class RugFold : MonoBehaviour
    {
        const int Panels = 16;
        const float Radius = .005f;
        public bool Folded { get; private set; }
        public bool Completed { get; private set; }

        Mesh original, work;
        MeshFilter filter;
        Vector3 scale;
        Bounds metric;
        Vector3[] rest;
        Vector2[] uv;
        int[] triangles;
        Collider[] colliders;
        bool[] colliderEnabled;
        MeshCollider foldedCollider;
        struct Vertex
        {
            public Vector3 p;
            public Vector2 uv;
            public static Vertex Lerp(Vertex a, Vertex b, float t)
            {
                return new Vertex
                {
                    p = Vector3.Lerp(a.p, b.p, t),
                    uv = Vector2.Lerp(a.uv, b.uv, t)
                };
            }
        }

        public static bool Supports(GameObject payload)
        {
            if (payload == null || payload.name != "PRE_DEC_Rug_03_08")
                return false;
            var f = payload.GetComponent<MeshFilter>();
            var folding = payload.GetComponent<RugFold>();
            return f != null && f.sharedMesh != null && (f.sharedMesh.name == "HSHP_MOD_Rug_03" || folding != null);
        }

        static List<Vertex> Clip(List<Vertex> input, float x, bool lower)
        {
            var result = new List<Vertex>();
            if (input.Count == 0)
                return result;
            var previous = input[input.Count - 1];
            var wasInside = lower ? previous.p.x >= x : previous.p.x <= x;
            foreach (var current in input)
            {
                var inside = lower ? current.p.x >= x : current.p.x <= x;
                if (inside != wasInside)
                    result.Add(Vertex.Lerp(previous, current, (x - previous.p.x) / (current.p.x - previous.p.x)));
                if (inside)
                    result.Add(current);
                previous = current;
                wasInside = inside;
            }

            return result;
        }

        void Prepare()
        {
            if (original != null)
                return;
            if (!Supports(gameObject))
                throw new InvalidOperationException("Unsupported folding mesh.");
            filter = GetComponent<MeshFilter>();
            original = filter.sharedMesh;
            if (!original.isReadable || original.subMeshCount != 1 || original.vertexCount != 20)
                throw new InvalidOperationException("Unexpected original rug topology.");
            scale = transform.lossyScale;
            var source = original.vertices;
            var sourceUV = original.uv;
            metric = new Bounds(Vector3.Scale(source[0], scale), Vector3.zero);
            foreach (var p in source)
                metric.Encapsulate(Vector3.Scale(p, scale));
            if (Mathf.Abs(metric.size.x - 1.869588f) > .001f || Mathf.Abs(metric.size.z - .591886f) > .001f || metric.size.y > .005f)
                throw new InvalidOperationException("Unexpected rug dimensions; no resizing is allowed.");
            var cuts = new List<float>
            {
                metric.min.x
            };
            var panel = (metric.size.x - (Panels - 1) * Mathf.PI * Radius) / Panels;
            var cursor = metric.min.x;
            for (var i = 0; i < Panels; i++)
            {
                cursor += panel;
                cuts.Add(cursor);
                if (i == Panels - 1)
                    continue;
                for (var j = 1; j <= 16; j++)
                    cuts.Add(cursor + Mathf.PI * Radius * j / 16);
                cursor += Mathf.PI * Radius;
            }

            cuts[cuts.Count - 1] = metric.max.x;
            var vertices = new List<Vector3>();
            var uvs = new List<Vector2>();
            var indices = new List<int>();
            var originalIndices = original.triangles;
            for (var t = 0; t < originalIndices.Length; t += 3)
            {
                var triangle = new List<Vertex>();
                for (var k = 0; k < 3; k++)
                {
                    var index = originalIndices[t + k];
                    triangle.Add(new Vertex { p = Vector3.Scale(source[index], scale), uv = sourceUV[index] });
                }

                for (var slab = 0; slab < cuts.Count - 1; slab++)
                {
                    var polygon = Clip(Clip(triangle, cuts[slab], true), cuts[slab + 1], false);
                    for (var k = 1; k + 1 < polygon.Count; k++)
                    {
                        if (Vector3.Cross(polygon[k].p - polygon[0].p, polygon[k + 1].p - polygon[0].p).sqrMagnitude < 1e-18f)
                            continue;
                        foreach (var v in new[]
                        {
                            polygon[0],
                            polygon[k],
                            polygon[k + 1]
                        }

                        )
                        {
                            indices.Add(vertices.Count);
                            vertices.Add(v.p);
                            uvs.Add(v.uv);
                        }
                    }
                }
            }

            rest = vertices.ToArray();
            uv = uvs.ToArray();
            triangles = indices.ToArray();
            work = new Mesh
            {
                name = "AP_RugAccordion",
                indexFormat = UnityEngine.Rendering.IndexFormat.UInt32
            };
            colliders = GetComponents<Collider>();
            colliderEnabled = new bool[colliders.Length];
            for (var i = 0; i < colliders.Length; i++)
                colliderEnabled[i] = colliders[i].enabled;
            foldedCollider = gameObject.AddComponent<MeshCollider>();
            foldedCollider.enabled = false;
        }

        Vector3 Bend(Vector3 p, float angle)
        {
            var panel = (metric.size.x - (Panels - 1) * Mathf.PI * Radius) / Panels;
            var s = Mathf.Clamp(p.x - metric.min.x, 0, metric.size.x);
            var point = Vector2.zero;
            float theta = 0;
            for (var i = 0; i < Panels; i++)
            {
                theta = i % 2 == 0 ? 0 : angle;
                var distance = Mathf.Min(s, panel);
                point += new Vector2(Mathf.Cos(theta), Mathf.Sin(theta)) * distance;
                s -= distance;
                if (s <= 1e-6f || i == Panels - 1)
                    break;
                var turn = Mathf.Min(s, Mathf.PI * Radius);
                var sign = i % 2 == 0 ? 1 : -1;
                var delta = sign * angle * turn / (Mathf.PI * Radius);
                if (angle < 1e-5f)
                    point.x += turn;
                else
                {
                    var r = Mathf.PI * Radius / (sign * angle);
                    point += new Vector2(r * (Mathf.Sin(theta + delta) - Mathf.Sin(theta)), r * (Mathf.Cos(theta) - Mathf.Cos(theta + delta)));
                }

                theta += delta;
                s -= turn;
                if (s <= 1e-6f)
                    break;
            }

            var thickness = p.y - metric.center.y;
            point += new Vector2(-Mathf.Sin(theta), Mathf.Cos(theta)) * thickness;
            return new Vector3(point.x, point.y, p.z);
        }

        public Vector3[] PlannedPoints(bool folded)
        {
            Prepare();
            return Points(folded ? 1 : 0);
        }

        Vector3[] Points(float fraction)
        {
            var points = new Vector3[rest.Length];
            var angle = Mathf.PI * fraction;
            var b = new Bounds(Bend(rest[0], angle), Vector3.zero);
            for (var i = 0; i < points.Length; i++)
            {
                points[i] = Bend(rest[i], angle);
                b.Encapsulate(points[i]);
            }

            var shift = metric.center - b.center;
            for (var i = 0; i < points.Length; i++)
            {
                var v = points[i] + shift;
                points[i] = new Vector3(v.x / scale.x, v.y / scale.y, v.z / scale.z);
            }

            return points;
        }

        void Pose(float fraction)
        {
            work.vertices = Points(fraction);
            work.uv = uv;
            work.triangles = triangles;
            work.RecalculateNormals();
            work.RecalculateBounds();
            filter.sharedMesh = work;
        }

        public IEnumerator Animate(bool fold)
        {
            Prepare();
            if (Completed && Folded == fold)
                throw new InvalidOperationException("Rug already has the requested fold state.");
            Completed = false;
            foreach (var collider in colliders)
                collider.enabled = false;
            foldedCollider.enabled = false;
            var start = Time.time;
            while (Time.time - start < 1.5f)
            {
                var t = Mathf.SmoothStep(0, 1, (Time.time - start) / 1.5f);
                Pose(fold ? t : 1 - t);
                yield return null;
            }

            if (fold)
            {
                Pose(1);
                foldedCollider.sharedMesh = work;
                foldedCollider.enabled = true;
            }
            else
            {
                filter.sharedMesh = original;
                for (var i = 0; i < colliders.Length; i++)
                    colliders[i].enabled = colliderEnabled[i];
            }

            Folded = fold;
            Completed = true;
            Physics.SyncTransforms();
        }
    }
}
