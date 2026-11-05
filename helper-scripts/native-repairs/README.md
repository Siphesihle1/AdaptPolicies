# Local native simulator repairs

This tool builds the `adaptpolicies-shirt-grab-v1` patch for a **separate copy** of
the official VirtualHome Linux v2.3.0 player (Unity 2021.2.14f1). It preserves that
player's assets and original IK implementation. It does not rebuild the incomplete
public Unity asset project. No simulator binaries are distributed here.

The hanging `MOD_PRO_Shirt_*` instances have meshes but no colliders. Native
`GetGrabPose` rejects them before interaction execution. With the explicit
`ADAPTPOLICIES_NATIVE_REPAIRS=shirt-grab` setting, the patch supplies the existing
horizontal grab pose for these mesh-only shirts. Navigation, IK, attachment,
release, action responses and all other objects continue through the original
native implementation. No collider, object, graph state or success response is
fabricated. Without the setting, the original grab-pose implementation runs.

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
`ADAPTPOLICIES_NATIVE_REPAIRS=shirt-grab` in the simulator process environment.
Record the manifest with every replay; this is a custom runtime, not stock v2.3.0.

Optional `ADAPTPOLICIES_NATIVE_DIAGNOSTICS` names a directory for read-only scene
snapshots. Without it, the graph diagnostic hook immediately returns. The build
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

Evidence: `outputs/local/shirt_grab_repair_main_v1/` and
`outputs/local/official_diagnostic_scene_comparison/`. The last complete stock
replay remains55/69. This targeted test does not replace the required final
all69-entry replay or resolve the other13 native failures.
