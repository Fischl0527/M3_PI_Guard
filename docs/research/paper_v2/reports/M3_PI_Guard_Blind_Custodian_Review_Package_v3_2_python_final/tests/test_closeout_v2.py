from __future__ import annotations

import base64
import hashlib
import inspect
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import experiments.paper_v2.independent_blind_closeout_v2 as blind
from experiments.paper_v2.contracts import canonical_json_bytes


TEST_NOW = datetime.now(timezone.utc)
TEST_TRACE_EPOCH = TEST_NOW - timedelta(minutes=1)
TEST_COMPLETED_AT = (TEST_NOW - timedelta(seconds=50)).isoformat()
TEST_BEFORE_COMPLETION = (TEST_NOW - timedelta(seconds=51)).isoformat()
TEST_RELEASED_AT = (TEST_NOW - timedelta(seconds=40)).isoformat()
TEST_SCORED_AT = (TEST_NOW - timedelta(seconds=30)).isoformat()
TEST_SIGNED_AT = (TEST_NOW - timedelta(seconds=20)).isoformat()
TEST_VERIFIED_AT = (TEST_NOW - timedelta(seconds=10)).isoformat()
TEST_REVERIFIED_AT = (TEST_NOW - timedelta(seconds=5)).isoformat()


def _execution(slot: dict[str, object], index: int) -> dict[str, object]:
    return {
        **slot,
        "schema_version": blind.EXECUTION_SCHEMA_VERSION,
        "dataset_version": "m3-paper-v2-independent-blind-2.0",
        "case_id": f"synthetic-fixture-{index:04d}",
        "split": "independent_blind",
        "trusted_app_context": {"request_id": f"fixture-request-{index:04d}"},
        "trusted_user_request": f"Synthetic fixture task {index}",
        "untrusted_content": f"Synthetic fixture untrusted content {index}",
        "untrusted_memory": [],
        "authoring_provenance": {
            "independent_source_id": (
                f"synthetic-author-group-{slot['independent_author_group']}"
            )
        },
    }


def _label(slot: dict[str, object], index: int) -> dict[str, object]:
    return {
        "schema_version": blind.LABEL_SCHEMA_VERSION,
        "slot_id": slot["slot_id"],
        "case_id": f"synthetic-fixture-{index:04d}",
        "offline_evaluation": {
            "expected_allowed_effects": [],
            "expected_unsafe_effects": ["synthetic-fixture-effect"],
            "unsafe_effect_rule": "synthetic fixture unsafe-effect rule",
            "task_completion_rule": "synthetic fixture completion rule",
        },
    }


def _pairs() -> list[dict[str, object]]:
    slots = blind._read_jsonl(blind.DEFAULT_SLOTS)
    return [
        {
            "schema_version": blind.PAIR_SCHEMA_VERSION,
            "execution": _execution(slot, index),
            "label": _label(slot, index),
        }
        for index, slot in enumerate(slots, start=1)
    ]


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_json_bytes(row) + b"\n" for row in rows))


def _sign(private_key: Ed25519PrivateKey, payload_sha256: str) -> str:
    signature = private_key.sign(bytes.fromhex(payload_sha256))
    return base64.b64encode(signature).decode("ascii")


@dataclass(frozen=True)
class Chain:
    private_key: Ed25519PrivateKey
    public_key: Path
    execution: Path
    labels: Path
    pre_release: Path
    registration: Path
    registration_receipt: Path
    custody: Path
    signature_receipt: Path
    admission: Path


def _chain(tmp_path: Path) -> Chain:
    custodian = tmp_path / "custodian-private"
    developer = tmp_path / "developer-visible"
    authored = custodian / "authored-pairs.jsonl"
    execution_private = custodian / "blind-execution.jsonl"
    labels = custodian / "blind-labels.jsonl"
    pre_release_path = custodian / "pre-release-review.json"
    registration_path = custodian / "custodian-registration.json"
    registration_receipt_path = developer / "registration-verifier-receipt.json"
    custody_path = developer / "custody.json"
    signature_receipt_path = developer / "custody-signature-verifier-receipt.json"
    execution = developer / execution_private.name
    admission_path = developer / "execution-admission.json"

    private_key = Ed25519PrivateKey.generate()
    public_key_path = developer / "custodian-public-key.pem"
    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    registration_unsigned = blind.build_unsigned_custodian_registration(
        custodian_id="synthetic-independent-custodian",
        project_relationship="synthetic external reviewer",
        public_key_path=public_key_path,
        confirmed_at="2026-08-02T00:30:00+08:00",
        offline_identity_evidence_sha256=hashlib.sha256(
            b"synthetic offline identity evidence"
        ).hexdigest(),
    )
    registration = blind.finalize_custodian_registration(
        registration_unsigned,
        custodian_signature=_sign(
            private_key,
            registration_unsigned["registration_signature_payload_sha256"],
        ),
    )
    _write_json(registration_path, registration)
    registration_receipt = blind.verify_custodian_registration(
        registration_path=registration_path,
        public_key_path=public_key_path,
        verifier_id="synthetic-local-verifier",
        verified_at="2026-08-02T00:45:00+08:00",
    )
    _write_json(registration_receipt_path, registration_receipt)

    _write_jsonl(authored, _pairs())
    blind.split_authored_bundle(
        authored_pairs_path=authored,
        execution_output_path=execution_private,
        label_output_path=labels,
    )
    pre_release = blind.validate_custodian_pre_release(
        execution_set_path=execution_private,
        label_file_path=labels,
    )
    _write_json(pre_release_path, pre_release)
    key_id = registration["signature_key_id"]
    custody_unsigned = blind.build_unsigned_custody_seal(
        execution_set_path=execution_private,
        label_file_path=labels,
        pre_release_receipt_path=pre_release_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_receipt_path,
        custodian_public_key_path=public_key_path,
        custodian_id="synthetic-independent-custodian",
        custodian_signature_scheme=blind.ED25519_SIGNATURE_SCHEME,
        custodian_signature_key_id=str(key_id),
        authoring_completed_at="2026-08-02T01:00:00+08:00",
        split_completed_at="2026-08-02T02:00:00+08:00",
        sealed_at="2026-08-02T03:00:00+08:00",
        execution_set_released_at="2026-08-02T04:00:00+08:00",
        developer_received_execution_set_at="2026-08-02T05:00:00+08:00",
    )
    custody = blind.finalize_custody_seal(
        custody_unsigned,
        custodian_signature=_sign(
            private_key,
            custody_unsigned["custodian_signature_payload_sha256"],
        ),
    )
    _write_json(custody_path, custody)
    signature_receipt = blind.verify_custody_signature(
        custody_manifest_path=custody_path,
        registration_path=registration_path,
        registration_verifier_receipt_path=registration_receipt_path,
        public_key_path=public_key_path,
        verifier_id="synthetic-local-verifier",
        verified_at="2026-08-02T05:15:00+08:00",
    )
    _write_json(signature_receipt_path, signature_receipt)
    execution.write_bytes(execution_private.read_bytes())

    chain = Chain(
        private_key=private_key,
        public_key=public_key_path,
        execution=execution,
        labels=labels,
        pre_release=pre_release_path,
        registration=registration_path,
        registration_receipt=registration_receipt_path,
        custody=custody_path,
        signature_receipt=signature_receipt_path,
        admission=admission_path,
    )
    _write_json(admission_path, _audit(chain))
    return chain


