$ErrorActionPreference = "Stop"

# DAY5 Dashboard 启动配置区。默认指向 Qwen2.5 代表样本矩阵。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$LogsDir = "outputs/runs/day5_qwen25_matrix"
$Metrics = "outputs/metrics/day5_qwen25_summary.csv"

Set-Location $RepoRoot

streamlit run m3_eval/dashboard.py -- --logs $LogsDir --metrics $Metrics
