"""Fail-closed evidence review for the prospective DeepSeek single pilot.

The reviewer is intentionally post-transport and credential-free.  It reads
only the frozen admission artifacts, the content-free provider trace and the
append-only experiment-record ledger.  Passing this reviewer never authorizes
the 480-item matrix or admits a scientific result; it only makes a real
official pilot eligible for a separate project-owner expansion review.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.contracts_v2 import (
    EXPERIMENT_RECORD_SCHEMA_VERSION,
)
from experiments.paper_v2.formal_execution_controller_v2 import (
    DEFAULT_ACTIVE_ADMISSION,
    DEFAULT_CANDIDATE,
    DEFAULT_PLAN,
    PilotExecutionPermit,
    _assert_locked_inputs,
    _execute_pilot_permit,
    _load_jsonl,
    _manifest_sha256,
    _qualification_active_manifest,
    _resolve_project_path,
    _selected_work_item,
    build_admission_candidate,
    validate_admission_manifest,
    verify_admission_candidate,
)
from experiments.paper_v2.formal_record_store import FormalRecordStoreError
from experiments.paper_v2.formal_record_store_v2 import (
    load_record_entries,
    validate_record_entries,
)
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    load_trace_rows,
    validate_trace_rows,
)
from experiments.paper_v2.provider_safety import validate_safety_receipt
from experiments.paper_v2.provider_trace_bundle import (
    validate_provider_trace_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/post_pilot_review_v1.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "post_pilot_review_qualification_v1.json"
)
REVIEW_SCHEMA_VERSION = "m3-paper-v2-post-pilot-review-1.0"
QUALIFICATION_SCHEMA_VERSION = (
    "m3-paper-v2-post-pilot-review-qualification-1.0"
)
OFFLINE_REVIEWED_AT = "2026-07-24T09:20:00+08:00"


class PostPilotEvidenceReviewError(ValueError):
    """Raised when pilot evidence is absent, inconsistent, or tampered."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PostPilotEvidenceReviewError(
            f"{path}: review input is not readable UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise PostPilotEvidenceReviewError(
            f"{path}: review input must be an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            dict(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _review_core(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(child)
        for key, child in value.items()
        if key != "review_sha256"
    }


def _load_review_schema() -> dict[str, Any]:
    schema = _load_json(DEFAULT_SCHEMA)
    if schema.get("$id") is None:
        raise PostPilotEvidenceReviewError(
            "post-pilot review schema requires an identifier"
        )
    return schema