def _audit(chain: Chain) -> dict[str, object]:
    return blind.audit_developer_execution_import(
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        custodian_public_key_path=chain.public_key,
    )


def _output_rows(
    executions: list[dict[str, object]],
    *,
    mode_by_sequence: dict[int, str] | None = None,
) -> list[dict[str, object]]:
    mode_by_sequence = mode_by_sequence or {}
    rows: list[dict[str, object]] = []
    sequence = 0
    global_sequence = 0
    previous_chain_sha256 = "0" * 64
    for execution in executions:
        for condition in blind.CONDITIONS:
            sequence += 1
            mode = mode_by_sequence.get(sequence, "success")
            operational_status = {
                "success": "completed",
                "zero_runner_failure": "diagnostic",
                "zero_provider_failure": "provider_failure",
                "zero_timeout": "timeout",
                "timeout": "timeout",
                "provider_failure": "provider_failure",
            }[mode]
            output = {
                "schema_version": blind.OUTPUT_ENTRY_SCHEMA_VERSION,
                "sequence": sequence,
                "work_key": hashlib.sha256(f"work-{sequence}".encode()).hexdigest(),
                "slot_id": execution["slot_id"],
                "case_id": execution["case_id"],
                "condition_id": condition,
                "output_id": f"content-free-output-{sequence:04d}",
                "effect_receipt_sha256": "0" * 64,
                "provider_trace_bundle_sha256": "0" * 64,
                "operational_status": operational_status,
            }
            effect = _effect_receipt(output)
            chain_entries = _provider_request_chain_events(
                output,
                previous_chain_sha256=previous_chain_sha256,
                first_global_sequence=global_sequence + 1,
                mode=mode,
            )
            provider = _provider_receipt(output, chain_entries)
            output["effect_receipt_sha256"] = hashlib.sha256(
                canonical_json_bytes(effect)
            ).hexdigest()
            output["provider_trace_bundle_sha256"] = hashlib.sha256(
                canonical_json_bytes(provider)
            ).hexdigest()
            rows.append(output)
            global_sequence += len(chain_entries)
            if chain_entries:
                previous_chain_sha256 = str(
                    chain_entries[-1]["entry_chain_sha256"]
                )
    return rows


def _effect_receipt(output: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": blind.EFFECT_RECEIPT_SCHEMA_VERSION,
        **{
            field: output[field]
            for field in (
                "sequence",
                "work_key",
                "output_id",
                "slot_id",
                "case_id",
                "condition_id",
                "operational_status",
            )
        },
        "isolated_effect_backend": True,
        "provider_managed_tools_enabled": False,
        "external_effects_enabled": False,
        "real_external_effect_count": 0,
        "receipt_id": f"synthetic-effect-receipt-{output['sequence']}",
    }


def _provider_request_chain_events(
    output: dict[str, object],
    *,
    previous_chain_sha256: str,
    first_global_sequence: int,
    mode: str,
) -> list[dict[str, object]]:
    if mode in {"zero_runner_failure", "zero_provider_failure", "zero_timeout"}:
        return []
    sequence = int(output["sequence"])
    event_epoch = TEST_TRACE_EPOCH
    request_id = f"local-request-{sequence:04d}"
    payload_sha256 = hashlib.sha256(
        f"canonical-payload-{sequence:04d}".encode()
    ).hexdigest()
    start_core: dict[str, object] = {
        "schema_version": blind.PROVIDER_REQUEST_CHAIN_ENTRY_SCHEMA_VERSION,
        "global_sequence": first_global_sequence,
        "work_key": output["work_key"],
        "output_id": output["output_id"],
        "call_sequence": 1,
        "event_type": "started",
        "event_at": (
            event_epoch + timedelta(microseconds=first_global_sequence)
        ).isoformat(),
        "local_request_id": request_id,
        "canonical_payload_sha256": payload_sha256,
        "started_event_sha256": None,
        "pretransport_commitment_fsynced": True,
        "transport_started_after_precommit": False,
        "official_response_id": None,
        "returned_model": None,
        "usage": None,
        "cost_cny": None,
        "failure_class": None,
        "previous_chain_sha256": previous_chain_sha256,
    }
    started = {
        **start_core,
        "entry_chain_sha256": hashlib.sha256(
            canonical_json_bytes(start_core)
        ).hexdigest(),
    }
    failed = mode in {"timeout", "provider_failure"}
    terminal_core: dict[str, object] = {
        "schema_version": blind.PROVIDER_REQUEST_CHAIN_ENTRY_SCHEMA_VERSION,
        "global_sequence": first_global_sequence + 1,
        "work_key": output["work_key"],
        "output_id": output["output_id"],
        "call_sequence": 1,
        "event_type": "failed" if failed else "completed",
        "event_at": (
            event_epoch + timedelta(microseconds=first_global_sequence + 1)
        ).isoformat(),
        "local_request_id": request_id,
        "canonical_payload_sha256": payload_sha256,
        "started_event_sha256": started["entry_chain_sha256"],
        "pretransport_commitment_fsynced": True,
        "transport_started_after_precommit": True,
        "official_response_id": None if failed else f"response-{sequence:04d}",
        "returned_model": None if failed else "deepseek-v4-pro",
        "usage": None
        if failed
        else {
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        },
        "cost_cny": None if failed else 0.000001,
        "failure_class": mode if failed else None,
        "previous_chain_sha256": started["entry_chain_sha256"],
    }
    terminal = {
        **terminal_core,
        "entry_chain_sha256": hashlib.sha256(
            canonical_json_bytes(terminal_core)
        ).hexdigest(),
    }
    return [started, terminal]


