$ErrorActionPreference = "Stop"

# DAY3 stub 全量运行配置区。需要改路径时只改这里。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$Cases = "m3_attacks/cases/all_cases.jsonl"
$BaselineOut = "outputs/runs/day3_stub_baseline_all.jsonl"
$GuardedOut = "outputs/runs/day3_stub_guarded_all.jsonl"
$BaselineCsv = "outputs/runs/day3_stub_baseline_all.csv"
$GuardedCsv = "outputs/runs/day3_stub_guarded_all.csv"
$MaxSteps = 5

Set-Location $RepoRoot

python -m m3_core.run_batch `
  --cases $Cases `
  --backend stub `
  --defense baseline `
  --max-steps $MaxSteps `
  --out $BaselineOut `
  --csv-out $BaselineCsv

python -m m3_core.run_batch `
  --cases $Cases `
  --backend stub `
  --defense guarded `
  --max-steps $MaxSteps `
  --out $GuardedOut `
  --csv-out $GuardedCsv

Write-Host "DAY3 stub runs complete."
