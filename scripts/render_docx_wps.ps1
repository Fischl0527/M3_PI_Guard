[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputDocx,

    [string]$OutputDir = "",

    [ValidateRange(72, 600)]
    [int]$Dpi = 144,

    [string]$WpsProgId = "KWPS.Application",

    [string]$PdftoppmExecutable = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = if ($PSScriptRoot) {
    $PSScriptRoot
} elseif ($MyInvocation.MyCommand.Path) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    throw "Unable to resolve the scripts directory."
}
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))

function Get-Sha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-WpsProcessIds {
    return @(
        Get-Process -Name "wps" -ErrorAction SilentlyContinue |
            ForEach-Object { [int]$_.Id }
    )
}

function Get-NewProcessIds {
    param(
        [int[]]$Before,
        [int[]]$After
    )

    return @(
        $After | Where-Object { $Before -notcontains $_ } | Sort-Object -Unique
    )
}

function Release-ComObject {
    param(
        [AllowNull()]
        [object]$ComObject
    )

    if ($null -ne $ComObject -and [System.Runtime.InteropServices.Marshal]::IsComObject($ComObject)) {
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($ComObject)
    }
}

function Assert-SourceUnchanged {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedSha256,
        [Parameter(Mandatory = $true)]
        [long]$ExpectedLength,
        [Parameter(Mandatory = $true)]
        [long]$ExpectedMtimeUtcTicks
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Source DOCX disappeared during render QA: $Path"
    }
    $item = Get-Item -LiteralPath $Path
    $actualSha256 = Get-Sha256 -Path $Path
    if ($actualSha256 -ne $ExpectedSha256 -or
        [long]$item.Length -ne $ExpectedLength -or
        [long]$item.LastWriteTimeUtc.Ticks -ne $ExpectedMtimeUtcTicks) {
        throw (
            "Source DOCX changed during render QA. " +
            "expected_sha=$ExpectedSha256 actual_sha=$actualSha256 " +
            "expected_bytes=$ExpectedLength actual_bytes=$($item.Length) " +
            "expected_mtime_ticks=$ExpectedMtimeUtcTicks actual_mtime_ticks=$($item.LastWriteTimeUtc.Ticks)"
        )
    }
}

$SourcePath = [System.IO.Path]::GetFullPath($InputDocx)
if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
    throw "Input DOCX is missing: $SourcePath"
}
if ([System.IO.Path]::GetExtension($SourcePath) -ine ".docx") {
    throw "Input must be a .docx file: $SourcePath"
}

$SourceItem = Get-Item -LiteralPath $SourcePath
$SourceSha256 = Get-Sha256 -Path $SourcePath
$SourceLength = [long]$SourceItem.Length
$SourceMtimeUtcTicks = [long]$SourceItem.LastWriteTimeUtc.Ticks
$SourceMtimeUtc = $SourceItem.LastWriteTimeUtc.ToString("o")

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $safeStem = [System.IO.Path]::GetFileNameWithoutExtension($SourcePath) -replace '[^A-Za-z0-9._-]', '_'
    $OutputDir = Join-Path $RepoRoot ".agent\tmp\docx-render\$safeStem-$timestamp"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputDir)
if (Test-Path -LiteralPath $OutputPath) {
    throw "Output directory already exists; refusing to overwrite QA evidence: $OutputPath"
}

if ([string]::IsNullOrWhiteSpace($PdftoppmExecutable)) {
    $PdftoppmExecutable = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
}
$PdftoppmPath = [System.IO.Path]::GetFullPath($PdftoppmExecutable)
if (-not (Test-Path -LiteralPath $PdftoppmPath -PathType Leaf)) {
    throw "Bundled pdftoppm.exe is missing: $PdftoppmPath"
}
$PdfInfoPath = Join-Path (Split-Path -Parent $PdftoppmPath) "pdfinfo.exe"
if (-not (Test-Path -LiteralPath $PdfInfoPath -PathType Leaf)) {
    throw "Bundled pdfinfo.exe is missing beside pdftoppm.exe: $PdfInfoPath"
}

