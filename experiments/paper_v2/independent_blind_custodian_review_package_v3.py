"""构建 Python 原生独立盲测托管人审查材料包（版本 V3）。

打包所有验证脚本、静态类型检查器与报告模板，供托管人一键复核。
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
MANIFEST_NAME = "review_manifest_v3.json"
SCHEMA_VERSION = "m3-paper-v2-independent-blind-python-review-manifest-3.0"
FROZEN_SLOTS_SHA256 = (
    "4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8"
)
ASSET_ROOT = (
    "protocols/paper_upgrade_v2/independent_blind_python_review_package_v3"
)

# Complete repository read boundary.  Never replace with directory walking.
SOURCE_COPY_MAP: Mapping[str, str] = {
    "scripts/independent_blind_custodian_cli_v3.py": "custodian.py",
    f"{ASSET_ROOT}/README.md": "README.md",
    f"{ASSET_ROOT}/.gitignore": ".gitignore",
    f"{ASSET_ROOT}/requirements-review.txt": "requirements-review.txt",
    f"{ASSET_ROOT}/review_package_config.json": "review_package_config.json",
    f"{ASSET_ROOT}/review_package_config.schema.json": (
        "schemas/review_package_config.schema.json"
    ),
    f"{ASSET_ROOT}/review_manifest_v3.schema.json": (
        "schemas/review_manifest_v3.schema.json"
    ),
    f"{ASSET_ROOT}/offline_identity_attestation_template.txt": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_python_review_package_v3/"
        "offline_identity_attestation_template.txt"
    ),
    "experiments/paper_v2/independent_blind_closeout_v2.py": (
        "review_source/experiments/paper_v2/independent_blind_closeout_v2.py"
    ),
    "experiments/paper_v2/independent_blind_closeout_v1.py": (
        "review_source/experiments/paper_v2/independent_blind_closeout_v1.py"
    ),
    "protocols/paper_upgrade_v2/independent_blind_closeout_interface_v1.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_closeout_interface_v1.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_closeout_interface_v2.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_closeout_interface_v2.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/slots.jsonl"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/status.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/status.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/"
    "case_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/case_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/"
    "custody_manifest_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/custody_manifest_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/README.md": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/README.md"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "authored_pair_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/authored_pair_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "case_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/case_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "content_free_output_entry_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "content_free_output_entry_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "effect_receipt_entry_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/effect_receipt_entry_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "custodian_registration_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "custodian_registration_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "custody_manifest_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/custody_manifest_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "label_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/label_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "provider_request_chain_started_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "provider_request_chain_started_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "provider_request_chain_terminal_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "provider_request_chain_terminal_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "provider_trace_receipt_entry_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "provider_trace_receipt_entry_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "registration_verifier_receipt_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "registration_verifier_receipt_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "scoring_attestation_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/scoring_attestation_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "scoring_attestation_verifier_receipt_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "scoring_attestation_verifier_receipt_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "scoring_entry_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/scoring_entry_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "scoring_integrity_verifier_receipt_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "scoring_integrity_verifier_receipt_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "signature_verifier_receipt_template.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/"
        "signature_verifier_receipt_template.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "slot_reference.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/slot_reference.json"
    ),
    "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/"
    "status.json": (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/status.json"
    ),
    "tests/unit/test_paper_v2_independent_blind_closeout_v2.py": (
        "tests/test_closeout_v2.py"
    ),
    "tests/unit/test_paper_v2_independent_blind_closeout_v1.py": (
        "review_source/tests/unit/"
        "test_paper_v2_independent_blind_closeout_v1.py"
    ),
    "experiments/paper_v2/independent_blind_custodian_review_package_v3.py": (
        "review/build_source/independent_blind_custodian_review_package_v3.py"
    ),
    "tests/unit/"
    "test_paper_v2_independent_blind_custodian_review_package_v3.py": (
        "review/build_source/"
        "test_paper_v2_independent_blind_custodian_review_package_v3.py"
    ),
}

EMPTY_WORK_DIRS = (
    "work/private/registration",
    "work/private/authored_pairs",
    "work/private/labels",
    "work/private/scoring",
    "work/generated/receipts",
    "work/generated/signatures",
    "work/generated/release",
    "work/incoming_from_developer",
    "work/handoff",
    "work/runtime",
)

_PACKAGE_MARKER = '"""Standalone review package marker."""\n'
_CONTRACTS = '''\
"""Minimal canonical JSON contract for the standalone review package."""
from __future__ import annotations

import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
'''

_CONFTEST = '''\
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "review_source"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
'''

_PACKAGE_TEST = '''\
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_review_package_verifies_and_has_no_powershell_wrapper() -> None:
    completed = subprocess.run(
        [sys.executable, "-B", "custodian.py", "verify"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "review_package_verified"
    assert not list(ROOT.rglob("*.ps1"))


def test_manifest_binds_active_core_and_frozen_slots() -> None:
    manifest = json.loads(
        (ROOT / "review_manifest_v3.json").read_text(encoding="utf-8")
    )
    entries = {row["path"]: row for row in manifest["files"]}
    core = ROOT / (
        "review_source/experiments/paper_v2/independent_blind_closeout_v2.py"
    )
    slots = ROOT / (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/slots.jsonl"
    )
    assert hashlib.sha256(core.read_bytes()).hexdigest() == entries[
        core.relative_to(ROOT).as_posix()
    ]["sha256"] == manifest["critical_bindings"]["closeout_core_sha256"]
    assert hashlib.sha256(slots.read_bytes()).hexdigest() == (
        "4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8"
    )


def test_mutable_config_is_work_scoped_and_private_key_is_external() -> None:
    config = json.loads(
        (ROOT / "review_package_config.json").read_text(encoding="utf-8")
    )
    assert config["work_root"] == "work"
    assert all(path.startswith("work/") for path in config["paths"].values())
    assert "private_key" not in config["paths"]
'''


class ReviewPackageV3Error(ValueError):
    """当审查包无法安全构建时抛出的异常。"""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or "." in path.parts
        or ".." in path.parts
        or "\\" in value
    ):
        raise ReviewPackageV3Error(f"unsafe package-relative path: {value}")
    return path


def safe_source(project_root: Path, relative: str) -> Path:
    target = project_root.joinpath(*safe_relative(relative).parts)
    try:
        resolved = target.resolve(strict=True)
    except OSError as exc:
        raise ReviewPackageV3Error(f"missing allowlisted source: {relative}") from exc
    if (
        not resolved.is_relative_to(project_root)
        or not resolved.is_file()
        or target.is_symlink()
    ):
        raise ReviewPackageV3Error(f"unsafe allowlisted source: {relative}")
    return resolved


def validate_output_dir(output_dir: Path) -> Path:
    if not output_dir.is_absolute():
        raise ReviewPackageV3Error("output directory must be absolute")
    if ".." in output_dir.parts:
        raise ReviewPackageV3Error("output directory traversal is forbidden")
    if output_dir.exists() or output_dir.is_symlink():
        raise ReviewPackageV3Error("output directory exists; overwrite refused")
    try:
        parent = output_dir.parent.resolve(strict=True)
    except OSError as exc:
        raise ReviewPackageV3Error("output parent must already exist") from exc
    if not parent.is_dir() or output_dir.parent.is_symlink():
        raise ReviewPackageV3Error("output parent must be a real directory")
    if not re.fullmatch(r'[^<>:"/\\|?*]+', output_dir.name):
        raise ReviewPackageV3Error("unsafe output directory name")
    return parent / output_dir.name


def generated_files() -> dict[str, bytes]:
    values = {
        "review_source/experiments/__init__.py": _PACKAGE_MARKER,
        "review_source/experiments/paper_v2/__init__.py": _PACKAGE_MARKER,
        "review_source/experiments/paper_v2/contracts.py": _CONTRACTS,
        "tests/conftest.py": _CONFTEST,
        "tests/test_review_package_v3.py": _PACKAGE_TEST,
    }
    return {
        path: value.replace("\r\n", "\n").encode("utf-8")
        for path, value in values.items()
    }


def build_review_package(
    output_dir: Path, *, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    root = project_root.resolve(strict=True)
    if not root.is_dir():
        raise ReviewPackageV3Error("project root must be a directory")
    destination = validate_output_dir(output_dir)
    payloads = generated_files()
    roles = {path: "generated_offline_review_support" for path in payloads}
    for source_relative, destination_relative in SOURCE_COPY_MAP.items():
        destination_path = safe_relative(destination_relative).as_posix()
        if destination_path in payloads:
            raise ReviewPackageV3Error(
                f"duplicate package destination: {destination_path}"
            )
        payloads[destination_path] = safe_source(root, source_relative).read_bytes()
        roles[destination_path] = "explicitly_allowlisted_review_source"

    slots_path = (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/slots.jsonl"
    )
    if sha256_bytes(payloads[slots_path]) != FROZEN_SLOTS_SHA256:
        raise ReviewPackageV3Error("frozen 600-slot hash drift")
    status_path = (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v2/status.json"
    )
    try:
        status = json.loads(payloads[status_path])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewPackageV3Error("v2 authoring source status is invalid") from exc
    if not (
        status.get("candidate_present") is False
        and status.get("independent_label_file_present") is False
        and status.get("real_authoring_pairs_present") is False
        and status.get("scientific_outcomes_read") == 0
    ):
        raise ReviewPackageV3Error("authoring source is not label-empty")
    forbidden_suffixes = (".env", ".pem", ".key", ".pfx", ".p12", ".ps1")
    if any(path.lower().endswith(forbidden_suffixes) for path in payloads):
        raise ReviewPackageV3Error("forbidden credential/wrapper file in package")
    if any(
        token in path.lower()
        for path in payloads
        for token in ("authored_pairs.jsonl", "blind_labels", "output_package_v2")
    ):
        raise ReviewPackageV3Error("private or prior-run data in immutable package")

    destination.mkdir(exist_ok=False)
    for relative in EMPTY_WORK_DIRS:
        destination.joinpath(*safe_relative(relative).parts).mkdir(
            parents=True, exist_ok=False
        )
    entries: list[dict[str, Any]] = []
    for relative in sorted(payloads):
        target = destination.joinpath(*safe_relative(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payloads[relative])
        entries.append(
            {
                "path": relative,
                "bytes": len(payloads[relative]),
                "sha256": sha256_bytes(payloads[relative]),
                "role": roles[relative],
            }
        )
    core_path = (
        "review_source/experiments/paper_v2/independent_blind_closeout_v2.py"
    )
    cli_path = "custodian.py"
    core: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "sealed_python_first_review_package",
        "files": entries,
        "initially_empty_work_directories": list(EMPTY_WORK_DIRS),
        "frozen_slots": {
            "path": slots_path,
            "rows": 600,
            "sha256": FROZEN_SLOTS_SHA256,
        },
        "critical_bindings": {
            "closeout_core_sha256": sha256_bytes(payloads[core_path]),
            "custodian_cli_sha256": sha256_bytes(payloads[cli_path]),
            "review_package_config_sha256": sha256_bytes(
                payloads["review_package_config.json"]
            ),
        },
        "evidence_boundary": {
            "source_enumeration_used": False,
            "source_allowlist_entries": len(SOURCE_COPY_MAP),
            "real_authoring_pairs_copied": 0,
            "real_candidate_rows_copied": 0,
            "real_label_rows_copied": 0,
            "credentials_read": False,
            "private_key_copied": False,
            "configuration_files_copied": 0,
            "prior_outputs_copied": 0,
            "powershell_wrappers_copied": 0,
            "network_calls_made": 0,
        },
        "single_use": {
            "existing_destination_refused": True,
            "overwrite_supported": False,
            "all_runtime_outputs_under_gitignored_work": True,
            "private_key_required_package_external": True,
        },
    }
    manifest = {
        **core,
        "manifest_sha256": sha256_bytes(canonical_json_bytes(core)),
    }
    (destination / MANIFEST_NAME).write_bytes(canonical_json_bytes(manifest) + b"\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build_review_package(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
