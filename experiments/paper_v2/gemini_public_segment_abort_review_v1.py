"""在响应后证据契约校验失败时封签 Gemini 公开分段 1。

严格隔离异常分段，杜绝残缺数据影响全局评测指标。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.gemini_public_controller_v1 as public_v1
import experiments.paper_v2.gemini_public_controller_v4 as public_v4
import experiments.paper_v2.provider_request_trace_candidate as trace
from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEGMENT_INDEX = 1
QUOTA_DAY = "2026-08-03"
WRAPPER_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/gemini_public_v5_s1_2026-08-03_guarded"
)
WRAPPER_RECEIPT = WRAPPER_ROOT / "receipt.json"
WRAPPER_STDERR = WRAPPER_ROOT / "03_execute.stderr.log"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/"
    "gemini_public_canary_v4_s1_abort_review_v1.json"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-public-segment-abort-review-1.0"
GENERATED_AT = "2026-08-04T00:50:00+08:00"
EXPECTED_ERROR = (
    "GeminiTraceAttachingRuntimeV1Error: incomplete Gemini trace cannot "
    "retain a response claim"
)


class GeminiPublicSegmentAbortReviewV1Error(ValueError):
    """当不可变 segment-1 论据偏离中止审查时抛出的异常。"""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicSegmentAbortReviewV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise GeminiPublicSegmentAbortReviewV1Error(
            f"{path}: expected object"
        )
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _file_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiPublicSegmentAbortReviewV1Error(
            f"required segment evidence missing: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _without_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item for key, item in value.items() if key != "manifest_sha256"
    }


def classify_request_chain(
    *,
    provider_request_id: Any,
    provider_response_id: Any,
    trace_mode: Any,
    request_trace_complete: Any,
    identity_verified: Any,
) -> str:
    """仅分类解释封存失败所需的元数据。"""

    if (
        provider_request_id is None
        and isinstance(provider_response_id, str)
        and bool(provider_response_id)
        and trace_mode == "precommitted_local_plus_provider_response"
        and request_trace_complete is False
        and identity_verified is True
    ):
        return "local_precommit_complete_provider_request_id_unavailable"
    return "unclassified_request_chain"


def _raw_sealed_state(permit: Any) -> dict[str, Any]:
    """加载失败的分段，且不调用仅成功的状态门禁。"""

    records = public_v1.load_record_entries(permit.record_ledger_path)
    record_status = public_v1.validate_record_entries(
        records,
        work_items=permit.work_items,
        execution_identity=permit.execution_identity,
        run_id=permit.run_id,
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
    attempts = public_v1.matrix_v1._load_jsonl(permit.attempt_ledger_path)
    attempt_status = public_v1.matrix_v1.validate_attempt_events(
        attempts,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
    )
    calls = public_v1.load_call_events(permit.call_ledger_path)
    call_status = public_v1.validate_call_events(
        calls,
        execution_identity=permit.execution_identity,
        provider_id="gemini",
        model_id=public_v4.MODEL_ID,
    )
    return {
        "records": records,
        "record_status": record_status,
        "attempts": attempts,
        "attempt_status": attempt_status,
        "calls": calls,
        "call_status": call_status,
    }


def build_review() -> dict[str, Any]:
    permit = public_v4._permit(
        segment_index=SEGMENT_INDEX,
        quota_day=QUOTA_DAY,
        selected_admission=public_v4.admission_path(
            SEGMENT_INDEX, QUOTA_DAY
        ),
    )
    state = _raw_sealed_state(permit)
    attempts = state["attempts"]
    calls = state["calls"]
    call_status = state["call_status"]
    trace_paths = sorted(permit.trace_root.glob("*.jsonl"))
    if len(trace_paths) != 1:
        raise GeminiPublicSegmentAbortReviewV1Error(
            "segment 1 must retain exactly one provider trace"
        )
    trace_path = trace_paths[0]
    trace_rows = trace.load_trace_rows(trace_path)
    trace_status = trace.validate_trace_rows(trace_rows)
    terminal = trace_rows[-1]["event"] if trace_rows else {}
    attestation = terminal.get("attestation", {})
    call_receipt = calls[-1].get("receipt", {}) if calls else {}
    receipt_evidence = (
        call_receipt.get("evidence", {})
        if isinstance(call_receipt, Mapping)
        else {}
    )
    wrapper = _read_object(WRAPPER_RECEIPT)
    stderr_text = WRAPPER_STDERR.read_text(encoding="utf-8")
    request_chain_class = classify_request_chain(
        provider_request_id=attestation.get("provider_request_id"),
        provider_response_id=attestation.get("provider_response_id"),
        trace_mode=attestation.get("trace_mode"),
        request_trace_complete=receipt_evidence.get(
            "request_trace_complete"
        ),
        identity_verified=receipt_evidence.get("identity_verified"),
    )
    checks = {
        "candidate_and_admission_reproduced": (
            permit.candidate["manifest_sha256"]
            == "c28603732cf87b2bbd4a4f19b8aa7bc97a1e44841a8edf588c48614893b104e6"
            and permit.admission["manifest_sha256"]
            == "93ba06fc760069961e2c58df3a3e9c5a8216c5a2edcab158e4a150736761e03a"
        ),
        "one_open_work_item_attempt": (
            len(attempts) == 1
            and attempts[0].get("event_type") == "started"
            and state["attempt_status"]["open_work_keys"]
            == [attempts[0].get("work_key")]
        ),
        "one_official_call_completed_without_retry": (
            len(calls) == 2
            and [row.get("event_type") for row in calls]
            == ["started", "completed"]
            and call_status["call_count"] == 1
            and call_status["completed_calls"] == 1
            and call_status["failed_calls"] == 0
            and call_status["open_attempts"] == 0
            and all(row.get("automatic_retry") is False for row in calls)
        ),
        "append_only_trace_completed": (
            len(trace_rows) == 2
            and trace_status["completed_requests"] == 1
            and trace_status["open_requests"] == 0
            and terminal.get("event_type") == "completed"
        ),
        "official_response_bound_to_local_precommit": (
            request_chain_class
            == "local_precommit_complete_provider_request_id_unavailable"
            and attestation.get("provider_response_id")
            == receipt_evidence.get("response_id")
            and attestation.get("model_id") == public_v4.MODEL_ID
            and receipt_evidence.get("returned_model") == public_v4.MODEL_ID
            and receipt_evidence.get("model_identity_exact_match") is True
            and attestation.get("payload_sha256")
            == receipt_evidence.get("payload_sha256")
        ),
        "no_experiment_record_or_scientific_outcome": (
            not state["records"]
            and wrapper.get("scientific_outcomes_accessed_by_wrapper") is False
        ),
        "free_only_and_no_external_effect": (
            receipt_evidence.get("budget", {}).get("charged_usd") == 0.0
            and wrapper.get("paid_ceiling_usd") == 0.0
            and wrapper.get("provider_tools_enabled") is False
            and wrapper.get("external_effects_enabled") is False
        ),
        "wrapper_sealed_nonzero_once": (
            wrapper.get("final_exit_code") == 1
            and wrapper.get("automatic_retries") == 0
            and wrapper.get("steps", {})
            .get("03_execute", {})
            .get("exit_code")
            == 1
        ),
        "exact_contract_error_archived": EXPECTED_ERROR in stderr_text,
        "failure_was_not_rate_limit": (
            receipt_evidence.get("http_status") == 200
            and "429" not in stderr_text
        ),
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise GeminiPublicSegmentAbortReviewV1Error(
            f"failed Gemini segment-1 abort checks: {failed}"
        )
    source_paths = [
        public_v4.CANDIDATE_PATH,
        public_v4.admission_path(SEGMENT_INDEX, QUOTA_DAY),
        permit.attempt_ledger_path,
        permit.call_ledger_path,
        trace_path,
        WRAPPER_RECEIPT,
        WRAPPER_STDERR,
        Path(__file__),
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "status": "aborted_result_ineligible_contract_revision_required",
        "segment_index": SEGMENT_INDEX,
        "quota_day": QUOTA_DAY,
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "candidate_manifest_sha256": permit.candidate["manifest_sha256"],
        "admission_manifest_sha256": permit.admission["manifest_sha256"],
        "request_chain_class": request_chain_class,
        "stop_reason": (
            "provider_request_id_unavailable_conflicts_with_historical_"
            "formal_record_semantics"
        ),
        "technical_checks": checks,
        "trace_summary": {
            "work_item_attempt_events": len(attempts),
            "open_work_item_attempts": len(
                state["attempt_status"]["open_work_keys"]
            ),
            "provider_call_events": len(calls),
            "provider_calls_completed": call_status["completed_calls"],
            "official_http_status": int(receipt_evidence["http_status"]),
            "provider_request_id_available": False,
            "official_response_id_available": True,
            "exact_model_identity": True,
            "append_only_trace_terminal": True,
            "experiment_records": len(state["records"]),
        },
        "evidence_boundary": {
            "prompts_read": 0,
            "response_text_read": 0,
            "credentials_read": False,
            "scientific_outcomes_read": 0,
            "external_effects_enabled": False,
            "provider_tools_enabled": False,
            "charged_usd": 0.0,
        },
        "disposition": {
            "same_segment_resumable": False,
            "same_work_item_retry_allowed": False,
            "result_eligible": False,
            "orphan_response_promotable": False,
            "quota_day_consumed": True,
            "prospective_contract_revision_required": True,
            "fresh_segment_and_execution_identity_required": True,
        },
        "locked_evidence": [_file_lock(path) for path in source_paths],
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(
            value,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_review()
    _write_json(path, value)
    return value


def verify_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = _read_object(path)
    if (
        observed.get("manifest_sha256")
        != sha256_canonical_json(_without_manifest(observed))
        or observed != build_review()
    ):
        raise GeminiPublicSegmentAbortReviewV1Error(
            "Gemini segment-1 abort review drift"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = write_review() if args.write else verify_review()
    print(
        json.dumps(
            {
                "status": value["status"],
                "segment_index": value["segment_index"],
                "request_chain_class": value["request_chain_class"],
                "result_eligible": value["disposition"]["result_eligible"],
                "same_work_item_retry_allowed": value["disposition"][
                    "same_work_item_retry_allowed"
                ],
                "manifest_sha256": value["manifest_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
