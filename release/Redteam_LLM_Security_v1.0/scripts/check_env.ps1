$ErrorActionPreference = "Continue"

# DAY5 环境检查配置区。只读检查，不修改仓库文件。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }

Set-Location $RepoRoot

Write-Host "==== M3_PI_Guard Environment Check ===="
Write-Host ""

Write-Host "Checking Python..."
python --version

Write-Host ""
Write-Host "Checking Python packages..."
pip show openai
pip show pandas
pip show streamlit

Write-Host ""
Write-Host "Checking Ollama..."
ollama list

Write-Host ""
Write-Host "Checking project directories..."
foreach ($Path in @("m3_core", "m3_attacks", "m3_guard", "m3_eval", "fixtures", "scripts", "sandbox", "outputs")) {
  Write-Host ("{0}: {1}" -f $Path, (Test-Path $Path))
}

Write-Host ""
Write-Host "Checking sandbox directories..."
foreach ($Path in @("sandbox/secrets", "sandbox/outbox", "sandbox/logs")) {
  Write-Host ("{0}: {1}" -f $Path, (Test-Path $Path))
}

Write-Host ""
Write-Host "Checking local canary file..."
if (Test-Path "sandbox/secrets/api_key.txt") {
  Write-Host "sandbox/secrets/api_key.txt: True"
} else {
  Write-Host "sandbox/secrets/api_key.txt: False"
}

Write-Host ""
Write-Host "Done."
