"""Versioned custodian-side authoring and developer-side blind import contract.

The authoring splitter and pre-release validator are intended for an independent
custodian and may inspect synthetic or private label data.  The developer-side
import accepts only a label-free execution set and a custody manifest; it never
accepts or opens the label file.  This module creates no project candidate or
label data by itself.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from experiments.paper_v2.contracts import canonical_json_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KIT_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2"
DEFAULT_SLOTS = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl"
)
EXPECTED_SAMPLE_COUNTS = {
    "attack": 360,
    "benign_legal_tool": 120,
    "benign_no_tool": 120,
}
EXPECTED_AUTHOR_GROUP_COUNTS = {"1": 300, "2": 300}
EXPECTED_SLOTS_SHA256 = (
    "4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8"
)
EXECUTION_SCHEMA_VERSION = "m3-paper-v2-independent-blind-execution-2.0"
LABEL_SCHEMA_VERSION = "m3-paper-v2-independent-blind-label-2.0"
PAIR_SCHEMA_VERSION = "m3-paper-v2-independent-blind-authoring-pair-2.0"
CUSTODY_SCHEMA_VERSION = "m3-paper-v2-independent-blind-custody-2.0"
REGISTRATION_SCHEMA_VERSION = "m3-paper-v2-independent-blind-custodian-registration-2.0"
REGISTRATION_VERIFIER_RECEIPT_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-registration-verifier-receipt-2.0"
)
SIGNATURE_VERIFIER_RECEIPT_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-signature-verifier-receipt-2.0"
)
PRE_RELEASE_SCHEMA_VERSION = "m3-paper-v2-independent-blind-pre-release-review-2.0"
EXECUTION_ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-execution-admission-2.0"
)
OUTPUT_ENTRY_SCHEMA_VERSION = "m3-paper-v2-independent-blind-output-entry-2.0"
OUTPUT_SEAL_SCHEMA_VERSION = "m3-paper-v2-independent-blind-output-seal-2.0"
LABEL_RELEASE_SCHEMA_VERSION = "m3-paper-v2-independent-blind-label-release-2.0"
SCORING_ENTRY_SCHEMA_VERSION = "m3-paper-v2-independent-blind-scoring-entry-2.0"
SCORING_SEAL_SCHEMA_VERSION = "m3-paper-v2-independent-blind-scoring-seal-2.0"
SCORING_ATTESTATION_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-scoring-attestation-2.0"
)
SCORING_ATTESTATION_VERIFIER_RECEIPT_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-scoring-attestation-verifier-receipt-2.0"
)
ED25519_SIGNATURE_SCHEME = "ed25519-detached-sha256-digest-v1"
CONDITIONS = (
    "no_defense",
    "safe_prompt_or_spotlighting",
    "promptguard_detector_only",
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_full",
)
SLOT_BOUND_FIELDS = (
    "slot_id",
    "sample_type",
    "scenario_type",
    "attack_family",
    "language",
    "primary_authorization_regime",
    "independent_author_group",
)
FORBIDDEN_EXECUTION_FIELDS = frozenset(
    {
        "answer_key",
        "evaluation",
        "evaluator",
        "evaluator_label",
        "expected_allowed_effects",
        "expected_outcome",
        "expected_safe_behavior",
        "expected_unsafe_effects",
        "gold",
        "gold_action",
        "gold_answer",
        "gold_label",
        "label",
        "labels",
        "offline_evaluation",
        "task_completion",
        "unsafe_effect",
        "unsafe_target_actions",
    }
)
EXECUTION_CONTENT_FIELDS = frozenset(
    {
        "trusted_app_context",
        "trusted_user_request",
        "untrusted_content",
        "untrusted_memory",
    }
)
EXECUTION_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "dataset_version",
        "slot_id",
        "case_id",
        "split",
        "sample_type",
        "scenario_type",
        "attack_family",
        "language",
        "primary_authorization_regime",
        "independent_author_group",
        "trusted_app_context",
        "trusted_user_request",
        "untrusted_content",
        "untrusted_memory",
        "authoring_provenance",
    }
)
FORBIDDEN_EXECUTION_KEY_MARKERS = (
    "annotation",
    "answer",
    "answerkey",
    "evaluation",
    "evaluator",
    "expectedallowed",
    "expectedoutcome",
    "expectedsafe",
    "expectedunsafe",
    "gold",
    "groundtruth",
    "label",
    "offline",
    "outcome",
    "result",
    "score",
    "taskcompletion",
    "unsafeeffect",
    "unsafetarget",
    "verdict",
)
OUTPUT_ENTRY_FIELDS = frozenset(
    {
        "schema_version",
        "sequence",
        "work_key",
        "slot_id",
        "case_id",
        "condition_id",
        "output_id",
        "effect_receipt_sha256",
        "provider_trace_bundle_sha256",
        "operational_status",
    }
)
TERMINAL_OPERATIONAL_STATUSES = frozenset(
    {
        "completed",
        "diagnostic",
        "max_steps",
        "parse_failure",
        "provider_failure",
        "refusal",
        "timeout",
    }
)
SCORING_ENTRY_FIELDS = frozenset(
    {
        "schema_version",
        "sequence",
        "work_key",
        "slot_id",
        "case_id",
        "condition_id",
        "output_id",
        "output_row_sha256",
        "label_row_sha256",
        "unsafe_effect",
        "task_completion",
        "operational_status",
    }
)
REGISTRATION_VERIFIER_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "verified",
        "registration_manifest_sha256",
        "registration_payload_sha256",
        "custodian_signature_sha256",
        "signature_scheme",
        "signature_key_id",
        "public_key_spki_sha256",
        "custodian_id",
        "offline_identity_evidence_sha256",
        "verifier_id",
        "verified_at",
        "checks",
        "evidence_boundary",
        "manifest_sha256",
    }
)
SIGNATURE_VERIFIER_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "verified",
        "custody_manifest_sha256",
        "custody_manifest_digest",
        "custody_payload_sha256",
        "custodian_signature_sha256",
        "signature_scheme",
        "signature_key_id",
        "public_key_spki_sha256",
        "custodian_id",
        "registration_manifest_sha256",
        "registration_verifier_receipt_sha256",
        "verifier_id",
        "verified_at",
        "verification_implementation",
        "checks",
        "evidence_boundary",
        "manifest_sha256",
    }
)
REGISTRATION_SIGNED_EXCLUSIONS = frozenset(
    {
        "custodian_signature",
        "registration_signature_payload_sha256",
        "manifest_sha256",
    }
)
SIGNED_CUSTODY_EXCLUSIONS = frozenset(
    {"custodian_signature", "custodian_signature_payload_sha256", "manifest_sha256"}
)
SIGNED_SCORING_ATTESTATION_EXCLUSIONS = frozenset(
    {"custodian_signature", "signature_payload_sha256", "manifest_sha256"}
)


class IndependentBlindCloseoutV2Error(ValueError):
    """Raised when a v2 blind authoring or custody invariant fails."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndependentBlindCloseoutV2Error(f"{path}: unreadable JSON") from exc
    if not isinstance(value, dict):
        raise IndependentBlindCloseoutV2Error(f"{path}: expected JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise IndependentBlindCloseoutV2Error(f"{path}: unreadable JSONL") from exc
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            raise IndependentBlindCloseoutV2Error(
                f"{path}:{line_number}: blank JSONL row"
            )
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IndependentBlindCloseoutV2Error(
                f"{path}:{line_number}: invalid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise IndependentBlindCloseoutV2Error(
                f"{path}:{line_number}: expected JSON object"
            )
        rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"".join(canonical_json_bytes(row) + b"\n" for row in rows)
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    core = {key: item for key, item in value.items() if key != "manifest_sha256"}
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _require_manifest_integrity(
    value: Mapping[str, Any], *, schema_version: str, status: str | None = None
) -> None:
    if value.get("schema_version") != schema_version:
        raise IndependentBlindCloseoutV2Error("manifest schema version mismatch")
    if status is not None and value.get("status") != status:
        raise IndependentBlindCloseoutV2Error("manifest status mismatch")
    if value.get("manifest_sha256") != _manifest_sha(value):
        raise IndependentBlindCloseoutV2Error("manifest self-digest mismatch")


def _load_ed25519_public_key(path: Path) -> tuple[Ed25519PublicKey, bytes, str]:
    try:
        pem = path.read_bytes()
        key = serialization.load_pem_public_key(pem)
    except (OSError, ValueError, TypeError) as exc:
        raise IndependentBlindCloseoutV2Error(
            "custodian public key must be readable PEM"
        ) from exc
    if not isinstance(key, Ed25519PublicKey):
        raise IndependentBlindCloseoutV2Error("custodian public key must be Ed25519")
    der = key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(der).hexdigest()
    return key, der, fingerprint


def _decode_ed25519_signature(value: Any) -> bytes:
    try:
        signature = base64.b64decode(str(value), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise IndependentBlindCloseoutV2Error(
            "custodian signature must be canonical base64"
        ) from exc
    if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != value:
        raise IndependentBlindCloseoutV2Error(
            "custodian signature must encode exactly 64 Ed25519 bytes"
        )
    return signature


def _verify_ed25519_digest_signature(
    *, public_key: Ed25519PublicKey, signature_b64: Any, payload_sha256: Any
) -> bool:
    if not _is_sha256(payload_sha256):
        return False
    try:
        signature = _decode_ed25519_signature(signature_b64)
        public_key.verify(signature, bytes.fromhex(str(payload_sha256)))
    except (IndependentBlindCloseoutV2Error, InvalidSignature):
        return False
    return True


def _non_placeholder(value: Any, *, minimum_length: int = 1) -> bool:
    text = str(value or "").strip()
    if len(text) < minimum_length:
        return False
    lowered = text.lower()
    return not (
        (text.startswith("<") and text.endswith(">"))
        or lowered in {"pending", "unknown", "none", "null", "tbd", "todo"}
    )


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else None


def _field_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(child_path)
            paths.extend(_field_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_field_paths(child, f"{prefix}[{index}]"))
    return paths


def _terminal_field_name(path: str) -> str:
    return path.rsplit(".", maxsplit=1)[-1].split("[", maxsplit=1)[0].lower()


def _normalized_semantic_key(path: str) -> str:
    terminal = _terminal_field_name(path)
    return "".join(character for character in terminal if character.isalnum())


def _forbidden_execution_paths(row: Mapping[str, Any]) -> list[str]:
    return sorted(
        path
        for path in _field_paths(row)
        if _terminal_field_name(path) in FORBIDDEN_EXECUTION_FIELDS
        or any(
            marker in _normalized_semantic_key(path)
            for marker in FORBIDDEN_EXECUTION_KEY_MARKERS
        )
    )


def _slots(path: Path = DEFAULT_SLOTS) -> list[dict[str, Any]]:
    if _sha256_file(path) != EXPECTED_SLOTS_SHA256:
        raise IndependentBlindCloseoutV2Error(
            "frozen slots.jsonl SHA-256 does not match the runtime hard lock"
        )
    rows = _read_jsonl(path)
    ids = [str(row.get("slot_id", "")) for row in rows]
    sample_counts = Counter(str(row.get("sample_type", "")) for row in rows)
    author_counts = Counter(str(row.get("independent_author_group", "")) for row in rows)
    if (
        len(rows) != 600
        or len(set(ids)) != 600
        or dict(sample_counts) != EXPECTED_SAMPLE_COUNTS
        or dict(author_counts) != EXPECTED_AUTHOR_GROUP_COUNTS
    ):
        raise IndependentBlindCloseoutV2Error("frozen 600-slot source drift")
    return rows


def _execution_validation(
    rows: Sequence[Mapping[str, Any]],
    slots: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, bool], dict[str, Any]]:
    slot_by_id = {str(slot["slot_id"]): slot for slot in slots}
    expected_ids = [str(slot["slot_id"]) for slot in slots]
    row_ids = [str(row.get("slot_id", "")) for row in rows]
    case_ids = [str(row.get("case_id", "")) for row in rows]
    top_level_drift = {
        str(row.get("slot_id", "")): {
            "missing": sorted(EXECUTION_REQUIRED_FIELDS - set(row)),
            "unexpected": sorted(set(row) - EXECUTION_REQUIRED_FIELDS),
        }
        for row in rows
        if set(row) != EXECUTION_REQUIRED_FIELDS
    }
    forbidden = {
        str(row.get("slot_id", "")): paths
        for row in rows
        if (paths := _forbidden_execution_paths(row))
    }
    mismatched_slots: list[str] = []
    for row in rows:
        slot_id = str(row.get("slot_id", ""))
        slot = slot_by_id.get(slot_id)
        if slot is None or any(row.get(field) != slot.get(field) for field in SLOT_BOUND_FIELDS):
            mismatched_slots.append(slot_id)
    content_complete = all(
        row.get("schema_version") == EXECUTION_SCHEMA_VERSION
        and row.get("dataset_version") == "m3-paper-v2-independent-blind-2.0"
        and _non_placeholder(row.get("case_id"))
        and _non_placeholder(row.get("trusted_user_request"))
        and _non_placeholder(row.get("untrusted_content"))
        and isinstance(row.get("trusted_app_context"), Mapping)
        and isinstance(row.get("untrusted_memory"), list)
        and isinstance(row.get("authoring_provenance"), Mapping)
        and _non_placeholder(row.get("authoring_provenance", {}).get("independent_source_id"))
        for row in rows
    )
    sample_counts = Counter(str(row.get("sample_type", "")) for row in rows)
    author_counts = Counter(str(row.get("independent_author_group", "")) for row in rows)
    checks = {
        "exactly_600_rows": len(rows) == 600,
        "sample_counts_360_120_120": dict(sample_counts) == EXPECTED_SAMPLE_COUNTS,
        "author_groups_300_300": dict(author_counts) == EXPECTED_AUTHOR_GROUP_COUNTS,
        "slot_ids_unique_and_complete": len(set(row_ids)) == 600
        and set(row_ids) == set(expected_ids),
        "slot_order_exact": row_ids == expected_ids,
        "case_ids_unique_and_nonempty": len(set(case_ids)) == 600
        and all(_non_placeholder(case_id) for case_id in case_ids),
        "slot_metadata_matches_frozen_source": not mismatched_slots,
        "top_level_schema_exact": not top_level_drift,
        "execution_content_complete": content_complete,
        "split_is_independent_blind": all(
            row.get("split") == "independent_blind" for row in rows
        ),
        "primary_authorization_regime_present": all(
            _non_placeholder(row.get("primary_authorization_regime")) for row in rows
        ),
        "developer_visible_label_fields_absent": not forbidden,
    }
    diagnostics = {
        "observed_sample_counts": dict(sorted(sample_counts.items())),
        "observed_author_group_counts": dict(sorted(author_counts.items())),
        "mismatched_slot_ids": sorted(mismatched_slots),
        "forbidden_fields_by_slot": forbidden,
        "top_level_schema_drift_by_slot": top_level_drift,
    }
    return checks, diagnostics


def _label_validation(
    labels: Sequence[Mapping[str, Any]],
    executions: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, bool], dict[str, Any]]:
    execution_keys = [
        (str(row.get("slot_id", "")), str(row.get("case_id", "")))
        for row in executions
    ]
    label_keys = [
        (str(row.get("slot_id", "")), str(row.get("case_id", "")))
        for row in labels
    ]
    content_leaks = {
        str(row.get("slot_id", "")): sorted(
            path
            for path in _field_paths(row)
            if _terminal_field_name(path) in EXECUTION_CONTENT_FIELDS
        )
        for row in labels
        if any(
            _terminal_field_name(path) in EXECUTION_CONTENT_FIELDS
            for path in _field_paths(row)
        )
    }
    complete = all(
        row.get("schema_version") == LABEL_SCHEMA_VERSION
        and isinstance(row.get("offline_evaluation"), Mapping)
        and isinstance(row.get("offline_evaluation", {}).get("expected_allowed_effects"), list)
        and isinstance(row.get("offline_evaluation", {}).get("expected_unsafe_effects"), list)
        and _non_placeholder(row.get("offline_evaluation", {}).get("unsafe_effect_rule"))
        and _non_placeholder(row.get("offline_evaluation", {}).get("task_completion_rule"))
        for row in labels
    )
    checks = {
        "exactly_600_label_rows": len(labels) == 600,
        "label_ids_unique": len(set(label_keys)) == 600,
        "label_order_matches_execution": label_keys == execution_keys,
        "label_payload_complete": complete,
        "execution_content_absent_from_label_file": not content_leaks,
    }
    return checks, {"execution_content_leaks_by_slot": content_leaks}


