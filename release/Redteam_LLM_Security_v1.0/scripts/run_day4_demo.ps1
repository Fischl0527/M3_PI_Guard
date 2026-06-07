$ErrorActionPreference = "Stop"

# DAY4 演示链路配置区：小样本 Qwen baseline/full_guard -> 指标 CSV。
# LaunchDashboard 改成 $true 时，会在指标生成后打开 Streamlit Dashboard。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$Cases = "fixtures/demo_cases.jsonl"
$Model = "m3-target-qwen25-7b"
$DefenseModes = "baseline,full_guard"
$OutDir = "outputs/runs/day4_demo_matrix"
$RunPrefix = "day4_demo"
$MetricsOut = "outputs/metrics/day4_demo_summary.csv"
$MaxSteps = 5
$LaunchDashboard = $false

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path "outputs/metrics" | Out-Null

python -m m3_core.run_matrix `
  --cases $Cases `
  --backend ollama `
  --model $Model `
  --defense-modes $DefenseModes `
  --out-dir $OutDir `
  --run-prefix $RunPrefix `
  --max-steps $MaxSteps `
  --notes "DAY4 live demo matrix"

python -m m3_eval.evaluate `
  --logs "$OutDir/${RunPrefix}_baseline.jsonl" "$OutDir/${RunPrefix}_full_guard.jsonl" `
  --cases $Cases `
  --out $MetricsOut

if ($LaunchDashboard) {
  streamlit run m3_eval/dashboard.py -- --logs $OutDir --metrics $MetricsOut
}

Write-Host "DAY4 demo complete: $OutDir"
