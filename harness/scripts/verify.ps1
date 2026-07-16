[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [switch]$RequireExperimentsComplete
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $Root

if (-not $PythonExe) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

$script:Failed = 0

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Invoke-Check {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Host "`n== $Name =="
    try {
        & $Action
        Write-Host "PASS: $Name"
    }
    catch {
        Write-Host "FAIL: $Name"
        Write-Host $_.Exception.Message
        $script:Failed = 1
    }
}

Invoke-Check "Harness files" {
    $Required = @(
        "AGENTS.md", "harness/README.md",
        "harness/docs/architecture.md", "harness/docs/development-rules.md",
        "harness/docs/decision-log.md", "harness/docs/agent-guide.md",
        "harness/state/progress.md", "harness/state/memory.md",
        "harness/state/current-task.md", "harness/state/session-handoff.md",
        "harness/state/task-history.md", "harness/state/failure-log.md",
        "harness/specs/product-spec.md", "harness/specs/technical-spec.md",
        "harness/specs/acceptance-criteria.md",
        "harness/features/feature_list.json", "experiments/registry.json",
        "harness/workspaces/runpro/10_analysis/approval-gate.md",
        "harness/workspaces/runpro/10_analysis/requirement-ledger.md",
        "harness/scripts/init.sh", "harness/scripts/verify.sh",
        "harness/scripts/test.sh", "harness/scripts/cleanup.sh",
        "harness/scripts/verify.ps1", "harness/scripts/test.ps1",
        "harness/config/permissions.yaml", "harness/config/policies.md",
        "harness/config/workflow.md"
    )
    $Missing = @($Required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($Missing.Count -gt 0) {
        throw "Missing Harness files: $($Missing -join ', ')"
    }
}

Invoke-Check "Harness and project source boundary" {
    $LegacyHarnessPaths = @(
        "README_AGENT.md",
        ".agent",
        "features",
        "specs",
        "tasks",
        "runpro_workspace",
        "agent/current-task.md",
        "agent/failure-log.md",
        "agent/memory.md",
        "agent/progress.md",
        "agent/session-handoff.md",
        "agent/task-history.md"
    )
    $LegacyFound = @($LegacyHarnessPaths | Where-Object { Test-Path -LiteralPath $_ })
    if ($LegacyFound.Count -gt 0) {
        throw "Legacy Harness paths remain mixed with project source: $($LegacyFound -join ', ')"
    }
    foreach ($ProjectPath in @(
        "m3_core", "m3_guard", "m3_eval", "m3_attacks",
        "experiments", "protocols", "schemas", "fixtures", "tests", "scripts"
    )) {
        if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) {
            throw "Project source directory is missing from repository root: $ProjectPath"
        }
    }
}

Invoke-Check "JSON contracts" {
    foreach ($Path in @(
        "harness/features/feature_list.json",
        "experiments/registry.json",
        "schemas/attack_case.schema.json",
        "schemas/run_log.schema.json",
        "schemas/tool_call.schema.json"
    )) {
        Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null
        Write-Host "parsed $Path"
    }
}

Invoke-Check "PowerShell syntax" {
    foreach ($Path in @(
        "harness/scripts/verify.ps1",
        "harness/scripts/test.ps1",
        "scripts/run_final_dashboard.ps1"
    )) {
        $Tokens = $null
        $Errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            (Resolve-Path -LiteralPath $Path).Path,
            [ref]$Tokens,
            [ref]$Errors
        ) | Out-Null
        if ($Errors.Count -gt 0) {
            throw "$Path parse errors: $($Errors.Message -join '; ')"
        }
    }
}

if (Get-Command bash -ErrorAction SilentlyContinue) {
    Invoke-Check "Shell syntax" {
        Invoke-External "bash" @(
            "-n",
            "harness/scripts/init.sh",
            "harness/scripts/verify.sh",
            "harness/scripts/test.sh",
            "harness/scripts/cleanup.sh"
        )
    }
}

Invoke-Check "Python compile" {
    Invoke-External $PythonExe @("-m", "compileall", "-q", "m3_core", "m3_guard", "m3_attacks", "m3_eval", "experiments", "tests", "scripts")
}

Invoke-Check "Unit and integration tests" {
    Invoke-External "powershell" @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        "harness/scripts/test.ps1", "-PythonExe", $PythonExe
    )
}

Invoke-Check "Experiment registry structure" {
    Invoke-External $PythonExe @("-m", "experiments.validate_registry")
}

if (Test-Path -LiteralPath "outputs/experiments/e17_source_index_corrected_v2.json" -PathType Leaf) {
    Invoke-Check "Corrected E17 source index" {
        Invoke-External $PythonExe @("scripts/build_e17_source_index.py", "--check")
    }
}

if ($RequireExperimentsComplete) {
    Invoke-Check "Experiment registry complete" {
        Invoke-External $PythonExe @("-m", "experiments.validate_registry", "--require-complete")
    }
}

Write-Host "`nVerification failed=$script:Failed"
exit $script:Failed
