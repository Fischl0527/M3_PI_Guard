[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$CustodianId,
    [Parameter(Mandatory=$true)][string]$ProjectRelationship,
    [Parameter(Mandatory=$true)][string]$ConfirmedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$identity = Join-Path $root "private\registration\offline_identity_attestation.txt"
$publicKey = Join-Path $root "release\custodian_public_key.pem"
$unsigned = Join-Path $root "signatures\unsigned_registration_v2.json"
if (Test-Path -LiteralPath $unsigned) { throw "overwrite refused: $unsigned" }
foreach ($source in @($identity, $publicKey)) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "required file missing: $source" }
}
$identityHash = (Get-FileHash -LiteralPath $identity -Algorithm SHA256).Hash.ToLowerInvariant()
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 build-unsigned-registration `
        --custodian-id $CustodianId --project-relationship $ProjectRelationship `
        --custodian-public-key $publicKey --confirmed-at $ConfirmedAt `
        --offline-identity-evidence-sha256 $identityHash --write-unsigned $unsigned
    if ($LASTEXITCODE -ne 0) { throw "unsigned registration build failed" }
} finally { Pop-Location }
