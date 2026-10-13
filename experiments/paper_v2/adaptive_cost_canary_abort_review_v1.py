"""自适应成本金丝雀运行中止的盲审封签复核模块。

当自适应成本探索触发预算熔断或运行异常中止时，在不窥探未完成结果的前提下，
固化现场上下文证据并执行规范的中止审查。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.adaptive_cost_canary_controller_v1 as canary_v1
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    _load_jsonl,
    cross_bind_query_and_call_ledgers,
    validate_query_events,
)
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.public_execution_store_v1 import (
    validate_public_budget_events,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/adaptive_cost_canary_abort_review_v1.json"
)
RUNTIME_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/adaptive_cost_canary_v1_runtime_20260730"
)
GENERATED_AT = "2026-07-30T01:58:26+08:00"
EXPECTED_ERROR = "KeyError: 'effective_guard_decision'"


class AdaptiveCostCanaryAbortReviewError(ValueError):
    """当失败的自适应-v1 证据无法被封存固化时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdaptiveCostCanaryAbortReviewError(
            f"{path}: expected an object"
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


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveCostCanaryAbortReviewError(
            f"missing adaptive-v1 abort artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def build_abort_review() -> dict[str, Any]:
    candidate = canary_v1.verify_candidate()
    admission = canary_v1.validate_canary_admission(
        canary_v1._load_json(canary_v1.DEFAULT_ADMISSION)
    )
    permit = canary_v1.authorize_canary(
        admission_path=canary_v1.DEFAULT_ADMISSION
    )
    role_policy = canary_v1.adaptive_role_policy()
    query_events = _load_jsonl(permit.query_ledger_path)
    budget_events = canary_v1._load_budget_events(
        permit.budget_ledger_path
    )
    query_status = validate_query_events(
        query_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    budget_status = validate_public_budget_events(
        budget_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    cross_bind_query_and_call_ledgers(
        query_events=query_events,
        budget_events=budget_events,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    stderr_path = RUNTIME_ROOT / "stderr.log"
    stdout_path = RUNTIME_ROOT / "stdout.log"
    stderr = stderr_path.read_text(encoding="utf-8")
    if EXPECTED_ERROR not in stderr:
        raise AdaptiveCostCanaryAbortReviewError(
            "adaptive-v1 stderr fingerprint drift"
        )
    trace_paths = sorted(permit.trace_root.glob("*.jsonl"))
    if (
        query_status["event_count"] != 2
        or query_status["terminal_query_count"] != 1
        or query_status["formal_candidate_query_count"] != 1
        or query_status["diagnostic_query_count"] != 0
        or query_status["completed_provider_call_count"] != 1
        or query_status["open_query_work_keys"]
        or budget_status["event_count"] != 1
        or budget_status["paused"] is not False
        or len(trace_paths) != 1
    ):
        raise AdaptiveCostCanaryAbortReviewError(
            "adaptive-v1 abort cardinality drift"
        )
    locks = [
        _lock(Path(__file__)),
        _lock(
            PROJECT_ROOT
            / "protocols/paper_upgrade_v2/adaptive_cost_canary_candidate_v1.json"
        ),
        _lock(canary_v1.DEFAULT_ADMISSION),
        _lock(
            PROJECT_ROOT
            / "experiments/paper_v2/adaptive_cost_canary_controller_v1.py"
        ),
        _lock(
            PROJECT_ROOT
            / "experiments/paper_v2/adaptive_cost_canary_plan_v1.py"
        ),
        _lock(permit.query_ledger_path),
        _lock(permit.budget_ledger_path),
        *[_lock(path) for path in trace_paths],
        _lock(stderr_path),
        _lock(stdout_path),
    ]
    checks = {
        "candidate_and_admission_valid": True,
        "query_chain_valid": True,
        "query_is_terminal": True,
        "budget_chain_valid": True,
        "query_and_provider_call_cross_bound": True,
        "one_provider_trace_complete": True,
        "automatic_retry_used": False,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "runtime_process_remaining": False,
    }
    core = {
        "schema_version": "m3-paper-v2-adaptive-cost-canary-abort-review-1.0",
        "generated_at": GENERATED_AT,
        "status": (
            "adaptive_v1_aborted_after_one_terminal_query_result_ineligible"
        ),
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_manifest_sha256": admission["manifest_sha256"],
        "stop_reason": "post_record_decision_field_name_mismatch",
        "root_cause": {
            "requested_field": "effective_guard_decision",
            "record_contract_field": "initial_guard_decision",
            "provider_usage_anomaly_observed": False,
            "record_and_trace_are_valid": True,
            "remediation": (
                "Use a fresh candidate/run/execution/output identity and "
                "derive the MCTS decision from initial_guard_decision."
            ),
        },
        "operational_summary": {
            "maximum_queries": 400,
            "query_event_count": query_status["event_count"],
            "terminal_query_count": query_status[
                "terminal_query_count"
            ],
            "open_query_count": 0,
            "provider_calls_completed": query_status[
                "completed_provider_call_count"
            ],
            "role_cumulative_usage": budget_status[
                "role_cumulative_usage"
            ],
            "role_cumulative_cost_cny": budget_status[
                "role_cumulative_cost_cny"
            ],
            "automatic_retries": 0,
        },
        "integrity_checks": checks,
        "artifact_locks": locks,
        "evidence_boundary": {
            "old_root_resumable": False,
            "old_query_reusable_in_fresh_result": False,
            "selective_retry_authorized": False,
            "formal_continuation_authorized": False,
            "analysis_authorized": False,
            "result_admission_authorized": False,
            "scientific_outcomes_aggregated": False,
            "scientific_outcome_fields_reported": False,
            "network_calls_made_by_review": 0,
            "append_only_ledgers_mutated_by_review": False,
        },
        "checks_sha256": sha256_canonical_json(checks),
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_abort_review(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveCostCanaryAbortReviewError(
            "adaptive-v1 abort review must be an object"
        )
    expected = build_abort_review()
    if dict(value) != expected:
        raise AdaptiveCostCanaryAbortReviewError(
            "adaptive-v1 abort review drift"
        )
    return copy.deepcopy(dict(value))


def write_abort_review(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = build_abort_review()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_abort_review(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    return validate_abort_review(_load_json(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = (
        verify_abort_review(args.output)
        if args.verify
        else write_abort_review(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
