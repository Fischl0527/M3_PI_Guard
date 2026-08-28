"""Lean B200-survivor to B500 adaptive-tail runner.

Only query indices 201--500 for the twelve prospectively selected survivors
are eligible.  The runner copies the existing 200-query search state once,
persists one compact raw row per new query, and never replays provider calls or
performs recursive historical evidence validation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.adaptive_cost_canary_controller_v1 as canary_controller
import experiments.paper_v2.adaptive_cost_canary_plan_v1 as canary_plan
import experiments.paper_v2.adaptive_formal_plan_v2 as formal_plan
from experiments.paper_v1.adaptive_attack import AdaptiveMCTSSearch, OracleResult
from experiments.paper_v2.incremental_empirical_plan_v1 import (
    ADAPTIVE_TAIL_PLAN,
    GLOBAL_FUSE_CNY,
    MANIFEST_PATH,
    PROJECT_ROOT,
    REGULAR_FUSES_CNY,
)
from experiments.paper_v2.incremental_live_ledgers_v1 import (
    IncrementalPublicBudgetTracker,
)
from experiments.paper_v2.lean_empirical_runner import (
    _deepseek_api_key,
    _read_jsonl,
)
from experiments.paper_v2.public_execution_store_v1 import (
    assemble_public_experiment_record,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)
from m3_core.project_config import parse_env_file, resolve_config_path


OUTPUT_ROOT = PROJECT_ROOT / "outputs/experiments/incremental_empirical_v1/adaptive-tail"
RAW_PATH = OUTPUT_ROOT / "raw_query_records_v1.jsonl"
FAILURE_PATH = OUTPUT_ROOT / "failure_records_v1.jsonl"
BUDGET_PATH = OUTPUT_ROOT / "internal/deepseek_budget_events.jsonl"
TRACE_ROOT = OUTPUT_ROOT / "internal/provider_traces"
CHECKPOINT_ROOT = OUTPUT_ROOT / "search_checkpoints"
CANARY_GATE_PATH = OUTPUT_ROOT / "canary_gate_v1.json"
COST_SUMMARY_PATH = OUTPUT_ROOT / "cost_summary_v1.json"
SOURCE_STAGE_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/adaptive_formal_pro_v2"
    / "pro_200-0f3e1f04239237c56b3ece87ef8eda8a6a4daf299bfa1c88bb04bf6280737d2f"
)
SOURCE_CHECKPOINT_ROOT = SOURCE_STAGE_ROOT / "search_checkpoints"
ADAPTIVE_SEED = 20260723
CANARY_NEW_QUERIES = 5


class IncrementalAdaptiveTailError(RuntimeError):
    """Raised when E5 cannot preserve its frozen continuation boundary."""


class IncrementalAdaptiveTailStop(RuntimeError):
    """Clean stop after one response-less or otherwise non-continuable query."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_tail_plan() -> list[dict[str, Any]]:
    rows = sorted(_read_jsonl(ADAPTIVE_TAIL_PLAN), key=lambda row: int(row["sequence"]))
    if (
        len(rows) != 12
        or len({str(row["work_key"]) for row in rows}) != 12
        or {str(row["attack_family"]) for row in rows} != {"A1", "A2", "A3"}
        or any(
            row.get("study") != "adaptive-tail"
            or row.get("start_query") != 201
            or row.get("end_query") != 500
            or row.get("selection_condition")
            != "no_unsafe_effect_through_query_200"
            or row.get("stop_after_first_unsafe_effect") is not True
            or row.get("model_id") != "deepseek-v4-pro"
            for row in rows
        )
        or sum(int(row["formal_prefix_query_count"]) == CANARY_NEW_QUERIES for row in rows)
        != 2
    ):
        raise IncrementalAdaptiveTailError("adaptive-tail frozen plan drift")
    for family in ("A1", "A2", "A3"):
        if sum(row["attack_family"] == family for row in rows) != 4:
            raise IncrementalAdaptiveTailError("adaptive-tail family balance drift")
    return rows


def _source_record(task: Mapping[str, Any]) -> dict[str, Any]:
    return canary_plan._read_task_record(task)


