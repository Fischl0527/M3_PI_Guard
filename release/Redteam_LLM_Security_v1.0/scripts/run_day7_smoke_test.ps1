$ErrorActionPreference = "Stop"

# DAY7 smoke test configuration. Run this script from the release root or from
# the scripts directory; paths are resolved back to the package root.
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$PackageRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$CasesPath = "fixtures/demo_cases.jsonl"
$OutDir = "outputs/runs/day7_smoke_stub"
$RunPrefix = "day7_smoke"
$SummaryPath = "outputs/metrics/day7_smoke_summary.csv"
$ResultPath = "outputs/quality/day7_smoke_test_result.md"

Set-Location $PackageRoot
New-Item -ItemType Directory -Force -Path "outputs/quality" | Out-Null

Write-Host "==== DAY7 Smoke Test ===="
Write-Host "Package root: $PackageRoot"

python -m m3_core.run_matrix `
  --cases $CasesPath `
  --backend stub `
  --defense-modes baseline,full_guard `
  --out-dir $OutDir `
  --run-prefix $RunPrefix `
  --max-steps 5

python -m m3_eval.evaluate `
  --log-dir $OutDir `
  --cases $CasesPath `
  --out $SummaryPath

$BaselineLog = Join-Path $PackageRoot "$OutDir/$RunPrefix`_baseline.jsonl"
$GuardLog = Join-Path $PackageRoot "$OutDir/$RunPrefix`_full_guard.jsonl"
$BaselineRows = if (Test-Path $BaselineLog) { (Get-Content $BaselineLog | Where-Object { $_.Trim() }).Count } else { 0 }
$GuardRows = if (Test-Path $GuardLog) { (Get-Content $GuardLog | Where-Object { $_.Trim() }).Count } else { 0 }
$DemoCaseCount = (Get-Content $CasesPath | Where-Object { $_.Trim() }).Count
$Succeeded = (Test-Path $BaselineLog) -and (Test-Path $GuardLog) -and (Test-Path $SummaryPath)

$Result = @(
  "# DAY7 Smoke Test Result",
  "",
  "## Test Time",
  "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
  "",
  "## Test Directory",
  $PackageRoot,
  "",
  "## Test Commands",
  "- stub demo matrix",
  "- evaluate log directory",
  "",
  "## Result",
  "- demo_cases: $DemoCaseCount",
  "- baseline_log: $BaselineLog",
  "- baseline_rows: $BaselineRows",
  "- full_guard_log: $GuardLog",
  "- full_guard_rows: $GuardRows",
  "- summary_csv: $(Join-Path $PackageRoot $SummaryPath)",
  "- success: $Succeeded",
  "",
  "## Issues",
  "$(if ($Succeeded) { 'None.' } else { 'Smoke test did not produce all expected files.' })",
  "",
  "## Conclusion",
  "$(if ($Succeeded) { 'The release package can run the local stub demo independently.' } else { 'The release package needs manual inspection.' })"
)
$Result | Set-Content -Path $ResultPath -Encoding UTF8

Write-Host "Smoke test finished."
Write-Host "Result written: $ResultPath"
