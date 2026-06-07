$ErrorActionPreference = "Stop"

# DAY3 评测汇总配置区。当前 m3_eval 输出 JSON；C 队员后续可扩展 CSV。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$Cases = "m3_attacks/cases/all_cases.jsonl"
$MetricsDir = "outputs/metrics"

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $MetricsDir | Out-Null

python -m m3_eval.evaluate `
  --cases $Cases `
  --baseline "outputs/runs/day3_stub_baseline_all.jsonl" `
  --guarded "outputs/runs/day3_stub_guarded_all.jsonl" `
  --out "outputs/metrics/day3_stub_summary.json"

if ((Test-Path "outputs/runs/day3_qwen25_baseline_20.jsonl") -and `
    (Test-Path "outputs/runs/day3_qwen25_guarded_20.jsonl")) {
  python -m m3_eval.evaluate `
    --cases $Cases `
    --baseline "outputs/runs/day3_qwen25_baseline_20.jsonl" `
    --guarded "outputs/runs/day3_qwen25_guarded_20.jsonl" `
    --out "outputs/metrics/day3_qwen25_summary_20.json"
}

Write-Host "DAY3 evaluation complete."
