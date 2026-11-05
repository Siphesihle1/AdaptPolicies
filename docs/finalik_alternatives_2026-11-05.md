# Final IK alternatives investigation — 2026-11-05

A replacement appears technically possible, but there is no verified drop-in alternative for VirtualHome's Final IK integration. The most useful first experiment is a narrow grasp/release implementation using Unity's built-in humanoid IK, with a separate interaction coordinator. FastIK is an MIT-licensed solver candidate that passes a source compatibility compilation against the installed Unity2021.3.10f1 references. Neither approach has been integrated or runtime-validated. This work does not fix any remaining dataset entries.

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
