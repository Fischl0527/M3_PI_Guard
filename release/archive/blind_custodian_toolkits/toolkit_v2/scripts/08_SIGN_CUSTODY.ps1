[CmdletBinding()]
param(
    [string]$OpenSSLExe = "openssl",
    [Parameter(Mandatory=$true)][string]$PrivateKeyPath
)
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
& (Join-Path $PSScriptRoot "SIGN_EXTERNAL_ED25519_DIGEST.ps1") `
    -OpenSSLExe $OpenSSLExe -PrivateKeyPath $PrivateKeyPath `
    -UnsignedJsonPath (Join-Path $root "signatures\unsigned_custody_v2.json") `
    -DigestField "custodian_signature_payload_sha256" `
    -SignatureOutputPath (Join-Path $root "signatures\custody_signature_base64.txt")
if ($LASTEXITCODE -ne 0) { throw "custody signature failed" }
