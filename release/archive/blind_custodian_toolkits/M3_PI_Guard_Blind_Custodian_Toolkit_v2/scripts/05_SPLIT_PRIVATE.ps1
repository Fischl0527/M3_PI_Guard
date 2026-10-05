[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$authored = Join-Path $root "private\authored_pairs\authored_pairs.jsonl"
$execution = Join-Path $root "release\blind_execution_v2.jsonl"
$labels = Join-Path $root "private\labels\blind_labels_v2.jsonl"
$receipt = Join-Path $root "receipts\split_receipt_v2.json"
foreach ($target in @($execution, $labels, $receipt)) {
    if (Test-Path -LiteralPath $target) { throw "overwrite refused: $target" }
}
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 split `
        --authored-pairs $authored --execution-output $execution `
        --label-output $labels --write-receipt $receipt
    if ($LASTEXITCODE -ne 0) { throw "private split failed" }
} finally { Pop-Location }
