$ErrorActionPreference = "Stop"

# DAY4 Qwen 代表样本矩阵配置区。
# 如果演示电脑时间紧，把 DefenseModes 改成 "baseline,full_guard" 即为最低验收。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$Cases = "fixtures/day4_representative_cases.jsonl"
$Model = "m3-target-qwen25-7b"
$DefenseModes = "baseline,keyword_only,policy_only,full_guard"
$OutDir = "outputs/runs/day4_qwen25_matrix"
$RunPrefix = "day4_qwen25_rep"
$MaxSteps = 5

Set-Location $RepoRoot

python -m m3_core.run_matrix `
  --cases $Cases `
  --backend ollama `
  --model $Model `
  --defense-modes $DefenseModes `
  --out-dir $OutDir `
  --run-prefix $RunPrefix `
  --max-steps $MaxSteps `
  --notes "DAY4 Qwen2.5 representative ablation matrix"

Write-Host "DAY4 Qwen matrix complete: $OutDir"
