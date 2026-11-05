# Final IK alternatives investigation — 2026-11-05

A replacement appears technically possible, but there is no verified drop-in alternative for VirtualHome's Final IK integration. The built-in IK experiment now passes an isolated grasp/release trajectory with the original Male2 rig. A separate source-player build also succeeds using the installed player's compiled IK code, but missing model packs make its scenes incompatible with the dataset. Current native repairs therefore use a separate copy of the official player with its original IK and assets intact; see the follow-up below.

## What VirtualHome requires

Inspected upstream revision `8462a29eb8b3b75b49e5be6eaa84b34536c21d41`:

- `CharacterControl.cs` requires `FullBodyBipedIK` and `InteractionSystem`. It assigns targets and weights for hands, thighs, shoulders and body; sitting changes relative-hand weights; door actions access an arm chain. These are broader requirements than solving a single arm.
- `HandInteraction.cs` loads serialized `InteractionObject` hand-pose prefabs, copies weight curves/multipliers/events, and wires messages to pickup/activation callbacks. Grasping and switching depend on those events, not only the resulting bone positions.
- `ScriptExecution.cs` and `TestDriver.cs` select left/right effectors and invoke the character interaction routines. `BlendHandRelativePos.cs` adjusts hand weights from Animator state callbacks.
- `skip_animation=true` sets character speed to150 and adjusts transitions. It still calls interaction execution and waits on `InteractionSystem.inInteraction`; it does not eliminate Final IK. `skip_execution=true` would skip the actions and cannot serve as native validation.

Replacing the dependency therefore needs a solver backend, interaction timing/callback coordinator, hand-pose data conversion, and preservation of attachment/release and navigation behavior. Empty compatibility classes or accepting actions without executing their effects would not satisfy this requirement.

## Candidate approaches

**Built-in Animator IK:** Unity2021.3 supports hand/foot target positions and rotations, look-at targets and body positioning for a correctly configured Humanoid Avatar. The actual `Male2.prefab` references `athlet_male.fbx`, whose import metadata has animationType3 (Humanoid). This supports a feasibility experiment without adding another package. It does not prove the runtime Avatar is valid, the Animator's IK pass is enabled, or that shoulder/thigh/full-body behavior matches Final IK. The interaction coordinator and hand-pose conversion are still required. [Unity documentation](https://docs.unity3d.com/2021.3/Documentation/Manual/InverseKinematics.html).

**FastIK/SimpleIK:** inspected a separate, read-only clone at `c3af974d047bd1d5f8971144f2aec95da2a8030c`. Its license is MIT, and the sample project targets Unity2019.1.5f1. Compiled all three core scripts (`FastIKFabric`, `FastIKCCD`, `FastIKLook`) using the installed Editor's Roslyn compiler and generated Unity2021.3.10f1 reference response file; compilation exits0 and produces an external compatibility DLL. All VirtualHome source files were excluded from this standalone check. This confirms C# API compatibility, not runtime solver quality or VirtualHome compatibility. Independent limb chains do not supply the existing interaction event system or a full-body biped solver. [Repository](https://github.com/ditzel/SimpleIK).

**Unity Animation Rigging:** its Two Bone IK and other constraints provide a maintained constraint-based route for replacing portions of the rig. Official package registry metadata for1.1.1 and1.2.1 lists minimum Unity2020.2.0a16, making them candidates for this Editor; neither version was installed or compiled here. Its package has its own Unity license and should not be described as MIT. New constraints, rig setup, event coordination and data migration would be necessary. [Package documentation](https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.2/manual/index.html), [Two Bone IK](https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.2/manual/constraints/TwoBoneIKConstraint.html), [package license](https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.2/license/LICENSE.html).

