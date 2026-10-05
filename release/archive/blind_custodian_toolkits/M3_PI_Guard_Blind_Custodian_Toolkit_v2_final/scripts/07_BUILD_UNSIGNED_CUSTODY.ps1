[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$AuthoringCompletedAt,
    [Parameter(Mandatory=$true)][string]$SplitCompletedAt,
    [Parameter(Mandatory=$true)][string]$SealedAt,
    [Parameter(Mandatory=$true)][string]$ExecutionReleasedAt,
    [Parameter(Mandatory=$true)][string]$DeveloperReceivedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$registrationPath = Join-Path $root "release\custodian_registration_v2.json"
$registration = Get-Content -LiteralPath $registrationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$unsigned = Join-Path $root "signatures\unsigned_custody_v2.json"
if (Test-Path -LiteralPath $unsigned) { throw "overwrite refused: $unsigned" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 build-unsigned-custody `
        --execution-set ".\release\blind_execution_v2.jsonl" `
        --label-file ".\private\labels\blind_labels_v2.jsonl" `
        --pre-release-receipt ".\receipts\pre_release_review_v2.json" `
        --registration $registrationPath `
        --registration-verifier-receipt ".\receipts\custodian_registration_verifier_receipt_v2.json" `
        --custodian-public-key ".\release\custodian_public_key.pem" `
        --custodian-id ([string]$registration.custodian_id) `
        --custodian-signature-key-id ([string]$registration.signature_key_id) `
        --authoring-completed-at $AuthoringCompletedAt `
        --split-completed-at $SplitCompletedAt --sealed-at $SealedAt `
        --execution-set-released-at $ExecutionReleasedAt `
        --developer-received-execution-set-at $DeveloperReceivedAt `
        --write-unsigned $unsigned
    if ($LASTEXITCODE -ne 0) { throw "unsigned custody build failed" }
} finally { Pop-Location }
