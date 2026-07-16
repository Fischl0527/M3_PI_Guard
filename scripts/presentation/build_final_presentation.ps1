param(
    [ValidateSet('Preview', 'Final')]
    [string]$Mode = 'Preview',
    [string]$Output = '',
    [string]$AnalysisDir = '',
    [string]$Registry = '',
    [string]$Workspace = ''
)

$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$SkillDir = 'C:\Users\gaohang\.codex\plugins\cache\openai-primary-runtime\presentations\26.709.11516\skills\presentations'
$MapSource = Join-Path $PSScriptRoot 'final-deck-frame-map.source.json'
$Map = Get-Content -LiteralPath $MapSource -Raw | ConvertFrom-Json
$Template = Get-ChildItem -LiteralPath (Join-Path $Repo 'docs\presentation') -Filter 'Redteam_LLM_Security_*.pptx' -File |
    Where-Object { (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant() -eq $Map.sourceDeckSha256 } |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $Template) {
    throw "Could not find the exact source-deck SHA-256 under docs/presentation."
}
$ThreadId = if ($env:CODEX_THREAD_ID) { $env:CODEX_THREAD_ID } else { 'manual-m3-final-presentation' }
if (-not $Workspace) {
    $Workspace = Join-Path ([System.IO.Path]::GetTempPath()) "codex-presentations\$ThreadId\m3-pi-guard-final-deck"
}
$TmpDir = Join-Path ([System.IO.Path]::GetFullPath($Workspace)) 'tmp'
$PreviewDir = Join-Path $TmpDir 'preview\final'
$LayoutDir = Join-Path $TmpDir 'layout\final'
$QaDir = Join-Path $TmpDir 'qa'
$AssetDir = Join-Path $TmpDir 'assets'
$OutputDir = Join-Path $TmpDir 'output'
$MapPath = Join-Path $TmpDir 'template-frame-map.json'
$Starter = Join-Path $TmpDir 'template-starter.pptx'
$Montage = Join-Path $PreviewDir 'final-montage.webp'
$ContactSheet = Join-Path $QaDir 'final-contact-sheet.png'
$FinalRenderDir = Join-Path $QaDir ("final-render-{0}" -f ([Guid]::NewGuid().ToString('N')))
$BuildManifest = Join-Path $QaDir 'deck-build-manifest.json'

$env:HOME = $env:USERPROFILE
$BundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$QaPython = if (Test-Path $BundledPython) { $BundledPython } else { (Get-Command python -ErrorAction Stop).Source }
$env:PYTHON = $QaPython
$GitUnzip = 'C:\Program Files\Git\usr\bin'
if (Test-Path (Join-Path $GitUnzip 'unzip.exe')) {
    $env:PATH = "$GitUnzip;$env:PATH"
}

New-Item -ItemType Directory -Force -Path $TmpDir, $PreviewDir, $LayoutDir, $QaDir, $AssetDir, $OutputDir, $FinalRenderDir | Out-Null

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][object[]]$Arguments
    )
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "External command failed ($LASTEXITCODE): $Command $($Arguments -join ' ')"
    }
}

function Get-OrderedSlidePngs {
    param(
        [Parameter(Mandatory = $true)][string]$Directory,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $Slides = @(
        Get-ChildItem -LiteralPath $Directory -Filter 'slide-*.png' -File | ForEach-Object {
            if ($_.BaseName -notmatch '^slide-(\d+)$') {
                throw "$Label contains an unexpected slide PNG name: $($_.Name)"
            }
            [pscustomobject]@{
                number = [int]$Matches[1]
                path = $_.FullName
            }
        }
    )
    if ($Slides.Count -ne 12) {
        throw "$Label must contain exactly 12 slide PNGs; found $($Slides.Count) in $Directory."
    }
    $Ordered = @($Slides | Sort-Object number)
    $ActualNumbers = @($Ordered | Select-Object -ExpandProperty number)
    $ExpectedNumbers = @(1..12)
    if (($ActualNumbers -join ',') -ne ($ExpectedNumbers -join ',')) {
        throw "$Label must contain slide numbers 1 through 12 exactly once; found $($ActualNumbers -join ',')."
    }
    return @($Ordered | Select-Object -ExpandProperty path)
}

$TemplateHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Template).Hash.ToLowerInvariant()
if ($TemplateHash -ne $Map.sourceDeckSha256) {
    throw "Source deck SHA-256 drift: expected $($Map.sourceDeckSha256), got $TemplateHash"
}

Copy-Item -LiteralPath $MapSource -Destination $MapPath -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'template-audit.source.txt') -Destination (Join-Path $TmpDir 'template-audit.txt') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'deviation-log.source.txt') -Destination (Join-Path $TmpDir 'deviation-log.txt') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'source-notes.source.txt') -Destination (Join-Path $TmpDir 'source-notes.txt') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'build_final_deck.mjs') -Destination (Join-Path $TmpDir 'build-final-deck.mjs') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'expand_template_inspect.mjs') -Destination (Join-Path $TmpDir 'expand-template-inspect.mjs') -Force

