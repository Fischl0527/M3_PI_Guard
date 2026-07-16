[CmdletBinding()]
param(
    [string]$PythonExecutable = "python",
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = if ($PSScriptRoot) {
    $PSScriptRoot
} elseif ($MyInvocation.MyCommand.Path) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    throw "Unable to resolve the scripts directory."
}

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$ExperimentRoot = Join-Path $RepoRoot "outputs\experiments"
$RegistryPath = Join-Path $RepoRoot "experiments\registry.json"
$ProgramRoot = Join-Path $ExperimentRoot "program_final_v3"
$ProgramManifestPath = Join-Path $ExperimentRoot "program_manifest_final_v3.json"
$BlindFreezePath = Join-Path $ExperimentRoot "blind_freeze_v3.json"
$FinalAnalysisDir = Join-Path $ExperimentRoot "final_analysis"
$E11SupplementDir = Join-Path $ExperimentRoot "E11_posthoc_amendment_v1"
$DashboardEntry = Join-Path $RepoRoot "m3_eval\evidence_dashboard.py"
$DashboardStreamlitEntry = Join-Path $ScriptDir "dashboard_app.py"

# The final dashboard is intentionally closed over the registry-selected
# primary manifests. E9/E14 live in corrected r2 output roots, so deriving the
# allowlist from outputs\experiments\E0..E17 would silently reopen superseded
# V3 evidence. These arrays are populated only after the registry is parsed and
# every selected primary manifest is resolved inside the repository.
$FormalBundleDirs = @()
$DashboardSources = @()
$V3ProvenanceSources = @($ProgramRoot, $BlindFreezePath)
$ApprovedBoundarySources = @()
$RejectedLegacySources = @(
    (Join-Path $ExperimentRoot "E9"),
    (Join-Path $ExperimentRoot "E14"),
    (Join-Path $ExperimentRoot "program_final"),
    (Join-Path $ExperimentRoot "program_final_repro"),
    (Join-Path $ExperimentRoot "program_final_v2"),
    (Join-Path $ExperimentRoot "program_final_v2_repro"),
    (Join-Path $ExperimentRoot "program_final_v3_repro"),
    (Join-Path $ExperimentRoot "program_v3"),
    (Join-Path $ExperimentRoot "program_v2"),
    (Join-Path $ExperimentRoot "program"),
    (Join-Path $ExperimentRoot "program_repro"),
    (Join-Path $ExperimentRoot "program_manifest_final.json"),
    (Join-Path $ExperimentRoot "program_manifest_final_repro.json"),
    (Join-Path $ExperimentRoot "program_manifest_final_v2.json"),
    (Join-Path $ExperimentRoot "program_manifest_final_v2_repro.json"),
    (Join-Path $ExperimentRoot "program_manifest_final_v3_repro.json"),
    (Join-Path $ExperimentRoot "program_manifest_v3.json"),
    (Join-Path $ExperimentRoot "program_manifest_v2.json"),
    (Join-Path $ExperimentRoot "program_manifest.json"),
    (Join-Path $ExperimentRoot "stub_repro_program_manifest.json"),
    (Join-Path $ExperimentRoot "blind_freeze.json"),
    (Join-Path $ExperimentRoot "_invalid"),
    (Join-Path $ExperimentRoot "E14_initial_cold_start_diagnostic")
)

