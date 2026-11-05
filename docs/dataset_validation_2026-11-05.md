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

The user specified the automation CLI at `C:/Users/bbdnet2399/AppData/Local/Unity/bin/unity`, available in MSYS2 Zsh PATH; subsequent launches use it through the mandatory wrapper. Its `license status` reports active Personal but signedIn=false. `unity build` reproduces the batch licensing failure. `unity open --wait` is unsupported on Windows in installed CLI1.0.0-beta.13; supported `unity open` without --wait accepted explicit Linux native build arguments and launched the source project. Its Editor is resolving/downloading the pinned Unity packages at this update. Source assets have fully restored at the pinned revision (1.27GiB Git pack). No native repair, completed baseline build or new replay is claimed. CLI launch success alone does not validate a build. The earlier missing-installation observations below describe the preceding investigation.

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
