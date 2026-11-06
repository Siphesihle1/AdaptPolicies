param(
    [Parameter(Mandatory=$true)][string]$ManagedDirectory,
    [Parameter(Mandatory=$true)][string]$HelperAssembly,
    [Parameter(Mandatory=$true)][string]$OutputAssembly,
    [Parameter(Mandatory=$true)][string]$CecilAssembly
)
$ErrorActionPreference = 'Stop'
Add-Type -Path $CecilAssembly
$source = Join-Path $ManagedDirectory 'Assembly-CSharp.dll'
$expectedHash = 'f8fb0a272bf646aaeefa8df870aba5bda1dec291690191295da235b3c32fb4b0'
$actualHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) { throw 'Expected the unmodified official Linux v2.3.0 Assembly-CSharp.dll.' }
if ([IO.Path]::GetFullPath($source) -eq [IO.Path]::GetFullPath($OutputAssembly)) { throw 'Output must be separate from the original assembly.' }
$resolver = [Mono.Cecil.DefaultAssemblyResolver]::new()
$resolver.AddSearchDirectory($ManagedDirectory)
$resolver.AddSearchDirectory([IO.Path]::GetDirectoryName($HelperAssembly))
$parameters = [Mono.Cecil.ReaderParameters]::new()
$parameters.AssemblyResolver = $resolver
$original = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($source,$parameters)
$helper = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($HelperAssembly,$parameters)
try {
    $creator = @($original.MainModule.Types | Where-Object Name -eq 'EnvironmentGraphCreator')
    if ($creator.Count -ne 1) { throw 'Expected one graph creator.' }
    $create = @($creator[0].Methods | Where-Object Name -eq 'CreateGraph')
    if ($create.Count -ne 1 -or $create[0].Parameters.Count -ne 1 -or $create[0].Parameters[0].ParameterType.FullName -ne 'UnityEngine.Transform') { throw 'Unexpected graph creation signature.' }
    $capture = $helper.MainModule.GetType('AdaptPolicies.NativeDiagnostics.SceneAssetDiagnostics').Methods | Where-Object Name -eq 'Capture'
    $captureReference = $original.MainModule.ImportReference($capture)
    $processor = $create[0].Body.GetILProcessor()
    $curtain = $helper.MainModule.GetType('AdaptPolicies.NativeRepairs.NativeOpeningRepair')
    $prepare = $original.MainModule.ImportReference(($curtain.Methods | Where-Object Name -eq 'Prepare'))
    $createStart = $create[0].Body.Instructions[0]
    $processor.InsertBefore($createStart,$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_1))
    $processor.InsertBefore($createStart,$processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$prepare))
    $returns = @($create[0].Body.Instructions | Where-Object { $_.OpCode.Code -eq [Mono.Cecil.Cil.Code]::Ret })
    if ($returns.Count -ne 1) { throw 'Unexpected graph creation return structure.' }
    $returnInstruction = $returns[0]
    $returnInstruction.OpCode = [Mono.Cecil.Cil.OpCodes]::Dup
    $returnInstruction.Operand = $null
    $argument = $processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_1)
    $call = $processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$captureReference)
    $return = $processor.Create([Mono.Cecil.Cil.OpCodes]::Ret)
    $processor.InsertAfter($returnInstruction,$argument)
    $processor.InsertAfter($argument,$call)
    $processor.InsertAfter($call,$return)

    $grab = @($original.MainModule.Types | ForEach-Object { $_.Methods } | Where-Object Name -eq 'GetGrabPose')
    if ($grab.Count -ne 1 -or $grab[0].Parameters.Count -ne 1 -or !$grab[0].IsStatic) { throw 'Unexpected grab-pose method signature.' }
    $repair = $helper.MainModule.GetType('AdaptPolicies.NativeRepairs.ShirtGrabRepair')
    $canUse = $original.MainModule.ImportReference(($repair.Methods | Where-Object Name -eq 'HasMeshOnlyShirt'))
    $getPose = $original.MainModule.ImportReference(($repair.Methods | Where-Object Name -eq 'GetPose'))
    $processor = $grab[0].Body.GetILProcessor()
    $first = $grab[0].Body.Instructions[0]
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_0))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$canUse))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Brfalse,$first))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$getPose))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Ret))

    $character = @($original.MainModule.Types | Where-Object Name -eq 'CharacterControl')
    if ($character.Count -ne 1) { throw 'Expected one character controller.' }
    $interaction = @($character[0].Methods | Where-Object Name -eq 'StartInteraction')
    if ($interaction.Count -ne 1 -or $interaction[0].Parameters.Count -ne 3 -or $interaction[0].Parameters[0].ParameterType.FullName -ne 'UnityEngine.GameObject') { throw 'Unexpected native interaction signature.' }
    $awaitInteraction = $original.MainModule.ImportReference(($curtain.Methods | Where-Object Name -eq 'AwaitInteraction'))
    $processor = $interaction[0].Body.GetILProcessor()
    foreach ($instruction in @($interaction[0].Body.Instructions | Where-Object { $_.OpCode.Code -eq [Mono.Cecil.Cil.Code]::Ret })) {
        $instruction.OpCode = [Mono.Cecil.Cil.OpCodes]::Ldarg_1
        $instruction.Operand = $null
        $call = $processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$awaitInteraction)
        $return = $processor.Create([Mono.Cecil.Cil.OpCodes]::Ret)
        $processor.InsertAfter($instruction,$call)
        $processor.InsertAfter($call,$return)
    }

    $front = @($original.MainModule.Types | ForEach-Object { $_.Methods } | Where-Object Name -eq 'GetObjectFrontVec')
    if ($front.Count -ne 1 -or $front[0].Parameters.Count -ne 1 -or !$front[0].IsStatic) { throw 'Unexpected front-direction method signature.' }
    $isCurtain = $original.MainModule.ImportReference(($curtain.Methods | Where-Object Name -eq 'IsRepairedInteraction'))
    $getFront = $original.MainModule.ImportReference(($curtain.Methods | Where-Object Name -eq 'GetFront'))
    $processor = $front[0].Body.GetILProcessor()
    $first = $front[0].Body.Instructions[0]
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_0))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$isCurtain))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Brfalse,$first))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_0))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$getFront))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Ret))

    $updates = @($creator[0].Methods | Where-Object Name -eq 'UpdateGraph')
    if ($updates.Count -ne 1 -or $updates[0].Parameters.Count -eq 0 -or $updates[0].Parameters[0].ParameterType.FullName -ne 'UnityEngine.Transform') { throw 'Unexpected graph-update signature.' }
    $processor = $updates[0].Body.GetILProcessor()
    foreach ($instruction in @($updates[0].Body.Instructions | Where-Object { $_.OpCode.Code -eq [Mono.Cecil.Cil.Code]::Ret })) {
        $instruction.OpCode = [Mono.Cecil.Cil.OpCodes]::Dup
        $instruction.Operand = $null
        $argument = $processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_1)
        $call = $processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$captureReference)
        $return = $processor.Create([Mono.Cecil.Cil.OpCodes]::Ret)
        $processor.InsertAfter($instruction,$argument)
        $processor.InsertAfter($argument,$call)
        $processor.InsertAfter($call,$return)
    }
    $put = @($original.MainModule.Types | ForEach-Object { $_.Methods } | Where-Object Name -eq 'ExecutePut')
    if ($put.Count -ne 1 -or $put[0].Parameters.Count -ne 1 -or $put[0].Parameters[0].ParameterType.FullName -ne 'StoryGenerator.Utilities.State') { throw 'Unexpected put coroutine signature.' }
    $bin = $helper.MainModule.GetType('AdaptPolicies.NativeRepairs.LidlessBinRepair')
    $preparePut = $original.MainModule.ImportReference(($bin.Methods | Where-Object Name -eq 'PreparePut'))
    $processor = $put[0].Body.GetILProcessor()
    $first = $put[0].Body.Instructions[0]
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_1))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$preparePut))

    $folder = $helper.MainModule.GetType('AdaptPolicies.NativeRepairs.FolderPaperRepair')
    $folderPrepare = $original.MainModule.ImportReference(($folder.Methods | Where-Object Name -eq 'PreparePut'))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_1))
    $processor.InsertBefore($first,$processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$folderPrepare))
    $executor = $original.MainModule.Types | Where-Object Name -eq 'ScriptExecutor'
    $planner = $executor.NestedTypes | Where-Object Name -eq '<ProcessPutAction>d__85'
    $move = $planner.Methods | Where-Object Name -eq 'MoveNext'
    $calls = @($move.Body.Instructions | Where-Object { $_.OpCode.Code -eq [Mono.Cecil.Cil.Code]::Call -and $_.Operand.Name -eq 'CalculatePutPositions' })
    if ($calls.Count -ne 1 -or $calls[0].Operand.Parameters.Count -ne 7) { throw 'Unexpected native put-position planner call.' }
    $processor = $move.Body.GetILProcessor()
    $currentField = $planner.Fields | Where-Object Name -eq 'current'
    $actionField = $planner.Fields | Where-Object Name -eq 'a'
    $processor.InsertBefore($calls[0],$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_0))
    $processor.InsertBefore($calls[0],$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldfld,$currentField))
    $processor.InsertBefore($calls[0],$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldarg_0))
    $processor.InsertBefore($calls[0],$processor.Create([Mono.Cecil.Cil.OpCodes]::Ldfld,$actionField))
    $calls[0].Operand = $original.MainModule.ImportReference(($folder.Methods | Where-Object Name -eq 'Positions'))

    $hand = $original.MainModule.Types | Where-Object Name -eq 'HandInteraction'
    $getIO = @($hand.Methods | Where-Object Name -eq 'Get_IO_grab')
    if ($getIO.Count -ne 1 -or $getIO[0].Parameters.Count -ne 2) { throw 'Unexpected native grab interaction factory.' }
    $restore = $original.MainModule.ImportReference(($folder.Methods | Where-Object Name -eq 'RestoreReleasePose'))
    $processor = $getIO[0].Body.GetILProcessor()
    foreach ($instruction in @($getIO[0].Body.Instructions | Where-Object { $_.OpCode.Code -eq [Mono.Cecil.Cil.Code]::Ret })) {
        $instruction.OpCode = [Mono.Cecil.Cil.OpCodes]::Ldarg_0
        $instruction.Operand = $null
        $call = $processor.Create([Mono.Cecil.Cil.OpCodes]::Call,$restore)
        $return = $processor.Create([Mono.Cecil.Cil.OpCodes]::Ret)
        $processor.InsertAfter($instruction,$call)
        $processor.InsertAfter($call,$return)
    }

    $original.Write($OutputAssembly)
    $manifest = [ordered]@{
        base = 'Official VirtualHome Linux v2.3.0 (Unity 2021.2.14f1)'
        patch = 'adaptpolicies-native-repairs-v5'
        originalSha256 = $actualHash
        helperSha256 = (Get-FileHash -LiteralPath $HelperAssembly -Algorithm SHA256).Hash.ToLowerInvariant()
        patchedSha256 = (Get-FileHash -LiteralPath $OutputAssembly -Algorithm SHA256).Hash.ToLowerInvariant()
        modifiedMethods = @($create[0].FullName,$updates[0].FullName,$grab[0].FullName,$front[0].FullName,$interaction[0].FullName,$put[0].FullName,$move.FullName,$getIO[0].FullName)
        activation = 'ADAPTPOLICIES_NATIVE_REPAIRS=shirt-grab,window-curtains,window-opening,lidless-bin-colliders,folder-opening'
        assetsModified = $false
        originalInstallationModified = $false
        nativeReplayVerified = $false
    }
    $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($OutputAssembly,'.manifest.json'))
    $manifest | ConvertTo-Json -Depth 4
}
finally {
    $original.Dispose()
    $helper.Dispose()
    $resolver.Dispose()
}
