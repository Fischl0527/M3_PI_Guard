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
foreach ($Artifact in @($RunningPath, $StdoutPath, $StderrPath, $ReceiptPath)) {
    if (Test-Path -LiteralPath $Artifact) {
        throw "Harness v2 helper is single-use; existing artifact: $Artifact"
    }
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python executable does not exist: $PythonExe"
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Value
    )
    $Temporary = "$Path.tmp-$PID"
    $Json = $Value | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText(
        $Temporary,
        $Json + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $Temporary -Destination $Path
}

$ScrubbedEnvironmentVariables = @(
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "M3_CANARY_SECRET_API_KEY",
    "M3_FRONTIER_API_CONSENT",
    "OPENAI_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY"
)
foreach ($VariableName in $ScrubbedEnvironmentVariables) {
    Remove-Item -LiteralPath "Env:$VariableName" -ErrorAction SilentlyContinue
}

$StartedAt = [DateTimeOffset]::Now
$VerifyShaBefore = (
    Get-FileHash -LiteralPath $VerifyScript -Algorithm SHA256
).Hash.ToLowerInvariant()
$HelperShaBefore = (
    Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256
).Hash.ToLowerInvariant()

$Child = Start-Process -FilePath "C:\Program Files\PowerShell\7\pwsh.exe" `
    -ArgumentList @("-NoProfile", "-File", $VerifyScript, "-PythonExe", $PythonExe) `
    -WorkingDirectory $ProjectRoot -RedirectStandardOutput $StdoutPath `
    -RedirectStandardError $StderrPath -WindowStyle Hidden -PassThru

$Running = [ordered]@{
    schema_version = "m3-harness-detached-running-2.0"
    status = "running"
    started_at = $StartedAt.ToString("o")
    helper_pid = $PID
    child_pid = $Child.Id
    project_root = $ProjectRoot
    verify_script_sha256 = $VerifyShaBefore
    helper_script_sha256 = $HelperShaBefore
    api_environment_variables_scrubbed = $ScrubbedEnvironmentVariables
    network_or_provider_call_authorized = $false
    automatic_restart = $false
}
Write-JsonAtomic -Path $RunningPath -Value $Running

$Child.WaitForExit()
$Child.Refresh()
$CompletedAt = [DateTimeOffset]::Now
$ChildExitCode = $Child.ExitCode
$VerifyShaAfter = (
    Get-FileHash -LiteralPath $VerifyScript -Algorithm SHA256
).Hash.ToLowerInvariant()
$HelperShaAfter = (
    Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256
).Hash.ToLowerInvariant()
$Stdout = [System.IO.File]::ReadAllText($StdoutPath)
$FailureMarkerCount = [regex]::Matches($Stdout, "(?m)^FAIL: ").Count
$ZeroMarkerCount = [regex]::Matches(
    $Stdout,
    "(?m)^Verification failed=0\s*$"
).Count
$AnyAggregateMarkerCount = [regex]::Matches(
    $Stdout,
    "(?m)^Verification failed=\d+\s*$"
).Count
$TerminalLineIsZero = $Stdout.TrimEnd().EndsWith("Verification failed=0")

$Checks = [ordered]@{
    child_exit_code_zero = ($ChildExitCode -eq 0)
    verifier_source_stable = ($VerifyShaBefore -eq $VerifyShaAfter)
    helper_source_stable = ($HelperShaBefore -eq $HelperShaAfter)
    exactly_one_aggregate_marker = ($AnyAggregateMarkerCount -eq 1)
    exactly_one_zero_marker = ($ZeroMarkerCount -eq 1)
    aggregate_marker_is_terminal = $TerminalLineIsZero
    no_failed_harness_stage = ($FailureMarkerCount -eq 0)
    network_or_provider_call_authorized_false = $true
}
$EvidencePassed = -not ($Checks.Values -contains $false)
if ($EvidencePassed) {
    $ReceiptExitCode = 0
    $Status = "completed_exit_zero_evidence_pass"
}
elseif ($ChildExitCode -ne 0) {
    $ReceiptExitCode = $ChildExitCode
    $Status = "completed_child_nonzero"
}
elseif ($VerifyShaBefore -ne $VerifyShaAfter -or $HelperShaBefore -ne $HelperShaAfter) {
    $ReceiptExitCode = 86
    $Status = "completed_source_drift"
}
else {
    $ReceiptExitCode = 87
    $Status = "completed_invalid_terminal_evidence"
}

$Receipt = [ordered]@{
    schema_version = "m3-harness-detached-receipt-2.0"
    status = $Status
    started_at = $StartedAt.ToString("o")
    completed_at = $CompletedAt.ToString("o")
    elapsed_seconds = [Math]::Round(($CompletedAt - $StartedAt).TotalSeconds, 3)
    helper_pid = $PID
    child_pid = $Child.Id
    operating_system_exit_code_directly_observed = $true
    child_exit_code = $ChildExitCode
    exit_code = $ReceiptExitCode
    evidence_gate_passed = $EvidencePassed
    checks = $Checks
    verify_script_sha256_before = $VerifyShaBefore
    verify_script_sha256_after = $VerifyShaAfter
    helper_script_sha256_before = $HelperShaBefore
    helper_script_sha256_after = $HelperShaAfter
    running_sha256 = (Get-FileHash -LiteralPath $RunningPath -Algorithm SHA256).Hash.ToLowerInvariant()
    stdout_sha256 = (Get-FileHash -LiteralPath $StdoutPath -Algorithm SHA256).Hash.ToLowerInvariant()
    stderr_sha256 = (Get-FileHash -LiteralPath $StderrPath -Algorithm SHA256).Hash.ToLowerInvariant()
    stdout_bytes = (Get-Item -LiteralPath $StdoutPath).Length
    stderr_bytes = (Get-Item -LiteralPath $StderrPath).Length
    aggregate_marker_count = $AnyAggregateMarkerCount
    zero_marker_count = $ZeroMarkerCount
    failed_harness_stage_count = $FailureMarkerCount
    api_environment_variables_scrubbed = $ScrubbedEnvironmentVariables
    network_or_provider_call_authorized = $false
    automatic_restart = $false
}
Write-JsonAtomic -Path $ReceiptPath -Value $Receipt
exit $ReceiptExitCode
