"""共享人民币计费预算下的 20 任务分阶段 DeepSeek Flash 自适应实验控制器。

调度执行高并发 Flash 模型的自适应提示注入对抗，按任务跟踪开销与攻击成功状态。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.adaptive_cost_canary_controller_v1 as canary_v1
import experiments.paper_v2.adaptive_formal_pro_controller_v1 as pro
import experiments.paper_v2.adaptive_formal_second_plan_v1 as second_plan
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    cross_bind_query_and_call_ledgers,
)
from experiments.paper_v2.adaptive_runner import run_task_budget
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.incremental_live_ledgers_v1 import (
    IncrementalAdaptiveQueryLedger,
    IncrementalPublicBudgetTracker,
)
from experiments.paper_v2.official_provider_executor import ProviderPausedError
from m3_core.project_config import is_placeholder, parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
OUTPUT_BASE = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/adaptive_formal_second/deepseek_flash"
)
MODEL_KEY = "deepseek_flash"
MODEL_ID = "deepseek-v4-flash"
MODEL_ROLE = "second"
STAGES = {
    "flash_50": {"budget": 50, "prior": None, "hard_limit_cny": 5.0},
    "flash_200": {
        "budget": 200,
        "prior": "flash_50",
        "hard_limit_cny": 24.447195,
    },
}
TOTAL_FLASH_CEILING_CNY = sum(
    float(spec["hard_limit_cny"]) for spec in STAGES.values()
)
GENERATED_AT = "2026-08-02T02:00:54+08:00"
SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-deepseek-flash-stage-1.0"
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-adaptive-formal-deepseek-flash-admission-1.0"
)
TASK_EVENT_SCHEMA_VERSION = (
    "m3-paper-v2-adaptive-formal-deepseek-flash-task-event-1.0"
)
REVIEW_SCHEMA_VERSION = (
    "m3-paper-v2-adaptive-formal-deepseek-flash-review-1.0"
)
OWNER_APPROVAL_STATEMENT = (
    "The project owner approved the DeepSeek Flash 20-task adaptive panel at "
    "budgets 50 and 200 under the shared CNY 180 DeepSeek adaptive fuse, "
    "zero automatic retries, disabled provider tools, and isolated effects."
)
OWNER_STATEMENT_SHA256 = hashlib.sha256(
    OWNER_APPROVAL_STATEMENT.encode("utf-8")
).hexdigest()


class AdaptiveFormalDeepSeekFlashControllerV1Error(ValueError):
    """当 Flash 自适应论据边界发生漂移时抛出的异常。"""


def _technical_checks_pass(checks: Mapping[str, bool]) -> bool:
    """评估技术门禁，其所有键均为肯定性不变量。"""

    if (
        "scientific_outcomes_not_aggregated" not in checks
        or "scientific_outcomes_aggregated" in checks
        or any(not isinstance(value, bool) for value in checks.values())
    ):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "adaptive technical checks must use affirmative invariants"
        )
    return bool(checks) and all(checks.values())


class AdaptiveFlashStop(RuntimeError):
    """终端诊断查询后的正常停止异常。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stage_spec(stage: str) -> dict[str, Any]:
    try:
        return copy.deepcopy(STAGES[stage])
    except KeyError as exc:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "unknown Flash adaptive stage"
        ) from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            f"{path}: expected object"
        )
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    values: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise AdaptiveFormalDeepSeekFlashControllerV1Error(
                    f"{path}:{number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AdaptiveFormalDeepSeekFlashControllerV1Error(
                    f"{path}:{number}: expected object"
                )
            values.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            f"{path}: invalid JSONL"
        ) from exc
    return values


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            f"missing frozen input: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "artifact lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            f"artifact lock drift: {path}"
        )


def candidate_path(stage: str) -> Path:
    _stage_spec(stage)
    return PROTOCOL_ROOT / f"adaptive_formal_{stage}_candidate_v1.json"


def admission_path(stage: str) -> Path:
    _stage_spec(stage)
    return PROTOCOL_ROOT / "admissions" / f"adaptive_formal_{stage}_admission_v1.json"


