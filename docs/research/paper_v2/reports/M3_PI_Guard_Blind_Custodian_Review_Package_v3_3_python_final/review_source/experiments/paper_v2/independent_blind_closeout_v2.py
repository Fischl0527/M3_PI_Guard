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
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
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
EFFECT_RECEIPT_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-isolated-effect-receipt-2.0"
)
PROVIDER_TRACE_RECEIPT_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-provider-trace-receipt-2.1"
)
PROVIDER_REQUEST_CHAIN_ENTRY_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-provider-request-chain-entry-2.1"
)
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
SCORING_ATTESTATION_INTEGRITY_VERIFIER_RECEIPT_SCHEMA_VERSION = (
    "m3-paper-v2-independent-blind-scoring-integrity-verifier-receipt-2.0"
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
EFFECT_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "sequence",
        "work_key",
        "output_id",
        "slot_id",
        "case_id",
        "condition_id",
        "operational_status",
        "isolated_effect_backend",
        "provider_managed_tools_enabled",
        "external_effects_enabled",
        "real_external_effect_count",
        "receipt_id",
    }
)
PROVIDER_TRACE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "sequence",
        "work_key",
        "output_id",
        "slot_id",
        "case_id",
        "condition_id",
        "operational_status",
        "provider_id",
        "model_id",
        "endpoint_type",
        "endpoint_host",
        "local_request_ids_sha256",
        "canonical_payload_hashes_sha256",
        "official_response_ids_sha256",
        "returned_model_ids_sha256",
        "provider_call_count",
        "completed_call_count",
        "failed_call_count",
        "zero_call_reason",
        "zero_call_failure_class",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_cny",
        "budget_ceiling_cny",
        "within_budget",
        "trace_start_global_sequence",
        "trace_end_global_sequence",
        "trace_genesis_previous_sha256",
        "trace_tail_entry_sha256",
        "all_attempts_terminal",
        "open_attempt_count",
        "automatic_retry_count",
        "provider_managed_tools_enabled",
        "external_connectors_enabled",
        "trace_receipt_id",
    }
)
PROVIDER_REQUEST_CHAIN_ENTRY_FIELDS = frozenset(
    {
        "schema_version",
        "global_sequence",
        "work_key",
        "output_id",
        "call_sequence",
        "event_type",
        "event_at",
        "local_request_id",
        "canonical_payload_sha256",
        "started_event_sha256",
        "pretransport_commitment_fsynced",
        "transport_started_after_precommit",
        "official_response_id",
        "returned_model",
        "usage",
        "cost_cny",
        "failure_class",
        "previous_chain_sha256",
        "entry_chain_sha256",
    }
)
PROVIDER_REQUEST_CHAIN_USAGE_FIELDS = frozenset(
    {
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "completion_tokens",
        "total_tokens",
    }
)
FILE_BINDING_FIELDS = frozenset({"filename", "rows", "sha256"})
OUTPUT_SEAL_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "completed_at",
        "execution_set_sha256",
        "custody_manifest_sha256",
        "execution_admission_sha256",
        "execution_admission_manifest_sha256",
        "output_package",
        "effect_receipt_bundle",
        "provider_trace_receipt_bundle",
        "provider_request_chain_bundle",
        "execution_checks",
        "output_checks",
        "runtime_receipt_checks",
        "custody_bound",
        "diagnostics",
        "evidence_boundary",
        "manifest_sha256",
    }
)
OUTPUT_SEAL_DIAGNOSTIC_FIELDS = frozenset(
    {"top_level_schema_drift", "semantic_leaks"}
)
OUTPUT_SEAL_EVIDENCE_FIELDS = frozenset(
    {
        "output_content_included",
        "scientific_results_included",
        "label_file_opened",
        "label_rows_read",
        "developer_received_label_file_before_completion",
        "execution_complete",
        "result_admission_authorized",
        "network_calls_made_by_sealer",
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
PROVIDER_FAILURE_STATUS_BY_CLASS = {
    "provider_failure": "provider_failure",
    "transport_failure": "provider_failure",
    "timeout": "timeout",
    "runner_failure": "diagnostic",
}
ZERO_CALL_REASON_BY_CLASS = {
    "provider_failure": "provider_unavailable_before_transport",
    "transport_failure": "transport_unavailable_before_request_start",
    "timeout": "pretransport_timeout",
    "runner_failure": "runner_failed_before_provider_transport",
}
COMPLETED_ONLY_OPERATIONAL_STATUSES = frozenset(
    {
        "completed",
        "diagnostic",
        "max_steps",
        "parse_failure",
        "refusal",
    }
)
PROVIDER_FAILURE_EVENT_CLASSES = frozenset(
    {"provider_failure", "transport_failure"}
)
OPAQUE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,255}$")
DEEPSEEK_BLIND_BUDGET_CEILING_CNY = 15.0
MAX_RUNTIME_EVENT_CLOCK_SKEW = timedelta(minutes=5)
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
REGISTRATION_UNSIGNED_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "custodian_id",
        "project_relationship",
        "independence_attested",
        "participated_in_implementation",
        "participated_in_threshold_selection",
        "participated_in_experiment_tuning",
        "labels_embargoed_until_execution_complete",
        "developer_must_not_receive_labels_before_scoring",
        "signature_scheme",
        "signature_key_id",
        "public_key_spki_sha256",
        "offline_identity_evidence_sha256",
        "confirmed_at",
        "label_rows_present",
        "execution_authorized",
        "network_calls_made",
        "registration_signature_payload_sha256",
    }
)
REGISTRATION_FINAL_FIELDS = frozenset(
    {*REGISTRATION_UNSIGNED_FIELDS, "custodian_signature", "manifest_sha256"}
)
REGISTRATION_VERIFIER_CHECK_FIELDS = frozenset(
    {
        "registration_top_level_schema_exact",
        "registration_nested_sensitive_payload_absent",
        "registration_fields_are_scalar",
        "registration_manifest_integrity",
        "registration_schema_v2",
        "registration_status_signed",
        "custodian_identity_present",
        "relationship_present",
        "independence_attested",
        "not_implementation_participant",
        "not_threshold_participant",
        "not_tuning_participant",
        "label_embargo_attested",
        "developer_label_embargo_attested",
        "confirmed_at_timezone_aware",
        "offline_identity_evidence_committed",
        "signature_scheme_ed25519",
        "public_key_fingerprint_matches",
        "key_id_matches_public_key",
        "payload_digest_matches",
        "signature_math_verified",
        "registration_has_zero_labels",
        "registration_does_not_authorize_execution",
        "verifier_identity_present",
        "verifier_distinct_from_custodian",
        "verified_at_timezone_aware",
        "verification_not_before_confirmation",
        "verification_not_materially_future_dated",
    }
)
REGISTRATION_VERIFIER_EVIDENCE_FIELDS = frozenset(
    {
        "signature_math_verified",
        "public_key_control_cryptographically_verified",
        "public_key_real_person_identity_is_offline_attestation",
        "offline_identity_evidence_content_opened",
        "label_rows_read",
        "execution_authorized",
        "clock_start_authorized",
        "clock_start_is_technical_gate_only",
        "offline_identity_not_cryptographically_proven",
        "network_calls_made",
    }
)
CUSTODY_RELEASE_CHAIN_FIELDS = frozenset(
    {
        "authoring_completed_at",
        "split_completed_at",
        "sealed_at",
        "execution_set_released_at",
        "developer_received_execution_set_at",
        "label_file_released_at",
        "developer_received_label_file_at",
    }
)
CUSTODY_UNSIGNED_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "candidate_filename",
        "candidate_row_count",
        "candidate_sha256",
        "label_file_filename",
        "label_file_row_count",
        "label_file_sha256",
        "custodian_id",
        "custodian_independence_attested",
        "custodian_participated_in_implementation",
        "custodian_signature_scheme",
        "custodian_signature_key_id",
        "developer_access_before_seal",
        "developer_label_access_before_execution",
        "execution_and_label_files_distinct",
        "release_phase",
        "release_chain",
        "pre_release_manifest_sha256",
        "registration_manifest_sha256",
        "registration_verifier_receipt_sha256",
        "slot_source_sha256",
        "custodian_signature_payload_sha256",
    }
)
CUSTODY_FINAL_FIELDS = frozenset(
    {*CUSTODY_UNSIGNED_FIELDS, "custodian_signature", "manifest_sha256"}
)
SCORING_ATTESTATION_UNSIGNED_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "custodian_id",
        "signed_at",
        "scoring_result_seal_sha256",
        "scoring_result_seal_manifest_sha256",
        "custody_manifest_sha256",
        "custody_manifest_digest",
        "registration_manifest_sha256",
        "registration_manifest_digest",
        "signature_scheme",
        "signature_key_id",
        "public_key_spki_sha256",
        "developer_received_label_file_before_scoring",
        "private_label_payload_in_manifest",
        "result_admission_authorized",
        "network_calls_made",
        "signature_payload_sha256",
    }
)
SCORING_ATTESTATION_FINAL_FIELDS = frozenset(
    {
        *SCORING_ATTESTATION_UNSIGNED_FIELDS,
        "custodian_signature",
        "manifest_sha256",
    }
)
SCORING_SEAL_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "scored_at",
        "custodian_id",
        "custody_manifest_sha256",
        "execution_output_seal_sha256",
        "label_release_seal_sha256",
        "output_package_sha256",
        "label_file_sha256",
        "scoring_results",
        "scoring_checks",
        "chain_checks",
        "execution_output_chain_checks",
        "diagnostics",
        "evidence_boundary",
        "manifest_sha256",
    }
)
SCORING_RESULT_BINDING_FIELDS = frozenset(
    {
        "filename",
        "rows",
        "sha256",
        "unsafe_effect_true_count",
        "task_completion_true_count",
    }
)
SCORING_SEAL_DIAGNOSTIC_FIELDS = frozenset({"top_level_schema_drift"})
SCORING_SEAL_EVIDENCE_FIELDS = frozenset(
    {
        "labels_opened_only_by_custodian_scoring",
        "verification_scope",
        "scoring_semantics_attested_by_independent_custodian",
        "scoring_semantics_recomputed",
        "developer_received_label_file_before_scoring",
        "private_label_payload_in_result_manifest",
        "scientific_results_present",
        "result_admission_authorized",
        "network_calls_made",
    }
)
SCORING_CHECK_FIELDS = frozenset(
    {
        "exactly_3600_scored_rows",
        "top_level_schema_exact",
        "schema_versions_exact",
        "score_rows_bind_output_and_label_case_identity",
        "scientific_flags_boolean",
        "operational_status_preserved",
    }
)
SCORING_CHAIN_CHECK_FIELDS = frozenset(
    {
        "scored_at_timezone_aware",
        "scored_at_not_materially_future_dated",
        "scoring_after_label_release",
        "custodian_identity_bound",
        "output_package_bound",
        "label_file_bound",
        "release_seal_bound_to_output",
        "developer_had_no_labels_before_scoring",
        "execution_output_chain_revalidated",
    }
)
EXECUTION_OUTPUT_CHAIN_CHECK_FIELDS = frozenset(
    {
        "output_seal_top_level_schema_exact",
        "output_seal_file_bindings_schema_exact",
        "output_seal_diagnostics_schema_exact",
        "output_seal_evidence_schema_exact",
        "execution_revalidated",
        "output_package_3600_revalidated",
        "runtime_receipt_bundles_revalidated",
        "recorded_execution_checks_exact",
        "recorded_output_checks_exact",
        "recorded_runtime_receipt_checks_exact",
        "recorded_custody_bound_true",
        "execution_set_sha256_bound",
        "custody_manifest_sha256_bound",
        "custody_manifest_integrity",
        "execution_admission_file_bound",
        "execution_admission_manifest_bound",
        "output_filename_bound",
        "output_rows_3600_bound",
        "output_package_sha256_bound",
        "effect_receipt_bundle_bound",
        "provider_trace_receipt_bundle_bound",
        "provider_request_chain_bundle_bound",
        "seal_claims_execution_complete",
        "seal_claims_labels_unopened",
    }
)
MAX_REGISTRATION_CLOCK_SKEW = timedelta(minutes=5)
MAX_STAGE_CLOCK_SKEW = timedelta(minutes=5)
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
CUSTODY_SIGNATURE_VERIFIER_CHECK_FIELDS = frozenset(
    {
        "custody_top_level_schema_exact",
        "custody_release_chain_schema_exact",
        "custody_release_chain_values_scalar",
        "custody_has_no_other_nested_payload",
        "custody_manifest_integrity",
        "custody_schema_v2",
        "custody_status_sealed",
        "custody_payload_digest_matches",
        "custodian_signature_scheme_ed25519",
        "custodian_key_matches_public_key",
        "custodian_signature_math_verified",
        "registration_receipt_reverified",
        "custodian_matches_registration",
        "registration_manifest_bound",
        "registration_verifier_receipt_bound",
        "verifier_identity_present",
        "verifier_distinct_from_custodian",
        "verified_at_timezone_aware",
        "custody_verification_not_materially_future_dated",
        "custody_verification_after_execution_handoff",
        "custody_verification_after_registration",
    }
)
CUSTODY_SIGNATURE_VERIFIER_EVIDENCE_FIELDS = frozenset(
    {
        "signature_math_verified",
        "public_key_control_cryptographically_verified",
        "public_key_real_person_identity_is_offline_attestation",
        "offline_identity_not_cryptographically_proven",
        "verified_true_cannot_replace_mathematical_reverification",
        "label_file_opened",
        "label_rows_read",
        "execution_authorized",
        "network_calls_made",
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


def _is_opaque_id(value: Any) -> bool:
    """Accept short ASCII identifiers only; never free-form prompt/result text."""

    return isinstance(value, str) and OPAQUE_ID_PATTERN.fullmatch(value) is not None


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


def _forbidden_registration_paths(registration: Mapping[str, Any]) -> list[str]:
    """Reject sensitive extension payloads while permitting frozen scalar field names."""

    forbidden: list[str] = []
    for path in _field_paths(registration):
        if "." not in path and "[" not in path and path in REGISTRATION_FINAL_FIELDS:
            continue
        normalized = _normalized_semantic_key(path)
        if any(marker in normalized for marker in FORBIDDEN_EXECUTION_KEY_MARKERS):
            forbidden.append(path)
    return sorted(forbidden)


def _exact_true_boolean_group(
    value: Any, expected_fields: frozenset[str]
) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == expected_fields
        and all(item is True for item in value.values())
    )


def _sensitive_extension_paths(
    value: Mapping[str, Any],
    *,
    top_level_fields: frozenset[str],
    nested_fields: Mapping[str, frozenset[str]],
) -> list[str]:
    """Find label/evaluator-like keys outside a manifest's frozen schema.

    Exact schema checks reject every extension.  This separate recursive check
    makes the confidentiality boundary explicit and prevents a future schema
    relaxation from silently accepting a nested answer-key channel.
    """

    allowed_paths = set(top_level_fields)
    for group, fields in nested_fields.items():
        allowed_paths.update(f"{group}.{field}" for field in fields)
    return sorted(
        path
        for path in _field_paths(value)
        if path not in allowed_paths
        and (
            _terminal_field_name(path) in FORBIDDEN_EXECUTION_FIELDS
            or any(
                marker in _normalized_semantic_key(path)
                for marker in FORBIDDEN_EXECUTION_KEY_MARKERS
            )
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
        "release_chain_not_materially_future_dated": timezone_aware
        and all(
            value <= datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW
            for value in parsed
            if value is not None
        ),
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

    if set(unsigned_registration) != REGISTRATION_UNSIGNED_FIELDS:
        raise IndependentBlindCloseoutV2Error(
            "unsigned registration top-level schema is not exact"
        )
    if _forbidden_registration_paths(unsigned_registration):
        raise IndependentBlindCloseoutV2Error(
            "unsigned registration contains forbidden nested semantics"
        )
    if any(
        isinstance(value, (Mapping, list)) for value in unsigned_registration.values()
    ):
        raise IndependentBlindCloseoutV2Error(
            "registration fields must remain scalar"
        )
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
    confirmed_time = _parse_time(registration.get("confirmed_at"))
    verified_time = _parse_time(verified_at)
    now = datetime.now(timezone.utc)
    checks = {
        "registration_top_level_schema_exact": set(registration)
        == REGISTRATION_FINAL_FIELDS,
        "registration_nested_sensitive_payload_absent": not (
            _forbidden_registration_paths(registration)
        ),
        "registration_fields_are_scalar": all(
            not isinstance(value, (Mapping, list)) for value in registration.values()
        ),
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
        "verifier_distinct_from_custodian": verifier_id
        != registration.get("custodian_id"),
        "verified_at_timezone_aware": _parse_time(verified_at) is not None,
        "verification_not_before_confirmation": confirmed_time is not None
        and verified_time is not None
        and verified_time >= confirmed_time,
        "verification_not_materially_future_dated": verified_time is not None
        and verified_time <= now + MAX_REGISTRATION_CLOCK_SKEW,
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
            "clock_start_is_technical_gate_only": True,
            "offline_identity_not_cryptographically_proven": True,
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
    confirmed_time = _parse_time(registration.get("confirmed_at"))
    verified_time = _parse_time(receipt.get("verified_at"))
    now = datetime.now(timezone.utc)
    receipt_checks = (
        receipt.get("checks") if isinstance(receipt.get("checks"), Mapping) else {}
    )
    receipt_evidence = (
        receipt.get("evidence_boundary")
        if isinstance(receipt.get("evidence_boundary"), Mapping)
        else {}
    )
    return {
        "registration_top_level_schema_exact": set(registration)
        == REGISTRATION_FINAL_FIELDS,
        "registration_nested_sensitive_payload_absent": not (
            _forbidden_registration_paths(registration)
        ),
        "registration_fields_are_scalar": all(
            not isinstance(value, (Mapping, list)) for value in registration.values()
        ),
        "registration_receipt_top_level_schema_exact": set(receipt)
        == REGISTRATION_VERIFIER_RECEIPT_FIELDS,
        "registration_receipt_checks_schema_exact": set(receipt_checks)
        == REGISTRATION_VERIFIER_CHECK_FIELDS,
        "registration_receipt_evidence_schema_exact": set(receipt_evidence)
        == REGISTRATION_VERIFIER_EVIDENCE_FIELDS,
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
        "registration_verifier_distinct_from_custodian": receipt.get(
            "verifier_id"
        )
        != registration.get("custodian_id"),
        "registration_verified_at_timezone_aware": _parse_time(
            receipt.get("verified_at")
        )
        is not None,
        "registration_verification_not_before_confirmation": confirmed_time
        is not None
        and verified_time is not None
        and verified_time >= confirmed_time,
        "registration_verification_not_materially_future_dated": verified_time
        is not None
        and verified_time <= now + MAX_REGISTRATION_CLOCK_SKEW,
        "registration_recorded_checks_all_pass": bool(receipt_checks)
        and all(value is True for value in receipt_checks.values()),
        "registration_signature_math_reverified": signature_valid,
        "registration_clock_only_not_execution": receipt_evidence.get(
            "clock_start_authorized"
        )
        is True
        and receipt_evidence.get("execution_authorized") is False,
        "registration_clock_is_technical_gate_only": receipt_evidence.get(
            "clock_start_is_technical_gate_only"
        )
        is True
        and receipt_evidence.get("offline_identity_not_cryptographically_proven")
        is True,
    }


def custody_signature_payload_sha256(custody: Mapping[str, Any]) -> str:
    """Return the digest an external custodian signature must bind."""

    payload = {
        key: item
        for key, item in custody.items()
        if key not in SIGNED_CUSTODY_EXCLUSIONS
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _custody_schema_checks(
    custody: Mapping[str, Any], *, finalized: bool
) -> dict[str, bool]:
    release_chain = custody.get("release_chain")
    expected = CUSTODY_FINAL_FIELDS if finalized else CUSTODY_UNSIGNED_FIELDS
    return {
        "custody_top_level_schema_exact": set(custody) == expected,
        "custody_release_chain_schema_exact": isinstance(release_chain, Mapping)
        and set(release_chain) == CUSTODY_RELEASE_CHAIN_FIELDS,
        "custody_release_chain_values_scalar": isinstance(release_chain, Mapping)
        and all(not isinstance(value, (Mapping, list)) for value in release_chain.values()),
        "custody_has_no_other_nested_payload": all(
            key == "release_chain" or not isinstance(value, (Mapping, list))
            for key, value in custody.items()
        ),
    }


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

    unsigned_schema_checks = _custody_schema_checks(
        unsigned_custody, finalized=False
    )
    if not all(unsigned_schema_checks.values()):
        raise IndependentBlindCloseoutV2Error(
            "unsigned custody schema is not exact"
        )
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
    verified_time = _parse_time(verified_at)
    execution_received_time = _parse_time(
        custody.get("release_chain", {}).get("developer_received_execution_set_at")
    )
    registration_verified_time = _parse_time(registration_receipt.get("verified_at"))
    checks = {
        **_custody_schema_checks(custody, finalized=True),
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
        "verifier_distinct_from_custodian": verifier_id
        != custody.get("custodian_id"),
        "verified_at_timezone_aware": _parse_time(verified_at) is not None,
        "custody_verification_not_materially_future_dated": verified_time
        is not None
        and verified_time <= datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW,
        "custody_verification_after_execution_handoff": verified_time is not None
        and execution_received_time is not None
        and verified_time >= execution_received_time,
        "custody_verification_after_registration": verified_time is not None
        and registration_verified_time is not None
        and verified_time >= registration_verified_time,
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
            "offline_identity_not_cryptographically_proven": True,
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
    receipt_verified_time = _parse_time(receipt.get("verified_at"))
    execution_received_time = _parse_time(
        custody.get("release_chain", {}).get("developer_received_execution_set_at")
    )
    return {
        **_custody_schema_checks(custody, finalized=True),
        "signature_receipt_top_level_schema_exact": set(receipt)
        == SIGNATURE_VERIFIER_RECEIPT_FIELDS,
        "signature_receipt_checks_schema_exact": set(checks)
        == CUSTODY_SIGNATURE_VERIFIER_CHECK_FIELDS,
        "signature_receipt_evidence_schema_exact": set(evidence)
        == CUSTODY_SIGNATURE_VERIFIER_EVIDENCE_FIELDS,
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
        "signature_receipt_not_materially_future_dated": receipt_verified_time
        is not None
        and receipt_verified_time
        <= datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW,
        "signature_receipt_after_execution_handoff": receipt_verified_time
        is not None
        and execution_received_time is not None
        and receipt_verified_time >= execution_received_time,
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
        **_custody_schema_checks(custody, finalized=True),
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


def _require_replayed_passing_admission(
    *,
    admission: Mapping[str, Any],
    admission_path: Path,
    execution_set_path: Path,
    custody_manifest_path: Path,
    pre_release_receipt_path: Path,
    signature_verifier_receipt_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    custodian_public_key_path: Path,
) -> None:
    """Reject any admission that cannot be rebuilt from signed primary evidence."""

    _require_passing_admission(
        admission=admission,
        admission_path=admission_path,
        execution_set_path=execution_set_path,
    )
    rebuilt = audit_developer_execution_import(
        execution_set_path=execution_set_path,
        custody_manifest_path=custody_manifest_path,
        pre_release_receipt_path=pre_release_receipt_path,
        signature_verifier_receipt_path=signature_verifier_receipt_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_verifier_receipt_path,
        custodian_public_key_path=custodian_public_key_path,
    )
    if rebuilt != admission:
        raise IndependentBlindCloseoutV2Error(
            "execution admission does not exactly match full primary-evidence replay"
        )


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
        and all(_is_sha256(value) for value in work_keys),
        "output_ids_unique_nonempty": len(set(output_ids)) == 3600
        and all(_is_opaque_id(value) for value in output_ids),
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


def _runtime_receipt_bundle_validation(
    *,
    outputs: Sequence[Mapping[str, Any]],
    effect_receipts: Sequence[Mapping[str, Any]],
    provider_receipts: Sequence[Mapping[str, Any]],
    provider_request_chain: Sequence[Mapping[str, Any]],
) -> dict[str, bool]:
    """Validate content-free runtime receipts and the prospective request ledger.

    Each provider call is represented by a pre-transport ``started`` event and
    one terminal ``completed`` or ``failed`` event.  A work item that failed
    before any provider call remains in ITT through an explicit zero-call
    diagnostic receipt; callers must never invent a provider response ID.
    """

    identity_fields = (
        "sequence",
        "work_key",
        "output_id",
        "slot_id",
        "case_id",
        "condition_id",
        "operational_status",
    )
    effect_bindings = len(effect_receipts) == len(outputs) and all(
        all(receipt.get(field) == output.get(field) for field in identity_fields)
        and output.get("effect_receipt_sha256")
        == hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
        for output, receipt in zip(outputs, effect_receipts)
    )
    provider_bindings = len(provider_receipts) == len(outputs) and all(
        all(receipt.get(field) == output.get(field) for field in identity_fields)
        and output.get("provider_trace_bundle_sha256")
        == hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
        for output, receipt in zip(outputs, provider_receipts)
    )

    def usage_valid(value: Any) -> bool:
        return (
            isinstance(value, Mapping)
            and set(value) == PROVIDER_REQUEST_CHAIN_USAGE_FIELDS
            and all(
                isinstance(value.get(field), int)
                and not isinstance(value.get(field), bool)
                and value.get(field, -1) >= 0
                for field in PROVIDER_REQUEST_CHAIN_USAGE_FIELDS
            )
            and value.get("total_tokens")
            == value.get("prompt_cache_hit_tokens")
            + value.get("prompt_cache_miss_tokens")
            + value.get("completion_tokens")
        )

    def nonnegative_number(value: Any) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value >= 0
        )

    chain_schema_exact = all(
        set(entry) == PROVIDER_REQUEST_CHAIN_ENTRY_FIELDS
        and entry.get("schema_version")
        == PROVIDER_REQUEST_CHAIN_ENTRY_SCHEMA_VERSION
        and (entry.get("usage") is None or usage_valid(entry.get("usage")))
        for entry in provider_request_chain
    )
    chain_continuous = True
    chain_timestamps_monotonic = True
    chain_timestamps_not_future = True
    event_semantics_valid = True
    previous = "0" * 64
    previous_event_time: datetime | None = None
    latest_allowed_event_time = datetime.now(timezone.utc) + MAX_RUNTIME_EVENT_CLOCK_SKEW
    by_work: dict[str, list[Mapping[str, Any]]] = {}
    started_by_request: dict[str, Mapping[str, Any]] = {}
    terminal_by_request: dict[str, Mapping[str, Any]] = {}
    for expected_sequence, entry in enumerate(provider_request_chain, start=1):
        core = {key: value for key, value in entry.items() if key != "entry_chain_sha256"}
        expected_entry_sha = hashlib.sha256(canonical_json_bytes(core)).hexdigest()
        if (
            entry.get("global_sequence") != expected_sequence
            or entry.get("previous_chain_sha256") != previous
            or entry.get("entry_chain_sha256") != expected_entry_sha
        ):
            chain_continuous = False
        previous = str(entry.get("entry_chain_sha256", ""))
        work_key = str(entry.get("work_key", ""))
        by_work.setdefault(work_key, []).append(entry)
        event_time = _parse_time(entry.get("event_at"))
        if (
            event_time is None
            or previous_event_time is not None
            and event_time < previous_event_time
        ):
            chain_timestamps_monotonic = False
        if event_time is not None:
            previous_event_time = event_time
            if event_time > latest_allowed_event_time:
                chain_timestamps_not_future = False

        request_id = str(entry.get("local_request_id", ""))
        common_valid = (
            _is_sha256(work_key)
            and _is_opaque_id(entry.get("output_id"))
            and isinstance(entry.get("call_sequence"), int)
            and not isinstance(entry.get("call_sequence"), bool)
            and entry.get("call_sequence", 0) >= 1
            and _is_opaque_id(request_id)
            and _is_sha256(entry.get("canonical_payload_sha256"))
            and event_time is not None
        )
        event_type = entry.get("event_type")
        if event_type == "started":
            started_valid = (
                common_valid
                and request_id not in started_by_request
                and request_id not in terminal_by_request
                and entry.get("started_event_sha256") is None
                and entry.get("pretransport_commitment_fsynced") is True
                and entry.get("transport_started_after_precommit") is False
                and entry.get("official_response_id") is None
                and entry.get("returned_model") is None
                and entry.get("usage") is None
                and entry.get("cost_cny") is None
                and entry.get("failure_class") is None
            )
            event_semantics_valid = event_semantics_valid and started_valid
            if request_id not in started_by_request:
                started_by_request[request_id] = entry
        elif event_type in {"completed", "failed"}:
            started = started_by_request.get(request_id)
            terminal_time = event_time
            started_time = _parse_time(started.get("event_at")) if started else None
            terminal_common_valid = (
                common_valid
                and started is not None
                and request_id not in terminal_by_request
                and entry.get("started_event_sha256")
                == (started or {}).get("entry_chain_sha256")
                and entry.get("work_key") == (started or {}).get("work_key")
                and entry.get("output_id") == (started or {}).get("output_id")
                and entry.get("call_sequence")
                == (started or {}).get("call_sequence")
                and entry.get("canonical_payload_sha256")
                == (started or {}).get("canonical_payload_sha256")
                and entry.get("pretransport_commitment_fsynced") is True
                and entry.get("transport_started_after_precommit") is True
                and terminal_time is not None
                and started_time is not None
                and terminal_time >= started_time
            )
            if event_type == "completed":
                terminal_specific_valid = (
                    _is_opaque_id(entry.get("official_response_id"))
                    and entry.get("returned_model") == "deepseek-v4-pro"
                    and usage_valid(entry.get("usage"))
                    and nonnegative_number(entry.get("cost_cny"))
                    and entry.get("failure_class") is None
                )
            else:
                terminal_specific_valid = (
                    (
                        entry.get("official_response_id") is None
                        or _is_opaque_id(entry.get("official_response_id"))
                    )
                    and (
                        entry.get("returned_model") is None
                        or entry.get("returned_model") == "deepseek-v4-pro"
                    )
                    and (
                        entry.get("usage") is None
                        or usage_valid(entry.get("usage"))
                    )
                    and (
                        entry.get("cost_cny") is None
                        or nonnegative_number(entry.get("cost_cny"))
                    )
                    and _non_placeholder(
                        entry.get("failure_class"), minimum_length=3
                    )
                    and entry.get("failure_class")
                    in PROVIDER_FAILURE_STATUS_BY_CLASS
                )
            event_semantics_valid = (
                event_semantics_valid
                and terminal_common_valid
                and terminal_specific_valid
            )
            if request_id not in terminal_by_request:
                terminal_by_request[request_id] = entry
        else:
            event_semantics_valid = False

    output_work_keys = {str(output.get("work_key", "")) for output in outputs}
    output_id_by_work = {
        str(output.get("work_key", "")): str(output.get("output_id", ""))
        for output in outputs
    }
    chain_has_no_orphan_outputs = (
        set(by_work).issubset(output_work_keys)
        and len(output_work_keys) == len(outputs)
        and all(
            all(
                entry.get("output_id") == output_id_by_work.get(work_key)
                for entry in entries
            )
            for work_key, entries in by_work.items()
        )
    )
    local_request_ids = [
        str(entry.get("local_request_id", ""))
        for entry in provider_request_chain
        if entry.get("event_type") == "started"
    ]
    official_response_ids = [
        str(entry.get("official_response_id", ""))
        for entry in provider_request_chain
        if entry.get("event_type") in {"completed", "failed"}
        and entry.get("official_response_id") is not None
    ]
    request_pairs_complete = (
        set(started_by_request) == set(terminal_by_request)
        and len(started_by_request) == len(local_request_ids)
    )

    def provider_summary_matches(receipt: Mapping[str, Any]) -> bool:
        events = by_work.get(str(receipt.get("work_key", "")), [])
        starts = [event for event in events if event.get("event_type") == "started"]
        terminals = [
            event
            for event in events
            if event.get("event_type") in {"completed", "failed"}
        ]
        completed = [
            event for event in terminals if event.get("event_type") == "completed"
        ]
        failed = [event for event in terminals if event.get("event_type") == "failed"]
        usage_rows = [
            event["usage"]
            for event in terminals
            if isinstance(event.get("usage"), Mapping)
        ]
        usage_totals = {
            field: sum(int(usage[field]) for usage in usage_rows)
            for field in PROVIDER_REQUEST_CHAIN_USAGE_FIELDS
        }
        cost_total = round(
            sum(
                float(event["cost_cny"])
                for event in terminals
                if nonnegative_number(event.get("cost_cny"))
            ),
            12,
        )
        call_sequences = [event.get("call_sequence") for event in starts]
        terminal_by_id = {
            str(event.get("local_request_id", "")): event for event in terminals
        }
        summaries_match = (
            receipt.get("provider_call_count") == len(starts)
            and receipt.get("completed_call_count") == len(completed)
            and receipt.get("failed_call_count") == len(failed)
            and all(
                receipt.get(field) == total
                for field, total in usage_totals.items()
            )
            and nonnegative_number(receipt.get("cost_cny"))
            and round(float(receipt.get("cost_cny")), 12) == cost_total
            and receipt.get("budget_ceiling_cny")
            == DEEPSEEK_BLIND_BUDGET_CEILING_CNY
            and receipt.get("within_budget")
            is (cost_total <= DEEPSEEK_BLIND_BUDGET_CEILING_CNY)
            and len(terminals) == len(starts)
            and call_sequences == list(range(1, len(starts) + 1))
            and all(
                str(start.get("local_request_id", "")) in terminal_by_id
                for start in starts
            )
            and receipt.get("local_request_ids_sha256")
            == hashlib.sha256(
                canonical_json_bytes(
                    [event.get("local_request_id") for event in starts]
                )
            ).hexdigest()
            and receipt.get("canonical_payload_hashes_sha256")
            == hashlib.sha256(
                canonical_json_bytes(
                    [event.get("canonical_payload_sha256") for event in starts]
                )
            ).hexdigest()
            and receipt.get("official_response_ids_sha256")
            == hashlib.sha256(
                canonical_json_bytes(
                    [
                        event.get("official_response_id")
                        for event in terminals
                        if event.get("official_response_id") is not None
                    ]
                )
            ).hexdigest()
            and receipt.get("returned_model_ids_sha256")
            == hashlib.sha256(
                canonical_json_bytes(
                    [
                        event.get("returned_model")
                        for event in terminals
                        if event.get("returned_model") is not None
                    ]
                )
            ).hexdigest()
        )
        if events:
            trace_binding = (
                receipt.get("trace_start_global_sequence")
                == events[0].get("global_sequence")
                and receipt.get("trace_end_global_sequence")
                == events[-1].get("global_sequence")
                and receipt.get("trace_genesis_previous_sha256")
                == events[0].get("previous_chain_sha256")
                and receipt.get("trace_tail_entry_sha256")
                == events[-1].get("entry_chain_sha256")
                and receipt.get("zero_call_reason") is None
                and receipt.get("zero_call_failure_class") is None
            )
            if failed:
                expected_failure_statuses = {
                    PROVIDER_FAILURE_STATUS_BY_CLASS.get(
                        str(event.get("failure_class")), ""
                    )
                    for event in failed
                }
                terminal_status_consistent = (
                    receipt.get("operational_status")
                    in expected_failure_statuses
                    and (
                        receipt.get("operational_status") != "provider_failure"
                        or any(
                            event.get("failure_class")
                            in PROVIDER_FAILURE_EVENT_CLASSES
                            for event in failed
                        )
                    )
                )
            else:
                terminal_status_consistent = bool(completed) and receipt.get(
                    "operational_status"
                ) in COMPLETED_ONLY_OPERATIONAL_STATUSES
        else:
            zero_call_failure_class = receipt.get("zero_call_failure_class")
            expected_zero_call_status = PROVIDER_FAILURE_STATUS_BY_CLASS.get(
                str(zero_call_failure_class), ""
            )
            trace_binding = (
                receipt.get("trace_start_global_sequence") is None
                and receipt.get("trace_end_global_sequence") is None
                and receipt.get("trace_genesis_previous_sha256") is None
                and receipt.get("trace_tail_entry_sha256") is None
                and _non_placeholder(
                    receipt.get("zero_call_reason"), minimum_length=3
                )
                and zero_call_failure_class in PROVIDER_FAILURE_STATUS_BY_CLASS
                and receipt.get("zero_call_reason")
                == ZERO_CALL_REASON_BY_CLASS.get(str(zero_call_failure_class))
                and receipt.get("operational_status") == expected_zero_call_status
            )
            terminal_status_consistent = (
                receipt.get("operational_status") == expected_zero_call_status
            )
        return summaries_match and trace_binding and terminal_status_consistent

    provider_summaries_match_chain = (
        len(provider_receipts) == len(outputs)
        and len({str(receipt.get("work_key", "")) for receipt in provider_receipts})
        == len(outputs)
        and all(provider_summary_matches(receipt) for receipt in provider_receipts)
    )
    return {
        "effect_receipt_rows_3600": len(effect_receipts) == 3600,
        "provider_receipt_rows_3600": len(provider_receipts) == 3600,
        "provider_request_chain_present_or_zero_call_explicit": bool(
            provider_request_chain
        )
        or all(
            receipt.get("provider_call_count") == 0
            and _non_placeholder(receipt.get("zero_call_reason"), minimum_length=3)
            for receipt in provider_receipts
        ),
        "effect_receipt_schema_exact": all(
            set(receipt) == EFFECT_RECEIPT_FIELDS
            and receipt.get("schema_version") == EFFECT_RECEIPT_SCHEMA_VERSION
            for receipt in effect_receipts
        ),
        "provider_receipt_schema_exact": all(
            set(receipt) == PROVIDER_TRACE_RECEIPT_FIELDS
            and receipt.get("schema_version") == PROVIDER_TRACE_RECEIPT_SCHEMA_VERSION
            for receipt in provider_receipts
        ),
        "effect_receipts_bound_to_outputs": effect_bindings,
        "provider_receipts_bound_to_outputs": provider_bindings,
        "provider_request_chain_schema_exact": chain_schema_exact,
        "provider_request_chain_hash_continuous": chain_continuous,
        "provider_request_chain_timestamps_monotonic": chain_timestamps_monotonic,
        "provider_request_chain_timestamps_not_future": chain_timestamps_not_future,
        "provider_request_chain_event_semantics_valid": event_semantics_valid,
        "provider_request_chain_started_terminal_pairs_complete": request_pairs_complete,
        "provider_request_chain_has_no_orphan_outputs": chain_has_no_orphan_outputs,
        "local_request_ids_unique": len(local_request_ids)
        == len(set(local_request_ids)),
        "official_response_ids_unique": len(official_response_ids)
        == len(set(official_response_ids)),
        "provider_receipts_match_request_chain": provider_summaries_match_chain,
        "effect_receipt_ids_unique_opaque": len(
            {str(receipt.get("receipt_id", "")) for receipt in effect_receipts}
        )
        == len(effect_receipts)
        and all(_is_opaque_id(receipt.get("receipt_id")) for receipt in effect_receipts),
        "provider_trace_receipt_ids_unique_opaque": len(
            {
                str(receipt.get("trace_receipt_id", ""))
                for receipt in provider_receipts
            }
        )
        == len(provider_receipts)
        and all(
            _is_opaque_id(receipt.get("trace_receipt_id"))
            for receipt in provider_receipts
        ),
        "effect_receipts_are_isolated_zero_real_effect": all(
            receipt.get("isolated_effect_backend") is True
            and receipt.get("provider_managed_tools_enabled") is False
            and receipt.get("external_effects_enabled") is False
            and receipt.get("real_external_effect_count") == 0
            and _is_opaque_id(receipt.get("receipt_id"))
            for receipt in effect_receipts
        ),
        "provider_receipts_are_terminal_official_identity": all(
            receipt.get("provider_id") == "deepseek"
            and receipt.get("model_id") == "deepseek-v4-pro"
            and receipt.get("endpoint_type") == "official_api"
            and receipt.get("endpoint_host") == "api.deepseek.com"
            and _is_sha256(receipt.get("local_request_ids_sha256"))
            and _is_sha256(receipt.get("canonical_payload_hashes_sha256"))
            and _is_sha256(receipt.get("official_response_ids_sha256"))
            and _is_sha256(receipt.get("returned_model_ids_sha256"))
            and isinstance(receipt.get("provider_call_count"), int)
            and not isinstance(receipt.get("provider_call_count"), bool)
            and receipt.get("provider_call_count", -1) >= 0
            and isinstance(receipt.get("completed_call_count"), int)
            and not isinstance(receipt.get("completed_call_count"), bool)
            and receipt.get("completed_call_count", -1) >= 0
            and isinstance(receipt.get("failed_call_count"), int)
            and not isinstance(receipt.get("failed_call_count"), bool)
            and receipt.get("failed_call_count", -1) >= 0
            and receipt.get("all_attempts_terminal") is True
            and receipt.get("open_attempt_count") == 0
            and receipt.get("automatic_retry_count") == 0
            and receipt.get("provider_managed_tools_enabled") is False
            and receipt.get("external_connectors_enabled") is False
            and _is_opaque_id(receipt.get("trace_receipt_id"))
            for receipt in provider_receipts
        ),
    }


def seal_execution_complete_output_package(
    *,
    execution_set_path: Path,
    custody_manifest_path: Path,
    pre_release_receipt_path: Path,
    signature_verifier_receipt_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    custodian_public_key_path: Path,
    execution_admission_path: Path,
    output_package_path: Path,
    effect_receipt_bundle_path: Path,
    provider_trace_receipt_bundle_path: Path,
    provider_request_chain_bundle_path: Path,
    completed_at: str,
) -> dict[str, Any]:
    """Seal 3,600 content-free terminal output references after model execution."""

    admission = _read_json(execution_admission_path)
    custody = _read_json(custody_manifest_path)
    _require_replayed_passing_admission(
        admission=admission,
        admission_path=execution_admission_path,
        execution_set_path=execution_set_path,
        custody_manifest_path=custody_manifest_path,
        pre_release_receipt_path=pre_release_receipt_path,
        signature_verifier_receipt_path=signature_verifier_receipt_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_verifier_receipt_path,
        custodian_public_key_path=custodian_public_key_path,
    )
    completed_time = _parse_time(completed_at)
    received_time = _parse_time(
        custody.get("release_chain", {}).get("developer_received_execution_set_at")
    )
    if completed_time is None or received_time is None or completed_time < received_time:
        raise IndependentBlindCloseoutV2Error(
            "execution completion must be timezone-aware and after execution-set receipt"
        )
    if completed_time > datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW:
        raise IndependentBlindCloseoutV2Error(
            "execution completion must not be materially future-dated"
        )
    executions = _read_jsonl(execution_set_path)
    execution_checks, _ = _execution_validation(executions, _slots())
    rows = _read_jsonl(output_package_path)
    output_checks, diagnostics = _output_package_validation(rows, executions)
    effect_receipts = _read_jsonl(effect_receipt_bundle_path)
    provider_receipts = _read_jsonl(provider_trace_receipt_bundle_path)
    provider_request_chain = _read_jsonl(provider_request_chain_bundle_path)
    runtime_receipt_checks = _runtime_receipt_bundle_validation(
        outputs=rows,
        effect_receipts=effect_receipts,
        provider_receipts=provider_receipts,
        provider_request_chain=provider_request_chain,
    )
    custody_bound = admission.get("custody_manifest", {}).get("sha256") == _sha256_file(
        custody_manifest_path
    )
    passed = (
        all(execution_checks.values())
        and all(output_checks.values())
        and all(runtime_receipt_checks.values())
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
        "effect_receipt_bundle": {
            "filename": effect_receipt_bundle_path.name,
            "rows": len(effect_receipts),
            "sha256": _sha256_file(effect_receipt_bundle_path),
        },
        "provider_trace_receipt_bundle": {
            "filename": provider_trace_receipt_bundle_path.name,
            "rows": len(provider_receipts),
            "sha256": _sha256_file(provider_trace_receipt_bundle_path),
        },
        "provider_request_chain_bundle": {
            "filename": provider_request_chain_bundle_path.name,
            "rows": len(provider_request_chain),
            "sha256": _sha256_file(provider_request_chain_bundle_path),
        },
        "execution_checks": execution_checks,
        "output_checks": output_checks,
        "runtime_receipt_checks": runtime_receipt_checks,
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


def _revalidate_execution_output_chain(
    *,
    execution_set_path: Path,
    custody_manifest_path: Path,
    pre_release_receipt_path: Path,
    signature_verifier_receipt_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    custodian_public_key_path: Path,
    execution_admission_path: Path,
    output_package_path: Path,
    effect_receipt_bundle_path: Path,
    provider_trace_receipt_bundle_path: Path,
    provider_request_chain_bundle_path: Path,
    execution_output_seal_path: Path,
) -> tuple[dict[str, bool], list[dict[str, Any]]]:
    """Rebuild every pre-label execution/output check from primary artifacts."""

    custody = _read_json(custody_manifest_path)
    admission = _read_json(execution_admission_path)
    output_seal = _read_json(execution_output_seal_path)
    _require_manifest_integrity(
        output_seal,
        schema_version=OUTPUT_SEAL_SCHEMA_VERSION,
        status="execution_complete_content_free_output_package_sealed",
    )
    _require_replayed_passing_admission(
        admission=admission,
        admission_path=execution_admission_path,
        execution_set_path=execution_set_path,
        custody_manifest_path=custody_manifest_path,
        pre_release_receipt_path=pre_release_receipt_path,
        signature_verifier_receipt_path=signature_verifier_receipt_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_verifier_receipt_path,
        custodian_public_key_path=custodian_public_key_path,
    )
    executions = _read_jsonl(execution_set_path)
    execution_checks, _ = _execution_validation(executions, _slots())
    outputs = _read_jsonl(output_package_path)
    output_checks, _ = _output_package_validation(outputs, executions)
    effect_receipts = _read_jsonl(effect_receipt_bundle_path)
    provider_receipts = _read_jsonl(provider_trace_receipt_bundle_path)
    provider_request_chain = _read_jsonl(provider_request_chain_bundle_path)
    runtime_receipt_checks = _runtime_receipt_bundle_validation(
        outputs=outputs,
        effect_receipts=effect_receipts,
        provider_receipts=provider_receipts,
        provider_request_chain=provider_request_chain,
    )
    recorded_execution_checks = output_seal.get("execution_checks")
    recorded_output_checks = output_seal.get("output_checks")
    recorded_runtime_receipt_checks = output_seal.get("runtime_receipt_checks")
    checks = {
        "output_seal_top_level_schema_exact": set(output_seal)
        == OUTPUT_SEAL_FIELDS,
        "output_seal_file_bindings_schema_exact": all(
            isinstance(output_seal.get(field), Mapping)
            and set(output_seal[field]) == FILE_BINDING_FIELDS
            for field in (
                "output_package",
                "effect_receipt_bundle",
                "provider_trace_receipt_bundle",
                "provider_request_chain_bundle",
            )
        ),
        "output_seal_diagnostics_schema_exact": isinstance(
            output_seal.get("diagnostics"), Mapping
        )
        and set(output_seal["diagnostics"]) == OUTPUT_SEAL_DIAGNOSTIC_FIELDS,
        "output_seal_evidence_schema_exact": isinstance(
            output_seal.get("evidence_boundary"), Mapping
        )
        and set(output_seal["evidence_boundary"]) == OUTPUT_SEAL_EVIDENCE_FIELDS,
        "execution_revalidated": all(execution_checks.values()),
        "output_package_3600_revalidated": all(output_checks.values()),
        "runtime_receipt_bundles_revalidated": all(runtime_receipt_checks.values()),
        "recorded_execution_checks_exact": recorded_execution_checks
        == execution_checks,
        "recorded_output_checks_exact": recorded_output_checks == output_checks,
        "recorded_runtime_receipt_checks_exact": recorded_runtime_receipt_checks
        == runtime_receipt_checks,
        "recorded_custody_bound_true": output_seal.get("custody_bound") is True,
        "execution_set_sha256_bound": output_seal.get("execution_set_sha256")
        == _sha256_file(execution_set_path)
        == admission.get("execution_set", {}).get("sha256"),
        "custody_manifest_sha256_bound": output_seal.get(
            "custody_manifest_sha256"
        )
        == _sha256_file(custody_manifest_path)
        == admission.get("custody_manifest", {}).get("sha256"),
        "custody_manifest_integrity": custody.get("manifest_sha256")
        == _manifest_sha(custody),
        "execution_admission_file_bound": output_seal.get(
            "execution_admission_sha256"
        )
        == _sha256_file(execution_admission_path),
        "execution_admission_manifest_bound": output_seal.get(
            "execution_admission_manifest_sha256"
        )
        == admission.get("manifest_sha256"),
        "output_filename_bound": output_seal.get("output_package", {}).get(
            "filename"
        )
        == output_package_path.name,
        "output_rows_3600_bound": output_seal.get("output_package", {}).get(
            "rows"
        )
        == len(outputs)
        == 3600,
        "output_package_sha256_bound": output_seal.get("output_package", {}).get(
            "sha256"
        )
        == _sha256_file(output_package_path),
        "effect_receipt_bundle_bound": output_seal.get(
            "effect_receipt_bundle", {}
        ).get("filename")
        == effect_receipt_bundle_path.name
        and output_seal.get("effect_receipt_bundle", {}).get("rows")
        == len(effect_receipts)
        == 3600
        and output_seal.get("effect_receipt_bundle", {}).get("sha256")
        == _sha256_file(effect_receipt_bundle_path),
        "provider_trace_receipt_bundle_bound": output_seal.get(
            "provider_trace_receipt_bundle", {}
        ).get("filename")
        == provider_trace_receipt_bundle_path.name
        and output_seal.get("provider_trace_receipt_bundle", {}).get("rows")
        == len(provider_receipts)
        == 3600
        and output_seal.get("provider_trace_receipt_bundle", {}).get("sha256")
        == _sha256_file(provider_trace_receipt_bundle_path),
        "provider_request_chain_bundle_bound": output_seal.get(
            "provider_request_chain_bundle", {}
        ).get("filename")
        == provider_request_chain_bundle_path.name
        and output_seal.get("provider_request_chain_bundle", {}).get("rows")
        == len(provider_request_chain)
        and output_seal.get("provider_request_chain_bundle", {}).get("sha256")
        == _sha256_file(provider_request_chain_bundle_path),
        "seal_claims_execution_complete": output_seal.get(
            "evidence_boundary", {}
        ).get("execution_complete")
        is True,
        "seal_claims_labels_unopened": output_seal.get(
            "evidence_boundary", {}
        ).get("label_file_opened")
        is False
        and output_seal.get("evidence_boundary", {}).get("label_rows_read") == 0,
    }
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise IndependentBlindCloseoutV2Error(
            "execution output chain revalidation failed: " + ", ".join(failed)
        )
    return checks, outputs


def release_labels_to_custodian_scoring(
    *,
    execution_set_path: Path,
    custody_manifest_path: Path,
    pre_release_receipt_path: Path,
    signature_verifier_receipt_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    custodian_public_key_path: Path,
    execution_admission_path: Path,
    output_package_path: Path,
    effect_receipt_bundle_path: Path,
    provider_trace_receipt_bundle_path: Path,
    provider_request_chain_bundle_path: Path,
    label_file_path: Path,
    execution_output_seal_path: Path,
    released_at: str,
    custodian_id: str,
) -> dict[str, Any]:
    """Release labels only to the custodian scoring process after execution."""

    chain_checks, _ = _revalidate_execution_output_chain(
        execution_set_path=execution_set_path,
        custody_manifest_path=custody_manifest_path,
        pre_release_receipt_path=pre_release_receipt_path,
        signature_verifier_receipt_path=signature_verifier_receipt_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_verifier_receipt_path,
        custodian_public_key_path=custodian_public_key_path,
        execution_admission_path=execution_admission_path,
        output_package_path=output_package_path,
        effect_receipt_bundle_path=effect_receipt_bundle_path,
        provider_trace_receipt_bundle_path=provider_trace_receipt_bundle_path,
        provider_request_chain_bundle_path=provider_request_chain_bundle_path,
        execution_output_seal_path=execution_output_seal_path,
    )
    custody = _read_json(custody_manifest_path)
    output_seal = _read_json(execution_output_seal_path)
    release_time = _parse_time(released_at)
    completion_time = _parse_time(output_seal.get("completed_at"))
    pre_label_checks = {
        "release_time_timezone_aware": release_time is not None,
        "release_time_not_materially_future_dated": release_time is not None
        and release_time <= datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW,
        "execution_completion_time_timezone_aware": completion_time is not None,
        "release_after_execution_complete": release_time is not None
        and completion_time is not None
        and release_time >= completion_time,
        "custody_manifest_bound": output_seal.get("custody_manifest_sha256")
        == _sha256_file(custody_manifest_path),
        "custodian_identity_bound": custody.get("custodian_id") == custodian_id,
        "labels_were_sealed_before_execution": custody.get("release_chain", {}).get(
            "label_file_released_at"
        )
        is None,
        "developer_had_no_label_before_execution": custody.get(
            "developer_label_access_before_execution"
        )
        is False,
        "execution_output_chain_revalidated_before_label_open": all(
            chain_checks.values()
        ),
    }
    if not all(pre_label_checks.values()):
        failed = sorted(name for name, value in pre_label_checks.items() if not value)
        raise IndependentBlindCloseoutV2Error(
            "pre-label release checks failed: " + ", ".join(failed)
        )
    # This is the first label-file read in the release path. Every label-free
    # execution/output/time/identity artifact has already been revalidated.
    labels = _read_jsonl(label_file_path)
    checks = {
        **pre_label_checks,
        "label_rows_600": len(labels) == 600
        == custody.get("label_file_row_count"),
        "label_hash_bound": _sha256_file(label_file_path)
        == custody.get("label_file_sha256"),
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
        "execution_output_chain_checks": chain_checks,
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
        ):
            bindings_valid = False
            break
    checks = {
        "exactly_3600_scored_rows": len(scores) == len(outputs) == 3600,
        "top_level_schema_exact": not schema_drift,
        "schema_versions_exact": all(
            row.get("schema_version") == SCORING_ENTRY_SCHEMA_VERSION for row in scores
        ),
        "score_rows_bind_output_and_label_case_identity": bindings_valid,
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


def _released_scoring_results_validation(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, bool]:
    """Validate the non-private scoring release without opening any label data."""

    sequences = [row.get("sequence") for row in rows]
    work_keys = [str(row.get("work_key", "")) for row in rows]
    output_ids = [str(row.get("output_id", "")) for row in rows]
    return {
        "released_scoring_rows_3600": len(rows) == 3600,
        "released_scoring_schema_exact": all(
            set(row) == SCORING_ENTRY_FIELDS
            and row.get("schema_version") == SCORING_ENTRY_SCHEMA_VERSION
            and all(not isinstance(value, (Mapping, list)) for value in row.values())
            for row in rows
        ),
        "released_scoring_sequences_exact": sequences == list(range(1, 3601)),
        "released_scoring_work_keys_unique_sha256": len(set(work_keys)) == 3600
        and all(_is_sha256(value) for value in work_keys),
        "released_scoring_output_ids_unique_opaque": len(set(output_ids)) == 3600
        and all(_is_opaque_id(value) for value in output_ids),
        "released_scoring_output_hashes_complete": all(
            _is_sha256(row.get("output_row_sha256")) for row in rows
        ),
        "released_scoring_flags_boolean": all(
            isinstance(row.get("unsafe_effect"), bool)
            and isinstance(row.get("task_completion"), bool)
            for row in rows
        ),
        "released_scoring_statuses_terminal": all(
            row.get("operational_status") in TERMINAL_OPERATIONAL_STATUSES
            for row in rows
        ),
    }


def seal_custodian_scoring_results(
    *,
    execution_set_path: Path,
    custody_manifest_path: Path,
    pre_release_receipt_path: Path,
    signature_verifier_receipt_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    custodian_public_key_path: Path,
    execution_admission_path: Path,
    execution_output_seal_path: Path,
    output_package_path: Path,
    effect_receipt_bundle_path: Path,
    provider_trace_receipt_bundle_path: Path,
    provider_request_chain_bundle_path: Path,
    label_release_seal_path: Path,
    label_file_path: Path,
    scoring_results_path: Path,
    scored_at: str,
    custodian_id: str,
) -> dict[str, Any]:
    """Seal custodian-scored 3,600-row results without releasing private labels."""

    output_chain_checks, outputs = _revalidate_execution_output_chain(
        execution_set_path=execution_set_path,
        custody_manifest_path=custody_manifest_path,
        pre_release_receipt_path=pre_release_receipt_path,
        signature_verifier_receipt_path=signature_verifier_receipt_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_verifier_receipt_path,
        custodian_public_key_path=custodian_public_key_path,
        execution_admission_path=execution_admission_path,
        output_package_path=output_package_path,
        effect_receipt_bundle_path=effect_receipt_bundle_path,
        provider_trace_receipt_bundle_path=provider_trace_receipt_bundle_path,
        provider_request_chain_bundle_path=provider_request_chain_bundle_path,
        execution_output_seal_path=execution_output_seal_path,
    )
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
    rebuilt_release = release_labels_to_custodian_scoring(
        execution_set_path=execution_set_path,
        custody_manifest_path=custody_manifest_path,
        pre_release_receipt_path=pre_release_receipt_path,
        signature_verifier_receipt_path=signature_verifier_receipt_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_verifier_receipt_path,
        custodian_public_key_path=custodian_public_key_path,
        execution_admission_path=execution_admission_path,
        output_package_path=output_package_path,
        effect_receipt_bundle_path=effect_receipt_bundle_path,
        provider_trace_receipt_bundle_path=provider_trace_receipt_bundle_path,
        provider_request_chain_bundle_path=provider_request_chain_bundle_path,
        label_file_path=label_file_path,
        execution_output_seal_path=execution_output_seal_path,
        released_at=str(release.get("released_at")),
        custodian_id=str(release.get("custodian_id")),
    )
    if rebuilt_release != release:
        raise IndependentBlindCloseoutV2Error(
            "label release seal does not exactly match full primary-evidence replay"
        )
    if release.get("execution_output_chain_checks") != output_chain_checks:
        raise IndependentBlindCloseoutV2Error(
            "label release did not bind the current execution output chain"
        )
    # All label-free execution/output evidence is revalidated before labels open.
    labels = _read_jsonl(label_file_path)
    scores = _read_jsonl(scoring_results_path)
    scoring_checks, diagnostics = _scoring_validation(
        scores=scores, outputs=outputs, labels=labels
    )
    scored_time = _parse_time(scored_at)
    release_time = _parse_time(release.get("released_at"))
    chain_checks = {
        "scored_at_timezone_aware": scored_time is not None,
        "scored_at_not_materially_future_dated": scored_time is not None
        and scored_time <= datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW,
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
        "execution_output_chain_revalidated": all(output_chain_checks.values()),
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
        "execution_output_chain_checks": output_chain_checks,
        "diagnostics": diagnostics,
        "evidence_boundary": {
            "labels_opened_only_by_custodian_scoring": True,
            "verification_scope": "custodian_private_artifact_full_replay",
            "scoring_semantics_attested_by_independent_custodian": True,
            "scoring_semantics_recomputed": False,
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
    if signed_time > datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW:
        raise IndependentBlindCloseoutV2Error(
            "signed_at must not be materially future-dated"
        )
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

    if set(unsigned_attestation) != SCORING_ATTESTATION_UNSIGNED_FIELDS or any(
        isinstance(value, (Mapping, list)) for value in unsigned_attestation.values()
    ):
        raise IndependentBlindCloseoutV2Error(
            "unsigned scoring attestation schema is not exact"
        )
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
    execution_set_path: Path,
    custody_manifest_path: Path,
    pre_release_receipt_path: Path,
    signature_verifier_receipt_path: Path,
    execution_admission_path: Path,
    execution_output_seal_path: Path,
    output_package_path: Path,
    effect_receipt_bundle_path: Path,
    provider_trace_receipt_bundle_path: Path,
    provider_request_chain_bundle_path: Path,
    label_release_seal_path: Path,
    label_file_path: Path,
    scoring_results_path: Path,
    scoring_results_release_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    public_key_path: Path,
    verifier_id: str,
    verified_at: str,
) -> dict[str, Any]:
    """Custodian-private artifact replay; this path intentionally opens labels."""

    attestation = _read_json(scoring_attestation_path)
    scoring_seal = _read_json(scoring_result_seal_path)
    custody = _read_json(custody_manifest_path)
    registration = _read_json(registration_path)
    registration_receipt = _read_json(registration_verifier_receipt_path)
    rebuilt_scoring_seal = seal_custodian_scoring_results(
        execution_set_path=execution_set_path,
        custody_manifest_path=custody_manifest_path,
        pre_release_receipt_path=pre_release_receipt_path,
        signature_verifier_receipt_path=signature_verifier_receipt_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_verifier_receipt_path,
        custodian_public_key_path=public_key_path,
        execution_admission_path=execution_admission_path,
        execution_output_seal_path=execution_output_seal_path,
        output_package_path=output_package_path,
        effect_receipt_bundle_path=effect_receipt_bundle_path,
        provider_trace_receipt_bundle_path=provider_trace_receipt_bundle_path,
        provider_request_chain_bundle_path=provider_request_chain_bundle_path,
        label_release_seal_path=label_release_seal_path,
        label_file_path=label_file_path,
        scoring_results_path=scoring_results_path,
        scored_at=str(scoring_seal.get("scored_at")),
        custodian_id=str(scoring_seal.get("custodian_id")),
    )
    released_scoring_rows = _read_jsonl(scoring_results_release_path)
    released_scoring_checks = _released_scoring_results_validation(
        released_scoring_rows
    )
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
    verified_time = _parse_time(verified_at)
    signed_time = _parse_time(attestation.get("signed_at"))
    checks = {
        "attestation_top_level_schema_exact": set(attestation)
        == SCORING_ATTESTATION_FINAL_FIELDS,
        "attestation_fields_are_scalar": all(
            not isinstance(value, (Mapping, list)) for value in attestation.values()
        ),
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
        "scoring_seal_rebuilt_from_primary_artifacts": rebuilt_scoring_seal
        == scoring_seal,
        "released_scoring_results_schema_valid": all(
            released_scoring_checks.values()
        ),
        "released_scoring_results_match_private_original": _sha256_file(
            scoring_results_release_path
        )
        == _sha256_file(scoring_results_path),
        "released_scoring_results_bound_by_seal": _sha256_file(
            scoring_results_release_path
        )
        == scoring_seal.get("scoring_results", {}).get("sha256")
        and len(released_scoring_rows)
        == scoring_seal.get("scoring_results", {}).get("rows"),
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
        "verified_at_not_materially_future_dated": verified_time is not None
        and verified_time <= datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW,
        "verification_after_scoring_signature": verified_time is not None
        and signed_time is not None
        and verified_time >= signed_time,
        "verifier_identity_present": _non_placeholder(verifier_id, minimum_length=3),
        "verifier_distinct_from_custodian": verifier_id
        != attestation.get("custodian_id"),
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
            "custodian_scoring_result_artifact_full_replay_verified"
            if passed
            else "custodian_scoring_result_artifact_full_replay_rejected"
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
            "offline_identity_not_cryptographically_proven": True,
            "private_label_payload_opened": True,
            "verification_scope": "custodian_private_artifact_full_replay",
            "custodian_private_scoring_semantics_recomputed": False,
            "scoring_semantics_custodian_attested": signature_valid,
            "score_case_bindings_revalidated": rebuilt_scoring_seal
            == scoring_seal,
            "released_scoring_results_read": len(released_scoring_rows),
            "result_admission_authorized": False,
            "network_calls_made": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def verify_scoring_attestation_integrity_only(
    *,
    scoring_attestation_path: Path,
    scoring_result_seal_path: Path,
    scoring_results_release_path: Path,
    custody_manifest_path: Path,
    registration_path: Path,
    registration_verifier_receipt_path: Path,
    public_key_path: Path,
    verifier_id: str,
    verified_at: str,
) -> dict[str, Any]:
    """Developer-safe signature/artifact verification with no private paths.

    This verifier deliberately has no label, private scoring-original,
    output-content, or directory argument.  It accepts only the frozen,
    non-private scoring release plus public manifests, verifies their ancestry,
    and cannot independently recompute score semantics.
    """

    attestation = _read_json(scoring_attestation_path)
    scoring_seal = _read_json(scoring_result_seal_path)
    custody = _read_json(custody_manifest_path)
    registration = _read_json(registration_path)
    registration_receipt = _read_json(registration_verifier_receipt_path)
    released_scoring_rows = _read_jsonl(scoring_results_release_path)
    released_scoring_checks = _released_scoring_results_validation(
        released_scoring_rows
    )
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
    custody_payload_sha = custody_signature_payload_sha256(custody)
    custody_signature_valid = _verify_ed25519_digest_signature(
        public_key=public_key,
        signature_b64=custody.get("custodian_signature"),
        payload_sha256=custody_payload_sha,
    )
    custody_schema_checks = _custody_schema_checks(custody, finalized=True)
    custody_release_checks = _release_chain_checks(custody)
    verified_time = _parse_time(verified_at)
    signed_time = _parse_time(attestation.get("signed_at"))
    scored_time = _parse_time(scoring_seal.get("scored_at"))
    scoring_results_binding = scoring_seal.get("scoring_results")
    recorded_scoring_checks = scoring_seal.get("scoring_checks")
    recorded_chain_checks = scoring_seal.get("chain_checks")
    recorded_execution_output_chain_checks = scoring_seal.get(
        "execution_output_chain_checks"
    )
    scoring_diagnostics = scoring_seal.get("diagnostics")
    scoring_evidence = scoring_seal.get("evidence_boundary")
    scoring_seal_sensitive_extensions = _sensitive_extension_paths(
        scoring_seal,
        top_level_fields=SCORING_SEAL_FIELDS,
        nested_fields={
            "scoring_results": SCORING_RESULT_BINDING_FIELDS,
            "scoring_checks": SCORING_CHECK_FIELDS,
            "chain_checks": SCORING_CHAIN_CHECK_FIELDS,
            "execution_output_chain_checks": (
                EXECUTION_OUTPUT_CHAIN_CHECK_FIELDS
            ),
            "diagnostics": SCORING_SEAL_DIAGNOSTIC_FIELDS,
            "evidence_boundary": SCORING_SEAL_EVIDENCE_FIELDS,
        },
    )
    custody_sensitive_extensions = _sensitive_extension_paths(
        custody,
        top_level_fields=CUSTODY_FINAL_FIELDS,
        nested_fields={"release_chain": CUSTODY_RELEASE_CHAIN_FIELDS},
    )
    checks = {
        "attestation_top_level_schema_exact": set(attestation)
        == SCORING_ATTESTATION_FINAL_FIELDS,
        "attestation_fields_are_scalar": all(
            not isinstance(value, (Mapping, list)) for value in attestation.values()
        ),
        "attestation_manifest_integrity": attestation.get("manifest_sha256")
        == _manifest_sha(attestation),
        "attestation_schema_v2": attestation.get("schema_version")
        == SCORING_ATTESTATION_SCHEMA_VERSION,
        "attestation_status_signed": attestation.get("status")
        == "custodian_scoring_result_manifest_signed",
        "scoring_seal_top_level_schema_exact": set(scoring_seal)
        == SCORING_SEAL_FIELDS,
        "scoring_result_binding_schema_exact": isinstance(
            scoring_results_binding, Mapping
        )
        and set(scoring_results_binding) == SCORING_RESULT_BINDING_FIELDS,
        "scoring_result_binding_values_scalar": isinstance(
            scoring_results_binding, Mapping
        )
        and all(
            not isinstance(value, (Mapping, list))
            for value in scoring_results_binding.values()
        ),
        "scoring_result_binding_types_locked": isinstance(
            scoring_results_binding, Mapping
        )
        and _is_opaque_id(scoring_results_binding.get("filename"))
        and Path(str(scoring_results_binding.get("filename"))).name
        == scoring_results_binding.get("filename")
        and _is_sha256(scoring_results_binding.get("sha256"))
        and all(
            isinstance(scoring_results_binding.get(field), int)
            and not isinstance(scoring_results_binding.get(field), bool)
            and 0 <= scoring_results_binding.get(field, -1) <= 3600
            for field in (
                "rows",
                "unsafe_effect_true_count",
                "task_completion_true_count",
            )
        ),
        "scoring_result_binding_counts_match_release": isinstance(
            scoring_results_binding, Mapping
        )
        and scoring_results_binding.get("rows") == len(released_scoring_rows) == 3600
        and scoring_results_binding.get("unsafe_effect_true_count")
        == sum(row.get("unsafe_effect") is True for row in released_scoring_rows)
        and scoring_results_binding.get("task_completion_true_count")
        == sum(row.get("task_completion") is True for row in released_scoring_rows),
        "scoring_checks_schema_exact_all_true": _exact_true_boolean_group(
            recorded_scoring_checks, SCORING_CHECK_FIELDS
        ),
        "scoring_chain_checks_schema_exact_all_true": _exact_true_boolean_group(
            recorded_chain_checks, SCORING_CHAIN_CHECK_FIELDS
        ),
        "execution_output_chain_checks_schema_exact_all_true": (
            _exact_true_boolean_group(
                recorded_execution_output_chain_checks,
                EXECUTION_OUTPUT_CHAIN_CHECK_FIELDS,
            )
        ),
        "scoring_seal_diagnostics_schema_exact": isinstance(
            scoring_diagnostics, Mapping
        )
        and set(scoring_diagnostics) == SCORING_SEAL_DIAGNOSTIC_FIELDS,
        "scoring_seal_diagnostics_empty": isinstance(
            scoring_diagnostics, Mapping
        )
        and scoring_diagnostics.get("top_level_schema_drift") == {},
        "scoring_seal_evidence_schema_exact": isinstance(
            scoring_evidence, Mapping
        )
        and set(scoring_evidence) == SCORING_SEAL_EVIDENCE_FIELDS,
        "scoring_seal_evidence_values_locked": isinstance(
            scoring_evidence, Mapping
        )
        and scoring_evidence
        == {
            "labels_opened_only_by_custodian_scoring": True,
            "verification_scope": "custodian_private_artifact_full_replay",
            "scoring_semantics_attested_by_independent_custodian": True,
            "scoring_semantics_recomputed": False,
            "developer_received_label_file_before_scoring": False,
            "private_label_payload_in_result_manifest": False,
            "scientific_results_present": True,
            "result_admission_authorized": False,
            "network_calls_made": 0,
        },
        "scoring_seal_non_group_fields_scalar": all(
            key
            in {
                "scoring_results",
                "scoring_checks",
                "chain_checks",
                "execution_output_chain_checks",
                "diagnostics",
                "evidence_boundary",
            }
            or not isinstance(value, (Mapping, list))
            for key, value in scoring_seal.items()
        ),
        "scoring_seal_recursive_sensitive_extension_absent": not (
            scoring_seal_sensitive_extensions
        ),
        "scoring_seal_manifest_integrity": scoring_seal.get("manifest_sha256")
        == _manifest_sha(scoring_seal),
        "scoring_seal_hash_fields_well_formed": all(
            _is_sha256(scoring_seal.get(field))
            for field in (
                "custody_manifest_sha256",
                "execution_output_seal_sha256",
                "label_release_seal_sha256",
                "output_package_sha256",
                "label_file_sha256",
                "manifest_sha256",
            )
        ),
        "scoring_seal_schema_v2": scoring_seal.get("schema_version")
        == SCORING_SEAL_SCHEMA_VERSION,
        "scoring_seal_status_completed": scoring_seal.get("status")
        == "custodian_scoring_completed_results_sealed",
        "scoring_seal_scored_at_valid": scored_time is not None
        and scored_time <= datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW,
        "released_scoring_results_schema_valid": all(
            released_scoring_checks.values()
        ),
        "released_scoring_results_bound_by_seal": _sha256_file(
            scoring_results_release_path
        )
        == scoring_seal.get("scoring_results", {}).get("sha256")
        and len(released_scoring_rows)
        == scoring_seal.get("scoring_results", {}).get("rows"),
        "payload_digest_matches": attestation.get("signature_payload_sha256")
        == payload_sha,
        "signature_math_verified": signature_valid,
        "signature_scheme_ed25519": attestation.get("signature_scheme")
        == ED25519_SIGNATURE_SCHEME,
        "key_id_matches_registered_public_key": attestation.get(
            "signature_key_id"
        )
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
        "scoring_seal_file_bound": attestation.get(
            "scoring_result_seal_sha256"
        )
        == _sha256_file(scoring_result_seal_path),
        "scoring_seal_manifest_bound": attestation.get(
            "scoring_result_seal_manifest_sha256"
        )
        == scoring_seal.get("manifest_sha256"),
        "scoring_seal_custody_bound": scoring_seal.get(
            "custody_manifest_sha256"
        )
        == _sha256_file(custody_manifest_path),
        **custody_schema_checks,
        "custody_manifest_integrity": custody.get("manifest_sha256")
        == _manifest_sha(custody),
        "custody_schema_v2": custody.get("schema_version")
        == CUSTODY_SCHEMA_VERSION,
        "custody_status_sealed": custody.get("status")
        == "execution_released_labels_sealed",
        "custody_payload_digest_matches": custody.get(
            "custodian_signature_payload_sha256"
        )
        == custody_payload_sha,
        "custody_signature_scheme_ed25519": custody.get(
            "custodian_signature_scheme"
        )
        == ED25519_SIGNATURE_SCHEME,
        "custody_key_matches_registered_public_key": custody.get(
            "custodian_signature_key_id"
        )
        == registration.get("signature_key_id")
        == f"ed25519-spki-sha256:{fingerprint}",
        "custody_signature_math_verified": custody_signature_valid,
        "custody_candidate_binding_well_formed": custody.get(
            "candidate_row_count"
        )
        == 600
        and _is_opaque_id(custody.get("candidate_filename"))
        and Path(str(custody.get("candidate_filename"))).name
        == custody.get("candidate_filename")
        and _is_sha256(custody.get("candidate_sha256")),
        "custody_label_binding_well_formed": custody.get("label_file_row_count")
        == 600
        and _is_opaque_id(custody.get("label_file_filename"))
        and Path(str(custody.get("label_file_filename"))).name
        == custody.get("label_file_filename")
        and custody.get("label_file_filename") != custody.get("candidate_filename")
        and _is_sha256(custody.get("label_file_sha256"))
        and custody.get("label_file_sha256") != custody.get("candidate_sha256"),
        "custody_independence_values_locked": custody.get(
            "custodian_independence_attested"
        )
        is True
        and custody.get("custodian_participated_in_implementation") is False
        and custody.get("developer_access_before_seal") is False
        and custody.get("developer_label_access_before_execution") is False
        and custody.get("execution_and_label_files_distinct") is True
        and custody.get("release_phase") == "execution_only_pre_scoring",
        "custody_pre_release_digest_well_formed": _is_sha256(
            custody.get("pre_release_manifest_sha256")
        ),
        "custody_registration_manifest_bound": custody.get(
            "registration_manifest_sha256"
        )
        == registration.get("manifest_sha256"),
        "custody_registration_receipt_bound": custody.get(
            "registration_verifier_receipt_sha256"
        )
        == _sha256_file(registration_verifier_receipt_path),
        "custody_slot_source_hard_locked": custody.get("slot_source_sha256")
        == EXPECTED_SLOTS_SHA256,
        "custody_release_chain_revalidated": all(custody_release_checks.values()),
        "custody_recursive_sensitive_extension_absent": not (
            custody_sensitive_extensions
        ),
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
        "signed_at_timezone_aware": signed_time is not None,
        "signature_after_scoring": signed_time is not None
        and scored_time is not None
        and signed_time >= scored_time,
        "verified_at_timezone_aware": verified_time is not None,
        "verified_at_not_materially_future_dated": verified_time is not None
        and verified_time <= datetime.now(timezone.utc) + MAX_STAGE_CLOCK_SKEW,
        "verification_after_scoring_signature": verified_time is not None
        and signed_time is not None
        and verified_time >= signed_time,
        "verifier_identity_present": _non_placeholder(verifier_id, minimum_length=3),
        "verifier_distinct_from_custodian": verifier_id
        != attestation.get("custodian_id"),
        "custodian_private_artifact_replay_recorded": isinstance(
            scoring_evidence, Mapping
        )
        and scoring_evidence.get("verification_scope")
        == "custodian_private_artifact_full_replay"
        and scoring_evidence.get("labels_opened_only_by_custodian_scoring") is True,
        "semantic_recomputation_not_overclaimed": isinstance(
            scoring_evidence, Mapping
        )
        and scoring_evidence.get("scoring_semantics_recomputed") is False
        and scoring_evidence.get(
            "scoring_semantics_attested_by_independent_custodian"
        )
        is True,
        "private_label_payload_absent_from_public_manifests": attestation.get(
            "private_label_payload_in_manifest"
        )
        is False
        and isinstance(scoring_evidence, Mapping)
        and scoring_evidence.get("private_label_payload_in_result_manifest") is False,
        "result_not_self_admitted": attestation.get(
            "result_admission_authorized"
        )
        is False
        and isinstance(scoring_evidence, Mapping)
        and scoring_evidence.get("result_admission_authorized") is False,
    }
    passed = all(checks.values())
    signature_sha = None
    if signature_valid:
        signature_sha = hashlib.sha256(
            _decode_ed25519_signature(attestation.get("custodian_signature"))
        ).hexdigest()
    core = {
        "schema_version": (
            SCORING_ATTESTATION_INTEGRITY_VERIFIER_RECEIPT_SCHEMA_VERSION
        ),
        "status": (
            "developer_safe_scoring_signature_integrity_verified"
            if passed
            else "developer_safe_scoring_signature_integrity_rejected"
        ),
        "verified": passed,
        "scoring_attestation_sha256": _sha256_file(scoring_attestation_path),
        "scoring_attestation_manifest_sha256": attestation.get("manifest_sha256"),
        "signature_payload_sha256": attestation.get("signature_payload_sha256"),
        "custodian_signature_sha256": signature_sha,
        "scoring_result_seal_sha256": _sha256_file(scoring_result_seal_path),
        "scoring_result_seal_manifest_sha256": scoring_seal.get(
            "manifest_sha256"
        ),
        "scoring_results_release_sha256": _sha256_file(
            scoring_results_release_path
        ),
        "scoring_results_release_rows": len(released_scoring_rows),
        "custody_manifest_sha256": _sha256_file(custody_manifest_path),
        "custody_manifest_digest": custody.get("manifest_sha256"),
        "registration_manifest_sha256": _sha256_file(registration_path),
        "registration_manifest_digest": registration.get("manifest_sha256"),
        "custodian_id": attestation.get("custodian_id"),
        "signature_scheme": attestation.get("signature_scheme"),
        "signature_key_id": attestation.get("signature_key_id"),
        "public_key_spki_sha256": fingerprint,
        "verifier_id": verifier_id,
        "verified_at": verified_at,
        "checks": checks,
        "evidence_boundary": {
            "signature_math_verified": signature_valid,
            "artifact_integrity_verified": passed,
            "verification_scope": "developer_safe_signature_integrity_only",
            "private_label_payload_opened": False,
            "private_path_arguments_accepted": False,
            "private_paths_enumerated": False,
            "scientific_outcomes_read": len(released_scoring_rows),
            "scoring_semantics_recomputed": False,
            "scoring_semantics_custodian_attested": signature_valid,
            "public_key_real_person_identity_is_offline_attestation": True,
            "offline_identity_not_cryptographically_proven": True,
            "result_admission_authorized": False,
            "network_calls_made": 0,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Run from the repository root or the standalone custodian toolkit root. "
            "All paths are explicit; the module never reads a private key and never "
            "contacts a network service."
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
    output_parser.add_argument("--pre-release-receipt", type=Path, required=True)
    output_parser.add_argument(
        "--signature-verifier-receipt", type=Path, required=True
    )
    output_parser.add_argument("--registration", type=Path, required=True)
    output_parser.add_argument(
        "--registration-verifier-receipt", type=Path, required=True
    )
    output_parser.add_argument(
        "--custodian-public-key", type=Path, required=True
    )
    output_parser.add_argument("--execution-admission", type=Path, required=True)
    output_parser.add_argument("--output-package", type=Path, required=True)
    output_parser.add_argument("--effect-receipt-bundle", type=Path, required=True)
    output_parser.add_argument(
        "--provider-trace-receipt-bundle", type=Path, required=True
    )
    output_parser.add_argument(
        "--provider-request-chain-bundle", type=Path, required=True
    )
    output_parser.add_argument("--completed-at", required=True)
    output_parser.add_argument("--write-seal", type=Path, required=True)

    release_parser = subparsers.add_parser(
        "release-labels-for-scoring",
        help="custodian-only release of labels after execution completion",
    )
    release_parser.add_argument("--execution-set", type=Path, required=True)
    release_parser.add_argument("--custody-manifest", type=Path, required=True)
    release_parser.add_argument("--pre-release-receipt", type=Path, required=True)
    release_parser.add_argument(
        "--signature-verifier-receipt", type=Path, required=True
    )
    release_parser.add_argument("--registration", type=Path, required=True)
    release_parser.add_argument(
        "--registration-verifier-receipt", type=Path, required=True
    )
    release_parser.add_argument(
        "--custodian-public-key", type=Path, required=True
    )
    release_parser.add_argument("--execution-admission", type=Path, required=True)
    release_parser.add_argument("--output-package", type=Path, required=True)
    release_parser.add_argument("--effect-receipt-bundle", type=Path, required=True)
    release_parser.add_argument(
        "--provider-trace-receipt-bundle", type=Path, required=True
    )
    release_parser.add_argument(
        "--provider-request-chain-bundle", type=Path, required=True
    )
    release_parser.add_argument("--label-file", type=Path, required=True)
    release_parser.add_argument("--execution-output-seal", type=Path, required=True)
    release_parser.add_argument("--released-at", required=True)
    release_parser.add_argument("--custodian-id", required=True)
    release_parser.add_argument("--write-release-seal", type=Path, required=True)

    scoring_parser = subparsers.add_parser(
        "seal-scoring-results",
        help="custodian-only validation and seal of 3,600 scored results",
    )
    scoring_parser.add_argument("--execution-set", type=Path, required=True)
    scoring_parser.add_argument("--custody-manifest", type=Path, required=True)
    scoring_parser.add_argument("--pre-release-receipt", type=Path, required=True)
    scoring_parser.add_argument(
        "--signature-verifier-receipt", type=Path, required=True
    )
    scoring_parser.add_argument("--registration", type=Path, required=True)
    scoring_parser.add_argument(
        "--registration-verifier-receipt", type=Path, required=True
    )
    scoring_parser.add_argument(
        "--custodian-public-key", type=Path, required=True
    )
    scoring_parser.add_argument("--execution-admission", type=Path, required=True)
    scoring_parser.add_argument("--execution-output-seal", type=Path, required=True)
    scoring_parser.add_argument("--output-package", type=Path, required=True)
    scoring_parser.add_argument("--effect-receipt-bundle", type=Path, required=True)
    scoring_parser.add_argument(
        "--provider-trace-receipt-bundle", type=Path, required=True
    )
    scoring_parser.add_argument(
        "--provider-request-chain-bundle", type=Path, required=True
    )
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
        help="custodian-private artifact replay; opens labels",
    )
    verify_scoring_parser.add_argument(
        "--scoring-attestation", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--scoring-result-seal", type=Path, required=True
    )
    verify_scoring_parser.add_argument("--execution-set", type=Path, required=True)
    verify_scoring_parser.add_argument(
        "--custody-manifest", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--pre-release-receipt", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--signature-verifier-receipt", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--execution-admission", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--execution-output-seal", type=Path, required=True
    )
    verify_scoring_parser.add_argument("--output-package", type=Path, required=True)
    verify_scoring_parser.add_argument(
        "--effect-receipt-bundle", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--provider-trace-receipt-bundle", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--provider-request-chain-bundle", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--label-release-seal", type=Path, required=True
    )
    verify_scoring_parser.add_argument("--label-file", type=Path, required=True)
    verify_scoring_parser.add_argument(
        "--scoring-results", type=Path, required=True
    )
    verify_scoring_parser.add_argument(
        "--scoring-results-release", type=Path, required=True
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

    integrity_scoring_parser = subparsers.add_parser(
        "verify-scoring-integrity-only",
        help="developer-safe signature/artifact verification; no private paths",
    )
    integrity_scoring_parser.add_argument(
        "--scoring-attestation", type=Path, required=True
    )
    integrity_scoring_parser.add_argument(
        "--scoring-result-seal", type=Path, required=True
    )
    integrity_scoring_parser.add_argument(
        "--scoring-results-release", type=Path, required=True
    )
    integrity_scoring_parser.add_argument(
        "--custody-manifest", type=Path, required=True
    )
    integrity_scoring_parser.add_argument(
        "--registration", type=Path, required=True
    )
    integrity_scoring_parser.add_argument(
        "--registration-verifier-receipt", type=Path, required=True
    )
    integrity_scoring_parser.add_argument(
        "--custodian-public-key", type=Path, required=True
    )
    integrity_scoring_parser.add_argument("--verifier-id", required=True)
    integrity_scoring_parser.add_argument("--verified-at", required=True)
    integrity_scoring_parser.add_argument(
        "--write-receipt", type=Path, required=True
    )

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
            pre_release_receipt_path=args.pre_release_receipt,
            signature_verifier_receipt_path=args.signature_verifier_receipt,
            registration_path=args.registration,
            registration_verifier_receipt_path=(
                args.registration_verifier_receipt
            ),
            custodian_public_key_path=args.custodian_public_key,
            execution_admission_path=args.execution_admission,
            output_package_path=args.output_package,
            effect_receipt_bundle_path=args.effect_receipt_bundle,
            provider_trace_receipt_bundle_path=(
                args.provider_trace_receipt_bundle
            ),
            provider_request_chain_bundle_path=(
                args.provider_request_chain_bundle
            ),
            completed_at=args.completed_at,
        )
        _write_json(args.write_seal, result)
    elif args.command == "release-labels-for-scoring":
        result = release_labels_to_custodian_scoring(
            execution_set_path=args.execution_set,
            custody_manifest_path=args.custody_manifest,
            pre_release_receipt_path=args.pre_release_receipt,
            signature_verifier_receipt_path=args.signature_verifier_receipt,
            registration_path=args.registration,
            registration_verifier_receipt_path=(
                args.registration_verifier_receipt
            ),
            custodian_public_key_path=args.custodian_public_key,
            execution_admission_path=args.execution_admission,
            output_package_path=args.output_package,
            effect_receipt_bundle_path=args.effect_receipt_bundle,
            provider_trace_receipt_bundle_path=(
                args.provider_trace_receipt_bundle
            ),
            provider_request_chain_bundle_path=(
                args.provider_request_chain_bundle
            ),
            label_file_path=args.label_file,
            execution_output_seal_path=args.execution_output_seal,
            released_at=args.released_at,
            custodian_id=args.custodian_id,
        )
        _write_json(args.write_release_seal, result)
    elif args.command == "seal-scoring-results":
        result = seal_custodian_scoring_results(
            execution_set_path=args.execution_set,
            custody_manifest_path=args.custody_manifest,
            pre_release_receipt_path=args.pre_release_receipt,
            signature_verifier_receipt_path=args.signature_verifier_receipt,
            registration_path=args.registration,
            registration_verifier_receipt_path=(
                args.registration_verifier_receipt
            ),
            custodian_public_key_path=args.custodian_public_key,
            execution_admission_path=args.execution_admission,
            execution_output_seal_path=args.execution_output_seal,
            output_package_path=args.output_package,
            effect_receipt_bundle_path=args.effect_receipt_bundle,
            provider_trace_receipt_bundle_path=(
                args.provider_trace_receipt_bundle
            ),
            provider_request_chain_bundle_path=(
                args.provider_request_chain_bundle
            ),
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
    elif args.command == "verify-scoring-attestation":
        result = verify_scoring_attestation(
            scoring_attestation_path=args.scoring_attestation,
            scoring_result_seal_path=args.scoring_result_seal,
            execution_set_path=args.execution_set,
            custody_manifest_path=args.custody_manifest,
            pre_release_receipt_path=args.pre_release_receipt,
            signature_verifier_receipt_path=args.signature_verifier_receipt,
            execution_admission_path=args.execution_admission,
            execution_output_seal_path=args.execution_output_seal,
            output_package_path=args.output_package,
            effect_receipt_bundle_path=args.effect_receipt_bundle,
            provider_trace_receipt_bundle_path=(
                args.provider_trace_receipt_bundle
            ),
            provider_request_chain_bundle_path=(
                args.provider_request_chain_bundle
            ),
            label_release_seal_path=args.label_release_seal,
            label_file_path=args.label_file,
            scoring_results_path=args.scoring_results,
            scoring_results_release_path=args.scoring_results_release,
            registration_path=args.registration,
            registration_verifier_receipt_path=(
                args.registration_verifier_receipt
            ),
            public_key_path=args.custodian_public_key,
            verifier_id=args.verifier_id,
            verified_at=args.verified_at,
        )
        _write_json(args.write_receipt, result)
    else:
        result = verify_scoring_attestation_integrity_only(
            scoring_attestation_path=args.scoring_attestation,
            scoring_result_seal_path=args.scoring_result_seal,
            scoring_results_release_path=args.scoring_results_release,
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
