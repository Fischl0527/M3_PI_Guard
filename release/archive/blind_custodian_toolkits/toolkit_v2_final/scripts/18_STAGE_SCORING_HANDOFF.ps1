[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$destination = Join-Path $root "release\scoring_handoff_v2"
if (Test-Path -LiteralPath $destination) { throw "scoring handoff already exists; overwrite refused" }
$sources = @(
    (Join-Path $root "private\scoring\scoring_results_v2.jsonl"),
    (Join-Path $root "receipts\label_release_seal_v2.json"),
    (Join-Path $root "receipts\custodian_scoring_result_seal_v2.json"),
    (Join-Path $root "receipts\custodian_scoring_attestation_v2.json"),
    (Join-Path $root "receipts\custodian_scoring_attestation_verifier_receipt_v2.json")
)
foreach ($source in $sources) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "required scoring source missing: $source" }
}
$seal = Get-Content -LiteralPath (Join-Path $root "receipts\custodian_scoring_result_seal_v2.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$seal.status -ne "custodian_scoring_completed_results_sealed") {
    throw "scoring result seal is not passing"
}
$attestationReceipt = Get-Content -LiteralPath (Join-Path $root "receipts\custodian_scoring_attestation_verifier_receipt_v2.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$attestationReceipt.status -ne "custodian_scoring_result_signature_verified") {
    throw "scoring attestation signature is not verified"
}
[void](New-Item -ItemType Directory -Path $destination -ErrorAction Stop)
$records = @()
foreach ($source in $sources) {
    $name = Split-Path -Leaf $source
    $target = Join-Path $destination $name
    Copy-Item -LiteralPath $source -Destination $target -ErrorAction Stop
    $records += [ordered]@{
        filename = $name
        sha256 = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        bytes = (Get-Item -LiteralPath $target).Length
    }
}
$manifest = [ordered]@{
    schema_version = "m3-paper-v2-independent-blind-scoring-handoff-2.0"
    status = "scoring_handoff_staged_without_private_labels"
    files = $records
    private_label_file_included = $false
    network_calls_made = 0
}
$manifestPath = Join-Path $destination "scoring_handoff_manifest_v2.json"
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 6 -Compress) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Write-Output ($manifest | ConvertTo-Json -Depth 6)
