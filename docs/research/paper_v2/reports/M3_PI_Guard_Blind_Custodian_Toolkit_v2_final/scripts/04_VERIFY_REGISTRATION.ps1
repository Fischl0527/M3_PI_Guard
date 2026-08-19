[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$VerifierId,
    [Parameter(Mandatory=$true)][string]$VerifiedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "receipts\custodian_registration_verifier_receipt_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 verify-registration `
        --registration ".\release\custodian_registration_v2.json" `
        --custodian-public-key ".\release\custodian_public_key.pem" `
        --verifier-id $VerifierId --verified-at $VerifiedAt --write-receipt $output
    if ($LASTEXITCODE -ne 0) { throw "registration verification failed" }
} finally { Pop-Location }
