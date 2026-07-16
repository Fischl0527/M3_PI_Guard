[CmdletBinding()]
param(
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $Root

if (-not $PythonExe) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

if (-not (Test-Path -LiteralPath "tests" -PathType Container)) {
    throw "FAIL: local tests directory is missing"
}

& $PythonExe -m pytest -q
exit $LASTEXITCODE
