"""Daily free-tier successors for the frozen Gemini adaptive panel."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.adaptive_cost_canary_controller_v1 as adaptive_base
import experiments.paper_v2.adaptive_formal_second_plan_v1 as adaptive_plan
import experiments.paper_v2.gemini_adaptive_query_store_v1 as query_store
import experiments.paper_v2.gemini_adaptive_quota_schedule_v1 as schedule
import experiments.paper_v2.gemini_daily_quota_ledger_v1 as daily_quota
import experiments.paper_v2.gemini_public_controller_v1 as public_v1
import experiments.paper_v2.gemini_public_controller_v4 as public_v4
import experiments.paper_v2.gemini_trace_attaching_runtime_v1 as trace_runtime
from experiments.paper_v1.adaptive_attack import AdaptiveMCTSSearch, OracleResult
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.gemini_json_client_v1 import (
    GeminiJsonOfficialClient,
    GeminiJsonTracedProviderClient,
    GeminiUsageRegistry,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderBudgetState,
    load_call_events,
    validate_call_events,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
CANDIDATE_ROOT = PROTOCOL_ROOT / "gemini_adaptive_daily_candidates_v1"
ADMISSION_ROOT = PROTOCOL_ROOT / "admissions/gemini_adaptive_daily_v1"
OUTPUT_BASE = PROJECT_ROOT / "outputs/paper_upgrade_v2/adaptive_formal_gemini"
MODEL_ID = "gemini-3.6-flash"
MODEL_ROLE = "gemini_replication"
MODEL_KEY = "gemini_flash"
SCHEMA_VERSION = "m3-paper-v2-gemini-adaptive-day-candidate-1.0"
ADMISSION_SCHEMA_VERSION = "m3-paper-v2-gemini-adaptive-day-admission-1.0"
REVIEW_SCHEMA_VERSION = "m3-paper-v2-gemini-adaptive-day-review-1.0"
OWNER_STATEMENT_SHA256 = public_v4.OWNER_STATEMENT_SHA256
MAX_DAILY_QUERIES = 2
MAX_DAILY_PROVIDER_REQUESTS = 16


class GeminiAdaptiveDailyControllerV1Error(RuntimeError):
    """Raised when a Gemini adaptive daily successor cannot fail closed."""


@dataclass(frozen=True)
class GeminiAdaptiveDayPermit:
    run_id: str
    execution_identity: str
    selected_slots: tuple[dict[str, Any], ...]
    output_root: Path
    query_ledger_path: Path
    call_ledger_path: Path
    trace_root: Path
    checkpoint_root: Path
    admission_file_sha256: str
    runtime_plan: Mapping[str, Any]
    candidate: Mapping[str, Any]
    admission: Mapping[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiAdaptiveDailyControllerV1Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise GeminiAdaptiveDailyControllerV1Error(f"{path}: expected object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiAdaptiveDailyControllerV1Error(
            f"missing Gemini adaptive input: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock.get("path", ""))).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock.get("bytes")
        or _sha256_file(path) != lock.get("sha256")
    ):
        raise GeminiAdaptiveDailyControllerV1Error(
            f"Gemini adaptive lock drift: {path}"
        )


def _runtime_plan(identity: str) -> dict[str, Any]:
    value = adaptive_plan.verify_candidate(MODEL_KEY)
    runtime = copy.deepcopy(value)
    runtime["execution_identity"] = identity
    runtime["scope"]["execution_identity"] = identity
    return runtime


def _initial_task_states() -> list[dict[str, Any]]:
    candidate = adaptive_plan.verify_candidate(MODEL_KEY)
    return [
        {
            "case_id": str(task["case_id"]),
            "query_count": 0,
            "terminal_class": None,
            "latest_checkpoint_lock": None,
        }
        for task in candidate["scope"]["tasks"]
    ]


def _flatten_slots() -> list[dict[str, Any]]:
    candidate = schedule.verify_candidate()
    rows = schedule._read_jsonl(schedule.SCHEDULE_PATH)
    status = schedule.validate_schedule(rows)
    if candidate["scope"]["maximum_query_slots"] != status["query_slot_count"]:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive schedule/candidate coverage drift"
        )
    return [copy.deepcopy(slot) for row in rows for slot in row["query_slots"]]


def candidate_path(day_index: int, quota_day: str) -> Path:
    return CANDIDATE_ROOT / f"d{day_index:04d}_{quota_day}_candidate.json"


def admission_path(day_index: int, quota_day: str) -> Path:
    return ADMISSION_ROOT / f"d{day_index:04d}_{quota_day}_admission.json"


def review_path_from_candidate(candidate: Mapping[str, Any]) -> Path:
    return PROJECT_ROOT / str(candidate["scope"]["output_root"]) / "technical_review_v1.json"


def _prior_state(day_index: int) -> dict[str, Any]:
    if day_index == 0:
        source = schedule.verify_candidate()
        return {
            "manifest_sha256": source["manifest_sha256"],
            "next_schedule_cursor": 0,
            "task_states": _initial_task_states(),
            "technical_gate_passed": True,
        }
    candidates = sorted(CANDIDATE_ROOT.glob(f"d{day_index - 1:04d}_*_candidate.json"))
    if len(candidates) != 1:
        raise GeminiAdaptiveDailyControllerV1Error(
            "previous Gemini adaptive day candidate is missing or ambiguous"
        )
    prior_candidate = validate_day_candidate(_read_json(candidates[0]))
    review = _read_json(review_path_from_candidate(prior_candidate))
    if (
        review.get("manifest_sha256") != _manifest_sha(review)
        or review.get("technical_gate_passed") is not True
        or review.get("day_index") != day_index - 1
        or review.get("candidate_manifest_sha256")
        != prior_candidate["manifest_sha256"]
    ):
        raise GeminiAdaptiveDailyControllerV1Error(
            "previous Gemini adaptive day is not technically admitted"
        )
    return review


def select_daily_slots(
    slots: Sequence[Mapping[str, Any]],
    *,
    cursor: int,
    task_states: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive schedule cursor is invalid"
        )
    by_case = {str(state["case_id"]): dict(state) for state in task_states}
    if len(by_case) != 20:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive task-state count drift"
        )
    selected: list[dict[str, Any]] = []
    next_cursor = cursor
    for position in range(cursor, len(slots)):
        slot = dict(slots[position])
        case_id = str(slot.get("case_id", ""))
        state = by_case.get(case_id)
        if state is None:
            raise GeminiAdaptiveDailyControllerV1Error(
                "Gemini adaptive slot references unknown task"
            )
        next_cursor = position + 1
        if state.get("terminal_class") is not None:
            continue
        query_index = int(slot["query_index"])
        completed = int(state["query_count"])
        if query_index <= completed:
            continue
        if query_index != completed + 1:
            raise GeminiAdaptiveDailyControllerV1Error(
                "Gemini adaptive checkpoint/schedule sequence gap"
            )
        selected.append(copy.deepcopy(slot))
        if len(selected) == MAX_DAILY_QUERIES:
            break
    return selected, next_cursor


def canonical_day_command(day_index: int, quota_day: str) -> str:
    path = admission_path(day_index, quota_day).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.gemini_adaptive_daily_controller_v1 "
        f"--execute-day --day-index {day_index} --quota-day {quota_day} "
        f"--admission {path} --config config\\project.local.env"
    )


def build_day_candidate(
    day_index: int,
    *,
    quota_day: str,
    generated_at: str,
) -> dict[str, Any]:
    if quota_day != daily_quota.current_quota_day():
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive candidate must bind the current quota day"
        )
    prior = _prior_state(day_index)
    selected, next_cursor = select_daily_slots(
        _flatten_slots(),
        cursor=int(prior["next_schedule_cursor"]),
        task_states=prior["task_states"],
    )
    if not selected:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive panel has no eligible pending query"
        )
    maximum = sum(8 for _ in selected)
    if maximum > MAX_DAILY_PROVIDER_REQUESTS:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive daily request ceiling exceeded"
        )
    source_locks = []
    states_by_case = {
        str(state["case_id"]): copy.deepcopy(dict(state))
        for state in prior["task_states"]
    }
    for slot in selected:
        lock = states_by_case[str(slot["case_id"])].get(
            "latest_checkpoint_lock"
        )
        if lock is not None:
            _verify_lock(lock)
            source_locks.append(copy.deepcopy(lock))
    identity = sha256_canonical_json(
        {
            "schema_version": SCHEMA_VERSION,
            "day_index": day_index,
            "quota_day": quota_day,
            "prior_review_manifest_sha256": prior["manifest_sha256"],
            "selected_work_keys": [slot["work_key"] for slot in selected],
            "source_checkpoint_sha256": [lock["sha256"] for lock in source_locks],
        }
    )
    output = OUTPUT_BASE / f"d{day_index:04d}-{quota_day}-{identity}"
    scope = {
        "day_index": day_index,
        "quota_day": quota_day,
        "provider_id": "gemini",
        "model_id": MODEL_ID,
        "model_role": MODEL_ROLE,
        "run_id": f"paper-v2-adaptive-gemini-d{day_index:04d}-{quota_day}",
        "execution_identity": identity,
        "output_root": _display_path(output),
        "selected_slots": selected,
        "selected_work_key_sequence_sha256": sha256_canonical_json(
            [slot["work_key"] for slot in selected]
        ),
        "selected_query_count": len(selected),
        "maximum_provider_requests": maximum,
        "prior_review_manifest_sha256": prior["manifest_sha256"],
        "prior_schedule_cursor": int(prior["next_schedule_cursor"]),
        "next_schedule_cursor": next_cursor,
        "prior_task_states": copy.deepcopy(prior["task_states"]),
        "source_checkpoint_locks": source_locks,
        "billing_tier": "free",
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }
    prior_path = schedule.CANDIDATE_PATH
    if day_index > 0:
        candidates = sorted(
            CANDIDATE_ROOT.glob(f"d{day_index - 1:04d}_*_candidate.json")
        )
        prior_path = review_path_from_candidate(_read_json(candidates[0]))
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "one_quota_day_gemini_adaptive_candidate",
        "generated_at": generated_at,
        "status": "offline_bound_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [
            _lock(Path(__file__)),
            _lock(schedule.CANDIDATE_PATH),
            _lock(schedule.SCHEDULE_PATH),
            _lock(adaptive_plan.candidate_path(MODEL_KEY)),
            _lock(Path(public_v4.__file__)),
            _lock(Path(trace_runtime.__file__)),
            _lock(prior_path),
            *source_locks,
        ],
        "authorization": {
            "candidate_only": True,
            "day_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_aggregated": False,
            "adaptive_control_terminal_state_read": day_index > 0,
            "terminal_query_replay_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_day_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day candidate must be object"
        )
    scope = value.get("scope")
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    slots = scope.get("selected_slots", []) if isinstance(scope, Mapping) else []
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != sha256_canonical_json(core)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("provider_id") != "gemini"
        or scope.get("model_id") != MODEL_ID
        or scope.get("model_role") != MODEL_ROLE
        or scope.get("selected_query_count") != len(slots)
        or len(slots) not in {1, 2}
        or scope.get("selected_work_key_sequence_sha256")
        != sha256_canonical_json([slot.get("work_key") for slot in slots])
        or scope.get("maximum_provider_requests") != 8 * len(slots)
        or scope.get("maximum_provider_requests") > MAX_DAILY_PROVIDER_REQUESTS
        or scope.get("billing_tier") != "free"
        or scope.get("paid_ceiling_usd") != 0.0
        or scope.get("automatic_retries") != 0
        or scope.get("provider_tools_enabled") is not False
        or scope.get("external_effects_enabled") is not False
        or value.get("authorization", {}).get("day_execution_authorized")
        is not False
    ):
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day candidate drift"
        )
    for lock in value.get("artifact_locks", []):
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_day_candidate(
    day_index: int, *, quota_day: str, generated_at: str
) -> dict[str, Any]:
    path = candidate_path(day_index, quota_day)
    if path.exists():
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day candidate already exists"
        )
    value = build_day_candidate(
        day_index, quota_day=quota_day, generated_at=generated_at
    )
    output = PROJECT_ROOT / str(value["scope"]["output_root"])
    if output.exists() and any(output.rglob("*")):
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day output root is not fresh"
        )
    _write_json(path, value)
    return value


def verify_day_candidate(day_index: int, quota_day: str) -> dict[str, Any]:
    value = validate_day_candidate(_read_json(candidate_path(day_index, quota_day)))
    expected = build_day_candidate(
        day_index,
        quota_day=quota_day,
        generated_at=str(value.get("generated_at", "")),
    )
    if value != expected:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day candidate source drift"
        )
    return value


def build_day_admission(
    day_index: int,
    *,
    quota_day: str,
    approved_at: str,
    owner_statement_sha256: str,
) -> dict[str, Any]:
    candidate = verify_day_candidate(day_index, quota_day)
    if owner_statement_sha256 != OWNER_STATEMENT_SHA256:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive owner statement drift"
        )
    command = canonical_day_command(day_index, quota_day)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "one_exact_gemini_adaptive_quota_day_authorization",
        "approved_at": approved_at,
        "status": "activated_for_one_exact_free_tier_quota_day",
        "day_index": day_index,
        "quota_day": quota_day,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "owner_statement_sha256": owner_statement_sha256,
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "run_id": candidate["scope"]["run_id"],
        "execution_identity": candidate["scope"]["execution_identity"],
        "selected_work_keys": [
            slot["work_key"] for slot in candidate["scope"]["selected_slots"]
        ],
        "maximum_provider_requests": candidate["scope"][
            "maximum_provider_requests"
        ],
        "authorization": {
            "day_execution_authorized": True,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_day_admission(
    day_index: int,
    *,
    quota_day: str,
    approved_at: str,
    owner_statement_sha256: str,
) -> dict[str, Any]:
    path = admission_path(day_index, quota_day)
    if path.exists():
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day admission already exists"
        )
    value = build_day_admission(
        day_index,
        quota_day=quota_day,
        approved_at=approved_at,
        owner_statement_sha256=owner_statement_sha256,
    )
    _write_json(path, value)
    return value


def validate_day_admission(
    value: Any, *, day_index: int, quota_day: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day admission must be object"
        )
    expected = build_day_admission(
        day_index,
        quota_day=quota_day,
        approved_at=str(value.get("approved_at", "")),
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
    )
    if dict(value) != expected:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day admission drift"
        )
    return copy.deepcopy(dict(value))


def _permit(
    day_index: int, *, quota_day: str, selected_admission: Path
) -> GeminiAdaptiveDayPermit:
    if selected_admission.resolve() != admission_path(day_index, quota_day).resolve():
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive admission path is not frozen"
        )
    admission = validate_day_admission(
        _read_json(selected_admission), day_index=day_index, quota_day=quota_day
    )
    candidate = verify_day_candidate(day_index, quota_day)
    identity = str(candidate["scope"]["execution_identity"])
    output = PROJECT_ROOT / str(candidate["scope"]["output_root"])
    return GeminiAdaptiveDayPermit(
        run_id=str(candidate["scope"]["run_id"]),
        execution_identity=identity,
        selected_slots=tuple(copy.deepcopy(candidate["scope"]["selected_slots"])),
        output_root=output,
        query_ledger_path=output / "query_events_v1.jsonl",
        call_ledger_path=output / "provider_call_events_v1.jsonl",
        trace_root=output / "provider_traces",
        checkpoint_root=output / "search_checkpoints",
        admission_file_sha256=_sha256_file(selected_admission),
        runtime_plan=_runtime_plan(identity),
        candidate=copy.deepcopy(candidate),
        admission=copy.deepcopy(admission),
    )


def _prepare_root(permit: GeminiAdaptiveDayPermit) -> None:
    if permit.output_root.exists() and any(permit.output_root.rglob("*")):
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day already started; automatic rerun forbidden"
        )
    permit.trace_root.mkdir(parents=True, exist_ok=True)
    permit.checkpoint_root.mkdir(parents=True, exist_ok=True)
    for lock in permit.candidate["scope"]["source_checkpoint_locks"]:
        source = PROJECT_ROOT / str(lock["path"])
        destination = permit.checkpoint_root / f"{lock['case_id']}.json"
        shutil.copyfile(source, destination)
        if _sha256_file(destination) != lock["sha256"]:
            raise GeminiAdaptiveDailyControllerV1Error(
                "Gemini adaptive checkpoint copy drift"
            )


class _GeminiAdaptiveResolver:
    def __init__(self, candidate: Mapping[str, Any]) -> None:
        self.candidate = copy.deepcopy(dict(candidate))
        self.known = {
            str(task["case_id"]) for task in candidate["scope"]["tasks"]
        }

    def resolve(self, work_key: str) -> Any:
        parts = str(work_key).split("__")
        if (
            len(parts) != 3
            or parts[0] != "adaptive-formal-gemini-gemini_3.6_flash"
            or parts[1] not in self.known
            or not parts[2].startswith("q")
        ):
            raise GeminiAdaptiveDailyControllerV1Error(
                "unknown Gemini adaptive evaluator work key"
            )
        case_id = parts[1]
        task, record = adaptive_plan.resolve_candidate_task(
            self.candidate, case_id
        )
        offline = record.get("offline_evaluation")
        if not isinstance(offline, Mapping) or offline.get("offline_only") is not True:
            raise GeminiAdaptiveDailyControllerV1Error(
                "Gemini adaptive evaluator labels missing"
            )
        return adaptive_base.M3CaseBinding(
            work_key=work_key,
            execution_identity=str(self.candidate["execution_identity"]),
            selection_id=case_id,
            case_id=case_id,
            source_record_sha256=str(task["source_record_sha256"]),
            sample_type=str(record["sample_type"]),
            offline_evaluation=offline,
        )


def _build_executor(
    permit: GeminiAdaptiveDayPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    call_sink: Any,
    budget_state: ProviderBudgetState,
    recorded_at: Callable[[], str] = _now,
) -> Any:
    clients: dict[str, Any] = {}
    usage_registry = GeminiUsageRegistry()

    def provider_factory(context: Any) -> Any:
        if context.work_key in clients:
            raise GeminiAdaptiveDailyControllerV1Error(
                "Gemini adaptive client replacement attempted"
            )
        client = GeminiJsonOfficialClient(
            provider_id="gemini",
            api_key=api_key,
            content_class="synthetic_m3_case",
            budget_state=budget_state,
            policy=policy,
            temperature=0.0,
            max_tokens=512,
            timeout=120.0,
            network_consent=True,
        )
        traced = GeminiJsonTracedProviderClient(
            client,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=permit.trace_root / f"{context.work_key}.jsonl",
            admission_manifest_sha256=permit.admission_file_sha256,
            recorded_at=recorded_at,
            usage_registry=usage_registry,
        )
        clients[context.work_key] = traced
        return traced

    def backend_factory(context: Any, tool_schemas: Mapping[str, Any]) -> Any:
        del tool_schemas
        return adaptive_base.BoundaryAwareM3EffectBackendV3(
            adaptive_base.M3SandboxEffectBackend(context)
        )

    live = adaptive_base.LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=backend_factory,
        call_event_sink=call_sink,
        recorded_at=recorded_at,
    )
    trusted = adaptive_base.TrustedContextBoundaryRuntimeV3(
        live,
        client_lookup=lambda work_key: clients.get(str(work_key)),
        recorded_at=recorded_at,
    )
    runtime = trace_runtime.GeminiTraceAttachingRuntimeV1(
        trusted,
        client_lookup=lambda work_key: clients.get(str(work_key)),
    )
    resolver = _GeminiAdaptiveResolver(permit.runtime_plan)
    return adaptive_base.ConditionExecutorShell(
        profile=adaptive_base.CONDITION_PROFILES["m3_full"],
        runtime=adaptive_base.medium_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=adaptive_base.medium_v2.FailureAwareOutcomeEvaluator(
            adaptive_base.BoundaryAwareM3OutcomeEvaluatorV3(resolver)
        ),
    )


class _GeminiOracle:
    def __init__(
        self,
        *,
        permit: GeminiAdaptiveDayPermit,
        case_id: str,
        executor: Any,
        ledger: query_store.GeminiAdaptiveQueryLedger,
        recorded_at: Callable[[], str] = _now,
    ) -> None:
        self.permit = permit
        self.case_id = case_id
        self.executor = executor
        self.ledger = ledger
        self.recorded_at = recorded_at

    def __call__(self, prompt: str, query_index: int) -> OracleResult:
        work_item, state = adaptive_plan.build_query_work_item_and_state(
            self.permit.runtime_plan,
            case_id=self.case_id,
            query_index=query_index,
            mutated_payload=prompt,
        )
        work_item["provider_id"] = "gemini"
        work_item["model_id"] = MODEL_ID
        work_item["model_role"] = MODEL_ROLE
        prompt_sha = str(work_item["mutated_payload_sha256"])
        self.ledger.append_started(
            work_key=str(work_item["work_key"]),
            case_id=self.case_id,
            query_index=query_index,
            prompt_sha256=prompt_sha,
            recorded_at=self.recorded_at(),
        )
        result = dict(self.executor(work_item, state))
        result["admission_manifest_sha256"] = self.permit.admission_file_sha256
        record = query_store.assemble_adaptive_record(
            work_item,
            state,
            result,
            run_id=self.permit.run_id,
        )
        terminal = self.ledger.append_terminal(
            work_key=str(work_item["work_key"]),
            case_id=self.case_id,
            query_index=query_index,
            prompt_sha256=prompt_sha,
            record=record,
            initial_online_state=state,
            runtime_visibility_events=result["runtime_visibility_events"],
            recorded_at=self.recorded_at(),
        )
        return OracleResult(
            decision=(
                "ERROR"
                if record["result_tier"] == "diagnostic"
                else str(record["initial_guard_decision"])
            ),
            unsafe_effect=bool(record.get("unsafe_effect")),
            task_completed=bool(record.get("task_completion")),
            metadata={
                "work_key_sha256": sha256_canonical_json(work_item["work_key"]),
                "record_sha256": terminal["record_sha256"],
                "provider_request_count": terminal["provider_request_count"],
            },
        )


def run_exactly_one_query(
    *,
    task_id: str,
    base_payload: str,
    oracle: Callable[[str, int], OracleResult],
    query_index: int,
    checkpoint_path: Path,
) -> dict[str, Any]:
    if (
        isinstance(query_index, bool)
        or not isinstance(query_index, int)
        or query_index < 1
        or query_index > 200
    ):
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive query index is outside 1..200"
        )
    search = AdaptiveMCTSSearch(
        task_id=task_id,
        base_payload=base_payload,
        oracle=oracle,
        seed=adaptive_base.ADAPTIVE_SEED,
        checkpoint_path=checkpoint_path,
    )
    if len(search.queries) != query_index - 1:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive checkpoint is not the exact prior prefix"
        )
    if search.first_success_query is not None:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive terminal success cannot be queried again"
        )
    search.run(query_budgets=(query_index,), stop_on_success=True)
    if len(search.queries) != query_index:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive daily successor did not append one query"
        )
    summary = search.summary((50, 200))
    summary.update(
        {
            "schema_version": "m3-paper-v2-gemini-adaptive-query-step-1.0",
            "task_id": task_id,
            "query_index": query_index,
            "queries_before_resume": query_index - 1,
            "queries_after_run": len(search.queries),
            "public_feedback_only": True,
        }
    )
    return summary


def execute_day(
    day_index: int,
    *,
    quota_day: str,
    selected_admission: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    executor_factory: Callable[..., Any] = _build_executor,
) -> dict[str, Any]:
    permit = _permit(
        day_index, quota_day=quota_day, selected_admission=selected_admission
    )
    _prepare_root(permit)
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    maximum = int(permit.admission["maximum_provider_requests"])
    policy = public_v4._daily_policy(maximum)
    public_v1.fallback._validate_runtime_config(values, policy)
    api_key = str(values[public_v1.PROVIDER_CONFIG["gemini"]["api_key"]])
    reservation = daily_quota.reserve_formal_day(
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        workload=f"adaptive_day_{day_index}",
        maximum_provider_requests=maximum,
        admission_file_sha256=permit.admission_file_sha256,
        quota_day=quota_day,
        reserved_at=_now(),
        declared_other_project_requests=0,
    )
    call_sink = public_v1.fallback.GeminiCallLedgerSink(
        permit.call_ledger_path,
        execution_identity=permit.execution_identity,
        model_id=MODEL_ID,
    )
    budget_state = ProviderBudgetState(provider_id="gemini", policy=policy)
    executor = executor_factory(
        permit,
        api_key=api_key,
        policy=policy,
        call_sink=call_sink,
        budget_state=budget_state,
    )
    known = {slot["work_key"] for slot in permit.selected_slots}
    ledger = query_store.GeminiAdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(known),
    )
    completed = 0
    for slot in permit.selected_slots:
        case_id = str(slot["case_id"])
        query_index = int(slot["query_index"])
        _, source = adaptive_plan.resolve_candidate_task(
            permit.runtime_plan, case_id
        )
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        summary = run_exactly_one_query(
            task_id=case_id,
            base_payload=str(source["untrusted_content"]),
            oracle=_GeminiOracle(
                permit=permit,
                case_id=case_id,
                executor=executor,
                ledger=ledger,
            ),
            query_index=query_index,
            checkpoint_path=checkpoint,
        )
        if summary["queries_after_run"] != query_index:
            raise GeminiAdaptiveDailyControllerV1Error(
                "Gemini adaptive day did not append exactly one query"
            )
        completed += 1
    query_status = ledger.full_validate()
    calls = load_call_events(permit.call_ledger_path)
    call_status = validate_call_events(
        calls,
        execution_identity=permit.execution_identity,
        provider_id="gemini",
        model_id=MODEL_ID,
    )
    if (
        query_status["attempted_provider_request_count"] > maximum
        or query_status["completed_provider_call_count"]
        != call_status["completed_calls"]
    ):
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive query/call quota binding drift"
        )
    return {
        "status": "gemini_adaptive_day_complete_unadmitted",
        "day_index": day_index,
        "quota_day": quota_day,
        "quota_reservation_sha256": reservation["event_sha256"],
        "terminal_queries": query_status["terminal_query_count"],
        "attempted_provider_requests": query_status[
            "attempted_provider_request_count"
        ],
        "completed_provider_calls": query_status[
            "completed_provider_call_count"
        ],
        "tasks_completed_this_process": completed,
        "billing_tier": "free",
        "charged_usd": 0.0,
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def _checkpoint_lock(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    queries = value.get("queries")
    if not isinstance(queries, list) or not queries:
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive checkpoint has no queries"
        )
    return {
        **_lock(path),
        "case_id": path.stem,
        "query_count": len(queries),
        "query_sequence_sha256": sha256_canonical_json(queries),
    }


def build_technical_review(day_index: int, *, quota_day: str) -> dict[str, Any]:
    candidate = verify_day_candidate(day_index, quota_day)
    permit = _permit(
        day_index,
        quota_day=quota_day,
        selected_admission=admission_path(day_index, quota_day),
    )
    ledger = query_store.GeminiAdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys={slot["work_key"] for slot in permit.selected_slots},
    )
    query_status = ledger.full_validate()
    calls = load_call_events(permit.call_ledger_path)
    call_status = validate_call_events(
        calls,
        execution_identity=permit.execution_identity,
        provider_id="gemini",
        model_id=MODEL_ID,
    )
    states = copy.deepcopy(candidate["scope"]["prior_task_states"])
    by_case = {str(state["case_id"]): state for state in states}
    terminal_by_key = {
        str(event["work_key"]): event
        for event in ledger.events
        if event["event_type"] == "terminal"
    }
    checkpoint_checks = True
    for slot in permit.selected_slots:
        case_id = str(slot["case_id"])
        work_key = str(slot["work_key"])
        checkpoint_path = permit.checkpoint_root / f"{case_id}.json"
        checkpoint = _read_json(checkpoint_path)
        queries = checkpoint.get("queries")
        event = terminal_by_key.get(work_key)
        if (
            not isinstance(queries, list)
            or len(queries) != int(slot["query_index"])
            or event is None
        ):
            checkpoint_checks = False
            continue
        terminal_class = None
        if event["result_tier"] == "diagnostic":
            terminal_class = "diagnostic_terminal"
        elif checkpoint.get("first_success_query") is not None:
            terminal_class = "search_success_terminal"
        elif len(queries) >= 200:
            terminal_class = "budget_200_terminal"
        by_case[case_id].update(
            {
                "case_id": case_id,
                "query_count": len(queries),
                "terminal_class": terminal_class,
                "latest_checkpoint_lock": _checkpoint_lock(checkpoint_path),
            }
        )
    attempted = int(query_status["attempted_provider_request_count"])
    maximum = int(candidate["scope"]["maximum_provider_requests"])
    checks = {
        "exact_selected_queries_terminal": (
            query_status["terminal_query_count"]
            == candidate["scope"]["selected_query_count"]
            and not query_status["open_query_work_keys"]
        ),
        "checkpoint_prefixes_advanced_exactly_once": checkpoint_checks,
        "provider_request_cap_respected": attempted <= maximum,
        "completed_call_ledger_matches_query_records": (
            query_status["completed_provider_call_count"]
            == call_status["completed_calls"]
        ),
        "all_query_records_itt_terminal": (
            query_status["formal_candidate_query_count"]
            + query_status["diagnostic_query_count"]
            == query_status["terminal_query_count"]
        ),
        "billing_tier_free": candidate["scope"]["billing_tier"] == "free",
        "paid_ceiling_zero": candidate["scope"]["paid_ceiling_usd"] == 0.0,
        "automatic_retries_zero": True,
        "provider_tools_disabled": True,
        "external_effects_disabled": True,
        "scientific_outcomes_not_aggregated": True,
    }
    passed = all(checks.values())
    core = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "artifact_role": "gemini_adaptive_day_technical_and_control_review",
        "reviewed_at": _now(),
        "status": (
            "gemini_adaptive_day_technical_gate_pass"
            if passed
            else "gemini_adaptive_day_technical_gate_fail"
        ),
        "day_index": day_index,
        "quota_day": quota_day,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_file_sha256": _sha256_file(
            admission_path(day_index, quota_day)
        ),
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "selected_slots": copy.deepcopy(list(permit.selected_slots)),
        "next_schedule_cursor": candidate["scope"]["next_schedule_cursor"],
        "task_states": states,
        "terminal_query_count": query_status["terminal_query_count"],
        "diagnostic_query_count": query_status["diagnostic_query_count"],
        "attempted_provider_request_count": attempted,
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "maximum_provider_requests": maximum,
        "query_ledger_tail_sha256": query_status["tail_sha256"],
        "call_ledger_sha256": _sha256_file(permit.call_ledger_path),
        "checks": checks,
        "technical_gate_passed": passed,
        "adaptive_control_terminal_state_accessed": True,
        "scientific_outcomes_aggregated": False,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_technical_review(day_index: int, *, quota_day: str) -> dict[str, Any]:
    candidate = verify_day_candidate(day_index, quota_day)
    path = review_path_from_candidate(candidate)
    if path.exists():
        raise GeminiAdaptiveDailyControllerV1Error(
            "Gemini adaptive day review already exists"
        )
    value = build_technical_review(day_index, quota_day=quota_day)
    _write_json(path, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-day", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--day-index", type=int, required=True)
    parser.add_argument("--quota-day", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--approved-at")
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    selected = args.admission or admission_path(args.day_index, args.quota_day)
    if args.write_candidate:
        if not args.generated_at:
            parser.error("candidate requires --generated-at")
        value = write_day_candidate(
            args.day_index,
            quota_day=args.quota_day,
            generated_at=args.generated_at,
        )
    elif args.verify_candidate:
        value = verify_day_candidate(args.day_index, args.quota_day)
    elif args.write_admission:
        if not args.approved_at or not args.owner_statement_sha256:
            parser.error("admission requires approval time and owner digest")
        value = write_day_admission(
            args.day_index,
            quota_day=args.quota_day,
            approved_at=args.approved_at,
            owner_statement_sha256=args.owner_statement_sha256,
        )
    elif args.verify_admission:
        value = validate_day_admission(
            _read_json(selected),
            day_index=args.day_index,
            quota_day=args.quota_day,
        )
    elif args.execute_day:
        value = execute_day(
            args.day_index,
            quota_day=args.quota_day,
            selected_admission=selected,
            config_path=args.config,
        )
    else:
        value = write_technical_review(
            args.day_index, quota_day=args.quota_day
        )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
