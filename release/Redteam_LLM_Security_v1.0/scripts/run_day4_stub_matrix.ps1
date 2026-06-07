$ErrorActionPreference = "Stop"

# DAY4 stub 全量四模式矩阵配置区。需要调整样本或输出目录时只改这里。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$Cases = "m3_attacks/cases/all_cases.jsonl"
$DefenseModes = "baseline,keyword_only,policy_only,full_guard"
$OutDir = "outputs/runs/day4_stub_matrix"
$RunPrefix = "day4_stub_all"
$MaxSteps = 5

Set-Location $RepoRoot

python -m m3_core.run_matrix `
  --cases $Cases `
  --backend stub `
  --defense-modes $DefenseModes `
  --out-dir $OutDir `
  --run-prefix $RunPrefix `
  --max-steps $MaxSteps `
  --notes "DAY4 stub full-sample ablation matrix"

Write-Host "DAY4 stub matrix complete: $OutDir"
