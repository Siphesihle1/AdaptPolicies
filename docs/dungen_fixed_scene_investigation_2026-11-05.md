# DunGen exclusion investigation — 2026-11-05

Excluding DunGen from a build for the existing fixed environments appears feasible, but removing its C# import alone is insufficient. A compiler-checked candidate isolates the procedural API handlers; the fixed room prefabs also contain procedural components/settings references that need separate treatment. This investigation does not establish a successful simulator build or unchanged native behavior. Final IK and the independent batch licensing issue remain unresolved.

The investigated upstream revision is `8462a29eb8b3b75b49e5be6eaa84b34536c21d41`. No candidate was applied to that checkout, the installed simulator or AdaptPolicies runtime/data. The only existing tracked change in the upstream checkout is the shader compiler log removed during the earlier Editor import. Assets, ProjectSettings and Packages remain byte-identical to Git.

## Code boundary

`Assets/Story Generator/Scripts/TestDriver.cs` is the only C# file referencing DunGen. It imports `DunGen` and accesses `RuntimeDungeon.Generator` inside the `procedural_generation` handler. The `clear_procedural` handler loads the procedural scene, while `process` looks up the generated `Dungeon` object. These three handlers form the candidate exclusion boundary.

Normal fixed-environment loading uses a serialized prefab catalog. Explicit environment IDs0,1,2 resolve to `Home_0.prefab`, `Home_1.prefab`, and `Home_2.prefab` under `Assets/Resources/FloorPlan/Release/Home`. These IDs are catalog indices, not Unity scene-asset build indices. The ordinary `environment`, `clear` and `fast_reset` handlers contain no DunGen type references and are byte-for-byte unchanged in the candidate.

The external candidate uses `VIRTUALHOME_FIXED_SCENES` to exclude the import and return `success=false` with an explicit unsupported-feature message from the three procedural handlers. Their original bodies remain available when the symbol is absent. Rejected procedural requests do not execute the original scene/reset/generation mutations. This is a prototype, not an installed fixed-scene build.

## Asset boundary

The build settings include `Scene_0.unity` (the catalog/server scene) and `Scene_1.unity` (the procedural scene). Scene_1 contains `Home_Procedural_Generation`, a serialized generator and DunGen coroutine helpers. Scene_0 has none of the identified DunGen script GUIDs in its own serialized script references.

However, recursively following serialized asset GUIDs from each of the three fixed home prefabs reaches room prefabs containing missing-script components with tile/doorway fields, plus `Assets/Resources/DunGen Settings.asset`. Relevant missing script GUIDs are:

- `238d443cf4b172f4989d5ce455c57c3b`: room component with tile bounds, placement and doorway-list fields.
- `32a188f8ee195cf4cb8b2fdccd193b79`: procedural doorway component with connector/blocker weights, socket and connection fields.
- `ad1ebb4e3aa3b474d849bc53fbe48191` and `59296c11d75e7024ebd73d93f5babf99`: settings/default-socket asset components.

Tile/doorway roles are inferred from serialized fields and object names; the absent package's original script metadata is unavailable. These references occur in the rooms used by Home0,1,2, not just in the procedural scene. They cannot be dismissed merely because procedural generation is never called. The static audit does not establish whether their missing runtime behavior affects door blockers, bounds or initialization.

## Verification and limits

Used the Editor's bundled Roslyn C# compiler and the response file produced by the earlier source import. This runs without starting an Editor window or bypassing Editor licensing. Compiler outputs were redirected outside the source checkout; no substitute dependency classes were supplied.

- Original source and the candidate without the fixed-scene symbol report identical distinct compiler errors.
- With the symbol, the DunGen missing-namespace diagnostic disappears; the remaining diagnostics are the same missing Final IK/RootMotion types.
- All three compiler runs fail overall. This proves the observed source-level DunGen dependency is conditionally isolated; it does not prove a complete build succeeds or reveal errors masked by the remaining dependency failures.
- The ordinary reset/loading handler texts are unchanged, and the three fixed prefab catalog entries/order are preserved. No scene, prefab or settings assets were modified.
- No native scene comparison or task replay was performed. Existing dataset validity results and all14 unresolved native failures are unchanged.

Local evidence is under `outputs/local/dungen_fixed_scene_investigation/`: `candidate.patch`, `asset-audit.json`, `verification.json`, and three compiler logs. The candidate source and compiler response files are outside the repository in temporary `dungen-fixed-scene-candidate/`.

## Requirements before adopting a fixed-scene build

1. Add a fixed-scene build mode that rejects procedural requests and requires explicit environment IDs. The current no-argument `environment` path can still load Scene_1; the prototype intentionally leaves it unchanged, so it is not ready for adoption.
2. Exclude the procedural scene/settings and remove only identified procedural components from build copies of the fixed rooms. Preserve room objects, transforms, geometry, colliders and fixed prefab ordering. Do not delete doorway objects wholesale or remove every missing MonoBehaviour; that could affect other dependencies or node identities.
3. Resolve Final IK and produce a Linux baseline through the chosen interactive Editor workflow. Batch licensing remains unresolved but is no longer a prerequisite for this route. DunGen exclusion does not replace Final IK or solve licensing.
4. Compare native environment IDs0,1,2 against official-v2.3.0 for node identity, geometry, structural relations and door/navigation behavior. Only after that comparison should the remaining native action repairs and final69-entry replay proceed.
