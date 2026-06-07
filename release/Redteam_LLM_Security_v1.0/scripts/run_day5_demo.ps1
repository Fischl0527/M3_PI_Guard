$ErrorActionPreference = "Stop"

# DAY5 现场 demo 配置区。LaunchDashboard 改为 $true 时会自动启动 Streamlit。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$Cases = "fixtures/demo_cases.jsonl"
$Model = "m3-target-qwen25-7b"
$DefenseModes = "baseline,full_guard"
$OutDir = "outputs/runs/day5_demo_matrix"
$RunPrefix = "day5_demo"
$MetricsOut = "outputs/metrics/day5_demo_summary.csv"
$MaxSteps = 5
$LaunchDashboard = $false

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
  --notes "DAY5 final live demo matrix"

python -m m3_eval.evaluate `
  --log-dir $OutDir `
  --cases $Cases `
  --out $MetricsOut

if ($LaunchDashboard) {
  streamlit run m3_eval/dashboard.py -- --logs $OutDir --metrics $MetricsOut
}

Write-Host "DAY5 demo complete: $OutDir"
