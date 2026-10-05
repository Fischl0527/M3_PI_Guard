[CmdletBinding()]
param(
    [string]$OpenSSLExe = "openssl",
    [Parameter(Mandatory=$true)][string]$PrivateKeyPath
)
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
& (Join-Path $PSScriptRoot "SIGN_EXTERNAL_ED25519_DIGEST.ps1") `
    -OpenSSLExe $OpenSSLExe -PrivateKeyPath $PrivateKeyPath `
    -UnsignedJsonPath (Join-Path $root "signatures\unsigned_scoring_attestation_v2.json") `
    -DigestField "signature_payload_sha256" `
    -SignatureOutputPath (Join-Path $root "signatures\scoring_attestation_signature_base64.txt")
if ($LASTEXITCODE -ne 0) { throw "scoring attestation signature failed" }
