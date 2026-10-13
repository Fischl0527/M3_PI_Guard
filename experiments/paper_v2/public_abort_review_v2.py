"""冻结 Public-v2 主金丝雀的无内容偏见中止审查记录。

复核第二轮金丝雀测试的熔断触发条件与现场快照。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import formal_matrix_controller_v1 as medium_v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.medium_runtime import DEFAULT_V2_PLAN
from experiments.paper_v2.public_execution_store_v1 import (
    cross_bind_public_budget_and_records,
    load_public_record_entries,
    validate_public_budget_events,
    validate_public_record_entries,
)
from experiments.paper_v2.public_live_controller_v2 import (
    _canary_rows,
    validate_canary_admission,
)
from experiments.paper_v2.public_matrix_plan_v1 import DEFAULT_PLAN
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions/"
    "deepseek_public_primary_canary_admission_v2.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v2.json"
)
GENERATED_AT = "2026-07-28T12:52:00+08:00"


class PublicAbortReviewV2Error(ValueError):
    """当固化的 Public-v2 中止论据发生漂移时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicAbortReviewV2Error(f"{path}: expected an object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicAbortReviewV2Error(f"missing abort evidence: {path}")
    return {
        "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                key: item
                for key, item in value.items()
                if key != "manifest_sha256"
            }
        )
    ).hexdigest()


def _plan_work_keys(path: Path) -> set[str]:
    return {
        str(row["work_key"])
        for row in medium_v1._load_jsonl(path)
    }


