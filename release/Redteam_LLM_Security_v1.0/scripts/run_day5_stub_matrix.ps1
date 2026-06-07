$ErrorActionPreference = "Stop"

# DAY5 stub 全量四模式最终实验配置区。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$Cases = "m3_attacks/cases/all_cases.jsonl"
$DefenseModes = "baseline,keyword_only,policy_only,full_guard"
$OutDir = "outputs/runs/day5_stub_matrix"
$RunPrefix = "day5_stub_all"
$MaxSteps = 5

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path "outputs/metrics" | Out-Null
New-Item -ItemType Directory -Force -Path "sandbox/outbox" | Out-Null
New-Item -ItemType Directory -Force -Path "sandbox/logs" | Out-Null
Remove-Item "sandbox/outbox/day5_outbox.jsonl" -ErrorAction SilentlyContinue
Remove-Item "sandbox/logs/day5_tool_events.jsonl" -ErrorAction SilentlyContinue

python -m m3_core.run_matrix `
  --cases $Cases `
  --backend stub `
  --defense-modes $DefenseModes `
  --out-dir $OutDir `
  --run-prefix $RunPrefix `
  --run-group day5 `
  --max-steps $MaxSteps `
  --notes "DAY5 stub final full-sample ablation matrix"

Write-Host "DAY5 stub matrix complete: $OutDir"