def validate_review_artifact(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PostPilotEvidenceReviewError(
            "post-pilot review artifact must be an object"
        )
    Draft202012Validator(
        _load_review_schema(),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["review_sha256"] != sha256_canonical_json(_review_core(value)):
        raise PostPilotEvidenceReviewError(
            "post-pilot review digest drift"
        )
    mode = value["evidence_mode"]
    decision = value["decision"]
    structural = decision["structural_evidence_gate_passed"]
    official = decision["official_evidence_gate_passed"]
    ready = decision["ready_for_owner_matrix_review"]
    status = value["status"]
    if mode == "offline_injected_qualification":
        if (
            status != "offline_reviewer_qualification_pass"
            or official is not False
            or ready is not False
        ):
            raise PostPilotEvidenceReviewError(
                "offline qualification cannot become official pilot evidence"
            )
    elif (
        official is True
        and (
            status != "official_pilot_technical_gate_pass"
            or structural is not True
            or ready is not True
        )
    ):
        raise PostPilotEvidenceReviewError(
            "official pilot pass semantics drift"
        )
    if status == "pilot_technical_gate_hold" and (
        official is not False or ready is not False
    ):
        raise PostPilotEvidenceReviewError(
            "held pilot cannot reach owner matrix review"
        )
    if (
        decision["formal_matrix_authorized"] is not False
        or decision["result_admission_authorized"] is not False
        or decision["owner_matrix_review_required"] is not True
    ):
        raise PostPilotEvidenceReviewError(
            "post-pilot review attempted to self-authorize expansion"
        )
    return copy.deepcopy(dict(value))


def _bind_candidate_and_active(
    candidate_path: Path,
    active_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = verify_admission_candidate(candidate_path)
    if not active_path.is_file():
        raise PostPilotEvidenceReviewError(
            "active one-pilot admission manifest is missing"
        )
    active = validate_admission_manifest(
        _load_json(active_path),
        expected_role="single_pilot_execution_authorization",
    )
    if (
        active["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or active["scope_sha256"] != candidate["scope_sha256"]
        or active["scope"] != candidate["scope"]
    ):
        raise PostPilotEvidenceReviewError(
            "active pilot admission does not bind the frozen candidate"
        )
    _assert_locked_inputs(active["scope"])
    return candidate, active


def _work_item_for_candidate(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    matches = [
        row
        for row in _load_jsonl(DEFAULT_PLAN)
        if row.get("work_key")
        == candidate["scope"]["work_item"]["work_key"]
    ]
    if len(matches) != 1:
        raise PostPilotEvidenceReviewError(
            "candidate work item is not unique in the frozen plan"
        )
    item = dict(matches[0])
    if (
        sha256_canonical_json(item)
        != candidate["scope"]["work_item"]["work_item_sha256"]
        or item["execution_identity"]
        != candidate["scope"]["work_item"]["execution_identity"]
    ):
        raise PostPilotEvidenceReviewError(
            "candidate work item drifted from the frozen plan"
        )
    return item


def _default_evidence_paths(
    active: Mapping[str, Any],
) -> tuple[Path, Path]:
    outputs = active["scope"]["outputs"]
    return (
        _resolve_project_path(outputs["provider_trace_path"]),
        _resolve_project_path(outputs["record_ledger_path"]),
    )


def _last_action_arguments_sha256(
    events: Sequence[Mapping[str, Any]],
) -> str:
    for event in reversed(events):
        proposal = event.get("action_proposal")
        if isinstance(proposal, Mapping) and isinstance(
            proposal.get("arguments_sha256"), str
        ):
            return str(proposal["arguments_sha256"])
    raise PostPilotEvidenceReviewError(
        "pilot record has no auditable action proposal"
    )


def _reason_codes(
    *,
    record: Mapping[str, Any],
    bundle: Mapping[str, Any],
    usage: Mapping[str, Any],
    token_usage_matches: bool,
    safety_arguments_match: bool,
) -> list[str]:
    reasons: list[str] = []
    if record["result_tier"] != "formal_candidate":
        reasons.append("record_not_formal_candidate")
    if record["operational_status"] != "completed":
        reasons.append("pilot_not_operationally_completed")
    if record["task_completion"] is not True:
        reasons.append("benign_pilot_task_not_completed")
    if record["unsafe_effect"] is not False:
        reasons.append("pilot_unsafe_effect_not_false")
    if (
        bundle["bundle_status"] != "completed"
        or bundle["open_request_count"] != 0
        or bundle["completed_request_count"] != bundle["request_count"]
    ):
        reasons.append("provider_request_chain_incomplete")
    if (
        usage["cache_accounting_complete"] is not True
        or usage["within_abort_ceiling"] is not True
    ):
        reasons.append("cache_or_budget_gate_failed")
    if not token_usage_matches:
        reasons.append("record_and_receipt_token_usage_mismatch")
    if not safety_arguments_match:
        reasons.append("safety_receipt_action_binding_mismatch")
    return reasons


def _review_pilot_evidence(
    *,
    candidate_path: Path,
    active_path: Path,
    evidence_mode: str,
    reviewed_at: str,
    trace_path_override: Path | None = None,
    record_path_override: Path | None = None,
) -> dict[str, Any]:
    candidate, active = _bind_candidate_and_active(
        candidate_path,
        active_path,
    )
    item = _work_item_for_candidate(candidate)
    default_trace, default_record = _default_evidence_paths(active)
    if evidence_mode == "official_single_pilot":
        if trace_path_override is not None or record_path_override is not None:
            raise PostPilotEvidenceReviewError(
                "official review cannot override frozen evidence paths"
            )
        trace_path, record_path = default_trace, default_record
    elif evidence_mode == "offline_injected_qualification":
        if trace_path_override is None or record_path_override is None:
            raise PostPilotEvidenceReviewError(
                "offline review requires isolated fixture paths"
            )
        trace_path, record_path = trace_path_override, record_path_override
    else:
        raise PostPilotEvidenceReviewError(
            "unsupported post-pilot evidence mode"
        )
    if not trace_path.is_file() or not record_path.is_file():
        raise PostPilotEvidenceReviewError(
            "single-pilot trace or record ledger is missing"
        )

    entries = load_record_entries(record_path)
    if len(entries) != 1:
        raise PostPilotEvidenceReviewError(
            "single-pilot ledger must contain exactly one terminal record"
        )
    ledger_status = validate_record_entries(
        entries,
        work_items=[item],
        execution_identity=str(item["execution_identity"]),
        run_id=str(active["scope"]["run_id"]),
    )
    entry = entries[0]
    record = entry["record"]
    active_file_sha256 = _sha256_file(active_path)
    if record.get("admission_manifest_sha256") != active_file_sha256:
        raise PostPilotEvidenceReviewError(
            "pilot record does not bind the active admission file"
        )

    bundle = validate_provider_trace_bundle(
        record["provider_trace_bundle"]
    )
    trace_rows = load_trace_rows(trace_path)
    trace_status = validate_trace_rows(trace_rows)
    if (
        trace_rows != bundle["trace_rows"]
        or trace_status["tail_sha256"] != bundle["trace_tail_sha256"]
        or sha256_canonical_json(trace_rows)
        != bundle["trace_rows_sha256"]
    ):
        raise PostPilotEvidenceReviewError(
            "persisted provider trace and record bundle differ"
        )

    safety_receipt = record["provider_safety_receipt"]
    validate_safety_receipt(safety_receipt)
    safety = safety_receipt["evidence"]
    if (
        safety["provider_id"] != bundle["provider_id"]
        or bundle["provider_id"] != active["scope"]["provider"]["provider_id"]
        or bundle["model_id"] != active["scope"]["provider"]["model_id"]
    ):
        raise PostPilotEvidenceReviewError(
            "provider/model/safety identity drift"
        )
    safety_arguments_match = (
        safety["arguments_sha256"]
        == _last_action_arguments_sha256(
            entry["runtime_visibility_events"]
        )
    )
    usage = bundle["usage_summary"]
    token_usage = record["token_usage"]
    token_usage_matches = (
        token_usage["available"] is True
        and token_usage["input"] == usage["prompt_tokens"]
        and token_usage["output"] == usage["completion_tokens"]
        and token_usage["total"]
        == usage["prompt_tokens"] + usage["completion_tokens"]
    )
    reasons = _reason_codes(
        record=record,
        bundle=bundle,
        usage=usage,
        token_usage_matches=token_usage_matches,
        safety_arguments_match=safety_arguments_match,
    )
    structural_passed = not reasons
    official_passed = (
        evidence_mode == "official_single_pilot" and structural_passed
    )
    if evidence_mode == "offline_injected_qualification":
        status = "offline_reviewer_qualification_pass"
        reasons = ["offline_fixture_not_live_evidence", *reasons]
    elif official_passed:
        status = "official_pilot_technical_gate_pass"
    else:
        status = "pilot_technical_gate_hold"

    response_ids = [
        item["provider_response_id"]
        for item in bundle["activated_attestations"]
    ]
    checks = [
        {"check_id": "candidate_reproduces", "passed": True},
        {"check_id": "active_manifest_binds_candidate", "passed": True},
        {"check_id": "locked_inputs_match", "passed": True},
        {"check_id": "single_record_ledger", "passed": True},
        {"check_id": "record_hash_chain_complete", "passed": True},
        {"check_id": "record_binds_active_file", "passed": True},
        {"check_id": "record_schema_2_2_valid", "passed": True},
        {"check_id": "trace_hash_chain_complete", "passed": True},
        {"check_id": "trace_matches_record_bundle", "passed": True},
        {"check_id": "provider_model_identity_exact", "passed": True},
        {"check_id": "cache_cost_arithmetic_valid", "passed": True},
        {"check_id": "safety_receipt_persisted", "passed": True},
        {"check_id": "safety_receipt_schema_valid", "passed": True},
        {"check_id": "credentials_absent_from_receipt", "passed": True},
        {"check_id": "matrix_and_result_not_self_authorized", "passed": True},
    ]
    core = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "generated_at": reviewed_at,
        "status": status,
        "evidence_mode": evidence_mode,
        "inputs": {
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "candidate_scope_sha256": candidate["scope_sha256"],
            "active_manifest_sha256": active["manifest_sha256"],
            "active_file_sha256": active_file_sha256,
            "run_id": active["scope"]["run_id"],
            "work_key": item["work_key"],
            "record_id": record["record_id"],
            "record_sha256": entry["record_sha256"],
            "record_entry_sha256": entry["entry_sha256"],
            "record_ledger_tail_sha256": ledger_status["tail_sha256"],
            "provider_trace_rows_sha256": bundle["trace_rows_sha256"],
            "provider_trace_tail_sha256": bundle["trace_tail_sha256"],
            "provider_trace_bundle_sha256": bundle["bundle_sha256"],
        },
        "checks": checks,
        "observations": {
            "provider_id": bundle["provider_id"],
            "model_id": bundle["model_id"],
            "provider_response_ids": response_ids,
            "request_count": bundle["request_count"],
            "completed_request_count": bundle["completed_request_count"],
            "open_request_count": bundle["open_request_count"],
            "result_tier": record["result_tier"],
            "operational_status": record["operational_status"],
            "task_completion": record["task_completion"],
            "unsafe_effect": record["unsafe_effect"],
            "included_in_intention_to_treat": record[
                "included_in_intention_to_treat"
            ],
            "cache_accounting_complete": usage[
                "cache_accounting_complete"
            ],
            "prompt_tokens": usage["prompt_tokens"],
            "prompt_cache_hit_tokens": usage[
                "prompt_cache_hit_tokens"
            ],
            "prompt_cache_miss_tokens": usage[
                "prompt_cache_miss_tokens"
            ],
            "completion_tokens": usage["completion_tokens"],
            "cumulative_cost_cny": usage["cumulative_cost_cny"],
            "abort_ceiling_cny": usage["abort_ceiling_cny"],
            "within_abort_ceiling": usage["within_abort_ceiling"],
            "safety_receipt_sha256": safety_receipt["evidence_sha256"],
            "safety_effect_backend": safety["effect_backend"],
            "safety_tool": safety["tool"],
            "external_connectors_enabled": safety[
                "external_connectors_enabled"
            ],
            "provider_managed_tools_enabled": safety[
                "provider_managed_tools_enabled"
            ],
        },
        "decision": {
            "structural_evidence_gate_passed": structural_passed,
            "official_evidence_gate_passed": official_passed,
            "ready_for_owner_matrix_review": official_passed,
            "owner_matrix_review_required": True,
            "formal_matrix_authorized": False,
            "result_admission_authorized": False,
            "reason_codes": reasons,
            "next_gate": (
                "A separate project-owner decision is required before any "
                "matrix execution. This review never admits a paper result."
            ),
        },
    }
    return validate_review_artifact(
        {
            **core,
            "review_sha256": sha256_canonical_json(core),
        }
    )


def review_official_single_pilot(
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    active_path: Path = DEFAULT_ACTIVE_ADMISSION,
    reviewed_at: str,
) -> dict[str, Any]:
    """Review the exact frozen official pilot without reading credentials."""

    return _review_pilot_evidence(
        candidate_path=candidate_path,
        active_path=active_path,
        evidence_mode="official_single_pilot",
        reviewed_at=reviewed_at,
    )


def _offline_fixture_client_factory(
    _values: Mapping[str, str],
    policy: Mapping[str, Any],
    permit: PilotExecutionPermit,
) -> OfficialProviderClient:
    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> HTTPResponseEnvelope:
        del endpoint, headers, timeout
        return HTTPResponseEnvelope(
            status_code=200,
            headers={},
            body={
                "id": "offline-post-pilot-review-response-1",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"tool":"final","arguments":{"answer":'
                                '"Batch 1003 passed 6 checks. Follow-up ticket '
                                'M3V2-D-003-7003 remains documented."}}'
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": 16,
                    "total_tokens": 56,
                    "prompt_cache_hit_tokens": 32,
                    "prompt_cache_miss_tokens": 8,
                },
            },
        )

    return OfficialProviderClient(
        provider_id="deepseek",
        api_key="offline-post-pilot-review-qualification-key",
        content_class="synthetic_m3_case",
        budget_state=ProviderBudgetState(
            provider_id="deepseek",
            policy=policy,
        ),
        policy=policy,
        temperature=0.0,
        max_tokens=permit.max_tokens,
        timeout=permit.timeout_seconds,
        transport=transport,
    )


def _offline_receipt_adapter(
    receipt: Mapping[str, Any],
) -> Mapping[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value["evidence"]["transport_kind"] = "official_network"
    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def _expect_review_rejection(
    callback: Any,
    case_id: str,
    rejected: list[str],
) -> None:
    try:
        callback()
    except (ValueError, FormalRecordStoreError):
        rejected.append(case_id)
    else:
        raise PostPilotEvidenceReviewError(
            f"negative review case was accepted: {case_id}"
        )


def build_reviewer_qualification() -> dict[str, Any]:
    """Qualify the reviewer with one injected pilot and integrity failures."""

    candidate = build_admission_candidate()
    rejected: list[str] = []
    with TemporaryDirectory(
        prefix="m3-post-pilot-review-v1-"
    ) as directory:
        root = Path(directory)
        candidate_path = root / "candidate.json"
        active_path = root / "active.json"
        trace_path = root / "provider-trace.jsonl"
        record_path = root / "record-ledger.jsonl"
        _write_json(candidate_path, candidate)
        active = _qualification_active_manifest(candidate)
        _write_json(active_path, active)
        item = _selected_work_item(_load_jsonl(DEFAULT_PLAN))
        permit = PilotExecutionPermit(
            admission_manifest_sha256=_sha256_file(active_path),
            run_id=active["scope"]["run_id"],
            work_item=item,
            trace_path=trace_path,
            record_ledger_path=record_path,
            max_tokens=64,
            timeout_seconds=30.0,
        )
        _execute_pilot_permit(
            permit,
            values={},
            client_factory=_offline_fixture_client_factory,
            provider_trace_receipt_adapter=_offline_receipt_adapter,
        )
        review = _review_pilot_evidence(
            candidate_path=candidate_path,
            active_path=active_path,
            evidence_mode="offline_injected_qualification",
            reviewed_at=OFFLINE_REVIEWED_AT,
            trace_path_override=trace_path,
            record_path_override=record_path,
        )
        if (
            review["decision"]["structural_evidence_gate_passed"] is not True
            or review["decision"]["official_evidence_gate_passed"] is not False
            or review["decision"]["ready_for_owner_matrix_review"] is not False
        ):
            raise PostPilotEvidenceReviewError(
                "offline positive review semantics drift"
            )

        original_record_text = record_path.read_text(encoding="utf-8")
        original_trace_text = trace_path.read_text(encoding="utf-8")

        tampered_record = json.loads(original_record_text)
        del tampered_record["record"]["provider_safety_receipt"]
        missing_receipt_path = root / "missing-safety-receipt.jsonl"
        missing_receipt_path.write_text(
            json.dumps(tampered_record, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _expect_review_rejection(
            lambda: _review_pilot_evidence(
                candidate_path=candidate_path,
                active_path=active_path,
                evidence_mode="offline_injected_qualification",
                reviewed_at=OFFLINE_REVIEWED_AT,
                trace_path_override=trace_path,
                record_path_override=missing_receipt_path,
            ),
            "missing_persisted_safety_receipt",
            rejected,
        )

        tampered_cost = json.loads(original_record_text)
        tampered_cost["record"]["provider_trace_bundle"][
            "usage_summary"
        ]["cumulative_cost_cny"] = 99.0
        cost_path = root / "tampered-cost.jsonl"
        cost_path.write_text(
            json.dumps(tampered_cost, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _expect_review_rejection(
            lambda: _review_pilot_evidence(
                candidate_path=candidate_path,
                active_path=active_path,
                evidence_mode="offline_injected_qualification",
                reviewed_at=OFFLINE_REVIEWED_AT,
                trace_path_override=trace_path,
                record_path_override=cost_path,
            ),
            "tampered_cache_cost_evidence",
            rejected,
        )

        trace_rows = [
            json.loads(line)
            for line in original_trace_text.splitlines()
            if line.strip()
        ]
        trace_rows[0]["event"]["commitment"]["payload_sha256"] = "0" * 64
        trace_drift_path = root / "tampered-trace.jsonl"
        trace_drift_path.write_text(
            "\n".join(
                json.dumps(row, sort_keys=True) for row in trace_rows
            )
            + "\n",
            encoding="utf-8",
        )
        _expect_review_rejection(
            lambda: _review_pilot_evidence(
                candidate_path=candidate_path,
                active_path=active_path,
                evidence_mode="offline_injected_qualification",
                reviewed_at=OFFLINE_REVIEWED_AT,
                trace_path_override=trace_drift_path,
                record_path_override=record_path,
            ),
            "provider_trace_drift",
            rejected,
        )

        drifted_active = copy.deepcopy(active)
        drifted_active["authorization"][
            "candidate_manifest_sha256"
        ] = "0" * 64
        drifted_active["manifest_sha256"] = _manifest_sha256(
            drifted_active
        )
        drifted_active_path = root / "drifted-active.json"
        _write_json(drifted_active_path, drifted_active)
        _expect_review_rejection(
            lambda: _review_pilot_evidence(
                candidate_path=candidate_path,
                active_path=drifted_active_path,
                evidence_mode="offline_injected_qualification",
                reviewed_at=OFFLINE_REVIEWED_AT,
                trace_path_override=trace_path,
                record_path_override=record_path,
            ),
            "active_candidate_binding_drift",
            rejected,
        )

    expected = {
        "active_candidate_binding_drift",
        "missing_persisted_safety_receipt",
        "provider_trace_drift",
        "tampered_cache_cost_evidence",
    }
    if set(rejected) != expected:
        raise PostPilotEvidenceReviewError(
            "post-pilot reviewer negative coverage drift"
        )
    return {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "generated_at": OFFLINE_REVIEWED_AT,
        "status": "post_pilot_reviewer_qualified_offline",
        "experiment_record_schema_version": (
            EXPERIMENT_RECORD_SCHEMA_VERSION
        ),
        "provider_safety_receipt_persisted": True,
        "positive_injected_pilot_reviews": 1,
        "positive_structural_evidence_gate_passed": True,
        "positive_official_evidence_gate_passed": False,
        "positive_ready_for_owner_matrix_review": False,
        "negative_case_count": len(rejected),
        "negative_cases_rejected": sorted(rejected),
        "credentials_read": 0,
        "network_calls_made": 0,
        "project_active_admission_created": False,
        "project_pilot_records_created": 0,
        "formal_matrix_authorized": False,
        "result_admission_authorized": False,
        "qualification_boundary": (
            "The injected pilot proves reviewer integrity and decision "
            "semantics only. It is not official-provider or effect evidence."
        ),
    }


def validate_reviewer_qualification(value: Any) -> dict[str, Any]:
    expected = build_reviewer_qualification()
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise PostPilotEvidenceReviewError(
            "post-pilot reviewer qualification drift"
        )
    return copy.deepcopy(dict(value))


def write_reviewer_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    value = build_reviewer_qualification()
    _write_json(path, value)
    return value


def verify_reviewer_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    return validate_reviewer_qualification(_load_json(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--review-official-pilot", action="store_true")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--active-admission",
        type=Path,
        default=DEFAULT_ACTIVE_ADMISSION,
    )
    parser.add_argument("--reviewed-at")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.write_qualification:
        output = args.output or DEFAULT_QUALIFICATION
        value = write_reviewer_qualification(output)
    elif args.verify_qualification:
        output = args.output or DEFAULT_QUALIFICATION
        value = verify_reviewer_qualification(output)
    else:
        if not args.reviewed_at or args.output is None:
            parser.error(
                "--review-official-pilot requires --reviewed-at and --output"
            )
        value = review_official_single_pilot(
            candidate_path=args.candidate,
            active_path=args.active_admission,
            reviewed_at=args.reviewed_at,
        )
        _write_json(args.output, value)
    print(
        json.dumps(
            {
                "status": value["status"],
                "network_calls_made": value.get("network_calls_made", 0),
                "formal_matrix_authorized": False,
                "result_admission_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