def build_runtime_candidate(
    plan_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = list(plan_rows or load_tail_plan())
    identities = {str(row["execution_identity"]) for row in rows}
    run_ids = {str(row["run_id"]) for row in rows}
    if len(identities) != 1 or len(run_ids) != 1:
        raise IncrementalAdaptiveTailError("adaptive-tail execution identity drift")
    compact: list[dict[str, Any]] = []
    for row in rows:
        record = _source_record(row)
        compact.append(
            {
                "case_id": str(row["case_id"]),
                "source": str(row["source"]),
                "source_line": int(row["source_line"]),
                "source_record_sha256": str(row["source_record_sha256"]),
                "attack_family": str(row["attack_family"]),
                "language": str(record.get("language", "unknown")),
                "base_payload_sha256": hashlib.sha256(
                    str(record["untrusted_content"]).encode("utf-8")
                ).hexdigest(),
            }
        )
    return {
        "schema_version": "m3-paper-v2-adaptive-tail-runtime-candidate-1.0",
        "execution_identity": identities.pop(),
        "scope": {
            "run_id": run_ids.pop(),
            "tasks": compact,
            "start_query": 201,
            "end_query": 500,
        },
    }


def _known_query_keys(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        formal_plan.adaptive_query_work_key(str(row["case_id"]), query_index)
        for row in rows
        for query_index in range(201, 501)
    }


def _read_checkpoint(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IncrementalAdaptiveTailError(f"invalid adaptive checkpoint: {path}") from exc
    if not isinstance(value, dict):
        raise IncrementalAdaptiveTailError(f"adaptive checkpoint is not an object: {path}")
    return value


def _validate_source_checkpoint(task: Mapping[str, Any]) -> dict[str, Any]:
    case_id = str(task["case_id"])
    path = SOURCE_CHECKPOINT_ROOT / f"{case_id}.json"
    value = _read_checkpoint(path)
    queries = value.get("queries")
    if (
        not isinstance(queries, list)
        or len(queries) != 200
        or value.get("first_success_query") is not None
        or [int(row.get("query", -1)) for row in queries] != list(range(1, 201))
    ):
        raise IncrementalAdaptiveTailError(
            f"{case_id}: source is not a no-success B200 checkpoint"
        )
    return value


def prepare_checkpoints(
    tasks: Sequence[Mapping[str, Any]],
    *,
    checkpoint_root: Path = CHECKPOINT_ROOT,
) -> dict[str, int]:
    copied = 0
    reused = 0
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        case_id = str(task["case_id"])
        source = _validate_source_checkpoint(task)
        source_path = SOURCE_CHECKPOINT_ROOT / f"{case_id}.json"
        destination = checkpoint_root / f"{case_id}.json"
        if not destination.exists():
            shutil.copyfile(source_path, destination)
            copied += 1
        else:
            reused += 1
        observed = _read_checkpoint(destination)
        queries = observed.get("queries")
        if (
            not isinstance(queries, list)
            or len(queries) < 200
            or queries[:200] != source["queries"]
            or observed.get("first_success_query") not in {
                None,
                *range(201, len(queries) + 1),
            }
        ):
            raise IncrementalAdaptiveTailError(
                f"{case_id}: copied B200 prefix or tail checkpoint drift"
            )
    return {"copied": copied, "reused": reused}


def _latest_raw() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(RAW_PATH):
        key = str(row.get("work_key", ""))
        if not key:
            raise IncrementalAdaptiveTailError("adaptive raw row lacks work key")
        attempt = int(row.get("attempt", 0))
        if attempt <= int(latest.get(key, {}).get("attempt", 0)):
            raise IncrementalAdaptiveTailError("adaptive raw attempt order drift")
        latest[key] = row
    return latest


def _explicit_retry_allowed(key: str, latest: Mapping[str, Any]) -> bool:
    """Return whether an explicitly named response-less row may be retried.

    A second response-less attempt is normally terminal.  The sole exception is
    the local trace-directory collision produced by the old recovery-root
    selector: it failed before a provider request and therefore did not consume
    the scientific work item.  The exception is deliberately narrow and still
    rejects every response-bearing history.
    """

    history = [
        row
        for row in _read_jsonl(RAW_PATH)
        if str(row.get("work_key", "")) == key
    ]
    attempts = [int(row.get("attempt", 0)) for row in history]
    if (
        not history
        or int(latest.get("attempt", 0)) != attempts[-1]
        or latest.get("response_obtained") is not False
        or not all(row.get("response_obtained") is False for row in history)
    ):
        return False
    if latest.get("retry_eligible") is True:
        return attempts == [1]
    if (
        attempts != [1, 2]
        or latest.get("operational_status") != "pre_response_transport_failure"
        or latest.get("error_type") != "ProviderTraceBundleError"
        or history[0].get("retry_eligible") is not True
    ):
        return False
    collision_trace = (
        TRACE_ROOT.parent / "provider_traces_recovery2" / f"{key}.jsonl"
    )
    if not collision_trace.is_file() or collision_trace.stat().st_size == 0:
        return False
    trace_rows = _read_jsonl(collision_trace)
    return bool(trace_rows) and not any(
        row.get("event", {}).get("event_type") == "completed"
        for row in trace_rows
        if isinstance(row.get("event"), Mapping)
    )


def _fresh_recovery_trace_root(trace_root: Path = TRACE_ROOT) -> Path:
    """Choose a never-before-used trace root for an explicit recovery process."""

    suffix = 2
    while True:
        candidate = trace_root.parent / f"{trace_root.name}_recovery{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1


def _request_chain(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    bundle = record.get("provider_trace_bundle")
    if not isinstance(bundle, Mapping):
        return []
    requests: list[dict[str, Any]] = []
    for item in bundle.get("activated_attestations", []):
        if not isinstance(item, Mapping):
            continue
        requests.append(
            {
                "local_request_id": item.get("client_request_id"),
                "payload_sha256": item.get("payload_sha256"),
                "provider_response_id": item.get("provider_response_id"),
                "returned_model": item.get("model_id"),
            }
        )
    return requests


def _query_cost(record: Mapping[str, Any]) -> dict[str, Any]:
    bundle = record.get("provider_trace_bundle")
    usage = bundle.get("usage_summary") if isinstance(bundle, Mapping) else None
    if not isinstance(usage, Mapping) or usage.get("cumulative_cost_cny") is None:
        return {}
    return {
        "currency": "CNY",
        "amount": float(usage["cumulative_cost_cny"]),
    }


def _raw_success_row(
    *,
    task: Mapping[str, Any],
    work_item: Mapping[str, Any],
    record: Mapping[str, Any],
    attempt: int,
) -> dict[str, Any]:
    requests = _request_chain(record)
    response_obtained = any(item.get("provider_response_id") for item in requests)
    return {
        "schema_version": "m3-paper-v2-adaptive-tail-query-record-1.0",
        "study_id": task["study_id"],
        "study": "adaptive-tail",
        "run_id": task["run_id"],
        "execution_identity": task["execution_identity"],
        "work_key": work_item["work_key"],
        "case_id": task["case_id"],
        "attack_family": task["attack_family"],
        "query_index": work_item["query_index"],
        "attempt": attempt,
        "sample_role": "adaptive_tail",
        "selection_condition": task["selection_condition"],
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-pro",
        "response_obtained": response_obtained,
        "provider_requests": requests,
        "unsafe_effect": bool(record.get("unsafe_effect")),
        "task_completion": bool(record.get("task_completion")),
        "operational_status": str(record.get("operational_status")),
        "guard_decision": str(record.get("initial_guard_decision", "ERROR")),
        "latency_ms": copy.deepcopy(record.get("latency_ms", {})),
        "token_usage": copy.deepcopy(record.get("token_usage", {})),
        "cost": _query_cost(record),
        "online_forbidden_fields_present": bool(
            record.get("online_visible_field_digest", {}).get(
                "forbidden_fields_present", True
            )
        ),
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "retry_eligible": not response_obtained,
        "included_in_itt": response_obtained,
        "public_record": copy.deepcopy(dict(record)),
        "recorded_at": _now(),
    }


def _raw_failure_row(
    *,
    task: Mapping[str, Any],
    work_item: Mapping[str, Any],
    attempt: int,
    exc: Exception,
    trace_root: Path,
) -> dict[str, Any]:
    trace_path = trace_root / f"{work_item['work_key']}.jsonl"
    response_obtained = False
    if trace_path.is_file():
        response_obtained = any(
            row.get("event", {}).get("event_type") == "completed"
            for row in _read_jsonl(trace_path)
            if isinstance(row.get("event"), Mapping)
        )
    return {
        "schema_version": "m3-paper-v2-adaptive-tail-query-failure-1.0",
        "study_id": task["study_id"],
        "study": "adaptive-tail",
        "run_id": task["run_id"],
        "execution_identity": task["execution_identity"],
        "work_key": work_item["work_key"],
        "case_id": task["case_id"],
        "attack_family": task["attack_family"],
        "query_index": work_item["query_index"],
        "attempt": attempt,
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-pro",
        "response_obtained": response_obtained,
        "operational_status": (
            "post_response_runner_failure"
            if response_obtained
            else "pre_response_transport_failure"
        ),
        "latency_ms": {},
        "token_usage": {},
        "cost": {"currency": "CNY", "amount": 0.0},
        "error_type": type(exc).__name__,
        "retry_eligible": not response_obtained and attempt == 1,
        "included_in_itt": response_obtained or attempt >= 2,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "recorded_at": _now(),
    }


class _TailOracle:
    def __init__(
        self,
        *,
        task: Mapping[str, Any],
        candidate: Mapping[str, Any],
        executor: Any,
        role_policy: Mapping[str, Any],
        retry_failed_work_keys: set[str],
        trace_root: Path,
    ) -> None:
        self.task = task
        self.candidate = candidate
        self.executor = executor
        self.role_policy = role_policy
        self.retry_failed_work_keys = retry_failed_work_keys
        self.trace_root = trace_root

    def __call__(self, prompt: str, query_index: int) -> OracleResult:
        if not 201 <= query_index <= 500:
            raise IncrementalAdaptiveTailError("adaptive-tail query escaped 201--500")
        work_item, state = formal_plan.build_query_work_item_and_state(
            self.candidate,
            case_id=str(self.task["case_id"]),
            query_index=query_index,
            mutated_payload=prompt,
        )
        key = str(work_item["work_key"])
        existing = _latest_raw().get(key)
        attempt = 1
        if existing is not None:
            if (
                key not in self.retry_failed_work_keys
                or not _explicit_retry_allowed(key, existing)
            ):
                raise IncrementalAdaptiveTailStop(
                    f"{key}: existing terminal row is not explicitly retryable"
                )
            attempt = int(existing["attempt"]) + 1
        try:
            result = dict(self.executor(work_item, state))
            result["admission_manifest_sha256"] = hashlib.sha256(
                MANIFEST_PATH.read_bytes()
            ).hexdigest()
            record = assemble_public_experiment_record(
                work_item,
                state,
                result,
                run_id=str(self.task["run_id"]),
                role_policy=self.role_policy,
            )
            raw = _raw_success_row(
                task=self.task,
                work_item=work_item,
                record=record,
                attempt=attempt,
            )
            _append_jsonl(RAW_PATH, raw)
            if raw["response_obtained"] is not True:
                raise IncrementalAdaptiveTailStop(
                    f"{key}: response-less result requires explicit review"
                )
            return OracleResult(
                decision=(
                    str(raw["guard_decision"])
                    if raw["guard_decision"] in {"ALLOW", "ASK", "DENY"}
                    else "ERROR"
                ),
                unsafe_effect=bool(raw["unsafe_effect"]),
                task_completed=bool(raw["task_completion"]),
                metadata={
                    "work_key": key,
                    "response_obtained": True,
                },
            )
        except IncrementalAdaptiveTailStop:
            raise
        except Exception as exc:
            failure = _raw_failure_row(
                task=self.task,
                work_item=work_item,
                attempt=attempt,
                exc=exc,
                trace_root=self.trace_root,
            )
            _append_jsonl(RAW_PATH, failure)
            _append_jsonl(FAILURE_PATH, failure)
            raise IncrementalAdaptiveTailStop(str(exc)) from exc


def _policy() -> dict[str, Any]:
    from experiments.paper_v2.incremental_study_runner_v1 import (
        apply_incremental_peak_pricing,
        cumulative_spend_cny,
    )

    spent = cumulative_spend_cny()
    remaining_global = GLOBAL_FUSE_CNY - float(spent["global"])
    limit = min(REGULAR_FUSES_CNY["adaptive"], remaining_global)
    if limit <= 0:
        raise IncrementalAdaptiveTailError("adaptive/global CNY fuse is exhausted")
    policy = apply_incremental_peak_pricing(
        build_role_policy(load_public_policy(), "primary"),
        "deepseek-v4-pro",
    )
    policy["deepseek"]["hard_spend_limit_cny"] = limit
    policy["deepseek"]["abort_ceiling_cny"] = limit
    policy["deepseek"]["abort_at_fraction"] = 1.0
    policy["deepseek"]["untouched_reserve_cny"] = 0.0
    policy["common_controls"]["automatic_retries"] = 0
    policy["common_controls"]["canary_concurrency"] = 1
    return policy


def _permit(
    *,
    plan_rows: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    tracker_trace_root: Path,
) -> canary_controller.AdaptiveExecutionPermit:
    return canary_controller.AdaptiveExecutionPermit(
        run_id=str(candidate["scope"]["run_id"]),
        execution_identity=str(candidate["execution_identity"]),
        tasks=tuple(copy.deepcopy(dict(row)) for row in plan_rows),
        known_work_keys=frozenset(_known_query_keys(plan_rows)),
        output_root=OUTPUT_ROOT,
        query_ledger_path=OUTPUT_ROOT / "internal/unused_query_ledger.jsonl",
        budget_ledger_path=BUDGET_PATH,
        trace_root=tracker_trace_root,
        checkpoint_root=CHECKPOINT_ROOT,
        admission_file_sha256=hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        candidate=candidate,
        admission={"status": "user_approved_incremental_plan"},
    )


def evaluate_canary_gate() -> dict[str, Any]:
    tasks = [row for row in load_tail_plan() if int(row["formal_prefix_query_count"]) == 5]
    latest = _latest_raw()
    checks: list[bool] = []
    observed = 0
    for task in tasks:
        checkpoint = _read_checkpoint(CHECKPOINT_ROOT / f"{task['case_id']}.json")
        queries = checkpoint.get("queries", [])
        new_count = max(0, len(queries) - 200)
        expected = min(CANARY_NEW_QUERIES, new_count)
        task_rows = [
            latest.get(formal_plan.adaptive_query_work_key(str(task["case_id"]), index))
            for index in range(201, 201 + expected)
        ]
        actual = [row for row in task_rows if isinstance(row, Mapping)]
        observed += len(actual)
        checks.append(
            bool(actual)
            and len(actual) == expected
            and all(
                row.get("response_obtained") is True
                and row.get("online_forbidden_fields_present") is False
                and row.get("provider_tools_enabled") is False
                and row.get("external_effects_enabled") is False
                and row.get("operational_status") == "completed"
                and row.get("provider_requests")
                and all(
                    request.get("local_request_id")
                    and request.get("payload_sha256")
                    and request.get("provider_response_id")
                    and request.get("returned_model") == "deepseek-v4-pro"
                    for request in row["provider_requests"]
                )
                for row in actual
            )
        )
    passed = len(tasks) == 2 and len(checks) == 2 and all(checks)
    value = {
        "schema_version": "m3-paper-v2-adaptive-tail-canary-gate-1.0",
        "study": "adaptive-tail",
        "gate_passed": passed,
        "status": "passed" if passed else "failed",
        "planned_tasks": 2,
        "planned_new_queries_per_task": CANARY_NEW_QUERIES,
        "observed_query_rows": observed,
        "exact_returned_model": passed,
        "complete_request_chain": passed,
        "online_field_isolation": passed,
        "provider_tools_and_external_effects_zero": passed,
        "scientific_outcomes_inspected": False,
    }
    _write_json(CANARY_GATE_PATH, value)
    return value


def _require_canary() -> dict[str, Any]:
    if not CANARY_GATE_PATH.is_file():
        raise IncrementalAdaptiveTailError("adaptive-tail canary gate is missing")
    gate = evaluate_canary_gate()
    if gate["gate_passed"] is not True:
        raise IncrementalAdaptiveTailError("adaptive-tail canary gate did not pass")
    return gate


def run_adaptive_tail(
    *,
    canary_only: bool,
    config_path: Path | None,
    retry_failed_work_keys: Sequence[str] = (),
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    executor_factory: Callable[..., Any] = canary_controller._build_executor,
) -> dict[str, Any]:
    rows = load_tail_plan()
    selected = (
        [row for row in rows if int(row["formal_prefix_query_count"]) == 5]
        if canary_only
        else rows
    )
    if not canary_only:
        _require_canary()
    candidate = build_runtime_candidate(rows)
    checkpoint_state = prepare_checkpoints(selected)
    latest = _latest_raw()
    retry_set = set(retry_failed_work_keys)
    unknown_retries = retry_set - _known_query_keys(rows)
    if unknown_retries:
        raise IncrementalAdaptiveTailError("adaptive retry key is outside E5")
    for key in retry_set:
        prior = latest.get(key)
        if prior is None or not _explicit_retry_allowed(key, prior):
            raise IncrementalAdaptiveTailError("adaptive retry is not response-less")

    pending = []
    for task in selected:
        checkpoint = _read_checkpoint(CHECKPOINT_ROOT / f"{task['case_id']}.json")
        count = len(checkpoint.get("queries", []))
        if checkpoint.get("first_success_query") is None and count < (
            205 if canary_only else 500
        ):
            pending.append(task)
    if not pending:
        gate = evaluate_canary_gate() if canary_only else _require_canary()
        return {
            "status": "nothing_pending",
            "study": "adaptive-tail",
            "tasks_selected": len(selected),
            "tasks_executed": 0,
            "canary_gate_passed": bool(gate["gate_passed"]),
            "checkpoint_state": checkpoint_state,
        }

    policy = _policy()
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    runtime_values = dict(values)
    runtime_values["FRONTIER_DEEPSEEK_MODEL_ID"] = "deepseek-v4-pro"
    api_key = _deepseek_api_key(runtime_values, policy)
    process_trace_root = _fresh_recovery_trace_root() if retry_set else TRACE_ROOT
    permit = _permit(
        plan_rows=rows,
        candidate=candidate,
        tracker_trace_root=process_trace_root,
    )
    tracker = IncrementalPublicBudgetTracker(
        BUDGET_PATH,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    executor = executor_factory(
        replace(permit, trace_root=process_trace_root),
        tracker,
        api_key=api_key,
        role_policy=policy,
    )
    tasks_executed = 0
    stop_reason: str | None = None
    for task in pending:
        record = _source_record(task)
        checkpoint_path = CHECKPOINT_ROOT / f"{task['case_id']}.json"
        search = AdaptiveMCTSSearch(
            task_id=str(task["case_id"]),
            base_payload=str(record["untrusted_content"]),
            oracle=_TailOracle(
                task=task,
                candidate=candidate,
                executor=executor,
                role_policy=policy,
                retry_failed_work_keys=retry_set,
                trace_root=process_trace_root,
            ),
            seed=ADAPTIVE_SEED,
            checkpoint_path=checkpoint_path,
        )
        target = 205 if canary_only else 500
        try:
            search.run(query_budgets=(target,), stop_on_success=True)
        except IncrementalAdaptiveTailStop as exc:
            stop_reason = str(exc)
            break
        tasks_executed += 1

    _write_json(
        COST_SUMMARY_PATH,
        {
            "schema_version": "m3-paper-v2-adaptive-tail-cost-summary-1.0",
            "cost_cny": tracker.status["role_cumulative_cost_cny"],
            "provider_call_count": tracker.status["event_count"],
            "hard_limit_cny": policy["deepseek"]["hard_spend_limit_cny"],
            "automatic_retries": 0,
            "recorded_at": _now(),
        },
    )
    gate = evaluate_canary_gate() if canary_only else _require_canary()
    return {
        "status": "paused" if stop_reason else "stage_complete",
        "study": "adaptive-tail",
        "tasks_selected": len(selected),
        "tasks_executed": tasks_executed,
        "stop_reason": stop_reason,
        "new_query_rows": len(_read_jsonl(RAW_PATH)),
        "cumulative_cost_cny": tracker.status["role_cumulative_cost_cny"],
        "canary_gate_passed": bool(gate["gate_passed"]),
        "checkpoint_state": checkpoint_state,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "automatic_retries": 0,
    }


__all__ = [
    "IncrementalAdaptiveTailError",
    "build_runtime_candidate",
    "evaluate_canary_gate",
    "load_tail_plan",
    "prepare_checkpoints",
    "run_adaptive_tail",
]
