"""具备决策字段显式记录的全新自适应成本金丝雀恢复控制器。

修正了记录字段缺失问题，在重放和恢复执行中完整捕获防护判定决策流与中间审计事件。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.adaptive_cost_canary_abort_review_v1 as abort_v1
import experiments.paper_v2.adaptive_cost_canary_controller_v1 as canary_v1
import experiments.paper_v2.adaptive_cost_canary_plan_v1 as plan_v1
from experiments.paper_v1.adaptive_attack import OracleResult
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    AdaptiveQueryLedger,
    cross_bind_query_and_call_ledgers,
    validate_query_events,
)
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.formal_condition_executors import (
    ConditionExecutorShell,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
)
from experiments.paper_v2.public_execution_store_v1 import (
    PublicBudgetTracker,
    assemble_public_experiment_record,
    validate_public_budget_events,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
SCHEMA_ROOT = PROJECT_ROOT / "schemas/paper_v2"
CANDIDATE_PATH = PROTOCOL_ROOT / "adaptive_cost_canary_candidate_v2.json"
ADMISSION_PATH = (
    PROTOCOL_ROOT
    / "admissions/adaptive_cost_canary_admission_v2.json"
)
CANDIDATE_SCHEMA = (
    SCHEMA_ROOT / "adaptive_cost_canary_candidate_v2.schema.json"
)
ADMISSION_SCHEMA = (
    SCHEMA_ROOT / "adaptive_cost_canary_admission_v2.schema.json"
)
CANDIDATE_SCHEMA_VERSION = (
    "m3-paper-v2-adaptive-cost-canary-candidate-2.0"
)
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-adaptive-cost-canary-admission-2.0"
)
RUN_ID = "adaptive-cost-canary-primary-v2"
OUTPUT_ROOT = (
    "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary"
)
GENERATED_AT = "2026-07-30T02:00:00+08:00"
TECHNICAL_REVIEW_NAME = "technical_cost_review_v2.json"


class AdaptiveCostCanaryV2Error(ValueError):
    """当自适应-v2 无法保持其全新的恢复边界时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdaptiveCostCanaryV2Error(f"{path}: expected an object")
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


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveCostCanaryV2Error(
            f"missing adaptive-v2 artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def _candidate_artifact_paths() -> list[Path]:
    return [
        Path(__file__),
        CANDIDATE_SCHEMA,
        ADMISSION_SCHEMA,
        plan_v1.DEFAULT_CANDIDATE,
        abort_v1.DEFAULT_OUTPUT,
        PROJECT_ROOT
        / "experiments/paper_v2/adaptive_cost_canary_controller_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/adaptive_cost_canary_plan_v1.py",
        PROJECT_ROOT / "experiments/paper_v2/adaptive_query_ledger_v1.py",
    ]


def build_candidate() -> dict[str, Any]:
    source = plan_v1.verify_candidate()
    abort = abort_v1.verify_abort_review()
    locks = [_lock(path) for path in _candidate_artifact_paths()]
    identity = sha256_canonical_json(
        {
            "schema_version": (
                "m3-paper-v2-adaptive-cost-canary-identity-2.0"
            ),
            "source_candidate_manifest_sha256": source[
                "manifest_sha256"
            ],
            "source_abort_review_manifest_sha256": abort[
                "manifest_sha256"
            ],
            "controller_sha256": locks[0]["sha256"],
            "run_id": RUN_ID,
            "output_root": OUTPUT_ROOT,
            "old_query_records_reused": False,
        }
    )
    source_scope = copy.deepcopy(source["scope"])
    scope = {
        **source_scope,
        "run_id": RUN_ID,
        "execution_identity": identity,
        "output_root": OUTPUT_ROOT,
        "plan_version": (
            "m3-paper-v2-adaptive-cost-canary-recovery-plan-2.0"
        ),
        "recovery": {
            "source_v1_candidate_manifest_sha256": source[
                "manifest_sha256"
            ],
            "source_v1_abort_review_manifest_sha256": abort[
                "manifest_sha256"
            ],
            "fresh_run_identity": True,
            "fresh_execution_identity": True,
            "fresh_output_root": True,
            "old_v1_query_records_reused": False,
            "decision_field": "initial_guard_decision",
        },
        "budget": {
            "fresh_hard_limit_cny": 5.0,
            "prior_failed_cost_cny": abort["operational_summary"][
                "role_cumulative_cost_cny"
            ],
            "projected_adaptive_total_ceiling_cny": round(
                5.0
                + float(
                    abort["operational_summary"][
                        "role_cumulative_cost_cny"
                    ]
                ),
                7,
            ),
        },
    }
    core = {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "artifact_role": "fresh_adaptive_recovery_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_execution_not_authorized",
        "execution_identity": identity,
        "scope": scope,
        "artifact_locks": locks,
        "authorization": {
            "candidate_only": True,
            "canary_execution_authorized": False,
            "formal_continuation_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "provider_calls_while_building": 0,
            "scientific_outcomes_accessed": False,
            "formal_results_created": 0,
            "old_v1_query_records_reused": False,
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return validate_candidate(value)


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 candidate must be an object"
        )
    Draft202012Validator(
        _load_json(CANDIDATE_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if (
        value["scope_sha256"]
        != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"] != _manifest_sha(value)
        or value["scope"]["execution_identity"]
        != value["execution_identity"]
        or value["scope"]["run_id"] != RUN_ID
        or value["scope"]["output_root"] != OUTPUT_ROOT
        or value["scope"]["recovery"]["old_v1_query_records_reused"]
        is not False
    ):
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 candidate identity/digest drift"
        )
    locks = value["artifact_locks"]
    if len({item["path"] for item in locks}) != len(locks):
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 candidate has duplicate locks"
        )
    for item in locks:
        path = (PROJECT_ROOT / str(item["path"])).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise AdaptiveCostCanaryV2Error(
                "adaptive-v2 artifact lock escapes project"
            ) from exc
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise AdaptiveCostCanaryV2Error(
                f"adaptive-v2 artifact lock drift: {item['path']}"
            )
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    observed = validate_candidate(_load_json(CANDIDATE_PATH))
    expected = build_candidate()
    if observed != expected:
        raise AdaptiveCostCanaryV2Error("adaptive-v2 candidate drift")
    return observed


def canonical_canary_command() -> str:
    admission = ADMISSION_PATH.relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.adaptive_cost_canary_controller_v2 "
        f"--execute-canary --admission {admission} "
        "--config config\\project.local.env"
    )


def build_canary_admission(
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    if (
        len(owner_statement_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in owner_statement_sha256
        )
    ):
        raise AdaptiveCostCanaryV2Error(
            "owner statement digest must be lowercase SHA-256"
        )
    candidate = verify_candidate()
    command = canonical_canary_command()
    scope = {
        "run_id": RUN_ID,
        "execution_identity": candidate["execution_identity"],
        "provider_id": "deepseek",
        "endpoint_type": "official_api",
        "model_role": "primary",
        "model_id": plan_v1.MODEL_ID,
        "task_count": plan_v1.TASK_COUNT,
        "query_budget_per_task": plan_v1.QUERY_BUDGET,
        "maximum_queries": plan_v1.MAX_QUERIES,
        "maximum_provider_calls": candidate["scope"][
            "maximum_provider_calls"
        ],
        "hard_limit_cny": 5.0,
        "output_root": OUTPUT_ROOT,
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(
            command.encode("utf-8")
        ).hexdigest(),
    }
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "adaptive_cost_canary_execution_authorization",
        "approved_at": approved_at,
        "status": "activated_for_fresh_adaptive_cost_canary_only",
        "scope": scope,
        "authorization": {
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "candidate_scope_sha256": candidate["scope_sha256"],
            "owner_statement_sha256": owner_statement_sha256,
            "canary_execution_authorized": True,
            "formal_continuation_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "technical_cost_gate_only": True,
            "scientific_outcomes_may_be_reviewed": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "old_v1_query_records_reused": False,
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_canary_admission(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 admission must be an object"
        )
    Draft202012Validator(
        _load_json(ADMISSION_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    candidate = verify_candidate()
    expected = build_canary_admission(
        owner_statement_sha256=str(
            value["authorization"]["owner_statement_sha256"]
        ),
        approved_at=str(value["approved_at"]),
    )
    if (
        dict(value) != expected
        or value["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
    ):
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 admission digest/scope drift"
        )
    return copy.deepcopy(dict(value))


def write_canary_admission(
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    value = build_canary_admission(
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(ADMISSION_PATH, value)
    return value


def authorize_canary(
    *,
    admission_path: Path,
) -> canary_v1.AdaptiveExecutionPermit:
    if admission_path.resolve() != ADMISSION_PATH.resolve():
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 admission path is not frozen"
        )
    admission = validate_canary_admission(_load_json(admission_path))
    candidate = verify_candidate()
    tasks = tuple(
        copy.deepcopy(dict(task))
        for task in candidate["scope"]["tasks"]
    )
    keys = frozenset(
        plan_v1.all_query_work_keys(
            [{"case_id": task["case_id"]} for task in tasks]
        )
    )
    if len(keys) != plan_v1.MAX_QUERIES:
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 query work-key cardinality drift"
        )
    root = PROJECT_ROOT / OUTPUT_ROOT
    return canary_v1.AdaptiveExecutionPermit(
        run_id=RUN_ID,
        execution_identity=str(candidate["execution_identity"]),
        tasks=tasks,
        known_work_keys=keys,
        output_root=root,
        query_ledger_path=root / "query_ledger.jsonl",
        budget_ledger_path=root / "provider_budget_ledger.jsonl",
        trace_root=root / "provider_traces",
        checkpoint_root=root / "search_checkpoints",
        admission_file_sha256=_sha256_file(admission_path),
        candidate=candidate,
        admission=admission,
    )


def _oracle_decision(record: Mapping[str, Any]) -> str:
    if record.get("result_tier") == "diagnostic":
        return "ERROR"
    decision = record.get("initial_guard_decision")
    if decision not in {"ALLOW", "ASK", "DENY"}:
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 record lacks a valid initial guard decision"
        )
    return str(decision)


class _AdaptiveOfficialOracleV2:
    def __init__(
        self,
        *,
        permit: canary_v1.AdaptiveExecutionPermit,
        case_id: str,
        executor: ConditionExecutorShell,
        query_ledger: AdaptiveQueryLedger,
        tracker: PublicBudgetTracker,
        role_policy: Mapping[str, Any],
        recorded_at: Callable[[], str] = canary_v1._now,
    ) -> None:
        self.permit = permit
        self.case_id = case_id
        self.executor = executor
        self.query_ledger = query_ledger
        self.tracker = tracker
        self.role_policy = role_policy
        self.recorded_at = recorded_at
        self.stop_reason: str | None = None

    def __call__(self, prompt: str, query_index: int) -> OracleResult:
        if self.stop_reason is not None:
            raise canary_v1.AdaptiveCanaryStop(self.stop_reason)
        self.tracker.assert_before_request()
        work_item, state = plan_v1.build_query_work_item_and_state(
            self.permit.candidate,
            case_id=self.case_id,
            query_index=query_index,
            mutated_payload=prompt,
        )
        prompt_sha = str(work_item["mutated_payload_sha256"])
        self.query_ledger.append_started(
            work_key=str(work_item["work_key"]),
            case_id=self.case_id,
            query_index=query_index,
            prompt_sha256=prompt_sha,
            recorded_at=self.recorded_at(),
        )
        result = dict(self.executor(work_item, state))
        result["admission_manifest_sha256"] = (
            self.permit.admission_file_sha256
        )
        record = assemble_public_experiment_record(
            work_item,
            state,
            result,
            run_id=self.permit.run_id,
            role_policy=self.role_policy,
        )
        terminal = self.query_ledger.append_terminal(
            work_key=str(work_item["work_key"]),
            case_id=self.case_id,
            query_index=query_index,
            prompt_sha256=prompt_sha,
            record=record,
            recorded_at=self.recorded_at(),
        )
        if (
            record["result_tier"] == "diagnostic"
            or self.tracker.status["paused"]
        ):
            self.stop_reason = (
                "diagnostic_query"
                if record["result_tier"] == "diagnostic"
                else "budget_pause"
            )
        return OracleResult(
            decision=_oracle_decision(record),
            unsafe_effect=bool(record.get("unsafe_effect")),
            task_completed=bool(record.get("task_completion")),
            metadata={
                "work_key_sha256": sha256_canonical_json(
                    work_item["work_key"]
                ),
                "record_sha256": terminal["record_sha256"],
                "provider_call_count": terminal["provider_call_count"],
            },
        )


def _assert_fresh_root(
    permit: canary_v1.AdaptiveExecutionPermit,
) -> None:
    paths = [
        permit.query_ledger_path,
        permit.budget_ledger_path,
    ]
    if any(path.exists() for path in paths):
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 root already started; automatic rerun is forbidden"
        )
    if (
        permit.trace_root.exists()
        and any(permit.trace_root.iterdir())
    ) or (
        permit.checkpoint_root.exists()
        and any(permit.checkpoint_root.iterdir())
    ):
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 root contains prior evidence"
        )


def execute_cost_canary(
    *,
    admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    executor_factory: Callable[..., ConditionExecutorShell] = (
        canary_v1._build_executor
    ),
) -> dict[str, Any]:
    permit = authorize_canary(admission_path=admission_path)
    _assert_fresh_root(permit)
    role_policy = canary_v1.adaptive_role_policy()
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    api_key = canary_v1._validate_runtime_config(
        values,
        role_policy=role_policy,
    )
    tracker = PublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    query_ledger = AdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    executor = executor_factory(
        permit,
        tracker,
        api_key=api_key,
        role_policy=role_policy,
    )
    completed = 0
    stop_reason: str | None = None
    for task in permit.tasks:
        case_id = str(task["case_id"])
        _, source_record = plan_v1.resolve_candidate_task(
            permit.candidate,
            case_id,
        )
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        oracle = _AdaptiveOfficialOracleV2(
            permit=permit,
            case_id=case_id,
            executor=executor,
            query_ledger=query_ledger,
            tracker=tracker,
            role_policy=role_policy,
        )
        try:
            summary = canary_v1.run_task_budget(
                task_id=case_id,
                base_payload=str(source_record["untrusted_content"]),
                oracle=oracle,
                budget=plan_v1.QUERY_BUDGET,
                checkpoint_path=checkpoint,
                seed=canary_v1.ADAPTIVE_SEED,
            )
        except (
            canary_v1.AdaptiveCanaryStop,
            ProviderPausedError,
        ) as exc:
            stop_reason = str(exc)
            break
        if summary["budget_completed"] is not True:
            raise AdaptiveCostCanaryV2Error(
                "adaptive-v2 task did not reach success or query budget"
            )
        completed += 1
        if oracle.stop_reason is not None:
            stop_reason = oracle.stop_reason
            break
    budget_events = canary_v1._load_budget_events(
        permit.budget_ledger_path
    )
    query_status = validate_query_events(
        query_ledger.events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    cross_bind_query_and_call_ledgers(
        query_events=query_ledger.events,
        budget_events=budget_events,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    return {
        "status": (
            "adaptive_cost_canary_complete_candidate_unadmitted"
            if stop_reason is None and completed == len(permit.tasks)
            else "adaptive_cost_canary_paused"
        ),
        "run_id": permit.run_id,
        "model_id": plan_v1.MODEL_ID,
        "tasks_completed_this_process": completed,
        "terminal_query_count": query_status["terminal_query_count"],
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "cumulative_cost_cny": tracker.status[
            "role_cumulative_cost_cny"
        ],
        "stop_reason": stop_reason,
        "result_admission_authorized": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "old_v1_query_records_reused": False,
    }


def build_technical_review(
    *,
    admission_path: Path,
) -> dict[str, Any]:
    permit = authorize_canary(admission_path=admission_path)
    role_policy = canary_v1.adaptive_role_policy()
    query_events = (
        []
        if not permit.query_ledger_path.exists()
        else [
            json.loads(line)
            for line in permit.query_ledger_path.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]
    )
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
    if query_status["open_query_work_keys"]:
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 technical review found an open query"
        )
    if query_status["terminal_query_count"] > plan_v1.MAX_QUERIES:
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 technical review exceeded query cap"
        )
    task_complete_count = 0
    checkpoint_query_total = 0
    terminal_by_case: dict[str, list[Mapping[str, Any]]] = {}
    for event in query_events:
        if event.get("event_type") == "terminal":
            terminal_by_case.setdefault(
                str(event["case_id"]),
                [],
            ).append(event)
    for task in permit.tasks:
        case_id = str(task["case_id"])
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        if not checkpoint.exists():
            continue
        value = _load_json(checkpoint)
        queries = value.get("queries")
        if not isinstance(queries, list):
            raise AdaptiveCostCanaryV2Error(
                "adaptive-v2 checkpoint queries are missing"
            )
        events = sorted(
            terminal_by_case.get(case_id, []),
            key=lambda event: int(event["query_index"]),
        )
        if (
            len(events) != len(queries)
            or [event["query_index"] for event in events]
            != list(range(1, len(queries) + 1))
            or any(
                event["prompt_sha256"] != query.get("prompt_sha256")
                for event, query in zip(events, queries, strict=True)
            )
        ):
            raise AdaptiveCostCanaryV2Error(
                "adaptive-v2 checkpoint/query ledger drift"
            )
        if (
            value.get("first_success_query") is not None
            or len(queries) == plan_v1.QUERY_BUDGET
        ):
            task_complete_count += 1
        checkpoint_query_total += len(queries)
    if checkpoint_query_total != query_status["terminal_query_count"]:
        raise AdaptiveCostCanaryV2Error(
            "adaptive-v2 checkpoint/query total drift"
        )
    passed = (
        task_complete_count == len(permit.tasks)
        and query_status["diagnostic_query_count"] == 0
        and query_status["terminal_query_count"] > 0
        and budget_status["event_count"]
        == query_status["completed_provider_call_count"]
        and budget_status["paused"] is False
    )
    core = {
        "schema_version": (
            "m3-paper-v2-adaptive-technical-cost-review-2.0"
        ),
        "artifact_role": "outcome_blind_adaptive_cost_review",
        "reviewed_at": canary_v1._now(),
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "admission_file_sha256": permit.admission_file_sha256,
        "technical_gate_passed": passed,
        "task_execution_complete_count": task_complete_count,
        "expected_task_count": len(permit.tasks),
        "terminal_query_count": query_status["terminal_query_count"],
        "maximum_queries": plan_v1.MAX_QUERIES,
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "cumulative_cost_cny": budget_status[
            "role_cumulative_cost_cny"
        ],
        "hard_limit_cny": 5.0,
        "query_ledger_tail_sha256": query_status["tail_sha256"],
        "budget_ledger_tail_sha256": budget_status["tail_sha256"],
        "query_call_cross_binding_complete": True,
        "old_v1_query_records_reused": False,
        "scientific_outcomes_aggregated": False,
        "scientific_result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-canary", action="store_true")
    action.add_argument("--technical-review", action="store_true")
    parser.add_argument("--admission", type=Path, default=ADMISSION_PATH)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    elif args.write_admission:
        if not args.owner_statement_sha256 or not args.approved_at:
            parser.error(
                "--write-admission requires owner digest and approved-at"
            )
        value = write_canary_admission(
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
        )
    elif args.verify_admission:
        value = validate_canary_admission(_load_json(args.admission))
    elif args.execute_canary:
        value = execute_cost_canary(
            admission_path=args.admission,
            config_path=args.config,
        )
    else:
        value = build_technical_review(admission_path=args.admission)
        output = args.output or (
            PROJECT_ROOT / OUTPUT_ROOT / TECHNICAL_REVIEW_NAME
        )
        _write_json(output, value)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