function Resolve-RepoPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function Test-IsSameOrDescendant {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Candidate,
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $candidatePath = [System.IO.Path]::GetFullPath($Candidate)
    $rootPath = [System.IO.Path]::GetFullPath($Root)
    return $candidatePath -eq $rootPath -or
        $candidatePath.StartsWith($rootPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-SourceNotInvalidated {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (Test-Path -LiteralPath $Path -PathType Container) {
        foreach ($markerName in @("INVALIDATED.json", "SUPERSEDED.json")) {
            $marker = Join-Path $Path $markerName
            if (Test-Path -LiteralPath $marker -PathType Leaf) {
                throw "Approved source has an invalidation marker: $marker"
            }
        }
    }

    if ([System.IO.Path]::GetExtension($Path) -eq ".json") {
        $marker = Join-Path (Split-Path -Parent $Path) (([System.IO.Path]::GetFileNameWithoutExtension($Path)) + ".INVALIDATED.json")
        if (Test-Path -LiteralPath $marker -PathType Leaf) {
            throw "Approved JSON source has a sibling invalidation marker: $marker"
        }
    }
}

function Read-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required JSON file is missing: $Path"
    }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Resolve-RegistryPrimaryBundleDirs {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Registry
    )

    $resolvedDirs = @()
    foreach ($experimentId in @(0..17 | ForEach-Object { "E$_" })) {
        $entries = @($Registry.experiments | Where-Object { [string]$_.id -eq $experimentId })
        if ($entries.Count -ne 1 -or [string]$entries[0].status -ne "completed") {
            throw "Registry does not contain one completed active entry for $experimentId."
        }
        $entry = $entries[0]
        $primaryValue = $null
        if ($entry.PSObject.Properties.Name -contains "primary_manifest") {
            if ($entry.primary_manifest -is [string]) {
                $primaryValue = [string]$entry.primary_manifest
            } elseif ($null -ne $entry.primary_manifest -and
                $entry.primary_manifest.PSObject.Properties.Name -contains "path") {
                # Transitional compatibility is read-only. Final synthesis has
                # a stricter string-only registry contract.
                $primaryValue = [string]$entry.primary_manifest.path
            }
        }
        if (-not $primaryValue) {
            $candidates = @()
            foreach ($value in @($entry.required_artifacts) + @($entry.evidence)) {
                if (-not $value) { continue }
                $candidate = Resolve-RepoPath -Path ([string]$value)
                if ([System.IO.Path]::GetFileName($candidate) -eq "manifest.json" -and
                    (Split-Path -Leaf (Split-Path -Parent $candidate)) -eq $experimentId) {
                    $candidates += $candidate
                }
            }
            $candidates = @($candidates | Select-Object -Unique)
            if ($candidates.Count -ne 1) {
                throw "Registry must identify exactly one primary manifest for $experimentId; found $($candidates.Count)."
            }
            $primaryValue = $candidates[0]
        }
        $primaryPath = Resolve-RepoPath -Path $primaryValue
        if (-not (Test-Path -LiteralPath $primaryPath -PathType Leaf) -or
            [System.IO.Path]::GetFileName($primaryPath) -ne "manifest.json") {
            throw "Registered primary manifest is missing or invalid for ${experimentId}: $primaryPath"
        }
        $resolvedDirs += Split-Path -Parent $primaryPath
    }
    return @($resolvedDirs)
}

