"""Admission-gated DeepSeek Pro bridge for the adaptive 8x50 cost canary.

This controller is inert unless a separate hash-bound admission exists.  It
maps each MCTS mutation to the frozen M3 ``untrusted_content`` field, executes
M3-full in the isolated sandbox, and binds every adaptive query to zero or more
official provider calls through independent append-only ledgers.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v2 as medium_v2
from experiments.paper_v1.adaptive_attack import OracleResult
from experiments.paper_v2.adaptive_cost_canary_plan_v1 import (
    MAX_QUERIES,
    MODEL_ID,
    QUERY_BUDGET,
    RUN_ID,
    all_query_work_keys,
    build_query_work_item_and_state,
    resolve_candidate_task,
    verify_candidate,
)
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    AdaptiveQueryLedger,
    cross_bind_query_and_call_ledgers,
    validate_query_events,
)
from experiments.paper_v2.adaptive_runner import run_task_budget
from experiments.paper_v2.boundary_rejection_runtime_v3 import (
    BoundaryAwareM3EffectBackendV3,
    BoundaryAwareM3OutcomeEvaluatorV3,
    TrustedContextBoundaryRuntimeV3,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    CONDITION_PROFILES,
    ConditionExecutorShell,
    OnlineExecutorContext,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    M3SandboxEffectBackend,
)
from experiments.paper_v2.m3_offline_evaluator import M3CaseBinding
from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
)
from experiments.paper_v2.provider_live_qualification import (
    CONSENT_VALUE,
    PROVIDER_CONFIG,
)
from experiments.paper_v2.public_deepseek_client_v1 import (
    PublicDeepSeekJsonOfficialClient,
)
from experiments.paper_v2.public_execution_store_v1 import (
    PublicBudgetClient,
    PublicBudgetTracker,
    assemble_public_experiment_record,
    validate_public_budget_events,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicProviderBudgetState,
    build_role_policy,
    load_public_policy,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    PublicDeepSeekJsonTracedProviderClient,
)
from experiments.paper_v2.trusted_context_runtime_v2 import (
    TracedClientRegistry,
)
from m3_core.project_config import (
    is_placeholder,
    parse_env_file,
    resolve_config_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/adaptive_cost_canary_admission_v1.schema.json"
)
DEFAULT_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "adaptive_cost_canary_admission_v1.json"
)
SCHEMA_VERSION = "m3-paper-v2-adaptive-cost-canary-admission-1.0"
ADMISSION_STATUS = "activated_for_adaptive_cost_canary_only"
TECHNICAL_REVIEW_NAME = "technical_cost_review_v1.json"
MAX_TOKENS = 512
TIMEOUT_SECONDS = 120.0
ADAPTIVE_SEED = 20260723


class AdaptiveCostCanaryControllerError(ValueError):
    """Raised when the adaptive canary crosses a frozen boundary."""


class AdaptiveCanaryStop(RuntimeError):
    """Internal clean stop after a terminal diagnostic or budget pause."""


@dataclass(frozen=True)
class AdaptiveExecutionPermit:
    run_id: str
    execution_identity: str
    tasks: tuple[dict[str, Any], ...]
    known_work_keys: frozenset[str]
    output_root: Path
    query_ledger_path: Path
    budget_ledger_path: Path
    trace_root: Path
    checkpoint_root: Path
    admission_file_sha256: str
    candidate: Mapping[str, Any]
    admission: Mapping[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdaptiveCostCanaryControllerError(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_canary_command() -> str:
    admission = DEFAULT_ADMISSION.relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.adaptive_cost_canary_controller_v1 "
        f"--execute-canary --admission {admission} "
        "--config config\\project.local.env"
    )


def adaptive_role_policy() -> dict[str, Any]:
    """Project the public Pro price into an independent CNY 5 fuse."""

    policy = build_role_policy(load_public_policy(), "primary")
    policy["deepseek"]["hard_spend_limit_cny"] = 5.0
    policy["deepseek"]["abort_at_fraction"] = 1.0
    policy["deepseek"]["abort_ceiling_cny"] = 5.0
    policy["deepseek"]["untouched_reserve_cny"] = 0.0
    policy["common_controls"]["canary_concurrency"] = 1
    policy["common_controls"]["automatic_retries"] = 0
    return policy


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
        raise AdaptiveCostCanaryControllerError(
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
        "model_id": MODEL_ID,
        "task_count": candidate["scope"]["task_count"],
        "query_budget_per_task": QUERY_BUDGET,
        "maximum_queries": MAX_QUERIES,
        "maximum_provider_calls": candidate["scope"][
            "maximum_provider_calls"
        ],
        "hard_limit_cny": 5.0,
        "output_root": candidate["scope"]["output_root"],
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(
            command.encode()
        ).hexdigest(),
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "adaptive_cost_canary_execution_authorization",
        "approved_at": approved_at,
        "status": ADMISSION_STATUS,
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
            "prompt_or_response_content_stored_in_provider_trace": False,
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_canary_admission(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    schema = _load_json(DEFAULT_SCHEMA)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(dict(value))
    candidate = verify_candidate()
    expected_scope = build_canary_admission(
        owner_statement_sha256=str(
            value["authorization"]["owner_statement_sha256"]
        ),
        approved_at=str(value["approved_at"]),
    )["scope"]
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("status") != ADMISSION_STATUS
        or value.get("scope") != expected_scope
        or value.get("scope_sha256")
        != sha256_canonical_json(value["scope"])
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or value["authorization"]["candidate_scope_sha256"]
        != candidate["scope_sha256"]
        or value["authorization"]["canary_execution_authorized"] is not True
        or value["authorization"]["formal_continuation_authorized"] is not False
        or value["authorization"]["result_admission_authorized"] is not False
    ):
        raise AdaptiveCostCanaryControllerError(
            "adaptive canary admission digest/scope drift"
        )
    return copy.deepcopy(dict(value))


def authorize_canary(
    *,
    admission_path: Path,
) -> AdaptiveExecutionPermit:
    if admission_path.resolve() != DEFAULT_ADMISSION.resolve():
        raise AdaptiveCostCanaryControllerError(
            "adaptive canary admission path is not frozen"
        )
    admission = validate_canary_admission(_load_json(admission_path))
    candidate = verify_candidate()
    output_root = PROJECT_ROOT / str(candidate["scope"]["output_root"])
    tasks = tuple(
        copy.deepcopy(dict(task)) for task in candidate["scope"]["tasks"]
    )
    freeze_tasks = [
        {
            "case_id": task["case_id"],
        }
        for task in tasks
    ]
    keys = frozenset(
        all_query_work_keys(freeze_tasks)
    )
    if len(keys) != MAX_QUERIES:
        raise AdaptiveCostCanaryControllerError(
            "adaptive query work-key cardinality drift"
        )
    return AdaptiveExecutionPermit(
        run_id=RUN_ID,
        execution_identity=str(candidate["execution_identity"]),
        tasks=tasks,
        known_work_keys=keys,
        output_root=output_root,
        query_ledger_path=output_root / "query_ledger.jsonl",
        budget_ledger_path=output_root / "provider_budget_ledger.jsonl",
        trace_root=output_root / "provider_traces",
        checkpoint_root=output_root / "search_checkpoints",
        admission_file_sha256=_sha256_file(admission_path),
        candidate=candidate,
        admission=admission,
    )


class AdaptiveM3CaseResolver:
    """Resolve evaluator labels by frozen case id after online execution."""

    def __init__(self, candidate: Mapping[str, Any]) -> None:
        self.candidate = copy.deepcopy(dict(candidate))
        self._known = {
            str(task["case_id"])
            for task in candidate["scope"]["tasks"]
        }

    def resolve(self, work_key: str) -> M3CaseBinding:
        parts = str(work_key).split("__")
        if (
            len(parts) != 3
            or parts[0] != "adaptive-cost-v1"
            or parts[1] not in self._known
            or not parts[2].startswith("q")
        ):
            raise AdaptiveCostCanaryControllerError(
                "unknown adaptive evaluator work key"
            )
        case_id = parts[1]
        task, record = resolve_candidate_task(self.candidate, case_id)
        offline = record.get("offline_evaluation")
        if not isinstance(offline, Mapping) or offline.get(
            "offline_only"
        ) is not True:
            raise AdaptiveCostCanaryControllerError(
                "adaptive evaluator labels are missing"
            )
        return M3CaseBinding(
            work_key=work_key,
            execution_identity=str(self.candidate["execution_identity"]),
            selection_id=case_id,
            case_id=case_id,
            source_record_sha256=str(task["source_record_sha256"]),
            sample_type=str(record["sample_type"]),
            offline_evaluation=offline,
        )


def _validate_runtime_config(
    values: Mapping[str, str],
    *,
    role_policy: Mapping[str, Any],
) -> str:
    fields = PROVIDER_CONFIG["deepseek"]
    if values.get("M3_FRONTIER_API_CONSENT") != CONSENT_VALUE:
        raise AdaptiveCostCanaryControllerError(
            "explicit local network consent is missing"
        )
    if is_placeholder(values.get(fields["api_key"])):
        raise AdaptiveCostCanaryControllerError(
            "DeepSeek API key is missing or a placeholder"
        )
    if str(values.get(fields["base_url"], "")).rstrip("/") != str(
        role_policy["deepseek"]["base_url"]
    ).rstrip("/"):
        raise AdaptiveCostCanaryControllerError(
            "DeepSeek base URL differs from the adaptive policy"
        )
    if str(values.get(fields["model_id"], "")) != MODEL_ID:
        raise AdaptiveCostCanaryControllerError(
            "DeepSeek adaptive model identity drift"
        )
    return str(values[fields["api_key"]])


def _build_executor(
    permit: AdaptiveExecutionPermit,
    tracker: PublicBudgetTracker,
    *,
    api_key: str,
    role_policy: Mapping[str, Any],
    recorded_at: Callable[[], str] = _now,
    client_factory: Callable[..., Any] = (
        PublicDeepSeekJsonOfficialClient
    ),
    receipt_adapter: (
        Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
    ) = None,
) -> ConditionExecutorShell:
    registry = TracedClientRegistry()

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> PublicDeepSeekJsonTracedProviderClient:
        client = client_factory(
            provider_id="deepseek",
            api_key=api_key,
            content_class="synthetic_m3_case",
            budget_state=PublicProviderBudgetState(
                "deepseek",
                role_policy,
            ),
            policy=role_policy,
            model_role="primary",
            temperature=0.0,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT_SECONDS,
            network_consent=True,
        )
        budget_client = PublicBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
            recorded_at=recorded_at,
        )
        traced = PublicDeepSeekJsonTracedProviderClient(
            budget_client,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=permit.trace_root / f"{context.work_key}.jsonl",
            recorded_at=recorded_at,
            receipt_adapter=receipt_adapter,
        )
        return registry.register(context.work_key, traced)

    def backend_factory(
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> BoundaryAwareM3EffectBackendV3:
        del tool_schemas
        return BoundaryAwareM3EffectBackendV3(
            M3SandboxEffectBackend(context)
        )

    runtime = TrustedContextBoundaryRuntimeV3(
        LiveConditionRuntime(
            provider_client_factory=provider_factory,
            effect_backend_factory=backend_factory,
            recorded_at=recorded_at,
        ),
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    resolver = AdaptiveM3CaseResolver(permit.candidate)
    return ConditionExecutorShell(
        profile=CONDITION_PROFILES["m3_full"],
        runtime=medium_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=medium_v2.FailureAwareOutcomeEvaluator(
            BoundaryAwareM3OutcomeEvaluatorV3(resolver)
        ),
    )


class _AdaptiveOfficialOracle:
    def __init__(
        self,
        *,
        permit: AdaptiveExecutionPermit,
        case_id: str,
        executor: ConditionExecutorShell,
        query_ledger: AdaptiveQueryLedger,
        tracker: PublicBudgetTracker,
        role_policy: Mapping[str, Any],
        recorded_at: Callable[[], str] = _now,
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
            raise AdaptiveCanaryStop(self.stop_reason)
        self.tracker.assert_before_request()
        work_item, state = build_query_work_item_and_state(
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
        decision = (
            "ERROR"
            if record["result_tier"] == "diagnostic"
            else str(record["effective_guard_decision"])
        )
        return OracleResult(
            decision=decision,
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


def _load_budget_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            raise AdaptiveCostCanaryControllerError(
                f"{path}:{number}: blank budget row"
            )
        value = json.loads(line)
        if not isinstance(value, dict):
            raise AdaptiveCostCanaryControllerError(
                f"{path}:{number}: expected an object"
            )
        rows.append(value)
    return rows


def execute_cost_canary(
    *,
    admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    executor_factory: Callable[..., ConditionExecutorShell] = _build_executor,
) -> dict[str, Any]:
    permit = authorize_canary(admission_path=admission_path)
    role_policy = adaptive_role_policy()
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    api_key = _validate_runtime_config(values, role_policy=role_policy)
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
    if query_ledger.status["open_query_work_keys"]:
        raise AdaptiveCostCanaryControllerError(
            "open adaptive query requires manual review before resumption"
        )
    executor = executor_factory(
        permit,
        tracker,
        api_key=api_key,
        role_policy=role_policy,
    )
    tasks_completed_this_process = 0
    stop_reason: str | None = None
    for task in permit.tasks:
        case_id = str(task["case_id"])
        _, record = resolve_candidate_task(permit.candidate, case_id)
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        oracle = _AdaptiveOfficialOracle(
            permit=permit,
            case_id=case_id,
            executor=executor,
            query_ledger=query_ledger,
            tracker=tracker,
            role_policy=role_policy,
        )
        try:
            summary = run_task_budget(
                task_id=case_id,
                base_payload=str(record["untrusted_content"]),
                oracle=oracle,
                budget=QUERY_BUDGET,
                checkpoint_path=checkpoint,
                seed=ADAPTIVE_SEED,
            )
        except (AdaptiveCanaryStop, ProviderPausedError) as exc:
            stop_reason = str(exc)
            break
        if summary["budget_completed"] is not True:
            raise AdaptiveCostCanaryControllerError(
                "adaptive task did not reach success or its query budget"
            )
        tasks_completed_this_process += 1
        if oracle.stop_reason is not None:
            stop_reason = oracle.stop_reason
            break
    budget_events = _load_budget_events(permit.budget_ledger_path)
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
            if stop_reason is None
            and tasks_completed_this_process == len(permit.tasks)
            else "adaptive_cost_canary_paused"
        ),
        "run_id": permit.run_id,
        "model_id": MODEL_ID,
        "tasks_completed_this_process": tasks_completed_this_process,
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
    }


def build_technical_review(
    *,
    admission_path: Path,
) -> dict[str, Any]:
    """Review query/call integrity and cost without reporting outcomes."""

    permit = authorize_canary(admission_path=admission_path)
    role_policy = adaptive_role_policy()
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
    budget_events = _load_budget_events(permit.budget_ledger_path)
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
        raise AdaptiveCostCanaryControllerError(
            "adaptive technical review found an open query"
        )
    if query_status["terminal_query_count"] > MAX_QUERIES:
        raise AdaptiveCostCanaryControllerError(
            "adaptive technical review exceeded 400 queries"
        )
    if budget_status["role_cumulative_cost_cny"] > 5.0:
        raise AdaptiveCostCanaryControllerError(
            "adaptive technical review exceeded CNY 5"
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
            raise AdaptiveCostCanaryControllerError(
                "adaptive checkpoint queries are missing"
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
            raise AdaptiveCostCanaryControllerError(
                "adaptive checkpoint/query ledger drift"
            )
        complete = (
            value.get("first_success_query") is not None
            or len(queries) == QUERY_BUDGET
        )
        if complete:
            task_complete_count += 1
        checkpoint_query_total += len(queries)
    if checkpoint_query_total != query_status["terminal_query_count"]:
        raise AdaptiveCostCanaryControllerError(
            "adaptive checkpoint/query total drift"
        )
    passed = (
        task_complete_count == len(permit.tasks)
        and query_status["diagnostic_query_count"] == 0
        and query_status["terminal_query_count"] > 0
        and budget_status["event_count"]
        == query_status["completed_provider_call_count"]
    )
    core = {
        "schema_version": "m3-paper-v2-adaptive-technical-cost-review-1.0",
        "artifact_role": "outcome_blind_adaptive_cost_review",
        "reviewed_at": _now(),
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "admission_file_sha256": permit.admission_file_sha256,
        "technical_gate_passed": passed,
        "task_execution_complete_count": task_complete_count,
        "expected_task_count": len(permit.tasks),
        "terminal_query_count": query_status["terminal_query_count"],
        "maximum_queries": MAX_QUERIES,
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "query_to_call_ratio": (
            round(
                query_status["completed_provider_call_count"]
                / query_status["terminal_query_count"],
                6,
            )
            if query_status["terminal_query_count"]
            else None
        ),
        "cumulative_cost_cny": budget_status[
            "role_cumulative_cost_cny"
        ],
        "hard_limit_cny": 5.0,
        "query_ledger_tail_sha256": query_status["tail_sha256"],
        "budget_ledger_tail_sha256": budget_status["tail_sha256"],
        "query_call_cross_binding_complete": True,
        "scientific_outcomes_aggregated": False,
        "scientific_result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-candidate", action="store_true")
    parser.add_argument("--execute-canary", action="store_true")
    parser.add_argument("--technical-review", action="store_true")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    selected = sum(
        (
            bool(args.verify_candidate),
            bool(args.execute_canary),
            bool(args.technical_review),
        )
    )
    if selected != 1:
        parser.error("select exactly one controller action")
    if args.verify_candidate:
        value = verify_candidate()
    else:
        if args.admission is None:
            parser.error("--admission is required")
        if args.execute_canary:
            value = execute_cost_canary(
                admission_path=args.admission,
                config_path=args.config,
            )
        else:
            value = build_technical_review(
                admission_path=args.admission,
            )
            output = (
                args.output
                or (
                    PROJECT_ROOT
                    / str(
                        verify_candidate()["scope"]["output_root"]
                    )
                    / TECHNICAL_REVIEW_NAME
                )
            )
            _write_json(output, value)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AdaptiveCostCanaryControllerError",
    "AdaptiveExecutionPermit",
    "AdaptiveM3CaseResolver",
    "adaptive_role_policy",
    "authorize_canary",
    "build_canary_admission",
    "build_technical_review",
    "canonical_canary_command",
    "execute_cost_canary",
    "validate_canary_admission",
]
