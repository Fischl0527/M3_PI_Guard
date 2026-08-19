[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunDirectory,
    [string]$PythonExe = "F:\robot\Anaconda3\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ResolvedRunDirectory = [System.IO.Path]::GetFullPath($RunDirectory)
$VerificationRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $ProjectRoot "outputs\verification")
)
if (-not $ResolvedRunDirectory.StartsWith(
    $VerificationRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Harness receipt directory must stay under outputs/verification."
}

$RunningPath = Join-Path $ResolvedRunDirectory "running.json"
$StdoutPath = Join-Path $ResolvedRunDirectory "stdout.log"
$StderrPath = Join-Path $ResolvedRunDirectory "stderr.log"
$ReceiptPath = Join-Path $ResolvedRunDirectory "receipt.json"
$VerifyScript = Join-Path $ProjectRoot "harness\scripts\verify.ps1"

if (-not (Test-Path -LiteralPath $ResolvedRunDirectory -PathType Container)) {
    throw "Harness run directory was not pre-created by the launcher."
}
if (Test-Path -LiteralPath $ReceiptPath) {
    throw "Harness receipt already exists; this helper is single-use."
}

$StartedAt = [DateTimeOffset]::Now
$env:DEEPSEEK_API_KEY = $null
$env:GEMINI_API_KEY = $null
$env:GOOGLE_API_KEY = $null

$Running = [ordered]@{
    schema_version = "m3-harness-detached-running-1.0"
    status = "running"
    started_at = $StartedAt.ToString("o")
    helper_pid = $PID
    project_root = $ProjectRoot
    verify_script_sha256 = (Get-FileHash -LiteralPath $VerifyScript -Algorithm SHA256).Hash.ToLowerInvariant()
    api_environment_variables_scrubbed = @(
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY"
    )
    network_or_provider_call_authorized = $false
}
$Running | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $RunningPath -Encoding UTF8

$Child = Start-Process -FilePath "C:\Program Files\PowerShell\7\pwsh.exe" `
    -ArgumentList @("-NoProfile", "-File", $VerifyScript, "-PythonExe", $PythonExe) `
    -WorkingDirectory $ProjectRoot -RedirectStandardOutput $StdoutPath `
    -RedirectStandardError $StderrPath -WindowStyle Hidden -Wait -PassThru
$CompletedAt = [DateTimeOffset]::Now

$Receipt = [ordered]@{
    schema_version = "m3-harness-detached-receipt-1.0"
    status = if ($Child.ExitCode -eq 0) { "completed_exit_zero" } else { "completed_nonzero" }
    started_at = $StartedAt.ToString("o")
    completed_at = $CompletedAt.ToString("o")
    helper_pid = $PID
    child_pid = $Child.Id
    operating_system_exit_code_directly_observed = $true
    exit_code = $Child.ExitCode
    verify_script_sha256 = (Get-FileHash -LiteralPath $VerifyScript -Algorithm SHA256).Hash.ToLowerInvariant()
    helper_script_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    running_sha256 = (Get-FileHash -LiteralPath $RunningPath -Algorithm SHA256).Hash.ToLowerInvariant()
    stdout_sha256 = (Get-FileHash -LiteralPath $StdoutPath -Algorithm SHA256).Hash.ToLowerInvariant()
    stderr_sha256 = (Get-FileHash -LiteralPath $StderrPath -Algorithm SHA256).Hash.ToLowerInvariant()
    stdout_bytes = (Get-Item -LiteralPath $StdoutPath).Length
    stderr_bytes = (Get-Item -LiteralPath $StderrPath).Length
    api_environment_variables_scrubbed = @(
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY"
    )
    network_or_provider_call_authorized = $false
}
$Receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
exit $Child.ExitCode