function Assert-CompletedFormalEvidence {
    if (-not (Test-Path -LiteralPath $DashboardEntry -PathType Leaf)) {
        throw "Dashboard entry is missing: $DashboardEntry"
    }
    if (-not (Test-Path -LiteralPath $DashboardStreamlitEntry -PathType Leaf)) {
        throw "Streamlit-safe dashboard entry is missing: $DashboardStreamlitEntry"
    }

    $registry = Read-JsonFile -Path $RegistryPath
    $seenExperimentIds = @{}
    foreach ($bundleDir in $FormalBundleDirs) {
        $manifestPath = Join-Path $bundleDir "manifest.json"
        $manifest = Read-JsonFile -Path $manifestPath
        $experimentId = [string]$manifest.experiment_id
        if ($experimentId -notin @(0..17 | ForEach-Object { "E$_" }) -or
            $seenExperimentIds.ContainsKey($experimentId)) {
            throw "Bundle identity is missing, duplicated, or outside E0-E17 at $manifestPath"
        }
        $seenExperimentIds[$experimentId] = $true
        if ([string]$manifest.status -ne "completed") {
            throw "Formal bundle is not completed: $experimentId"
        }
        if ($experimentId -in @("E9", "E14")) {
            if ([string]$manifest.protocol_id -ne "CONTEXT_CORRECTION_V2" -or
                [string]$manifest.workload_revision -ne "r2" -or
                [string]$manifest.denominator_policy -ne "V2_only_old_V3_excluded" -or
                [string]$manifest.validity_checks.status -ne "pass") {
                throw "Corrected context evidence identity is invalid: $experimentId"
            }
        }
        if ($experimentId -eq "E17") {
            $sourceMode = [string]$manifest.configuration.source_mode
            if ($sourceMode -eq "human_stratified_sample") {
                if ([string]$manifest.protocol_id -ne "E17_HUMAN_STRATIFIED_360_V1" -or
                    [string]$manifest.configuration.evidence_tier -ne "human_stratified_sample" -or
                    [int]$manifest.sampling_contract.population_rows -ne 3299 -or
                    [int]$manifest.sampling_contract.sample_rows -ne 360 -or
                    [int]$manifest.sampling_contract.representative_rows -ne 300 -or
                    [int]$manifest.sampling_contract.targeted_rows -ne 60 -or
                    [bool]$manifest.sampling_contract.targeted_groups_pooled_into_population_estimates -ne $false -or
                    [bool]$manifest.configuration.coverage.full_population_human_reviewed -ne $false) {
                    throw "E17 stratified-human sampling contract is invalid."
                }
            } elseif ($sourceMode -ne "formal_program_corrected_context") {
                throw "E17 is neither corrected formal full review nor admitted stratified human audit."
            }
        }

        $registryEntries = @($registry.experiments | Where-Object { [string]$_.id -eq $experimentId })
        if ($registryEntries.Count -ne 1 -or [string]$registryEntries[0].status -ne "completed") {
            throw "Registry does not mark $experimentId as completed."
        }
    }
    if ($seenExperimentIds.Count -ne 18) {
        throw "Resolved formal bundle set does not contain exactly E0-E17."
    }

    if (-not (Test-Path -LiteralPath $ProgramRoot -PathType Container)) {
        throw "Formal v3 program root is missing: $ProgramRoot"
    }
    $null = Read-JsonFile -Path $BlindFreezePath
    $programManifest = Read-JsonFile -Path $ProgramManifestPath
    if ([string]$programManifest.status -ne "completed") {
        throw "Formal v3 program manifest is not completed."
    }
    foreach ($stageName in @("main", "derived", "stability")) {
        $stage = $programManifest.stages.PSObject.Properties[$stageName]
        if ($null -eq $stage -or [string]$stage.Value.status -ne "completed") {
            throw "Formal program stage is not completed: $stageName"
        }
        $recordedFreeze = [string]$stage.Value.frozen_inputs.blind_freeze.path
        if (-not $recordedFreeze -or (Resolve-RepoPath -Path $recordedFreeze) -ne [System.IO.Path]::GetFullPath($BlindFreezePath)) {
            throw "Formal stage does not reference blind_freeze_v3.json: $stageName"
        }
    }

    foreach ($stageProperty in $programManifest.stages.PSObject.Properties) {
        foreach ($job in @($stageProperty.Value.jobs)) {
            $outDir = [string]$job.matrix_config.out_dir
            if ($outDir -and -not (Test-IsSameOrDescendant -Candidate (Resolve-RepoPath -Path $outDir) -Root $ProgramRoot)) {
                throw "Program manifest job escapes program_final_v3: $outDir"
            }
        }
    }

    $finalManifest = Read-JsonFile -Path (Join-Path $FinalAnalysisDir "manifest.json")
    if ([string]$finalManifest.artifact_type -ne "final_analysis_synthesis" -or
        [string]$finalManifest.status -ne "completed") {
        throw "final_analysis is not a completed final_analysis_synthesis bundle."
    }

    $expectedIds = @(0..17 | ForEach-Object { "E$_" })
    $actualIds = @($finalManifest.registry_experiments | ForEach-Object { [string]$_ })
    if (($actualIds -join "|") -ne ($expectedIds -join "|")) {
        throw "final_analysis does not declare the exact E0-E17 registry sequence."
    }

    $supplementManifestPath = Join-Path $E11SupplementDir "manifest.json"
    $supplementManifest = Read-JsonFile -Path $supplementManifestPath
    if ([string]$supplementManifest.protocol_id -ne "E11_POSTHOC_AMENDMENT_V1" -or
        [string]$supplementManifest.experiment_id -ne "E11" -or
        [string]$supplementManifest.amendment_type -ne "posthoc_protocol_amendment" -or
        [int]$supplementManifest.visualization_revision -ne 2 -or
        [string]$supplementManifest.status -ne "completed" -or
        [string]$supplementManifest.evidence_tier -ne "formal_model_posthoc" -or
        [bool]$supplementManifest.pre_registered -ne $false -or
        [string]$supplementManifest.denominator_policy -ne "excluded_from_original_e11_denominator" -or
        [int]$supplementManifest.case_count -ne 24 -or
        [int]$supplementManifest.logical_run_count -ne 48) {
        throw "E11 post-hoc supplement identity, completion, or claim-boundary flags are invalid."
    }
    $expectedConditions = @("posthoc_off", "posthoc_full")
    $actualConditions = @($supplementManifest.conditions | ForEach-Object { [string]$_ })
    if (($actualConditions -join "|") -ne ($expectedConditions -join "|")) {
        throw "E11 post-hoc supplement conditions drifted."
    }
    $expectedPatterns = @("memory_to_file", "read_to_send", "search_to_api", "tool_output_to_next_action")
    $actualPatterns = @($supplementManifest.pattern_counts.PSObject.Properties.Name | Sort-Object)
    if (($actualPatterns -join "|") -ne ($expectedPatterns -join "|") -or
        @($supplementManifest.pattern_counts.PSObject.Properties | Where-Object { [int]$_.Value -ne 6 }).Count -ne 0) {
        throw "E11 post-hoc supplement pattern counts drifted."
    }

    $scopeBoundary = $finalManifest.e11_scope_boundary
    if ($null -eq $scopeBoundary -or
        [bool]$scopeBoundary.claim_boundary.original_e11_primary_manifest_replaced -ne $false -or
        [bool]$scopeBoundary.claim_boundary.denominators_pooled -ne $false -or
        [bool]$scopeBoundary.claim_boundary.retroactive_preregistration_claimed -ne $false -or
        [bool]$scopeBoundary.posthoc_supplement.pre_registered -ne $false -or
        [int]$scopeBoundary.posthoc_supplement.visualization_revision -ne 2 -or
        (Resolve-RepoPath -Path ([string]$scopeBoundary.posthoc_supplement.manifest_path)) -ne [System.IO.Path]::GetFullPath($supplementManifestPath)) {
        throw "final_analysis does not preserve the E11 original/post-hoc claim boundary."
    }

    foreach ($source in $ApprovedBoundarySources) {
        Assert-SourceNotInvalidated -Path $source
        $sourcePath = [System.IO.Path]::GetFullPath($source)
        foreach ($excluded in $RejectedLegacySources) {
            $excludedPath = [System.IO.Path]::GetFullPath($excluded)
            if (Test-IsSameOrDescendant -Candidate $sourcePath -Root $excludedPath) {
                throw "Excluded evidence source entered the final allowlist: $sourcePath"
            }
        }
    }
}