def review_path(stage: str) -> Path:
    candidate = _read_json(candidate_path(stage))
    return PROJECT_ROOT / str(candidate["scope"]["output_root"]) / "technical_review_v1.json"


def _load_prior_review(stage: str) -> dict[str, Any] | None:
    prior = _stage_spec(stage)["prior"]
    if prior is None:
        return None
    review = _read_json(review_path(str(prior)))
    if (
        review.get("manifest_sha256") != _manifest_sha(review)
        or review.get("technical_gate_passed") is not True
        or review.get("stage") != prior
    ):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "prior Flash stage not admitted"
        )
    for lock in review.get("final_checkpoint_locks", []):
        _verify_lock(lock)
    return review


def _checkpoint_lock(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    queries = value.get("queries")
    if not isinstance(queries, list) or not queries:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "checkpoint lacks queries"
        )
    return {
        **_lock(path),
        "case_id": path.stem,
        "query_count": len(queries),
        "query_sequence_sha256": sha256_canonical_json(queries),
    }


def _role_policy(stage: str) -> dict[str, Any]:
    policy = canary_v1.build_role_policy(canary_v1.load_public_policy(), MODEL_ROLE)
    limit = float(_stage_spec(stage)["hard_limit_cny"])
    policy["deepseek"]["hard_spend_limit_cny"] = limit
    policy["deepseek"]["abort_at_fraction"] = 1.0
    policy["deepseek"]["abort_ceiling_cny"] = limit
    policy["deepseek"]["untouched_reserve_cny"] = 0.0
    policy["common_controls"]["canary_concurrency"] = 1
    policy["common_controls"]["automatic_retries"] = 0
    return policy


def canonical_stage_command(stage: str) -> str:
    path = admission_path(stage).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.adaptive_formal_deepseek_flash_controller_v1 "
        f"--execute-stage --stage {stage} --admission {path} "
        r"--config config\project.local.env"
    )


def build_stage_candidate(stage: str) -> dict[str, Any]:
    plan = second_plan.verify_candidate(MODEL_KEY)
    spec = _stage_spec(stage)
    prior = _load_prior_review(stage)
    tasks = copy.deepcopy(plan["scope"]["tasks"])
    sources = [] if prior is None else copy.deepcopy(prior["final_checkpoint_locks"])
    if prior is not None and len(sources) != len(tasks):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash source checkpoint count drift"
        )
    identity = sha256_canonical_json(
        {
            "schema_version": SCHEMA_VERSION,
            "plan_manifest_sha256": plan["manifest_sha256"],
            "prior_review_manifest_sha256": None
            if prior is None
            else prior["manifest_sha256"],
            "stage": stage,
            "target_budget": spec["budget"],
            "source_checkpoint_sha256": [lock["sha256"] for lock in sources],
        }
    )
    output = OUTPUT_BASE / f"{stage}-{identity}"
    if output.exists() and any(output.rglob("*")):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash stage output root is not fresh"
        )
    prefix_cost = float(
        pro.formal_plan.verify_candidate()["scope"]["formal_prefix"][
            "cumulative_cost_cny"
        ]
    )
    if round(prefix_cost + pro.TOTAL_NEW_STAGE_CEILING_CNY + TOTAL_FLASH_CEILING_CNY, 10) != 180.0:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "DeepSeek aggregate adaptive ceiling drift"
        )
    scope = {
        "stage": stage,
        "target_budget": int(spec["budget"]),
        "provider_id": "deepseek",
        "model_id": MODEL_ID,
        "model_role": MODEL_ROLE,
        "run_id": f"paper-v2-adaptive-{stage}-v1",
        "execution_identity": identity,
        "authorized_case_ids": [str(task["case_id"]) for task in tasks],
        "authorized_task_count": len(tasks),
        "source_checkpoint_count": len(sources),
        "stage_hard_limit_cny": float(spec["hard_limit_cny"]),
        "all_flash_stages_hard_ceiling_cny": TOTAL_FLASH_CEILING_CNY,
        "historical_prefix_cost_cny": prefix_cost,
        "all_pro_stages_hard_ceiling_cny": pro.TOTAL_NEW_STAGE_CEILING_CNY,
        "projected_deepseek_adaptive_ceiling_cny": 180.0,
        "output_root": _display_path(output),
        "plan_candidate_manifest_sha256": plan["manifest_sha256"],
        "prior_review_manifest_sha256": None
        if prior is None
        else prior["manifest_sha256"],
    }
    paths = [Path(__file__), second_plan.candidate_path(MODEL_KEY), Path(pro.__file__)]
    if prior is not None:
        paths.append(review_path(str(spec["prior"])))
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "single_deepseek_flash_adaptive_stage_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "tasks": tasks,
        "artifact_locks": [_lock(path) for path in paths],
        "source_checkpoint_locks": sources,
        "authorization": {
            "candidate_only": True,
            "stage_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "execution_controls": {
            "automatic_retries": 0,
            "concurrency": 1,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "first_429": "seal_current_stage",
            "terminal_query_replay_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_aggregated": False,
            "shared_mutable_state_with_pro": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_stage_candidate(value: Any, *, stage: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash stage candidate missing"
        )
    scope = value.get("scope")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("stage") != stage
        or scope.get("target_budget") != _stage_spec(stage)["budget"]
        or scope.get("model_id") != MODEL_ID
        or scope.get("authorized_task_count") != 20
        or scope.get("stage_hard_limit_cny")
        != float(_stage_spec(stage)["hard_limit_cny"])
        or scope.get("all_flash_stages_hard_ceiling_cny")
        != TOTAL_FLASH_CEILING_CNY
        or scope.get("projected_deepseek_adaptive_ceiling_cny") != 180.0
        or value.get("authorization", {}).get("stage_execution_authorized")
        is not False
        or value.get("execution_controls", {}).get("automatic_retries") != 0
    ):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash stage candidate drift"
        )
    for lock in [*value.get("artifact_locks", []), *value.get("source_checkpoint_locks", [])]:
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_stage_candidate(stage: str) -> dict[str, Any]:
    value = build_stage_candidate(stage)
    _write_json(candidate_path(stage), value)
    return value


