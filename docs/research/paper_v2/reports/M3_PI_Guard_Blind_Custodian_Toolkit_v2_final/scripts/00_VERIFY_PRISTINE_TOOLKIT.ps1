[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe ".\scripts\verify_toolkit_v2.py" --root $root --pristine
    if ($LASTEXITCODE -ne 0) { throw "toolkit pristine verification failed" }
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 --help
    if ($LASTEXITCODE -ne 0) { throw "closeout module help failed" }
} finally {
    Pop-Location
}
