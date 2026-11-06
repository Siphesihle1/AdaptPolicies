#!/usr/bin/env zsh
set -eu
if (( $# != 3 )); then
    print -u2 'Usage: build.sh ORIGINAL_MANAGED_DIRECTORY UNITY_EDITOR_DIRECTORY OUTPUT_DIRECTORY'
    exit 2
fi
managed=$(cygpath -u "$1")
editor=$(cygpath -u "$2")
output=$(cygpath -u "$3")
source_dir=${0:A:h}
if [[ "${output:A}/" == "${managed:A}/"* ]]; then
    print -u2 'Output must be outside the original Managed directory.'
    exit 2
fi
test -f "$managed/Assembly-CSharp.dll"
test -f "$editor/Data/DotNetSdkRoslyn/csc.dll"
mkdir -p "$output"
"$editor/Data/NetCoreRuntime/dotnet.exe" "$(cygpath -m "$editor/Data/DotNetSdkRoslyn/csc.dll")" \
    -nologo -target:library -nostdlib+ -langversion:7.3 \
    -out:"$(cygpath -m "$output/AdaptPolicies.NativeRepairs.dll")" \
    -r:"$(cygpath -m "$managed/mscorlib.dll")" \
    -r:"$(cygpath -m "$managed/netstandard.dll")" \
    -r:"$(cygpath -m "$managed/System.dll")" \
    -r:"$(cygpath -m "$managed/System.Core.dll")" \
    -r:"$(cygpath -m "$managed/UnityEngine.CoreModule.dll")" \
    -r:"$(cygpath -m "$managed/UnityEngine.PhysicsModule.dll")" \
    -r:"$(cygpath -m "$managed/Newtonsoft.Json.dll")" \
    -r:"$(cygpath -m "$managed/Assembly-CSharp.dll")" \
    -r:"$(cygpath -m "$managed/Assembly-CSharp-firstpass.dll")" \
    "$(cygpath -m "$source_dir/SceneAssetDiagnostics.cs")" \
    "$(cygpath -m "$source_dir/ShirtGrabRepair.cs")" \
    "$(cygpath -m "$source_dir/NativeRepairFeatures.cs")" \
    "$(cygpath -m "$source_dir/WindowCurtainRepair.cs")" \
    "$(cygpath -m "$source_dir/WindowOpeningRepair.cs")" \
    "$(cygpath -m "$source_dir/NativeOpeningRepair.cs")" \
    "$(cygpath -m "$source_dir/LidlessBinRepair.cs")" \
    "$(cygpath -m "$source_dir/FolderOpeningRepair.cs")" \
    "$(cygpath -m "$source_dir/FolderPaperRepair.cs")"
pwsh.exe -NoProfile -File "$(cygpath -m "$source_dir/patch-player.ps1")" \
    -ManagedDirectory "$(cygpath -m "$managed")" \
    -HelperAssembly "$(cygpath -m "$output/AdaptPolicies.NativeRepairs.dll")" \
    -OutputAssembly "$(cygpath -m "$output/Assembly-CSharp.dll")" \
    -CecilAssembly "$(cygpath -m "$editor/Data/MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll")"
