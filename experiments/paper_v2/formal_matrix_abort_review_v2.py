"""针对已停止的 DeepSeek v6 矩阵执行无内容偏见的中止复核。

捕获异常中断现场，防止未决记录污染后续正式数据集。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.formal_matrix_controller_v1 as v1
import experiments.paper_v2.formal_matrix_controller_v6 as v6
from experiments.paper_v2.contracts import canonical_json_bytes
from experiments.paper_v2.formal_record_store_v2 import (
    load_record_entries,
    validate_record_entries,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    / "6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9"
)
DEFAULT_REVIEW = OUTPUT_ROOT / "formal_matrix_abort_review_v2.json"


class FormalMatrixAbortReviewV2Error(RuntimeError):
    """当停止的 v6 技术论据无法验证时抛出的异常。"""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalMatrixAbortReviewV2Error(f"{path}: expected an object")
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


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {key: item for key, item in value.items() if key != "manifest_sha256"}
        )
    ).hexdigest()


def build_abort_review() -> dict[str, Any]:
    candidate = v6.verify_matrix_candidate()
    admission = v6.verify_continuation_admission()
    rows = v1._plan_rows()
    keys = {str(row["work_key"]) for row in rows}
    execution_identity = str(rows[0]["execution_identity"])
    records = load_record_entries(OUTPUT_ROOT / "experiment_records_v2.jsonl")
    record_status = validate_record_entries(
        records,
        work_items=rows,
        execution_identity=execution_identity,
        run_id=v6.RUN_ID,
    )
    attempts = v1._load_jsonl(OUTPUT_ROOT / "matrix_attempts_v1.jsonl")
    attempt_status = v1.validate_attempt_events(
        attempts,
        run_id=v6.RUN_ID,
        execution_identity=execution_identity,
        known_work_keys=keys,
    )
    budget_events = v1._load_jsonl(OUTPUT_ROOT / "matrix_budget_v1.jsonl")
    policy = _read_json(v6.DEFAULT_BUDGET_POLICY)
    budget_status = v1.validate_budget_events(
        budget_events,
        run_id=v6.RUN_ID,
        execution_identity=execution_identity,
        known_work_keys=keys,
        policy=policy,
        prior_usage=candidate["scope"]["budget"]["prior_project_usage"],
    )
    terminal_keys = set(record_status["terminal_work_keys"])
    terminal_attempts = set(attempt_status["terminal_by_work_key"])
    open_keys = set(attempt_status["open_work_keys"])
    if (
        terminal_keys != terminal_attempts
        or len(open_keys) != 1
        or open_keys & terminal_keys
    ):
        raise FormalMatrixAbortReviewV2Error(
            "stopped v6 ledger shape differs from the recorded stop"
        )
    open_key = next(iter(open_keys))
    completed_budget = [
        event for event in budget_events if event["work_key"] != open_key
    ]
    open_budget = [
        event for event in budget_events if event["work_key"] == open_key
    ]
    v1._cross_bind_budget_and_records(
        budget_events=completed_budget,
        record_entries=records,
        trace_root=OUTPUT_ROOT / "provider_traces",
    )
    trace_path = OUTPUT_ROOT / "provider_traces" / f"{open_key}.jsonl"
    trace_rows = v1._trace_rows(trace_path)
    completed_trace_events = [
        row
        for row in trace_rows
        if row["event"]["event_type"] == "completed"
    ]
    if (
        len(trace_rows) != 2 * len(open_budget)
        or len(completed_trace_events) != len(open_budget)
        or any(event["automatic_retry"] for event in (row["event"] for row in trace_rows))
    ):
        raise FormalMatrixAbortReviewV2Error(
            "stopped v6 orphan trace does not bind its completed calls"
        )
    statuses = Counter(
        str(entry["record"]["operational_status"]) for entry in records
    )
    tiers = Counter(str(entry["record"]["result_tier"]) for entry in records)
    core = {
        "schema_version": "m3-paper-v2-formal-matrix-abort-review-2.0",
        "status": "aborted_result_ineligible_new_version_required",
        "run_id": v6.RUN_ID,
        "matrix_identity": candidate["scope"]["matrix_identity"],
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "continuation_admission_sha256": _sha256_file(
            v6.DEFAULT_CONTINUATION_ADMISSION
        ),
        "stop_reason": "boundary_rejection_evidence_validation_gap",
        "operational_summary": {
            "record_count": len(records),
            "remaining_work_items": len(rows) - len(records),
            "operational_status_counts": dict(sorted(statuses.items())),
            "result_tier_counts": dict(sorted(tiers.items())),
            "attempt_event_count": len(attempts),
            "open_attempt_count": len(open_keys),
            "record_backed_open_attempt_count": 0,
            "orphaned_completed_work_item_count": 1,
            "orphaned_completed_response_count": len(open_budget),
            "provider_calls_completed": len(budget_events),
            "project_cumulative_cost_cny": budget_status[
                "project_cumulative_cost_cny"
            ],
            "project_cumulative_usage": copy.deepcopy(
                budget_status["project_cumulative_usage"]
            ),
            "budget_status": (
                "paused" if budget_status["paused"] else "continue"
            ),
        },
        "integrity_checks": {
            "record_chain_valid": True,
            "attempt_chain_valid": True,
            "budget_chain_valid": True,
            "terminal_records_equal_terminal_attempts": True,
            "open_attempt_disjoint_from_records": True,
            "completed_record_calls_cross_bound": True,
            "orphan_trace_calls_equal_open_budget_calls": True,
            "automatic_retry_used": False,
            "external_effects_enabled": False,
        },
        "evidence_locks": {
            "record_ledger_sha256": _sha256_file(
                OUTPUT_ROOT / "experiment_records_v2.jsonl"
            ),
            "attempt_ledger_sha256": _sha256_file(
                OUTPUT_ROOT / "matrix_attempts_v1.jsonl"
            ),
            "budget_ledger_sha256": _sha256_file(
                OUTPUT_ROOT / "matrix_budget_v1.jsonl"
            ),
            "orphaned_open_attempt_trace_sha256": _sha256_file(trace_path),
        },
        "evidence_boundary": {
            "scientific_outcomes_reviewed": False,
            "result_admission_authorized": False,
            "analysis_authorized": False,
            "prior_run_resumable": False,
            "open_attempt_retry_authorized": False,
            "network_calls_made_by_review": 0,
            "append_only_ledgers_mutated_by_review": False,
        },
        "supersession_requirement": (
            "Any further execution must use a new run and matrix identity."
        ),
        "active_admission_manifest_sha256": admission["manifest_sha256"],
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def write_abort_review(path: Path = DEFAULT_REVIEW) -> dict[str, Any]:
    value = build_abort_review()
    _write_json(path, value)
    return value


def verify_abort_review(path: Path = DEFAULT_REVIEW) -> dict[str, Any]:
    observed = _read_json(path)
    expected = build_abort_review()
    if observed != expected:
        raise FormalMatrixAbortReviewV2Error("v6 abort review drift")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = write_abort_review() if args.write else verify_abort_review()
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
