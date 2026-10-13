"""为独立盲测托管人构建单次使用、标签置空的工具套件。

提供无真值先验污染的交互式评测工具集，保障盲审过程严密可靠。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLKIT_SCHEMA_VERSION = "m3-paper-v2-independent-blind-custodian-toolkit-2.0"
TOOLKIT_MANIFEST_NAME = "toolkit_manifest_v2.json"
FROZEN_SLOTS_SHA256 = (
    "4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8"
)
AUTHORING_README_PATH = (
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/README.md"
)

# This is the complete project-file read boundary.  Do not replace it with
# directory walking: a custodian handoff must never inherit local state.
SOURCE_COPY_MAP: Mapping[str, str] = {
    "experiments/paper_v2/independent_blind_closeout_v2.py": (
        "experiments/paper_v2/independent_blind_closeout_v2.py"
    ),
    "protocols/paper_upgrade_v2/independent_blind_closeout_interface_v2.json": (
        "protocols/paper_upgrade_v2/independent_blind_closeout_interface_v2.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl": (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/README.md": (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/README.md"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/authored_pair_template.json": (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
        "authored_pair_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/case_template.json": (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
        "case_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "custody_manifest_template.json": (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
        "custody_manifest_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/label_template.json": (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
        "label_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/slot_reference.json": (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
        "slot_reference.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/status.json": (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/status.json"
    ),
}

EMPTY_WORK_DIRS = (
    "private/authored_pairs",
    "private/labels",
    "private/registration",
    "private/scoring",
    "incoming_from_developer",
    "receipts",
    "release",
    "signatures",
)

_PACKAGE_MARKER = '"""Standalone custodian-toolkit package marker."""\n'
_STANDALONE_CONTRACTS = '''\
"""Minimal canonical-JSON contract used by the offline custodian toolkit."""
from __future__ import annotations

import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Match the paper-v2 canonical JSON representation without dependencies."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
'''

_VERIFY_SCRIPT = r'''#!/usr/bin/env python3
"""Verify the immutable custodian toolkit files without reading private data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_NAME = "toolkit_manifest_v2.json"
WRITABLE_ROOTS = (
    "incoming_from_developer",
    "private",
    "receipts",
    "release",
    "signatures",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_child(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts or "\\" in relative:
        raise ValueError(f"unsafe manifest path: {relative}")
    target = root.joinpath(*pure.parts)
    if not target.resolve(strict=False).is_relative_to(root):
        raise ValueError(f"manifest path escapes toolkit: {relative}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pristine", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    manifest_path = root / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    core = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    expected_manifest_sha = hashlib.sha256(canonical(core)).hexdigest()
    checks: dict[str, bool] = {
        "root_is_directory": root.is_dir(),
        "manifest_digest_matches": manifest.get("manifest_sha256") == expected_manifest_sha,
        "manifest_status_sealed": manifest.get("status") == "sealed_label_empty_toolkit",
    }
    listed: set[Path] = {manifest_path}
    for index, entry in enumerate(manifest.get("files", []), start=1):
        relative = str(entry.get("path", ""))
        target = safe_child(root, relative)
        listed.add(target)
        checks[f"file_{index:02d}_regular"] = target.is_file() and not target.is_symlink()
        checks[f"file_{index:02d}_size"] = target.is_file() and target.stat().st_size == entry.get("bytes")
        checks[f"file_{index:02d}_sha256"] = target.is_file() and sha256_file(target) == entry.get("sha256")
    extras: list[str] = []
    private_entries: list[str] = []
    symlinks: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            symlinks.append(relative)
            continue
        under_writable = relative.split("/", maxsplit=1)[0] in WRITABLE_ROOTS
        if path.is_file() and path not in listed and not under_writable:
            extras.append(relative)
        if args.pristine and under_writable and path.is_file():
            private_entries.append(relative)
    checks["no_symlinks"] = not symlinks
    checks["no_unlisted_immutable_files"] = not extras
    checks["work_directories_pristine"] = not args.pristine or not private_entries
    passed = all(checks.values())
    result = {
        "schema_version": "m3-paper-v2-custodian-toolkit-verification-2.0",
        "status": "toolkit_verified" if passed else "toolkit_rejected",
        "checks": checks,
        "diagnostics": {
            "unlisted_immutable_files": sorted(extras),
            "pristine_work_entries": sorted(private_entries),
            "symlinks": sorted(symlinks),
        },
        "private_content_opened": False,
        "credentials_read": False,
        "network_calls_made": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
'''

_SEAL_SCRIPT = r'''#!/usr/bin/env python3
"""Build/finalize custody JSON at fixed toolkit-local paths, without overwrite."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.paper_v2.independent_blind_closeout_v2 import (
    build_unsigned_custody_seal,
    finalize_custody_seal,
)
from experiments.paper_v2.contracts import canonical_json_bytes


EXECUTION = ROOT / "release/blind_execution_v2.jsonl"
LABELS = ROOT / "private/labels/blind_labels_v2.jsonl"
UNSIGNED = ROOT / "signatures/unsigned_custody_v2.json"
DIGEST = ROOT / "signatures/custody_payload_sha256.txt"
FINAL = ROOT / "release/blind_custody_v2.json"


def write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-unsigned")
    build.add_argument("--custodian-id", required=True)
    build.add_argument("--signature-scheme", required=True)
    build.add_argument("--signature-key-id", required=True)
    for name in (
        "authoring-completed-at",
        "split-completed-at",
        "sealed-at",
        "execution-set-released-at",
        "developer-received-execution-set-at",
    ):
        build.add_argument(f"--{name}", required=True)
    final = commands.add_parser("finalize")
    final.add_argument(
        "--signature-file",
        type=Path,
        default=ROOT / "signatures/custody_payload_sha256.txt.asc",
    )
    args = parser.parse_args()
    if args.command == "build-unsigned":
        if UNSIGNED.exists() or DIGEST.exists():
            raise FileExistsError("unsigned custody outputs already exist; overwrite refused")
        value = build_unsigned_custody_seal(
            execution_set_path=EXECUTION,
            label_file_path=LABELS,
            custodian_id=args.custodian_id,
            custodian_signature_scheme=args.signature_scheme,
            custodian_signature_key_id=args.signature_key_id,
            authoring_completed_at=args.authoring_completed_at,
            split_completed_at=args.split_completed_at,
            sealed_at=args.sealed_at,
            execution_set_released_at=args.execution_set_released_at,
            developer_received_execution_set_at=args.developer_received_execution_set_at,
        )
        write_new(UNSIGNED, canonical_json_bytes(value) + b"\n")
        write_new(
            DIGEST,
            (str(value["custodian_signature_payload_sha256"]) + "\n").encode("ascii"),
        )
        result = {"status": "unsigned_custody_written", "network_calls_made": 0}
    else:
        if FINAL.exists():
            raise FileExistsError("final custody output already exists; overwrite refused")
        signature_file = args.signature_file.resolve(strict=True)
        signatures_root = (ROOT / "signatures").resolve(strict=True)
        if not signature_file.is_relative_to(signatures_root):
            raise ValueError("signature file must stay inside toolkit signatures directory")
        signature = signature_file.read_text(encoding="utf-8")
        value = finalize_custody_seal(
            read_object(UNSIGNED), custodian_signature=signature
        )
        write_new(FINAL, canonical_json_bytes(value) + b"\n")
        result = {"status": "final_custody_written", "network_calls_made": 0}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

_README = r'''# M3-PI Guard 独立盲测保管人工具包 v2

此目录只含公开接口、空模板和 600 个冻结空槽位；初始状态不含真实候选、
标签、保管人身份、签名、API 密钥或实验结果。整个保管流程应在保管人控制的
离线电脑或独立账户中进行，严禁把开发者可见的项目 `.env` 或 API 配置复制进来。

## 唯一正确的工作目录

将整个工具包复制到保管人电脑，例如 `D:\M3_Blind_Custodian_v2`。打开
PowerShell 后，先进入**工具包根目录**（能同时看到 `experiments`、`protocols`、
`private`、`release`、`scripts` 的目录）：

```powershell
Set-Location -LiteralPath 'D:\M3_Blind_Custodian_v2'
```

下文所有命令都从此目录运行。若 Python 不在 PATH，把示例中的 `python`
换成保管人机器的完整 Python 路径；不要使用开发者的 API 配置。

## 必须保管的文件

- `private\authored_pairs\authored_pairs.jsonl`：600 行原始私有 pair；不交开发者。
- `private\labels\blind_labels_v2.jsonl`：600 行独立标签；正式执行和结果 ID
  提交完成前绝不交开发者。
- `signatures\unsigned_custody_v2.json`：待签名 custody 声明。
- `signatures\custody_payload_sha256.txt` 及其 `.asc`：签名载荷与 detached
  signature。签名私钥必须保存在工具包之外，绝不复制或发送。
- `receipts\split_receipt_v2.json`、`receipts\pre_release_review_v2.json`：保管人
  侧校验回执，长期留存。

可以在封存后交给开发者的只有：

- `release\blind_execution_v2.jsonl`（无标签执行集）；
- `release\blind_custody_v2.json`（已签署的 custody manifest）；
- detached signature 与对应公钥可单独交给指定外部验签人。

## 文件夹职责

- `protocols\...\slots.jsonl`：冻结 600 槽位，不修改；SHA-256 已锁定。
- `private`：只由保管人访问，永不作为开发者导入目录。
- `release`：只放允许移交开发者的无标签文件。
- `receipts`：保存命令回执。
- `signatures`：保存公开签名材料；不得放签名私钥。

## 操作顺序

### 0. 验证工具包初始状态

```powershell
& '.\scripts\00_VERIFY_PRISTINE_TOOLKIT.ps1' -PythonExe 'python'
```

必须看到 `toolkit_verified`。该命令不读取 `private` 内容、不读取 credential、
不联网。

### 1. 私下编写 600 行

逐行参考
`protocols\paper_upgrade_v2\independent_blind_authoring_kit_v2\authored_pair_template.json`
和冻结槽位，把完整 JSONL 保存为：

`private\authored_pairs\authored_pairs.jsonl`

必须一行一个 JSON 对象、共 600 行，顺序与 `slots.jsonl` 完全一致。不能将
API 密钥、真实个人隐私、生产系统标识或可产生真实外部效果的凭据写入样本。

### 2. 确定性拆分 execution 与 label

```powershell
& '.\scripts\02_SPLIT_PRIVATE.ps1' -PythonExe 'python'
```

脚本生成无标签 `release\blind_execution_v2.jsonl`、私有
`private\labels\blind_labels_v2.jsonl` 和拆分回执。脚本拒绝覆盖已有输出。

### 3. 保管人侧预发布检查

```powershell
& '.\scripts\03_VALIDATE_PRE_RELEASE.ps1' -PythonExe 'python'
```

必须看到 `custodian_pre_release_passed`。此步骤会读取标签，只能由保管人运行。

### 4. 生成待签名 custody 文件

所有时间必须是带时区 ISO-8601，且按实际发生时间填写：

```powershell
& '.\scripts\04_BUILD_UNSIGNED_CUSTODY.ps1' `
  -PythonExe 'python' `
  -CustodianId '真实姓名或登记的稳定身份' `
  -SignatureScheme 'OpenPGP detached signature' `
  -SignatureKeyId '公钥 Key ID' `
  -AuthoringCompletedAt '2026-08-03T10:00:00+08:00' `
  -SplitCompletedAt '2026-08-03T10:10:00+08:00' `
  -SealedAt '2026-08-03T10:20:00+08:00' `
  -ExecutionReleasedAt '2026-08-03T10:30:00+08:00' `
  -DeveloperReceivedAt '2026-08-03T10:40:00+08:00'
```

示例时间只能替换为真实时间，不能照抄冒充事实。

### 5. 使用保管人自己的外部密钥签名

OpenPGP 示例（私钥仍在外部 GPG keyring）：

```powershell
gpg --armor --detach-sign --local-user '公钥 Key ID' `
  --output '.\signatures\custody_payload_sha256.txt.asc' `
  '.\signatures\custody_payload_sha256.txt'
```

若使用 minisign，应把 scheme/key ID 如实登记并生成等价 detached signature；
不得伪造签名字符串。

### 6. 写出最终 custody manifest

```powershell
& '.\scripts\05_FINALIZE_CUSTODY.ps1' -PythonExe 'python'
```

脚本只把签名绑定进 `release\blind_custody_v2.json`，不验证公钥信任链；外部
验签人仍须用公钥验证 detached signature。

### 7. 移交与继续保密

先把 release 中两个文件交开发者；保管人继续单独保存全部 private、receipts、
signatures 和工具包 manifest。开发者完成 3,600 条执行并提交内容无关的 output
ID 后，才进入保管人侧评分。标签解封前不得给开发者案例级标签、规则或答案。

## 禁止事项

- 不在项目开发仓库内填写或保存私有标签。
- 不把 `.env`、API key、签名私钥或密码放入工具包。
- 不修改冻结槽位或已经生成的终态文件；脚本拒绝覆盖。
- 不让模型或脚本执行真实邮件、支付、浏览器、生产 API 或其他外部效果。
- 不把一次本地字段校验描述为密码学验签；签名真实性必须由外部 verifier 证明。
'''

_PS_VERIFY = r'''[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe ".\scripts\verify_toolkit_v2.py" --root $root --pristine
    if ($LASTEXITCODE -ne 0) { throw "toolkit pristine verification failed" }
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 --help
    if ($LASTEXITCODE -ne 0) { throw "closeout module help failed" }
} finally {
    Pop-Location
}
'''

_PS_SPLIT = r'''[CmdletBinding()]
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
    $output = & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 split `
        --authored-pairs $authored --execution-output $execution --label-output $labels
    if ($LASTEXITCODE -ne 0) { throw "private split failed" }
    [IO.File]::WriteAllText($receipt, ($output -join [Environment]::NewLine) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $output
} finally {
    Pop-Location
}
'''

_PS_VALIDATE = r'''[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$execution = Join-Path $root "release\blind_execution_v2.jsonl"
$labels = Join-Path $root "private\labels\blind_labels_v2.jsonl"
$receipt = Join-Path $root "receipts\pre_release_review_v2.json"
if (Test-Path -LiteralPath $receipt) { throw "overwrite refused: $receipt" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $output = & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 validate-pre-release `
        --execution-set $execution --label-file $labels
    if ($LASTEXITCODE -ne 0) { throw "pre-release validation failed" }
    [IO.File]::WriteAllText($receipt, ($output -join [Environment]::NewLine) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $output
} finally {
    Pop-Location
}
'''

_PS_BUILD_UNSIGNED = r'''[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$CustodianId,
    [Parameter(Mandatory=$true)][string]$SignatureScheme,
    [Parameter(Mandatory=$true)][string]$SignatureKeyId,
    [Parameter(Mandatory=$true)][string]$AuthoringCompletedAt,
    [Parameter(Mandatory=$true)][string]$SplitCompletedAt,
    [Parameter(Mandatory=$true)][string]$SealedAt,
    [Parameter(Mandatory=$true)][string]$ExecutionReleasedAt,
    [Parameter(Mandatory=$true)][string]$DeveloperReceivedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe ".\scripts\custodian_seal_v2.py" build-unsigned `
        --custodian-id $CustodianId --signature-scheme $SignatureScheme `
        --signature-key-id $SignatureKeyId `
        --authoring-completed-at $AuthoringCompletedAt `
        --split-completed-at $SplitCompletedAt --sealed-at $SealedAt `
        --execution-set-released-at $ExecutionReleasedAt `
        --developer-received-execution-set-at $DeveloperReceivedAt
    if ($LASTEXITCODE -ne 0) { throw "unsigned custody build failed" }
} finally {
    Pop-Location
}
'''

_PS_FINALIZE = r'''[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe ".\scripts\custodian_seal_v2.py" finalize
    if ($LASTEXITCODE -ne 0) { throw "custody finalization failed" }
} finally {
    Pop-Location
}
'''

_PS_SIGN_EXTERNAL = r'''[CmdletBinding()]
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
'''

_PS_BUILD_REGISTRATION = r'''[CmdletBinding()]
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
'''

_PS_SIGN_REGISTRATION = r'''[CmdletBinding()]
param(
    [string]$OpenSSLExe = "openssl",
    [Parameter(Mandatory=$true)][string]$PrivateKeyPath
)
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
& (Join-Path $PSScriptRoot "SIGN_EXTERNAL_ED25519_DIGEST.ps1") `
    -OpenSSLExe $OpenSSLExe -PrivateKeyPath $PrivateKeyPath `
    -UnsignedJsonPath (Join-Path $root "signatures\unsigned_registration_v2.json") `
    -DigestField "registration_signature_payload_sha256" `
    -SignatureOutputPath (Join-Path $root "signatures\registration_signature_base64.txt")
if ($LASTEXITCODE -ne 0) { throw "registration signature failed" }
'''

_PS_FINALIZE_REGISTRATION = r'''[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "release\custodian_registration_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 finalize-registration `
        --unsigned-registration ".\signatures\unsigned_registration_v2.json" `
        --signature-base64-file ".\signatures\registration_signature_base64.txt" `
        --write-registration $output
    if ($LASTEXITCODE -ne 0) { throw "registration finalization failed" }
} finally { Pop-Location }
'''

_PS_VERIFY_REGISTRATION = r'''[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$VerifierId,
    [Parameter(Mandatory=$true)][string]$VerifiedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "receipts\custodian_registration_verifier_receipt_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 verify-registration `
        --registration ".\release\custodian_registration_v2.json" `
        --custodian-public-key ".\release\custodian_public_key.pem" `
        --verifier-id $VerifierId --verified-at $VerifiedAt --write-receipt $output
    if ($LASTEXITCODE -ne 0) { throw "registration verification failed" }
} finally { Pop-Location }
'''

_PS_SPLIT_FINAL = r'''[CmdletBinding()]
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
'''

_PS_VALIDATE_FINAL = r'''[CmdletBinding()]
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
'''

_PS_BUILD_CUSTODY_FINAL = r'''[CmdletBinding()]
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
'''

_PS_SIGN_CUSTODY = r'''[CmdletBinding()]
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
'''

_PS_FINALIZE_CUSTODY_FINAL = r'''[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "release\blind_custody_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 finalize-custody `
        --unsigned-custody ".\signatures\unsigned_custody_v2.json" `
        --signature-base64-file ".\signatures\custody_signature_base64.txt" `
        --write-custody $output
    if ($LASTEXITCODE -ne 0) { throw "custody finalization failed" }
} finally { Pop-Location }
'''

_PS_VERIFY_CUSTODY = r'''[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$VerifierId,
    [Parameter(Mandatory=$true)][string]$VerifiedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "receipts\custody_signature_verifier_receipt_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 verify-signature-receipt `
        --custody-manifest ".\release\blind_custody_v2.json" `
        --registration ".\release\custodian_registration_v2.json" `
        --registration-verifier-receipt ".\receipts\custodian_registration_verifier_receipt_v2.json" `
        --custodian-public-key ".\release\custodian_public_key.pem" `
        --verifier-id $VerifierId --verified-at $VerifiedAt --write-receipt $output
    if ($LASTEXITCODE -ne 0) { throw "custody signature verification failed" }
} finally { Pop-Location }
'''

_PS_STAGE_DEVELOPER_HANDOFF = r'''[CmdletBinding()]
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
'''

_PS_RELEASE_LABELS = r'''[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$ReleasedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$registration = Get-Content -LiteralPath (Join-Path $root "release\custodian_registration_v2.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$output = Join-Path $root "receipts\label_release_seal_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 release-labels-for-scoring `
        --custody-manifest ".\release\blind_custody_v2.json" `
        --label-file ".\private\labels\blind_labels_v2.jsonl" `
        --execution-output-seal ".\incoming_from_developer\execution_output_seal_v2.json" `
        --released-at $ReleasedAt --custodian-id ([string]$registration.custodian_id) `
        --write-release-seal $output
    if ($LASTEXITCODE -ne 0) { throw "label release for scoring failed" }
} finally { Pop-Location }
'''

_PS_SEAL_SCORING = r'''[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$ScoredAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$registration = Get-Content -LiteralPath (Join-Path $root "release\custodian_registration_v2.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$output = Join-Path $root "receipts\custodian_scoring_result_seal_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 seal-scoring-results `
        --custody-manifest ".\release\blind_custody_v2.json" `
        --execution-output-seal ".\incoming_from_developer\execution_output_seal_v2.json" `
        --output-package ".\incoming_from_developer\output_package_v2.jsonl" `
        --label-release-seal ".\receipts\label_release_seal_v2.json" `
        --label-file ".\private\labels\blind_labels_v2.jsonl" `
        --scoring-results ".\private\scoring\scoring_results_v2.jsonl" `
        --scored-at $ScoredAt --custodian-id ([string]$registration.custodian_id) `
        --write-result-seal $output
    if ($LASTEXITCODE -ne 0) { throw "scoring result seal failed" }
} finally { Pop-Location }
'''

_PS_BUILD_SCORING_ATTESTATION = r'''[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$SignedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$registration = Get-Content -LiteralPath (Join-Path $root "release\custodian_registration_v2.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$output = Join-Path $root "signatures\unsigned_scoring_attestation_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 build-unsigned-scoring-attestation `
        --scoring-result-seal ".\receipts\custodian_scoring_result_seal_v2.json" `
        --custody-manifest ".\release\blind_custody_v2.json" `
        --registration ".\release\custodian_registration_v2.json" `
        --custodian-id ([string]$registration.custodian_id) `
        --signed-at $SignedAt --write-unsigned $output
    if ($LASTEXITCODE -ne 0) { throw "unsigned scoring attestation build failed" }
} finally { Pop-Location }
'''

_PS_SIGN_SCORING_ATTESTATION = r'''[CmdletBinding()]
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
'''

_PS_FINALIZE_SCORING_ATTESTATION = r'''[CmdletBinding()]
param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "receipts\custodian_scoring_attestation_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 finalize-scoring-attestation `
        --unsigned-attestation ".\signatures\unsigned_scoring_attestation_v2.json" `
        --signature-base64-file ".\signatures\scoring_attestation_signature_base64.txt" `
        --write-attestation $output
    if ($LASTEXITCODE -ne 0) { throw "scoring attestation finalization failed" }
} finally { Pop-Location }
'''

_PS_VERIFY_SCORING_ATTESTATION = r'''[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [Parameter(Mandatory=$true)][string]$VerifierId,
    [Parameter(Mandatory=$true)][string]$VerifiedAt
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root "receipts\custodian_scoring_attestation_verifier_receipt_v2.json"
if (Test-Path -LiteralPath $output) { throw "overwrite refused: $output" }
Push-Location -LiteralPath $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExe -m experiments.paper_v2.independent_blind_closeout_v2 verify-scoring-attestation `
        --scoring-attestation ".\receipts\custodian_scoring_attestation_v2.json" `
        --scoring-result-seal ".\receipts\custodian_scoring_result_seal_v2.json" `
        --custody-manifest ".\release\blind_custody_v2.json" `
        --registration ".\release\custodian_registration_v2.json" `
        --registration-verifier-receipt ".\receipts\custodian_registration_verifier_receipt_v2.json" `
        --custodian-public-key ".\release\custodian_public_key.pem" `
        --verifier-id $VerifierId --verified-at $VerifiedAt --write-receipt $output
    if ($LASTEXITCODE -ne 0) { throw "scoring attestation verification failed" }
} finally { Pop-Location }
'''

_PS_STAGE_SCORING_HANDOFF = r'''[CmdletBinding()]
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
'''

_IDENTITY_ATTESTATION_TEMPLATE = '''\
M3-PI Guard 独立盲测保管人离线身份与独立性声明（模板）

保管人稳定身份：<真实姓名或经登记的稳定身份>
与项目关系：<导师/同学/外部协作者等>
未参与项目代码实现：是
未参与阈值选择：是
未参与实验调参：是
同意在正式执行完成前不向开发者提供标签：是
同意先只提供无标签 execution set：是
确认时间（带时区）：<ISO-8601>
线下身份核验方式：<由真人 verifier 填写，不放身份证号等高敏感信息>

本文件只保存在保管人 private/registration 目录。公开登记仅记录其 SHA-256，
不公开本文件正文。请删除所有尖括号占位符后再使用。
'''

_SCORING_ENTRY_TEMPLATE = '''\
{"case_id":"<copy from output row>","condition_id":"<copy from output row>","label_row_sha256":"<canonical private label-row SHA-256>","operational_status":"<copy from output row>","output_id":"<copy from output row>","output_row_sha256":"<canonical output-row SHA-256>","schema_version":"m3-paper-v2-independent-blind-scoring-entry-2.0","sequence":1,"slot_id":"<copy from output row>","task_completion":false,"unsafe_effect":false,"work_key":"<copy from output row>"}
'''

_REQUIREMENTS = "cryptography==44.0.1\n"

_README_FINAL = r'''# M3-PI Guard 独立盲测保管人工具包 v2（Ed25519 完整链）

## 1. 工作目录与边界

把整个目录放在保管人独立控制的电脑或账户，例如：

```powershell
Set-Location -LiteralPath 'D:\M3_Blind_Custodian_v2'
```

这一级必须能看到 `experiments`、`protocols`、`private`、`release`、
`incoming_from_developer`、`receipts`、`signatures`、`scripts`。下文所有脚本都
从此根目录运行。工具包初始状态不含真实样本、标签、身份、签名、密钥、API
配置或结果；脚本不联网，也不调用任何模型或外部效果工具。

每条命令的工作目录固定如下，运行前都应先执行本节的 `Set-Location`：

| 命令 | 固定工作目录 |
|---|---|
| Python 依赖检查/离线安装 | 工具包根目录 |
| OpenSSL 生成私钥、导出公钥 | 工具包根目录（私钥输出路径必须指向根目录外） |
| `00` 至 `11` 的登记、拆分、封存、验签、首次 staging | 工具包根目录 |
| `12` 至 `18` 的标签释放、评分封存、签名验算、最终 staging | 工具包根目录 |

不要进入 `scripts`、`private` 或 `release` 后运行命令；文中的相对路径全部以
工具包根目录为基准。

Python 必须可导入 `cryptography`。离线环境若缺失，只能从可信 wheelhouse 安装：

```powershell
python -m pip install --no-index --find-links 'D:\trusted-wheelhouse' -r '.\requirements-custodian.txt'
```

## 2. 必须长期保管什么

始终不交开发者：

- `private\registration\offline_identity_attestation.txt`；
- `private\authored_pairs\authored_pairs.jsonl`（600 个私有 pair）；
- `private\labels\blind_labels_v2.jsonl`（600 个私有标签）；
- 工具包外部的 Ed25519 私钥；
- `receipts\split_receipt_v2.json` 和 `signatures` 中的待签名/签名过程文件。

执行前先把 verifier/pre-release 回执写入 `receipts`，验证通过后由固定 staging
脚本单向复制到 `release\developer_handoff_v2`。只把这个目录交开发者；它
必须包含且仅包含以下公开证据（另有一个逐文件 SHA-256 清单）：

1. `blind_execution_v2.jsonl`；
2. `blind_custody_v2.json`；
3. `pre_release_review_v2.json`；
4. `custodian_registration_v2.json`；
5. `custodian_registration_verifier_receipt_v2.json`；
6. `custody_signature_verifier_receipt_v2.json`；
7. `custodian_public_key.pem`；
8. 根目录 `toolkit_manifest_v2.json`。

标签文件绝不能进入 release、开发仓库、邮件附件或共享盘。Ed25519 私钥必须
保存在工具包根目录之外；脚本只把外部私钥路径传给本机 OpenSSL，不复制、
不记录私钥路径或密钥内容。

## 3. Day-1：登记真实保管人（零标签）

### 3.1 验证初始包

```powershell
& '.\scripts\00_VERIFY_PRISTINE_TOOLKIT.ps1' -PythonExe 'python'
```

必须出现 `toolkit_verified`，且 closeout 模块 help 正常。

### 3.2 在工具包外生成 Ed25519 私钥并导出公钥

以下私钥目录只是示例，必须由保管人独占且位于工具包外：

```powershell
New-Item -ItemType Directory -Path 'D:\M3_Custodian_PrivateKey' -ErrorAction Stop
openssl genpkey -algorithm ED25519 -out 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem'
openssl pkey -in 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem' -pubout -out '.\release\custodian_public_key.pem'
```

不得把私钥复制进工具包。把
`templates\offline_identity_attestation_template.txt` 复制为
`private\registration\offline_identity_attestation.txt`，由真人填写并删除所有
占位符。不要写身份证号、API key 等高敏感信息。

### 3.3 构建、签名、完成并验算登记

```powershell
& '.\scripts\01_BUILD_UNSIGNED_REGISTRATION.ps1' -PythonExe 'python' `
  -CustodianId '真实姓名或登记的稳定身份' `
  -ProjectRelationship '与项目的真实关系' `
  -ConfirmedAt '2026-08-03T09:00:00+08:00'

& '.\scripts\02_SIGN_REGISTRATION.ps1' -OpenSSLExe 'openssl' `
  -PrivateKeyPath 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem'

& '.\scripts\03_FINALIZE_REGISTRATION.ps1' -PythonExe 'python'

& '.\scripts\04_VERIFY_REGISTRATION.ps1' -PythonExe 'python' `
  -VerifierId '真实验签人稳定身份' `
  -VerifiedAt '2026-08-03T09:20:00+08:00'
```

所有示例时间必须换成真实、带时区且顺序正确的时间。最后 receipt 状态必须为
`custodian_registration_verified_clock_may_start`。数学验签只证明公钥控制权；
真人身份仍由线下核验声明负责，不能夸称密码学证明了真实姓名。

## 4. 编写与封存 600 条

### 4.1 编写

逐行参考 v2 `authored_pair_template.json`，严格按 v1 `slots.jsonl` 顺序写入：

`private\authored_pairs\authored_pairs.jsonl`

必须恰好 600 行：attack 360、benign_legal_tool 120、benign_no_tool 120；作者组
300/300。不得含真实 credential、生产标识或可触发真实外部效果的数据。

### 4.2 拆分和保管人侧检查

```powershell
& '.\scripts\05_SPLIT_PRIVATE.ps1' -PythonExe 'python'
& '.\scripts\06_VALIDATE_PRE_RELEASE.ps1' -PythonExe 'python'
```

第二条必须返回 `custodian_pre_release_passed`。两条命令会读取私有 label，因此
只能在保管人环境运行；所有输出均拒绝覆盖。

### 4.3 构建并签署 custody

```powershell
& '.\scripts\07_BUILD_UNSIGNED_CUSTODY.ps1' -PythonExe 'python' `
  -AuthoringCompletedAt '2026-08-05T10:00:00+08:00' `
  -SplitCompletedAt '2026-08-05T10:10:00+08:00' `
  -SealedAt '2026-08-05T10:20:00+08:00' `
  -ExecutionReleasedAt '2026-08-05T10:30:00+08:00' `
  -DeveloperReceivedAt '2026-08-05T10:40:00+08:00'

& '.\scripts\08_SIGN_CUSTODY.ps1' -OpenSSLExe 'openssl' `
  -PrivateKeyPath 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem'

& '.\scripts\09_FINALIZE_CUSTODY.ps1' -PythonExe 'python'

& '.\scripts\10_VERIFY_CUSTODY_SIGNATURE.ps1' -PythonExe 'python' `
  -VerifierId '真实验签人稳定身份' `
  -VerifiedAt '2026-08-05T10:50:00+08:00'
```

最后状态必须为 `custody_signature_cryptographically_verified`。此时还不能手工
挑文件发送。仍在工具包根目录运行固定白名单 staging：

```powershell
& '.\scripts\11_STAGE_DEVELOPER_HANDOFF.ps1'
```

脚本从 `receipts` 与公开工作文件复制八项证据到
`release\developer_handoff_v2`，生成逐文件 SHA-256 清单，并拒绝 label JSONL、
authored pair 和 private key。只移交该完整目录；继续独占全部 private、
receipts、signatures 和外部私钥。

## 5. 开发者完成 3,600 条后，保管人评分

在收到开发者返回文件前不执行本节。先把以下两项放入固定目录：

- `incoming_from_developer\execution_output_seal_v2.json`；
- `incoming_from_developer\output_package_v2.jsonl`（3,600 行、内容无关引用）。

确认 output seal 表明完整执行已发生后，才运行：

```powershell
& '.\scripts\12_RELEASE_LABELS_FOR_SCORING.ps1' -PythonExe 'python' `
  -ReleasedAt '2026-08-20T10:00:00+08:00'
```

这只允许标签进入保管人评分进程，不允许交开发者。参考
`templates\scoring_entry_template.json`，结合私有标签与 output package 产生恰好
3,600 行 `private\scoring\scoring_results_v2.jsonl`，然后运行：

```powershell
& '.\scripts\13_SEAL_SCORING_RESULTS.ps1' -PythonExe 'python' `
  -ScoredAt '2026-08-21T10:00:00+08:00'
```

评分 seal 还不是最终签名证据。使用与登记/custody 相同的外部 Ed25519 私钥，
按顺序构建、签名、完成和由具名 verifier 数学复核结果 manifest：

```powershell
& '.\scripts\14_BUILD_UNSIGNED_SCORING_ATTESTATION.ps1' -PythonExe 'python' `
  -SignedAt '2026-08-21T10:10:00+08:00'

& '.\scripts\15_SIGN_SCORING_ATTESTATION.ps1' -OpenSSLExe 'openssl' `
  -PrivateKeyPath 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem'

& '.\scripts\16_FINALIZE_SCORING_ATTESTATION.ps1' -PythonExe 'python'

& '.\scripts\17_VERIFY_SCORING_ATTESTATION.ps1' -PythonExe 'python' `
  -VerifierId '真实验签人稳定身份' `
  -VerifiedAt '2026-08-21T10:20:00+08:00'
```

receipt 状态必须为 `custodian_scoring_result_signature_verified`。随后仍从工具包
根目录执行：

```powershell
& '.\scripts\18_STAGE_SCORING_HANDOFF.ps1'
```

它只把 `scoring_results_v2.jsonl`、`label_release_seal_v2.json`、结果 seal、
已签署 scoring attestation、验签 receipt 及逐文件 SHA-256 清单放入
`release\scoring_handoff_v2`。只交该目录；仍不交私有 label JSONL。

## 6. 绝对禁止

- 不修改冻结 `slots.jsonl`、历史 v1 文件或任何已终态输出；
- 不把 `.env`、API key、签名私钥、密码、真实隐私或生产凭据放进工具包；
- 不允许开发者在执行完成前看到 label、规则、答案或案例级判定；
- 不执行真实邮件、支付、浏览器、生产 API 或任何真实外部效果；
- 不因结果好坏删除、改写或重跑终态记录；
- 不把字段完整性检查冒充 Ed25519 数学验签，也不把公钥控制权冒充真人身份。
'''


class CustodianToolkitV2Error(ValueError):
    """当无法安全生成无标签工具包时抛出的异常。"""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or ".." in path.parts
        or "." in path.parts
        or "\\" in value
    ):
        raise CustodianToolkitV2Error(f"unsafe toolkit-relative path: {value}")
    return path


def _safe_source_file(project_root: Path, relative: str) -> Path:
    path = _safe_relative_path(relative)
    target = project_root.joinpath(*path.parts)
    try:
        resolved = target.resolve(strict=True)
    except OSError as exc:
        raise CustodianToolkitV2Error(f"missing allowlisted source: {relative}") from exc
    if not resolved.is_relative_to(project_root) or not resolved.is_file():
        raise CustodianToolkitV2Error(f"allowlisted source escaped project: {relative}")
    if target.is_symlink():
        raise CustodianToolkitV2Error(f"symlink source refused: {relative}")
    return resolved


def _validate_output_dir(output_dir: Path) -> Path:
    if not output_dir.is_absolute():
        raise CustodianToolkitV2Error("output directory must be an absolute path")
    if ".." in output_dir.parts:
        raise CustodianToolkitV2Error("output directory traversal is forbidden")
    if output_dir.exists() or output_dir.is_symlink():
        raise CustodianToolkitV2Error("output directory already exists; overwrite refused")
    try:
        parent = output_dir.parent.resolve(strict=True)
    except OSError as exc:
        raise CustodianToolkitV2Error("output parent must already exist") from exc
    if not parent.is_dir() or output_dir.parent.is_symlink():
        raise CustodianToolkitV2Error("output parent must be a real directory")
    if not re.fullmatch(r"[^<>:\"/\\|?*]+", output_dir.name):
        raise CustodianToolkitV2Error("output directory name contains unsafe characters")
    return parent / output_dir.name


def _generated_files() -> dict[str, bytes]:
    text_files = {
        "README_CUSTODIAN_ZH.md": _README_FINAL,
        "requirements-custodian.txt": _REQUIREMENTS,
        "experiments/__init__.py": _PACKAGE_MARKER,
        "experiments/paper_v2/__init__.py": _PACKAGE_MARKER,
        "experiments/paper_v2/contracts.py": _STANDALONE_CONTRACTS,
        "scripts/verify_toolkit_v2.py": _VERIFY_SCRIPT,
        "scripts/00_VERIFY_PRISTINE_TOOLKIT.ps1": _PS_VERIFY,
        "scripts/SIGN_EXTERNAL_ED25519_DIGEST.ps1": _PS_SIGN_EXTERNAL,
        "scripts/01_BUILD_UNSIGNED_REGISTRATION.ps1": _PS_BUILD_REGISTRATION,
        "scripts/02_SIGN_REGISTRATION.ps1": _PS_SIGN_REGISTRATION,
        "scripts/03_FINALIZE_REGISTRATION.ps1": _PS_FINALIZE_REGISTRATION,
        "scripts/04_VERIFY_REGISTRATION.ps1": _PS_VERIFY_REGISTRATION,
        "scripts/05_SPLIT_PRIVATE.ps1": _PS_SPLIT_FINAL,
        "scripts/06_VALIDATE_PRE_RELEASE.ps1": _PS_VALIDATE_FINAL,
        "scripts/07_BUILD_UNSIGNED_CUSTODY.ps1": _PS_BUILD_CUSTODY_FINAL,
        "scripts/08_SIGN_CUSTODY.ps1": _PS_SIGN_CUSTODY,
        "scripts/09_FINALIZE_CUSTODY.ps1": _PS_FINALIZE_CUSTODY_FINAL,
        "scripts/10_VERIFY_CUSTODY_SIGNATURE.ps1": _PS_VERIFY_CUSTODY,
        "scripts/11_STAGE_DEVELOPER_HANDOFF.ps1": _PS_STAGE_DEVELOPER_HANDOFF,
        "scripts/12_RELEASE_LABELS_FOR_SCORING.ps1": _PS_RELEASE_LABELS,
        "scripts/13_SEAL_SCORING_RESULTS.ps1": _PS_SEAL_SCORING,
        "scripts/14_BUILD_UNSIGNED_SCORING_ATTESTATION.ps1": (
            _PS_BUILD_SCORING_ATTESTATION
        ),
        "scripts/15_SIGN_SCORING_ATTESTATION.ps1": _PS_SIGN_SCORING_ATTESTATION,
        "scripts/16_FINALIZE_SCORING_ATTESTATION.ps1": (
            _PS_FINALIZE_SCORING_ATTESTATION
        ),
        "scripts/17_VERIFY_SCORING_ATTESTATION.ps1": (
            _PS_VERIFY_SCORING_ATTESTATION
        ),
        "scripts/18_STAGE_SCORING_HANDOFF.ps1": _PS_STAGE_SCORING_HANDOFF,
        "templates/offline_identity_attestation_template.txt": (
            _IDENTITY_ATTESTATION_TEMPLATE
        ),
        "templates/scoring_entry_template.json": _SCORING_ENTRY_TEMPLATE,
    }
    return {
        path: text.replace("\r\n", "\n").encode("utf-8")
        for path, text in text_files.items()
    }


def build_custodian_toolkit(
    output_dir: Path,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """创建新的不可变接口树加上空的私有工作文件夹。"""

    root = project_root.resolve(strict=True)
    if not root.is_dir():
        raise CustodianToolkitV2Error("project root must be a directory")
    destination = _validate_output_dir(output_dir)

    payloads = _generated_files()
    roles: dict[str, str] = {path: "generated_offline_support" for path in payloads}
    for source_relative, destination_relative in SOURCE_COPY_MAP.items():
        source = _safe_source_file(root, source_relative)
        destination_path = _safe_relative_path(destination_relative).as_posix()
        if destination_path in payloads:
            raise CustodianToolkitV2Error(
                f"duplicate toolkit destination: {destination_path}"
            )
        payload = source.read_bytes()
        if source_relative == AUTHORING_README_PATH:
            text = payload.decode("utf-8")
            text = text.replace(
                "所有模块命令均在仓库根目录运行。本机当前路径为：",
                "开发者模块命令均在开发者仓库根目录运行，以下为占位示例：",
            )
            text = re.sub(
                r"(?im)^Set-Location\s+['\"][A-Z]:[\\/][^'\"]*['\"]\s*$",
                "Set-Location '<developer-project-root>'",
                text,
            )
            text = re.sub(
                r"(?im)^\$PY\s*=\s*['\"][A-Z]:[\\/][^'\"]*python\.exe['\"]\s*$",
                "$PY = '<project-python.exe>'",
                text,
            )
            payload = text.encode("utf-8")
        payloads[destination_path] = payload
        roles[destination_path] = "allowlisted_public_interface"

    slots_path = (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl"
    )
    if _sha256_bytes(payloads[slots_path]) != FROZEN_SLOTS_SHA256:
        raise CustodianToolkitV2Error("frozen 600-slot hash drift")
    status_path = (
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/status.json"
    )
    try:
        status = json.loads(payloads[status_path])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CustodianToolkitV2Error("v2 kit status is invalid") from exc
    if not (
        status.get("candidate_present") is False
        and status.get("independent_label_file_present") is False
        and status.get("real_authoring_pairs_present") is False
        and status.get("scientific_outcomes_read") == 0
    ):
        raise CustodianToolkitV2Error("v2 source kit is not label-empty")

    # All reads and validation finish before the single-use destination exists.
    destination.mkdir(exist_ok=False)
    for relative in EMPTY_WORK_DIRS:
        path = _safe_relative_path(relative)
        destination.joinpath(*path.parts).mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    for relative in sorted(payloads):
        path = _safe_relative_path(relative)
        target = destination.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payloads[relative])
        entries.append(
            {
                "path": relative,
                "bytes": len(payloads[relative]),
                "sha256": _sha256_bytes(payloads[relative]),
                "role": roles[relative],
            }
        )
    core: dict[str, Any] = {
        "schema_version": TOOLKIT_SCHEMA_VERSION,
        "status": "sealed_label_empty_toolkit",
        "files": entries,
        "initially_empty_work_directories": list(EMPTY_WORK_DIRS),
        "frozen_slots": {
            "rows": 600,
            "sha256": FROZEN_SLOTS_SHA256,
        },
        "evidence_boundary": {
            "source_enumeration_used": False,
            "source_allowlist_entries": len(SOURCE_COPY_MAP),
            "real_authoring_pairs_copied": 0,
            "real_candidate_rows_copied": 0,
            "real_label_rows_copied": 0,
            "credentials_read": False,
            "configuration_files_copied": 0,
            "prior_outputs_copied": 0,
            "network_calls_made": 0,
        },
        "single_use": {
            "existing_destination_refused": True,
            "overwrite_supported": False,
        },
    }
    manifest = {
        **core,
        "manifest_sha256": hashlib.sha256(_canonical_json_bytes(core)).hexdigest(),
    }
    manifest_path = destination / TOOLKIT_MANIFEST_NAME
    manifest_path.write_bytes(_canonical_json_bytes(manifest) + b"\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--allow-deprecated-builder",
        action="store_true",
        help=(
            "explicitly acknowledge that v2 wrappers no longer match the "
            "hardened closeout interface; use the Python-first v3 package instead"
        ),
    )
    args = parser.parse_args()
    if not args.allow_deprecated_builder:
        parser.error(
            "v2 builder is superseded and fails closed because its wrappers do not "
            "match the hardened closeout interface; use "
            "independent_blind_custodian_review_package_v3.py"
        )
    result = build_custodian_toolkit(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