function Assert-HashVerifiedEvidenceChain {
    # The public report evidence loader is also the strict cross-artifact
    # validator: it rehashes every E0-E17 source, the E18 artifact ledger and
    # figure manifest, and confirms that the live registry/input ledger still
    # matches the snapshot admitted by final_analysis.
    # Keep -c on one physical line: Windows PowerShell 5.1 can split a
    # multiline here-string into multiple argv elements for native commands.
    $validationCode = 'import sys; from scripts.build_final_report import load_report_evidence; evidence = load_report_evidence(repository_root=sys.argv[1], analysis_dir=sys.argv[2], registry_path=sys.argv[3]); assert len(evidence.bundles) == 18 and len(evidence.charts) == 13'

    Push-Location $RepoRoot
    try {
        & $PythonExecutable -c $validationCode $RepoRoot $FinalAnalysisDir $RegistryPath
        if ($LASTEXITCODE -ne 0) {
            throw "Hash-verified dashboard evidence validation failed with code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
}

$registryForAllowlist = Read-JsonFile -Path $RegistryPath
$FormalBundleDirs = Resolve-RegistryPrimaryBundleDirs -Registry $registryForAllowlist
$DashboardSources = @($FormalBundleDirs) + @($ProgramManifestPath, $E11SupplementDir, $FinalAnalysisDir)
$ApprovedBoundarySources = @($DashboardSources) + @($V3ProvenanceSources)

Assert-CompletedFormalEvidence
Assert-HashVerifiedEvidenceChain

Write-Host "Final dashboard evidence gate passed." -ForegroundColor Green
Write-Host "Dashboard sources:" -ForegroundColor Cyan
$DashboardSources | ForEach-Object { Write-Host "  $_" }
Write-Host "Pinned v3 provenance:" -ForegroundColor Cyan
$V3ProvenanceSources | ForEach-Object { Write-Host "  $_" }
Write-Host "Rejected legacy/superseded sources:" -ForegroundColor Yellow
$RejectedLegacySources | ForEach-Object { Write-Host "  $_" }

if ($ValidateOnly) {
    return
}

$streamlitArgs = @("-m", "streamlit", "run", $DashboardStreamlitEntry, "--")
foreach ($bundleDir in $FormalBundleDirs) {
    $streamlitArgs += @("--bundle", $bundleDir)
}
$streamlitArgs += @(
    "--program-manifest", $ProgramManifestPath,
    "--bundle", $FinalAnalysisDir
)

# The raw amendment directory is hash-gated and allowlisted above, but it is
# not passed as a second E11 bundle. The E18 bundle supplies the verified 13th
# faceted chart; avoiding a duplicate experiment_id also prevents the post-hoc
# denominator from being mistaken for the original E11 cohort.

Push-Location $RepoRoot
try {
    & $PythonExecutable @streamlitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Streamlit exited with code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
