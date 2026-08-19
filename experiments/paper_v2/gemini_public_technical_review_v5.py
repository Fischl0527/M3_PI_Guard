"""Failure-aware technical review for segmented Gemini public evidence.

Gemini v4 correctly retained a post-response VIGIL parsing failure as an ITT
``runner_failure``.  Its technical gate nevertheless compared only call-ledger
``completed`` terminals with completed provider traces, conflating provider
transport success with downstream runtime success.  This review never changes
either ledger.  It reconciles the exact, allowlisted post-response failure while
requiring the official trace, terminal runtime record, free-tier boundary, and
isolated-effect evidence to remain complete.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import experiments.paper_v2.gemini_public_controller_v1 as public_v1
import experiments.paper_v2.gemini_public_controller_v4 as public_v4
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGGREGATE_REVIEW_PATH = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini/"
    "public-v5-canary-aggregate-review.json"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-public-segment-review-5.0"
AGGREGATE_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-canary-aggregate-review-5.0"
)
ALLOWLISTED_POST_RESPONSE_FAILURES = frozenset({"VigilLiveDependencyError"})


class GeminiPublicTechnicalReviewV5Error(ValueError):
    """Raised when transport/runtime evidence cannot be reconciled exactly."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicTechnicalReviewV5Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise GeminiPublicTechnicalReviewV5Error(f"{path}: expected object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


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
        raise GeminiPublicTechnicalReviewV5Error(f"missing source file: {path}")
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def review_path(segment_index: int) -> Path:
    candidate = public_v4.verify_candidate()
    try:
        output = candidate["scope"]["segments"][segment_index]["output_root"]
    except (IndexError, KeyError, TypeError) as exc:
        raise GeminiPublicTechnicalReviewV5Error(
            "segment index out of range"
        ) from exc
    return PROJECT_ROOT / str(output) / "technical_segment_review_v5.json"


