[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "receipts\custodian_scoring_attestation_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 finalize-scoring-attestation `
        --unsigned-attestation ".\signatures\unsigned_scoring_attestation_v2.json" `
        --signature-base64-file ".\signatures\scoring_attestation_signature_base64.txt" `
        --write-attestation $output
    if ($LASTEXITCODE -ne 0) { throw "scoring attestation finalization failed" }
} finally { Pop-Location }
