$ErrorActionPreference = "Stop"

# DAY5 Qwen2.5 代表样本最终实验配置区。
# 最低验收是 baseline,full_guard；需要完整消融时改成 baseline,keyword_only,policy_only,full_guard。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$Cases = "fixtures/day5_representative_cases.jsonl"
$Model = "m3-target-qwen25-7b"
$DefenseModes = "baseline,full_guard"
$OutDir = "outputs/runs/day5_qwen25_matrix"
$RunPrefix = "day5_qwen25_rep"
$MaxSteps = 5

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path "outputs/metrics" | Out-Null

python -m m3_core.run_matrix `
  --cases $Cases `
  --backend ollama `
  --model $Model `
  --defense-modes $DefenseModes `
  --out-dir $OutDir `
  --run-prefix $RunPrefix `
  --run-group day5 `
  --max-steps $MaxSteps `
  --notes "DAY5 Qwen2.5 representative final validation"

python -m m3_core.check_logs `
  --log-dir $OutDir `
  --out "outputs/metrics/day5_log_audit.json"

Write-Host "DAY5 Qwen matrix complete: $OutDir"