$OutputParent = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $OutputParent -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $OutputParent | Out-Null
}
$StageName = ".{0}.stage-{1}" -f (Split-Path -Leaf $OutputPath), ([guid]::NewGuid().ToString("N"))
$StagePath = Join-Path $OutputParent $StageName
New-Item -ItemType Directory -Path $StagePath | Out-Null
$WorkingCopy = Join-Path $StagePath "source-copy.docx"
$PdfPath = Join-Path $StagePath "document.pdf"
$PagesDir = Join-Path $StagePath "pages"
New-Item -ItemType Directory -Path $PagesDir | Out-Null

$WpsPidsBefore = @(Get-WpsProcessIds)
$WpsApplication = $null
$WpsDocument = $null
$OwnsEmptyComInstance = $false
$PrimaryError = $null
$PdfPageCount = 0
$PageRecords = @()

try {
    Copy-Item -LiteralPath $SourcePath -Destination $WorkingCopy
    if ((Get-Sha256 -Path $WorkingCopy) -ne $SourceSha256) {
        throw "Temporary DOCX copy hash differs from the source."
    }

    $WpsApplication = New-Object -ComObject $WpsProgId
    $OpenDocumentCount = [int]$WpsApplication.Documents.Count
    if ($OpenDocumentCount -ne 0) {
        throw "KWPS.Application is not an exclusive empty instance: Documents.Count=$OpenDocumentCount"
    }
    $OwnsEmptyComInstance = $true
    try {
        $WpsApplication.Visible = $false
    } catch {
        throw "Unable to hide KWPS.Application: $($_.Exception.Message)"
    }
    try {
        $WpsApplication.DisplayAlerts = 0
    } catch {
        throw "Unable to disable WPS alerts: $($_.Exception.Message)"
    }

    # ConfirmConversions=false, ReadOnly=true.  The source itself is never
    # passed to WPS; only this hash-identical temporary copy is opened.
    $WpsDocument = $WpsApplication.Documents.Open($WorkingCopy, $false, $true)
    if (-not [bool]$WpsDocument.ReadOnly) {
        throw "WPS did not open the temporary DOCX copy as read-only."
    }
    $WpsDocument.ExportAsFixedFormat($PdfPath, 17)
    if (-not (Test-Path -LiteralPath $PdfPath -PathType Leaf) -or
        (Get-Item -LiteralPath $PdfPath).Length -le 0) {
        throw "WPS did not create a non-empty PDF."
    }

    # Close before rasterization so no WPS write handle remains on the copy.
    $WpsDocument.Close(0)
    Release-ComObject -ComObject $WpsDocument
    $WpsDocument = $null

    $PagePrefix = Join-Path $PagesDir "page"
    & $PdftoppmPath -png -r $Dpi -- $PdfPath $PagePrefix
    if ($LASTEXITCODE -ne 0) {
        throw "pdftoppm.exe exited with code $LASTEXITCODE."
    }

    $PdfInfoOutput = @(& $PdfInfoPath $PdfPath 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "pdfinfo.exe exited with code $LASTEXITCODE."
    }
    $PageLine = $PdfInfoOutput | Where-Object { $_ -match '^Pages:\s+(\d+)\s*$' } | Select-Object -First 1
    if ($null -eq $PageLine -or [string]$PageLine -notmatch '^Pages:\s+(\d+)\s*$') {
        throw "pdfinfo.exe did not report a page count."
    }
    $PdfPageCount = [int]$Matches[1]
    $PageFiles = @(
        Get-ChildItem -LiteralPath $PagesDir -Filter "page-*.png" -File |
            Sort-Object Name
    )
    if ($PdfPageCount -le 0 -or $PageFiles.Count -le 0) {
        throw "Rendered page count must be positive: pdf=$PdfPageCount png=$($PageFiles.Count)"
    }
    if ($PageFiles.Count -ne $PdfPageCount) {
        throw "PDF/PNG page-count mismatch: pdf=$PdfPageCount png=$($PageFiles.Count)"
    }

    $PageRecords = @(
        for ($index = 0; $index -lt $PageFiles.Count; $index++) {
            $page = $PageFiles[$index]
            [ordered]@{
                page_number = $index + 1
                path = "pages/$($page.Name)"
                bytes = [long]$page.Length
                sha256 = Get-Sha256 -Path $page.FullName
            }
        }
    )
} catch {
    $PrimaryError = $_
} finally {
    if ($null -ne $WpsDocument) {
        try {
            $WpsDocument.Close(0)
        } catch {
            if ($null -eq $PrimaryError) {
                $PrimaryError = $_
            }
        }
        Release-ComObject -ComObject $WpsDocument
        $WpsDocument = $null
    }
    if ($null -ne $WpsApplication) {
        if ($OwnsEmptyComInstance) {
            try {
                $WpsApplication.Quit()
            } catch {
                if ($null -eq $PrimaryError) {
                    $PrimaryError = $_
                }
            }
        }
        Release-ComObject -ComObject $WpsApplication
        $WpsApplication = $null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$ResidualWpsPids = @()
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $ResidualWpsPids = @(Get-NewProcessIds -Before $WpsPidsBefore -After @(Get-WpsProcessIds))
    if ($ResidualWpsPids.Count -eq 0) {
        break
    }
    Start-Sleep -Milliseconds 250
}

$PostCheckErrors = @()
try {
    Assert-SourceUnchanged `
        -Path $SourcePath `
        -ExpectedSha256 $SourceSha256 `
        -ExpectedLength $SourceLength `
        -ExpectedMtimeUtcTicks $SourceMtimeUtcTicks
} catch {
    $PostCheckErrors += $_.Exception.Message
}
if ($ResidualWpsPids.Count -gt 0) {
    $PostCheckErrors += "WPS process residue detected after COM release: $($ResidualWpsPids -join ',')"
}
if ($PdfPageCount -le 0 -and $null -eq $PrimaryError) {
    $PostCheckErrors += "Rendered page count is zero."
}

if ($null -ne $PrimaryError -or $PostCheckErrors.Count -gt 0) {
    $messages = @()
    if ($null -ne $PrimaryError) {
        $messages += $PrimaryError.Exception.Message
    }
    $messages += $PostCheckErrors
    Remove-Item -LiteralPath $StagePath -Recurse -Force -ErrorAction SilentlyContinue
    throw ("DOCX render QA failed: " + ($messages -join " | "))
}

$Manifest = [ordered]@{
    schema_version = "1.0"
    status = "completed"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    source = [ordered]@{
        path = $SourcePath
        bytes = $SourceLength
        sha256 = $SourceSha256
        mtime_utc = $SourceMtimeUtc
        mtime_utc_ticks = $SourceMtimeUtcTicks
        opened_directly = $false
    }
    renderer = [ordered]@{
        wps_prog_id = $WpsProgId
        wps_process_ids_before = $WpsPidsBefore
        wps_process_ids_residual = $ResidualWpsPids
        pdftoppm_executable = $PdftoppmPath
        pdfinfo_executable = $PdfInfoPath
        dpi = $Dpi
    }
    pdf = [ordered]@{
        path = "document.pdf"
        bytes = [long](Get-Item -LiteralPath $PdfPath).Length
        sha256 = Get-Sha256 -Path $PdfPath
        page_count = $PdfPageCount
    }
    pages = $PageRecords
    visual_review = [ordered]@{
        status = "pending_manual_inspection"
        requirement = "Inspect every page PNG at 100% before accepting the DOCX."
    }
}
$ManifestPath = Join-Path $StagePath "render_manifest.json"
$Manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

try {
    Move-Item -LiteralPath $StagePath -Destination $OutputPath
} catch {
    Remove-Item -LiteralPath $StagePath -Recurse -Force -ErrorAction SilentlyContinue
    throw
}

$PublishedManifest = Join-Path $OutputPath "render_manifest.json"
Write-Host "DOCX render QA artifacts created." -ForegroundColor Green
Write-Host "Source SHA-256: $SourceSha256"
Write-Host "PDF pages: $PdfPageCount"
Write-Host "Output: $OutputPath"
Get-Content -LiteralPath $PublishedManifest -Raw -Encoding UTF8 | ConvertFrom-Json
