"""Content-free abort review for the stopped DeepSeek v7 canary."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.formal_matrix_controller_v1 as v1
import experiments.paper_v2.formal_matrix_controller_v7 as v7
from experiments.paper_v2.contracts import canonical_json_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    / "a34fe5b87607cb48144b0d36da282accc25d33cd18706351eb39dd25ebe04c75"
)
DEFAULT_REVIEW = OUTPUT_ROOT / "formal_matrix_abort_review_v3.json"


class FormalMatrixAbortReviewV3Error(RuntimeError):
    """Raised when stopped-v7 technical evidence cannot be verified."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalMatrixAbortReviewV3Error(f"{path}: expected an object")
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
    candidate = v7.verify_matrix_candidate()
    admission = v7.verify_canary_admission()
    rows = v1._plan_rows()
    keys = {str(row["work_key"]) for row in rows}
    execution_identity = str(rows[0]["execution_identity"])
    record_path = OUTPUT_ROOT / "experiment_records_v2.jsonl"
    if record_path.exists():
        raise FormalMatrixAbortReviewV3Error(
            "stopped v7 canary unexpectedly created a result ledger"
        )

    attempts = v1._load_jsonl(OUTPUT_ROOT / "matrix_attempts_v1.jsonl")
    attempt_status = v1.validate_attempt_events(
        attempts,
        run_id=v7.RUN_ID,
        execution_identity=execution_identity,
        known_work_keys=keys,
    )
    open_keys = set(attempt_status["open_work_keys"])
    terminal_attempts = set(attempt_status["terminal_by_work_key"])
    if len(attempts) != 1 or len(open_keys) != 1 or terminal_attempts:
        raise FormalMatrixAbortReviewV3Error(
            "stopped v7 attempt ledger differs from the recorded failure"
        )
    open_key = next(iter(open_keys))

    budget_events = v1._load_jsonl(OUTPUT_ROOT / "matrix_budget_v1.jsonl")
    policy = _read_json(v7.DEFAULT_BUDGET_POLICY)
    budget_status = v1.validate_budget_events(
        budget_events,
        run_id=v7.RUN_ID,
        execution_identity=execution_identity,
        known_work_keys=keys,
        policy=policy,
        prior_usage=candidate["scope"]["budget"]["prior_project_usage"],
    )
    if (
        len(budget_events) != 2
        or any(event["work_key"] != open_key for event in budget_events)
    ):
        raise FormalMatrixAbortReviewV3Error(
            "stopped v7 budget ledger differs from the recorded failure"
        )

    trace_path = OUTPUT_ROOT / "provider_traces" / f"{open_key}.jsonl"
    trace_rows = v1._trace_rows(trace_path)
    completed = [
        row
        for row in trace_rows
        if row["event"]["event_type"] == "completed"
    ]
    if (
        len(trace_rows) != 2 * len(budget_events)
        or len(completed) != len(budget_events)
        or any(
            row["event"]["automatic_retry"]
            for row in trace_rows
        )
    ):
        raise FormalMatrixAbortReviewV3Error(
            "stopped v7 trace does not bind its completed provider calls"
        )
    response_ids = [str(event["provider_response_id"]) for event in budget_events]
    if any(not value for value in response_ids):
        raise FormalMatrixAbortReviewV3Error(
            "stopped v7 provider response identity is incomplete"
        )

    incremental_cost = (
        budget_status["project_cumulative_cost_cny"]
        - candidate["scope"]["budget"]["prior_project_cost_cny"]
    )
    core = {
        "schema_version": "m3-paper-v2-formal-matrix-abort-review-3.0",
        "status": "aborted_result_ineligible_new_version_required",
        "run_id": v7.RUN_ID,
        "matrix_identity": candidate["scope"]["matrix_identity"],
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "canary_admission_sha256": _sha256_file(
            v7.DEFAULT_CANARY_ADMISSION
        ),
        "stop_reason": "lazy_boundary_adapter_binding_lifecycle_gap",
        "operational_summary": {
            "record_count": 0,
            "remaining_work_items": len(rows),
            "attempt_event_count": len(attempts),
            "open_attempt_count": len(open_keys),
            "record_backed_open_attempt_count": 0,
            "orphaned_completed_work_item_count": 1,
            "orphaned_completed_response_count": len(budget_events),
            "provider_calls_completed": len(budget_events),
            "provider_response_ids_sha256": hashlib.sha256(
                canonical_json_bytes(response_ids)
            ).hexdigest(),
            "incremental_cost_cny": round(incremental_cost, 10),
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
            "result_ledger_absent": True,
            "attempt_chain_valid": True,
            "budget_chain_valid": True,
            "open_attempt_disjoint_from_records": True,
            "orphan_trace_calls_equal_open_budget_calls": True,
            "official_response_ids_present": True,
            "automatic_retry_used": False,
            "external_effects_enabled": False,
        },
        "evidence_locks": {
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
        raise FormalMatrixAbortReviewV3Error("v7 abort review drift")
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