def build_abort_review() -> dict[str, Any]:
    admission = validate_canary_admission(
        _load_json(ADMISSION),
        model_role="primary",
    )
    rows = _canary_rows("primary")
    known_keys = {str(item["work_key"]) for item in rows}
    run_id = str(admission["scope"]["run_id"])
    execution_identity = str(admission["scope"]["execution_identity"])
    root = PROJECT_ROOT / str(admission["scope"]["output_root"])
    attempt_path = root / "attempt_events.jsonl"
    budget_path = root / "budget_events.jsonl"
    record_path = root / "experiment_records.jsonl"
    trace_root = root / "provider_traces"

    attempts = medium_v1._load_jsonl(attempt_path)
    attempt_status = medium_v1.validate_attempt_events(
        attempts,
        run_id=run_id,
        execution_identity=execution_identity,
        known_work_keys=known_keys,
    )
    open_keys = set(attempt_status["open_work_keys"])
    terminal_attempts = set(attempt_status["terminal_by_work_key"])
    if (
        len(attempts) != 25
        or len(open_keys) != 1
        or len(terminal_attempts) != 12
    ):
        raise PublicAbortReviewV2Error(
            "Public-v2 attempt ledger differs from the stopped canary"
        )
    open_key = next(iter(open_keys))

    role_policy = build_role_policy(load_public_policy(), "primary")
    budget_events = medium_v1._load_jsonl(budget_path)
    budget_status = validate_public_budget_events(
        budget_events,
        run_id=run_id,
        execution_identity=execution_identity,
        model_role="primary",
        known_work_keys=known_keys,
        role_policy=role_policy,
    )
    if (
        len(budget_events) != 29
        or budget_status["paused"]
        or budget_status["role_cumulative_usage"]
        != {
            "prompt_tokens": 22169,
            "completion_tokens": 1934,
            "prompt_cache_hit_tokens": 17536,
            "prompt_cache_miss_tokens": 4633,
        }
        or budget_status["role_cumulative_cost_cny"] != 0.0259414
    ):
        raise PublicAbortReviewV2Error(
            "Public-v2 budget ledger differs from the stopped canary"
        )

    record_entries = load_public_record_entries(record_path)
    record_status = validate_public_record_entries(
        record_entries,
        work_items=rows,
        execution_identity=execution_identity,
        run_id=run_id,
        role_policy=role_policy,
    )
    record_keys = {str(entry["work_key"]) for entry in record_entries}
    if (
        len(record_entries) != 12
        or record_keys != terminal_attempts
        or open_key in record_keys
        or record_status["remaining_work_items"] != 12
    ):
        raise PublicAbortReviewV2Error(
            "Public-v2 record/attempt boundary drift"
        )

    open_budget_events = [
        event
        for event in budget_events
        if str(event["work_key"]) == open_key
    ]
    completed_budget_events = [
        event
        for event in budget_events
        if str(event["work_key"]) != open_key
    ]
    if (
        len(open_budget_events) != 2
        or [event["call_index"] for event in open_budget_events] != [1, 2]
    ):
        raise PublicAbortReviewV2Error(
            "Public-v2 orphaned-call boundary drift"
        )
    cross_bind_public_budget_and_records(
        budget_events=completed_budget_events,
        record_entries=record_entries,
        trace_root=trace_root,
        role_policy=role_policy,
    )

    open_trace_path = trace_root / f"{open_key}.jsonl"
    open_trace = medium_v1._trace_rows(open_trace_path)
    completed_trace = [
        row
        for row in open_trace
        if row["event"]["event_type"] == "completed"
    ]
    trace_response_ids = {
        str(row["event"]["attestation"]["provider_response_id"])
        for row in completed_trace
    }
    budget_response_ids = {
        str(event["provider_response_id"])
        for event in open_budget_events
    }
    if (
        len(open_trace) != 4
        or [row["event"]["event_type"] for row in open_trace]
        != ["started", "completed", "started", "completed"]
        or any(row["event"]["automatic_retry"] for row in open_trace)
        or trace_response_ids != budget_response_ids
    ):
        raise PublicAbortReviewV2Error(
            "Public-v2 open-attempt trace drift"
        )

    public_keys = _plan_work_keys(DEFAULT_PLAN)
    medium_keys = _plan_work_keys(DEFAULT_V2_PLAN)
    open_item = next(
        item for item in rows if str(item["work_key"]) == open_key
    )
    if (
        open_item["benchmark"] != "m3-v2"
        or open_key not in public_keys
        or open_key in medium_keys
    ):
        raise PublicAbortReviewV2Error(
            "Public-v2 resolver mismatch classification drift"
        )

    response_ids = [
        str(event["provider_response_id"])
        for event in budget_events
    ]
    core: dict[str, Any] = {
        "schema_version": "m3-paper-v2-public-canary-abort-review-2.0",
        "generated_at": GENERATED_AT,
        "status": "aborted_partial_records_result_ineligible",
        "run_id": run_id,
        "execution_identity": execution_identity,
        "candidate_manifest_sha256": admission["authorization"][
            "candidate_manifest_sha256"
        ],
        "admission_manifest_sha256": admission["manifest_sha256"],
        "admission_file_sha256": _sha256_file(ADMISSION),
        "stop_reason": "public_m3_evaluator_bound_to_medium_plan",
        "operational_summary": {
            "expected_records": 24,
            "record_count": len(record_entries),
            "remaining_work_items": record_status[
                "remaining_work_items"
            ],
            "attempt_event_count": len(attempts),
            "terminal_attempt_count": len(terminal_attempts),
            "open_attempt_count": len(open_keys),
            "untouched_work_item_count": (
                len(rows) - len(record_entries) - len(open_keys)
            ),
            "provider_calls_completed": len(budget_events),
            "record_bound_provider_calls": len(completed_budget_events),
            "orphaned_completed_provider_calls": len(open_budget_events),
            "provider_response_ids_sha256": sha256_canonical_json(
                response_ids
            ),
            "role_cumulative_usage": budget_status[
                "role_cumulative_usage"
            ],
            "role_cumulative_cost_cny": budget_status[
                "role_cumulative_cost_cny"
            ],
            "budget_status": "continue",
        },
        "integrity_checks": {
            "candidate_and_admission_bound": True,
            "attempt_chain_valid": True,
            "budget_chain_valid": True,
            "record_chain_valid": True,
            "terminal_attempts_equal_record_keys": True,
            "open_attempt_disjoint_from_records": True,
            "completed_record_budget_trace_cross_bound": True,
            "orphan_trace_calls_equal_open_budget_calls": True,
            "official_response_ids_present": True,
            "automatic_retry_used": False,
            "public_m3_key_absent_from_medium_resolver_plan": True,
            "external_effects_enabled": False,
        },
        "artifact_locks": [
            _lock(path)
            for path in (
                ADMISSION,
                attempt_path,
                budget_path,
                record_path,
                open_trace_path,
            )
        ],
        "evidence_boundary": {
            "scientific_outcomes_aggregated": False,
            "scientific_outcome_fields_reported": False,
            "result_admission_authorized": False,
            "analysis_authorized": False,
            "run_resumable": False,
            "open_attempt_retry_authorized": False,
            "network_calls_made_by_review": 0,
            "append_only_ledgers_mutated_by_review": False,
        },
        "supersession_requirement": (
            "Any further execution requires a new run, execution identity, "
            "candidate, admission, and owner confirmation after the public "
            "M3 resolver is qualified."
        ),
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def write_abort_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_abort_review()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_abort_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_abort_review()
    if observed != expected:
        raise PublicAbortReviewV2Error("Public-v2 abort review drift")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    value = (
        write_abort_review(args.output)
        if args.write
        else verify_abort_review(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
