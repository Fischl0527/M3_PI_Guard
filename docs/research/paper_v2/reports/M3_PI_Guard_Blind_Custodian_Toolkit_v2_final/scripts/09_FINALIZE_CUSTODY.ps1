[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "release\blind_custody_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 finalize-custody `
        --unsigned-custody ".\signatures\unsigned_custody_v2.json" `
        --signature-base64-file ".\signatures\custody_signature_base64.txt" `
        --write-custody $output
    if ($LASTEXITCODE -ne 0) { throw "custody finalization failed" }
} finally { Pop-Location }