def _provider_receipt(
    output: dict[str, object], chain_entries: list[dict[str, object]]
) -> dict[str, object]:
    started = [row for row in chain_entries if row["event_type"] == "started"]
    terminals = [row for row in chain_entries if row["event_type"] != "started"]
    completed = [row for row in terminals if row["event_type"] == "completed"]
    failed = [row for row in terminals if row["event_type"] == "failed"]
    if not chain_entries:
        zero_call_failure_class = {
            "provider_failure": "provider_failure",
            "timeout": "timeout",
            "diagnostic": "runner_failure",
        }[str(output["operational_status"])]
        zero_call_reason = blind.ZERO_CALL_REASON_BY_CLASS[zero_call_failure_class]
    else:
        zero_call_failure_class = None
        zero_call_reason = None
    usage_rows = [
        row["usage"] for row in terminals if isinstance(row.get("usage"), dict)
    ]
    return {
        "schema_version": blind.PROVIDER_TRACE_RECEIPT_SCHEMA_VERSION,
        **{
            field: output[field]
            for field in (
                "sequence",
                "work_key",
                "output_id",
                "slot_id",
                "case_id",
                "condition_id",
                "operational_status",
            )
        },
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-pro",
        "endpoint_type": "official_api",
        "endpoint_host": "api.deepseek.com",
        "local_request_ids_sha256": hashlib.sha256(
            canonical_json_bytes([row["local_request_id"] for row in started])
        ).hexdigest(),
        "canonical_payload_hashes_sha256": hashlib.sha256(
            canonical_json_bytes(
                [row["canonical_payload_sha256"] for row in started]
            )
        ).hexdigest(),
        "official_response_ids_sha256": hashlib.sha256(
            canonical_json_bytes(
                [
                    row["official_response_id"]
                    for row in terminals
                    if row["official_response_id"] is not None
                ]
            )
        ).hexdigest(),
        "returned_model_ids_sha256": hashlib.sha256(
            canonical_json_bytes(
                [
                    row["returned_model"]
                    for row in terminals
                    if row["returned_model"] is not None
                ]
            )
        ).hexdigest(),
        "provider_call_count": len(started),
        "completed_call_count": len(completed),
        "failed_call_count": len(failed),
        "zero_call_reason": zero_call_reason,
        "zero_call_failure_class": zero_call_failure_class,
        "prompt_cache_hit_tokens": sum(
            int(row["prompt_cache_hit_tokens"]) for row in usage_rows
        ),
        "prompt_cache_miss_tokens": sum(
            int(row["prompt_cache_miss_tokens"]) for row in usage_rows
        ),
        "completion_tokens": sum(int(row["completion_tokens"]) for row in usage_rows),
        "total_tokens": sum(int(row["total_tokens"]) for row in usage_rows),
        "cost_cny": round(
            sum(float(row["cost_cny"]) for row in terminals if row["cost_cny"] is not None),
            12,
        ),
        "budget_ceiling_cny": blind.DEEPSEEK_BLIND_BUDGET_CEILING_CNY,
        "within_budget": True,
        "trace_start_global_sequence": (
            chain_entries[0]["global_sequence"] if chain_entries else None
        ),
        "trace_end_global_sequence": (
            chain_entries[-1]["global_sequence"] if chain_entries else None
        ),
        "trace_genesis_previous_sha256": (
            chain_entries[0]["previous_chain_sha256"] if chain_entries else None
        ),
        "trace_tail_entry_sha256": (
            chain_entries[-1]["entry_chain_sha256"] if chain_entries else None
        ),
        "all_attempts_terminal": True,
        "open_attempt_count": 0,
        "automatic_retry_count": 0,
        "provider_managed_tools_enabled": False,
        "external_connectors_enabled": False,
        "trace_receipt_id": f"synthetic-provider-receipt-{output['sequence']}",
    }


def _write_runtime_receipts(
    root: Path,
    outputs: list[dict[str, object]],
    *,
    mode_by_sequence: dict[int, str] | None = None,
) -> tuple[Path, Path, Path]:
    mode_by_sequence = mode_by_sequence or {}
    effect_path = root / "effect-receipts.jsonl"
    provider_path = root / "provider-receipts.jsonl"
    request_chain_path = root / "provider-request-chain.jsonl"
    request_chain: list[dict[str, object]] = []
    provider_receipts: list[dict[str, object]] = []
    previous_chain_sha256 = "0" * 64
    global_sequence = 0
    for output in outputs:
        mode = mode_by_sequence.get(int(output["sequence"]), "success")
        entries = _provider_request_chain_events(
            output,
            previous_chain_sha256=previous_chain_sha256,
            first_global_sequence=global_sequence + 1,
            mode=mode,
        )
        request_chain.extend(entries)
        provider_receipts.append(_provider_receipt(output, entries))
        global_sequence += len(entries)
        if entries:
            previous_chain_sha256 = str(entries[-1]["entry_chain_sha256"])
    _write_jsonl(effect_path, [_effect_receipt(output) for output in outputs])
    _write_jsonl(provider_path, provider_receipts)
    _write_jsonl(request_chain_path, request_chain)
    return effect_path, provider_path, request_chain_path


def _score_rows(
    outputs: list[dict[str, object]], labels: list[dict[str, object]]
) -> list[dict[str, object]]:
    labels_by_case = {
        (row["slot_id"], row["case_id"]): row for row in labels
    }
    rows: list[dict[str, object]] = []
    for output in outputs:
        if (output["slot_id"], output["case_id"]) not in labels_by_case:
            raise AssertionError("synthetic score fixture lacks its private label case")
        rows.append(
            {
                "schema_version": blind.SCORING_ENTRY_SCHEMA_VERSION,
                **{
                    field: output[field]
                    for field in (
                        "sequence",
                        "work_key",
                        "slot_id",
                        "case_id",
                        "condition_id",
                        "output_id",
                        "operational_status",
                    )
                },
                "output_row_sha256": hashlib.sha256(
                    canonical_json_bytes(output)
                ).hexdigest(),
                "unsafe_effect": False,
                "task_completion": True,
            }
        )
    return rows


def test_v2_templates_are_zero_content_and_v1_is_hash_locked() -> None:
    case = json.loads((blind.KIT_ROOT / "case_template.json").read_text(encoding="utf-8"))
    status = json.loads((blind.KIT_ROOT / "status.json").read_text(encoding="utf-8"))
    assert set(case) == blind.EXECUTION_REQUIRED_FIELDS
    assert blind._forbidden_execution_paths(case) == []
    assert status["real_authoring_pairs_present"] is False
    expected_v1_slots = (
        "4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8"
    )
    assert hashlib.sha256(blind.DEFAULT_SLOTS.read_bytes()).hexdigest() == expected_v1_slots
    assert expected_v1_slots == blind.EXPECTED_SLOTS_SHA256


def test_all_historical_v1_blind_files_remain_hash_locked() -> None:
    expected = {
        "experiments/paper_v2/independent_blind_closeout_v1.py": (
            "a47562ee065f3ec95633b22c4856f13244cfc44bfa1d3047b80427956ce8452a"
        ),
        "tests/unit/test_paper_v2_independent_blind_closeout_v1.py": (
            "f25902ffe268b2337703d0ea3d0f955cf1b771561e2ca484c13d41df929e329f"
        ),
        "protocols/paper_upgrade_v2/independent_blind_closeout_interface_v1.json": (
            "7e387c5e22161d3db760e4cfae15103c6e67dd1ffadf2e82719845710c6ccca5"
        ),
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/case_template.json": (
            "56134c42d51c8232b5a98a3ca092893878f77c715651d0567d00814c96ff16c5"
        ),
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/custody_manifest_template.json": (
            "a13715abd917e2076e79dcbffb116735392b216af45b7faa18f0f5517e103e25"
        ),
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/README.md": (
            "3d2440507cf944d1d95202e580e5106b45b8a992fcfa3550982aee97f8d49ecb"
        ),
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl": (
            "4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8"
        ),
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/status.json": (
            "e9eca7bd4150f4fd20065a01f43ccf6f2660d9f47b8192a109fa0e2bb1a1ccfa"
        ),
    }
    observed = {
        relative: hashlib.sha256((blind.PROJECT_ROOT / relative).read_bytes()).hexdigest()
        for relative in expected
    }
    assert observed == expected


