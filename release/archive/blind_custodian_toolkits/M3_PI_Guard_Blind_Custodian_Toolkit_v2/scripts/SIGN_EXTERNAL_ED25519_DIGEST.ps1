[CmdletBinding()]
param(
    [string]$OpenSSLExe = "openssl",
    [Parameter(Mandatory=$true)][string]$PrivateKeyPath,
    [Parameter(Mandatory=$true)][string]$UnsignedJsonPath,
    [Parameter(Mandatory=$true)]
    [ValidateSet("registration_signature_payload_sha256", "custodian_signature_payload_sha256", "signature_payload_sha256")]
    [string]$DigestField,
    [Parameter(Mandatory=$true)][string]$SignatureOutputPath
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$privateKey = (Resolve-Path -LiteralPath $PrivateKeyPath).Path
$relativePrivate = [IO.Path]::GetRelativePath($root, $privateKey)
if (-not $relativePrivate.StartsWith("..") -and -not [IO.Path]::IsPathRooted($relativePrivate)) {
    throw "private key must stay outside the toolkit root"
}
$unsigned = (Resolve-Path -LiteralPath $UnsignedJsonPath).Path
$signatureRoot = (Resolve-Path -LiteralPath (Join-Path $root "signatures")).Path
$relativeUnsigned = [IO.Path]::GetRelativePath($signatureRoot, $unsigned)
if ($relativeUnsigned.StartsWith("..") -or [IO.Path]::IsPathRooted($relativeUnsigned)) {
    throw "unsigned JSON must stay inside the toolkit signatures directory"
}
$signatureOutput = [IO.Path]::GetFullPath($SignatureOutputPath)
$relativeOutput = [IO.Path]::GetRelativePath($signatureRoot, $signatureOutput)
if ($relativeOutput.StartsWith("..") -or [IO.Path]::IsPathRooted($relativeOutput)) {
    throw "signature output must stay inside the toolkit signatures directory"
}
if (Test-Path -LiteralPath $signatureOutput) { throw "overwrite refused: $signatureOutput" }
$document = Get-Content -LiteralPath $unsigned -Raw -Encoding UTF8 | ConvertFrom-Json
$digest = [string]$document.$DigestField
if ($digest -notmatch '^[0-9a-f]{64}$') { throw "unsigned payload digest is not lowercase SHA-256" }
$digestTemp = [IO.Path]::GetTempFileName()
$signatureTemp = [IO.Path]::GetTempFileName()
try {
    [IO.File]::WriteAllBytes($digestTemp, [Convert]::FromHexString($digest))
    & $OpenSSLExe pkeyutl -sign -rawin -inkey $privateKey -in $digestTemp -out $signatureTemp
    if ($LASTEXITCODE -ne 0) { throw "OpenSSL Ed25519 signing failed" }
    $signatureBytes = [IO.File]::ReadAllBytes($signatureTemp)
    if ($signatureBytes.Length -ne 64) { throw "Ed25519 signature must be exactly 64 bytes" }
    $signatureBase64 = [Convert]::ToBase64String($signatureBytes)
    [IO.File]::WriteAllText($signatureOutput, $signatureBase64 + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    Write-Output '{"status":"external_ed25519_signature_written","private_key_copied":false,"private_key_path_recorded":false,"network_calls_made":0}'
} finally {
    Remove-Item -LiteralPath $digestTemp -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $signatureTemp -Force -ErrorAction SilentlyContinue
}
