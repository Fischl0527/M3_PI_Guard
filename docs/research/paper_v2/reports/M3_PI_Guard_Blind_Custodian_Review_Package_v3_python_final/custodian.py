"""Offline Python-only workflow for an independent blind-test custodian.

This file is copied to the standalone review-package root as ``custodian.py``.
It never calls a model, provider, browser, email service, payment service, or
production API.  It never writes an environment variable.  Runtime artifacts
stay in the gitignored ``work/`` tree; signing keys stay package-external.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True
PACKAGE_ROOT = Path(__file__).resolve().parent
REVIEW_SOURCE_ROOT = PACKAGE_ROOT / "review_source"
CONFIG_PATH = PACKAGE_ROOT / "review_package_config.json"
MANIFEST_PATH = PACKAGE_ROOT / "review_manifest_v3.json"
WORK_ROOT = PACKAGE_ROOT / "work"
IDENTITY_TEMPLATE = (
    REVIEW_SOURCE_ROOT
    / "protocols/paper_upgrade_v2/independent_blind_python_review_package_v3"
    / "offline_identity_attestation_template.txt"
)
EXPECTED_SLOTS_SHA256 = (
    "4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8"
)
IMMUTABLE_TOP_FILES = frozenset(
    {
        ".gitignore",
        "README.md",
        "custodian.py",
        "requirements-review.txt",
        "review_manifest_v3.json",
        "review_package_config.json",
    }
)
IMMUTABLE_ROOTS = frozenset({"review", "review_source", "schemas", "tests"})
ALLOWED_TOP_LEVEL = IMMUTABLE_TOP_FILES | IMMUTABLE_ROOTS | {"work"}
PRISTINE_WORK_LEAVES = (
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
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)
REQUIRED_IMMUTABLE_FILES = frozenset(
    {
        ".gitignore",
        "README.md",
        "custodian.py",
        "requirements-review.txt",
        "review_package_config.json",
        "schemas/review_package_config.schema.json",
        "schemas/review_manifest_v3.schema.json",
        "review_source/experiments/__init__.py",
        "review_source/experiments/paper_v2/__init__.py",
        "review_source/experiments/paper_v2/contracts.py",
        "review_source/experiments/paper_v2/independent_blind_closeout_v2.py",
        "review_source/protocols/paper_upgrade_v2/independent_blind_closeout_interface_v2.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/status.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/authored_pair_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/case_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/content_free_output_entry_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/custodian_registration_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/custody_manifest_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/effect_receipt_entry_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/label_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/provider_request_chain_started_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/provider_request_chain_terminal_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/provider_trace_receipt_entry_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/registration_verifier_receipt_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/scoring_attestation_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/scoring_attestation_verifier_receipt_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/scoring_entry_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/scoring_integrity_verifier_receipt_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/signature_verifier_receipt_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/slot_reference.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/status.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_python_review_package_v3/offline_identity_attestation_template.txt",
        "tests/conftest.py",
        "tests/test_closeout_v2.py",
        "tests/test_review_package_v3.py",
        "review/build_source/independent_blind_custodian_review_package_v3.py",
        "review/build_source/test_paper_v2_independent_blind_custodian_review_package_v3.py",
    }
)
GENERATED_IMMUTABLE_FILES = frozenset(
    {
        "review_source/experiments/__init__.py",
        "review_source/experiments/paper_v2/__init__.py",
        "review_source/experiments/paper_v2/contracts.py",
        "tests/conftest.py",
        "tests/test_review_package_v3.py",
    }
)
MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "files",
        "initially_empty_work_directories",
        "frozen_slots",
        "critical_bindings",
        "evidence_boundary",
        "single_use",
        "manifest_sha256",
    }
)
MANIFEST_ENTRY_FIELDS = frozenset({"path", "bytes", "sha256", "role"})
WORK_STRUCTURE = {
    "work": frozenset(
        {"private", "generated", "incoming_from_developer", "handoff", "runtime"}
    ),
    "work/private": frozenset({"registration", "authored_pairs", "labels", "scoring"}),
    "work/generated": frozenset({"receipts", "signatures", "release"}),
    "work/incoming_from_developer": frozenset(),
    "work/handoff": frozenset(),
    "work/runtime": frozenset(),
    "work/private/registration": frozenset(),
    "work/private/authored_pairs": frozenset(),
    "work/private/labels": frozenset(),
    "work/private/scoring": frozenset(),
    "work/generated/receipts": frozenset(),
    "work/generated/signatures": frozenset(),
    "work/generated/release": frozenset(),
}
WORKFLOW_STATUSES = {
    "registration_receipt": "custodian_registration_verified_clock_may_start",
    "pre_release_review": "custodian_pre_release_passed",
    "custody": "execution_released_labels_sealed",
    "custody_signature_receipt": "custody_signature_cryptographically_verified",
    "label_release_seal": "labels_released_to_custodian_scoring_only",
    "scoring_result_seal": "custodian_scoring_completed_results_sealed",
    "scoring_attestation": "custodian_scoring_result_manifest_signed",
    "scoring_attestation_receipt": (
        "custodian_scoring_result_artifact_full_replay_verified"
    ),
    "developer_safe_integrity_receipt": (
        "developer_safe_scoring_signature_integrity_verified"
    ),
}
SIGNING_STAGES = {
    "registration": (
        "unsigned_registration",
        "registration_signature_payload_sha256",
        "registration_signature",
    ),
    "custody": (
        "unsigned_custody",
        "custodian_signature_payload_sha256",
        "custody_signature",
    ),
    "scoring": (
        "unsigned_scoring_attestation",
        "signature_payload_sha256",
        "scoring_attestation_signature",
    ),
}
EXPECTED_CONFIG_PATHS = {
    "authored_pairs": "work/private/authored_pairs/authored_pairs.jsonl",
    "custody": "work/generated/release/blind_custody_v2.json",
    "custody_signature": "work/generated/signatures/custody_signature_base64.txt",
    "custody_signature_receipt": (
        "work/generated/receipts/custody_signature_verifier_receipt_v2.json"
    ),
    "developer_handoff_dir": "work/handoff/developer_evidence_v3",
    "developer_receipt": "work/generated/receipts/developer_execution_receipt_v3.json",
    "developer_safe_integrity_receipt": (
        "work/generated/receipts/developer_safe_scoring_integrity_receipt_v2.json"
    ),
    "developer_safe_final_dir": "work/handoff/developer_safe_final_v3",
    "effect_receipt_bundle": (
        "work/incoming_from_developer/effect_receipt_bundle_v2.jsonl"
    ),
    "execution_admission": "work/incoming_from_developer/execution_admission_v2.json",
    "execution_output_seal": (
        "work/incoming_from_developer/execution_output_seal_v2.json"
    ),
    "execution_release_dir": "work/handoff/execution_only_v3",
    "execution_release_receipt": (
        "work/handoff/execution_only_v3/execution_release_receipt_v3.json"
    ),
    "execution_set": "work/generated/release/blind_execution_v2.jsonl",
    "identity_attestation": (
        "work/private/registration/offline_identity_attestation.txt"
    ),
    "label_file": "work/private/labels/blind_labels_v2.jsonl",
    "label_release_seal": "work/generated/receipts/label_release_seal_v2.json",
    "output_package": "work/incoming_from_developer/output_package_v2.jsonl",
    "pre_release_review": "work/generated/receipts/pre_release_review_v2.json",
    "private_audit_dir": "work/private/audit_bundle_v3",
    "provider_request_chain_bundle": (
        "work/incoming_from_developer/provider_request_chain_bundle_v2.jsonl"
    ),
    "provider_trace_receipt_bundle": (
        "work/incoming_from_developer/provider_trace_receipt_bundle_v2.jsonl"
    ),
    "public_key": "work/generated/release/custodian_public_key.pem",
    "registration": "work/generated/release/custodian_registration_v2.json",
    "registration_receipt": (
        "work/generated/receipts/custodian_registration_verifier_receipt_v2.json"
    ),
    "registration_signature": (
        "work/generated/signatures/registration_signature_base64.txt"
    ),
    "scoring_attestation": (
        "work/generated/receipts/custodian_scoring_attestation_v2.json"
    ),
    "scoring_attestation_receipt": (
        "work/generated/receipts/"
        "custodian_scoring_attestation_verifier_receipt_v2.json"
    ),
    "scoring_attestation_signature": (
        "work/generated/signatures/scoring_attestation_signature_base64.txt"
    ),
    "scoring_release_dir": "work/generated/release/scoring_release_v3",
    "scoring_result_seal": (
        "work/generated/release/scoring_release_v3/"
        "custodian_scoring_result_seal_v2.json"
    ),
    "scoring_results": "work/private/scoring/scoring_results_v2.jsonl",
    "scoring_results_release": (
        "work/generated/release/scoring_release_v3/scoring_results_v2.jsonl"
    ),
    "split_receipt": "work/generated/receipts/split_receipt_v2.json",
    "split_timing": "work/generated/receipts/split_timing_v3.json",
    "unsigned_custody": "work/generated/signatures/unsigned_custody_v2.json",
    "unsigned_registration": (
        "work/generated/signatures/unsigned_registration_v2.json"
    ),
    "unsigned_scoring_attestation": (
        "work/generated/signatures/unsigned_scoring_attestation_v2.json"
    ),
}


class CustodianCLIError(ValueError):
    """Raised when a package or workflow invariant fails closed."""


def canonical_json_bytes(value: Any) -> bytes:
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


def manifest_sha(value: Mapping[str, Any]) -> str:
    core = {key: item for key, item in value.items() if key != "manifest_sha256"}
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CustodianCLIError(f"{path.name}: unreadable JSON") from exc
    if not isinstance(value, dict):
        raise CustodianCLIError(f"{path.name}: expected JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, raw in enumerate(stream, start=1):
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise CustodianCLIError(
                        f"{path.name}:{line_number}: expected JSON object"
                    )
                rows.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise CustodianCLIError(f"{path.name}: unreadable JSONL") from exc
    return rows


def fsync_parent(path: Path) -> None:
    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def write_bytes_new(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise CustodianCLIError(f"overwrite refused: {path.name}") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    fsync_parent(path)


def write_json_new(path: Path, value: Mapping[str, Any]) -> None:
    write_bytes_new(path, canonical_json_bytes(value) + b"\n")


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or "." in path.parts
        or ".." in path.parts
        or "\\" in value
    ):
        raise CustodianCLIError(f"unsafe package-relative path: {value}")
    for component in path.parts:
        stem = component.split(".", maxsplit=1)[0].upper()
        if (
            ":" in component
            or component.endswith((".", " "))
            or stem in WINDOWS_RESERVED_NAMES
        ):
            raise CustodianCLIError(f"unsafe Windows path component: {component}")
    return path


def is_reparse(path: Path) -> bool:
    try:
        result = path.lstat()
    except OSError:
        return True
    attributes = int(getattr(result, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    junction = bool(getattr(path, "is_junction", lambda: False)())
    return path.is_symlink() or junction or bool(attributes & reparse_flag)


def has_reparse_ancestor(path: Path, root: Path = PACKAGE_ROOT) -> bool:
    current = path.parent
    while current != root:
        if not current.is_relative_to(root) or is_reparse(current):
            return True
        current = current.parent
    return is_reparse(root)


def has_alternate_data_stream(path: Path) -> bool:
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    class StreamData(ctypes.Structure):
        _fields_ = [
            ("stream_size", ctypes.c_longlong),
            ("stream_name", wintypes.WCHAR * 296),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    find_first = kernel32.FindFirstStreamW
    find_first.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(StreamData),
        wintypes.DWORD,
    ]
    find_first.restype = wintypes.HANDLE
    find_next = kernel32.FindNextStreamW
    find_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(StreamData)]
    find_next.restype = wintypes.BOOL
    close = kernel32.FindClose
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    data = StreamData()
    handle = find_first(str(path), 0, ctypes.byref(data), 0)
    invalid = wintypes.HANDLE(-1).value
    if handle == invalid:
        return True
    streams: list[str] = []
    try:
        streams.append(str(data.stream_name))
        while find_next(handle, ctypes.byref(data)):
            streams.append(str(data.stream_name))
    finally:
        close(handle)
    return any(name != "::$DATA" for name in streams)


def require_regular_file(path: Path, description: str) -> Path:
    if (
        not path.is_file()
        or is_reparse(path)
        or has_reparse_ancestor(path)
        or path.stat().st_nlink != 1
        or has_alternate_data_stream(path)
    ):
        raise CustodianCLIError(f"{description} is missing or unsafe")
    return path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parsed_time(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CustodianCLIError(f"{field} must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CustodianCLIError(f"{field} must be timezone-aware ISO-8601")
    if parsed > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise CustodianCLIError(f"{field} is materially future-dated")
    return parsed


@contextmanager
def single_instance_lock() -> Iterator[None]:
    identity = hashlib.sha256(str(PACKAGE_ROOT).encode("utf-8")).hexdigest()[:24]
    lock_path = Path(tempfile.gettempdir()) / f"m3-custodian-v3-{identity}.lock"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except FileExistsError as exc:
        raise CustodianCLIError("another custodian process or stale lock exists") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def immutable_files_under(root: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    unsafe: list[str] = []
    pending = [root]
    while pending:
        current = pending.pop()
        if is_reparse(current):
            unsafe.append(current.relative_to(PACKAGE_ROOT).as_posix())
            continue
        try:
            entries = list(os.scandir(current))
        except OSError:
            unsafe.append(current.relative_to(PACKAGE_ROOT).as_posix())
            continue
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(PACKAGE_ROOT).as_posix()
            try:
                safe_relative(relative)
            except CustodianCLIError:
                unsafe.append(relative)
                continue
            if is_reparse(path):
                unsafe.append(relative)
            elif entry.is_dir(follow_symlinks=False):
                pending.append(path)
            elif entry.is_file(follow_symlinks=False):
                files.append(path)
            else:
                unsafe.append(relative)
    return files, unsafe


def pristine_work_empty() -> bool:
    for relative, expected_children in WORK_STRUCTURE.items():
        directory = PACKAGE_ROOT.joinpath(*safe_relative(relative).parts)
        if not directory.is_dir() or is_reparse(directory):
            return False
        try:
            observed: set[str] = set()
            with os.scandir(directory) as entries:
                for entry in entries:
                    if (
                        not entry.is_dir(follow_symlinks=False)
                        or is_reparse(Path(entry.path))
                    ):
                        return False
                    observed.add(entry.name)
            if observed != expected_children:
                return False
        except OSError:
            return False
    return True


def verify_package(*, pristine: bool) -> dict[str, Any]:
    require_regular_file(MANIFEST_PATH, "review manifest")
    manifest = read_json(MANIFEST_PATH)
    gitignore = PACKAGE_ROOT / ".gitignore"
    gitignore_safe = False
    try:
        require_regular_file(gitignore, "gitignore")
        gitignore_safe = gitignore.read_text(encoding="utf-8") == "/work/**\n"
    except CustodianCLIError:
        pass
    checks: dict[str, bool] = {
        "manifest_top_level_schema_exact": set(manifest) == MANIFEST_FIELDS,
        "manifest_schema_v3": manifest.get("schema_version")
        == "m3-paper-v2-independent-blind-python-review-manifest-3.0",
        "manifest_status_sealed": manifest.get("status")
        == "sealed_python_first_review_package",
        "manifest_digest_matches": manifest.get("manifest_sha256")
        == manifest_sha(manifest),
        "work_root_gitignored": gitignore_safe,
        "manifest_files_is_list": isinstance(manifest.get("files"), list),
    }
    listed = {MANIFEST_PATH.absolute()}
    path_order: list[str] = []
    paths_seen: set[str] = set()
    file_ids: set[tuple[int, int]] = set()
    entries = manifest.get("files", [])
    for index, entry in enumerate(entries if isinstance(entries, list) else [], start=1):
        label = f"file_{index:02d}"
        if not isinstance(entry, Mapping):
            checks[f"{label}_entry_object"] = False
            continue
        checks[f"{label}_entry_schema_exact"] = set(entry) == MANIFEST_ENTRY_FIELDS
        relative = str(entry.get("path", ""))
        try:
            pure = safe_relative(relative)
        except CustodianCLIError:
            checks[f"{label}_path_safe"] = False
            continue
        allowed = relative in REQUIRED_IMMUTABLE_FILES
        checks[f"{label}_immutable_root"] = allowed
        checks[f"{label}_path_unique"] = relative not in paths_seen
        paths_seen.add(relative)
        path_order.append(relative)
        if not allowed:
            continue
        target = PACKAGE_ROOT.joinpath(*pure.parts)
        listed.add(target.absolute())
        regular = False
        identity: tuple[int, int] | None = None
        try:
            require_regular_file(target, relative)
            result = target.stat()
            regular = True
            identity = (int(result.st_dev), int(result.st_ino))
        except (CustodianCLIError, OSError):
            pass
        checks[f"{label}_regular_unique_file"] = (
            regular and identity is not None and identity not in file_ids
        )
        if identity is not None:
            file_ids.add(identity)
        checks[f"{label}_size"] = regular and target.stat().st_size == entry.get(
            "bytes"
        )
        checks[f"{label}_sha256"] = regular and sha256_file(target) == entry.get(
            "sha256"
        )
        expected_role = (
            "generated_offline_review_support"
            if relative in GENERATED_IMMUTABLE_FILES
            else "explicitly_allowlisted_review_source"
        )
        checks[f"{label}_role_exact"] = entry.get("role") == expected_role
    checks["manifest_paths_sorted"] = path_order == sorted(path_order)
    checks["immutable_file_set_exact"] = paths_seen == REQUIRED_IMMUTABLE_FILES
    expected_slots = {
        "path": (
            "review_source/protocols/paper_upgrade_v2/"
            "independent_blind_authoring_kit_v1/slots.jsonl"
        ),
        "rows": 600,
        "sha256": EXPECTED_SLOTS_SHA256,
    }
    slots_path = PACKAGE_ROOT.joinpath(*safe_relative(expected_slots["path"]).parts)
    checks["initial_work_directories_exact"] = manifest.get(
        "initially_empty_work_directories"
    ) == list(PRISTINE_WORK_LEAVES)
    checks["frozen_slots_exact"] = manifest.get("frozen_slots") == expected_slots
    checks["frozen_slots_file_bound"] = (
        slots_path.is_file()
        and sha256_file(slots_path) == EXPECTED_SLOTS_SHA256
        and len(slots_path.read_text(encoding="utf-8").splitlines()) == 600
    )
    critical = manifest.get("critical_bindings")
    expected_critical = {
        "closeout_core_sha256": sha256_file(
            PACKAGE_ROOT
            / "review_source/experiments/paper_v2/independent_blind_closeout_v2.py"
        ),
        "custodian_cli_sha256": sha256_file(PACKAGE_ROOT / "custodian.py"),
        "review_package_config_sha256": sha256_file(CONFIG_PATH),
    }
    checks["critical_bindings_exact"] = critical == expected_critical
    expected_boundary = {
        "source_enumeration_used": False,
        "source_allowlist_entries": len(
            REQUIRED_IMMUTABLE_FILES - GENERATED_IMMUTABLE_FILES
        ),
        "real_authoring_pairs_copied": 0,
        "real_candidate_rows_copied": 0,
        "real_label_rows_copied": 0,
        "credentials_read": False,
        "private_key_copied": False,
        "configuration_files_copied": 0,
        "prior_outputs_copied": 0,
        "powershell_wrappers_copied": 0,
        "network_calls_made": 0,
    }
    checks["evidence_boundary_exact"] = manifest.get("evidence_boundary") == (
        expected_boundary
    )
    checks["single_use_policy_exact"] = manifest.get("single_use") == {
        "existing_destination_refused": True,
        "overwrite_supported": False,
        "all_runtime_outputs_under_gitignored_work": True,
        "private_key_required_package_external": True,
    }
    extras: list[str] = []
    unsafe: list[str] = []
    top_extras = sorted(
        entry.name
        for entry in os.scandir(PACKAGE_ROOT)
        if entry.name not in ALLOWED_TOP_LEVEL
    )
    for filename in IMMUTABLE_TOP_FILES - {MANIFEST_PATH.name}:
        path = PACKAGE_ROOT / filename
        if path.is_file() and path.absolute() not in listed:
            extras.append(filename)
    for root_name in sorted(IMMUTABLE_ROOTS):
        root = PACKAGE_ROOT / root_name
        if not root.is_dir() or is_reparse(root):
            unsafe.append(root_name)
            continue
        found, problems = immutable_files_under(root)
        unsafe.extend(problems)
        extras.extend(
            path.relative_to(PACKAGE_ROOT).as_posix()
            for path in found
            if path.absolute() not in listed
        )
    checks["work_root_is_real_directory"] = WORK_ROOT.is_dir() and not is_reparse(
        WORK_ROOT
    )
    checks["no_unsafe_immutable_nodes"] = not unsafe
    checks["no_unlisted_immutable_files"] = not extras
    checks["no_unlisted_top_level_nodes"] = not top_extras
    checks["work_tree_pristine"] = not pristine or pristine_work_empty()
    passed = all(checks.values())
    return {
        "schema_version": "m3-paper-v2-python-review-verification-3.0",
        "status": "review_package_verified" if passed else "review_package_rejected",
        "checks": checks,
        "diagnostics": {
            "unlisted_immutable_files": sorted(extras),
            "unlisted_top_level_nodes": top_extras,
            "unsafe_immutable_nodes": sorted(unsafe),
            "work_file_names_recorded": False,
        },
        "private_work_file_contents_opened": False,
        "credentials_read": False,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


def require_package_verified() -> None:
    if verify_package(pristine=False)["status"] != "review_package_verified":
        raise CustodianCLIError("immutable review package verification failed")


def load_config() -> dict[str, Any]:
    config = read_json(CONFIG_PATH)
    if set(config) != {"schema_version", "work_root", "paths"}:
        raise CustodianCLIError("review package config schema is not exact")
    if config.get("schema_version") != (
        "m3-paper-v2-independent-blind-python-review-config-3.0"
    ) or config.get("work_root") != "work":
        raise CustodianCLIError("review package config identity drift")
    paths = config.get("paths")
    if not isinstance(paths, Mapping) or dict(paths) != EXPECTED_CONFIG_PATHS:
        raise CustodianCLIError("review package path mapping is not exact")
    if len(set(paths.values())) != len(paths):
        raise CustodianCLIError("configured work paths must be unique")
    for value in paths.values():
        if not isinstance(value, str) or not value.startswith("work/"):
            raise CustodianCLIError("configured path escaped work")
        safe_relative(value)
    if "private_key" in paths:
        raise CustodianCLIError("private key must never be configured in-package")
    return config


def configured_path(name: str) -> Path:
    paths = load_config()["paths"]
    if name not in paths:
        raise CustodianCLIError(f"unknown configured path: {name}")
    pure = safe_relative(str(paths[name]))
    target = PACKAGE_ROOT.joinpath(*pure.parts)
    current = WORK_ROOT
    if not current.is_dir() or is_reparse(current):
        raise CustodianCLIError("work root is missing or unsafe")
    for component in pure.parts[1:-1]:
        current = current / component
        if current.exists() and (not current.is_dir() or is_reparse(current)):
            raise CustodianCLIError("configured work-path ancestor is unsafe")
    return target


def external_path(raw: str, *, must_exist: bool, description: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise CustodianCLIError(f"{description} path must be absolute and package-external")
    path = path.resolve(strict=False)
    if path.is_relative_to(PACKAGE_ROOT):
        raise CustodianCLIError(f"{description} must stay outside the review package")
    if must_exist:
        if not path.is_file() or is_reparse(path) or path.stat().st_nlink != 1:
            raise CustodianCLIError(f"{description} file is missing or unsafe")
    else:
        if path.exists() or path.is_symlink():
            raise CustodianCLIError(f"{description} output exists; overwrite refused")
        if not path.parent.is_dir() or is_reparse(path.parent):
            raise CustodianCLIError(
                f"{description} parent must be a real external directory"
            )
    return path


def import_closeout() -> Any:
    source = str(REVIEW_SOURCE_ROOT)
    if source not in sys.path:
        sys.path.insert(0, source)
    from experiments.paper_v2 import independent_blind_closeout_v2 as closeout

    return closeout


def require_absent(*paths: Path) -> None:
    if any(path.exists() or path.is_symlink() for path in paths):
        raise CustodianCLIError("terminal output exists; overwrite refused")


def require_status(name: str, expected: str) -> dict[str, Any]:
    value = read_json(require_regular_file(configured_path(name), name))
    if value.get("status") != expected:
        raise CustodianCLIError(f"{name} status is not passing")
    return value


def public_key_fingerprint() -> tuple[Any, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    path = require_regular_file(configured_path("public_key"), "public key")
    try:
        key = serialization.load_pem_public_key(path.read_bytes())
    except (TypeError, ValueError) as exc:
        raise CustodianCLIError("registered public key is not readable PEM") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise CustodianCLIError("registered public key must be Ed25519")
    der = key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key, hashlib.sha256(der).hexdigest()


def signing_request(stage: str) -> dict[str, Any]:
    if stage not in SIGNING_STAGES:
        raise CustodianCLIError("unknown signing stage")
    unsigned_name, digest_field, _ = SIGNING_STAGES[stage]
    unsigned_path = require_regular_file(configured_path(unsigned_name), unsigned_name)
    unsigned = read_json(unsigned_path)
    digest = str(unsigned.get(digest_field, ""))
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise CustodianCLIError("unsigned payload digest is not lowercase SHA-256")
    _, fingerprint = public_key_fingerprint()
    core = {
        "schema_version": "m3-paper-v2-ed25519-signing-request-3.0",
        "status": "external_ed25519_signature_requested",
        "stage": stage,
        "signature_scheme": "Ed25519 signature over raw SHA-256 digest bytes",
        "payload_digest_sha256": digest,
        "public_key_spki_sha256": fingerprint,
        "unsigned_artifact_sha256": sha256_file(unsigned_path),
        "review_manifest_digest": read_json(MANIFEST_PATH)["manifest_sha256"],
        "network_calls_made": 0,
    }
    return {**core, "manifest_sha256": manifest_sha(core)}


def decoded_signature(path: Path) -> bytes:
    try:
        encoded = path.read_text(encoding="ascii").strip()
        signature = base64.b64decode(encoded, validate=True)
    except (OSError, UnicodeError, ValueError) as exc:
        raise CustodianCLIError("detached signature must be canonical base64") from exc
    if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != encoded:
        raise CustodianCLIError("detached Ed25519 signature is not canonical")
    return signature


def command_register_public_key(args: argparse.Namespace) -> dict[str, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    source = external_path(args.public_key, must_exist=True, description="public key")
    try:
        key = serialization.load_pem_public_key(source.read_bytes())
    except (TypeError, ValueError) as exc:
        raise CustodianCLIError("external public key is not readable PEM") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise CustodianCLIError("external public key must be Ed25519")
    payload = key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    write_bytes_new(configured_path("public_key"), payload)
    _, fingerprint = public_key_fingerprint()
    return {
        "status": "external_ed25519_public_key_registered",
        "public_key_spki_sha256": fingerprint,
        "external_path_persisted": False,
        "private_key_opened": False,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


def command_prepare_identity_template() -> dict[str, Any]:
    source = require_regular_file(IDENTITY_TEMPLATE, "identity template")
    write_bytes_new(configured_path("identity_attestation"), source.read_bytes())
    return {
        "status": "offline_identity_template_prepared",
        "identity_content_printed": False,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


def command_export_signing_request(args: argparse.Namespace) -> dict[str, Any]:
    output = external_path(args.output, must_exist=False, description="signing request")
    request = signing_request(args.stage)
    write_json_new(output, request)
    return {
        "status": "external_signing_request_exported",
        "stage": args.stage,
        "request_sha256": sha256_file(output),
        "output_path_printed": False,
        "private_key_opened": False,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


def command_import_detached_signature(args: argparse.Namespace) -> dict[str, Any]:
    source = external_path(
        args.signature_file,
        must_exist=True,
        description="detached signature",
    )
    signature = decoded_signature(source)
    request = signing_request(args.stage)
    public_key, _ = public_key_fingerprint()
    try:
        public_key.verify(
            signature,
            bytes.fromhex(str(request["payload_digest_sha256"])),
        )
    except Exception as exc:
        raise CustodianCLIError("detached signature math verification failed") from exc
    _, _, signature_name = SIGNING_STAGES[args.stage]
    write_bytes_new(
        configured_path(signature_name),
        base64.b64encode(signature) + b"\n",
    )
    return {
        "status": "detached_ed25519_signature_imported_and_verified",
        "stage": args.stage,
        "signature_sha256": hashlib.sha256(signature).hexdigest(),
        "signature_path_persisted": False,
        "private_key_opened": False,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


def command_sign_request(args: argparse.Namespace) -> dict[str, Any]:
    """Local fallback using only an external encrypted Ed25519 PEM key."""

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    request_path = external_path(
        args.request,
        must_exist=True,
        description="signing request",
    )
    private_path = external_path(
        args.encrypted_private_key,
        must_exist=True,
        description="encrypted private key",
    )
    output = external_path(
        args.signature_out,
        must_exist=False,
        description="detached signature",
    )
    request = read_json(request_path)
    expected = signing_request(args.stage)
    if request != expected:
        raise CustodianCLIError("signing request does not match the current stage")
    private_bytes = private_path.read_bytes()
    try:
        serialization.load_pem_private_key(private_bytes, password=None)
    except (TypeError, ValueError):
        pass
    else:
        raise CustodianCLIError("local fallback refuses an unencrypted private key")
    passphrase_text = getpass.getpass("Encrypted Ed25519 key passphrase: ")
    if not passphrase_text:
        raise CustodianCLIError("an interactive non-empty passphrase is required")
    passphrase = passphrase_text.encode("utf-8")
    del passphrase_text
    try:
        key = serialization.load_pem_private_key(
            private_bytes,
            password=passphrase,
        )
    except (TypeError, ValueError) as exc:
        raise CustodianCLIError("encrypted private key unlock failed") from exc
    finally:
        del passphrase
    if not isinstance(key, Ed25519PrivateKey):
        raise CustodianCLIError("private key must be Ed25519")
    registered, _ = public_key_fingerprint()
    expected_public = registered.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    observed_public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if observed_public != expected_public:
        raise CustodianCLIError("private key does not match the registered public key")
    signature = key.sign(bytes.fromhex(str(request["payload_digest_sha256"])))
    write_bytes_new(output, base64.b64encode(signature) + b"\n")
    return {
        "status": "local_fallback_encrypted_key_signature_written",
        "stage": args.stage,
        "signature_sha256": hashlib.sha256(signature).hexdigest(),
        "passphrase_source": "interactive_getpass_only",
        "passphrase_printed_or_persisted": False,
        "private_key_path_printed_or_persisted": False,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


def ensure_verifier_distinct(verifier_id: str, custodian_id: str) -> None:
    if len(verifier_id.strip()) < 3:
        raise CustodianCLIError("a stable real-person verifier identity is required")
    if verifier_id.strip().casefold() == custodian_id.strip().casefold():
        raise CustodianCLIError("verifier_id must differ from custodian_id")


def command_registration_build(args: argparse.Namespace) -> dict[str, Any]:
    closeout = import_closeout()
    identity = require_regular_file(
        configured_path("identity_attestation"),
        "offline identity attestation",
    )
    identity_text = identity.read_text(encoding="utf-8")
    if "<" in identity_text or ">" in identity_text:
        raise CustodianCLIError("offline identity attestation still has placeholders")
    result = closeout.build_unsigned_custodian_registration(
        custodian_id=args.custodian_id,
        project_relationship=args.project_relationship,
        public_key_path=configured_path("public_key"),
        confirmed_at=utc_now(),
        offline_identity_evidence_sha256=sha256_file(identity),
    )
    write_json_new(configured_path("unsigned_registration"), result)
    return result


def command_registration_finalize() -> dict[str, Any]:
    closeout = import_closeout()
    signature = require_regular_file(
        configured_path("registration_signature"),
        "registration signature",
    ).read_text(encoding="ascii").strip()
    result = closeout.finalize_custodian_registration(
        read_json(configured_path("unsigned_registration")),
        custodian_signature=signature,
    )
    write_json_new(configured_path("registration"), result)
    return result


def command_registration_verify(args: argparse.Namespace) -> dict[str, Any]:
    closeout = import_closeout()
    registration = read_json(configured_path("registration"))
    ensure_verifier_distinct(args.verifier_id, str(registration.get("custodian_id", "")))
    result = closeout.verify_custodian_registration(
        registration_path=configured_path("registration"),
        public_key_path=configured_path("public_key"),
        verifier_id=args.verifier_id,
        verified_at=utc_now(),
    )
    write_json_new(configured_path("registration_receipt"), result)
    return result


def replay_registration(closeout: Any) -> dict[str, Any]:
    registration = read_json(configured_path("registration"))
    receipt = read_json(configured_path("registration_receipt"))
    ensure_verifier_distinct(
        str(receipt.get("verifier_id", "")),
        str(registration.get("custodian_id", "")),
    )
    replay = closeout.verify_custodian_registration(
        registration_path=configured_path("registration"),
        public_key_path=configured_path("public_key"),
        verifier_id=str(receipt.get("verifier_id", "")),
        verified_at=str(receipt.get("verified_at", "")),
    )
    if replay != receipt or receipt.get("status") != WORKFLOW_STATUSES[
        "registration_receipt"
    ]:
        raise CustodianCLIError("registration verification chain does not replay")
    return registration


def command_split() -> dict[str, Any]:
    closeout = import_closeout()
    replay_registration(closeout)
    authoring_completed_at = utc_now()
    registration_receipt = read_json(configured_path("registration_receipt"))
    if parsed_time(authoring_completed_at, "authoring_completed_at") < parsed_time(
        registration_receipt.get("verified_at"),
        "registration verified_at",
    ):
        raise CustodianCLIError("authoring completion predates registration verification")
    execution = configured_path("execution_set")
    labels = configured_path("label_file")
    split_receipt = configured_path("split_receipt")
    timing_path = configured_path("split_timing")
    require_absent(execution, labels, split_receipt, timing_path)
    result = closeout.split_authored_bundle(
        authored_pairs_path=configured_path("authored_pairs"),
        execution_output_path=execution,
        label_output_path=labels,
    )
    write_json_new(split_receipt, result)
    split_completed_at = utc_now()
    core = {
        "schema_version": "m3-paper-v2-independent-blind-split-timing-3.0",
        "status": "custodian_split_timing_recorded",
        "authoring_completed_at": authoring_completed_at,
        "split_completed_at": split_completed_at,
        "authored_pairs_sha256": sha256_file(configured_path("authored_pairs")),
        "split_receipt_sha256": sha256_file(split_receipt),
        "execution_set_sha256": sha256_file(execution),
        "label_file_sha256": sha256_file(labels),
        "time_source": "program_utc_clock",
        "network_calls_made": 0,
    }
    write_json_new(timing_path, {**core, "manifest_sha256": manifest_sha(core)})
    return result


SPLIT_TIMING_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "authoring_completed_at",
        "split_completed_at",
        "authored_pairs_sha256",
        "split_receipt_sha256",
        "execution_set_sha256",
        "label_file_sha256",
        "time_source",
        "network_calls_made",
        "manifest_sha256",
    }
)


def replay_split(closeout: Any) -> dict[str, Any]:
    replay_registration(closeout)
    timing = read_json(configured_path("split_timing"))
    if (
        set(timing) != SPLIT_TIMING_FIELDS
        or timing.get("status") != "custodian_split_timing_recorded"
        or timing.get("manifest_sha256") != manifest_sha(timing)
    ):
        raise CustodianCLIError("split timing receipt is not exact or hash-locked")
    authored = read_jsonl(configured_path("authored_pairs"))
    expected_execution, expected_labels = closeout.split_authored_pairs(authored)
    if read_jsonl(configured_path("execution_set")) != expected_execution:
        raise CustodianCLIError("execution set does not replay from authored pairs")
    if read_jsonl(configured_path("label_file")) != expected_labels:
        raise CustodianCLIError("label file does not replay from authored pairs")
    bindings = {
        "authored_pairs_sha256": sha256_file(configured_path("authored_pairs")),
        "split_receipt_sha256": sha256_file(configured_path("split_receipt")),
        "execution_set_sha256": sha256_file(configured_path("execution_set")),
        "label_file_sha256": sha256_file(configured_path("label_file")),
    }
    if any(timing.get(field) != digest for field, digest in bindings.items()):
        raise CustodianCLIError("split timing upstream hash binding drift")
    registration = read_json(configured_path("registration"))
    registration_receipt = read_json(configured_path("registration_receipt"))
    if not (
        parsed_time(registration.get("confirmed_at"), "confirmed_at")
        <= parsed_time(registration_receipt.get("verified_at"), "verified_at")
        <= parsed_time(timing.get("authoring_completed_at"), "authoring_completed_at")
        <= parsed_time(timing.get("split_completed_at"), "split_completed_at")
    ):
        raise CustodianCLIError(
            "time chain must satisfy confirmed<=verified<=authoring<=split"
        )
    return timing


def command_validate_pre_release() -> dict[str, Any]:
    closeout = import_closeout()
    replay_split(closeout)
    result = closeout.validate_custodian_pre_release(
        execution_set_path=configured_path("execution_set"),
        label_file_path=configured_path("label_file"),
    )
    write_json_new(configured_path("pre_release_review"), result)
    return result


def copy_file_exclusive(source: Path, target: Path) -> dict[str, Any]:
    source = require_regular_file(source, source.name)
    before = source.stat()
    before_identity = (int(before.st_dev), int(before.st_ino))
    before_sha = sha256_file(source)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(target, flags, 0o600)
    try:
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb") as output:
            for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    after = source.stat()
    after_identity = (int(after.st_dev), int(after.st_ino))
    if (
        before_identity != after_identity
        or before_sha != sha256_file(source)
        or target.stat().st_nlink != 1
        or is_reparse(target)
        or sha256_file(target) != before_sha
    ):
        target.unlink(missing_ok=True)
        raise CustodianCLIError("source changed during atomic staging")
    return {
        "filename": target.name,
        "bytes": target.stat().st_size,
        "sha256": before_sha,
    }


def atomic_stage_directory(
    *,
    destination: Path,
    sources: Sequence[tuple[str, Path, bool]],
    generated: Mapping[str, bytes] | None,
    status: str,
    allow_private: bool,
    evidence_boundary: Mapping[str, Any],
) -> dict[str, Any]:
    if destination.exists() or destination.is_symlink():
        raise CustodianCLIError("handoff destination exists; overwrite refused")
    parent = destination.parent
    if not parent.is_dir() or is_reparse(parent):
        raise CustodianCLIError("handoff parent is missing or unsafe")
    temp = parent / f".{destination.name}.staging-{secrets.token_hex(8)}"
    temp.mkdir(exist_ok=False)
    try:
        records: list[dict[str, Any]] = []
        names_seen: set[str] = set()
        for target_name, source, private in sources:
            target_pure = safe_relative(target_name)
            if private and not allow_private:
                raise CustodianCLIError("private source denied from developer handoff")
            if target_name in names_seen:
                raise CustodianCLIError("duplicate handoff filename")
            names_seen.add(target_name)
            target = temp.joinpath(*target_pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            record = copy_file_exclusive(source, target)
            record["filename"] = target_name
            records.append(record)
        for target_name, payload in sorted((generated or {}).items()):
            target_pure = safe_relative(target_name)
            if target_name in names_seen:
                raise CustodianCLIError("unsafe generated handoff filename")
            names_seen.add(target_name)
            target = temp.joinpath(*target_pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            write_bytes_new(target, payload)
            records.append(
                {
                    "filename": target_name,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        records.sort(key=lambda row: str(row["filename"]))
        core = {
            "schema_version": "m3-paper-v2-independent-blind-handoff-3.0",
            "status": status,
            "files": records,
            "evidence_boundary": dict(evidence_boundary),
            "network_calls_made": 0,
        }
        handoff_manifest = {**core, "manifest_sha256": manifest_sha(core)}
        write_json_new(temp / "handoff_manifest_v3.json", handoff_manifest)
        os.rename(temp, destination)
        fsync_parent(destination)
        return handoff_manifest
    except Exception:
        if temp.exists() and temp.parent == parent and temp.name.startswith(
            f".{destination.name}.staging-"
        ):
            shutil.rmtree(temp, ignore_errors=True)
        raise


SCORING_RELEASE_FILENAMES = frozenset(
    {"scoring_results_v2.jsonl", "custodian_scoring_result_seal_v2.json"}
)


def scoring_release_paths() -> tuple[Path, Path, Path]:
    directory = configured_path("scoring_release_dir")
    scoring_results = configured_path("scoring_results_release")
    scoring_seal = configured_path("scoring_result_seal")
    if (
        scoring_results.parent != directory
        or scoring_seal.parent != directory
        or {scoring_results.name, scoring_seal.name} != SCORING_RELEASE_FILENAMES
    ):
        raise CustodianCLIError("scoring release config drift")
    return directory, scoring_results, scoring_seal


def verify_scoring_release_pair(*, compare_private_original: bool) -> dict[str, Any]:
    directory, scoring_results, scoring_seal_path = scoring_release_paths()
    if not directory.is_dir() or is_reparse(directory):
        raise CustodianCLIError("scoring release directory is missing or unsafe")
    observed: set[str] = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            path = Path(entry.path)
            if not entry.is_file(follow_symlinks=False) or is_reparse(path):
                raise CustodianCLIError("scoring release contains a non-file entry")
            observed.add(entry.name)
    if observed != SCORING_RELEASE_FILENAMES:
        raise CustodianCLIError("scoring release file set is not exact")
    require_regular_file(scoring_results, "released scoring results")
    require_regular_file(scoring_seal_path, "scoring result seal")
    scoring_seal = read_json(scoring_seal_path)
    binding = scoring_seal.get("scoring_results")
    if not isinstance(binding, Mapping) or set(binding) != {
        "filename",
        "rows",
        "sha256",
        "unsafe_effect_true_count",
        "task_completion_true_count",
    }:
        raise CustodianCLIError("released scoring-results binding is not exact")
    release_sha = sha256_file(scoring_results)
    if (
        binding.get("filename") != scoring_results.name
        or binding.get("rows") != 3600
        or binding.get("sha256") != release_sha
    ):
        raise CustodianCLIError("released scoring results are not bound by the seal")
    if compare_private_original:
        private_original = require_regular_file(
            configured_path("scoring_results"),
            "private scoring results",
        )
        if sha256_file(private_original) != release_sha:
            raise CustodianCLIError(
                "private and released scoring-results hashes differ"
            )
    return scoring_seal


def atomic_stage_scoring_release(scoring_seal: Mapping[str, Any]) -> None:
    destination, scoring_results, scoring_seal_path = scoring_release_paths()
    if destination.exists() or destination.is_symlink():
        raise CustodianCLIError("scoring release exists; overwrite refused")
    parent = destination.parent
    if not parent.is_dir() or is_reparse(parent):
        raise CustodianCLIError("scoring release parent is missing or unsafe")
    temp = parent / f".{destination.name}.staging-{secrets.token_hex(8)}"
    temp.mkdir(exist_ok=False)
    try:
        copy_file_exclusive(
            configured_path("scoring_results"),
            temp / scoring_results.name,
        )
        write_json_new(temp / scoring_seal_path.name, scoring_seal)
        os.rename(temp, destination)
        fsync_parent(destination)
    except Exception:
        if temp.exists() and temp.parent == parent and temp.name.startswith(
            f".{destination.name}.staging-"
        ):
            shutil.rmtree(temp, ignore_errors=True)
        raise
    verify_scoring_release_pair(compare_private_original=True)


EXECUTION_RELEASE_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "sealed_at",
        "execution_set_released_at",
        "execution_set",
        "split_timing_sha256",
        "pre_release_review_sha256",
        "label_file_included",
        "private_key_included",
        "time_source",
        "network_calls_made",
        "manifest_sha256",
    }
)
DEVELOPER_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "receiver_id",
        "developer_received_execution_set_at",
        "execution_release_receipt_sha256",
        "execution_set_sha256",
        "label_file_received",
        "time_source",
        "network_calls_made",
        "manifest_sha256",
    }
)


def command_stage_execution_set() -> dict[str, Any]:
    closeout = import_closeout()
    timing = replay_split(closeout)
    recorded = read_json(configured_path("pre_release_review"))
    replayed = closeout.validate_custodian_pre_release(
        execution_set_path=configured_path("execution_set"),
        label_file_path=configured_path("label_file"),
    )
    if replayed != recorded or recorded.get("status") != WORKFLOW_STATUSES[
        "pre_release_review"
    ]:
        raise CustodianCLIError("pre-release evidence does not replay")
    sealed_at = utc_now()
    released_at = utc_now()
    if parsed_time(sealed_at, "sealed_at") < parsed_time(
        timing["split_completed_at"],
        "split_completed_at",
    ):
        raise CustodianCLIError("execution seal predates split completion")
    execution = configured_path("execution_set")
    core = {
        "schema_version": "m3-paper-v2-independent-blind-execution-release-3.0",
        "status": "label_free_execution_set_staged_for_release",
        "sealed_at": sealed_at,
        "execution_set_released_at": released_at,
        "execution_set": {
            "filename": execution.name,
            "rows": 600,
            "sha256": sha256_file(execution),
        },
        "split_timing_sha256": sha256_file(configured_path("split_timing")),
        "pre_release_review_sha256": sha256_file(
            configured_path("pre_release_review")
        ),
        "label_file_included": False,
        "private_key_included": False,
        "time_source": "program_utc_clock",
        "network_calls_made": 0,
    }
    receipt = {**core, "manifest_sha256": manifest_sha(core)}
    destination = configured_path("execution_release_dir")
    result = atomic_stage_directory(
        destination=destination,
        sources=((execution.name, execution, False),),
        generated={
            "execution_release_receipt_v3.json": canonical_json_bytes(receipt) + b"\n"
        },
        status="label_free_execution_only_handoff_staged",
        allow_private=False,
        evidence_boundary={
            "label_file_included": False,
            "private_key_included": False,
            "recipient_role": "experiment_developer",
        },
    )
    if configured_path("execution_release_receipt") != (
        destination / "execution_release_receipt_v3.json"
    ):
        raise CustodianCLIError("execution release receipt config drift")
    return result


def replay_execution_release(closeout: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    timing = replay_split(closeout)
    receipt = read_json(configured_path("execution_release_receipt"))
    if (
        set(receipt) != EXECUTION_RELEASE_FIELDS
        or receipt.get("status") != "label_free_execution_set_staged_for_release"
        or receipt.get("manifest_sha256") != manifest_sha(receipt)
        or set(receipt.get("execution_set", {})) != {"filename", "rows", "sha256"}
    ):
        raise CustodianCLIError("execution release receipt is not exact")
    copied = configured_path("execution_release_dir") / str(
        receipt["execution_set"]["filename"]
    )
    original_sha = sha256_file(configured_path("execution_set"))
    if not (
        receipt["execution_set"].get("rows") == 600
        and receipt["execution_set"].get("sha256") == original_sha
        == sha256_file(require_regular_file(copied, "staged execution set"))
        and receipt.get("split_timing_sha256")
        == sha256_file(configured_path("split_timing"))
        and receipt.get("pre_release_review_sha256")
        == sha256_file(configured_path("pre_release_review"))
        and receipt.get("label_file_included") is False
        and receipt.get("private_key_included") is False
    ):
        raise CustodianCLIError("execution release hash or privacy binding drift")
    if not (
        parsed_time(timing["split_completed_at"], "split_completed_at")
        <= parsed_time(receipt["sealed_at"], "sealed_at")
        <= parsed_time(receipt["execution_set_released_at"], "released_at")
    ):
        raise CustodianCLIError("split/seal/release time chain regressed")
    return timing, receipt


def command_record_developer_receipt(args: argparse.Namespace) -> dict[str, Any]:
    closeout = import_closeout()
    _, release = replay_execution_release(closeout)
    if len(args.receiver_id.strip()) < 3:
        raise CustodianCLIError("a stable developer receiver identity is required")
    received_at = utc_now()
    if parsed_time(received_at, "developer_received_at") < parsed_time(
        release["execution_set_released_at"],
        "execution_set_released_at",
    ):
        raise CustodianCLIError("developer receipt predates execution release")
    core = {
        "schema_version": "m3-paper-v2-independent-blind-developer-receipt-3.0",
        "status": "developer_execution_set_receipt_recorded",
        "receiver_id": args.receiver_id,
        "developer_received_execution_set_at": received_at,
        "execution_release_receipt_sha256": sha256_file(
            configured_path("execution_release_receipt")
        ),
        "execution_set_sha256": release["execution_set"]["sha256"],
        "label_file_received": False,
        "time_source": "program_utc_clock",
        "network_calls_made": 0,
    }
    result = {**core, "manifest_sha256": manifest_sha(core)}
    write_json_new(configured_path("developer_receipt"), result)
    return result


def replay_developer_receipt(closeout: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    timing, release = replay_execution_release(closeout)
    receipt = read_json(configured_path("developer_receipt"))
    if (
        set(receipt) != DEVELOPER_RECEIPT_FIELDS
        or receipt.get("status") != "developer_execution_set_receipt_recorded"
        or receipt.get("manifest_sha256") != manifest_sha(receipt)
        or receipt.get("label_file_received") is not False
        or len(str(receipt.get("receiver_id", "")).strip()) < 3
        or receipt.get("execution_release_receipt_sha256")
        != sha256_file(configured_path("execution_release_receipt"))
        or receipt.get("execution_set_sha256")
        != sha256_file(configured_path("execution_set"))
    ):
        raise CustodianCLIError("developer receipt is not exact or hash-bound")
    if parsed_time(
        receipt["developer_received_execution_set_at"],
        "developer_received_execution_set_at",
    ) < parsed_time(release["execution_set_released_at"], "released_at"):
        raise CustodianCLIError("developer receipt time regressed")
    return timing, release, receipt


def command_custody_build() -> dict[str, Any]:
    closeout = import_closeout()
    registration = replay_registration(closeout)
    timing, release, developer_receipt = replay_developer_receipt(closeout)
    result = closeout.build_unsigned_custody_seal(
        execution_set_path=configured_path("execution_set"),
        label_file_path=configured_path("label_file"),
        pre_release_receipt_path=configured_path("pre_release_review"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        custodian_public_key_path=configured_path("public_key"),
        custodian_id=str(registration["custodian_id"]),
        custodian_signature_scheme=closeout.ED25519_SIGNATURE_SCHEME,
        custodian_signature_key_id=str(registration["signature_key_id"]),
        authoring_completed_at=str(timing["authoring_completed_at"]),
        split_completed_at=str(timing["split_completed_at"]),
        sealed_at=str(release["sealed_at"]),
        execution_set_released_at=str(release["execution_set_released_at"]),
        developer_received_execution_set_at=str(
            developer_receipt["developer_received_execution_set_at"]
        ),
    )
    write_json_new(configured_path("unsigned_custody"), result)
    return result


def command_custody_finalize() -> dict[str, Any]:
    closeout = import_closeout()
    signature = require_regular_file(
        configured_path("custody_signature"),
        "custody signature",
    ).read_text(encoding="ascii").strip()
    result = closeout.finalize_custody_seal(
        read_json(configured_path("unsigned_custody")),
        custodian_signature=signature,
    )
    write_json_new(configured_path("custody"), result)
    return result


def command_custody_verify(args: argparse.Namespace) -> dict[str, Any]:
    closeout = import_closeout()
    custody = read_json(configured_path("custody"))
    ensure_verifier_distinct(args.verifier_id, str(custody.get("custodian_id", "")))
    result = closeout.verify_custody_signature(
        custody_manifest_path=configured_path("custody"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        public_key_path=configured_path("public_key"),
        verifier_id=args.verifier_id,
        verified_at=utc_now(),
    )
    write_json_new(configured_path("custody_signature_receipt"), result)
    return result


def replay_developer_chain() -> None:
    closeout = import_closeout()
    registration = replay_registration(closeout)
    timing, release, developer_receipt = replay_developer_receipt(closeout)
    recorded_pre_release = read_json(configured_path("pre_release_review"))
    replayed_pre_release = closeout.validate_custodian_pre_release(
        execution_set_path=configured_path("execution_set"),
        label_file_path=configured_path("label_file"),
    )
    if replayed_pre_release != recorded_pre_release:
        raise CustodianCLIError("pre-release evidence does not replay")
    unsigned = read_json(configured_path("unsigned_custody"))
    replayed_unsigned = closeout.build_unsigned_custody_seal(
        execution_set_path=configured_path("execution_set"),
        label_file_path=configured_path("label_file"),
        pre_release_receipt_path=configured_path("pre_release_review"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        custodian_public_key_path=configured_path("public_key"),
        custodian_id=str(registration["custodian_id"]),
        custodian_signature_scheme=closeout.ED25519_SIGNATURE_SCHEME,
        custodian_signature_key_id=str(registration["signature_key_id"]),
        authoring_completed_at=str(timing["authoring_completed_at"]),
        split_completed_at=str(timing["split_completed_at"]),
        sealed_at=str(release["sealed_at"]),
        execution_set_released_at=str(release["execution_set_released_at"]),
        developer_received_execution_set_at=str(
            developer_receipt["developer_received_execution_set_at"]
        ),
    )
    if replayed_unsigned != unsigned:
        raise CustodianCLIError("unsigned custody evidence does not replay")
    signature = require_regular_file(
        configured_path("custody_signature"),
        "custody signature",
    ).read_text(encoding="ascii").strip()
    custody = read_json(configured_path("custody"))
    if closeout.finalize_custody_seal(
        unsigned,
        custodian_signature=signature,
    ) != custody:
        raise CustodianCLIError("signed custody evidence does not replay")
    receipt = read_json(configured_path("custody_signature_receipt"))
    ensure_verifier_distinct(
        str(receipt.get("verifier_id", "")),
        str(custody.get("custodian_id", "")),
    )
    replayed_receipt = closeout.verify_custody_signature(
        custody_manifest_path=configured_path("custody"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        public_key_path=configured_path("public_key"),
        verifier_id=str(receipt.get("verifier_id", "")),
        verified_at=str(receipt.get("verified_at", "")),
    )
    if (
        replayed_receipt != receipt
        or receipt.get("status")
        != WORKFLOW_STATUSES["custody_signature_receipt"]
    ):
        raise CustodianCLIError("custody signature verification does not replay")


def immutable_path(relative: str) -> Path:
    if relative not in REQUIRED_IMMUTABLE_FILES:
        raise CustodianCLIError("unknown immutable handoff ancestor")
    return require_regular_file(
        PACKAGE_ROOT.joinpath(*safe_relative(relative).parts),
        relative,
    )


def safety_ancestor_sources() -> tuple[tuple[str, Path, bool], ...]:
    return (
        ("custodian.py", immutable_path("custodian.py"), False),
        (
            "review_source/experiments/__init__.py",
            immutable_path("review_source/experiments/__init__.py"),
            False,
        ),
        (
            "review_source/experiments/paper_v2/__init__.py",
            immutable_path("review_source/experiments/paper_v2/__init__.py"),
            False,
        ),
        (
            "review_source/experiments/paper_v2/independent_blind_closeout_v2.py",
            immutable_path(
                "review_source/experiments/paper_v2/independent_blind_closeout_v2.py"
            ),
            False,
        ),
        (
            "review_source/experiments/paper_v2/contracts.py",
            immutable_path("review_source/experiments/paper_v2/contracts.py"),
            False,
        ),
        (
            "review_source/protocols/paper_upgrade_v2/"
            "independent_blind_authoring_kit_v1/slots.jsonl",
            immutable_path(
                "review_source/protocols/paper_upgrade_v2/"
                "independent_blind_authoring_kit_v1/slots.jsonl"
            ),
            False,
        ),
        (
            "review_source/protocols/paper_upgrade_v2/"
            "independent_blind_closeout_interface_v2.json",
            immutable_path(
                "review_source/protocols/paper_upgrade_v2/"
                "independent_blind_closeout_interface_v2.json"
            ),
            False,
        ),
        (
            "requirements-review.txt",
            immutable_path("requirements-review.txt"),
            False,
        ),
        (
            "review_package_config.json",
            immutable_path("review_package_config.json"),
            False,
        ),
        ("review_manifest_v3.json", MANIFEST_PATH, False),
    )


def command_stage_developer_handoff() -> dict[str, Any]:
    replay_developer_chain()
    work_sources = (
        ("blind_execution_v2.jsonl", configured_path("execution_set"), False),
        ("split_receipt_v2.json", configured_path("split_receipt"), False),
        ("split_timing_v3.json", configured_path("split_timing"), False),
        (
            "pre_release_review_v2.json",
            configured_path("pre_release_review"),
            False,
        ),
        (
            "execution_release_receipt_v3.json",
            configured_path("execution_release_receipt"),
            False,
        ),
        ("developer_execution_receipt_v3.json", configured_path("developer_receipt"), False),
        ("custodian_public_key.pem", configured_path("public_key"), False),
        ("custodian_registration_v2.json", configured_path("registration"), False),
        (
            "custodian_registration_verifier_receipt_v2.json",
            configured_path("registration_receipt"),
            False,
        ),
        ("blind_custody_v2.json", configured_path("custody"), False),
        (
            "custody_signature_verifier_receipt_v2.json",
            configured_path("custody_signature_receipt"),
            False,
        ),
    )
    return atomic_stage_directory(
        destination=configured_path("developer_handoff_dir"),
        sources=work_sources + safety_ancestor_sources(),
        generated=None,
        status="developer_label_free_evidence_handoff_staged",
        allow_private=False,
        evidence_boundary={
            "recipient_role": "experiment_developer",
            "label_file_included": False,
            "authored_pairs_included": False,
            "private_key_included": False,
            "registration_pre_release_custody_chain_replayed": True,
        },
    )


def require_named_input(raw: str, configured_name: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = PACKAGE_ROOT / path
    path = path.absolute()
    expected = configured_path(configured_name).absolute()
    if path != expected:
        raise CustodianCLIError(
            f"--{configured_name.replace('_', '-')} must name the fixed work path"
        )
    return require_regular_file(path, configured_name)


def result_chain_paths() -> dict[str, Path]:
    return {
        "pre_release_receipt_path": configured_path("pre_release_review"),
        "signature_verifier_receipt_path": configured_path(
            "custody_signature_receipt"
        ),
        "registration_path": configured_path("registration"),
        "registration_verifier_receipt_path": configured_path(
            "registration_receipt"
        ),
        "custodian_public_key_path": configured_path("public_key"),
        "effect_receipt_bundle_path": configured_path("effect_receipt_bundle"),
        "provider_trace_receipt_bundle_path": configured_path(
            "provider_trace_receipt_bundle"
        ),
        "provider_request_chain_bundle_path": configured_path(
            "provider_request_chain_bundle"
        ),
    }


def command_release_labels(args: argparse.Namespace) -> dict[str, Any]:
    closeout = import_closeout()
    replay_developer_chain()
    output_package = require_named_input(args.output_package, "output_package")
    require_regular_file(configured_path("execution_admission"), "execution admission")
    require_regular_file(configured_path("execution_output_seal"), "execution output seal")
    for name in (
        "effect_receipt_bundle",
        "provider_trace_receipt_bundle",
        "provider_request_chain_bundle",
    ):
        require_regular_file(configured_path(name), name)
    registration = read_json(configured_path("registration"))
    result = closeout.release_labels_to_custodian_scoring(
        execution_set_path=configured_path("execution_set"),
        custody_manifest_path=configured_path("custody"),
        **result_chain_paths(),
        execution_admission_path=configured_path("execution_admission"),
        output_package_path=output_package,
        label_file_path=configured_path("label_file"),
        execution_output_seal_path=configured_path("execution_output_seal"),
        released_at=utc_now(),
        custodian_id=str(registration["custodian_id"]),
    )
    write_json_new(configured_path("label_release_seal"), result)
    return result


def command_seal_scoring() -> dict[str, Any]:
    closeout = import_closeout()
    require_absent(configured_path("scoring_release_dir"))
    registration = read_json(configured_path("registration"))
    result = closeout.seal_custodian_scoring_results(
        execution_set_path=configured_path("execution_set"),
        custody_manifest_path=configured_path("custody"),
        **result_chain_paths(),
        execution_admission_path=configured_path("execution_admission"),
        execution_output_seal_path=configured_path("execution_output_seal"),
        output_package_path=configured_path("output_package"),
        label_release_seal_path=configured_path("label_release_seal"),
        label_file_path=configured_path("label_file"),
        scoring_results_path=configured_path("scoring_results"),
        scored_at=utc_now(),
        custodian_id=str(registration["custodian_id"]),
    )
    atomic_stage_scoring_release(result)
    return result


def command_scoring_attestation_build() -> dict[str, Any]:
    closeout = import_closeout()
    registration = read_json(configured_path("registration"))
    result = closeout.build_unsigned_scoring_attestation(
        scoring_result_seal_path=configured_path("scoring_result_seal"),
        custody_manifest_path=configured_path("custody"),
        registration_path=configured_path("registration"),
        custodian_id=str(registration["custodian_id"]),
        signed_at=utc_now(),
    )
    write_json_new(configured_path("unsigned_scoring_attestation"), result)
    return result


def command_scoring_attestation_finalize() -> dict[str, Any]:
    closeout = import_closeout()
    signature = require_regular_file(
        configured_path("scoring_attestation_signature"),
        "scoring attestation signature",
    ).read_text(encoding="ascii").strip()
    result = closeout.finalize_scoring_attestation(
        read_json(configured_path("unsigned_scoring_attestation")),
        custodian_signature=signature,
    )
    write_json_new(configured_path("scoring_attestation"), result)
    return result


def command_scoring_attestation_verify(args: argparse.Namespace) -> dict[str, Any]:
    closeout = import_closeout()
    attestation = read_json(configured_path("scoring_attestation"))
    ensure_verifier_distinct(
        args.verifier_id,
        str(attestation.get("custodian_id", "")),
    )
    result = closeout.verify_scoring_attestation(
        scoring_attestation_path=configured_path("scoring_attestation"),
        scoring_result_seal_path=configured_path("scoring_result_seal"),
        execution_set_path=configured_path("execution_set"),
        custody_manifest_path=configured_path("custody"),
        pre_release_receipt_path=configured_path("pre_release_review"),
        signature_verifier_receipt_path=configured_path(
            "custody_signature_receipt"
        ),
        execution_admission_path=configured_path("execution_admission"),
        execution_output_seal_path=configured_path("execution_output_seal"),
        output_package_path=configured_path("output_package"),
        effect_receipt_bundle_path=configured_path("effect_receipt_bundle"),
        provider_trace_receipt_bundle_path=configured_path(
            "provider_trace_receipt_bundle"
        ),
        provider_request_chain_bundle_path=configured_path(
            "provider_request_chain_bundle"
        ),
        label_release_seal_path=configured_path("label_release_seal"),
        label_file_path=configured_path("label_file"),
        scoring_results_path=configured_path("scoring_results"),
        scoring_results_release_path=configured_path("scoring_results_release"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        public_key_path=configured_path("public_key"),
        verifier_id=args.verifier_id,
        verified_at=utc_now(),
    )
    write_json_new(configured_path("scoring_attestation_receipt"), result)
    return result


def command_scoring_attestation_verify_integrity_only(
    args: argparse.Namespace,
) -> dict[str, Any]:
    closeout = import_closeout()
    verify_scoring_release_pair(compare_private_original=False)
    attestation = read_json(configured_path("scoring_attestation"))
    ensure_verifier_distinct(
        args.verifier_id,
        str(attestation.get("custodian_id", "")),
    )
    result = closeout.verify_scoring_attestation_integrity_only(
        scoring_attestation_path=configured_path("scoring_attestation"),
        scoring_result_seal_path=configured_path("scoring_result_seal"),
        scoring_results_release_path=configured_path("scoring_results_release"),
        custody_manifest_path=configured_path("custody"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        public_key_path=configured_path("public_key"),
        verifier_id=args.verifier_id,
        verified_at=utc_now(),
    )
    write_json_new(configured_path("developer_safe_integrity_receipt"), result)
    return result


def replay_scoring_chain() -> None:
    closeout = import_closeout()
    replay_developer_chain()
    registration = read_json(configured_path("registration"))
    release = read_json(configured_path("label_release_seal"))
    replayed_release = closeout.release_labels_to_custodian_scoring(
        execution_set_path=configured_path("execution_set"),
        custody_manifest_path=configured_path("custody"),
        **result_chain_paths(),
        execution_admission_path=configured_path("execution_admission"),
        output_package_path=configured_path("output_package"),
        label_file_path=configured_path("label_file"),
        execution_output_seal_path=configured_path("execution_output_seal"),
        released_at=str(release.get("released_at", "")),
        custodian_id=str(registration["custodian_id"]),
    )
    if (
        replayed_release != release
        or release.get("status") != WORKFLOW_STATUSES["label_release_seal"]
    ):
        raise CustodianCLIError("label release chain does not replay")
    scoring = read_json(configured_path("scoring_result_seal"))
    replayed_scoring = closeout.seal_custodian_scoring_results(
        execution_set_path=configured_path("execution_set"),
        custody_manifest_path=configured_path("custody"),
        **result_chain_paths(),
        execution_admission_path=configured_path("execution_admission"),
        execution_output_seal_path=configured_path("execution_output_seal"),
        output_package_path=configured_path("output_package"),
        label_release_seal_path=configured_path("label_release_seal"),
        label_file_path=configured_path("label_file"),
        scoring_results_path=configured_path("scoring_results"),
        scored_at=str(scoring.get("scored_at", "")),
        custodian_id=str(registration["custodian_id"]),
    )
    if (
        replayed_scoring != scoring
        or scoring.get("status") != WORKFLOW_STATUSES["scoring_result_seal"]
    ):
        raise CustodianCLIError("scoring result chain does not replay")
    attestation = read_json(configured_path("scoring_attestation"))
    unsigned = read_json(configured_path("unsigned_scoring_attestation"))
    replayed_unsigned = closeout.build_unsigned_scoring_attestation(
        scoring_result_seal_path=configured_path("scoring_result_seal"),
        custody_manifest_path=configured_path("custody"),
        registration_path=configured_path("registration"),
        custodian_id=str(registration["custodian_id"]),
        signed_at=str(attestation.get("signed_at", "")),
    )
    if replayed_unsigned != unsigned:
        raise CustodianCLIError("unsigned scoring attestation does not replay")
    signature = require_regular_file(
        configured_path("scoring_attestation_signature"),
        "scoring attestation signature",
    ).read_text(encoding="ascii").strip()
    if closeout.finalize_scoring_attestation(
        unsigned,
        custodian_signature=signature,
    ) != attestation:
        raise CustodianCLIError("signed scoring attestation does not replay")
    receipt = read_json(configured_path("scoring_attestation_receipt"))
    ensure_verifier_distinct(
        str(receipt.get("verifier_id", "")),
        str(attestation.get("custodian_id", "")),
    )
    replayed_receipt = closeout.verify_scoring_attestation(
        scoring_attestation_path=configured_path("scoring_attestation"),
        scoring_result_seal_path=configured_path("scoring_result_seal"),
        execution_set_path=configured_path("execution_set"),
        custody_manifest_path=configured_path("custody"),
        pre_release_receipt_path=configured_path("pre_release_review"),
        signature_verifier_receipt_path=configured_path(
            "custody_signature_receipt"
        ),
        execution_admission_path=configured_path("execution_admission"),
        execution_output_seal_path=configured_path("execution_output_seal"),
        output_package_path=configured_path("output_package"),
        effect_receipt_bundle_path=configured_path("effect_receipt_bundle"),
        provider_trace_receipt_bundle_path=configured_path(
            "provider_trace_receipt_bundle"
        ),
        provider_request_chain_bundle_path=configured_path(
            "provider_request_chain_bundle"
        ),
        label_release_seal_path=configured_path("label_release_seal"),
        label_file_path=configured_path("label_file"),
        scoring_results_path=configured_path("scoring_results"),
        scoring_results_release_path=configured_path("scoring_results_release"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        public_key_path=configured_path("public_key"),
        verifier_id=str(receipt.get("verifier_id", "")),
        verified_at=str(receipt.get("verified_at", "")),
    )
    if (
        replayed_receipt != receipt
        or receipt.get("status")
        != WORKFLOW_STATUSES["scoring_attestation_receipt"]
    ):
        raise CustodianCLIError("scoring attestation verification does not replay")
    verify_scoring_release_pair(compare_private_original=True)


def replay_developer_safe_integrity() -> dict[str, Any]:
    closeout = import_closeout()
    verify_scoring_release_pair(compare_private_original=False)
    attestation = read_json(configured_path("scoring_attestation"))
    receipt = read_json(configured_path("developer_safe_integrity_receipt"))
    ensure_verifier_distinct(
        str(receipt.get("verifier_id", "")),
        str(attestation.get("custodian_id", "")),
    )
    replayed = closeout.verify_scoring_attestation_integrity_only(
        scoring_attestation_path=configured_path("scoring_attestation"),
        scoring_result_seal_path=configured_path("scoring_result_seal"),
        scoring_results_release_path=configured_path("scoring_results_release"),
        custody_manifest_path=configured_path("custody"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        public_key_path=configured_path("public_key"),
        verifier_id=str(receipt.get("verifier_id", "")),
        verified_at=str(receipt.get("verified_at", "")),
    )
    boundary = receipt.get("evidence_boundary")
    if (
        replayed != receipt
        or receipt.get("status")
        != WORKFLOW_STATUSES["developer_safe_integrity_receipt"]
        or not isinstance(boundary, Mapping)
        or boundary.get("verification_scope")
        != "developer_safe_signature_integrity_only"
        or boundary.get("private_label_payload_opened") is not False
        or boundary.get("private_path_arguments_accepted") is not False
        or boundary.get("private_paths_enumerated") is not False
        or boundary.get("scoring_semantics_recomputed") is not False
        or boundary.get("scientific_outcomes_read") != 3600
    ):
        raise CustodianCLIError(
            "developer-safe signature/integrity verification does not replay"
        )
    return receipt


def private_audit_sources() -> tuple[tuple[str, Path, bool], ...]:
    private = (
        (
            "private/offline_identity_attestation.txt",
            configured_path("identity_attestation"),
            True,
        ),
        (
            "private/authored_pairs.jsonl",
            configured_path("authored_pairs"),
            True,
        ),
        ("private/blind_labels_v2.jsonl", configured_path("label_file"), True),
        (
            "private/scoring_results_v2.jsonl",
            configured_path("scoring_results"),
            True,
        ),
    )
    chain_names = (
        "public_key",
        "unsigned_registration",
        "registration_signature",
        "registration",
        "registration_receipt",
        "split_receipt",
        "split_timing",
        "pre_release_review",
        "execution_set",
        "execution_release_receipt",
        "developer_receipt",
        "unsigned_custody",
        "custody_signature",
        "custody",
        "custody_signature_receipt",
        "execution_admission",
        "execution_output_seal",
        "output_package",
        "effect_receipt_bundle",
        "provider_trace_receipt_bundle",
        "provider_request_chain_bundle",
        "label_release_seal",
        "scoring_result_seal",
        "scoring_results_release",
        "unsigned_scoring_attestation",
        "scoring_attestation_signature",
        "scoring_attestation",
        "scoring_attestation_receipt",
    )
    chain = tuple(
        (f"chain/{configured_path(name).name}", configured_path(name), False)
        for name in chain_names
    )
    return private + chain + safety_ancestor_sources()


def developer_safe_final_sources() -> tuple[tuple[str, Path, bool], ...]:
    names = (
        "public_key",
        "registration",
        "registration_receipt",
        "pre_release_review",
        "execution_set",
        "execution_release_receipt",
        "developer_receipt",
        "custody",
        "custody_signature_receipt",
        "execution_admission",
        "execution_output_seal",
        "output_package",
        "effect_receipt_bundle",
        "provider_trace_receipt_bundle",
        "provider_request_chain_bundle",
        "label_release_seal",
        "scoring_results_release",
        "scoring_result_seal",
        "scoring_attestation",
        "developer_safe_integrity_receipt",
    )
    chain = tuple(
        (f"chain/{configured_path(name).name}", configured_path(name), False)
        for name in names
    )
    return chain + safety_ancestor_sources()


def command_stage_private_audit() -> dict[str, Any]:
    replay_scoring_chain()
    return atomic_stage_directory(
        destination=configured_path("private_audit_dir"),
        sources=private_audit_sources(),
        generated=None,
        status="custodian_private_artifact_full_replay_bundle_staged",
        allow_private=True,
        evidence_boundary={
            "recipient_role": "custodian_or_separately_isolated_second_reviewer",
            "developer_safe": False,
            "verification_scope": "custodian_private_artifact_full_replay",
            "labels_opened": True,
            "contains_private_labels": True,
            "contains_authored_pairs": True,
            "artifact_hash_and_signature_chain_full_replay_supported": True,
            "semantic_recomputation": False,
            "scoring_semantics_custodian_attested": True,
            "isolated_human_case_review_supported": True,
            "must_never_be_sent_to_developer": True,
            "private_key_included": False,
        },
    )


def command_stage_developer_safe_final() -> dict[str, Any]:
    replay_developer_safe_integrity()
    return atomic_stage_directory(
        destination=configured_path("developer_safe_final_dir"),
        sources=developer_safe_final_sources(),
        generated=None,
        status="developer_safe_signature_integrity_only_bundle_staged",
        allow_private=False,
        evidence_boundary={
            "recipient_role": "experiment_developer",
            "verification_scope": "developer_safe_signature_integrity_only",
            "labels_opened": False,
            "semantic_recomputation": False,
            "released_scoring_rows_read": 3600,
            "contains_private_label_file": False,
            "contains_authored_pairs": False,
            "private_key_included": False,
            "chain_hash_source_signature_verification_supported": True,
            "independent_case_semantics_recomputation_supported": False,
            "private_label_payload_available": False,
            "isolated_human_case_review_requires_private_audit_access": True,
        },
    )


def validate_internal_signature(stage: str) -> None:
    request = signing_request(stage)
    _, _, signature_name = SIGNING_STAGES[stage]
    signature = decoded_signature(
        require_regular_file(configured_path(signature_name), f"{stage} signature")
    )
    public_key, _ = public_key_fingerprint()
    try:
        public_key.verify(
            signature,
            bytes.fromhex(str(request["payload_digest_sha256"])),
        )
    except Exception as exc:
        raise CustodianCLIError(f"{stage} signature math verification failed") from exc


def replay_unsigned_registration(closeout: Any) -> dict[str, Any]:
    unsigned = read_json(configured_path("unsigned_registration"))
    identity = require_regular_file(
        configured_path("identity_attestation"),
        "offline identity attestation",
    )
    replayed = closeout.build_unsigned_custodian_registration(
        custodian_id=str(unsigned.get("custodian_id", "")),
        project_relationship=str(unsigned.get("project_relationship", "")),
        public_key_path=configured_path("public_key"),
        confirmed_at=str(unsigned.get("confirmed_at", "")),
        offline_identity_evidence_sha256=sha256_file(identity),
    )
    if replayed != unsigned:
        raise CustodianCLIError("unsigned registration does not replay")
    return unsigned


def replay_unsigned_custody(closeout: Any) -> dict[str, Any]:
    registration = replay_registration(closeout)
    timing, release, developer_receipt = replay_developer_receipt(closeout)
    replayed = closeout.build_unsigned_custody_seal(
        execution_set_path=configured_path("execution_set"),
        label_file_path=configured_path("label_file"),
        pre_release_receipt_path=configured_path("pre_release_review"),
        registration_path=configured_path("registration"),
        registration_verifier_receipt_path=configured_path("registration_receipt"),
        custodian_public_key_path=configured_path("public_key"),
        custodian_id=str(registration["custodian_id"]),
        custodian_signature_scheme=closeout.ED25519_SIGNATURE_SCHEME,
        custodian_signature_key_id=str(registration["signature_key_id"]),
        authoring_completed_at=str(timing["authoring_completed_at"]),
        split_completed_at=str(timing["split_completed_at"]),
        sealed_at=str(release["sealed_at"]),
        execution_set_released_at=str(release["execution_set_released_at"]),
        developer_received_execution_set_at=str(
            developer_receipt["developer_received_execution_set_at"]
        ),
    )
    if replayed != read_json(configured_path("unsigned_custody")):
        raise CustodianCLIError("unsigned custody does not replay")
    return replayed


def verify_stage_directory(
    destination: Path,
    *,
    expected_names: set[str],
    expected_status: str,
) -> None:
    if not destination.is_dir() or is_reparse(destination):
        raise CustodianCLIError("staged directory is missing or unsafe")
    manifest_path = require_regular_file(
        destination / "handoff_manifest_v3.json",
        "handoff manifest",
    )
    manifest = read_json(manifest_path)
    if set(manifest) != {
        "schema_version",
        "status",
        "files",
        "evidence_boundary",
        "network_calls_made",
        "manifest_sha256",
    } or manifest.get("manifest_sha256") != manifest_sha(manifest):
        raise CustodianCLIError("handoff manifest schema or digest drift")
    if manifest.get("status") != expected_status:
        raise CustodianCLIError("handoff manifest status drift")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise CustodianCLIError("handoff file list is invalid")
    recorded: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {
            "filename",
            "bytes",
            "sha256",
        }:
            raise CustodianCLIError("handoff file entry schema drift")
        relative = str(entry.get("filename", ""))
        if relative in recorded:
            raise CustodianCLIError("duplicate handoff file path")
        recorded.add(relative)
        path = destination.joinpath(*safe_relative(relative).parts)
        require_regular_file(path, "staged handoff file")
        if path.stat().st_size != entry.get("bytes") or sha256_file(path) != entry.get(
            "sha256"
        ):
            raise CustodianCLIError("staged handoff file binding drift")
    if recorded != expected_names:
        raise CustodianCLIError("handoff file set is not exact")
    actual: set[str] = set()
    found, unsafe = immutable_files_under(destination)
    if unsafe:
        raise CustodianCLIError("unsafe node in staged handoff")
    for path in found:
        relative = path.relative_to(destination).as_posix()
        if relative != "handoff_manifest_v3.json":
            actual.add(relative)
    if actual != expected_names:
        raise CustodianCLIError("unlisted file in staged handoff")


def command_self_test(with_pytest: bool) -> dict[str, Any]:
    verification = verify_package(pristine=False)
    slots = immutable_path(
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/slots.jsonl"
    )
    checks = {
        "immutable_package_verified": verification["status"]
        == "review_package_verified",
        "slots_sha256_locked": sha256_file(slots) == EXPECTED_SLOTS_SHA256,
        "slots_exactly_600": len(slots.read_text(encoding="utf-8").splitlines())
        == 600,
        "closeout_imported": import_closeout().EXPECTED_SLOTS_SHA256
        == EXPECTED_SLOTS_SHA256,
        "environment_not_mutated": True,
    }
    pytest_exit: int | None = None
    if with_pytest:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "-q",
                "tests",
            ],
            cwd=PACKAGE_ROOT,
            check=False,
        )
        pytest_exit = completed.returncode
        checks["packaged_pytest_exit_zero"] = pytest_exit == 0
    passed = all(checks.values())
    return {
        "schema_version": "m3-paper-v2-python-review-self-test-3.0",
        "status": "self_test_passed" if passed else "self_test_failed",
        "checks": checks,
        "pytest_exit_code": pytest_exit,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


PYTHON_COMMAND = ".\\work\\runtime\\venv\\Scripts\\python.exe -B .\\custodian.py"


def next_stage(stage: str, action: str) -> dict[str, Any]:
    return {
        "schema_version": "m3-paper-v2-custodian-next-stage-3.0",
        "status": "next_stage_available",
        "stage": stage,
        "command_or_action": action,
        "prior_stages_replayed": True,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


def expected_source_names(
    sources: Sequence[tuple[str, Path, bool]],
) -> set[str]:
    return {name for name, _, _ in sources}


def replay_label_release(closeout: Any) -> dict[str, Any]:
    replay_developer_chain()
    registration = read_json(configured_path("registration"))
    release = read_json(configured_path("label_release_seal"))
    replayed = closeout.release_labels_to_custodian_scoring(
        execution_set_path=configured_path("execution_set"),
        custody_manifest_path=configured_path("custody"),
        **result_chain_paths(),
        execution_admission_path=configured_path("execution_admission"),
        output_package_path=configured_path("output_package"),
        label_file_path=configured_path("label_file"),
        execution_output_seal_path=configured_path("execution_output_seal"),
        released_at=str(release.get("released_at", "")),
        custodian_id=str(registration["custodian_id"]),
    )
    if (
        replayed != release
        or release.get("status") != WORKFLOW_STATUSES["label_release_seal"]
    ):
        raise CustodianCLIError("label release chain does not replay")
    return release


def replay_scoring_seal(closeout: Any) -> dict[str, Any]:
    replay_label_release(closeout)
    registration = read_json(configured_path("registration"))
    scoring = read_json(configured_path("scoring_result_seal"))
    replayed = closeout.seal_custodian_scoring_results(
        execution_set_path=configured_path("execution_set"),
        custody_manifest_path=configured_path("custody"),
        **result_chain_paths(),
        execution_admission_path=configured_path("execution_admission"),
        execution_output_seal_path=configured_path("execution_output_seal"),
        output_package_path=configured_path("output_package"),
        label_release_seal_path=configured_path("label_release_seal"),
        label_file_path=configured_path("label_file"),
        scoring_results_path=configured_path("scoring_results"),
        scored_at=str(scoring.get("scored_at", "")),
        custodian_id=str(registration["custodian_id"]),
    )
    if (
        replayed != scoring
        or scoring.get("status") != WORKFLOW_STATUSES["scoring_result_seal"]
    ):
        raise CustodianCLIError("scoring result chain does not replay")
    verify_scoring_release_pair(compare_private_original=True)
    return scoring


def workflow_state() -> dict[str, Any]:
    closeout = import_closeout()
    if not configured_path("public_key").exists():
        return next_stage(
            "register_external_public_key",
            f"{PYTHON_COMMAND} register-public-key --public-key "
            "<ABSOLUTE_EXTERNAL_ED25519_PUBLIC_KEY_PEM>",
        )
    public_key_fingerprint()
    if not configured_path("identity_attestation").exists():
        return next_stage(
            "prepare_identity_attestation",
            f"{PYTHON_COMMAND} prepare-identity-template",
        )
    identity = require_regular_file(
        configured_path("identity_attestation"),
        "offline identity attestation",
    ).read_text(encoding="utf-8")
    if "<" in identity or ">" in identity:
        return next_stage(
            "edit_identity_attestation",
            "MANUAL: remove every placeholder from work/private/registration/"
            "offline_identity_attestation.txt",
        )
    if not configured_path("unsigned_registration").exists():
        return next_stage(
            "build_registration",
            f"{PYTHON_COMMAND} registration-build --custodian-id <CUSTODIAN_ID> "
            "--project-relationship <RELATIONSHIP>",
        )
    replay_unsigned_registration(closeout)
    if not configured_path("registration_signature").exists():
        return next_stage(
            "externally_sign_registration",
            f"{PYTHON_COMMAND} export-signing-request --stage registration "
            "--output <ABSOLUTE_EXTERNAL_REQUEST_JSON>; use approved external "
            f"signer; {PYTHON_COMMAND} import-detached-signature --stage "
            "registration --signature-file <ABSOLUTE_EXTERNAL_SIGNATURE_FILE>",
        )
    validate_internal_signature("registration")
    if not configured_path("registration").exists():
        return next_stage(
            "finalize_registration",
            f"{PYTHON_COMMAND} registration-finalize",
        )
    unsigned_registration = replay_unsigned_registration(closeout)
    registration = read_json(configured_path("registration"))
    signature = configured_path("registration_signature").read_text(
        encoding="ascii"
    ).strip()
    if closeout.finalize_custodian_registration(
        unsigned_registration,
        custodian_signature=signature,
    ) != registration:
        raise CustodianCLIError("signed registration does not replay")
    if not configured_path("registration_receipt").exists():
        return next_stage(
            "verify_registration",
            f"{PYTHON_COMMAND} registration-verify --verifier-id <DISTINCT_VERIFIER_ID>",
        )
    replay_registration(closeout)
    if not configured_path("authored_pairs").exists():
        return next_stage(
            "author_600_private_pairs",
            "MANUAL: create work/private/authored_pairs/authored_pairs.jsonl "
            "from frozen slots and immutable templates",
        )
    closeout.split_authored_pairs(read_jsonl(configured_path("authored_pairs")))
    if not configured_path("split_timing").exists():
        partial = any(
            configured_path(name).exists()
            for name in ("execution_set", "label_file", "split_receipt")
        )
        if partial:
            raise CustodianCLIError("partial split outputs exist; preserve and stop")
        return next_stage("split_private_pairs", f"{PYTHON_COMMAND} split")
    replay_split(closeout)
    if not configured_path("pre_release_review").exists():
        return next_stage(
            "validate_pre_release",
            f"{PYTHON_COMMAND} validate-pre-release",
        )
    recorded_pre_release = read_json(configured_path("pre_release_review"))
    if closeout.validate_custodian_pre_release(
        execution_set_path=configured_path("execution_set"),
        label_file_path=configured_path("label_file"),
    ) != recorded_pre_release:
        raise CustodianCLIError("pre-release validation does not replay")
    if not configured_path("execution_release_dir").exists():
        return next_stage(
            "stage_execution_only",
            f"{PYTHON_COMMAND} stage-execution-set",
        )
    replay_execution_release(closeout)
    if not configured_path("developer_receipt").exists():
        return next_stage(
            "record_developer_receipt_after_acknowledgement",
            f"{PYTHON_COMMAND} record-developer-receipt --receiver-id <RECEIVER_ID>",
        )
    replay_developer_receipt(closeout)
    if not configured_path("unsigned_custody").exists():
        return next_stage("build_custody", f"{PYTHON_COMMAND} custody-build")
    replay_unsigned_custody(closeout)
    if not configured_path("custody_signature").exists():
        return next_stage(
            "externally_sign_custody",
            f"{PYTHON_COMMAND} export-signing-request --stage custody --output "
            "<ABSOLUTE_EXTERNAL_REQUEST_JSON>; use approved external signer; "
            f"{PYTHON_COMMAND} import-detached-signature --stage custody "
            "--signature-file <ABSOLUTE_EXTERNAL_SIGNATURE_FILE>",
        )
    validate_internal_signature("custody")
    if not configured_path("custody").exists():
        return next_stage("finalize_custody", f"{PYTHON_COMMAND} custody-finalize")
    unsigned_custody = replay_unsigned_custody(closeout)
    custody_signature = configured_path("custody_signature").read_text(
        encoding="ascii"
    ).strip()
    if closeout.finalize_custody_seal(
        unsigned_custody,
        custodian_signature=custody_signature,
    ) != read_json(configured_path("custody")):
        raise CustodianCLIError("signed custody does not replay")
    if not configured_path("custody_signature_receipt").exists():
        return next_stage(
            "verify_custody",
            f"{PYTHON_COMMAND} custody-verify --verifier-id <DISTINCT_VERIFIER_ID>",
        )
    replay_developer_chain()
    if not configured_path("developer_handoff_dir").exists():
        return next_stage(
            "stage_developer_evidence",
            f"{PYTHON_COMMAND} stage-developer-handoff",
        )
    developer_sources = (
        (
            "blind_execution_v2.jsonl",
            configured_path("execution_set"),
            False,
        ),
        ("split_receipt_v2.json", configured_path("split_receipt"), False),
        ("split_timing_v3.json", configured_path("split_timing"), False),
        (
            "pre_release_review_v2.json",
            configured_path("pre_release_review"),
            False,
        ),
        (
            "execution_release_receipt_v3.json",
            configured_path("execution_release_receipt"),
            False,
        ),
        (
            "developer_execution_receipt_v3.json",
            configured_path("developer_receipt"),
            False,
        ),
        ("custodian_public_key.pem", configured_path("public_key"), False),
        (
            "custodian_registration_v2.json",
            configured_path("registration"),
            False,
        ),
        (
            "custodian_registration_verifier_receipt_v2.json",
            configured_path("registration_receipt"),
            False,
        ),
        ("blind_custody_v2.json", configured_path("custody"), False),
        (
            "custody_signature_verifier_receipt_v2.json",
            configured_path("custody_signature_receipt"),
            False,
        ),
    ) + safety_ancestor_sources()
    verify_stage_directory(
        configured_path("developer_handoff_dir"),
        expected_names=expected_source_names(developer_sources),
        expected_status="developer_label_free_evidence_handoff_staged",
    )
    for name, stage, message in (
        (
            "execution_admission",
            "wait_for_execution_admission",
            "WAIT: receive execution_admission_v2.json into the fixed incoming directory",
        ),
        (
            "execution_output_seal",
            "wait_for_execution_output_seal",
            "WAIT: receive execution_output_seal_v2.json into the fixed incoming directory",
        ),
        (
            "output_package",
            "wait_for_complete_output_package",
            "WAIT: receive the complete 3,600-row output_package_v2.jsonl",
        ),
        (
            "effect_receipt_bundle",
            "wait_for_effect_receipt_bundle",
            "WAIT: receive effect_receipt_bundle_v2.jsonl into the fixed incoming directory",
        ),
        (
            "provider_trace_receipt_bundle",
            "wait_for_provider_trace_receipt_bundle",
            "WAIT: receive provider_trace_receipt_bundle_v2.jsonl into the fixed incoming directory",
        ),
        (
            "provider_request_chain_bundle",
            "wait_for_provider_request_chain_bundle",
            "WAIT: receive provider_request_chain_bundle_v2.jsonl into the fixed incoming directory",
        ),
    ):
        if not configured_path(name).exists():
            return next_stage(stage, message)
        require_regular_file(configured_path(name), name)
    if not configured_path("label_release_seal").exists():
        return next_stage(
            "verify_complete_output_chain_and_release_labels_to_scoring",
            f"{PYTHON_COMMAND} release-labels-for-scoring --output-package "
            ".\\work\\incoming_from_developer\\output_package_v2.jsonl",
        )
    replay_label_release(closeout)
    if not configured_path("scoring_results").exists():
        return next_stage(
            "score_3600_rows_privately",
            "MANUAL: create work/private/scoring/scoring_results_v2.jsonl; "
            "never give the label file to the developer",
        )
    require_regular_file(configured_path("scoring_results"), "scoring results")
    if not configured_path("scoring_result_seal").exists():
        return next_stage(
            "seal_scoring_results",
            f"{PYTHON_COMMAND} seal-scoring-results",
        )
    replay_scoring_seal(closeout)
    if not configured_path("unsigned_scoring_attestation").exists():
        return next_stage(
            "build_scoring_attestation",
            f"{PYTHON_COMMAND} scoring-attestation-build",
        )
    unsigned_attestation = read_json(configured_path("unsigned_scoring_attestation"))
    replayed_unsigned_attestation = closeout.build_unsigned_scoring_attestation(
        scoring_result_seal_path=configured_path("scoring_result_seal"),
        custody_manifest_path=configured_path("custody"),
        registration_path=configured_path("registration"),
        custodian_id=str(registration["custodian_id"]),
        signed_at=str(unsigned_attestation.get("signed_at", "")),
    )
    if replayed_unsigned_attestation != unsigned_attestation:
        raise CustodianCLIError("unsigned scoring attestation does not replay")
    if not configured_path("scoring_attestation_signature").exists():
        return next_stage(
            "externally_sign_scoring_attestation",
            f"{PYTHON_COMMAND} export-signing-request --stage scoring --output "
            "<ABSOLUTE_EXTERNAL_REQUEST_JSON>; use approved external signer; "
            f"{PYTHON_COMMAND} import-detached-signature --stage scoring "
            "--signature-file <ABSOLUTE_EXTERNAL_SIGNATURE_FILE>",
        )
    validate_internal_signature("scoring")
    if not configured_path("scoring_attestation").exists():
        return next_stage(
            "finalize_scoring_attestation",
            f"{PYTHON_COMMAND} scoring-attestation-finalize",
        )
    scoring_signature = configured_path("scoring_attestation_signature").read_text(
        encoding="ascii"
    ).strip()
    if closeout.finalize_scoring_attestation(
        unsigned_attestation,
        custodian_signature=scoring_signature,
    ) != read_json(configured_path("scoring_attestation")):
        raise CustodianCLIError("signed scoring attestation does not replay")
    if not configured_path("scoring_attestation_receipt").exists():
        return next_stage(
            "verify_scoring_attestation",
            f"{PYTHON_COMMAND} scoring-attestation-verify --verifier-id "
            "<DISTINCT_VERIFIER_ID>",
        )
    replay_scoring_chain()
    if not configured_path("private_audit_dir").exists():
        return next_stage(
            "stage_private_full_replay_audit_bundle",
            f"{PYTHON_COMMAND} stage-private-audit",
        )
    verify_stage_directory(
        configured_path("private_audit_dir"),
        expected_names=expected_source_names(private_audit_sources()),
        expected_status="custodian_private_artifact_full_replay_bundle_staged",
    )
    if not configured_path("developer_safe_integrity_receipt").exists():
        return next_stage(
            "verify_developer_safe_signature_integrity_without_private_paths",
            f"{PYTHON_COMMAND} scoring-attestation-verify-integrity-only "
            "--verifier-id <DISTINCT_VERIFIER_ID>",
        )
    replay_developer_safe_integrity()
    if not configured_path("developer_safe_final_dir").exists():
        return next_stage(
            "stage_developer_safe_signed_evidence",
            f"{PYTHON_COMMAND} stage-developer-safe-final",
        )
    verify_stage_directory(
        configured_path("developer_safe_final_dir"),
        expected_names=expected_source_names(developer_safe_final_sources()),
        expected_status="developer_safe_signature_integrity_only_bundle_staged",
    )
    return {
        "schema_version": "m3-paper-v2-custodian-next-stage-3.0",
        "status": "custodian_workflow_complete",
        "all_stages_replayed": True,
        "private_audit_verification_scope": (
            "custodian_private_artifact_full_replay"
        ),
        "private_audit_labels_opened": True,
        "private_audit_semantic_recomputation": False,
        "developer_safe_verification_scope": (
            "developer_safe_signature_integrity_only"
        ),
        "developer_safe_labels_opened": False,
        "developer_safe_bundle_contains_private_labels": False,
        "developer_safe_bundle_can_recompute_case_semantics": False,
        "private_audit_bundle_must_not_be_sent_to_developer": True,
        "environment_variables_written": 0,
        "network_calls_made": 0,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Run from the standalone package root. Formal timestamps are recorded "
            "automatically in UTC. No command writes environment variables."
        ),
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("verify-pristine")
    commands.add_parser("verify")
    self_test = commands.add_parser("self-test")
    self_test.add_argument("--with-pytest", action="store_true")
    commands.add_parser("status")
    commands.add_parser("show-next")

    register_key = commands.add_parser("register-public-key")
    register_key.add_argument("--public-key", required=True)
    commands.add_parser("prepare-identity-template")

    export = commands.add_parser("export-signing-request")
    export.add_argument("--stage", choices=sorted(SIGNING_STAGES), required=True)
    export.add_argument("--output", required=True)
    import_signature = commands.add_parser("import-detached-signature")
    import_signature.add_argument(
        "--stage",
        choices=sorted(SIGNING_STAGES),
        required=True,
    )
    import_signature.add_argument("--signature-file", required=True)
    fallback = commands.add_parser("sign-request")
    fallback.add_argument("--stage", choices=sorted(SIGNING_STAGES), required=True)
    fallback.add_argument("--request", required=True)
    fallback.add_argument("--encrypted-private-key", required=True)
    fallback.add_argument("--signature-out", required=True)

    registration = commands.add_parser("registration-build")
    registration.add_argument("--custodian-id", required=True)
    registration.add_argument("--project-relationship", required=True)
    commands.add_parser("registration-finalize")
    verify_registration = commands.add_parser("registration-verify")
    verify_registration.add_argument("--verifier-id", required=True)

    commands.add_parser("split")
    commands.add_parser("validate-pre-release")
    commands.add_parser("stage-execution-set")
    developer_receipt = commands.add_parser("record-developer-receipt")
    developer_receipt.add_argument("--receiver-id", required=True)
    commands.add_parser("custody-build")
    commands.add_parser("custody-finalize")
    verify_custody = commands.add_parser("custody-verify")
    verify_custody.add_argument("--verifier-id", required=True)
    commands.add_parser("stage-developer-handoff")

    release = commands.add_parser("release-labels-for-scoring")
    release.add_argument("--output-package", required=True)
    commands.add_parser("seal-scoring-results")
    commands.add_parser("scoring-attestation-build")
    commands.add_parser("scoring-attestation-finalize")
    verify_attestation = commands.add_parser("scoring-attestation-verify")
    verify_attestation.add_argument("--verifier-id", required=True)
    verify_integrity = commands.add_parser(
        "scoring-attestation-verify-integrity-only"
    )
    verify_integrity.add_argument("--verifier-id", required=True)
    commands.add_parser("stage-private-audit")
    commands.add_parser("stage-developer-safe-final")
    return root


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "verify-pristine":
        return verify_package(pristine=True)
    if args.command == "verify":
        return verify_package(pristine=False)
    if args.command == "self-test":
        return command_self_test(args.with_pytest)
    require_package_verified()
    if args.command in {"status", "show-next"}:
        return workflow_state()
    if args.command == "register-public-key":
        return command_register_public_key(args)
    if args.command == "prepare-identity-template":
        return command_prepare_identity_template()
    if args.command == "export-signing-request":
        return command_export_signing_request(args)
    if args.command == "import-detached-signature":
        return command_import_detached_signature(args)
    if args.command == "sign-request":
        return command_sign_request(args)
    if args.command == "registration-build":
        return command_registration_build(args)
    if args.command == "registration-finalize":
        return command_registration_finalize()
    if args.command == "registration-verify":
        return command_registration_verify(args)
    if args.command == "split":
        return command_split()
    if args.command == "validate-pre-release":
        return command_validate_pre_release()
    if args.command == "stage-execution-set":
        return command_stage_execution_set()
    if args.command == "record-developer-receipt":
        return command_record_developer_receipt(args)
    if args.command == "custody-build":
        return command_custody_build()
    if args.command == "custody-finalize":
        return command_custody_finalize()
    if args.command == "custody-verify":
        return command_custody_verify(args)
    if args.command == "stage-developer-handoff":
        return command_stage_developer_handoff()
    if args.command == "release-labels-for-scoring":
        return command_release_labels(args)
    if args.command == "seal-scoring-results":
        return command_seal_scoring()
    if args.command == "scoring-attestation-build":
        return command_scoring_attestation_build()
    if args.command == "scoring-attestation-finalize":
        return command_scoring_attestation_finalize()
    if args.command == "scoring-attestation-verify":
        return command_scoring_attestation_verify(args)
    if args.command == "scoring-attestation-verify-integrity-only":
        return command_scoring_attestation_verify_integrity_only(args)
    if args.command == "stage-private-audit":
        return command_stage_private_audit()
    if args.command == "stage-developer-safe-final":
        return command_stage_developer_safe_final()
    raise CustodianCLIError(f"unsupported command: {args.command}")


def main() -> int:
    args = parser().parse_args()
    try:
        with single_instance_lock():
            result = dispatch(args)
    except (CustodianCLIError, OSError, ValueError, EOFError) as exc:
        print(
            json.dumps(
                {
                    "status": "command_rejected",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "environment_variables_written": 0,
                    "network_calls_made": 0,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    status_value = str(result.get("status", ""))
    return 2 if status_value.endswith(("rejected", "failed")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