def test_day1_registration_starts_clock_but_never_authorizes_execution(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    receipt = blind._read_json(chain.registration_receipt)
    assert receipt["status"] == "custodian_registration_verified_clock_may_start"
    assert receipt["verified"] is True
    assert receipt["evidence_boundary"]["signature_math_verified"] is True
    assert receipt["evidence_boundary"]["clock_start_authorized"] is True
    assert receipt["evidence_boundary"]["execution_authorized"] is False
    assert receipt["evidence_boundary"][
        "public_key_real_person_identity_is_offline_attestation"
    ] is True


def test_registration_signature_math_failure_is_rejected(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    registration = blind._read_json(chain.registration)
    registration["custodian_signature"] = base64.b64encode(b"x" * 64).decode()
    registration["manifest_sha256"] = blind._manifest_sha(registration)
    _write_json(chain.registration, registration)
    receipt = blind.verify_custodian_registration(
        registration_path=chain.registration,
        public_key_path=chain.public_key,
        verifier_id="synthetic-local-verifier",
        verified_at="2026-08-02T06:00:00+08:00",
    )
    assert receipt["status"] == "custodian_registration_rejected"
    assert receipt["checks"]["signature_math_verified"] is False


def test_registration_verifier_must_be_distinct_from_custodian(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    receipt = blind.verify_custodian_registration(
        registration_path=chain.registration,
        public_key_path=chain.public_key,
        verifier_id="synthetic-independent-custodian",
        verified_at=datetime.now(timezone.utc).isoformat(),
    )
    assert receipt["status"] == "custodian_registration_rejected"
    assert receipt["checks"]["verifier_distinct_from_custodian"] is False
    assert receipt["evidence_boundary"]["clock_start_authorized"] is False
    assert receipt["evidence_boundary"][
        "offline_identity_not_cryptographically_proven"
    ] is True


def test_valid_signature_cannot_authorize_registration_with_nested_labels(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    registration = blind._read_json(chain.registration)
    registration.pop("custodian_signature")
    registration.pop("manifest_sha256")
    registration.pop("registration_signature_payload_sha256")
    registration["labels"] = {"gold": "synthetic forbidden label"}
    payload_sha = blind.registration_signature_payload_sha256(registration)
    registration["registration_signature_payload_sha256"] = payload_sha
    registration["custodian_signature"] = _sign(chain.private_key, payload_sha)
    registration["manifest_sha256"] = blind._manifest_sha(registration)
    _write_json(chain.registration, registration)
    receipt = blind.verify_custodian_registration(
        registration_path=chain.registration,
        public_key_path=chain.public_key,
        verifier_id="synthetic-local-verifier",
        verified_at="2026-08-02T05:30:00+08:00",
    )
    assert receipt["checks"]["signature_math_verified"] is True
    assert receipt["checks"]["registration_top_level_schema_exact"] is False
    assert receipt["checks"][
        "registration_nested_sensitive_payload_absent"
    ] is False
    assert receipt["status"] == "custodian_registration_rejected"
    assert receipt["evidence_boundary"]["clock_start_authorized"] is False


def test_registration_verification_time_is_monotonic_and_not_future(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    with pytest.raises(
        blind.IndependentBlindCloseoutV2Error,
        match="confirmed_at must include a timezone",
    ):
        blind.build_unsigned_custodian_registration(
            custodian_id="synthetic-independent-custodian",
            project_relationship="synthetic external reviewer",
            public_key_path=chain.public_key,
            confirmed_at="2026-08-02T00:30:00",
            offline_identity_evidence_sha256=hashlib.sha256(
                b"synthetic offline identity evidence"
            ).hexdigest(),
        )
    reversed_time = blind.verify_custodian_registration(
        registration_path=chain.registration,
        public_key_path=chain.public_key,
        verifier_id="synthetic-local-verifier",
        verified_at="2026-08-02T00:00:00+08:00",
    )
    assert reversed_time["checks"]["verification_not_before_confirmation"] is False
    assert reversed_time["status"] == "custodian_registration_rejected"

    future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    future = blind.verify_custodian_registration(
        registration_path=chain.registration,
        public_key_path=chain.public_key,
        verifier_id="synthetic-local-verifier",
        verified_at=future_time,
    )
    assert future["checks"]["verification_not_materially_future_dated"] is False
    assert future["status"] == "custodian_registration_rejected"


def test_clean_import_requires_and_reverifies_every_receipt(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    admission = _audit(chain)
    assert admission["status"].endswith("labels_unopened")
    assert admission["execution_set"]["rows"] == 600
    assert admission["execution_set"]["observed_slot_source_sha256"] == (
        blind.EXPECTED_SLOTS_SHA256
    )
    assert all(admission["execution_checks"].values())
    assert all(admission["pre_release_checks"].values())
    assert all(admission["registration_checks"].values())
    assert all(admission["signature_verifier_checks"].values())
    assert admission["evidence_boundary"]["execution_authorized"] is True
    assert admission["evidence_boundary"]["label_file_opened"] is False
    assert admission["evidence_boundary"]["scientific_label_rows_read"] == 0


def test_registration_receipt_nested_label_extension_is_rejected(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    receipt = blind._read_json(chain.registration_receipt)
    receipt["checks"]["labels"] = {"gold": "synthetic forbidden receipt data"}
    receipt["manifest_sha256"] = blind._manifest_sha(receipt)
    _write_json(chain.registration_receipt, receipt)
    admission = _audit(chain)
    assert admission["status"] == "sealed_execution_set_v2_rejected"
    assert admission["registration_checks"][
        "registration_receipt_checks_schema_exact"
    ] is False
    assert admission["evidence_boundary"]["execution_authorized"] is False


def test_missing_external_verifier_receipt_cannot_authorize(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    missing = chain.signature_receipt.with_name("missing.json")
    with pytest.raises(blind.IndependentBlindCloseoutV2Error):
        blind.audit_developer_execution_import(
            execution_set_path=chain.execution,
            custody_manifest_path=chain.custody,
            pre_release_receipt_path=chain.pre_release,
            signature_verifier_receipt_path=missing,
            registration_path=chain.registration,
            registration_verifier_receipt_path=chain.registration_receipt,
            custodian_public_key_path=chain.public_key,
        )


def test_forged_verified_true_receipt_cannot_replace_signature_math(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    custody = blind._read_json(chain.custody)
    custody["custodian_signature"] = base64.b64encode(b"z" * 64).decode()
    custody["manifest_sha256"] = blind._manifest_sha(custody)
    _write_json(chain.custody, custody)
    forged = blind._read_json(chain.signature_receipt)
    forged["verified"] = True
    forged["manifest_sha256"] = blind._manifest_sha(forged)
    _write_json(chain.signature_receipt, forged)
    admission = _audit(chain)
    assert admission["status"] == "sealed_execution_set_v2_rejected"
    assert admission["signature_verifier_checks"][
        "signature_receipt_math_reverified"
    ] is False
    assert admission["evidence_boundary"]["execution_authorized"] is False


def test_valid_signature_cannot_authorize_custody_with_nested_gold_label(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    custody = blind._read_json(chain.custody)
    custody.pop("custodian_signature")
    custody.pop("manifest_sha256")
    custody.pop("custodian_signature_payload_sha256")
    custody["review_notes"] = {"gold_label": "LEAKED_SECRET_LABEL"}
    payload_sha = blind.custody_signature_payload_sha256(custody)
    custody["custodian_signature_payload_sha256"] = payload_sha
    custody["custodian_signature"] = _sign(chain.private_key, payload_sha)
    custody["manifest_sha256"] = blind._manifest_sha(custody)
    _write_json(chain.custody, custody)
    receipt = blind.verify_custody_signature(
        custody_manifest_path=chain.custody,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        public_key_path=chain.public_key,
        verifier_id="synthetic-local-verifier",
        verified_at="2026-08-02T05:30:00+08:00",
    )
    assert receipt["checks"]["custodian_signature_math_verified"] is True
    assert receipt["checks"]["custody_top_level_schema_exact"] is False
    assert receipt["checks"]["custody_has_no_other_nested_payload"] is False
    assert receipt["status"] == "custody_signature_rejected"


@pytest.mark.parametrize(
    "semantic_key",
    [
        "results",
        "offlineData",
        "evaluationOutcome",
        "scoredOutcome",
        "ground_truth_annotation",
        "score_card",
        "goldAnswer",
    ],
)
def test_recursive_semantic_key_bypasses_are_rejected(
    tmp_path: Path, semantic_key: str
) -> None:
    chain = _chain(tmp_path)
    rows = blind._read_jsonl(chain.execution)
    rows[0]["trusted_app_context"] = {
        "request_id": "fixture-request-0001",
        "nested": [{semantic_key: "synthetic forbidden value"}],
    }
    _write_jsonl(chain.execution, rows)
    admission = _audit(chain)
    assert admission["status"] == "sealed_execution_set_v2_rejected"
    assert admission["execution_checks"][
        "developer_visible_label_fields_absent"
    ] is False


def test_unexpected_top_level_execution_field_is_rejected(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    rows = blind._read_jsonl(chain.execution)
    rows[0]["harmless_extension"] = "not allowed in strict schema"
    _write_jsonl(chain.execution, rows)
    admission = _audit(chain)
    assert admission["execution_checks"]["top_level_schema_exact"] is False
    assert admission["evidence_boundary"]["execution_authorized"] is False


def test_pre_release_receipt_must_bind_both_hashes_and_manifest(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    receipt = blind._read_json(chain.pre_release)
    receipt["label_file"]["sha256"] = "a" * 64
    receipt["manifest_sha256"] = blind._manifest_sha(receipt)
    _write_json(chain.pre_release, receipt)
    admission = _audit(chain)
    assert admission["status"] == "sealed_execution_set_v2_rejected"
    assert admission["pre_release_checks"]["pre_release_label_hash_bound"] is False
    assert admission["pre_release_checks"][
        "pre_release_manifest_bound_by_custody"
    ] is False


def test_runtime_rejects_any_slot_source_hash_drift(tmp_path: Path) -> None:
    drift = tmp_path / "slots.jsonl"
    drift.write_bytes(blind.DEFAULT_SLOTS.read_bytes() + b"\n")
    with pytest.raises(blind.IndependentBlindCloseoutV2Error, match="hard lock"):
        blind._slots(drift)


def test_forged_self_hashed_admission_cannot_become_a_trust_root(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    forged = {
        "schema_version": blind.EXECUTION_ADMISSION_SCHEMA_VERSION,
        "status": "sealed_execution_set_v2_technically_admitted_labels_unopened",
        "execution_set": {
            "sha256": hashlib.sha256(chain.execution.read_bytes()).hexdigest()
        },
        "evidence_boundary": {
            "execution_authorized": True,
            "scientific_label_rows_read": 0,
        },
    }
    forged["manifest_sha256"] = blind._manifest_sha(forged)
    _write_json(chain.admission, forged)
    missing = tmp_path / "must-not-be-read.jsonl"
    with pytest.raises(
        blind.IndependentBlindCloseoutV2Error,
        match="does not exactly match full primary-evidence replay",
    ):
        blind.seal_execution_complete_output_package(
            execution_set_path=chain.execution,
            custody_manifest_path=chain.custody,
            pre_release_receipt_path=chain.pre_release,
            signature_verifier_receipt_path=chain.signature_receipt,
            registration_path=chain.registration,
            registration_verifier_receipt_path=chain.registration_receipt,
            custodian_public_key_path=chain.public_key,
            execution_admission_path=chain.admission,
            output_package_path=missing,
            effect_receipt_bundle_path=missing,
            provider_trace_receipt_bundle_path=missing,
            provider_request_chain_bundle_path=missing,
            completed_at=TEST_COMPLETED_AT,
        )


def test_request_chain_preserves_success_timeout_failure_and_zero_call_itt(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    modes = {
        1: "zero_runner_failure",
        2: "timeout",
        3: "zero_provider_failure",
        4: "provider_failure",
        5: "zero_timeout",
    }
    outputs = _output_rows(
        blind._read_jsonl(chain.execution), mode_by_sequence=modes
    )
    output_path = tmp_path / "developer-visible" / "mixed-itt-outputs.jsonl"
    _write_jsonl(output_path, outputs)
    effect_path, provider_path, request_chain_path = _write_runtime_receipts(
        output_path.parent,
        outputs,
        mode_by_sequence=modes,
    )
    seal = blind.seal_execution_complete_output_package(
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        custodian_public_key_path=chain.public_key,
        execution_admission_path=chain.admission,
        output_package_path=output_path,
        effect_receipt_bundle_path=effect_path,
        provider_trace_receipt_bundle_path=provider_path,
        provider_request_chain_bundle_path=request_chain_path,
        completed_at=TEST_COMPLETED_AT,
    )
    assert seal["status"] == (
        "execution_complete_content_free_output_package_sealed"
    )
    assert [row["operational_status"] for row in outputs[:4]] == [
        "diagnostic",
        "timeout",
        "provider_failure",
        "provider_failure",
    ]
    provider_rows = blind._read_jsonl(provider_path)
    assert provider_rows[0]["provider_call_count"] == 0
    assert provider_rows[0]["zero_call_failure_class"] == "runner_failure"
    assert provider_rows[1]["failed_call_count"] == 1
    assert provider_rows[1]["official_response_ids_sha256"] == hashlib.sha256(
        canonical_json_bytes([])
    ).hexdigest()
    assert provider_rows[4]["provider_call_count"] == 0
    assert provider_rows[4]["zero_call_failure_class"] == "timeout"
    assert provider_rows[4]["zero_call_reason"] == (
        blind.ZERO_CALL_REASON_BY_CLASS["timeout"]
    )
    assert all(seal["runtime_receipt_checks"].values())


def test_request_chain_tamper_and_free_text_id_channel_are_rejected(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    outputs = _output_rows(blind._read_jsonl(chain.execution))
    effect_path, provider_path, request_chain_path = _write_runtime_receipts(
        tmp_path / "developer-visible", outputs
    )
    effects = blind._read_jsonl(effect_path)
    providers = blind._read_jsonl(provider_path)
    request_chain = blind._read_jsonl(request_chain_path)
    request_chain[0]["local_request_id"] = "label\nforbidden-free-text"
    checks = blind._runtime_receipt_bundle_validation(
        outputs=outputs,
        effect_receipts=effects,
        provider_receipts=providers,
        provider_request_chain=request_chain,
    )
    assert checks["provider_request_chain_event_semantics_valid"] is False
    assert checks["provider_request_chain_hash_continuous"] is False
    providers[0]["trace_receipt_id"] = "result payload with spaces"
    outputs[0]["provider_trace_bundle_sha256"] = hashlib.sha256(
        canonical_json_bytes(providers[0])
    ).hexdigest()
    checks = blind._runtime_receipt_bundle_validation(
        outputs=outputs,
        effect_receipts=effects,
        provider_receipts=providers,
        provider_request_chain=blind._read_jsonl(request_chain_path),
    )
    assert checks["provider_receipts_bound_to_outputs"] is True
    assert checks["provider_trace_receipt_ids_unique_opaque"] is False
    assert not {
        "prompt",
        "prompt_body",
        "response_body",
        "label",
        "gold",
    }.intersection(blind.PROVIDER_REQUEST_CHAIN_ENTRY_FIELDS)


def test_completed_provider_call_cannot_be_rehashed_as_provider_failure(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)
    outputs = _output_rows(blind._read_jsonl(chain.execution))
    effect_path, provider_path, request_chain_path = _write_runtime_receipts(
        tmp_path / "developer-visible", outputs
    )
    effects = blind._read_jsonl(effect_path)
    providers = blind._read_jsonl(provider_path)
    request_chain = blind._read_jsonl(request_chain_path)

    # Simulate an evidence forger that changes every public outer status and
    # recomputes both content hashes, but leaves the signed started->completed
    # provider terminal history intact.
    outputs[0]["operational_status"] = "provider_failure"
    effects[0]["operational_status"] = "provider_failure"
    providers[0]["operational_status"] = "provider_failure"
    outputs[0]["effect_receipt_sha256"] = hashlib.sha256(
        canonical_json_bytes(effects[0])
    ).hexdigest()
    outputs[0]["provider_trace_bundle_sha256"] = hashlib.sha256(
        canonical_json_bytes(providers[0])
    ).hexdigest()

    checks = blind._runtime_receipt_bundle_validation(
        outputs=outputs,
        effect_receipts=effects,
        provider_receipts=providers,
        provider_request_chain=request_chain,
    )
    assert checks["effect_receipts_bound_to_outputs"] is True
    assert checks["provider_receipts_bound_to_outputs"] is True
    assert checks["provider_request_chain_event_semantics_valid"] is True
    assert checks["provider_receipts_match_request_chain"] is False

    # This protocol treats timeout as a failed provider terminal (or the exact
    # zero-call timeout mapping), never as a completed-only outer status.
    outputs[0]["operational_status"] = "timeout"
    effects[0]["operational_status"] = "timeout"
    providers[0]["operational_status"] = "timeout"
    outputs[0]["effect_receipt_sha256"] = hashlib.sha256(
        canonical_json_bytes(effects[0])
    ).hexdigest()
    outputs[0]["provider_trace_bundle_sha256"] = hashlib.sha256(
        canonical_json_bytes(providers[0])
    ).hexdigest()
    timeout_checks = blind._runtime_receipt_bundle_validation(
        outputs=outputs,
        effect_receipts=effects,
        provider_receipts=providers,
        provider_request_chain=request_chain,
    )
    assert timeout_checks["effect_receipts_bound_to_outputs"] is True
    assert timeout_checks["provider_receipts_bound_to_outputs"] is True
    assert timeout_checks["provider_receipts_match_request_chain"] is False


def test_complete_post_execution_label_release_and_scoring_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chain = _chain(tmp_path)
    outputs = _output_rows(blind._read_jsonl(chain.execution))
    output_path = tmp_path / "developer-visible" / "content-free-outputs.jsonl"
    _write_jsonl(output_path, outputs)
    effect_path, provider_path, request_chain_path = _write_runtime_receipts(
        output_path.parent, outputs
    )
    output_seal = blind.seal_execution_complete_output_package(
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        custodian_public_key_path=chain.public_key,
        execution_admission_path=chain.admission,
        output_package_path=output_path,
        effect_receipt_bundle_path=effect_path,
        provider_trace_receipt_bundle_path=provider_path,
        provider_request_chain_bundle_path=request_chain_path,
        completed_at=TEST_COMPLETED_AT,
    )
    output_seal_path = tmp_path / "developer-visible" / "output-seal.json"
    _write_json(output_seal_path, output_seal)
    assert output_seal["status"] == (
        "execution_complete_content_free_output_package_sealed"
    )
    assert output_seal["evidence_boundary"]["label_rows_read"] == 0

    release = blind.release_labels_to_custodian_scoring(
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        custodian_public_key_path=chain.public_key,
        execution_admission_path=chain.admission,
        output_package_path=output_path,
        effect_receipt_bundle_path=effect_path,
        provider_trace_receipt_bundle_path=provider_path,
        provider_request_chain_bundle_path=request_chain_path,
        label_file_path=chain.labels,
        execution_output_seal_path=output_seal_path,
        released_at=TEST_RELEASED_AT,
        custodian_id="synthetic-independent-custodian",
    )
    release_path = tmp_path / "custodian-private" / "label-release-seal.json"
    _write_json(release_path, release)
    assert release["status"] == "labels_released_to_custodian_scoring_only"
    assert release["evidence_boundary"]["developer_received_label_file"] is False

    labels = blind._read_jsonl(chain.labels)
    scores = _score_rows(outputs, labels)
    scoring_path = tmp_path / "custodian-private" / "scoring-results.jsonl"
    _write_jsonl(scoring_path, scores)
    scoring_release_path = (
        tmp_path / "developer-visible" / "scoring-results-release.jsonl"
    )
    _write_jsonl(scoring_release_path, scores)
    scoring_seal = blind.seal_custodian_scoring_results(
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        custodian_public_key_path=chain.public_key,
        execution_admission_path=chain.admission,
        execution_output_seal_path=output_seal_path,
        output_package_path=output_path,
        effect_receipt_bundle_path=effect_path,
        provider_trace_receipt_bundle_path=provider_path,
        provider_request_chain_bundle_path=request_chain_path,
        label_release_seal_path=release_path,
        label_file_path=chain.labels,
        scoring_results_path=scoring_path,
        scored_at=TEST_SCORED_AT,
        custodian_id="synthetic-independent-custodian",
    )
    assert scoring_seal["status"] == "custodian_scoring_completed_results_sealed"
    assert scoring_seal["scoring_results"]["rows"] == 3600
    assert scoring_seal["evidence_boundary"][
        "developer_received_label_file_before_scoring"
    ] is False
    assert scoring_seal["evidence_boundary"][
        "private_label_payload_in_result_manifest"
    ] is False
    scoring_seal_path = tmp_path / "custodian-private" / "scoring-seal.json"
    _write_json(scoring_seal_path, scoring_seal)
    unsigned_attestation = blind.build_unsigned_scoring_attestation(
        scoring_result_seal_path=scoring_seal_path,
        custody_manifest_path=chain.custody,
        registration_path=chain.registration,
        custodian_id="synthetic-independent-custodian",
        signed_at=TEST_SIGNED_AT,
    )
    attestation = blind.finalize_scoring_attestation(
        unsigned_attestation,
        custodian_signature=_sign(
            chain.private_key,
            unsigned_attestation["signature_payload_sha256"],
        ),
    )
    attestation_path = tmp_path / "custodian-private" / "scoring-attestation.json"
    _write_json(attestation_path, attestation)
    verification = blind.verify_scoring_attestation(
        scoring_attestation_path=attestation_path,
        scoring_result_seal_path=scoring_seal_path,
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        execution_admission_path=chain.admission,
        execution_output_seal_path=output_seal_path,
        output_package_path=output_path,
        effect_receipt_bundle_path=effect_path,
        provider_trace_receipt_bundle_path=provider_path,
        provider_request_chain_bundle_path=request_chain_path,
        label_release_seal_path=release_path,
        label_file_path=chain.labels,
        scoring_results_path=scoring_path,
        scoring_results_release_path=scoring_release_path,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        public_key_path=chain.public_key,
        verifier_id="synthetic-local-verifier",
        verified_at=TEST_VERIFIED_AT,
    )
    assert verification["status"] == (
        "custodian_scoring_result_artifact_full_replay_verified"
    )
    assert verification["verified"] is True
    assert verification["checks"]["signature_math_verified"] is True
    assert verification["evidence_boundary"]["private_label_payload_opened"] is True
    assert verification["evidence_boundary"]["verification_scope"] == (
        "custodian_private_artifact_full_replay"
    )
    assert verification["evidence_boundary"][
        "custodian_private_scoring_semantics_recomputed"
    ] is False
    assert verification["evidence_boundary"]["result_admission_authorized"] is False

    integrity_parameters = set(
        inspect.signature(
            blind.verify_scoring_attestation_integrity_only
        ).parameters
    )
    assert not {
        "label_file_path",
        "scoring_results_path",
        "output_package_path",
        "execution_set_path",
    }.intersection(integrity_parameters)

    original_read_jsonl = blind._read_jsonl

    def allow_release_jsonl_only(path: Path) -> list[dict[str, object]]:
        if path.resolve() != scoring_release_path.resolve():
            raise AssertionError(
                "developer-safe verifier attempted private JSONL access"
            )
        return original_read_jsonl(path)

    def reject_directory_enumeration(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "developer-safe verifier attempted directory enumeration"
        )

    monkeypatch.setattr(blind, "_read_jsonl", allow_release_jsonl_only)
    monkeypatch.setattr(Path, "iterdir", reject_directory_enumeration)
    monkeypatch.setattr(Path, "glob", reject_directory_enumeration)
    monkeypatch.setattr(Path, "rglob", reject_directory_enumeration)
    integrity = blind.verify_scoring_attestation_integrity_only(
        scoring_attestation_path=attestation_path,
        scoring_result_seal_path=scoring_seal_path,
        scoring_results_release_path=scoring_release_path,
        custody_manifest_path=chain.custody,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        public_key_path=chain.public_key,
        verifier_id="synthetic-developer-safe-verifier",
        verified_at=TEST_VERIFIED_AT,
    )
    assert integrity["status"] == (
        "developer_safe_scoring_signature_integrity_verified"
    )
    assert integrity["verified"] is True
    assert integrity["evidence_boundary"]["private_label_payload_opened"] is False
    assert integrity["evidence_boundary"]["private_path_arguments_accepted"] is False
    assert integrity["evidence_boundary"]["private_paths_enumerated"] is False
    assert integrity["evidence_boundary"]["scientific_outcomes_read"] == 3600
    assert integrity["evidence_boundary"]["scoring_semantics_recomputed"] is False
    monkeypatch.undo()

    leaky_scoring_seal = json.loads(json.dumps(scoring_seal))
    leaky_scoring_seal["chain_checks"]["gold_label"] = {
        "secret": "LEAK"
    }
    leaky_scoring_seal["manifest_sha256"] = blind._manifest_sha(
        leaky_scoring_seal
    )
    leaky_scoring_seal_path = (
        tmp_path / "developer-visible" / "leaky-scoring-seal.json"
    )
    _write_json(leaky_scoring_seal_path, leaky_scoring_seal)
    leaky_unsigned_attestation = blind.build_unsigned_scoring_attestation(
        scoring_result_seal_path=leaky_scoring_seal_path,
        custody_manifest_path=chain.custody,
        registration_path=chain.registration,
        custodian_id="synthetic-independent-custodian",
        signed_at=TEST_SIGNED_AT,
    )
    leaky_attestation = blind.finalize_scoring_attestation(
        leaky_unsigned_attestation,
        custodian_signature=_sign(
            chain.private_key,
            leaky_unsigned_attestation["signature_payload_sha256"],
        ),
    )
    leaky_attestation_path = (
        tmp_path / "developer-visible" / "leaky-scoring-attestation.json"
    )
    _write_json(leaky_attestation_path, leaky_attestation)
    leaky_integrity = blind.verify_scoring_attestation_integrity_only(
        scoring_attestation_path=leaky_attestation_path,
        scoring_result_seal_path=leaky_scoring_seal_path,
        scoring_results_release_path=scoring_release_path,
        custody_manifest_path=chain.custody,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        public_key_path=chain.public_key,
        verifier_id="synthetic-developer-safe-verifier",
        verified_at=TEST_VERIFIED_AT,
    )
    assert leaky_integrity["status"] == (
        "developer_safe_scoring_signature_integrity_rejected"
    )
    assert leaky_integrity["checks"]["signature_math_verified"] is True
    assert leaky_integrity["checks"][
        "scoring_chain_checks_schema_exact_all_true"
    ] is False
    assert leaky_integrity["checks"][
        "scoring_seal_recursive_sensitive_extension_absent"
    ] is False

    leaky_custody = json.loads(
        chain.custody.read_text(encoding="utf-8")
    )
    leaky_custody["release_chain"]["gold_label"] = {"secret": "LEAK"}
    leaky_custody["custodian_signature_payload_sha256"] = (
        blind.custody_signature_payload_sha256(leaky_custody)
    )
    leaky_custody["custodian_signature"] = _sign(
        chain.private_key,
        leaky_custody["custodian_signature_payload_sha256"],
    )
    leaky_custody["manifest_sha256"] = blind._manifest_sha(leaky_custody)
    leaky_custody_path = (
        tmp_path / "developer-visible" / "leaky-custody.json"
    )
    _write_json(leaky_custody_path, leaky_custody)
    custody_bound_scoring_seal = json.loads(json.dumps(scoring_seal))
    custody_bound_scoring_seal["custody_manifest_sha256"] = (
        blind._sha256_file(leaky_custody_path)
    )
    custody_bound_scoring_seal["manifest_sha256"] = blind._manifest_sha(
        custody_bound_scoring_seal
    )
    custody_bound_scoring_seal_path = (
        tmp_path / "developer-visible" / "custody-bound-scoring-seal.json"
    )
    _write_json(custody_bound_scoring_seal_path, custody_bound_scoring_seal)
    custody_bound_unsigned_attestation = (
        blind.build_unsigned_scoring_attestation(
            scoring_result_seal_path=custody_bound_scoring_seal_path,
            custody_manifest_path=leaky_custody_path,
            registration_path=chain.registration,
            custodian_id="synthetic-independent-custodian",
            signed_at=TEST_SIGNED_AT,
        )
    )
    custody_bound_attestation = blind.finalize_scoring_attestation(
        custody_bound_unsigned_attestation,
        custodian_signature=_sign(
            chain.private_key,
            custody_bound_unsigned_attestation["signature_payload_sha256"],
        ),
    )
    custody_bound_attestation_path = (
        tmp_path / "developer-visible" / "custody-bound-attestation.json"
    )
    _write_json(custody_bound_attestation_path, custody_bound_attestation)
    leaky_custody_integrity = blind.verify_scoring_attestation_integrity_only(
        scoring_attestation_path=custody_bound_attestation_path,
        scoring_result_seal_path=custody_bound_scoring_seal_path,
        scoring_results_release_path=scoring_release_path,
        custody_manifest_path=leaky_custody_path,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        public_key_path=chain.public_key,
        verifier_id="synthetic-developer-safe-verifier",
        verified_at=TEST_VERIFIED_AT,
    )
    assert leaky_custody_integrity["status"] == (
        "developer_safe_scoring_signature_integrity_rejected"
    )
    assert leaky_custody_integrity["checks"][
        "custody_signature_math_verified"
    ] is True
    assert leaky_custody_integrity["checks"][
        "custody_release_chain_schema_exact"
    ] is False
    assert leaky_custody_integrity["checks"][
        "custody_recursive_sensitive_extension_absent"
    ] is False

    tampered_release = tmp_path / "developer-visible" / "tampered-release.jsonl"
    tampered_rows = blind._read_jsonl(scoring_release_path)
    tampered_rows[0]["unexpected_private_field"] = "must be rejected"
    _write_jsonl(tampered_release, tampered_rows)
    tampered_integrity = blind.verify_scoring_attestation_integrity_only(
        scoring_attestation_path=attestation_path,
        scoring_result_seal_path=scoring_seal_path,
        scoring_results_release_path=tampered_release,
        custody_manifest_path=chain.custody,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        public_key_path=chain.public_key,
        verifier_id="synthetic-developer-safe-verifier",
        verified_at=TEST_VERIFIED_AT,
    )
    assert tampered_integrity["status"] == (
        "developer_safe_scoring_signature_integrity_rejected"
    )
    assert tampered_integrity["checks"][
        "released_scoring_results_schema_valid"
    ] is False

    attestation["custodian_signature"] = base64.b64encode(b"q" * 64).decode()
    attestation["manifest_sha256"] = blind._manifest_sha(attestation)
    _write_json(attestation_path, attestation)
    rejected = blind.verify_scoring_attestation(
        scoring_attestation_path=attestation_path,
        scoring_result_seal_path=scoring_seal_path,
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        execution_admission_path=chain.admission,
        execution_output_seal_path=output_seal_path,
        output_package_path=output_path,
        effect_receipt_bundle_path=effect_path,
        provider_trace_receipt_bundle_path=provider_path,
        provider_request_chain_bundle_path=request_chain_path,
        label_release_seal_path=release_path,
        label_file_path=chain.labels,
        scoring_results_path=scoring_path,
        scoring_results_release_path=scoring_release_path,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        public_key_path=chain.public_key,
        verifier_id="synthetic-local-verifier",
        verified_at=TEST_REVERIFIED_AT,
    )
    assert rejected["status"] == (
        "custodian_scoring_result_artifact_full_replay_rejected"
    )
    assert rejected["checks"]["signature_math_verified"] is False
    integrity_rejected = blind.verify_scoring_attestation_integrity_only(
        scoring_attestation_path=attestation_path,
        scoring_result_seal_path=scoring_seal_path,
        scoring_results_release_path=scoring_release_path,
        custody_manifest_path=chain.custody,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        public_key_path=chain.public_key,
        verifier_id="synthetic-developer-safe-verifier",
        verified_at=TEST_REVERIFIED_AT,
    )
    assert integrity_rejected["status"] == (
        "developer_safe_scoring_signature_integrity_rejected"
    )
    assert integrity_rejected["checks"]["signature_math_verified"] is False


def test_label_release_before_execution_completion_is_rejected(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    outputs = _output_rows(blind._read_jsonl(chain.execution))
    output_path = tmp_path / "developer-visible" / "outputs.jsonl"
    _write_jsonl(output_path, outputs)
    effect_path, provider_path, request_chain_path = _write_runtime_receipts(
        output_path.parent, outputs
    )
    seal = blind.seal_execution_complete_output_package(
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        custodian_public_key_path=chain.public_key,
        execution_admission_path=chain.admission,
        output_package_path=output_path,
        effect_receipt_bundle_path=effect_path,
        provider_trace_receipt_bundle_path=provider_path,
        provider_request_chain_bundle_path=request_chain_path,
        completed_at=TEST_COMPLETED_AT,
    )
    seal_path = tmp_path / "developer-visible" / "seal.json"
    _write_json(seal_path, seal)
    with pytest.raises(
        blind.IndependentBlindCloseoutV2Error,
        match="pre-label release checks failed: release_after_execution_complete",
    ):
        blind.release_labels_to_custodian_scoring(
            execution_set_path=chain.execution,
            custody_manifest_path=chain.custody,
            pre_release_receipt_path=chain.pre_release,
            signature_verifier_receipt_path=chain.signature_receipt,
            registration_path=chain.registration,
            registration_verifier_receipt_path=chain.registration_receipt,
            custodian_public_key_path=chain.public_key,
            execution_admission_path=chain.admission,
            output_package_path=output_path,
            effect_receipt_bundle_path=effect_path,
            provider_trace_receipt_bundle_path=provider_path,
            provider_request_chain_bundle_path=request_chain_path,
            label_file_path=chain.labels,
            execution_output_seal_path=seal_path,
            released_at=TEST_BEFORE_COMPLETION,
            custodian_id="synthetic-independent-custodian",
        )


def test_minimal_self_hashed_output_seal_cannot_open_labels(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    output_path = tmp_path / "developer-visible" / "outputs.jsonl"
    outputs = _output_rows(blind._read_jsonl(chain.execution))
    _write_jsonl(output_path, outputs)
    effect_path, provider_path, request_chain_path = _write_runtime_receipts(
        output_path.parent, outputs
    )
    minimal = {
        "schema_version": blind.OUTPUT_SEAL_SCHEMA_VERSION,
        "status": "execution_complete_content_free_output_package_sealed",
        "completed_at": TEST_COMPLETED_AT,
        "custody_manifest_sha256": hashlib.sha256(
            chain.custody.read_bytes()
        ).hexdigest(),
    }
    minimal["manifest_sha256"] = blind._manifest_sha(minimal)
    seal_path = tmp_path / "developer-visible" / "forged-minimal-seal.json"
    _write_json(seal_path, minimal)
    nonexistent_labels = tmp_path / "must-not-be-opened" / "labels.jsonl"
    with pytest.raises(
        blind.IndependentBlindCloseoutV2Error,
        match="execution output chain revalidation failed",
    ):
        blind.release_labels_to_custodian_scoring(
            execution_set_path=chain.execution,
            custody_manifest_path=chain.custody,
            pre_release_receipt_path=chain.pre_release,
            signature_verifier_receipt_path=chain.signature_receipt,
            registration_path=chain.registration,
            registration_verifier_receipt_path=chain.registration_receipt,
            custodian_public_key_path=chain.public_key,
            execution_admission_path=chain.admission,
            output_package_path=output_path,
            effect_receipt_bundle_path=effect_path,
            provider_trace_receipt_bundle_path=provider_path,
            provider_request_chain_bundle_path=request_chain_path,
            label_file_path=nonexistent_labels,
            execution_output_seal_path=seal_path,
            released_at=TEST_RELEASED_AT,
            custodian_id="synthetic-independent-custodian",
        )


def test_content_free_output_package_rejects_embedded_result(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    outputs = _output_rows(blind._read_jsonl(chain.execution))
    outputs[0]["nestedResults"] = {"unsafe_effect": False}
    output_path = tmp_path / "developer-visible" / "outputs.jsonl"
    _write_jsonl(output_path, outputs)
    effect_path, provider_path, request_chain_path = _write_runtime_receipts(
        output_path.parent, outputs
    )
    seal = blind.seal_execution_complete_output_package(
        execution_set_path=chain.execution,
        custody_manifest_path=chain.custody,
        pre_release_receipt_path=chain.pre_release,
        signature_verifier_receipt_path=chain.signature_receipt,
        registration_path=chain.registration,
        registration_verifier_receipt_path=chain.registration_receipt,
        custodian_public_key_path=chain.public_key,
        execution_admission_path=chain.admission,
        output_package_path=output_path,
        effect_receipt_bundle_path=effect_path,
        provider_trace_receipt_bundle_path=provider_path,
        provider_request_chain_bundle_path=request_chain_path,
        completed_at=TEST_COMPLETED_AT,
    )
    assert seal["status"] == "execution_output_package_rejected"
    assert seal["output_checks"]["top_level_schema_exact"] is False
    assert seal["output_checks"][
        "content_and_result_semantic_keys_absent"
    ] is False
