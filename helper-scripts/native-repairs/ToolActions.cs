using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using RootMotion.FinalIK;
using StoryGenerator.Utilities;
using UnityEngine;

namespace AdaptPolicies.NativeRepairs
{
    public sealed class ToolEffect : MonoBehaviour
    {
        public bool Applied;
        public bool Used;
        public GameObject Paste;
    }

    public static class ToolActions
    {
        static readonly FieldInfo Controller = typeof(ScriptExecutor).GetField("characterControl",BindingFlags.Instance | BindingFlags.NonPublic);
        static readonly MethodInfo Selector = typeof(ScriptExecutor).GetMethod("GetObjectSelector",BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
        public static readonly Vector3 Bristles = new Vector3(0,-.021487f,.097286f);
        public static readonly Vector3 Nozzle = new Vector3(0,.016778f,.06014f);
        static bool Brush(GameObject go) { return go != null && go.name == "PRE_PRO_Toothbrush_01"; }
        static GameObject ResolveHeld(ScriptExecutor executor,State state,ScriptObjectName name)
        {
            var selected=state.GetScriptGameObject(name);
            if(selected != null) return selected;
            if(Selector == null) throw new InvalidOperationException("Native object selector is unavailable.");
            var selector=(IObjectSelector)Selector.Invoke(executor,new object[]{name.Name,name.Instance});
            foreach(var key in new[]{"RIGHT_HAND_OBJECT","LEFT_HAND_OBJECT"})
            {
                var go=state.GetGameObject(key);
                if(go == null || !selector.IsSelectable(go)) continue;
                state.AddScriptGameObject(name,go,go.transform.position,state.InteractionPosition,true,OpenStatus.UNKNOWN);
                return go;
            }
            return null;
        }
        static bool Held(State s, GameObject go) { return go != null && (s.GetGameObject("RIGHT_HAND_OBJECT") == go || s.GetGameObject("LEFT_HAND_OBJECT") == go); }
        static bool Open(State s, ScriptObjectName name, GameObject tube)
        {
            // Native Find/Grab replace object data with UNKNOWN opening status.
            // Recover the most recent explicit opening state along this plan.
            for(var previous=s;previous != null;previous=previous.Previous)
            {
                ScriptObjectData data;
                if(previous.GetScriptGameObjectData(name,out data) && data.GameObject == tube && data.OpenStatus != OpenStatus.UNKNOWN)
                    return data.OpenStatus == OpenStatus.OPEN;
            }
            var cap = ToothpasteOpeningRepair.Cap(tube);
            return cap != null && Quaternion.Angle(cap.localRotation,Quaternion.identity)>130;
        }
        public static IEnumerable<IStateGroup> Process(ScriptExecutor executor, ManipulationAction action, State current)
        {
            var source = ResolveHeld(executor,current,action.Name);
            var brush = action.Kind == 34 ? ResolveHeld(executor,current,action.Target) : source;
            var effect = brush == null ? null : brush.GetComponent<ToolEffect>();
            var pending = brush == null ? null : current.GetObject("AP_APPLIED_"+brush.GetInstanceID());
            var applied = pending is bool ? (bool)pending : effect != null && effect.Applied;
            var valid = NativeRepairFeatures.Enabled("tool-manipulation") && Brush(brush) && Held(current,brush);
            if (action.Kind == 34) valid &= ToothpasteOpeningRepair.IsTube(source) && Held(current,source) && source != brush && Open(current,action.Name,source) && !applied;
            else valid &= applied;
            if (!valid)
            {
                Debug.Log("AP tool gate: source="+(source == null ? "null" : source.name)+" brush="+(brush == null ? "null" : brush.name)+" sourceHeld="+Held(current,source)+" brushHeld="+Held(current,brush)+" feature="+NativeRepairFeatures.Enabled("tool-manipulation")+" applied="+applied);
                executor.report.AddItem("PROCESS TOOL","Unsupported tool pair, unheld tool, closed source or unprepared/already prepared tool.");
                yield break;
            }
            var next = new State(current,action,current.InteractionPosition,s=>Execute(executor,s));
            next.AddObject("AP_APPLIED_"+brush.GetInstanceID(),action.Kind==34);
            yield return next;
        }
        public static void UpdateNode(EnvironmentObject node)
        {
            var effect = node.transform == null ? null : node.transform.GetComponent<ToolEffect>();
            if (effect == null) return;
            if (effect.Applied) node.states.Add((ObjectState)12); else node.states.Remove((ObjectState)12);
            if (effect.Used) node.states.Add((ObjectState)13);
        }
        static IEnumerator Execute(ScriptExecutor executor, State state)
        {
            var action = (ManipulationAction)state.Action;
            var source = state.GetScriptGameObject(action.Name);
            var brush = action.Kind == 34 ? state.GetScriptGameObject(action.Target) : source;
            var actor = (StoryGenerator.CharacterControl)Controller.GetValue(executor);
            var ik = actor.GetComponentInChildren<FullBodyBipedIK>();
            if (ik == null || ik.references.head == null)
            {
                executor.report.AddItem("EXECUTION TOOL","Native hand/head IK is unavailable.");
                yield break;
            }
            var applying = action.Kind == 34;
            var effect = brush.GetComponent<ToolEffect>() ?? brush.AddComponent<ToolEffect>();
            if (!applying && (!effect.Applied || effect.Paste == null))
            {
                executor.report.AddItem("EXECUTION TOOL","No physically applied paste remains on the tool.");
                yield break;
            }
            var cap = applying ? ToothpasteOpeningRepair.Cap(source) : null;
            if (applying && (cap == null || Quaternion.Angle(cap.localRotation,Quaternion.identity)<130))
            {
                executor.report.AddItem("EXECUTION TOOL","The physical source cap is closed.");
                yield break;
            }
            var brushRight = state.GetGameObject("RIGHT_HAND_OBJECT") == brush;
            using (var motion = new ToolMotion(ik,brush,brushRight,applying ? source : null))
            {
                var started = Time.time;
                GameObject deposited = null;
                while (Time.time-started<4.5f)
                {
                    motion.Elapsed = Time.time-started;
                    if (applying && deposited == null && motion.ContactTime >= .6f) deposited = Deposit(source,brush);
                    yield return null;
                }
                motion.Save();
                if (motion.ContactTime < .6f || (!applying && motion.StrokeRange < .015f))
                {
                    executor.report.AddItem("EXECUTION TOOL","Physical alignment/contact was not completed; no effect applied.");
                    yield break;
                }
                if (applying)
                {
                    effect.Paste = deposited; effect.Applied = deposited != null;
                }
                else
                {
                    UnityEngine.Object.Destroy(effect.Paste);effect.Paste=null;effect.Applied=false;effect.Used=true;
                }
            }
            yield return null;
        }

        static GameObject Deposit(GameObject source,GameObject brush)
        {
            var paste = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            paste.name = "AP_AppliedPaste";
            paste.transform.SetParent(brush.transform,false);
            paste.transform.localPosition = Bristles + Vector3.down*.0015f;
            paste.transform.localRotation = Quaternion.Euler(90,0,0);
            paste.transform.localScale = new Vector3(.003f,.012f,.003f);
            paste.GetComponent<Collider>().isTrigger = true;
            var material = new Material(Shader.Find("Standard"));material.color = new Color(.94f,.98f,1);
            paste.GetComponent<Renderer>().material = material;
            var filter = source.GetComponent<MeshFilter>(); var mesh = UnityEngine.Object.Instantiate(filter.sharedMesh);
            var points = mesh.vertices;
            for (var i=0;i<points.Length;i++) if(points[i].z<.04f) points[i].x *= .99f;
            mesh.vertices=points;mesh.RecalculateNormals();mesh.RecalculateBounds();filter.sharedMesh=mesh;
            source.GetComponent<MeshCollider>().sharedMesh=mesh;
            return paste;
        }
    }

