# Local native simulator repairs

This tool builds the `adaptpolicies-native-repairs-v8` patch for a **separate copy** of
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

The `folder-opening` feature separates the existing binder's accessible cover
from its body: all 300 original triangles remain in exactly one part, with their
original vertex attributes and materials. Native Open hinges the cover110 degrees;
Close restores it. Mesh colliders follow the real cover and body, while the
original volume box becomes a trigger. The initial semantic bounds stay unchanged.

For paper insertion into these binders, the native planner checks that the cover
is open and that the visible paper vertices fit between the covers. It also
understands a planned Open before PutIn in a single script. Original held-object
checks remain in place. The original hand interaction and release execute the
placement. A registered release orientation survives the original interaction
factory's yaw-only reset; unrelated hand interactions have no registered override.
The filed paper's original box collider is aligned with its visible mesh, fixing
the asset's offset collision bounds. Graph edges and action success are produced
by the native simulator. No INSIDE relation or success response is supplied by
the repair.

The `bin-carry` feature permits the known small `Garbage_can_8` asset through the
native class pickup gate without changing class properties or scene metadata.
Its original mesh, dimensions, IK pickup and hand attachment are retained.
The geometry guard requires the expected1320-vertex mesh, bounded dimensions and
an empty interior. A second planner guard also applies to existing interactions,
rejects repeat grabs and checks reach. Original free-hand and navigation checks
still run. Other prefabs retain the original pickup rules. Symbolic pickup has
the corresponding narrow exception for an empty MOVABLE bin of this prefab;
proximity, enclosure and free-hand checks remain required.

The kitchen door's native open-handle position is displaced from its fixed
doorway. For this one door prefab in the kitchen, the approach uses the midpoint
of its original doorway endpoints, the normal toward the kitchen and a0.4m
standoff. The original path search, collision checks and walking execute the
approach. The door leaf, interaction handle and scene metadata are unchanged.

The `sink-release-pose` feature plans the known frying pan and washing-liquid
bottle's sink placements from their full visible meshes in flat/upright release
poses aligned with the sink. The original planner otherwise measures the rotated,
held objects, whose enlarged world bounds can reject fitting placements.
Native surface rays and obstruction checks still
select candidate positions; a further check keeps the entire visible footprint
inside the sink surface. The same checked rotation is registered for the native
IK release, surviving the interaction factory's yaw reset. No scale, collider,
sink mesh, graph edge or success response is substituted. Other payloads and
destinations retain the original planner.

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
`ADAPTPOLICIES_NATIVE_REPAIRS=shirt-grab,window-curtains,window-opening,lidless-bin-colliders,folder-opening,bin-carry,sink-release-pose,washer-opening` in the simulator process environment.
Record the manifest with every replay; this is a custom runtime, not stock v2.3.0.

Optional `ADAPTPOLICIES_NATIVE_DIAGNOSTICS` names a directory for read-only scene
snapshots at graph creation/update, including live transforms and renderer bounds.
Paper diagnostics also include world vertices; mesh diagnostics include world
rotation and scale for independent containment checks in the binder's local frame.
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
`outputs/local/lidless_bin_negative_v4/`. At v4, six of3356 original methods had
narrow hooks and3350 were unchanged; six original failures remained.
The final all69 replay is still pending.

## Binder repair validation

The original seven paper-task actions and binder204 destination are unchanged.
The task passes native and symbolic execution. Three repeated Open/Close cycles
on each of binders203/204/453 verify110-degree motion and restoration. Both upright
and flat binders accept a single native Open/PutIn/Close script, retain a native
INSIDE relation after closing, contain all1057 visible paper vertices between
the covers, and release the held paper. Closed-folder and unheld-paper attempts
are rejected. All three original initial scenes remain equivalent.

Only train reference graph4's stale paper450 INSIDE livingroom335 edge changes
to bedroom73, following its unchanged receiving binder204. All annotations,
other reference graphs, protected graphs1/10, mapping manifests and the original
archive are preserved. This is a reference consistency correction, not an
execution or model-performance improvement.

Evidence: `outputs/local/folder_main_validation_v6/`. Nine targeted annotations
pass every native and symbolic action. Eight task regressions score all four
metrics1. The fresh paper replay has Exec/Precision1, PSR7/9 and SR0: its two
unsatisfied reference goals are unrelated `clock FACING tv` and `tv FACING clock`.
The physical filing goals are satisfied. Investigating these initial/goal relation
differences remains a separate evaluation-consistency issue; no FACING reference
edges or scoring formulas were changed to hide it. Python tests:81 passed.
Eight of3356 original methods have narrow hooks;3348 are unchanged.
Five original native-action failures remain, alongside this scoring issue.
The required final all69 replay and runtime adoption are still pending.

## Empty-bin carry validation

The user clarified “take out the trash” as carrying the empty bin to the kitchen
doorway. Its annotation now walks to kitchen205, finds bin229, grabs it and walks
to door224. All nine original subtask keys remain. Only train reference graph11
changes: the bin is held and near the character, while door224 and the lidless
bin retain their initial OPEN and CLOSED metadata respectively. The old goals
for opening the bin and closing the door do not describe this clarified task.
Scoring formulas are unchanged; the reference correction is separate from the
new physical pickup capability.