Invoke-Checked node @((Join-Path $SkillDir 'container_tools\setup_artifact_tool_workspace.mjs'), '--workspace', $TmpDir)
Invoke-Checked node @((Join-Path $SkillDir 'template_following_scripts\inspect_template_deck.mjs'), '--workspace', $TmpDir, '--pptx', $Template)
Invoke-Checked node @((Join-Path $TmpDir 'expand-template-inspect.mjs'), $Template, (Join-Path $TmpDir 'template-inspect\template-inspect.ndjson'))
Invoke-Checked node @((Join-Path $SkillDir 'template_following_scripts\validate_template_plan.mjs'), '--workspace', $TmpDir, '--map', $MapPath, '--source-slide-count', '12')
Invoke-Checked node @(
    (Join-Path $SkillDir 'template_following_scripts\prepare_template_starter_deck.mjs'),
    '--workspace', $TmpDir,
    '--pptx', $Template,
    '--map', $MapPath,
    '--out', $Starter,
    '--preview-dir', (Join-Path $TmpDir 'template-starter-preview'),
    '--layout-dir', (Join-Path $TmpDir 'template-starter-layout'),
    '--contact-sheet', (Join-Path $TmpDir 'template-starter-contact-sheet.png')
)

if ($Mode -eq 'Preview') {
    $FixtureDir = Join-Path $AssetDir 'fixture'
    $FixtureAssets = Join-Path $AssetDir 'fixture-charts'
    New-Item -ItemType Directory -Force -Path $FixtureDir, $FixtureAssets | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'generate_synthetic_fixture_assets.mjs') -Destination (Join-Path $FixtureDir 'generate-synthetic-fixture-assets.mjs') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'synthetic-fixture.json') -Destination (Join-Path $FixtureDir 'synthetic-fixture.json') -Force
    Invoke-Checked node @((Join-Path $FixtureDir 'generate-synthetic-fixture-assets.mjs'), '--out-dir', $FixtureAssets)
    if (-not $Output) { $Output = Join-Path $OutputDir 'M3_PI_Guard_synthetic_preview.pptx' }
    Invoke-Checked node @(
        (Join-Path $TmpDir 'build-final-deck.mjs'),
        '--mode', 'fixture',
        '--starter', $Starter,
        '--template', $Template,
        '--fixture', (Join-Path $FixtureDir 'synthetic-fixture.json'),
        '--fixture-assets', $FixtureAssets,
        '--out', $Output,
        '--preview-dir', $PreviewDir,
        '--layout-dir', $LayoutDir,
        '--montage', $Montage,
        '--build-manifest', $BuildManifest
    )
} else {
    if (-not $AnalysisDir) { $AnalysisDir = Join-Path $Repo 'outputs\experiments\final_analysis' }
    if (-not $Registry) { $Registry = Join-Path $Repo 'experiments\registry.json' }
    if (-not $Output) { $Output = Join-Path $Repo 'docs\presentation\Redteam_LLM_Security_final_experiments.pptx' }
    Invoke-Checked node @(
        (Join-Path $TmpDir 'build-final-deck.mjs'),
        '--mode', 'formal',
        '--starter', $Starter,
        '--template', $Template,
        '--analysis', $AnalysisDir,
        '--registry', $Registry,
        '--out', $Output,
        '--preview-dir', $PreviewDir,
        '--layout-dir', $LayoutDir,
        '--montage', $Montage,
        '--build-manifest', $BuildManifest
    )
}

Invoke-Checked node @(
    (Join-Path $SkillDir 'template_following_scripts\check_template_fidelity.mjs'),
    '--workspace', $TmpDir,
    '--starter-pptx', $Starter,
    '--final-pptx', $Output,
    '--map', $MapPath,
    '--starter-layout-dir', (Join-Path $TmpDir 'template-starter-layout'),
    '--final-layout-dir', $LayoutDir,
    '--edit-dir', $TmpDir
)

$PreviewSlidePngs = @(Get-OrderedSlidePngs -Directory $PreviewDir -Label 'Artifact-tool pre-export preview')

$RenderInput = Join-Path $QaDir 'render-input.pptx'
Copy-Item -LiteralPath $Output -Destination $RenderInput -Force
Invoke-Checked $QaPython @(
    (Join-Path $SkillDir 'container_tools\render_slides.py'),
    $RenderInput,
    '--output_dir', $FinalRenderDir
)
Invoke-Checked $QaPython @((Join-Path $SkillDir 'container_tools\slides_test.py'), $Output)
$FinalSlidePngs = @(Get-OrderedSlidePngs -Directory $FinalRenderDir -Label 'Final exported-PPT reread render')
$ContactSheetArgs = @(
    (Join-Path $SkillDir 'container_tools\create_montage.py'),
    '--input_files'
) + $FinalSlidePngs + @(
    '--output_file', $ContactSheet,
    '--num_col', '3',
    '--label_mode', 'filename',
    '--fail_on_image_error'
)
Invoke-Checked $QaPython $ContactSheetArgs

[pscustomobject]@{
    status = 'completed'
    mode = $Mode
    output = [System.IO.Path]::GetFullPath($Output)
    workspace = $Workspace
    preview_dir = $PreviewDir
    preview_slide_count = $PreviewSlidePngs.Count
    final_render_dir = $FinalRenderDir
    final_render_slide_count = $FinalSlidePngs.Count
    montage = $Montage
    contact_sheet = $ContactSheet
    build_manifest = $BuildManifest
} | ConvertTo-Json -Depth 4
