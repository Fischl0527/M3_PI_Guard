$ErrorActionPreference = "Stop"

# DAY5 release 包配置区。不会复制模型、.git、sandbox/secrets 或 outbox。
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$ReleaseDir = "release/M3_PI_Guard_v0.5"
$KeepRunDirs = @(
  "outputs/runs/day5_demo_matrix",
  "outputs/runs/day5_qwen25_matrix"
)

Set-Location $RepoRoot

$ResolvedRelease = (Join-Path $RepoRoot $ReleaseDir)
if ((Resolve-Path -Path (Split-Path -Parent $ResolvedRelease) -ErrorAction SilentlyContinue) -eq $null) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ResolvedRelease) | Out-Null
}
if (Test-Path $ResolvedRelease) {
  Remove-Item -LiteralPath $ResolvedRelease -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ResolvedRelease | Out-Null

foreach ($Path in @("m3_core", "m3_attacks", "m3_guard", "m3_eval", "fixtures", "docs", "scripts")) {
  if (Test-Path $Path) {
    Copy-Item -LiteralPath $Path -Destination (Join-Path $ResolvedRelease $Path) -Recurse -Force
  }
}

foreach ($File in @("README.md", "requirements-core.txt", "requirements-dashboard.txt", "DAY5-TARGET-A.md", "Modelfile.qwen25-7b-8k")) {
  if (Test-Path $File) {
    Copy-Item -LiteralPath $File -Destination (Join-Path $ResolvedRelease $File) -Force
  }
}

if (Test-Path "sandbox/public") {
  New-Item -ItemType Directory -Force -Path (Join-Path $ResolvedRelease "sandbox") | Out-Null
  Copy-Item -LiteralPath "sandbox/public" -Destination (Join-Path $ResolvedRelease "sandbox/public") -Recurse -Force
  Remove-Item -LiteralPath (Join-Path $ResolvedRelease "sandbox/public/agent_memory.txt") -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path (Join-Path $ResolvedRelease "outputs") | Out-Null
foreach ($Path in @("outputs/metrics", "outputs/figures")) {
  if (Test-Path $Path) {
    Copy-Item -LiteralPath $Path -Destination (Join-Path $ResolvedRelease $Path) -Recurse -Force
  }
}

foreach ($RunDir in $KeepRunDirs) {
  if (Test-Path $RunDir) {
    $Target = Join-Path $ResolvedRelease $RunDir
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
    Copy-Item -LiteralPath $RunDir -Destination $Target -Recurse -Force
  }
}

Get-ChildItem -LiteralPath $ResolvedRelease -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $ResolvedRelease -Recurse -Filter "*.pyc" | Remove-Item -Force

Write-Host "DAY5 release package ready: $ReleaseDir"
