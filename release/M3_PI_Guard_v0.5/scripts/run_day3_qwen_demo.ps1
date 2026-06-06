$ErrorActionPreference = "Stop"

# DAY3 Qwen 代表样本运行配置区。Qwen 可能较慢，可把 RunTwentyCases 改为 $false。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$DemoCases = "fixtures/demo_cases.jsonl"
$AllCases = "m3_attacks/cases/all_cases.jsonl"
$Model = "m3-target-qwen25-7b"
$MaxSteps = 5
$Limit = 20
$Families = "direct_jailbreak,rag_indirect,multilingual_t2l,json_rpc,tool_output_injection"
$RunTwentyCases = $true

Set-Location $RepoRoot

python -m m3_core.run_batch `
  --cases $DemoCases `
  --backend ollama `
  --model $Model `
  --defense baseline `
  --max-steps $MaxSteps `
  --out "outputs/runs/day3_qwen25_demo_baseline.jsonl" `
  --csv-out "outputs/runs/day3_qwen25_demo_baseline.csv"

python -m m3_core.run_batch `
  --cases $DemoCases `
  --backend ollama `
  --model $Model `
  --defense guarded `
  --max-steps $MaxSteps `
  --out "outputs/runs/day3_qwen25_demo_guarded.jsonl" `
  --csv-out "outputs/runs/day3_qwen25_demo_guarded.csv"

if ($RunTwentyCases) {
  python -m m3_core.run_batch `
    --cases $AllCases `
    --backend ollama `
    --model $Model `
    --defense baseline `
    --families $Families `
    --limit $Limit `
    --max-steps $MaxSteps `
    --out "outputs/runs/day3_qwen25_baseline_20.jsonl" `
    --csv-out "outputs/runs/day3_qwen25_baseline_20.csv"

  python -m m3_core.run_batch `
    --cases $AllCases `
    --backend ollama `
    --model $Model `
    --defense guarded `
    --families $Families `
    --limit $Limit `
    --max-steps $MaxSteps `
    --out "outputs/runs/day3_qwen25_guarded_20.jsonl" `
    --csv-out "outputs/runs/day3_qwen25_guarded_20.csv"
}

Write-Host "DAY3 Qwen runs complete."
