[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$SignedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$registration = Get-Content -LiteralPath (Join-Path $root "release\custodian_registration_v2.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$output = Join-Path $root "signatures\unsigned_scoring_attestation_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 build-unsigned-scoring-attestation `
        --scoring-result-seal ".\receipts\custodian_scoring_result_seal_v2.json" `
        --custody-manifest ".\release\blind_custody_v2.json" `
        --registration ".\release\custodian_registration_v2.json" `
        --custodian-id ([string]$registration.custodian_id) `
        --signed-at $SignedAt --write-unsigned $output
    if ($LASTEXITCODE -ne 0) { throw "unsigned scoring attestation build failed" }
} finally { Pop-Location }