def verify_stage_candidate(stage: str) -> dict[str, Any]:
    return validate_stage_candidate(_read_json(candidate_path(stage)), stage=stage)


def build_stage_admission(
    stage: str, *, owner_statement_sha256: str, approved_at: str
) -> dict[str, Any]:
    candidate = verify_stage_candidate(stage)
    if owner_statement_sha256 != OWNER_STATEMENT_SHA256:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "owner authorization digest drift"
        )
    command = canonical_stage_command(stage)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "one_exact_deepseek_flash_adaptive_stage_authorization",
        "approved_at": approved_at,
        "status": "activated_for_one_exact_flash_adaptive_stage",
        "stage": stage,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "owner_statement_sha256": owner_statement_sha256,
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "run_id": candidate["scope"]["run_id"],
        "execution_identity": candidate["scope"]["execution_identity"],
        "authorized_case_ids": candidate["scope"]["authorized_case_ids"],
        "authorization": {
            "stage_execution_authorized": True,
            "terminal_query_replay_authorized": False,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_stage_admission(
    stage: str, *, owner_statement_sha256: str, approved_at: str
) -> dict[str, Any]:
    value = build_stage_admission(
        stage,
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(admission_path(stage), value)
    return value


def validate_stage_admission(value: Any, *, stage: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash stage admission missing"
        )
    expected = build_stage_admission(
        stage,
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash stage admission drift"
        )
    return copy.deepcopy(dict(value))


def _runtime_plan(candidate: Mapping[str, Any]) -> dict[str, Any]:
    plan = second_plan.verify_candidate(MODEL_KEY)
    value = copy.deepcopy(plan)
    value["execution_identity"] = candidate["scope"]["execution_identity"]
    value["scope"]["execution_identity"] = candidate["scope"]["execution_identity"]
    value["scope"]["run_id"] = candidate["scope"]["run_id"]
    return value


def _permit(stage: str, selected_admission: Path) -> canary_v1.AdaptiveExecutionPermit:
    if selected_admission.resolve() != admission_path(stage).resolve():
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash admission path is not frozen"
        )
    admission = validate_stage_admission(_read_json(selected_admission), stage=stage)
    candidate = verify_stage_candidate(stage)
    runtime = _runtime_plan(candidate)
    tasks = tuple(copy.deepcopy(runtime["scope"]["tasks"]))
    keys = frozenset(second_plan.all_query_work_keys(MODEL_KEY, list(tasks)))
    output = PROJECT_ROOT / str(candidate["scope"]["output_root"])
    return canary_v1.AdaptiveExecutionPermit(
        run_id=str(candidate["scope"]["run_id"]),
        execution_identity=str(candidate["scope"]["execution_identity"]),
        tasks=tasks,
        known_work_keys=keys,
        output_root=output,
        query_ledger_path=output / "query_ledger.jsonl",
        budget_ledger_path=output / "provider_budget_ledger.jsonl",
        trace_root=output / "provider_traces",
        checkpoint_root=output / "search_checkpoints",
        admission_file_sha256=_sha256_file(selected_admission),
        candidate=runtime,
        admission=admission,
    )


def _prepare_root(
    permit: canary_v1.AdaptiveExecutionPermit,
    source_locks: Sequence[Mapping[str, Any]],
) -> None:
    if permit.output_root.exists() and any(permit.output_root.rglob("*")):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash stage already started; automatic rerun forbidden"
        )
    permit.checkpoint_root.mkdir(parents=True, exist_ok=True)
    permit.trace_root.mkdir(parents=True, exist_ok=True)
    for lock in source_locks:
        source = PROJECT_ROOT / str(lock["path"])
        destination = permit.checkpoint_root / f"{lock['case_id']}.json"
        shutil.copyfile(source, destination)
        if _sha256_file(destination) != lock["sha256"]:
            raise AdaptiveFormalDeepSeekFlashControllerV1Error(
                "Flash checkpoint copy drift"
            )