    [DefaultExecutionOrder(32000)]
    public sealed class ToolPoseDriver : MonoBehaviour
    {
        public Action Tick;
        void LateUpdate() { if(Tick != null) Tick(); }
    }

    sealed class ToolMotion : IDisposable
    {
        sealed class HandTarget
        {
            public IKEffector effector;
            public Transform previousTarget;
            public float previousPositionWeight, previousRotationWeight;
            public Vector3 initialPosition, localToolPosition;
            public Quaternion initialRotation, localToolRotation;
            public Transform target;
            public GameObject tool;
            public HandTarget(FullBodyBipedIK ik,GameObject tool,bool right)
            {
                this.tool=tool;effector=right ? ik.solver.rightHandEffector : ik.solver.leftHandEffector;
                var hand=effector.bone;
                if (!GameObjectUtils.IsInPath(hand.gameObject,tool.transform)) throw new InvalidOperationException("The tool must remain attached to its native hand.");
                localToolPosition=Vector3.Scale(hand.InverseTransformPoint(tool.transform.position),hand.lossyScale);
                localToolRotation=Quaternion.Inverse(hand.rotation)*tool.transform.rotation;
                initialPosition=hand.position;initialRotation=hand.rotation;
                previousTarget=effector.target;previousPositionWeight=effector.positionWeight;previousRotationWeight=effector.rotationWeight;
                target=new GameObject("AP_ToolHandTarget").transform;
            }
            public void Set(Vector3 contact,Vector3 localContact,Quaternion rotation,float weight)
            {
                var root=contact-rotation*Vector3.Scale(localContact,tool.transform.lossyScale);
                var handRotation=rotation*Quaternion.Inverse(localToolRotation);
                var handPosition=root-handRotation*localToolPosition;
                target.position=Vector3.Lerp(initialPosition,handPosition,weight);target.rotation=Quaternion.Slerp(initialRotation,handRotation,weight);
                effector.target=target;effector.positionWeight=1;effector.rotationWeight=1;
            }
            public void Restore()
            {
                Pause();
                UnityEngine.Object.Destroy(target.gameObject);
            }
            public void CaptureStart() { initialPosition=effector.bone.position;initialRotation=effector.bone.rotation; }
            public void Pause()
            {
                effector.target=previousTarget;effector.positionWeight=previousPositionWeight;effector.rotationWeight=previousRotationWeight;
            }
        }
        readonly FullBodyBipedIK ik;
        readonly GameObject brush,tube;
        readonly HandTarget brushHand,tubeHand;
        readonly bool brushRight;
        readonly ToolPoseDriver driver;
        readonly Animator[] animators;
        readonly AnimatorCullingMode[] cullingModes;
        readonly SkinnedMeshRenderer[] skins;
        readonly bool[] offscreen;
        bool driving,started;
        readonly List<object> samples=new List<object>();
        float lastSample=-1,strokeMin=float.PositiveInfinity,strokeMax=float.NegativeInfinity;
        int photos;
        Vector3 mouth;
        public float Elapsed,ContactTime;
        public float StrokeRange { get { return strokeMax-strokeMin; } }
        public ToolMotion(FullBodyBipedIK ik,GameObject brush,bool right,GameObject tube)
        {
            this.ik=ik;this.brush=brush;this.tube=tube;brushRight=right;
            var actor=ik.GetComponentInParent<StoryGenerator.CharacterControl>();
            animators=actor.GetComponentsInChildren<Animator>(true);cullingModes=new AnimatorCullingMode[animators.Length];
            for(var i=0;i<animators.Length;i++){cullingModes[i]=animators[i].cullingMode;animators[i].cullingMode=AnimatorCullingMode.AlwaysAnimate;}
            skins=actor.GetComponentsInChildren<SkinnedMeshRenderer>(true);offscreen=new bool[skins.Length];
            for(var i=0;i<skins.Length;i++){offscreen[i]=skins[i].updateWhenOffscreen;skins[i].updateWhenOffscreen=true;}
            brushHand=new HandTarget(ik,brush,right);
            if (tube != null) tubeHand=new HandTarget(ik,tube,!right);
            ik.solver.OnPreUpdate += Targets;
            driver=ik.gameObject.AddComponent<ToolPoseDriver>();driver.Tick=Drive;
        }
        void Drive()
        {
            if(!started) { brushHand.CaptureStart();if(tubeHand != null) tubeHand.CaptureStart();started=true; }
            var previous=ik.solver.IKPositionWeight;
            driving=true;
            try
            {
                ik.solver.IKPositionWeight=1;
                ik.solver.Update();
                Physics.SyncTransforms();
                Observe();
            }
            finally
            {
                driving=false;ik.solver.IKPositionWeight=previous;
                brushHand.Pause();if(tubeHand != null) tubeHand.Pause();
            }
        }
        void Targets()
        {
            if(!driving) return;
            var head=ik.references.head;
            var forward=Vector3.ProjectOnPlane(head.forward,Vector3.up).normalized;
            var right=Vector3.Cross(Vector3.up,forward);
            var weight=Mathf.SmoothStep(0,1,Mathf.Min(Elapsed,4.5f-Elapsed));
            if (tube != null)
            {
                var contact=head.position+forward*.38f-Vector3.up*.35f;
                var rotation=Quaternion.LookRotation(brushRight ? -right : right,Vector3.down);
                brushHand.Set(contact,ToolActions.Bristles,rotation,weight);
                tubeHand.Set(contact+Vector3.up*.002f,ToolActions.Nozzle,Quaternion.LookRotation(Vector3.down,forward),weight);
            }
            else
            {
                mouth=head.position+Vector3.up*.005f+forward*.115f;
                var stroke=Mathf.Sin(Elapsed*Mathf.PI*4)*.012f;
                brushHand.Set(mouth+right*stroke,ToolActions.Bristles,Quaternion.LookRotation(brushRight ? -right : right,forward),weight);
            }
        }
        void Observe()
        {
            var tip=brush.transform.TransformPoint(ToolActions.Bristles);
            var head=ik.references.head;
            var forward=Vector3.ProjectOnPlane(head.forward,Vector3.up).normalized;
            if(tube == null) mouth=head.position+Vector3.up*.005f+forward*.115f;
            var target=tube == null ? mouth : tube.transform.TransformPoint(ToolActions.Nozzle);
            var distance=Vector3.Distance(tip,target);
            if (Elapsed>1.1f && Elapsed<3.4f && distance < (tube == null ? .018f : .006f))
            {
                ContactTime += Time.deltaTime;
                if(tube == null)
                {
                    var right=Vector3.Cross(Vector3.up,Vector3.ProjectOnPlane(ik.references.head.forward,Vector3.up).normalized);
                    var stroke=Vector3.Dot(tip-mouth,right);
                    strokeMin=Mathf.Min(strokeMin,stroke);strokeMax=Mathf.Max(strokeMax,stroke);
                }
            }
            if (Elapsed-lastSample>.1f)
            {
                lastSample=Elapsed;
                samples.Add(new { time=Elapsed,distance=distance,tip=new[]{tip.x,tip.y,tip.z},target=new[]{target.x,target.y,target.z},contact=ContactTime });
            }
            if ((photos == 0 && Elapsed > 1.7f) || (photos == 1 && Elapsed > 2.5f))
            {
                Photo((tip+target)*.5f,forward);photos++;
            }
        }
        void Photo(Vector3 center,Vector3 forward)
        {
            var output=Environment.GetEnvironmentVariable("ADAPTPOLICIES_TOOL_DIAGNOSTICS");
            if(string.IsNullOrEmpty(output)) return;
            Directory.CreateDirectory(output);
            DumpRenderBindings(output);
            var go=new GameObject("AP_ToolDiagnosticCamera");var camera=go.AddComponent<Camera>();camera.enabled=false;
            var right=Vector3.Cross(Vector3.up,forward);
            camera.transform.position=center+forward*(photos == 0 ? .55f : .18f)+right*(photos == 0 ? .25f : .55f)+Vector3.up*.1f;
            camera.transform.rotation=Quaternion.LookRotation(center-camera.transform.position);camera.fieldOfView=45;
            var target=RenderTexture.GetTemporary(640,640,24);var old=RenderTexture.active;
            Texture2D image=null;
            try
            {
                camera.targetTexture=target;camera.Render();RenderTexture.active=target;
                image=new Texture2D(640,640,TextureFormat.RGB24,false);image.ReadPixels(new Rect(0,0,640,640),0,0);image.Apply();
                File.WriteAllBytes(Path.Combine(output,(tube == null ? "use" : "apply")+"-"+DateTime.UtcNow.Ticks+".png"),ImageConversion.EncodeToPNG(image));
            }
            catch(Exception error) { Debug.LogWarning("Tool diagnostic photo failed: "+error); }
            finally
            {
                RenderTexture.active=old;camera.targetTexture=null;RenderTexture.ReleaseTemporary(target);
                if(image != null) UnityEngine.Object.Destroy(image);UnityEngine.Object.Destroy(go);
            }
        }
        static string PathOf(Transform t)
        {
            var path="";
            for(;t!=null;t=t.parent) path=t.name+"#"+t.GetInstanceID()+"/"+path;
            return path;
        }
        void DumpRenderBindings(string output)
        {
            var actor=ik.GetComponentInParent<StoryGenerator.CharacterControl>();
            var renderers=new List<object>();
            foreach(var renderer in UnityEngine.Object.FindObjectsOfType<MeshRenderer>())
            {
                if(renderer.name.IndexOf("Tooth",StringComparison.OrdinalIgnoreCase)<0)continue;
                var p=renderer.transform.position;var b=renderer.bounds;
                renderers.Add(new{name=renderer.name,path=PathOf(renderer.transform),enabled=renderer.enabled,active=renderer.gameObject.activeInHierarchy,staticBatch=renderer.isPartOfStaticBatch,position=new[]{p.x,p.y,p.z},boundsCenter=new[]{b.center.x,b.center.y,b.center.z}});
            }
            var skins=new List<object>();
            foreach(var renderer in actor.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                var bones=new List<object>();
                foreach(var bone in renderer.bones)
                    if(bone != null && (bone.name.Contains("Hand") || bone.name.Contains("Head")))
                    {
                        var p=bone.position;
                        bones.Add(new{name=bone.name,path=PathOf(bone),position=new[]{p.x,p.y,p.z},right=bone==ik.references.rightHand,left=bone==ik.references.leftHand,head=bone==ik.references.head});
                    }
                skins.Add(new{path=PathOf(renderer.transform),mesh=renderer.sharedMesh.name,enabled=renderer.enabled,root=renderer.rootBone==null?null:PathOf(renderer.rootBone),bones=bones});
            }
            var animators=new List<object>();
            foreach(var animator in actor.GetComponentsInChildren<Animator>(true))
                animators.Add(new{path=PathOf(animator.transform),enabled=animator.enabled,hierarchy=animator.hasTransformHierarchy,human=animator.isHuman,culling=animator.cullingMode.ToString()});
            File.WriteAllText(System.IO.Path.Combine(output,"bindings-"+DateTime.UtcNow.Ticks+".json"),Newtonsoft.Json.JsonConvert.SerializeObject(new{ik=PathOf(ik.transform),head=PathOf(ik.references.head),right=PathOf(ik.references.rightHand),left=PathOf(ik.references.leftHand),brush=PathOf(brush.transform),renderers=renderers,skins=skins,animators=animators},Newtonsoft.Json.Formatting.Indented));
        }
        public void Save()
        {
            var output=Environment.GetEnvironmentVariable("ADAPTPOLICIES_TOOL_DIAGNOSTICS");
            if (string.IsNullOrEmpty(output)) return;
            Directory.CreateDirectory(output);
            File.WriteAllText(Path.Combine(output,(tube == null ? "use" : "apply")+"-"+DateTime.UtcNow.Ticks+".json"),Newtonsoft.Json.JsonConvert.SerializeObject(new { contactTime=ContactTime,strokeRange=StrokeRange,samples=samples },Newtonsoft.Json.Formatting.Indented));
        }
        public void Dispose()
        {
            ik.solver.OnPreUpdate -= Targets;
            driver.Tick=null;UnityEngine.Object.Destroy(driver);
            brushHand.Restore();if(tubeHand != null) tubeHand.Restore();
            for(var i=0;i<animators.Length;i++) animators[i].cullingMode=cullingModes[i];
            for(var i=0;i<skins.Length;i++) skins[i].updateWhenOffscreen=offscreen[i];
        }
    }
}
