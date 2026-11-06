# Dataset validation — 2026-11-05

**The fully-valid-dataset objective remains open.** The latest complete batch attempted all 69 entries: 55 completed every native/runtime action and 14 stopped on native failures. The run's frozen references passed 51/55 completed trajectories. After the final reference-only correction, all 55 completed trajectories pass strict SR in each of two independently executed full batches. No completed reference failures remain in those captured contexts.

Executed runtime/annotation commit: `3bb3684252c027730fd256ad49033e296ca47566`. Final reference-correction commit: `03d4400c32fb03a19cf09422934c2c1dd038120a`. Annotation sequences and runtime/evaluator code are unchanged across the last reference-only corrections. The frozen manifest contains 69 entries and 546 planned actions. Each task stops at its first rejected action, so rejected tasks do not execute all remaining actions. No LLM plans were generated. All 77 unit tests pass in the existing research_proj environment.

Each task resets its matching scene 0/1/2, adds Chars/Male2 in kitchen, and uses exact IDs with find_solution=False. Derived WASHED/HEATED/USED states come from runtime rules or confirmed native Talk, not fabricated native states. Native terminal placement, held-object and explicit switch/open/close facts were checked separately from strict reference scoring.

Full local evidence: [outputs/local/full_unity_replay_20261105T155815Z/report.md](../outputs/local/full_unity_replay_20261105T155815Z/report.md). The run stores frozen inputs/hashes, all 69 results, native/runtime graphs and per-action responses. [Cleanup verification](../outputs/local/full_unity_replay_20261105T155815Z/cleanup_verification.txt) confirms the dedicated simulator/Xvfb group has no active processes and ports 8082/8083 are clear. Source data stayed unchanged during replay; no dependencies, installed simulator assets or versions were altered.

The frozen reports retain their original reference scores. [Final reference rescoring](../outputs/local/final_reference_rescoring/summary.json) records current reference hashes and all 110 evaluations of the two batches' completed trajectories. This reuses real native executions with unchanged annotations/runtime; it is not a new Unity run. Final reference corrections and their exact edge reasons are recorded separately in the mapping audit.

## Latest results

| Dataset | Entries | Completed native/runtime replay |
| --- | ---: | ---: |
| train | 24 | 18 |
| test_seen | 10 | 7 |
| test_unseen | 10 | 8 |
| test_unseen_ambiguous_goals | 5 | 5 |
| env1 | 10 | 9 |
| env2 | 10 | 8 |

No rejected Unity action was accepted by the runtime. All 55 completed trajectories satisfy their directly annotated terminal facts in native Unity graphs. These checks establish the recorded replay outcomes; they are not proof that every natural-language goal is fully specified, nor estimates of LLM performance.

## Changes committed in this continuation

- Documented prompt/task initial-state provenance and retained runtime scene initialization.
- Required native response and character execution success before committing symbolic state or counting an action. A native/communication failure blocks later actions in that task.
- Repaired plate washing, stationary radio playback, direct book reading, accessible slippers, closet placement, living-room candle placement and native cellphone conversations. Added generated Read/Talk support with held-instance selection.
- Repaired all three toast annotations and scene2 salmon placement. Added supplied-partial-graph heating for edible Props and active toasters; repeated observations do not duplicate HEATED.
- Repaired all four failing ambiguous tasks: stage pans/plates before loading, retain served food on its plate, collect all four original fruit instances on a feasible stationary bowl, and stage the cereal plate at its destination. Added missing food/fruit goals and replay-derived heating; cook_lunch remains unchanged.
- Matched symbolic closet access to reset-separated native controls while retaining reported CLOSED. Closed fridges/cabinets/washers retain their access checks; native acceptance still gates all execution.
- Corrected stale room/proximity/orientation reference artifacts without changing evaluator formulas. Reset-context corrections cover eight initially affected references plus four follow-ups, limited to implicated clock/TV families and unrelated actor-neighbor proximity in three appliance tasks. Other orientations were restored. Current references pass all 110 completed-trajectory evaluations across two independent full batches.
- Aligned three repaired training examples; kept all 24 names/order and the other 21 strings intact.
- Preserved original-data archive, six mapping manifests, stable graph indices, wash-mug graph10, cutlery graph1, node metadata/order and unaffected graph records. Python changes were formatted with the configured VS Code Black distribution.

