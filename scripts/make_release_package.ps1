$ErrorActionPreference = "Stop"

# Release package configuration. The package excludes local models, secrets,
# runtime mailboxes, previous release bundles, and day-by-day process notes.
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { "" }
$RepoRoot = if ($ScriptDir) { (Resolve-Path (Join-Path $ScriptDir "..")).Path } else { (Get-Location).Path }
$ReleaseDir = "release/Redteam_LLM_Security_v1.0"
$KeepRunDirs = @(
  "outputs/runs/day6_demo_stub_matrix",
  "outputs/runs/day5_demo_matrix",
  "outputs/runs/day5_qwen25_matrix"
)
$SourceDirs = @("m3_core", "m3_attacks", "m3_guard", "m3_eval", "fixtures", "docs", "scripts")
$RootFiles = @("README.md", "requirements-core.txt", "requirements-dashboard.txt", "Modelfile.qwen25-7b-8k")

Set-Location $RepoRoot

$ResolvedRelease = (Join-Path $RepoRoot $ReleaseDir)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ResolvedRelease) | Out-Null
if (Test-Path $ResolvedRelease) {
  Remove-Item -LiteralPath $ResolvedRelease -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ResolvedRelease | Out-Null

foreach ($Path in $SourceDirs) {
  if (Test-Path $Path) {
    Copy-Item -LiteralPath $Path -Destination (Join-Path $ResolvedRelease $Path) -Recurse -Force
  }
}

foreach ($File in $RootFiles) {
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
  } else {
    New-Item -ItemType Directory -Force -Path (Join-Path $ResolvedRelease $Path) | Out-Null
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
Get-ChildItem -LiteralPath $ResolvedRelease -Recurse -Force -File |
  Where-Object {
    $_.Name -like "DAY*-TASK.md" -or
    $_.Name -like "DAY*-REPORT-A.md" -or
    $_.Name -like "DAY*-TARGET-A.md"
  } |
  Remove-Item -Force

foreach ($UnsafePath in @(
  ".git",
  ".venv",
  "models",
  "ollama_models",
  "private_notes",
  "release/M3_PI_Guard_v0.5",
  "sandbox/secrets",
  "sandbox/outbox",
  "sandbox/logs"
)) {
  $Candidate = Join-Path $ResolvedRelease $UnsafePath
  if (Test-Path $Candidate) {
    Remove-Item -LiteralPath $Candidate -Recurse -Force
  }
}

$QualityDir = Join-Path $RepoRoot "outputs/quality"
New-Item -ItemType Directory -Force -Path $QualityDir | Out-Null
$ChecklistPath = Join-Path $QualityDir "day6_release_checklist.md"
$ReportPath = Join-Path $ResolvedRelease "docs/report/作品报告_终稿.docx"
$Checklist = @(
  "# DAY6 Release Checklist",
  "",
  "- release_dir: $ReleaseDir",
  "- generated_at: $(Get-Date -Format s)",
  "- includes_core_modules: $(Test-Path (Join-Path $ResolvedRelease 'm3_core'))",
  "- includes_attack_cases: $(Test-Path (Join-Path $ResolvedRelease 'm3_attacks/cases/all_cases.jsonl'))",
  "- includes_guard: $(Test-Path (Join-Path $ResolvedRelease 'm3_guard'))",
  "- includes_eval: $(Test-Path (Join-Path $ResolvedRelease 'm3_eval'))",
  "- includes_demo_stub_logs: $(Test-Path (Join-Path $ResolvedRelease 'outputs/runs/day6_demo_stub_matrix'))",
  "- includes_final_report_docx: $(Test-Path $ReportPath)",
  "- excludes_model_dirs: $(-not (Test-Path (Join-Path $ResolvedRelease 'models')))",
  "- excludes_sandbox_secrets: $(-not (Test-Path (Join-Path $ResolvedRelease 'sandbox/secrets')))",
  "- excludes_sandbox_outbox: $(-not (Test-Path (Join-Path $ResolvedRelease 'sandbox/outbox')))",
  "- excludes_previous_release: $(-not (Test-Path (Join-Path $ResolvedRelease 'release/M3_PI_Guard_v0.5')))",
  "",
  "Note: if includes_final_report_docx is False, the formal report has not yet been merged into docs/report/."
)
$Checklist | Set-Content -Path $ChecklistPath -Encoding UTF8

Write-Host "Release package ready: $ReleaseDir"
Write-Host "Checklist written: outputs/quality/day6_release_checklist.md"
