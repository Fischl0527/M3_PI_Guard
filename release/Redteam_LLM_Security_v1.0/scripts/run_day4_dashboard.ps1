$ErrorActionPreference = "Stop"

# DAY4 Dashboard 启动配置区。优先指向 Qwen 代表样本矩阵。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$LogsDir = "outputs/runs/day4_qwen25_matrix"
$Metrics = "outputs/metrics/day4_qwen25_ablation_summary.csv"

Set-Location $RepoRoot

streamlit run m3_eval/dashboard.py -- --logs $LogsDir --metrics $Metrics