Evidence: `outputs/local/bin_carry_main_validation_v9/` and
`outputs/local/bin_carry_main_validation_v10/`. Three repeated carries retain
native hand attachment and original scale, move the visible bin more than1m,
and end with the character in the kitchen0.4m from the fixed doorway. Filled,
unsupported-prefab, full-hands and duplicate-grab controls reject pickup.
All three initial scenes remain equivalent. Nine other task regressions pass
every native/symbolic action and all four metrics; the fresh corrected-reference
trash replay is recorded separately. The older trash trace requiring an OPEN
bin is preserved, with PSR5/6, SR0, Precision/Exec1.

Python tests:86 passed. Eleven of3356 original methods have narrow hooks and
3345 are unchanged. Only the two declared managed DLLs differ from the original
player. All other annotation/reference records, protected graphs1/10, mapping
manifests and original archive are preserved. Four original native task failures
remain: clothes washing, pan washing, rug washing and brushing teeth. The varying
clock/TV FACING goals remain an evaluation-consistency backlog item even though
the latest paper regression passes. Native Close door224 while holding the bin
also failed during an earlier probe; the clarified task does not require Close.
No fix is claimed for that separate action. The final all69 replay and default
runtime adoption remain pending.

## Sink release-pose validation

The original sixteen frying-pan washing actions are unchanged. Pan269 and soap267
now both release through native IK onto sink247; their complete367- and569-vertex
visible meshes fit its footprint, touch its surface and are no longer held.
The existing runtime washing conditions mark the pan WASHED. Neither object is
rescaled. The first pan-only candidate exposed the same held-pose problem for
the soap bottle; it is retained as a failed complete-task candidate.

Evidence: `outputs/local/pan_main_validation_v1/` records seven physical pan
placements across three repeated pickup/reinsert cycles and a batch script,
plus rejection of an unheld placement. `outputs/local/pan_main_validation_v2/`
records the complete unchanged pan annotation, final live pan/soap vertex checks
and fourteen successful task regressions, including all other washing tasks
that previously completed. All three initial scenes remain equivalent.

Only train reference graph13 changes: its two INSIDE sink relations for the pan
and soap become ON, matching the original PutBack commands and the native sink's
zero-height surface. The pan gains an explicit WASHED goal. On the same frozen
successful trace, the old reference satisfies10/12 goals and415/415 preservation;
the corrected reference satisfies13/13 goals and415/415 preservation. Evaluator
formulas and every annotation remain unchanged. This reference correction and
strengthened washing goal are distinct from improved native executability.

The fresh corrected-reference replay in `outputs/local/pan_reference_validation_v2/`
passes16/16 actions and scores PSR/SR/Precision/Exec1. The fourteen regressions
also score all four metrics1. Python86 tests pass. The patch still changes only
eleven of3356 original methods;3345 are unchanged. All other player files are
byte-identical to the original. Protected graphs1/10, every other reference,
all mapping manifests and the original archive remain preserved.

Three original native failures remain: clothes washing, rug washing and brushing
teeth. The variable clock/TV FACING goals and the earlier held-bin door-Close
failure remain separate backlog items. Final all69 replay and runtime adoption
are still required; targeted tests are not an aggregate69-entry result.

## Washer repair validation

The `washer-opening` feature partitions the original textured front surface into
a fixed housing and a100-degree hinged door, interpolating the original UVs and
normals. Their combined surface area equals the original. An inner door backing
and physical cylindrical drum complete the cavity. Original player asset files
remain unchanged; these meshes are constructed in the separate runtime. Native
Open/Close switches drive the hinge. A native power switch toggles an indicator
and drives drum rotation while powered; switching off stops it.

Only the verified clothes-pile prefab is admitted to the new drum placement.
The planner checks every visible vertex, actual radial/depth limits, other
obstacles and an open door. Native held-object checks, IK and release remain.
The release rotation accounts for the original parent transform, matching the
native release implementation's local-rotation assignment. Closed-door, unheld
and oversized unfolded-rug insertions reject. No payload scale is changed.

The clothes annotation omits only unsupported Open closet374, retaining all
subtask keys and nineteen other actions. Only train reference graph0 changes:
closet374 retains its original CLOSED state, and clothes407 must be WASHED.
Washing inference now requires a closed, powered machine and adds WASHED only
once across repeated state updates. Its tests cover open/unpowered machines,
surface contact and unrelated machine IDs.

Evidence: `outputs/local/washer_main_validation_v2/`. Three full physical cycles
keep all266 visible clothes vertices inside through closing, power cycling and
reopening, with less than3mm radial clearance and original scale. Native
containment persists, retrieval succeeds, the drum moves during the powered
interval and remains stationary after switching off. An eleven-action batch
cycle and Open/Close/power controls in all three scenes also pass. Initial scenes
remain equivalent. Python89 tests pass. Only the two declared DLLs differ from
the original player; eleven original methods are hooked and3345 unchanged.

The fresh clothes replay passes19/19 native/symbolic actions and all four metrics1,
with a single WASHED state. All sixteen targeted annotations execute completely
with Exec/Precision1. Eleven score all four metrics1. Five have missing unrelated
FACING reference goals, including clock/TV and table objects facing the clock;
the exact tasks, scores and missing conditions are retained in validation-summary.
This evaluation-consistency issue remains unresolved. No FACING goals or scoring
formulas were changed. Protected graphs1/10, every other annotation/reference
record, mapping manifests and the original archive remain preserved.

Rug washing and brushing teeth remain unsupported. Explicit folding actions are
approved for further work, with their planning-interface impact to be documented.
The user declined toothbrushing-specific actions. No new vocabulary actions have
been added. Full all69 replay and final runtime adoption remain pending.
