[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$ReleasedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$registration = Get-Content -LiteralPath (Join-Path $root "release\custodian_registration_v2.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$output = Join-Path $root "receipts\label_release_seal_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 release-labels-for-scoring `
        --custody-manifest ".\release\blind_custody_v2.json" `
        --label-file ".\private\labels\blind_labels_v2.jsonl" `
        --execution-output-seal ".\incoming_from_developer\execution_output_seal_v2.json" `
        --released-at $ReleasedAt --custodian-id ([string]$registration.custodian_id) `
        --write-release-seal $output
    if ($LASTEXITCODE -ne 0) { throw "label release for scoring failed" }
} finally { Pop-Location }