**OpenIK:** MIT licensed with multiple solvers, but its current0.9.2 package declares Unity6000.0 as minimum. It is not suitable for direct installation in the pinned2021 project; backporting would add separate work. No backport was attempted. [Package manifest](https://github.com/WouterApts/openik-unity/blob/main/package.json).

## Suggested validation sequence

First prove one real grasp/hold/release trajectory using the existing Male2 rig, one existing object and a custom interaction coordinator. Require the expected hand/object attachment, correct instance, terminal relation and a completed native response. Exercise callbacks at both ordinary and accelerated speeds, and reject unsupported interactions explicitly.

Then test switch activation, hand-pose transitions, two-hand occupancy, sitting and door navigation. A compiling solver alone is insufficient. Before adopting any replacement, compare native scene identities/geometry and replay previously passing annotations as well as all69 entries. A replacement changes the simulator implementation and requires its own version/provenance; equivalence with official-v2.3.0 must not be assumed.

Local evidence: `outputs/local/finalik_alternative_investigation/compatibility-inputs.json`, `fastik-compiler.log`, and the isolated compatibility DLL. The clone, response file and diagnostics scripts remain under the external AdaptPolicies temporary directory. No project package installation, native asset/source patch, dependency version change, Editor launch, task replay or simulator replacement was performed in this investigation.

## Follow-up: working build and scene-preserving repair route

The separate built-in IK prototype validates the original Male2 Avatar as valid
and Humanoid, rejects an unreachable target, and completes reach/carry/release
with a primitive cube. It records480 IK callbacks. It does not validate legacy
interaction callbacks or any VirtualHome annotation. Exact C# sources and
sanitized logs are in `outputs/local/ik_grasp_prototype/`.

Read-only inspection of official v2.3.0's `Assembly-CSharp-firstpass.dll` found
the original RootMotion/FinalIK runtime classes. A local compatibility candidate
renames the assembly, removes duplicate non-RootMotion types, and retains all2110
methods and2246 fields unchanged, verified by a separate instruction/field audit.
Five inherited components restore original prefab script GUIDs. The existing
Editor PID22700 recompiles, exits Safe Mode, and validates Male2 plus all28
hand-pose prefabs. No additional Editor window was launched in this follow-up.

The fixed-scene source player builds successfully using that candidate: zero
errors,44 warnings,456.5s. Known DunGen tile/doorway components are removed from
external build-copy prefabs while retaining game objects and geometry; originals
are backed up. This is a local binary reuse experiment, not an open-source
replacement implementation. No binary is committed or redistributed.

Native comparison rejects that source player: scenes0/1/2 contain258/240/298
non-character nodes versus443/319/400 in the installed player, with different IDs
and structural edges. Editor inspection finds missing meshes in135 of142 targeted
entries. Their GUIDs have no asset mapping in the checkout. Its `.gitignore`
excludes Complete_Home_Interior_Pack and ModernHouseInteriorProps in addition to
RootMotion and DunGen. The source player is not adopted or used to remap datasets.
Evidence: `outputs/local/local_runtime_build/` and
`outputs/local/local_runtime_scene_comparison/`.

Instead, a separately copied official player receives a read-only managed graph
diagnostic hook. All three scenes match the original static metadata, IDs,
transforms, bounding boxes and structural edges exactly at four decimal places
(character nodes and transient CLOSE/FACING edges excluded). Its assets and IK
remain intact. Diagnostics establish that hanging scene0 shirts lack colliders;
window/curtain/folder/bin/washer objects lack native opening switches. This is
direct component evidence, beyond graph affordance metadata.

The first accepted native repair supplies the existing horizontal grab pose for
mesh-only hanging shirts while preserving the original method for other objects.
An earlier collider candidate was rejected because it added six incorrect
hanger-to-shirt ON edges. The accepted repair preserves initial scenes and passes
the nine-action clothes-to-bed annotation and evaluator. Reproducible source,
explicit activation and scoring implications are documented in
[`helper-scripts/native-repairs/README.md`](../helper-scripts/native-repairs/README.md).
The original player installation, packages and Python versions remain unchanged.

## Exact headless failure

After successful `unity auth login`, CLI status reports signedIn=true/OAuth and active Unity Personal. Ran the following from the external upstream checkout through the required Zsh wrapper, using the user's `unity` CLI in PATH:

```zsh
unity build 'C:/Users/bbdnet2399/AppData/Local/Temp/AdaptPolicies/upstream-virtualhome-unity' \
  --target StandaloneLinux64 \
  --editor-path 'C:/Program Files/Unity 2021.3.10f1/Editor/Unity.exe' \
  --output-path 'C:/Users/bbdnet2399/AppData/Local/Temp/AdaptPolicies/unity-baseline-build/virtualhome.x86_64' \
  --log-file 'C:/Users/bbdnet2399/AppData/Local/Temp/AdaptPolicies/unity-baseline-build/unity-cli-build.log' \
  --no-tail --timeout 180 --non-interactive --format json
```

The Editor log reports:

```text
BatchMode: Unity has not been activated with a valid License. Could be a new activation or renewal...
Exiting without the bug reporter. Application will terminate with return code 1
```

CLI exits6 with `COMMAND_FAILED` and `Build failed (exit 1)`. This occurs before source compilation. No new licensing retry was performed during this alternatives investigation. The startup licensing issue remains separate from missing source dependencies. Non-batch Editor startup works; it does not establish headless build capability.