The [mapping audit](ground_truth_graph_mapping_audit.md) records exact per-task changes and evidence. Reference, action-support and prompt changes define a revised benchmark version: rerun or rescore compared systems consistently. Improved annotation/reference validation is not improved LLM performance.

## Remaining failures

| Dataset | Task | First rejected action |
| --- | --- | --- |
| train | wash clothes | `<char0> [open] <closet> (374)` |
| train | put papers in the folder | `<char0> [open] <folder> (204)` |
| train | take out the trash | `<char0> [open] <garbagecan> (229)` |
| train | open the curtains | `<char0> [open] <curtains> (31)` |
| train | wash the frying pan | `<char0> [putback] <fryingpan> (269) <sink> (247)` |
| train | get my pants and shirt and place on the bed | `<char0> [open] <closet> (374)` |
| test_seen | open window | `<char0> [open] <window> (91)` |
| test_seen | wash the rug in washing machine | `<char0> [find] <rug> (252)` |
| test_seen | throw away the lime | `<char0> [find] <lime> (440)` |
| test_unseen | brush teeth | `<char0> [putback] <toothpaste> (62) <toothbrush> (65)` |
| test_unseen | throw away apple | `<char0> [open] <garbagecan> (229)` |
| env1 | throw away plum | `<char0> [open] <garbagecan> (183)` |
| env2 | open the curtains | `<char0> [open] <curtains> (128)` |
| env2 | throw away bananas | `<char0> [open] <garbagecan> (378)` |

## What is needed next

