[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$review = Join-Path $root "receipts\pre_release_review_v2.json"
if (Test-Path -LiteralPath $review) { throw "overwrite refused: $review" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 validate-pre-release `
        --execution-set ".\release\blind_execution_v2.jsonl" `
        --label-file ".\private\labels\blind_labels_v2.jsonl" `
        --write-review $review
    if ($LASTEXITCODE -ne 0) { throw "pre-release validation failed" }
} finally { Pop-Location }