class _FlashResolver:
    def __init__(self, candidate: Mapping[str, Any]) -> None:
        self.candidate = copy.deepcopy(dict(candidate))
        self.known = {
            str(task["case_id"]) for task in candidate["scope"]["tasks"]
        }

    def resolve(self, work_key: str) -> Any:
        parts = str(work_key).split("__")
        expected_prefix = "adaptive-formal-deepseek-deepseek_v4_flash"
        if (
            len(parts) != 3
            or parts[0] != expected_prefix
            or parts[1] not in self.known
            or not parts[2].startswith("q")
        ):
            raise AdaptiveFormalDeepSeekFlashControllerV1Error(
                "unknown Flash adaptive evaluator work key"
            )
        case_id = parts[1]
        task, record = second_plan.resolve_candidate_task(self.candidate, case_id)
        offline = record.get("offline_evaluation")
        if not isinstance(offline, Mapping) or offline.get("offline_only") is not True:
            raise AdaptiveFormalDeepSeekFlashControllerV1Error(
                "Flash evaluator labels missing"
            )
        return canary_v1.M3CaseBinding(
            work_key=work_key,
            execution_identity=str(self.candidate["execution_identity"]),
            selection_id=case_id,
            case_id=case_id,
            source_record_sha256=str(task["source_record_sha256"]),
            sample_type=str(record["sample_type"]),
            offline_evaluation=offline,
        )


def _validate_runtime_config(values: Mapping[str, str], policy: Mapping[str, Any]) -> str:
    fields = canary_v1.PROVIDER_CONFIG["deepseek"]
    if values.get("M3_FRONTIER_API_CONSENT") != canary_v1.CONSENT_VALUE:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "explicit local network consent missing"
        )
    if is_placeholder(values.get(fields["api_key"])):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "DeepSeek API key missing or placeholder"
        )
    if str(values.get(fields["base_url"], "")).rstrip("/") != str(
        policy["deepseek"]["base_url"]
    ).rstrip("/"):
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "DeepSeek base URL drift"
        )
    if str(values.get(fields["model_id"], "")) != MODEL_ID:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "DeepSeek Flash model identity drift"
        )
    return str(values[fields["api_key"]])