The installed simulator remains compiled official-v2.3.0. The [public Unity source project](https://github.com/xavierpuigf/virtualhome_unity) was inspected in a separate temporary checkout at revision 8462a29eb8b3b75b49e5be6eaa84b34536c21d41. Its ProjectSettings/ProjectVersion.txt specifies Unity Editor 2021.3.10f1. No editor/build environment was found in standard Windows/WSL paths, installed-app registry or Unity Hub editor-location configuration; the user subsequently confirmed there is no custom installation. A compatible build toolchain and source/asset compatibility checks are needed to implement and validate native fixes. Python-only acceptance, direct state injection, task deletion or fabricated washing states would not validate these entries.

### Source investigation after toolchain confirmation

**Subsequent toolchain update:** the user installed Windows Editor2021.3.10f1 and Linux Mono support and activated Unity Personal. Verified the Editor binary and Linux Mono player variations. Interactive workspace startup and isolated non-batch CLI project creation/import both succeed; the latter exits0. Batch startup still fails with an unavailable access token/no valid license. This is a batch-startup limitation, not evidence that interactive activation failed.

The user specified the automation CLI at `C:/Users/bbdnet2399/AppData/Local/Unity/bin/unity`, available in MSYS2 Zsh PATH; subsequent launches use it through the mandatory wrapper. Source assets have fully restored at the pinned revision (1.27GiB Git pack). `unity open --wait` is unsupported on Windows in installed CLI1.0.0-beta.13; supported `unity open` without --wait accepted explicit Linux native build arguments and launched source import. Pinned Package Manager dependencies downloaded, but compilation reported missing RootMotion/Final IK and DunGen types. The user closed that Editor window; its exit0 is not build success, and no Linux executable exists. No native repair, completed baseline build or new replay is claimed.

The user completed `unity auth login`; subsequent CLI status confirms active Personal, signedIn=true and OAuth authentication. A fresh headless `unity build` still failed before compilation with `Unity has not been activated with a valid License` (CLI exit6 / Editor exit1). Successful account sign-in did not resolve this Editor's batch-startup issue. This remains distinct from the source compilation dependencies.

The pinned upstream `.gitignore` explicitly excludes RootMotion and DunGen directories. Source uses `RootMotion.FinalIK` throughout character/hand interaction code and `DunGen.RuntimeDungeon` in procedural generation; these are not merely optional unused imports. No package copies were found in neighboring project directories or standard Asset Store caches. The user confirmed they do not have these packages. [Final IK](https://assetstore.unity.com/packages/tools/animation/final-ik-14290) and [DunGen](https://www.aegongames.com/dungen/) are separately supplied assets; no purchases, substitute implementations, dependency removals or Editor upgrades were performed. Compatible package versions and batch licensing remain prerequisites for rebuilding this source as-is. The earlier missing-installation observations below describe the preceding investigation.

The subsequent [DunGen exclusion investigation](dungen_fixed_scene_investigation_2026-11-05.md) finds a feasible source-code boundary for a fixed-environment build: an external conditional candidate removes the DunGen compiler diagnostic while preserving the other diagnostics and normal reset handlers. However, all three fixed homes also reference procedural tile/doorway/settings components. Their careful exclusion and an explicit-ID loading policy remain necessary before runtime validation. No candidate was applied; this investigation does not resolve Final IK, licensing or any of the14 native failures.

**Chosen workflow:** after direct Unity.exe and Hub-assisted batch tests both reproduced the license failure, the user chose interactive Editor operation. Open the external project through the preferred `unity open` CLI without `-batchmode`, `-nographics` or `-quit`. The normal interactive session launches and reaches the compile-error Safe Mode prompt. This avoids making headless licensing a prerequisite for the chosen workflow; it does not fix source dependencies. The user was asked to select Enter Safe Mode because the native dialog button is not exposed to Windows UI Automation. No source candidate or native task fix has been applied. [Final IK alternatives and evidence](finalik_alternatives_2026-11-05.md) describe the remaining replacement work.

- In the pinned source, `Assets/Story Generator/Scripts/ScriptExecution.cs`, `IsOpenablePosition` requires either `Properties_door` or a root `HandInteraction` with an Open switch, as well as the applicable interaction-distance checks. A graph-level `CAN_OPEN` property alone does not satisfy this code.
- `PrefabScripts/ObjAnnotator.cs` builds Open switches from model annotations and matching immediate child transforms. The pinned `Assets/Resources/Data/object_annotation.json` has no model annotation for `Dark_Grey_Washing_Machine` or `Garbage_can_2/6/7`. The washer prefab root also has no serialized HandInteraction. These are static source findings: another initialization path or differing installed assets must still be checked before claiming the precise native cause or a validated repair.
- The upstream [washer failure report](https://github.com/xavierpuigf/virtualhome/issues/102) independently reports the same scene0 washer72, prefab name and advertised `CAN_OPEN` mismatch. It supplies no verified fix.
- The official [release listing](https://github.com/xavierpuigf/virtualhome/releases) lists v2.3.0 as latest; no newer official release was identified in this check. This does not establish whether an older executable could support an individual action or preserve the dataset's scene identities.
- Unity still publishes [2021.3.10f1 installers](https://unity.com/releases/editor/whats-new/2021.3.10f1), including Windows Editor and Linux Mono build support. To continue native rebuilding, provision and activate a compatible Editor, restore the full source assets in an isolated checkout, build an unchanged baseline, and compare scene0/1/2 node identities, transforms and affordances with official-v2.3.0 before applying asset/action repairs. Then validate each repair and repeat all69 entries. An Editor install, activation, full asset restore, custom build and new replay have not been performed in this source investigation.

Controls reject Open on all nine scene0 curtain panels, all three windows, all three original folders (also held), the washer and garbage bin; closed washer loading also rejects. All six original shirts reject Grab. The original pan fails sink placement; resizing is diagnostic, not an accepted scene revision. Native Pour/Squeeze for toothpaste are absent from the installed parser. Failed tasks may expose further failures after their first rejected action is fixed. Empty outside/disposal steps in take_out_the_trash also require semantic review; a passing action-return count alone would not establish that natural-language task.

## Commit record

| Commit | Change |
| --- | --- |
| `f1dcfee2` | Document runtime initial-state provenance |
| `95610da3` | Repair plate washing with a feasible plate and matching faucet |
| `6e67a833` | Require Unity acceptance before advancing task execution |
| `d5a49aa4` | Play the stationary radio without an unsupported grab |
| `6e3f9295` | Read the held book directly under the table lamp |
| `77721678` | Correct five completed-task reference graph artifacts |
| `2390a972` | Derive heating for edible props and active toasters |
| `c88308ee` | Stage cooking vessels and require heated food served on plates |
| `176d2855` | Repair all three toast annotations and heated-bread goals |
| `288ffe14` | Place salmon on the frying pan in scene two |
| `43ffe30e` | Use accessible slippers and preserve the bed placement goal |
| `b5a74ec6` | Match symbolic closet access to verified native affordances |
| `54beaca1` | Place the candle on a shelf in the living room |
| `53239fdc` | Collect all four fruits on a feasible stationary bowl |
| `416eacbd` | Stage the breakfast plate before serving cereal |
| `983c07bf` | Place clothes in the accessible closet without unsupported door actions |
| `46842c24` | Support native phone conversations and repair calling a friend |
| `299aff7c` | Align repaired training examples with native-valid annotations |
| `6b607874` | Remove unrelated reset-context goals from eight affected references |
| `3bb36842` | Preserve unrelated orientations outside the reset-sensitive families |
| `03d4400c` | Correct four additional untouched clock and TV goal artifacts |
# Native follow-up: mesh-only hanging shirts

The source-player rebuild and original-player diagnostics are documented in
[`finalik_alternatives_2026-11-05.md`](finalik_alternatives_2026-11-05.md). The public
source can compile and build, but missing model assets make that player unsuitable
for these annotations. It has not replaced the installed official player.

A separate official-player copy with the `adaptpolicies-shirt-grab-v1` repair
preserves all initial static scene metadata, IDs, transforms, bounding boxes and
structural edges in scenes0/1/2. The native repair uses a renderer-backed hand-pose
fallback for the original mesh-only hanging shirts; all interaction execution
continues through the original native implementation. An attempted collider
variant was rejected when equivalence checking detected six extra ON edges.

The updated “get my pants and shirt and place on the bed” annotation passes9/9
native and symbolic actions. A fresh replay using the main-source patch and main
data yields PSR=1, SR=1, Precision=1, Exec=1. Native final relations place shirt376
and pants386 ON bed109. Existing unit tests:77 passed.

Only the unsupported Open closet374 action is removed. Reference train graph20
changes only closet374 OPEN→CLOSED, matching its unchanged initial state and
removing an incidental target from the clothes-placement goal. On the first
successful trace, the old reference scored15/16 conditions; the corrected
reference has15/15. This reference effect is separate from the native grab repair
and does not establish improved LLM performance. Evaluation formulas are unchanged.

Evidence: `outputs/local/shirt_grab_repair_v1/` (old reference retained),
`outputs/local/shirt_grab_repair_main_v1/` (fresh main-data replay), and
`outputs/local/official_diagnostic_scene_comparison/`. Build provenance records the
original assembly hash and the custom patch; the original simulator and all asset
files remain unchanged. Source and usage:
[`helper-scripts/native-repairs/`](../helper-scripts/native-repairs/README.md).

This resolves one previously failing task on the custom candidate. The last
complete stock replay remains55/69; no combined56/69 replay is claimed. Thirteen
other native task failures remain, and the final full all69 replay is still pending.

## 2026-11-06: native window-curtain opening

The `adaptpolicies-native-repairs-v2` candidate adds native Open switches to the
existing window-curtain objects, with real reversible panel scale/position
transitions and a room-facing approach. The train curtain31 and env2 curtain128
annotations both pass their original actions and unchanged evaluator references:
PSR=1, SR=1, Precision=1, Exec=1. Their annotation/graph files are unchanged.

Physical controls use live Unity transforms and renderer bounds. The legacy graph
API caches some child transforms and bounds; its response alone cannot establish
panel movement. Each target passes three Open/Close cycles: panels gather to20%
width on Open, report OPEN, and restore original positions/scales plus CLOSED on
Close. Repeated controls exposed a native timing race between IK completion and
the final physics tick. A curtain-only coroutine wrapper now waits for the real
switch transitions to finish, with a bounded failure if they do not complete.

A fresh build from the main sources passes all three initial scene-equivalence
checks, all six physical control cases, both curtain annotations and the full
nine-action shirt-task regression. Evidence:
`outputs/local/curtain_main_wait_validation_v2/`. Five of3356 original managed
methods have narrow hooks/wrappers; the other3351 are unchanged. All player asset
files and the original simulator installation remain unchanged.

This resolves two additional prior native failures on the custom candidate.
Eleven remain. The last complete stock replay is still55/69; the final all69
replay on the declared custom runtime remains pending.

## 2026-11-06: native hinged window opening

The explicit `window-opening` feature in `adaptpolicies-native-repairs-v3`
separates the original readable window meshes into a fixed outer frame and an
inner sash/glass assembly. All original triangles, material slots and vertex
attributes are retained. The native Open switch rotates the sash70 degrees
toward the room, and Close reverses that transition. A reachable contact point
allows closing the wider window after opening. Generated sash children are
excluded from prefab matching. Shared opening logic waits for actual native
transitions; it does not fabricate native success or graph states.

The unchanged test_seen/open_window annotation passes4/4 native and symbolic
actions with PSR=1, SR=1, Precision=1, Exec=1. Both accepted curtain annotations
and the9-action clothes-to-bed task also pass on the same final build. Scenes0/1/2
retain all initial static metadata and structural edges. Nine fresh-instance
window Open/Close controls pass across IDs70/91/364, with a stationary frame,
70-degree sash rotation, OPEN/CLOSED and restoration. Nine further controls
perform three successive Open/Close cycles on each same instance, confirming
that transitions rearm after Close. All six curtain controls still pass.

Evidence: `outputs/local/window_final_validation_v3/` and
`outputs/local/window_reopen_controls_v3/`. Earlier candidate evidence retains
the rejected far-edge contact point, which opened the wide window but made
Close unreachable. The final method audit still has3351/3356 original methods
unchanged and no original methods added or removed. Only the patched original
managed assembly and our separate helper DLL differ from the official player;
all original assets/IK and the original installation remain intact.

No dataset, archive, mapping, reference or evaluator changes. This resolves one
additional original task failure on the declared custom runtime;10 remain.
The last complete stock replay remains55/69. The final all69 replay is pending
the remaining container, approach and placement repairs; no aggregate result
is inferred from separate targeted runs.

## 2026-11-06: native lidless-bin disposal

Rendered inspection confirms that scene0 bin229, scene1 bin183 and scene2 bin378
are lidless. Their generic CAN_OPEN/CLOSED metadata does not describe their
physical accessibility. The explicit `lidless-bin-colliders` feature uses each
original hollow mesh as a collision surface. Existing box colliders become
triggers, retaining bounds without filling the interior. No lid, OPEN flag or
synthetic native success is added.

Native insertion initially failed because the solid box or missing collider
provided no interior floor for placement rays. Mesh colliders enable placement.
Further live controls caught a false-positive native result: the banana group
had an INSIDE edge while protruding through the bin side. A narrow ExecutePut
hook now centers visible payload geometry, checks every visible mesh vertex
against the interior and real floor, and supplies a fitting native target pose.
Original IK, pickup, release and native graph updates perform the action.

The four disposal annotations retain actual fruit insertion and omit unsupported
Open/Close steps. Lime440 approaches through coffee table371 before pickup.
Symbolic insertion/retrieval accepts only the three verified lidless prefabs
while preserving their legacy state; closed unknown bins and other containers
retain their access restrictions. Existing Unity acceptance remains mandatory.

Fresh native+symbolic replays pass apple6/6, plum4/4, bananas4/4 and lime6/6.
Post-replay live renderer bounds are contained in the receiving bin, the native
INSIDE edge exists, and the object is not held. Separate native controls pass
retrieval and reinsertion for all four fruits. An oversized-pan negative control
returns failure, retains the held object and creates no INSIDE edge.

The lime reference had one stale edge: lime440 INSIDE livingroom335 remained
after insertion into kitchen bin229. Only test_seen graph2 changes that edge to
kitchen205. The frozen old successful replay scored PSR=1, SR=1, Exec=1 but
Precision415/416. The corrected reference removes that erroneous preservation
condition and adds the proper room goal; a fresh six-action native replay scores
all four metrics1. Scoring formulas are unchanged. This reference effect is not
an execution or LLM-performance improvement.

All four disposal tasks now score all four metrics1. The shirt, two curtain and
window annotation regressions also pass, along with all3 scene comparisons,
9 window motion cases,6 curtain cases and81 Python tests. Six of3356 original
methods have narrow hooks;3350 remain unchanged. The player differs only in the
patched original managed assembly and added own helper DLL. Original asset
files, IK and installation remain unchanged.

Evidence: `outputs/local/lidless_main_validation_v4/`, the separate corrected-lime
and visual replay in `outputs/local/lidless_lime_reference_validation_v4/`,
`outputs/local/lidless_bin_physical_v4/`, and
`outputs/local/lidless_bin_negative_v4/`. Earlier rejected physical controls and
the original lime reference/score remain frozen. Only four annotation records
and that single graph2 edge change; all other records, mappings and original
archive are preserved, including protected wash-mug graph10 and cutlery graph1.

Six original failures remain: wash_clothes, put_papers_in_the_folder,
take_out_the_trash, wash_the_frying_pan, wash_the_rug_in_washing_machine and
brush_teeth. The last complete stock replay remains55/69. The required final
all69 replay on the declared combined runtime is still pending.
