[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$ScoredAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$registration = Get-Content -LiteralPath (Join-Path $root "release\custodian_registration_v2.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$output = Join-Path $root "receipts\custodian_scoring_result_seal_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 seal-scoring-results `
        --custody-manifest ".\release\blind_custody_v2.json" `
        --execution-output-seal ".\incoming_from_developer\execution_output_seal_v2.json" `
        --output-package ".\incoming_from_developer\output_package_v2.jsonl" `
        --label-release-seal ".\receipts\label_release_seal_v2.json" `
        --label-file ".\private\labels\blind_labels_v2.jsonl" `
        --scoring-results ".\private\scoring\scoring_results_v2.jsonl" `
        --scored-at $ScoredAt --custodian-id ([string]$registration.custodian_id) `
        --write-result-seal $output
    if ($LASTEXITCODE -ne 0) { throw "scoring result seal failed" }
} finally { Pop-Location }