def split_authored_pairs(
    pairs: Sequence[Mapping[str, Any]],
    *,
    slots_path: Path = DEFAULT_SLOTS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministically split custodian-private authoring pairs in slot order."""

    executions: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs, start=1):
        if set(pair) != {"schema_version", "execution", "label"}:
            raise IndependentBlindCloseoutV2Error(
                f"authoring pair {index} has unexpected fields"
            )
        if pair.get("schema_version") != PAIR_SCHEMA_VERSION:
            raise IndependentBlindCloseoutV2Error(
                f"authoring pair {index} has wrong schema version"
            )
        execution = pair.get("execution")
        label = pair.get("label")
        if not isinstance(execution, Mapping) or not isinstance(label, Mapping):
            raise IndependentBlindCloseoutV2Error(
                f"authoring pair {index} lacks execution/label objects"
            )
        executions.append(dict(execution))
        labels.append(dict(label))
    slots = _slots(slots_path)
    execution_checks, _ = _execution_validation(executions, slots)
    label_checks, _ = _label_validation(labels, executions)
    if not all(execution_checks.values()) or not all(label_checks.values()):
        raise IndependentBlindCloseoutV2Error(
            "authored pairs fail deterministic split qualification"
        )
    return executions, labels


def split_authored_bundle(
    *,
    authored_pairs_path: Path,
    execution_output_path: Path,
    label_output_path: Path,
    slots_path: Path = DEFAULT_SLOTS,
) -> dict[str, Any]:
    """Custodian-only file splitter; explicit outputs prevent implicit project data."""

    if execution_output_path.resolve() == label_output_path.resolve():
        raise IndependentBlindCloseoutV2Error(
            "execution and label outputs must be distinct files"
        )
    executions, labels = split_authored_pairs(
        _read_jsonl(authored_pairs_path), slots_path=slots_path
    )
    _write_jsonl(execution_output_path, executions)
    _write_jsonl(label_output_path, labels)
    core = {
        "schema_version": "m3-paper-v2-independent-blind-split-receipt-2.0",
        "status": "custodian_private_split_completed",
        "source_rows": len(executions),
        "execution_set": {
            "filename": execution_output_path.name,
            "rows": len(executions),
            "sha256": _sha256_file(execution_output_path),
        },
        "label_file": {
            "filename": label_output_path.name,
            "rows": len(labels),
            "sha256": _sha256_file(label_output_path),
        },
        "slot_source": {
            "filename": slots_path.name,
            "rows": 600,
            "sha256": _sha256_file(slots_path),
        },
        "evidence_boundary": {
            "intended_operator_role": "independent_custodian",
            "label_file_opened": True,
            "developer_safe_to_run_on_private_labels": False,
            "network_calls_made": 0,
            "project_candidate_created_implicitly": False,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def validate_custodian_pre_release(
    *,
    execution_set_path: Path,
    label_file_path: Path,
    slots_path: Path = DEFAULT_SLOTS,
) -> dict[str, Any]:
    """Validate both halves before the custodian releases only the execution set."""

    if execution_set_path.resolve() == label_file_path.resolve():
        raise IndependentBlindCloseoutV2Error(
            "execution and label files must be distinct"
        )
    executions = _read_jsonl(execution_set_path)
    labels = _read_jsonl(label_file_path)
    execution_checks, execution_diagnostics = _execution_validation(
        executions, _slots(slots_path)
    )
    label_checks, label_diagnostics = _label_validation(labels, executions)
    separation_checks = {
        "execution_and_label_paths_distinct": execution_set_path.resolve()
        != label_file_path.resolve(),
        "execution_and_label_hashes_distinct": _sha256_file(execution_set_path)
        != _sha256_file(label_file_path),
    }
    passed = (
        all(execution_checks.values())
        and all(label_checks.values())
        and all(separation_checks.values())
    )
    core = {
        "schema_version": PRE_RELEASE_SCHEMA_VERSION,
        "status": "custodian_pre_release_passed" if passed else "custodian_pre_release_rejected",
        "execution_set": {
            "filename": execution_set_path.name,
            "rows": len(executions),
            "sha256": _sha256_file(execution_set_path),
        },
        "label_file": {
            "filename": label_file_path.name,
            "rows": len(labels),
            "sha256": _sha256_file(label_file_path),
        },
        "slot_source": {
            "filename": slots_path.name,
            "rows": 600,
            "sha256": _sha256_file(slots_path),
        },
        "execution_checks": execution_checks,
        "label_checks": label_checks,
        "separation_checks": separation_checks,
        "diagnostics": {
            "execution": execution_diagnostics,
            "label": label_diagnostics,
        },
        "evidence_boundary": {
            "intended_operator_role": "independent_custodian",
            "label_file_opened": True,
            "scientific_label_rows_read": len(labels),
            "developer_safe_to_run_on_private_labels": False,
            "execution_authorized": False,
            "result_admission_authorized": False,
            "network_calls_made": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def _release_chain_checks(custody: Mapping[str, Any]) -> dict[str, bool]:
    chain = custody.get("release_chain")
    if not isinstance(chain, Mapping):
        return {
            "release_chain_fields_timezone_aware": False,
            "release_chain_order_valid": False,
            "labels_not_released_before_execution": False,
            "developer_received_no_label_file": False,
        }
    ordered_names = (
        "authoring_completed_at",
        "split_completed_at",
        "sealed_at",
        "execution_set_released_at",
        "developer_received_execution_set_at",
    )
    parsed = [_parse_time(chain.get(name)) for name in ordered_names]
    timezone_aware = all(value is not None for value in parsed)
    ordered = timezone_aware and all(
        left <= right
        for left, right in zip(parsed, parsed[1:])
        if left is not None and right is not None
    )
    return {
        "release_chain_fields_timezone_aware": timezone_aware,
        "release_chain_order_valid": ordered,
        "labels_not_released_before_execution": chain.get("label_file_released_at")
        is None,
        "developer_received_no_label_file": chain.get(
            "developer_received_label_file_at"
        )
        is None,
    }


def registration_signature_payload_sha256(registration: Mapping[str, Any]) -> str:
    """Digest signed by the custodian for the zero-label Day-1 registration."""

    payload = {
        key: item
        for key, item in registration.items()
        if key not in REGISTRATION_SIGNED_EXCLUSIONS
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def build_unsigned_custodian_registration(
    *,
    custodian_id: str,
    project_relationship: str,
    public_key_path: Path,
    confirmed_at: str,
    offline_identity_evidence_sha256: str,
) -> dict[str, Any]:
    """Create the zero-label registration payload; never reads a private key."""

    _, _, fingerprint = _load_ed25519_public_key(public_key_path)
    if not _non_placeholder(custodian_id, minimum_length=3):
        raise IndependentBlindCloseoutV2Error("real custodian identity is required")
    if not _non_placeholder(project_relationship, minimum_length=3):
        raise IndependentBlindCloseoutV2Error("project relationship is required")
    if _parse_time(confirmed_at) is None:
        raise IndependentBlindCloseoutV2Error("confirmed_at must include a timezone")
    if not _is_sha256(offline_identity_evidence_sha256):
        raise IndependentBlindCloseoutV2Error(
            "offline identity evidence must be committed by SHA-256"
        )
    core: dict[str, Any] = {
        "schema_version": REGISTRATION_SCHEMA_VERSION,
        "status": "custodian_registration_signed",
        "custodian_id": custodian_id,
        "project_relationship": project_relationship,
        "independence_attested": True,
        "participated_in_implementation": False,
        "participated_in_threshold_selection": False,
        "participated_in_experiment_tuning": False,
        "labels_embargoed_until_execution_complete": True,
        "developer_must_not_receive_labels_before_scoring": True,
        "signature_scheme": ED25519_SIGNATURE_SCHEME,
        "signature_key_id": f"ed25519-spki-sha256:{fingerprint}",
        "public_key_spki_sha256": fingerprint,
        "offline_identity_evidence_sha256": offline_identity_evidence_sha256,
        "confirmed_at": confirmed_at,
        "label_rows_present": 0,
        "execution_authorized": False,
        "network_calls_made": 0,
    }
    return {
        **core,
        "registration_signature_payload_sha256": (
            registration_signature_payload_sha256(core)
        ),
    }


def finalize_custodian_registration(
    unsigned_registration: Mapping[str, Any], *, custodian_signature: str
) -> dict[str, Any]:
    """Attach a real detached Ed25519 signature; does not access a private key."""

    if unsigned_registration.get("status") != "custodian_registration_signed":
        raise IndependentBlindCloseoutV2Error("unsigned registration status is invalid")
    expected_payload = registration_signature_payload_sha256(unsigned_registration)
    if (
        unsigned_registration.get("registration_signature_payload_sha256")
        != expected_payload
    ):
        raise IndependentBlindCloseoutV2Error("registration payload digest drift")
    _decode_ed25519_signature(custodian_signature)
    final = dict(unsigned_registration)
    final["custodian_signature"] = custodian_signature
    final["registration_signature_payload_sha256"] = (
        registration_signature_payload_sha256(final)
    )
    final["manifest_sha256"] = _manifest_sha(final)
    return final


def verify_custodian_registration(
    *,
    registration_path: Path,
    public_key_path: Path,
    verifier_id: str,
    verified_at: str,
) -> dict[str, Any]:
    """Mathematically verify Day-1 registration and emit a hash-locked receipt."""

    registration = _read_json(registration_path)
    public_key, _, fingerprint = _load_ed25519_public_key(public_key_path)
    payload_sha = registration_signature_payload_sha256(registration)
    signature_valid = _verify_ed25519_digest_signature(
        public_key=public_key,
        signature_b64=registration.get("custodian_signature"),
        payload_sha256=payload_sha,
    )
    checks = {
        "registration_manifest_integrity": registration.get("manifest_sha256")
        == _manifest_sha(registration),
        "registration_schema_v2": registration.get("schema_version")
        == REGISTRATION_SCHEMA_VERSION,
        "registration_status_signed": registration.get("status")
        == "custodian_registration_signed",
        "custodian_identity_present": _non_placeholder(
            registration.get("custodian_id"), minimum_length=3
        ),
        "relationship_present": _non_placeholder(
            registration.get("project_relationship"), minimum_length=3
        ),
        "independence_attested": registration.get("independence_attested") is True,
        "not_implementation_participant": registration.get(
            "participated_in_implementation"
        )
        is False,
        "not_threshold_participant": registration.get(
            "participated_in_threshold_selection"
        )
        is False,
        "not_tuning_participant": registration.get(
            "participated_in_experiment_tuning"
        )
        is False,
        "label_embargo_attested": registration.get(
            "labels_embargoed_until_execution_complete"
        )
        is True,
        "developer_label_embargo_attested": registration.get(
            "developer_must_not_receive_labels_before_scoring"
        )
        is True,
        "confirmed_at_timezone_aware": _parse_time(registration.get("confirmed_at"))
        is not None,
        "offline_identity_evidence_committed": _is_sha256(
            registration.get("offline_identity_evidence_sha256")
        ),
        "signature_scheme_ed25519": registration.get("signature_scheme")
        == ED25519_SIGNATURE_SCHEME,
        "public_key_fingerprint_matches": registration.get(
            "public_key_spki_sha256"
        )
        == fingerprint,
        "key_id_matches_public_key": registration.get("signature_key_id")
        == f"ed25519-spki-sha256:{fingerprint}",
        "payload_digest_matches": registration.get(
            "registration_signature_payload_sha256"
        )
        == payload_sha,
        "signature_math_verified": signature_valid,
        "registration_has_zero_labels": registration.get("label_rows_present") == 0,
        "registration_does_not_authorize_execution": registration.get(
            "execution_authorized"
        )
        is False,
        "verifier_identity_present": _non_placeholder(verifier_id, minimum_length=3),
        "verified_at_timezone_aware": _parse_time(verified_at) is not None,
    }
    passed = all(checks.values())
    signature = registration.get("custodian_signature")
    signature_sha = (
        hashlib.sha256(_decode_ed25519_signature(signature)).hexdigest()
        if signature_valid
        else None
    )
    core = {
        "schema_version": REGISTRATION_VERIFIER_RECEIPT_SCHEMA_VERSION,
        "status": (
            "custodian_registration_verified_clock_may_start"
            if passed
            else "custodian_registration_rejected"
        ),
        "verified": passed,
        "registration_manifest_sha256": _sha256_file(registration_path),
        "registration_payload_sha256": registration.get(
            "registration_signature_payload_sha256"
        ),
        "custodian_signature_sha256": signature_sha,
        "signature_scheme": registration.get("signature_scheme"),
        "signature_key_id": registration.get("signature_key_id"),
        "public_key_spki_sha256": fingerprint,
        "custodian_id": registration.get("custodian_id"),
        "offline_identity_evidence_sha256": registration.get(
            "offline_identity_evidence_sha256"
        ),
        "verifier_id": verifier_id,
        "verified_at": verified_at,
        "checks": checks,
        "evidence_boundary": {
            "signature_math_verified": signature_valid,
            "public_key_control_cryptographically_verified": signature_valid,
            "public_key_real_person_identity_is_offline_attestation": True,
            "offline_identity_evidence_content_opened": False,
            "label_rows_read": 0,
            "execution_authorized": False,
            "clock_start_authorized": passed,
            "network_calls_made": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def _registration_verifier_receipt_checks(
    *,
    registration: Mapping[str, Any],
    registration_path: Path,
    receipt: Mapping[str, Any],
    public_key_path: Path,
) -> dict[str, bool]:
    public_key, _, fingerprint = _load_ed25519_public_key(public_key_path)
    payload_sha = registration_signature_payload_sha256(registration)
    signature_valid = _verify_ed25519_digest_signature(
        public_key=public_key,
        signature_b64=registration.get("custodian_signature"),
        payload_sha256=payload_sha,
    )
    signature_sha = None
    if signature_valid:
        signature_sha = hashlib.sha256(
            _decode_ed25519_signature(registration.get("custodian_signature"))
        ).hexdigest()
    return {
        "registration_receipt_top_level_schema_exact": set(receipt)
        == REGISTRATION_VERIFIER_RECEIPT_FIELDS,
        "registration_manifest_integrity": registration.get("manifest_sha256")
        == _manifest_sha(registration),
        "registration_receipt_manifest_integrity": receipt.get("manifest_sha256")
        == _manifest_sha(receipt),
        "registration_receipt_schema_v2": receipt.get("schema_version")
        == REGISTRATION_VERIFIER_RECEIPT_SCHEMA_VERSION,
        "registration_receipt_status_passed": receipt.get("status")
        == "custodian_registration_verified_clock_may_start",
        "registration_receipt_verified_true": receipt.get("verified") is True,
        "registration_file_digest_bound": receipt.get(
            "registration_manifest_sha256"
        )
        == _sha256_file(registration_path),
        "registration_payload_digest_bound": receipt.get(
            "registration_payload_sha256"
        )
        == payload_sha,
        "registration_signature_bound": receipt.get("custodian_signature_sha256")
        == signature_sha,
        "registration_scheme_bound": receipt.get("signature_scheme")
        == registration.get("signature_scheme")
        == ED25519_SIGNATURE_SCHEME,
        "registration_key_id_bound": receipt.get("signature_key_id")
        == registration.get("signature_key_id")
        == f"ed25519-spki-sha256:{fingerprint}",
        "registration_public_key_bound": receipt.get("public_key_spki_sha256")
        == registration.get("public_key_spki_sha256")
        == fingerprint,
        "registration_custodian_bound": receipt.get("custodian_id")
        == registration.get("custodian_id"),
        "registration_offline_identity_evidence_bound": receipt.get(
            "offline_identity_evidence_sha256"
        )
        == registration.get("offline_identity_evidence_sha256"),
        "registration_verifier_identity_present": _non_placeholder(
            receipt.get("verifier_id"), minimum_length=3
        ),
        "registration_verified_at_timezone_aware": _parse_time(
            receipt.get("verified_at")
        )
        is not None,
        "registration_recorded_checks_all_pass": isinstance(
            receipt.get("checks"), Mapping
        )
        and bool(receipt.get("checks"))
        and all(value is True for value in receipt["checks"].values()),
        "registration_signature_math_reverified": signature_valid,
        "registration_clock_only_not_execution": isinstance(
            receipt.get("evidence_boundary"), Mapping
        )
        and receipt["evidence_boundary"].get("clock_start_authorized") is True
        and receipt["evidence_boundary"].get("execution_authorized") is False,
    }


def custody_signature_payload_sha256(custody: Mapping[str, Any]) -> str:
    """Return the digest an external custodian signature must bind."""

    payload = {
        key: item
        for key, item in custody.items()
        if key not in SIGNED_CUSTODY_EXCLUSIONS
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def build_unsigned_custody_seal(
    *,
    execution_set_path: Path,
    label_file_path: Path,
    pre_release_receipt_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    custodian_public_key_path: Path,
    custodian_id: str,
    custodian_signature_scheme: str,
    custodian_signature_key_id: str,
    authoring_completed_at: str,
    split_completed_at: str,
    sealed_at: str,
    execution_set_released_at: str,
    developer_received_execution_set_at: str,
    slots_path: Path = DEFAULT_SLOTS,
) -> dict[str, Any]:
    """Build the deterministic payload to be signed by the real custodian."""

    pre_release = validate_custodian_pre_release(
        execution_set_path=execution_set_path,
        label_file_path=label_file_path,
        slots_path=slots_path,
    )
    if pre_release["status"] != "custodian_pre_release_passed":
        raise IndependentBlindCloseoutV2Error(
            "cannot seal a rejected execution/label split"
        )
    recorded_pre_release = _read_json(pre_release_receipt_path)
    if recorded_pre_release != pre_release:
        raise IndependentBlindCloseoutV2Error(
            "pre-release receipt does not reproduce the current execution/label split"
        )
    registration = _read_json(registration_path)
    registration_receipt = _read_json(registration_verifier_receipt_path)
    registration_recheck = _registration_verifier_receipt_checks(
        registration=registration,
        registration_path=registration_path,
        receipt=registration_receipt,
        public_key_path=custodian_public_key_path,
    )
    if not all(registration_recheck.values()):
        raise IndependentBlindCloseoutV2Error(
            "a cryptographically verified Day-1 custodian registration is required"
        )
    if not _non_placeholder(custodian_id, minimum_length=3):
        raise IndependentBlindCloseoutV2Error("real custodian identity is required")
    if custodian_signature_scheme != ED25519_SIGNATURE_SCHEME:
        raise IndependentBlindCloseoutV2Error("Ed25519 custody signature is required")
    if not _non_placeholder(custodian_signature_key_id, minimum_length=3):
        raise IndependentBlindCloseoutV2Error("signature key identity is required")
    if custodian_id != registration.get("custodian_id"):
        raise IndependentBlindCloseoutV2Error("custodian differs from Day-1 registration")
    if custodian_signature_key_id != registration.get("signature_key_id"):
        raise IndependentBlindCloseoutV2Error("custodian key differs from Day-1 registration")
    core: dict[str, Any] = {
        "schema_version": CUSTODY_SCHEMA_VERSION,
        "status": "execution_released_labels_sealed",
        "candidate_filename": execution_set_path.name,
        "candidate_row_count": 600,
        "candidate_sha256": pre_release["execution_set"]["sha256"],
        "label_file_filename": label_file_path.name,
        "label_file_row_count": 600,
        "label_file_sha256": pre_release["label_file"]["sha256"],
        "custodian_id": custodian_id,
        "custodian_independence_attested": True,
        "custodian_participated_in_implementation": False,
        "custodian_signature_scheme": custodian_signature_scheme,
        "custodian_signature_key_id": custodian_signature_key_id,
        "developer_access_before_seal": False,
        "developer_label_access_before_execution": False,
        "execution_and_label_files_distinct": True,
        "release_phase": "execution_only_pre_scoring",
        "release_chain": {
            "authoring_completed_at": authoring_completed_at,
            "split_completed_at": split_completed_at,
            "sealed_at": sealed_at,
            "execution_set_released_at": execution_set_released_at,
            "developer_received_execution_set_at": developer_received_execution_set_at,
            "label_file_released_at": None,
            "developer_received_label_file_at": None,
        },
        "pre_release_manifest_sha256": pre_release["manifest_sha256"],
        "registration_manifest_sha256": registration.get("manifest_sha256"),
        "registration_verifier_receipt_sha256": _sha256_file(
            registration_verifier_receipt_path
        ),
        "slot_source_sha256": EXPECTED_SLOTS_SHA256,
    }
    if not all(_release_chain_checks(core).values()):
        raise IndependentBlindCloseoutV2Error("custody release order is invalid")
    return {
        **core,
        "custodian_signature_payload_sha256": custody_signature_payload_sha256(core),
    }


def finalize_custody_seal(
    unsigned_custody: Mapping[str, Any], *, custodian_signature: str
) -> dict[str, Any]:
    """Attach a non-placeholder detached signature without fabricating one."""

    if unsigned_custody.get("status") != "execution_released_labels_sealed":
        raise IndependentBlindCloseoutV2Error("unsigned custody status is invalid")
    expected_payload = custody_signature_payload_sha256(unsigned_custody)
    if unsigned_custody.get("custodian_signature_payload_sha256") != expected_payload:
        raise IndependentBlindCloseoutV2Error("unsigned custody payload digest drift")
    _decode_ed25519_signature(custodian_signature)
    final = dict(unsigned_custody)
    final["custodian_signature"] = custodian_signature
    final["custodian_signature_payload_sha256"] = custody_signature_payload_sha256(
        final
    )
    final["manifest_sha256"] = _manifest_sha(final)
    return final


def _pre_release_receipt_checks(
    *,
    receipt: Mapping[str, Any],
    receipt_path: Path,
    custody: Mapping[str, Any],
    execution_sha256: str,
) -> dict[str, bool]:
    execution = receipt.get("execution_set")
    label = receipt.get("label_file")
    slot_source = receipt.get("slot_source")
    evidence = receipt.get("evidence_boundary")
    recorded_groups = (
        receipt.get("execution_checks")
        if isinstance(receipt.get("execution_checks"), Mapping)
        else {}
    )
    label_checks = (
        receipt.get("label_checks")
        if isinstance(receipt.get("label_checks"), Mapping)
        else {}
    )
    separation_checks = (
        receipt.get("separation_checks")
        if isinstance(receipt.get("separation_checks"), Mapping)
        else {}
    )
    return {
        "pre_release_receipt_schema_v2": receipt.get("schema_version")
        == PRE_RELEASE_SCHEMA_VERSION,
        "pre_release_receipt_status_passed": receipt.get("status")
        == "custodian_pre_release_passed",
        "pre_release_receipt_manifest_integrity": receipt.get("manifest_sha256")
        == _manifest_sha(receipt),
        "pre_release_receipt_file_digest_available": _is_sha256(
            _sha256_file(receipt_path)
        ),
        "pre_release_manifest_bound_by_custody": custody.get(
            "pre_release_manifest_sha256"
        )
        == receipt.get("manifest_sha256"),
        "pre_release_execution_rows_600": isinstance(execution, Mapping)
        and execution.get("rows") == 600,
        "pre_release_execution_hash_bound": isinstance(execution, Mapping)
        and execution.get("sha256") == execution_sha256
        == custody.get("candidate_sha256"),
        "pre_release_execution_filename_bound": isinstance(execution, Mapping)
        and execution.get("filename") == custody.get("candidate_filename"),
        "pre_release_label_rows_600": isinstance(label, Mapping)
        and label.get("rows") == 600
        == custody.get("label_file_row_count"),
        "pre_release_label_hash_bound": isinstance(label, Mapping)
        and label.get("sha256") == custody.get("label_file_sha256"),
        "pre_release_label_filename_bound": isinstance(label, Mapping)
        and label.get("filename") == custody.get("label_file_filename"),
        "pre_release_slot_source_hard_locked": isinstance(slot_source, Mapping)
        and slot_source.get("rows") == 600
        and slot_source.get("sha256") == EXPECTED_SLOTS_SHA256
        == custody.get("slot_source_sha256"),
        "pre_release_execution_checks_all_pass": bool(recorded_groups)
        and all(value is True for value in recorded_groups.values()),
        "pre_release_label_checks_all_pass": bool(label_checks)
        and all(value is True for value in label_checks.values()),
        "pre_release_separation_checks_all_pass": bool(separation_checks)
        and all(value is True for value in separation_checks.values()),
        "pre_release_custodian_boundary_recorded": isinstance(evidence, Mapping)
        and evidence.get("intended_operator_role") == "independent_custodian"
        and evidence.get("label_file_opened") is True
        and evidence.get("execution_authorized") is False
        and evidence.get("result_admission_authorized") is False
        and evidence.get("network_calls_made") == 0,
    }


def verify_custody_signature(
    *,
    custody_manifest_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    public_key_path: Path,
    verifier_id: str,
    verified_at: str,
) -> dict[str, Any]:
    """Reverify Ed25519 custody authenticity and emit a non-self-authorizing receipt."""

    custody = _read_json(custody_manifest_path)
    registration = _read_json(registration_path)
    registration_receipt = _read_json(registration_verifier_receipt_path)
    public_key, _, fingerprint = _load_ed25519_public_key(public_key_path)
    registration_checks = _registration_verifier_receipt_checks(
        registration=registration,
        registration_path=registration_path,
        receipt=registration_receipt,
        public_key_path=public_key_path,
    )
    payload_sha = custody_signature_payload_sha256(custody)
    signature_valid = _verify_ed25519_digest_signature(
        public_key=public_key,
        signature_b64=custody.get("custodian_signature"),
        payload_sha256=payload_sha,
    )
    signature_sha = None
    if signature_valid:
        signature_sha = hashlib.sha256(
            _decode_ed25519_signature(custody.get("custodian_signature"))
        ).hexdigest()
    checks = {
        "custody_manifest_integrity": custody.get("manifest_sha256")
        == _manifest_sha(custody),
        "custody_schema_v2": custody.get("schema_version") == CUSTODY_SCHEMA_VERSION,
        "custody_status_sealed": custody.get("status")
        == "execution_released_labels_sealed",
        "custody_payload_digest_matches": custody.get(
            "custodian_signature_payload_sha256"
        )
        == payload_sha,
        "custodian_signature_scheme_ed25519": custody.get(
            "custodian_signature_scheme"
        )
        == ED25519_SIGNATURE_SCHEME,
        "custodian_key_matches_public_key": custody.get(
            "custodian_signature_key_id"
        )
        == f"ed25519-spki-sha256:{fingerprint}",
        "custodian_signature_math_verified": signature_valid,
        "registration_receipt_reverified": all(registration_checks.values()),
        "custodian_matches_registration": custody.get("custodian_id")
        == registration.get("custodian_id"),
        "registration_manifest_bound": custody.get(
            "registration_manifest_sha256"
        )
        == registration.get("manifest_sha256"),
        "registration_verifier_receipt_bound": custody.get(
            "registration_verifier_receipt_sha256"
        )
        == _sha256_file(registration_verifier_receipt_path),
        "verifier_identity_present": _non_placeholder(verifier_id, minimum_length=3),
        "verified_at_timezone_aware": _parse_time(verified_at) is not None,
    }
    passed = all(checks.values())
    core = {
        "schema_version": SIGNATURE_VERIFIER_RECEIPT_SCHEMA_VERSION,
        "status": (
            "custody_signature_cryptographically_verified"
            if passed
            else "custody_signature_rejected"
        ),
        "verified": passed,
        "custody_manifest_sha256": _sha256_file(custody_manifest_path),
        "custody_manifest_digest": custody.get("manifest_sha256"),
        "custody_payload_sha256": custody.get(
            "custodian_signature_payload_sha256"
        ),
        "custodian_signature_sha256": signature_sha,
        "signature_scheme": custody.get("custodian_signature_scheme"),
        "signature_key_id": custody.get("custodian_signature_key_id"),
        "public_key_spki_sha256": fingerprint,
        "custodian_id": custody.get("custodian_id"),
        "registration_manifest_sha256": registration.get("manifest_sha256"),
        "registration_verifier_receipt_sha256": _sha256_file(
            registration_verifier_receipt_path
        ),
        "verifier_id": verifier_id,
        "verified_at": verified_at,
        "verification_implementation": (
            "cryptography.Ed25519PublicKey.verify over raw SHA-256 digest bytes"
        ),
        "checks": checks,
        "evidence_boundary": {
            "signature_math_verified": signature_valid,
            "public_key_control_cryptographically_verified": signature_valid,
            "public_key_real_person_identity_is_offline_attestation": True,
            "verified_true_cannot_replace_mathematical_reverification": True,
            "label_file_opened": False,
            "label_rows_read": 0,
            "execution_authorized": False,
            "network_calls_made": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def _custody_signature_receipt_checks(
    *,
    custody: Mapping[str, Any],
    custody_manifest_path: Path,
    receipt: Mapping[str, Any],
    public_key_path: Path,
) -> dict[str, bool]:
    public_key, _, fingerprint = _load_ed25519_public_key(public_key_path)
    payload_sha = custody_signature_payload_sha256(custody)
    signature_valid = _verify_ed25519_digest_signature(
        public_key=public_key,
        signature_b64=custody.get("custodian_signature"),
        payload_sha256=payload_sha,
    )
    signature_sha = None
    if signature_valid:
        signature_sha = hashlib.sha256(
            _decode_ed25519_signature(custody.get("custodian_signature"))
        ).hexdigest()
    checks = receipt.get("checks") if isinstance(receipt.get("checks"), Mapping) else {}
    evidence = (
        receipt.get("evidence_boundary")
        if isinstance(receipt.get("evidence_boundary"), Mapping)
        else {}
    )
    return {
        "signature_receipt_top_level_schema_exact": set(receipt)
        == SIGNATURE_VERIFIER_RECEIPT_FIELDS,
        "signature_receipt_schema_v2": receipt.get("schema_version")
        == SIGNATURE_VERIFIER_RECEIPT_SCHEMA_VERSION,
        "signature_receipt_status_passed": receipt.get("status")
        == "custody_signature_cryptographically_verified",
        "signature_receipt_verified_true": receipt.get("verified") is True,
        "signature_receipt_manifest_integrity": receipt.get("manifest_sha256")
        == _manifest_sha(receipt),
        "signature_receipt_custody_file_bound": receipt.get(
            "custody_manifest_sha256"
        )
        == _sha256_file(custody_manifest_path),
        "signature_receipt_custody_manifest_bound": receipt.get(
            "custody_manifest_digest"
        )
        == custody.get("manifest_sha256"),
        "signature_receipt_payload_bound": receipt.get("custody_payload_sha256")
        == payload_sha
        == custody.get("custodian_signature_payload_sha256"),
        "signature_receipt_signature_bound": receipt.get(
            "custodian_signature_sha256"
        )
        == signature_sha,
        "signature_receipt_scheme_bound": receipt.get("signature_scheme")
        == custody.get("custodian_signature_scheme")
        == ED25519_SIGNATURE_SCHEME,
        "signature_receipt_key_bound": receipt.get("signature_key_id")
        == custody.get("custodian_signature_key_id")
        == f"ed25519-spki-sha256:{fingerprint}",
        "signature_receipt_public_key_bound": receipt.get(
            "public_key_spki_sha256"
        )
        == fingerprint,
        "signature_receipt_custodian_bound": receipt.get("custodian_id")
        == custody.get("custodian_id"),
        "signature_receipt_verifier_identity_present": _non_placeholder(
            receipt.get("verifier_id"), minimum_length=3
        ),
        "signature_receipt_verified_at_timezone_aware": _parse_time(
            receipt.get("verified_at")
        )
        is not None,
        "signature_receipt_recorded_checks_all_pass": bool(checks)
        and all(value is True for value in checks.values()),
        "signature_receipt_math_reverified": signature_valid,
        "signature_receipt_did_not_self_authorize": evidence.get(
            "execution_authorized"
        )
        is False
        and evidence.get(
            "verified_true_cannot_replace_mathematical_reverification"
        )
        is True,
    }


def audit_developer_execution_import(
    *,
    execution_set_path: Path,
    custody_manifest_path: Path,
    pre_release_receipt_path: Path,
    signature_verifier_receipt_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    custodian_public_key_path: Path,
    slots_path: Path = DEFAULT_SLOTS,
) -> dict[str, Any]:
    """Import the label-free set without accepting or opening the label file."""

    execution_set_path = execution_set_path.resolve()
    custody_manifest_path = custody_manifest_path.resolve()
    required_paths = (
        execution_set_path,
        custody_manifest_path,
        pre_release_receipt_path.resolve(),
        signature_verifier_receipt_path.resolve(),
        registration_path.resolve(),
        registration_verifier_receipt_path.resolve(),
        custodian_public_key_path.resolve(),
    )
    if not all(path.is_file() for path in required_paths):
        raise IndependentBlindCloseoutV2Error(
            "execution, custody, pre-release, registration, verifier receipts, and public key are required"
        )
    executions = _read_jsonl(execution_set_path)
    custody = _read_json(custody_manifest_path)
    pre_release_receipt = _read_json(pre_release_receipt_path)
    signature_receipt = _read_json(signature_verifier_receipt_path)
    registration = _read_json(registration_path)
    registration_receipt = _read_json(registration_verifier_receipt_path)
    execution_checks, diagnostics = _execution_validation(
        executions, _slots(slots_path)
    )
    candidate_sha = _sha256_file(execution_set_path)
    label_filename = str(custody.get("label_file_filename", ""))
    developer_visible_label_paths = {
        execution_set_path.parent / label_filename,
        custody_manifest_path.parent / label_filename,
    }
    label_not_visible = bool(label_filename) and not any(
        path.is_file() for path in developer_visible_label_paths
    )
    release_checks = _release_chain_checks(custody)
    expected_signature_payload = custody_signature_payload_sha256(custody)
    pre_release_checks = _pre_release_receipt_checks(
        receipt=pre_release_receipt,
        receipt_path=pre_release_receipt_path,
        custody=custody,
        execution_sha256=candidate_sha,
    )
    registration_checks = _registration_verifier_receipt_checks(
        registration=registration,
        registration_path=registration_path,
        receipt=registration_receipt,
        public_key_path=custodian_public_key_path,
    )
    signature_receipt_checks = _custody_signature_receipt_checks(
        custody=custody,
        custody_manifest_path=custody_manifest_path,
        receipt=signature_receipt,
        public_key_path=custodian_public_key_path,
    )
    custody_checks = {
        "custody_manifest_integrity": custody.get("manifest_sha256")
        == _manifest_sha(custody),
        "custody_schema_v2": custody.get("schema_version") == CUSTODY_SCHEMA_VERSION,
        "custody_status_sealed": custody.get("status")
        == "execution_released_labels_sealed",
        "candidate_filename_matches": custody.get("candidate_filename")
        == execution_set_path.name,
        "candidate_row_count_matches": custody.get("candidate_row_count") == 600,
        "candidate_sha256_matches": custody.get("candidate_sha256") == candidate_sha,
        "label_filename_declared_and_distinct": _non_placeholder(label_filename)
        and label_filename != execution_set_path.name,
        "label_row_count_declared": custody.get("label_file_row_count") == 600,
        "label_file_sha256_declared": _is_sha256(
            custody.get("label_file_sha256")
        ),
        "candidate_and_label_hashes_distinct": custody.get("candidate_sha256")
        != custody.get("label_file_sha256"),
        "custodian_identity_present": _non_placeholder(
            custody.get("custodian_id"), minimum_length=3
        ),
        "custodian_independence_attested": custody.get(
            "custodian_independence_attested"
        )
        is True,
        "custodian_not_implementer": custody.get(
            "custodian_participated_in_implementation"
        )
        is False,
        "signature_scheme_present": _non_placeholder(
            custody.get("custodian_signature_scheme"), minimum_length=3
        ),
        "signature_key_identity_present": _non_placeholder(
            custody.get("custodian_signature_key_id"), minimum_length=3
        ),
        "custodian_signature_present": _non_placeholder(
            custody.get("custodian_signature"), minimum_length=16
        ),
        "signature_payload_digest_matches": custody.get(
            "custodian_signature_payload_sha256"
        )
        == expected_signature_payload,
        "signature_scheme_is_supported_ed25519": custody.get(
            "custodian_signature_scheme"
        )
        == ED25519_SIGNATURE_SCHEME,
        "slot_source_sha256_hard_locked": custody.get("slot_source_sha256")
        == EXPECTED_SLOTS_SHA256,
        "registration_manifest_bound": custody.get(
            "registration_manifest_sha256"
        )
        == registration.get("manifest_sha256"),
        "registration_verifier_receipt_bound": custody.get(
            "registration_verifier_receipt_sha256"
        )
        == _sha256_file(registration_verifier_receipt_path),
        "developer_had_no_preseal_access": custody.get(
            "developer_access_before_seal"
        )
        is False,
        "developer_had_no_label_access": custody.get(
            "developer_label_access_before_execution"
        )
        is False,
        "execution_and_label_files_declared_distinct": custody.get(
            "execution_and_label_files_distinct"
        )
        is True,
        "release_phase_execution_only": custody.get("release_phase")
        == "execution_only_pre_scoring",
        "declared_label_file_not_developer_visible": label_not_visible,
        **release_checks,
    }
    passed = (
        all(execution_checks.values())
        and all(custody_checks.values())
        and all(pre_release_checks.values())
        and all(registration_checks.values())
        and all(signature_receipt_checks.values())
    )
    core = {
        "schema_version": EXECUTION_ADMISSION_SCHEMA_VERSION,
        "status": (
            "sealed_execution_set_v2_technically_admitted_labels_unopened"
            if passed
            else "sealed_execution_set_v2_rejected"
        ),
        "execution_set": {
            "filename": execution_set_path.name,
            "rows": len(executions),
            "sha256": candidate_sha,
            "slot_id_sequence_sha256": hashlib.sha256(
                canonical_json_bytes(
                    [str(row.get("slot_id", "")) for row in executions]
                )
            ).hexdigest(),
            "case_id_sequence_sha256": hashlib.sha256(
                canonical_json_bytes(
                    [str(row.get("case_id", "")) for row in executions]
                )
            ).hexdigest(),
            "observed_slot_source_sha256": _sha256_file(slots_path),
        },
        "custody_manifest": {
            "sha256": _sha256_file(custody_manifest_path),
            "custodian_id": custody.get("custodian_id"),
            "label_file_sha256": custody.get("label_file_sha256"),
            "custodian_signature_payload_sha256": custody.get(
                "custodian_signature_payload_sha256"
            ),
            "manifest_digest": custody.get("manifest_sha256"),
        },
        "pre_release_receipt": {
            "sha256": _sha256_file(pre_release_receipt_path),
            "manifest_sha256": pre_release_receipt.get("manifest_sha256"),
        },
        "signature_verifier_receipt": {
            "sha256": _sha256_file(signature_verifier_receipt_path),
            "manifest_sha256": signature_receipt.get("manifest_sha256"),
        },
        "registration": {
            "sha256": _sha256_file(registration_path),
            "manifest_sha256": registration.get("manifest_sha256"),
            "verifier_receipt_sha256": _sha256_file(
                registration_verifier_receipt_path
            ),
        },
        "execution_checks": execution_checks,
        "custody_checks": custody_checks,
        "pre_release_checks": pre_release_checks,
        "registration_checks": registration_checks,
        "signature_verifier_checks": signature_receipt_checks,
        "diagnostics": diagnostics,
        "evidence_boundary": {
            "label_file_argument_accepted": False,
            "label_file_opened": False,
            "developer_visible_label_file_found": not label_not_visible,
            "scientific_label_rows_read": 0,
            "network_calls_made": 0,
            "provider_calls_made": 0,
            "execution_authorized": passed,
            "result_admission_authorized": False,
            "signature_payload_binding_validated": custody_checks[
                "signature_payload_digest_matches"
            ],
            "signature_authenticity_cryptographically_verified": all(
                signature_receipt_checks.values()
            ),
            "signature_authenticity_requires_external_receipt": True,
            "signature_receipt_verified_true_was_not_trusted_without_math": True,
            "public_key_real_person_identity_is_offline_attestation": True,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def _require_passing_admission(
    *, admission: Mapping[str, Any], admission_path: Path, execution_set_path: Path
) -> None:
    _require_manifest_integrity(
        admission,
        schema_version=EXECUTION_ADMISSION_SCHEMA_VERSION,
        status="sealed_execution_set_v2_technically_admitted_labels_unopened",
    )
    if admission.get("evidence_boundary", {}).get("execution_authorized") is not True:
        raise IndependentBlindCloseoutV2Error("execution admission is not authorized")
    if admission.get("evidence_boundary", {}).get("scientific_label_rows_read") != 0:
        raise IndependentBlindCloseoutV2Error("execution admission crossed label boundary")
    if admission.get("execution_set", {}).get("sha256") != _sha256_file(
        execution_set_path
    ):
        raise IndependentBlindCloseoutV2Error("execution set drift after admission")
    if not _is_sha256(_sha256_file(admission_path)):
        raise IndependentBlindCloseoutV2Error("admission file digest unavailable")


def _output_package_validation(
    rows: Sequence[Mapping[str, Any]], executions: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, bool], dict[str, Any]]:
    expected = [
        (str(execution["slot_id"]), str(execution["case_id"]), condition)
        for execution in executions
        for condition in CONDITIONS
    ]
    observed = [
        (
            str(row.get("slot_id", "")),
            str(row.get("case_id", "")),
            str(row.get("condition_id", "")),
        )
        for row in rows
    ]
    schema_drift = {
        str(index): {
            "missing": sorted(OUTPUT_ENTRY_FIELDS - set(row)),
            "unexpected": sorted(set(row) - OUTPUT_ENTRY_FIELDS),
        }
        for index, row in enumerate(rows, start=1)
        if set(row) != OUTPUT_ENTRY_FIELDS
    }
    semantic_leaks = {
        str(index): _forbidden_execution_paths(row)
        for index, row in enumerate(rows, start=1)
        if _forbidden_execution_paths(row)
    }
    sequences = [row.get("sequence") for row in rows]
    work_keys = [str(row.get("work_key", "")) for row in rows]
    output_ids = [str(row.get("output_id", "")) for row in rows]
    checks = {
        "exactly_3600_terminal_rows": len(rows) == 3600,
        "top_level_schema_exact": not schema_drift,
        "content_and_result_semantic_keys_absent": not semantic_leaks,
        "schema_versions_exact": all(
            row.get("schema_version") == OUTPUT_ENTRY_SCHEMA_VERSION for row in rows
        ),
        "source_case_condition_order_exact": observed == expected,
        "sequences_exact": sequences == list(range(1, 3601)),
        "work_keys_unique_nonempty": len(set(work_keys)) == 3600
        and all(_non_placeholder(value) for value in work_keys),
        "output_ids_unique_nonempty": len(set(output_ids)) == 3600
        and all(_non_placeholder(value) for value in output_ids),
        "receipt_hashes_complete": all(
            _is_sha256(row.get("effect_receipt_sha256"))
            and _is_sha256(row.get("provider_trace_bundle_sha256"))
            for row in rows
        ),
        "all_rows_terminal_in_itt": all(
            row.get("operational_status") in TERMINAL_OPERATIONAL_STATUSES
            for row in rows
        ),
    }
    return checks, {
        "top_level_schema_drift": schema_drift,
        "semantic_leaks": semantic_leaks,
    }


def seal_execution_complete_output_package(
    *,
    execution_set_path: Path,
    custody_manifest_path: Path,
    execution_admission_path: Path,
    output_package_path: Path,
    completed_at: str,
) -> dict[str, Any]:
    """Seal 3,600 content-free terminal output references after model execution."""

    admission = _read_json(execution_admission_path)
    custody = _read_json(custody_manifest_path)
    _require_passing_admission(
        admission=admission,
        admission_path=execution_admission_path,
        execution_set_path=execution_set_path,
    )
    completed_time = _parse_time(completed_at)
    received_time = _parse_time(
        custody.get("release_chain", {}).get("developer_received_execution_set_at")
    )
    if completed_time is None or received_time is None or completed_time < received_time:
        raise IndependentBlindCloseoutV2Error(
            "execution completion must be timezone-aware and after execution-set receipt"
        )
    executions = _read_jsonl(execution_set_path)
    execution_checks, _ = _execution_validation(executions, _slots())
    rows = _read_jsonl(output_package_path)
    output_checks, diagnostics = _output_package_validation(rows, executions)
    custody_bound = admission.get("custody_manifest", {}).get("sha256") == _sha256_file(
        custody_manifest_path
    )
    passed = (
        all(execution_checks.values())
        and all(output_checks.values())
        and custody_bound
    )
    core = {
        "schema_version": OUTPUT_SEAL_SCHEMA_VERSION,
        "status": (
            "execution_complete_content_free_output_package_sealed"
            if passed
            else "execution_output_package_rejected"
        ),
        "completed_at": completed_at,
        "execution_set_sha256": _sha256_file(execution_set_path),
        "custody_manifest_sha256": _sha256_file(custody_manifest_path),
        "execution_admission_sha256": _sha256_file(execution_admission_path),
        "execution_admission_manifest_sha256": admission.get("manifest_sha256"),
        "output_package": {
            "filename": output_package_path.name,
            "rows": len(rows),
            "sha256": _sha256_file(output_package_path),
        },
        "execution_checks": execution_checks,
        "output_checks": output_checks,
        "custody_bound": custody_bound,
        "diagnostics": diagnostics,
        "evidence_boundary": {
            "output_content_included": False,
            "scientific_results_included": False,
            "label_file_opened": False,
            "label_rows_read": 0,
            "developer_received_label_file_before_completion": False,
            "execution_complete": passed,
            "result_admission_authorized": False,
            "network_calls_made_by_sealer": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def release_labels_to_custodian_scoring(
    *,
    custody_manifest_path: Path,
    label_file_path: Path,
    execution_output_seal_path: Path,
    released_at: str,
    custodian_id: str,
) -> dict[str, Any]:
    """Release labels only to the custodian scoring process after execution."""

    custody = _read_json(custody_manifest_path)
    output_seal = _read_json(execution_output_seal_path)
    _require_manifest_integrity(
        output_seal,
        schema_version=OUTPUT_SEAL_SCHEMA_VERSION,
        status="execution_complete_content_free_output_package_sealed",
    )
    labels = _read_jsonl(label_file_path)
    release_time = _parse_time(released_at)
    completion_time = _parse_time(output_seal.get("completed_at"))
    checks = {
        "release_time_timezone_aware": release_time is not None,
        "execution_completion_time_timezone_aware": completion_time is not None,
        "release_after_execution_complete": release_time is not None
        and completion_time is not None
        and release_time >= completion_time,
        "custody_manifest_bound": output_seal.get("custody_manifest_sha256")
        == _sha256_file(custody_manifest_path),
        "custodian_identity_bound": custody.get("custodian_id") == custodian_id,
        "label_rows_600": len(labels) == 600
        == custody.get("label_file_row_count"),
        "label_hash_bound": _sha256_file(label_file_path)
        == custody.get("label_file_sha256"),
        "labels_were_sealed_before_execution": custody.get("release_chain", {}).get(
            "label_file_released_at"
        )
        is None,
        "developer_had_no_label_before_execution": custody.get(
            "developer_label_access_before_execution"
        )
        is False,
    }
    passed = all(checks.values())
    core = {
        "schema_version": LABEL_RELEASE_SCHEMA_VERSION,
        "status": (
            "labels_released_to_custodian_scoring_only"
            if passed
            else "label_release_rejected"
        ),
        "released_at": released_at,
        "custodian_id": custodian_id,
        "custody_manifest_sha256": _sha256_file(custody_manifest_path),
        "execution_output_seal_sha256": _sha256_file(execution_output_seal_path),
        "execution_output_seal_manifest_sha256": output_seal.get("manifest_sha256"),
        "label_file": {
            "filename": label_file_path.name,
            "rows": len(labels),
            "sha256": _sha256_file(label_file_path),
        },
        "checks": checks,
        "evidence_boundary": {
            "label_receiver_role": "independent_custodian_scoring_process",
            "developer_received_label_file": False,
            "developer_label_rows_read": 0,
            "label_file_opened_by_custodian": True,
            "scoring_completed": False,
            "result_admission_authorized": False,
            "network_calls_made": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def _scoring_validation(
    *,
    scores: Sequence[Mapping[str, Any]],
    outputs: Sequence[Mapping[str, Any]],
    labels: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, bool], dict[str, Any]]:
    label_by_case = {
        (str(row.get("slot_id")), str(row.get("case_id"))): row for row in labels
    }
    schema_drift = {
        str(index): {
            "missing": sorted(SCORING_ENTRY_FIELDS - set(row)),
            "unexpected": sorted(set(row) - SCORING_ENTRY_FIELDS),
        }
        for index, row in enumerate(scores, start=1)
        if set(row) != SCORING_ENTRY_FIELDS
    }
    bindings_valid = True
    for score, output in zip(scores, outputs):
        label = label_by_case.get(
            (str(output.get("slot_id")), str(output.get("case_id")))
        )
        expected_fields = ("sequence", "work_key", "slot_id", "case_id", "condition_id", "output_id")
        if (
            label is None
            or any(score.get(field) != output.get(field) for field in expected_fields)
            or score.get("output_row_sha256")
            != hashlib.sha256(canonical_json_bytes(output)).hexdigest()
            or score.get("label_row_sha256")
            != hashlib.sha256(canonical_json_bytes(label)).hexdigest()
        ):
            bindings_valid = False
            break
    checks = {
        "exactly_3600_scored_rows": len(scores) == len(outputs) == 3600,
        "top_level_schema_exact": not schema_drift,
        "schema_versions_exact": all(
            row.get("schema_version") == SCORING_ENTRY_SCHEMA_VERSION for row in scores
        ),
        "score_rows_bind_output_and_private_label": bindings_valid,
        "scientific_flags_boolean": all(
            isinstance(row.get("unsafe_effect"), bool)
            and isinstance(row.get("task_completion"), bool)
            for row in scores
        ),
        "operational_status_preserved": all(
            score.get("operational_status") == output.get("operational_status")
            for score, output in zip(scores, outputs)
        ),
    }
    return checks, {"top_level_schema_drift": schema_drift}


def seal_custodian_scoring_results(
    *,
    custody_manifest_path: Path,
    execution_output_seal_path: Path,
    output_package_path: Path,
    label_release_seal_path: Path,
    label_file_path: Path,
    scoring_results_path: Path,
    scored_at: str,
    custodian_id: str,
) -> dict[str, Any]:
    """Seal custodian-scored 3,600-row results without releasing private labels."""

    custody = _read_json(custody_manifest_path)
    output_seal = _read_json(execution_output_seal_path)
    release = _read_json(label_release_seal_path)
    _require_manifest_integrity(
        output_seal,
        schema_version=OUTPUT_SEAL_SCHEMA_VERSION,
        status="execution_complete_content_free_output_package_sealed",
    )
    _require_manifest_integrity(
        release,
        schema_version=LABEL_RELEASE_SCHEMA_VERSION,
        status="labels_released_to_custodian_scoring_only",
    )
    outputs = _read_jsonl(output_package_path)
    labels = _read_jsonl(label_file_path)
    scores = _read_jsonl(scoring_results_path)
    scoring_checks, diagnostics = _scoring_validation(
        scores=scores, outputs=outputs, labels=labels
    )
    scored_time = _parse_time(scored_at)
    release_time = _parse_time(release.get("released_at"))
    chain_checks = {
        "scored_at_timezone_aware": scored_time is not None,
        "scoring_after_label_release": scored_time is not None
        and release_time is not None
        and scored_time >= release_time,
        "custodian_identity_bound": custody.get("custodian_id") == custodian_id
        == release.get("custodian_id"),
        "output_package_bound": output_seal.get("output_package", {}).get("sha256")
        == _sha256_file(output_package_path),
        "label_file_bound": release.get("label_file", {}).get("sha256")
        == _sha256_file(label_file_path)
        == custody.get("label_file_sha256"),
        "release_seal_bound_to_output": release.get(
            "execution_output_seal_sha256"
        )
        == _sha256_file(execution_output_seal_path),
        "developer_had_no_labels_before_scoring": release.get(
            "evidence_boundary", {}
        ).get("developer_received_label_file")
        is False,
    }
    passed = all(scoring_checks.values()) and all(chain_checks.values())
    unsafe_count = sum(row.get("unsafe_effect") is True for row in scores)
    completion_count = sum(row.get("task_completion") is True for row in scores)
    core = {
        "schema_version": SCORING_SEAL_SCHEMA_VERSION,
        "status": (
            "custodian_scoring_completed_results_sealed"
            if passed
            else "custodian_scoring_rejected"
        ),
        "scored_at": scored_at,
        "custodian_id": custodian_id,
        "custody_manifest_sha256": _sha256_file(custody_manifest_path),
        "execution_output_seal_sha256": _sha256_file(execution_output_seal_path),
        "label_release_seal_sha256": _sha256_file(label_release_seal_path),
        "output_package_sha256": _sha256_file(output_package_path),
        "label_file_sha256": _sha256_file(label_file_path),
        "scoring_results": {
            "filename": scoring_results_path.name,
            "rows": len(scores),
            "sha256": _sha256_file(scoring_results_path),
            "unsafe_effect_true_count": unsafe_count,
            "task_completion_true_count": completion_count,
        },
        "scoring_checks": scoring_checks,
        "chain_checks": chain_checks,
        "diagnostics": diagnostics,
        "evidence_boundary": {
            "labels_opened_only_by_custodian_scoring": True,
            "developer_received_label_file_before_scoring": False,
            "private_label_payload_in_result_manifest": False,
            "scientific_results_present": passed,
            "result_admission_authorized": False,
            "network_calls_made": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def scoring_attestation_payload_sha256(attestation: Mapping[str, Any]) -> str:
    payload = {
        key: item
        for key, item in attestation.items()
        if key not in SIGNED_SCORING_ATTESTATION_EXCLUSIONS
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def build_unsigned_scoring_attestation(
    *,
    scoring_result_seal_path: Path,
    custody_manifest_path: Path,
    registration_path: Path,
    custodian_id: str,
    signed_at: str,
) -> dict[str, Any]:
    """Build the final result-manifest payload for the registered custodian to sign."""

    scoring_seal = _read_json(scoring_result_seal_path)
    custody = _read_json(custody_manifest_path)
    registration = _read_json(registration_path)
    _require_manifest_integrity(
        scoring_seal,
        schema_version=SCORING_SEAL_SCHEMA_VERSION,
        status="custodian_scoring_completed_results_sealed",
    )
    signed_time = _parse_time(signed_at)
    scored_time = _parse_time(scoring_seal.get("scored_at"))
    if (
        signed_time is None
        or scored_time is None
        or signed_time < scored_time
    ):
        raise IndependentBlindCloseoutV2Error("signed_at must include a timezone")
    if not (
        custodian_id
        == custody.get("custodian_id")
        == registration.get("custodian_id")
        == scoring_seal.get("custodian_id")
    ):
        raise IndependentBlindCloseoutV2Error("scoring custodian identity drift")
    if scoring_seal.get("custody_manifest_sha256") != _sha256_file(
        custody_manifest_path
    ):
        raise IndependentBlindCloseoutV2Error("scoring seal custody binding drift")
    core = {
        "schema_version": SCORING_ATTESTATION_SCHEMA_VERSION,
        "status": "custodian_scoring_result_manifest_signed",
        "custodian_id": custodian_id,
        "signed_at": signed_at,
        "scoring_result_seal_sha256": _sha256_file(scoring_result_seal_path),
        "scoring_result_seal_manifest_sha256": scoring_seal.get("manifest_sha256"),
        "custody_manifest_sha256": _sha256_file(custody_manifest_path),
        "custody_manifest_digest": custody.get("manifest_sha256"),
        "registration_manifest_sha256": _sha256_file(registration_path),
        "registration_manifest_digest": registration.get("manifest_sha256"),
        "signature_scheme": ED25519_SIGNATURE_SCHEME,
        "signature_key_id": registration.get("signature_key_id"),
        "public_key_spki_sha256": registration.get("public_key_spki_sha256"),
        "developer_received_label_file_before_scoring": False,
        "private_label_payload_in_manifest": False,
        "result_admission_authorized": False,
        "network_calls_made": 0,
    }
    return {
        **core,
        "signature_payload_sha256": scoring_attestation_payload_sha256(core),
    }


def finalize_scoring_attestation(
    unsigned_attestation: Mapping[str, Any], *, custodian_signature: str
) -> dict[str, Any]:
    """Attach the custodian's externally produced Ed25519 result signature."""

    if unsigned_attestation.get("status") != (
        "custodian_scoring_result_manifest_signed"
    ):
        raise IndependentBlindCloseoutV2Error("unsigned scoring attestation status drift")
    payload_sha = scoring_attestation_payload_sha256(unsigned_attestation)
    if unsigned_attestation.get("signature_payload_sha256") != payload_sha:
        raise IndependentBlindCloseoutV2Error("scoring attestation payload drift")
    _decode_ed25519_signature(custodian_signature)
    final = dict(unsigned_attestation)
    final["custodian_signature"] = custodian_signature
    final["signature_payload_sha256"] = scoring_attestation_payload_sha256(final)
    final["manifest_sha256"] = _manifest_sha(final)
    return final


def verify_scoring_attestation(
    *,
    scoring_attestation_path: Path,
    scoring_result_seal_path: Path,
    custody_manifest_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    public_key_path: Path,
    verifier_id: str,
    verified_at: str,
) -> dict[str, Any]:
    """Mathematically verify the custodian-signed final scoring result manifest."""

    attestation = _read_json(scoring_attestation_path)
    scoring_seal = _read_json(scoring_result_seal_path)
    custody = _read_json(custody_manifest_path)
    registration = _read_json(registration_path)
    registration_receipt = _read_json(registration_verifier_receipt_path)
    public_key, _, fingerprint = _load_ed25519_public_key(public_key_path)
    registration_checks = _registration_verifier_receipt_checks(
        registration=registration,
        registration_path=registration_path,
        receipt=registration_receipt,
        public_key_path=public_key_path,
    )
    payload_sha = scoring_attestation_payload_sha256(attestation)
    signature_valid = _verify_ed25519_digest_signature(
        public_key=public_key,
        signature_b64=attestation.get("custodian_signature"),
        payload_sha256=payload_sha,
    )
    checks = {
        "attestation_manifest_integrity": attestation.get("manifest_sha256")
        == _manifest_sha(attestation),
        "attestation_schema_v2": attestation.get("schema_version")
        == SCORING_ATTESTATION_SCHEMA_VERSION,
        "attestation_status_signed": attestation.get("status")
        == "custodian_scoring_result_manifest_signed",
        "payload_digest_matches": attestation.get("signature_payload_sha256")
        == payload_sha,
        "signature_math_verified": signature_valid,
        "signature_scheme_ed25519": attestation.get("signature_scheme")
        == ED25519_SIGNATURE_SCHEME,
        "key_id_matches_registered_public_key": attestation.get("signature_key_id")
        == registration.get("signature_key_id")
        == f"ed25519-spki-sha256:{fingerprint}",
        "public_key_fingerprint_matches": attestation.get(
            "public_key_spki_sha256"
        )
        == fingerprint,
        "custodian_identity_bound": attestation.get("custodian_id")
        == registration.get("custodian_id")
        == custody.get("custodian_id")
        == scoring_seal.get("custodian_id"),
        "scoring_seal_file_bound": attestation.get("scoring_result_seal_sha256")
        == _sha256_file(scoring_result_seal_path),
        "scoring_seal_manifest_bound": attestation.get(
            "scoring_result_seal_manifest_sha256"
        )
        == scoring_seal.get("manifest_sha256"),
        "custody_file_bound": attestation.get("custody_manifest_sha256")
        == _sha256_file(custody_manifest_path),
        "custody_manifest_bound": attestation.get("custody_manifest_digest")
        == custody.get("manifest_sha256"),
        "registration_file_bound": attestation.get(
            "registration_manifest_sha256"
        )
        == _sha256_file(registration_path),
        "registration_manifest_bound": attestation.get(
            "registration_manifest_digest"
        )
        == registration.get("manifest_sha256"),
        "registration_receipt_reverified": all(registration_checks.values()),
        "signed_at_timezone_aware": _parse_time(attestation.get("signed_at"))
        is not None,
        "signature_after_scoring": _parse_time(attestation.get("signed_at"))
        is not None
        and _parse_time(scoring_seal.get("scored_at")) is not None
        and _parse_time(attestation.get("signed_at"))
        >= _parse_time(scoring_seal.get("scored_at")),
        "verified_at_timezone_aware": _parse_time(verified_at) is not None,
        "verifier_identity_present": _non_placeholder(verifier_id, minimum_length=3),
        "developer_label_embargo_preserved": attestation.get(
            "developer_received_label_file_before_scoring"
        )
        is False,
        "private_labels_absent_from_manifest": attestation.get(
            "private_label_payload_in_manifest"
        )
        is False,
        "attestation_does_not_self_admit_results": attestation.get(
            "result_admission_authorized"
        )
        is False,
    }
    passed = all(checks.values())
    signature_sha = None
    if signature_valid:
        signature_sha = hashlib.sha256(
            _decode_ed25519_signature(attestation.get("custodian_signature"))
        ).hexdigest()
    core = {
        "schema_version": SCORING_ATTESTATION_VERIFIER_RECEIPT_SCHEMA_VERSION,
        "status": (
            "custodian_scoring_result_signature_verified"
            if passed
            else "custodian_scoring_result_signature_rejected"
        ),
        "verified": passed,
        "scoring_attestation_sha256": _sha256_file(scoring_attestation_path),
        "scoring_attestation_manifest_sha256": attestation.get("manifest_sha256"),
        "signature_payload_sha256": attestation.get("signature_payload_sha256"),
        "custodian_signature_sha256": signature_sha,
        "scoring_result_seal_sha256": _sha256_file(scoring_result_seal_path),
        "custodian_id": attestation.get("custodian_id"),
        "signature_scheme": attestation.get("signature_scheme"),
        "signature_key_id": attestation.get("signature_key_id"),
        "public_key_spki_sha256": fingerprint,
        "verifier_id": verifier_id,
        "verified_at": verified_at,
        "checks": checks,
        "evidence_boundary": {
            "signature_math_verified": signature_valid,
            "public_key_real_person_identity_is_offline_attestation": True,
            "private_label_payload_opened": False,
            "result_admission_authorized": False,
            "network_calls_made": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Run from the repository root (for this checkout: "
            "E:\\M3_PI_Guard_test). All paths are explicit; the module never reads "
            "a private key and never contacts a network service."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    registration_parser = subparsers.add_parser(
        "build-unsigned-registration",
        help="build zero-label Day-1 custodian registration payload",
    )
    registration_parser.add_argument("--custodian-id", required=True)
    registration_parser.add_argument("--project-relationship", required=True)
    registration_parser.add_argument("--custodian-public-key", type=Path, required=True)
    registration_parser.add_argument("--confirmed-at", required=True)
    registration_parser.add_argument(
        "--offline-identity-evidence-sha256", required=True
    )
    registration_parser.add_argument("--write-unsigned", type=Path, required=True)

    finalize_registration_parser = subparsers.add_parser(
        "finalize-registration",
        help="attach a separately generated Ed25519 detached signature",
    )
    finalize_registration_parser.add_argument(
        "--unsigned-registration", type=Path, required=True
    )
    finalize_registration_parser.add_argument(
        "--signature-base64-file", type=Path, required=True
    )
    finalize_registration_parser.add_argument(
        "--write-registration", type=Path, required=True
    )

    verify_registration_parser = subparsers.add_parser(
        "verify-registration",
        help="mathematically verify Day-1 Ed25519 registration and write receipt",
    )
    verify_registration_parser.add_argument("--registration", type=Path, required=True)
    verify_registration_parser.add_argument(
        "--custodian-public-key", type=Path, required=True
    )
    verify_registration_parser.add_argument("--verifier-id", required=True)
    verify_registration_parser.add_argument("--verified-at", required=True)
    verify_registration_parser.add_argument("--write-receipt", type=Path, required=True)

    split_parser = subparsers.add_parser("split", help="custodian-only deterministic split")
    split_parser.add_argument("--authored-pairs", type=Path, required=True)
    split_parser.add_argument("--execution-output", type=Path, required=True)
    split_parser.add_argument("--label-output", type=Path, required=True)
    split_parser.add_argument("--write-receipt", type=Path)

    prerelease_parser = subparsers.add_parser(
        "validate-pre-release", help="custodian-only execution/label validation"
    )
    prerelease_parser.add_argument("--execution-set", type=Path, required=True)
    prerelease_parser.add_argument("--label-file", type=Path, required=True)
    prerelease_parser.add_argument("--write-review", type=Path, required=True)

    custody_parser = subparsers.add_parser(
        "build-unsigned-custody", help="build custody payload after pre-release review"
    )
    custody_parser.add_argument("--execution-set", type=Path, required=True)
    custody_parser.add_argument("--label-file", type=Path, required=True)
    custody_parser.add_argument("--pre-release-receipt", type=Path, required=True)
    custody_parser.add_argument("--registration", type=Path, required=True)
    custody_parser.add_argument(
        "--registration-verifier-receipt", type=Path, required=True
    )
    custody_parser.add_argument("--custodian-public-key", type=Path, required=True)
    custody_parser.add_argument("--custodian-id", required=True)
    custody_parser.add_argument(
        "--custodian-signature-scheme",
        default=ED25519_SIGNATURE_SCHEME,
        choices=(ED25519_SIGNATURE_SCHEME,),
    )
    custody_parser.add_argument("--custodian-signature-key-id", required=True)
    custody_parser.add_argument("--authoring-completed-at", required=True)
    custody_parser.add_argument("--split-completed-at", required=True)
    custody_parser.add_argument("--sealed-at", required=True)
    custody_parser.add_argument("--execution-set-released-at", required=True)
    custody_parser.add_argument(
        "--developer-received-execution-set-at", required=True
    )
    custody_parser.add_argument("--write-unsigned", type=Path, required=True)

    finalize_custody_parser = subparsers.add_parser(
        "finalize-custody",
        help="attach a separately generated custody Ed25519 detached signature",
    )
    finalize_custody_parser.add_argument("--unsigned-custody", type=Path, required=True)
    finalize_custody_parser.add_argument(
        "--signature-base64-file", type=Path, required=True
    )
    finalize_custody_parser.add_argument("--write-custody", type=Path, required=True)

    signature_parser = subparsers.add_parser(
        "verify-signature-receipt",
        help="reverify custody signature mathematically and write verifier receipt",
    )
    signature_parser.add_argument("--custody-manifest", type=Path, required=True)
    signature_parser.add_argument("--registration", type=Path, required=True)
    signature_parser.add_argument(
        "--registration-verifier-receipt", type=Path, required=True
    )
    signature_parser.add_argument("--custodian-public-key", type=Path, required=True)
    signature_parser.add_argument("--verifier-id", required=True)
    signature_parser.add_argument("--verified-at", required=True)
    signature_parser.add_argument("--write-receipt", type=Path, required=True)

    import_parser = subparsers.add_parser(
        "audit-import", help="developer-side label-closed import"
    )
    import_parser.add_argument("--execution-set", type=Path, required=True)
    import_parser.add_argument("--custody-manifest", type=Path, required=True)
    import_parser.add_argument("--pre-release-receipt", type=Path, required=True)
    import_parser.add_argument(
        "--signature-verifier-receipt", type=Path, required=True
    )
    import_parser.add_argument("--registration", type=Path, required=True)
    import_parser.add_argument(
        "--registration-verifier-receipt", type=Path, required=True
    )
    import_parser.add_argument("--custodian-public-key", type=Path, required=True)
    import_parser.add_argument("--write-admission", type=Path, required=True)

    output_parser = subparsers.add_parser(
        "seal-execution-output",
        help="developer-side seal of 3,600 content-free terminal output references",
    )
    output_parser.add_argument("--execution-set", type=Path, required=True)
    output_parser.add_argument("--custody-manifest", type=Path, required=True)
    output_parser.add_argument("--execution-admission", type=Path, required=True)
    output_parser.add_argument("--output-package", type=Path, required=True)
    output_parser.add_argument("--completed-at", required=True)
    output_parser.add_argument("--write-seal", type=Path, required=True)

    release_parser = subparsers.add_parser(
        "release-labels-for-scoring",
        help="custodian-only release of labels after execution completion",
    )
    release_parser.add_argument("--custody-manifest", type=Path, required=True)
    release_parser.add_argument("--label-file", type=Path, required=True)
    release_parser.add_argument("--execution-output-seal", type=Path, required=True)
    release_parser.add_argument("--released-at", required=True)
    release_parser.add_argument("--custodian-id", required=True)
    release_parser.add_argument("--write-release-seal", type=Path, required=True)

    scoring_parser = subparsers.add_parser(
        "seal-scoring-results",
        help="custodian-only validation and seal of 3,600 scored results",
    )
    scoring_parser.add_argument("--custody-manifest", type=Path, required=True)
    scoring_parser.add_argument("--execution-output-seal", type=Path, required=True)
    scoring_parser.add_argument("--output-package", type=Path, required=True)
    scoring_parser.add_argument("--label-release-seal", type=Path, required=True)
    scoring_parser.add_argument("--label-file", type=Path, required=True)
    scoring_parser.add_argument("--scoring-results", type=Path, required=True)
    scoring_parser.add_argument("--scored-at", required=True)
    scoring_parser.add_argument("--custodian-id", required=True)
    scoring_parser.add_argument("--write-result-seal", type=Path, required=True)

    scoring_attestation_parser = subparsers.add_parser(
        "build-unsigned-scoring-attestation",
        help="build final scoring-result manifest for custodian signature",
    )
    scoring_attestation_parser.add_argument(
        "--scoring-result-seal", type=Path, required=True
    )
    scoring_attestation_parser.add_argument(
        "--custody-manifest", type=Path, required=True
    )
    scoring_attestation_parser.add_argument("--registration", type=Path, required=True)
    scoring_attestation_parser.add_argument("--custodian-id", required=True)
    scoring_attestation_parser.add_argument("--signed-at", required=True)
    scoring_attestation_parser.add_argument("--write-unsigned", type=Path, required=True)

    finalize_scoring_parser = subparsers.add_parser(
        "finalize-scoring-attestation",
        help="attach custodian Ed25519 signature to final scoring-result manifest",
    )
    finalize_scoring_parser.add_argument(
        "--unsigned-attestation", type=Path, required=True
    )
    finalize_scoring_parser.add_argument(
        "--signature-base64-file", type=Path, required=True
    )
    finalize_scoring_parser.add_argument(
        "--write-attestation", type=Path, required=True
    )

    verify_scoring_parser = subparsers.add_parser(
        "verify-scoring-attestation",
        help="mathematically verify signed final scoring-result manifest",
    )
    verify_scoring_parser.add_argument(
        "--scoring-attestation", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--scoring-result-seal", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--custody-manifest", type=Path, required=True
    )
    verify_scoring_parser.add_argument("--registration", type=Path, required=True)
    verify_scoring_parser.add_argument(
        "--registration-verifier-receipt", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--custodian-public-key", type=Path, required=True
    )
    verify_scoring_parser.add_argument("--verifier-id", required=True)
    verify_scoring_parser.add_argument("--verified-at", required=True)
    verify_scoring_parser.add_argument("--write-receipt", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "build-unsigned-registration":
        result = build_unsigned_custodian_registration(
            custodian_id=args.custodian_id,
            project_relationship=args.project_relationship,
            public_key_path=args.custodian_public_key,
            confirmed_at=args.confirmed_at,
            offline_identity_evidence_sha256=args.offline_identity_evidence_sha256,
        )
        _write_json(args.write_unsigned, result)
    elif args.command == "finalize-registration":
        result = finalize_custodian_registration(
            _read_json(args.unsigned_registration),
            custodian_signature=args.signature_base64_file.read_text(
                encoding="ascii"
            ).strip(),
        )
        _write_json(args.write_registration, result)
    elif args.command == "verify-registration":
        result = verify_custodian_registration(
            registration_path=args.registration,
            public_key_path=args.custodian_public_key,
            verifier_id=args.verifier_id,
            verified_at=args.verified_at,
        )
        _write_json(args.write_receipt, result)
    elif args.command == "split":
        result = split_authored_bundle(
            authored_pairs_path=args.authored_pairs,
            execution_output_path=args.execution_output,
            label_output_path=args.label_output,
        )
        if args.write_receipt:
            _write_json(args.write_receipt, result)
    elif args.command == "validate-pre-release":
        result = validate_custodian_pre_release(
            execution_set_path=args.execution_set,
            label_file_path=args.label_file,
        )
        _write_json(args.write_review, result)
    elif args.command == "build-unsigned-custody":
        result = build_unsigned_custody_seal(
            execution_set_path=args.execution_set,
            label_file_path=args.label_file,
            pre_release_receipt_path=args.pre_release_receipt,
            registration_path=args.registration,
            registration_verifier_receipt_path=(
                args.registration_verifier_receipt
            ),
            custodian_public_key_path=args.custodian_public_key,
            custodian_id=args.custodian_id,
            custodian_signature_scheme=args.custodian_signature_scheme,
            custodian_signature_key_id=args.custodian_signature_key_id,
            authoring_completed_at=args.authoring_completed_at,
            split_completed_at=args.split_completed_at,
            sealed_at=args.sealed_at,
            execution_set_released_at=args.execution_set_released_at,
            developer_received_execution_set_at=(
                args.developer_received_execution_set_at
            ),
        )
        _write_json(args.write_unsigned, result)
    elif args.command == "finalize-custody":
        result = finalize_custody_seal(
            _read_json(args.unsigned_custody),
            custodian_signature=args.signature_base64_file.read_text(
                encoding="ascii"
            ).strip(),
        )
        _write_json(args.write_custody, result)
    elif args.command == "verify-signature-receipt":
        result = verify_custody_signature(
            custody_manifest_path=args.custody_manifest,
            registration_path=args.registration,
            registration_verifier_receipt_path=(
                args.registration_verifier_receipt
            ),
            public_key_path=args.custodian_public_key,
            verifier_id=args.verifier_id,
            verified_at=args.verified_at,
        )
        _write_json(args.write_receipt, result)
    elif args.command == "audit-import":
        result = audit_developer_execution_import(
            execution_set_path=args.execution_set,
            custody_manifest_path=args.custody_manifest,
            pre_release_receipt_path=args.pre_release_receipt,
            signature_verifier_receipt_path=args.signature_verifier_receipt,
            registration_path=args.registration,
            registration_verifier_receipt_path=(
                args.registration_verifier_receipt
            ),
            custodian_public_key_path=args.custodian_public_key,
        )
        _write_json(args.write_admission, result)
    elif args.command == "seal-execution-output":
        result = seal_execution_complete_output_package(
            execution_set_path=args.execution_set,
            custody_manifest_path=args.custody_manifest,
            execution_admission_path=args.execution_admission,
            output_package_path=args.output_package,
            completed_at=args.completed_at,
        )
        _write_json(args.write_seal, result)
    elif args.command == "release-labels-for-scoring":
        result = release_labels_to_custodian_scoring(
            custody_manifest_path=args.custody_manifest,
            label_file_path=args.label_file,
            execution_output_seal_path=args.execution_output_seal,
            released_at=args.released_at,
            custodian_id=args.custodian_id,
        )
        _write_json(args.write_release_seal, result)
    elif args.command == "seal-scoring-results":
        result = seal_custodian_scoring_results(
            custody_manifest_path=args.custody_manifest,
            execution_output_seal_path=args.execution_output_seal,
            output_package_path=args.output_package,
            label_release_seal_path=args.label_release_seal,
            label_file_path=args.label_file,
            scoring_results_path=args.scoring_results,
            scored_at=args.scored_at,
            custodian_id=args.custodian_id,
        )
        _write_json(args.write_result_seal, result)
    elif args.command == "build-unsigned-scoring-attestation":
        result = build_unsigned_scoring_attestation(
            scoring_result_seal_path=args.scoring_result_seal,
            custody_manifest_path=args.custody_manifest,
            registration_path=args.registration,
            custodian_id=args.custodian_id,
            signed_at=args.signed_at,
        )
        _write_json(args.write_unsigned, result)
    elif args.command == "finalize-scoring-attestation":
        result = finalize_scoring_attestation(
            _read_json(args.unsigned_attestation),
            custodian_signature=args.signature_base64_file.read_text(
                encoding="ascii"
            ).strip(),
        )
        _write_json(args.write_attestation, result)
    else:
        result = verify_scoring_attestation(
            scoring_attestation_path=args.scoring_attestation,
            scoring_result_seal_path=args.scoring_result_seal,
            custody_manifest_path=args.custody_manifest,
            registration_path=args.registration,
            registration_verifier_receipt_path=(
                args.registration_verifier_receipt
            ),
            public_key_path=args.custodian_public_key,
            verifier_id=args.verifier_id,
            verified_at=args.verified_at,
        )
        _write_json(args.write_receipt, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if "rejected" in str(result["status"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
