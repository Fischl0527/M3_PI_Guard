[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$destination = Join-Path $root "release\developer_handoff_v2"
if (Test-Path -LiteralPath $destination) { throw "handoff directory already exists; overwrite refused" }
$sources = @(
    (Join-Path $root "release\blind_execution_v2.jsonl"),
    (Join-Path $root "release\blind_custody_v2.json"),
    (Join-Path $root "release\custodian_registration_v2.json"),
    (Join-Path $root "release\custodian_public_key.pem"),
    (Join-Path $root "receipts\pre_release_review_v2.json"),
    (Join-Path $root "receipts\custodian_registration_verifier_receipt_v2.json"),
    (Join-Path $root "receipts\custody_signature_verifier_receipt_v2.json"),
    (Join-Path $root "toolkit_manifest_v2.json")
)
foreach ($source in $sources) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "required handoff source missing: $source" }
    if ((Split-Path -Leaf $source) -match '(?i)(label.*jsonl|authored_pairs|private.*key)') {
        throw "private artifact matched handoff denylist: $source"
    }
}
$statusChecks = @{
    (Join-Path $root "receipts\pre_release_review_v2.json") = "custodian_pre_release_passed"
    (Join-Path $root "receipts\custodian_registration_verifier_receipt_v2.json") = "custodian_registration_verified_clock_may_start"
    (Join-Path $root "receipts\custody_signature_verifier_receipt_v2.json") = "custody_signature_cryptographically_verified"
    (Join-Path $root "release\blind_custody_v2.json") = "execution_released_labels_sealed"
}
foreach ($path in $statusChecks.Keys) {
    $value = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$value.status -ne [string]$statusChecks[$path]) { throw "handoff source has non-passing status: $path" }
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
    schema_version = "m3-paper-v2-independent-blind-developer-handoff-2.0"
    status = "developer_handoff_staged_label_free"
    files = $records
    label_file_included = $false
    private_key_included = $false
    network_calls_made = 0
}
$manifestPath = Join-Path $destination "developer_handoff_manifest_v2.json"
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 6 -Compress) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Write-Output ($manifest | ConvertTo-Json -Depth 6)
