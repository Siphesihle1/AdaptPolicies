# Local native simulator repairs

This tool builds the `adaptpolicies-native-repairs-v4` patch for a **separate copy** of
the official VirtualHome Linux v2.3.0 player (Unity 2021.2.14f1). It preserves that
player's assets and original IK implementation. It does not rebuild the incomplete
public Unity asset project. No simulator binaries are distributed here.

The hanging `MOD_PRO_Shirt_*` instances have meshes but no colliders. Native
`GetGrabPose` rejects them before interaction execution. With the explicit
`ADAPTPOLICIES_NATIVE_REPAIRS=shirt-grab` setting, the patch supplies the existing
horizontal grab pose for these mesh-only shirts. Navigation, IK, attachment,
release, action responses and all other objects continue through the original
native implementation. Without that feature, the original grab-pose implementation runs.

The `window-curtains` feature installs native Open switches and reversible
scale/position transitions for the existing window-curtain panels. Open gathers
each panel to20% width at the outer edge; Close restores its original transforms.
The native approach direction faces the room. A repaired-opening coroutine wrapper
waits for the real switch transitions to finish before interaction completion,
including accelerated execution. Shower curtains retain their existing behavior.
The `window-opening` feature partitions the two original readable window meshes
into a stationary outer frame and a hinged inner sash with its original glass.
Every original triangle stays in exactly one part, retaining its material and
vertex attributes. Native Open rotates the sash70 degrees into the room; Close
restores it. The contact point stays close enough to the hinge for both actions.
Only original `PRE_Window_*` roots receive interactions; generated sash children
are excluded. No source asset files are replaced. The three features can be
enabled together with a comma-separated setting.

The `lidless-bin-colliders` feature uses the existing hollow meshes of
`Garbage_can_2`, `Garbage_can_6` and `Garbage_can_8` as non-convex mesh colliders.
Existing box colliders become triggers, retaining their metadata bounds while
allowing access to the interior. It adds no lid and does not set an OPEN state.
A narrow native Put hook centers visible payload geometry, checks its vertices
against the interior and actual floor, and selects a fitting target pose for
the original IK release. Unsupported destinations retain their original behavior.

## Build

Run commands through the required `%USERPROFILE%\scripts\zsh-run.cmd` wrapper.
From its Zsh context, call `build.sh` with all three arguments:

```zsh
zsh helper-scripts/native-repairs/build.sh \
  '/c/path/to/original-player-Managed' \
  '/c/Program Files/Unity 2021.3.10f1/Editor' \
  '/c/path/to/separate-patch-output'
```

The first directory is a Windows-accessible copy of the **original** player's
`linux_exec.v2.3.0_Data/Managed` directory. The tool uses the installed Editor's
compiler and Cecil library; it does not launch an Editor or change packages.
It rejects a source `Assembly-CSharp.dll` whose SHA256 differs from
`f8fb0a272bf646aaeefa8df870aba5bda1dec291690191295da235b3c32fb4b0`.

Outputs are `Assembly-CSharp.dll`, `AdaptPolicies.NativeRepairs.dll`, and a hash
manifest. Copy the two DLLs into the `Managed` directory of a separately copied
official player, retaining all other player files. Keep the original installation
unchanged. Set `VIRTUALHOME_SIM_ROOT` to the copied player's directory when using
the existing simulator launcher, and explicitly export
`ADAPTPOLICIES_NATIVE_REPAIRS=shirt-grab,window-curtains,window-opening,lidless-bin-colliders` in the simulator process environment.
Record the manifest with every replay; this is a custom runtime, not stock v2.3.0.

Optional `ADAPTPOLICIES_NATIVE_DIAGNOSTICS` names a directory for read-only scene
snapshots at graph creation/update, including live transforms and renderer bounds.
The original graph API caches some child transforms after articulated movement;
use these live snapshots for physical motion controls. Without the directory,
the diagnostic hooks immediately return. The build
manifest deliberately leaves runtime validation false; compilation is not a
native replay.

## Validation and dataset scope

All static node metadata, IDs, transforms, bounding boxes and structural edges
match the original reference scenes0/1/2 to four decimal places, excluding
character nodes and transient CLOSE/FACING edges. The repaired main annotation
for “get my pants and shirt and place on the bed” completes all9 actions with
native and symbolic success. Final native relations place shirt376 and pants386
on bed109. The evaluator reports PSR/SR/Precision/Exec=1.

The annotation omits unsupported `Open closet374`. Only graph20's closet374 state
changes from OPEN to its original CLOSED state. That removes one incidental
reference target (16 to15 conditions); the scoring formulas are unchanged. This
reference correction must be distinguished from improved native executability.
All other annotation records, graph records, mapping manifests, the original
archive, wash-mug graph10 and cutlery graph1 are preserved.

Both original curtain annotations (train and env2) also pass every native and
symbolic action and report PSR/SR/Precision/Exec=1 without changing their data or
references. Three repeated Open/Close cycles per target verify live width changes,
OPEN/CLOSED states and complete position/scale restoration. The shirt task passes
with both features enabled. Initial scenes0/1/2 remain equivalent.

Evidence: `outputs/local/shirt_grab_repair_main_v1/`,
`outputs/local/official_diagnostic_scene_comparison/`, and
`outputs/local/curtain_main_wait_validation_v2/`, and
`outputs/local/window_final_validation_v3/`. The unchanged four-action test_seen
window annotation passes native and symbolic execution with all four metrics1.
Windows70/91/364 each pass three physical Open/Close cycles, with70-degree sash
rotation, a stationary outer frame, and restoration on Close. Both curtain tasks,
the shirt task, six curtain motion cycles, and all three initial scene comparisons
also pass on the same build.

The last complete stock replay
remains55/69. These targeted tests do not replace the required final all69-entry
replay.

The four fruit-disposal annotations now omit impossible bin Open/Close steps
while retaining real insertion. The lime approaches its coffee table before
pickup. Symbolic insertion/retrieval permits access to the three explicitly
verified lidless prefabs despite their legacy CLOSED metadata; unknown bin
prefabs and other closed containers retain their access restrictions. Native
acceptance still gates every runtime action.

All four disposal tasks pass native and symbolic execution, with all four
metrics1. Live visible bounds are fully inside the bin volume after release;
objects are not held. An oversized-pan control is rejected without an INSIDE
edge. Existing shirt, curtain and window task/motion regressions pass. Python
tests:81 passed, including prefab and access-boundary negatives.

Only four annotation records and test_seen reference graph2's lime room edge
change. The old reference kept lime440 INSIDE livingroom335 after moving it
into kitchen bin229. That edge now targets kitchen205. The old successful trace
had Precision415/416; the corrected reference removes that invalid preservation
condition and adds the correct room goal. A fresh lime replay scores all1.
Scoring formulas are unchanged; this reference effect is not an execution or
LLM-performance improvement. Old reference evidence remains frozen.

Evidence: `outputs/local/lidless_main_validation_v4/`,
`outputs/local/lidless_lime_reference_validation_v4/`,
`outputs/local/lidless_bin_physical_v4/`, and
`outputs/local/lidless_bin_negative_v4/`. Six of3356 original methods have narrow
hooks;3350 are unchanged. Six original failures remain. The final all69 replay
is still pending.