def _build_executor(
    permit: canary_v1.AdaptiveExecutionPermit,
    tracker: IncrementalPublicBudgetTracker,
    *,
    api_key: str,
    role_policy: Mapping[str, Any],
    recorded_at: Callable[[], str] = _now,
) -> Any:
    registry = canary_v1.TracedClientRegistry()

    def provider_factory(context: Any) -> Any:
        client = canary_v1.PublicDeepSeekJsonOfficialClient(
            provider_id="deepseek",
            api_key=api_key,
            content_class="synthetic_m3_case",
            budget_state=canary_v1.PublicProviderBudgetState(
                "deepseek", role_policy
            ),
            policy=role_policy,
            model_role=MODEL_ROLE,
            temperature=0.0,
            max_tokens=canary_v1.MAX_TOKENS,
            timeout=canary_v1.TIMEOUT_SECONDS,
            network_consent=True,
        )
        budget_client = canary_v1.PublicBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
            recorded_at=recorded_at,
        )
        traced = canary_v1.PublicDeepSeekJsonTracedProviderClient(
            budget_client,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=permit.trace_root / f"{context.work_key}.jsonl",
            recorded_at=recorded_at,
        )
        return registry.register(context.work_key, traced)

    def backend_factory(context: Any, tool_schemas: Mapping[str, Any]) -> Any:
        del tool_schemas
        return canary_v1.BoundaryAwareM3EffectBackendV3(
            canary_v1.M3SandboxEffectBackend(context)
        )

    runtime = canary_v1.TrustedContextBoundaryRuntimeV3(
        canary_v1.LiveConditionRuntime(
            provider_client_factory=provider_factory,
            effect_backend_factory=backend_factory,
            recorded_at=recorded_at,
        ),
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    resolver = _FlashResolver(permit.candidate)
    return canary_v1.ConditionExecutorShell(
        profile=canary_v1.CONDITION_PROFILES["m3_full"],
        runtime=canary_v1.medium_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=canary_v1.medium_v2.FailureAwareOutcomeEvaluator(
            canary_v1.BoundaryAwareM3OutcomeEvaluatorV3(resolver)
        ),
    )


def _task_events_status(
    events: Sequence[Mapping[str, Any]],
    *,
    permit: canary_v1.AdaptiveExecutionPermit,
    stage: str,
) -> dict[str, Any]:
    known = {str(task["case_id"]) for task in permit.tasks}
    previous: str | None = None
    terminal: set[str] = set()
    for sequence, item in enumerate(events, 1):
        event = dict(item)
        core = {key: child for key, child in event.items() if key != "event_sha256"}
        case_id = str(event.get("case_id", ""))
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        if (
            event.get("schema_version") != TASK_EVENT_SCHEMA_VERSION
            or event.get("ledger_sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or event.get("run_id") != permit.run_id
            or event.get("execution_identity") != permit.execution_identity
            or event.get("stage") != stage
            or case_id not in known
            or case_id in terminal
            or event.get("terminal_class")
            not in {"search_terminal", "diagnostic_terminal"}
            or not checkpoint.is_file()
            or event.get("checkpoint_sha256") != _sha256_file(checkpoint)
            or event.get("event_sha256") != sha256_canonical_json(core)
        ):
            raise AdaptiveFormalDeepSeekFlashControllerV1Error(
                f"Flash task event {sequence} drift"
            )
        previous = str(event["event_sha256"])
        terminal.add(case_id)
    return {
        "event_count": len(events),
        "terminal_case_ids": sorted(terminal),
        "tail_sha256": previous,
    }


def _append_task_event(
    path: Path,
    *,
    permit: canary_v1.AdaptiveExecutionPermit,
    stage: str,
    case_id: str,
    terminal_class: str,
) -> None:
    events = _read_jsonl(path)
    status = _task_events_status(events, permit=permit, stage=stage)
    if case_id in status["terminal_case_ids"]:
        raise AdaptiveFormalDeepSeekFlashControllerV1Error(
            "Flash task already terminal"
        )
    checkpoint = permit.checkpoint_root / f"{case_id}.json"
    queries = _read_json(checkpoint)["queries"]
    core = {
        "schema_version": TASK_EVENT_SCHEMA_VERSION,
        "ledger_sequence": len(events) + 1,
        "previous_event_sha256": status["tail_sha256"],
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "stage": stage,
        "case_id": case_id,
        "target_budget": _stage_spec(stage)["budget"],
        "query_count": len(queries),
        "terminal_class": terminal_class,
        "checkpoint_path": _display_path(checkpoint),
        "checkpoint_sha256": _sha256_file(checkpoint),
        "recorded_at": _now(),
    }
    _append_jsonl(path, {**core, "event_sha256": sha256_canonical_json(core)})


def execute_stage(
    stage: str,
    *,
    selected_admission: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    executor_factory: Callable[..., Any] = _build_executor,
) -> dict[str, Any]:
    permit = _permit(stage, selected_admission)
    candidate = verify_stage_candidate(stage)
    _prepare_root(permit, candidate["source_checkpoint_locks"])
    policy = _role_policy(stage)
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    api_key = _validate_runtime_config(values, policy)
    tracker = IncrementalPublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role=MODEL_ROLE,
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    query_ledger = IncrementalAdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    executor = executor_factory(
        permit, tracker, api_key=api_key, role_policy=policy
    )
    target = int(candidate["scope"]["target_budget"])
    task_path = permit.output_root / "task_events_v1.jsonl"
    completed = 0
    diagnostics = 0
    stop_reason: str | None = None
    for task in permit.tasks:
        case_id = str(task["case_id"])
        _, source = second_plan.resolve_candidate_task(permit.candidate, case_id)
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        oracle = pro._AdaptiveFormalOracle(
            permit=permit,
            case_id=case_id,
            executor=executor,
            query_ledger=query_ledger,
            tracker=tracker,
            role_policy=policy,
            plan_module=second_plan,
        )
        terminal_class = "search_terminal"
        try:
            summary = run_task_budget(
                task_id=case_id,
                base_payload=str(source["untrusted_content"]),
                oracle=oracle,
                budget=target,
                checkpoint_path=checkpoint,
                seed=canary_v1.ADAPTIVE_SEED,
            )
            if summary["budget_completed"] is not True:
                raise AdaptiveFormalDeepSeekFlashControllerV1Error(
                    "Flash task is not terminal"
                )
        except (pro.AdaptiveFormalStop, AdaptiveFlashStop):
            if oracle.stop_reason != "diagnostic_query":
                raise
            terminal_class = "diagnostic_terminal"
            diagnostics += 1
        except ProviderPausedError as exc:
            stop_reason = str(exc)
            break
        _append_task_event(
            task_path,
            permit=permit,
            stage=stage,
            case_id=case_id,
            terminal_class=terminal_class,
        )
        completed += 1
    query_status = query_ledger.full_validate()
    budget_status = tracker.full_validate()
    cross_bind_query_and_call_ledgers(
        query_events=query_ledger.events,
        budget_events=tracker.events,
        trace_root=permit.trace_root,
        role_policy=policy,
    )
    task_status = _task_events_status(
        _read_jsonl(task_path), permit=permit, stage=stage
    )
    return {
        "status": (
            "adaptive_formal_flash_stage_complete_unadmitted"
            if completed == len(permit.tasks) and stop_reason is None
            else "adaptive_formal_flash_stage_paused"
        ),
        "stage": stage,
        "tasks_completed_this_process": completed,
        "expected_stage_tasks": len(permit.tasks),
        "diagnostic_tasks_this_process": diagnostics,
        "terminal_query_count_this_stage": query_status["terminal_query_count"],
        "provider_calls_this_stage": query_status["completed_provider_call_count"],
        "stage_cost_cny": budget_status["role_cumulative_cost_cny"],
        "task_event_count": task_status["event_count"],
        "stop_reason": stop_reason,
        "result_admission_authorized": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }


def build_technical_review(stage: str) -> dict[str, Any]:
    permit = _permit(stage, admission_path(stage))
    candidate = verify_stage_candidate(stage)
    policy = _role_policy(stage)
    query_ledger = IncrementalAdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    tracker = IncrementalPublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role=MODEL_ROLE,
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    query_status = query_ledger.full_validate()
    budget_status = tracker.full_validate()
    cross_bind_query_and_call_ledgers(
        query_events=query_ledger.events,
        budget_events=tracker.events,
        trace_root=permit.trace_root,
        role_policy=policy,
    )
    events = _read_jsonl(permit.output_root / "task_events_v1.jsonl")
    task_status = _task_events_status(events, permit=permit, stage=stage)
    target = int(candidate["scope"]["target_budget"])
    checkpoints_ok = True
    for event in events:
        checkpoint = _read_json(
            permit.checkpoint_root / f"{event['case_id']}.json"
        )
        queries = checkpoint.get("queries")
        first = checkpoint.get("first_success_query")
        if (
            not isinstance(queries, list)
            or len(queries) > target
            or not (
                event["terminal_class"] == "diagnostic_terminal"
                or first is not None
                or len(queries) == target
            )
        ):
            checkpoints_ok = False
    source_prefixes = True
    for lock in candidate["source_checkpoint_locks"]:
        checkpoint = _read_json(
            permit.checkpoint_root / f"{lock['case_id']}.json"
        )
        queries = checkpoint.get("queries")
        count = int(lock["query_count"])
        if (
            not isinstance(queries, list)
            or len(queries) < count
            or sha256_canonical_json(queries[:count])
            != lock["query_sequence_sha256"]
        ):
            source_prefixes = False
    diagnostic_ids = sorted(
        {
            str(event["case_id"])
            for event in query_ledger.events
            if event.get("event_type") == "terminal"
            and event.get("result_tier") == "diagnostic"
        }
    )
    checks = {
        "all_query_attempts_terminal": not query_status["open_query_work_keys"],
        "all_authorized_tasks_terminal": set(task_status["terminal_case_ids"])
        == {str(task["case_id"]) for task in permit.tasks},
        "checkpoint_budget_or_success_terminal": checkpoints_ok,
        "source_checkpoint_query_prefixes_preserved": source_prefixes,
        "budget_event_count_matches_provider_calls": budget_status["event_count"]
        == query_status["completed_provider_call_count"],
        "stage_cost_limit_respected": float(
            budget_status["role_cumulative_cost_cny"]
        )
        <= float(candidate["scope"]["stage_hard_limit_cny"]),
        "terminal_query_replay_count_zero": True,
        "provider_tools_disabled": True,
        "external_effects_disabled": True,
        "scientific_outcomes_not_aggregated": True,
    }
    passed = _technical_checks_pass(checks)
    final_locks = [
        _checkpoint_lock(path)
        for path in sorted(permit.checkpoint_root.glob("*.json"))
    ]
    core = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "artifact_role": "outcome_blind_flash_adaptive_technical_review",
        "reviewed_at": _now(),
        "status": (
            "adaptive_formal_flash_stage_technical_gate_pass"
            if passed
            else "adaptive_formal_flash_stage_technical_gate_fail"
        ),
        "stage": stage,
        "target_budget": target,
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_file_sha256": _sha256_file(admission_path(stage)),
        "authorized_task_count": len(permit.tasks),
        "terminal_task_count": task_status["event_count"],
        "diagnostic_case_ids_this_stage": diagnostic_ids,
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "stage_cost_cny": budget_status["role_cumulative_cost_cny"],
        "stage_hard_limit_cny": candidate["scope"]["stage_hard_limit_cny"],
        "query_ledger_tail_sha256": query_status["tail_sha256"],
        "budget_ledger_tail_sha256": budget_status["tail_sha256"],
        "task_ledger_tail_sha256": task_status["tail_sha256"],
        "final_checkpoint_locks": final_locks,
        "checks": checks,
        "technical_gate_passed": passed,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_technical_review(stage: str) -> dict[str, Any]:
    value = build_technical_review(stage)
    _write_json(review_path(stage), value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-stage", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    selected = args.admission or admission_path(args.stage)
    if args.write_candidate:
        value = write_stage_candidate(args.stage)
    elif args.verify_candidate:
        value = verify_stage_candidate(args.stage)
    elif args.write_admission:
        if not args.owner_statement_sha256 or not args.approved_at:
            parser.error("admission requires owner digest and approved time")
        value = write_stage_admission(
            args.stage,
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
        )
    elif args.verify_admission:
        value = validate_stage_admission(_read_json(selected), stage=args.stage)
    elif args.execute_stage:
        value = execute_stage(
            args.stage,
            selected_admission=selected,
            config_path=args.config,
        )
    else:
        value = write_technical_review(args.stage)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
