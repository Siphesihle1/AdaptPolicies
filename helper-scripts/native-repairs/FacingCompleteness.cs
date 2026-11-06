using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.CompilerServices;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public static class FacingCompleteness
    {
        sealed class Phase { public int Value=-1; }
        static readonly ConditionalWeakTable<EnvironmentGraph,Phase> Phases=new ConditionalWeakTable<EnvironmentGraph,Phase>();
        static readonly FieldInfo EdgeSet=typeof(EnvironmentGraphCreator).GetField("edgeSet",BindingFlags.Instance|BindingFlags.NonPublic);
        static bool Eligible(EnvironmentObject node)
        {
            if(node.transform==null || node.category=="Rooms" || node.category=="Doors" || node.class_name=="character")return false;
            foreach(var ignored in EnvironmentGraphCreator.IGNORE_IN_EDGE_OBJECTS)if(node.class_name==ignored)return false;
            return true;
        }
        public static void Refresh(EnvironmentGraph graph,EnvironmentGraphCreator creator)
        {
            if(!NativeRepairFeatures.Enabled("facing-completeness"))return;
            var phase=Phases.GetOrCreateValue(graph);var current=creator.characters.Count==0?0:1;
            if(phase.Value==current)return;
            Physics.SyncTransforms();
            var nodes=new List<EnvironmentObject>();var ids=new HashSet<int>();
            foreach(var node in graph.nodes)if(Eligible(node)){nodes.Add(node);ids.Add(node.id);}
            nodes.Sort((a,b)=>a.id.CompareTo(b.id));
            var edges=(ISet<Tuple<int,int,ObjectRelation>>)EdgeSet.GetValue(creator);
            var removed=0;
            for(var i=graph.edges.Count-1;i>=0;i--)
            {
                var edge=graph.edges[i];
                if(edge.relation_type!=ObjectRelation.FACING || !ids.Contains(edge.from_id) || !ids.Contains(edge.to_id))continue;
                edges.Remove(Tuple.Create(edge.from_id,edge.to_id,edge.relation_type));graph.edges.RemoveAt(i);removed++;
            }
            var body=new List<Collider>();var assetRoots=new HashSet<Transform>();
            foreach(var node in graph.nodes)if(node.transform!=null && node.class_name!="character")assetRoots.Add(node.transform);
            foreach(var actor in creator.characters.Keys)
            {
                foreach(var collider in actor.transform.GetComponentsInChildren<Collider>(true))
                {
                    if(!collider.enabled)continue;
                    var payload=false;
                    for(var parent=collider.transform;parent!=null && parent!=actor.transform;parent=parent.parent)
                        if(assetRoots.Contains(parent)){payload=true;break;}
                    if(!payload)body.Add(collider);
                }
            }
            var before=graph.edges.Count;
            try
            {
                foreach(var collider in body)collider.enabled=false;
                Physics.SyncTransforms();
                foreach(var look in nodes)
                {
                    if(!look.properties.Contains("LOOKABLE"))continue;
                    foreach(var subject in nodes)
                        if(subject!=look && (subject.bounding_box.bounds.center-look.bounding_box.bounds.center).sqrMagnitude<=creator.EdgeRadius2)
                            creator.Facing(look,subject);
                }
            }
            finally
            {
                foreach(var collider in body)if(collider!=null)collider.enabled=true;
                Physics.SyncTransforms();
            }
            phase.Value=current;
            Debug.Log("AP facing completeness: phase="+current+" old="+removed+" recomputed="+(graph.edges.Count-before)+" bodyColliders="+body.Count);
        }
    }
}