def _record_map(
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    records = {
        str(entry["record"]["work_key"]): entry["record"] for entry in entries
    }
    if len(records) != len(entries):
        raise GeminiPublicTechnicalReviewV5Error("duplicate Gemini record")
    return records


def reconcile_post_response_calls(
    *,
    calls: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    record_by_work = _record_map(records)
    terminal_events = [
        dict(event) for event in calls if event.get("event_type") != "started"
    ]
    by_work: dict[str, list[dict[str, Any]]] = {}
    reconciled: list[dict[str, Any]] = []
    ordinary_completed = 0
    for event in terminal_events:
        work_key = str(event.get("work_key", ""))
        by_work.setdefault(work_key, []).append(event)
        if event.get("event_type") == "completed":
            ordinary_completed += 1
            continue
        if event.get("event_type") != "failed":
            continue
        record = record_by_work.get(work_key)
        bundle = None if record is None else record.get("provider_trace_bundle")
        if (
            event.get("error_type") not in ALLOWLISTED_POST_RESPONSE_FAILURES
            or not isinstance(record, Mapping)
            or record.get("operational_status") != "runner_failure"
            or record.get("included_in_intention_to_treat") is not True
            or not isinstance(bundle, Mapping)
            or bundle.get("bundle_status") != "completed"
            or int(bundle.get("completed_request_count", -1)) < 1
        ):
            continue
        reconciled.append(
            {
                "work_key": work_key,
                "call_index": int(event["call_index"]),
                "attempt_id": str(event["attempt_id"]),
                "runtime_error_type": str(event["error_type"]),
                "provider_transport_status": "completed_by_trace",
                "runtime_status": "runner_failure_retained_in_itt",
                "trace_tail_sha256": str(bundle["trace_tail_sha256"]),
            }
        )
    per_work_match = True
    for work_key, record in record_by_work.items():
        bundle = record["provider_trace_bundle"]
        terminal_count = len(by_work.get(work_key, []))
        if terminal_count != int(bundle["completed_request_count"]):
            per_work_match = False
            break
    return {
        "terminal_event_count": len(terminal_events),
        "ordinary_completed_call_count": ordinary_completed,
        "reconciled_post_response_failure_count": len(reconciled),
        "reconciled_calls": reconciled,
        "per_work_terminal_count_matches_completed_trace_count": per_work_match,
    }


def build_segment_review(
    segment_index: int,
    *,
    quota_day: str,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    permit = public_v4._permit(
        segment_index=segment_index,
        quota_day=quota_day,
        selected_admission=public_v4.admission_path(segment_index, quota_day),
    )
    state = public_v1._state(permit)
    records = state["records"]
    original_review_path = public_v4.review_path(segment_index)
    original_review = _read_json(original_review_path)
    reconciliation = reconcile_post_response_calls(
        calls=state["calls"], records=records
    )
    bundles = [entry["record"]["provider_trace_bundle"] for entry in records]
    record_values = [entry["record"] for entry in records]
    trace_calls = sum(int(bundle["completed_request_count"]) for bundle in bundles)
    reconciled = int(reconciliation["reconciled_post_response_failure_count"])
    call_status = state["call_status"]
    runner_failures = sum(
        record["operational_status"] == "runner_failure"
        for record in record_values
    )
    checks = {
        "exact_record_count": len(records) == len(permit.work_items),
        "all_attempts_terminal": not state["attempt_status"]["open_work_keys"],
        "all_call_attempts_terminal": call_status["open_attempts"] == 0,
        "provider_call_cap_respected": call_status["call_count"]
        <= int(permit.admission["maximum_provider_requests"]),
        "provider_attempt_count_matches_trace": call_status["call_count"]
        == trace_calls,
        "completed_plus_reconciled_matches_trace": call_status[
            "completed_calls"
        ]
        + reconciled
        == trace_calls,
        "all_failed_calls_are_exactly_reconciled": call_status["failed_calls"]
        == reconciled,
        "no_paused_calls": call_status["paused_calls"] == 0,
        "per_work_terminal_count_matches_trace": bool(
            reconciliation[
                "per_work_terminal_count_matches_completed_trace_count"
            ]
        ),
        "all_trace_bundles_complete": all(
            bundle["bundle_status"] == "completed"
            and bundle["provider_id"] == "gemini"
            and bundle["model_id"] == public_v4.MODEL_ID
            for bundle in bundles
        ),
        "all_free_tier_zero_charge": all(
            bundle["usage_summary"]["billing_tier"] == "free"
            and bundle["usage_summary"]["charged_usd"] == 0.0
            and bundle["usage_summary"]["paid_ceiling_usd"] == 0.0
            for bundle in bundles
        ),
        "all_records_retained_in_itt": all(
            record["included_in_intention_to_treat"] is True
            for record in record_values
        ),
        "all_runner_failures_explained_by_reconciliation": runner_failures
        == reconciled,
        "all_effects_isolated": all(
            record["provider_safety_receipt"]["evidence"][
                "external_connectors_enabled"
            ]
            is False
            and record["provider_safety_receipt"]["evidence"][
                "provider_managed_tools_enabled"
            ]
            is False
            for record in record_values
        ),
    }
    passed = bool(checks) and all(checks.values())
    source_paths = [
        Path(__file__),
        public_v4.CANDIDATE_PATH,
        public_v4.admission_path(segment_index, quota_day),
        original_review_path,
        permit.record_ledger_path,
        permit.attempt_ledger_path,
        permit.call_ledger_path,
        *sorted(permit.trace_root.glob("*.jsonl")),
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "failure_aware_outcome_blind_gemini_segment_review",
        "reviewed_at": reviewed_at or _now(),
        "status": (
            "gemini_public_v5_segment_technical_gate_pass"
            if passed
            else "gemini_public_v5_segment_technical_gate_fail"
        ),
        "segment_index": segment_index,
        "quota_day": quota_day,
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "candidate_manifest_sha256": permit.candidate["manifest_sha256"],
        "admission_file_sha256": permit.admission_file_sha256,
        "original_v4_review_manifest_sha256": original_review[
            "manifest_sha256"
        ],
        "expected_records": len(permit.work_items),
        "observed_records": len(records),
        "provider_call_attempts": call_status["call_count"],
        "provider_transport_completions": trace_calls,
        "runtime_runner_failures_retained_in_itt": runner_failures,
        "reconciliation": reconciliation,
        "allowlisted_post_response_failure_types": sorted(
            ALLOWLISTED_POST_RESPONSE_FAILURES
        ),
        "checks": checks,
        "technical_gate_passed": passed,
        "matrix_continuation_eligible": passed,
        "scientific_outcomes_accessed": False,
        "result_admission_authorized": False,
        "source_locks": [_file_lock(path) for path in source_paths],
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_segment_review(segment_index: int, *, quota_day: str) -> dict[str, Any]:
    value = build_segment_review(segment_index, quota_day=quota_day)
    _write_json(review_path(segment_index), value)
    return value


def verify_segment_review(segment_index: int, *, quota_day: str) -> dict[str, Any]:
    observed = _read_json(review_path(segment_index))
    expected = build_segment_review(
        segment_index,
        quota_day=quota_day,
        reviewed_at=str(observed.get("reviewed_at", "")),
    )
    if observed != expected or observed.get("manifest_sha256") != _manifest_sha(
        observed
    ):
        raise GeminiPublicTechnicalReviewV5Error("segment review drift")
    return copy.deepcopy(observed)


def build_aggregate_review(*, reviewed_at: str | None = None) -> dict[str, Any]:
    candidate = public_v4.verify_candidate()
    reviews: list[dict[str, Any]] = []
    for segment in candidate["scope"]["segments"]:
        index = int(segment["segment_index"])
        review = _read_json(review_path(index))
        if (
            review.get("manifest_sha256") != _manifest_sha(review)
            or review.get("status")
            != "gemini_public_v5_segment_technical_gate_pass"
            or review.get("execution_identity") != segment["execution_identity"]
            or review.get("observed_records") != segment["record_count"]
        ):
            raise GeminiPublicTechnicalReviewV5Error(
                f"segment {index} v5 review not admitted"
            )
        reviews.append(review)
    quota_days = [str(review["quota_day"]) for review in reviews]
    checks = {
        "all_eight_segment_gates_passed": len(reviews) == 8,
        "exact_twelve_canary_records": sum(
            int(review["observed_records"]) for review in reviews
        )
        == 12,
        "quota_days_are_distinct": len(set(quota_days)) == len(quota_days),
        "all_failures_retained_in_itt": all(
            review["checks"]["all_records_retained_in_itt"] is True
            for review in reviews
        ),
        "all_effects_isolated": all(
            review["checks"]["all_effects_isolated"] is True
            for review in reviews
        ),
    }
    passed = all(checks.values())
    core = {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "artifact_role": "failure_aware_gemini_canary_aggregate_review",
        "reviewed_at": reviewed_at or _now(),
        "status": (
            "gemini_public_v5_canary_technical_gate_pass"
            if passed
            else "gemini_public_v5_canary_technical_gate_fail"
        ),
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "segment_review_manifest_sha256": [
            review["manifest_sha256"] for review in reviews
        ],
        "observed_records": sum(
            int(review["observed_records"]) for review in reviews
        ),
        "provider_transport_completions": sum(
            int(review["provider_transport_completions"]) for review in reviews
        ),
        "runtime_runner_failures_retained_in_itt": sum(
            int(review["runtime_runner_failures_retained_in_itt"])
            for review in reviews
        ),
        "checks": checks,
        "matrix_continuation_eligible": passed,
        "scientific_outcomes_accessed": False,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_aggregate_review() -> dict[str, Any]:
    value = build_aggregate_review()
    _write_json(AGGREGATE_REVIEW_PATH, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-segment-review", action="store_true")
    action.add_argument("--verify-segment-review", action="store_true")
    action.add_argument("--write-aggregate-review", action="store_true")
    parser.add_argument("--segment-index", type=int)
    parser.add_argument("--quota-day")
    args = parser.parse_args()
    if args.write_aggregate_review:
        value = write_aggregate_review()
    else:
        if args.segment_index is None or not args.quota_day:
            parser.error("segment review requires index and quota day")
        value = (
            write_segment_review(args.segment_index, quota_day=args.quota_day)
            if args.write_segment_review
            else verify_segment_review(args.segment_index, quota_day=args.quota_day)
        )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
