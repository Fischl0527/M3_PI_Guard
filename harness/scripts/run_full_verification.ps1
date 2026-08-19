[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PythonExe,
    [Parameter(Mandatory = $true)][string]$ReceiptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VerifyScript = (Resolve-Path (
    Join-Path $PSScriptRoot "verify.ps1"
)).Path
$ResolvedPython = (Resolve-Path -LiteralPath $PythonExe).Path
$ResolvedReceipt = [System.IO.Path]::GetFullPath((
    Join-Path $Root $ReceiptPath
))

if (-not $ResolvedReceipt.StartsWith(
    [System.IO.Path]::GetFullPath((Join-Path $Root "outputs")),
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "ReceiptPath must stay under the repository outputs directory."
}

$ReceiptDirectory = Split-Path -Parent $ResolvedReceipt
New-Item -ItemType Directory -Path $ReceiptDirectory -Force | Out-Null
$StartedAt = [DateTimeOffset]::Now.ToString("o")

& $VerifyScript -PythonExe $ResolvedPython
$VerificationExitCode = $LASTEXITCODE

$Receipt = [ordered]@{
    schema_version = "m3-harness-full-verification-receipt-1.0"
    started_at = $StartedAt
    completed_at = [DateTimeOffset]::Now.ToString("o")
    python_executable = $ResolvedPython
    verification_script = $VerifyScript
    exit_code = $VerificationExitCode
}
$Receipt |
    ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath $ResolvedReceipt -Encoding UTF8

exit $VerificationExitCode
