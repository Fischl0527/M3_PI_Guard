"""Run the E6 cross-provider activity and repeatability calibration.

The runner consumes two frozen provider plans, keeps DeepSeek and Gemini state
under disjoint roots, and treats W1--W3 as formal temporal replicates rather
than retries.  It reuses the paper-v2 provider clients, trace ledgers, offline
evaluator, and isolated effect backends.  No provider-managed tool or external
effect is available on this path.
"""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.formal_matrix_controller_v2 as medium_v2
import experiments.paper_v2.incremental_study_runner_v1 as incremental
import experiments.paper_v2.lean_empirical_runner as lean
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    ALL_CONDITION_PROFILES,
    E6_CALIBRATION_CONDITIONS,
    OnlineExecutorContext,
    build_e6_calibration_condition_dispatcher,
)
from experiments.paper_v2.gemini_json_client_v1 import (
    GeminiJsonOfficialClient,
    GeminiJsonTracedProviderClient,
    GeminiUsageRegistry,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    M3SandboxEffectBackend,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
    load_call_events,
)
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import (
    PublicFrozenAgentDojoCaseResolverV2,
)
from experiments.paper_v2.public_m3_live_dependency_v4 import (
    PublicFrozenM3CaseResolverV4,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/e6_cross_provider_calibration_v1"
)
PLAN_PATHS = {
    "deepseek": PROTOCOL_ROOT / "execution_plan_deepseek_v1.jsonl",
    "gemini": PROTOCOL_ROOT / "execution_plan_gemini_v1.jsonl",
}
MANIFEST_PATH = PROTOCOL_ROOT / "manifest_v1.json"
OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs/experiments/e6_cross_provider_calibration_v1"
)
PROVIDER_ROOT_NAMES = {
    "deepseek": "deepseek_pro",
    "gemini": "gemini_flash",
}
EXPECTED_MODELS = {
    "deepseek": "deepseek-v4-pro",
    "gemini": "gemini-3.6-flash",
}
EXPECTED_MODEL_ROLES = {
    "deepseek": "primary",
    "gemini": "cross_provider_replication",
}
EXPECTED_COUNTS = {"deepseek": 1_080, "gemini": 540}
EXPECTED_TASK_COUNTS = {"deepseek": 60, "gemini": 30}
EXPECTED_WINDOW_COUNTS = {"deepseek": 360, "gemini": 180}
WINDOWS = ("W1", "W2", "W3")
WINDOW_INDEX = {window: index for index, window in enumerate(WINDOWS, start=1)}
PREFIX_ROWS = 12
MAX_TOKENS = 512
TIMEOUT_SECONDS = 180.0
DEEPSEEK_RUNAWAY_CNY = 1_000.0
STUDY_ID = "m3-q2-e6-cross-provider-calibration-v1"
REQUIRED_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "study_id",
        "run_id",
        "execution_identity",
        "work_key",
        "provider_id",
        "model_id",
        "model_role",
        "underlying_task_id",
        "case_id",
        "benchmark",
        "selection_id",
        "evaluation_case_type",
        "source_reference",
        "source_record_sha256",
        "selection_stratum",
        "condition_id",
        "condition_role",
        "condition_order_position",
        "authorization_regime",
        "replicate_window",
        "replicate_index",
        "sample_role",
        "gemini_nested_replication",
        "e3_anchor",
        "historical_control_conditions",
        "max_provider_calls",
        "formal_prefix",
        "status",
        "sequence",
    }
)


class E6CalibrationRunnerError(RuntimeError):
    """Raised when E6 execution cannot preserve its frozen contract."""


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise E6CalibrationRunnerError("window timestamps must include an offset")
    return parsed


def _provider_root(provider_id: str) -> Path:
    try:
        return OUTPUT_ROOT / PROVIDER_ROOT_NAMES[provider_id]
    except KeyError as exc:
        raise E6CalibrationRunnerError(
            f"unsupported E6 provider: {provider_id}"
        ) from exc


def _raw_path(provider_id: str) -> Path:
    return _provider_root(provider_id) / "raw_records_v1.jsonl"


def _gate_path(provider_id: str, window: str) -> Path:
    return _provider_root(provider_id) / f"window_gate_{window}.json"


def _seal_path(provider_id: str, window: str) -> Path:
    return _provider_root(provider_id) / f"window_seal_{window}.json"


def _window_state_path(provider_id: str, window: str) -> Path:
    return (
        _provider_root(provider_id)
        / "internal"
        / f"window_state_{window}.json"
    )


def _identity_lock_path(provider_id: str) -> Path:
    return (
        _provider_root(provider_id)
        / "internal"
        / "returned_model_identity_lock.json"
    )


def _provider_stop_path(provider_id: str) -> Path:
    return _provider_root(provider_id) / "internal" / "provider_stop_v1.json"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise E6CalibrationRunnerError(f"{path}: expected JSON object")
    return value


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _condition_call_cap(condition_id: str) -> int:
    profile = ALL_CONDITION_PROFILES.get(condition_id)
    if profile is None or condition_id not in E6_CALIBRATION_CONDITIONS:
        raise E6CalibrationRunnerError(
            f"unsupported E6 condition: {condition_id}"
        )
    return profile.max_provider_calls


def _load_plan(provider_id: str) -> list[dict[str, Any]]:
    if provider_id not in EXPECTED_COUNTS:
        raise E6CalibrationRunnerError(f"unsupported provider: {provider_id}")
    rows = lean._read_jsonl(PLAN_PATHS[provider_id])
    if (
        len(rows) != EXPECTED_COUNTS[provider_id]
        or len({str(row.get("work_key")) for row in rows}) != len(rows)
        or len({int(row.get("sequence", 0)) for row in rows}) != len(rows)
    ):
        raise E6CalibrationRunnerError(f"{provider_id}: frozen plan count drift")

    expected_model = EXPECTED_MODELS[provider_id]
    expected_role = EXPECTED_MODEL_ROLES[provider_id]
    for row in rows:
        if not REQUIRED_PLAN_FIELDS.issubset(row):
            raise E6CalibrationRunnerError(
                f"{provider_id}: work-item fields drift"
            )
        source = row.get("source_reference")
        condition = str(row.get("condition_id"))
        if (
            row.get("study_id") != STUDY_ID
            or row.get("provider_id") != provider_id
            or row.get("model_id") != expected_model
            or row.get("model_role") != expected_role
            or row.get("authorization_regime") != "auto_compiled"
            or row.get("sample_role") != "risk_enriched_repeatability"
            or not isinstance(row.get("gemini_nested_replication"), bool)
            or (
                provider_id == "gemini"
                and row.get("gemini_nested_replication") is not True
            )
            or row.get("status") != "pending"
            or row.get("replicate_window") not in WINDOWS
            or row.get("replicate_index")
            != WINDOW_INDEX[str(row.get("replicate_window"))]
            or row.get("max_provider_calls") != _condition_call_cap(condition)
            or not isinstance(source, Mapping)
            or source.get("sha256") != row.get("source_record_sha256")
        ):
            raise E6CalibrationRunnerError(
                f"{provider_id}: work-item contract drift"
            )

    for window in WINDOWS:
        window_rows = [
            row for row in rows if row["replicate_window"] == window
        ]
        task_ids = {str(row["underlying_task_id"]) for row in window_rows}
        if (
            len(window_rows) != EXPECTED_WINDOW_COUNTS[provider_id]
            or len(task_ids) != EXPECTED_TASK_COUNTS[provider_id]
            or sum(row["formal_prefix"] is True for row in window_rows)
            != PREFIX_ROWS
            or len({str(row["run_id"]) for row in window_rows}) != 1
            or len({str(row["execution_identity"]) for row in window_rows}) != 1
        ):
            raise E6CalibrationRunnerError(
                f"{provider_id}/{window}: window structure drift"
            )
        for task_id in task_ids:
            task_rows = [
                row
                for row in window_rows
                if str(row["underlying_task_id"]) == task_id
            ]
            if (
                {str(row["condition_id"]) for row in task_rows}
                != set(E6_CALIBRATION_CONDITIONS)
                or {int(row["condition_order_position"]) for row in task_rows}
                != set(range(1, 7))
            ):
                raise E6CalibrationRunnerError(
                    f"{provider_id}/{window}/{task_id}: condition balance drift"
                )
    if len({str(row["run_id"]) for row in rows}) != len(WINDOWS):
        raise E6CalibrationRunnerError(
            f"{provider_id}: run identity is not window-isolated"
        )
    if len({str(row["execution_identity"]) for row in rows}) != len(WINDOWS):
        raise E6CalibrationRunnerError(
            f"{provider_id}: execution identity is not window-isolated"
        )
    if provider_id == "deepseek":
        nested_tasks = {
            str(row["underlying_task_id"])
            for row in rows
            if row["gemini_nested_replication"] is True
        }
        if len(nested_tasks) != EXPECTED_TASK_COUNTS["gemini"]:
            raise E6CalibrationRunnerError(
                "DeepSeek plan does not mark the thirty Gemini nested tasks"
            )
    return sorted(rows, key=lambda row: int(row["sequence"]))


def _window_rows(provider_id: str, window: str) -> list[dict[str, Any]]:
    if window not in WINDOWS:
        raise E6CalibrationRunnerError(f"unsupported E6 window: {window}")
    return [
        row
        for row in _load_plan(provider_id)
        if row["replicate_window"] == window
    ]


def _latest_records(provider_id: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in lean._read_jsonl(_raw_path(provider_id)):
        key = str(row.get("work_key", ""))
        attempt = row.get("attempt")
        if not key or isinstance(attempt, bool) or not isinstance(attempt, int):
            raise E6CalibrationRunnerError("E6 raw record identity drift")
        previous = latest.get(key)
        if previous is not None:
            previous_attempt = int(previous["attempt"])
            administrative = row.get("record_kind") == "window_closure"
            if attempt < previous_attempt or (
                attempt == previous_attempt and not administrative
            ):
                raise E6CalibrationRunnerError(
                    "E6 raw attempts are not append-only"
                )
        latest[key] = copy.deepcopy(dict(row))
    return latest


def _is_terminal(row: Mapping[str, Any]) -> bool:
    if row.get("terminal_status") is not None:
        return bool(row["terminal_status"])
    return bool(
        row.get("response_obtained") is True
        or (
            row.get("included_in_primary_itt") is True
            and row.get("retry_eligible") is not True
        )
    )


def _is_fatal_contract_error(exc: Exception) -> bool:
    name = type(exc).__name__
    return any(
        token in name
        for token in (
            "Contract",
            "Identity",
            "Ledger",
            "Payload",
            "Safety",
            "Usage",
        )
    )


def _clock_minutes(value: datetime) -> int:
    return value.hour * 60 + value.minute


def _circular_clock_difference_minutes(left: datetime, right: datetime) -> int:
    difference = abs(_clock_minutes(left) - _clock_minutes(right))
    return min(difference, 24 * 60 - difference)


def _ensure_window_started(
    provider_id: str,
    window: str,
    *,
    started_at: str | None = None,
) -> dict[str, Any]:
    path = _window_state_path(provider_id, window)
    if path.is_file():
        value = _read_json(path)
        if (
            value.get("provider_id") != provider_id
            or value.get("replicate_window") != window
        ):
            raise E6CalibrationRunnerError("window-state identity drift")
        return value

    current = _parse_time(started_at or _now())
    index = WINDOW_INDEX[window]
    if index > 1:
        previous_window = WINDOWS[index - 2]
        previous_path = _seal_path(provider_id, previous_window)
        if not previous_path.is_file():
            raise E6CalibrationRunnerError(
                f"{provider_id}/{window}: previous window is not sealed"
            )
        previous = _read_json(previous_path)
        previous_start = _parse_time(str(previous["window_started_at"]))
        separation = current - previous_start
        if (
            current.date() != previous_start.date() + timedelta(days=1)
            or separation < timedelta(hours=18)
            or separation > timedelta(hours=30)
            or _circular_clock_difference_minutes(current, previous_start) > 120
        ):
            raise E6CalibrationRunnerError(
                f"{provider_id}/{window}: temporal spacing drift"
            )
    if window == "W3":
        first = _read_json(_seal_path(provider_id, "W1"))
        if current - _parse_time(str(first["window_started_at"])) > timedelta(
            hours=72
        ):
            raise E6CalibrationRunnerError("W3 starts outside the 72-hour frame")

    counterpart = "gemini" if provider_id == "deepseek" else "deepseek"
    counterpart_path = _window_state_path(counterpart, window)
    if counterpart_path.is_file():
        counterpart_start = _parse_time(
            str(_read_json(counterpart_path)["window_started_at"])
        )
        if abs(current - counterpart_start) > timedelta(hours=2):
            raise E6CalibrationRunnerError(
                f"{provider_id}/{window}: providers did not start within two hours"
            )

    value = {
        "schema_version": "m3-paper-v2-e6-window-state-1.0",
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "replicate_window": window,
        "replicate_index": index,
        "window_started_at": current.isoformat(),
        "window_completed_at": None,
        "status": "running",
    }
    _write_json(path, value)
    return value


def _permit(
    provider_id: str,
    window: str,
    rows: Sequence[Mapping[str, Any]],
) -> lean.LeanPermit:
    if not rows:
        raise E6CalibrationRunnerError("selected E6 stage has no work items")
    run_ids = {str(row["run_id"]) for row in rows}
    identities = {str(row["execution_identity"]) for row in rows}
    if len(run_ids) != 1 or len(identities) != 1:
        raise E6CalibrationRunnerError("selected rows mix window identity")
    if not MANIFEST_PATH.is_file():
        raise E6CalibrationRunnerError("E6 manifest is missing")
    root = _provider_root(provider_id)
    return lean.LeanPermit(
        provider_id=provider_id,
        run_id=run_ids.pop(),
        execution_identity=identities.pop(),
        work_items=tuple(copy.deepcopy(dict(row)) for row in rows),
        output_root=root,
        raw_path=_raw_path(provider_id),
        trace_root=root / "internal/provider_traces" / window,
        budget_path=root / "internal" / f"deepseek_budget_events_{window}.jsonl",
        call_path=root / "internal" / f"gemini_call_events_{window}.jsonl",
        max_tokens=MAX_TOKENS,
        timeout_seconds=TIMEOUT_SECONDS,
        plan_manifest_sha256=hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        attempt_by_work_key={},
    )


def _deepseek_spend_cny() -> float:
    total = 0.0
    for row in _latest_records("deepseek").values():
        if row.get("record_kind", "execution") != "execution":
            continue
        cost = row.get("cost")
        if isinstance(cost, Mapping) and cost.get("currency") == "CNY":
            total += float(cost.get("amount", 0.0))
    return round(total, 10)


def _deepseek_policy() -> dict[str, Any]:
    policy = lean.build_role_policy(lean.load_public_policy(), "primary")
    policy = incremental.apply_incremental_peak_pricing(
        policy, EXPECTED_MODELS["deepseek"]
    )
    deepseek = policy.get("deepseek")
    if not isinstance(deepseek, dict):
        raise E6CalibrationRunnerError("DeepSeek policy is missing")
    if deepseek.get("model_id") != EXPECTED_MODELS["deepseek"]:
        raise E6CalibrationRunnerError("DeepSeek policy/model identity drift")
    remaining = DEEPSEEK_RUNAWAY_CNY - _deepseek_spend_cny()
    if remaining <= 0:
        raise E6CalibrationRunnerError("E6 runaway protection is exhausted")
    deepseek["hard_spend_limit_cny"] = remaining
    deepseek["abort_ceiling_cny"] = remaining
    deepseek["abort_at_fraction"] = 1.0
    return policy


def _gemini_dispatcher(
    permit: lean.LeanPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    plan_path: Path,
    recorded_at: Callable[[], str] = _now,
) -> Any:
    """Assemble existing Gemini components against the E6 plan identity."""

    registry = lean.gemini_public_v1._Registry()
    agentdojo = PublicFrozenAgentDojoCaseResolverV2(plan_path=plan_path)
    public_m3 = PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity,
        plan_path=plan_path,
    )
    call_sink = lean.gemini_fallback.GeminiCallLedgerSink(
        permit.call_path,
        execution_identity=permit.execution_identity,
        model_id=EXPECTED_MODELS["gemini"],
    )
    budget_state = lean._gemini_budget_state(
        load_call_events(permit.call_path), policy
    )
    usage_registry = GeminiUsageRegistry()
    traced_factory = functools.partial(
        GeminiJsonTracedProviderClient,
        usage_registry=usage_registry,
    )

    def provider_factory(context: OnlineExecutorContext) -> Any:
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        client = GeminiJsonOfficialClient(
            provider_id="gemini",
            api_key=api_key,
            content_class=content_class,
            budget_state=budget_state,
            policy=policy,
            temperature=0.0,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
            network_consent=True,
        )
        return registry.register(
            context.work_key,
            traced_factory(
                client,
                execution_identity=context.execution_identity,
                work_key=context.work_key,
                trace_path=lean._provider_trace_path(permit, context.work_key),
                admission_manifest_sha256=permit.plan_manifest_sha256,
                recorded_at=recorded_at,
            ),
        )

    def backend_factory(
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> Any:
        if context.benchmark == "m3-v2":
            return lean.BoundaryAwareM3EffectBackendV3(
                M3SandboxEffectBackend(context)
            )
        return agentdojo.build_backend(context, tool_schemas)

    live = LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=backend_factory,
        vigil_factory=medium_v2.RedactedVigilConstraintFactory(),
        call_event_sink=call_sink,
        recorded_at=recorded_at,
    )
    trusted = lean.TrustedContextBoundaryRuntimeV3(
        live,
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    runtime = lean.gemini_trace_v2.GeminiTraceAttachingRuntimeV2(
        trusted,
        client_lookup=registry.get,
    )
    return build_e6_calibration_condition_dispatcher(
        runtime=medium_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=lean._offline_evaluator(agentdojo=agentdojo, m3=public_m3),
    )


def _dispatcher(
    provider_id: str,
    permit: lean.LeanPermit,
    *,
    values: Mapping[str, str],
    all_rows: Sequence[Mapping[str, Any]],
) -> Any:
    if provider_id == "deepseek":
        policy = _deepseek_policy()
        api_key = lean._deepseek_api_key(values, policy)
        return lean._deepseek_dispatcher(
            permit,
            api_key=api_key,
            role_policy=policy,
            plan_path=PLAN_PATHS[provider_id],
            known_work_items=all_rows,
            dispatcher_builder=build_e6_calibration_condition_dispatcher,
        )

    policy = lean._gemini_policy()
    lean.gemini_fallback._validate_runtime_config(values, policy)
    if values.get("FRONTIER_GEMINI_MODEL_ID") != EXPECTED_MODELS["gemini"]:
        raise E6CalibrationRunnerError("Gemini model identity drift")
    key_field = lean.gemini_fallback.PROVIDER_CONFIG["gemini"]["api_key"]
    return _gemini_dispatcher(
        permit,
        api_key=str(values[key_field]),
        policy=policy,
        plan_path=PLAN_PATHS[provider_id],
    )


def _public_result_fields(result: Mapping[str, Any]) -> dict[str, Any]:
    events = result.get("runtime_visibility_events")
    first: Mapping[str, Any] | None = None
    if isinstance(events, list):
        first = next(
            (
                event
                for event in events
                if isinstance(event, Mapping) and event.get("parse_ok") is True
            ),
            None,
        )
    proposal_digest: str | None = None
    tool_category: str | None = None
    guard_decision: dict[str, Any] | None = None
    source_digest: str | None = None
    if first is not None:
        proposal = first.get("action_proposal")
        if isinstance(proposal, Mapping):
            tool_category = str(proposal.get("tool", "")) or None
            proposal_digest = sha256_canonical_json(
                {
                    "tool": tool_category,
                    "arguments_sha256": proposal.get("arguments_sha256"),
                }
            )
        decision = first.get("guard_decision")
        if isinstance(decision, Mapping):
            guard_decision = {
                "decision": decision.get("decision"),
                "reason_code": decision.get("reason_code"),
                "violated_constraints": copy.deepcopy(
                    list(decision.get("violated_constraints") or [])
                ),
            }
        controller = first.get("controller_evidence")
        if isinstance(controller, Mapping):
            raw_digest = controller.get("source_sha256")
            source_digest = str(raw_digest) if raw_digest else None

    safety = result.get("safety_receipt")
    simulated_receipt: dict[str, Any] | None = None
    if isinstance(safety, Mapping):
        evidence = safety.get("evidence")
        if isinstance(evidence, Mapping):
            simulated_receipt = {
                "effect_backend": evidence.get("effect_backend"),
                "tool": evidence.get("tool"),
                "arguments_sha256": evidence.get("arguments_sha256"),
                "external_connectors_enabled": evidence.get(
                    "external_connectors_enabled"
                ),
                "provider_managed_tools_enabled": evidence.get(
                    "provider_managed_tools_enabled"
                ),
                "decision": evidence.get("decision"),
                "evidence_sha256": safety.get("evidence_sha256"),
            }
    details = result.get("evaluation_details")
    return {
        "proposal_digest": proposal_digest,
        "tool_category": tool_category,
        "parameter_source_summary": {
            "available": False,
            "source_sha256": source_digest,
            "reason": "argument_provenance_is_not_persisted_by_the_public_event_contract",
        },
        "guard_decision": guard_decision,
        "simulated_effect_receipt": simulated_receipt,
        "evaluator_verdict": {
            "unsafe_effect": bool(result.get("unsafe_effect", False)),
            "task_completion": bool(result.get("task_completion", False)),
            "evaluation_details_sha256": (
                sha256_canonical_json(dict(details))
                if isinstance(details, Mapping)
                else None
            ),
        },
    }


def _enrich_record(
    record: Mapping[str, Any],
    work_item: Mapping[str, Any],
    *,
    result: Mapping[str, Any] | None,
    window_started_at: str,
) -> dict[str, Any]:
    value = copy.deepcopy(dict(record))
    value["schema_version"] = "m3-paper-v2-e6-raw-record-1.0"
    for field in (
        "underlying_task_id",
        "condition_role",
        "condition_order_position",
        "replicate_window",
        "replicate_index",
        "gemini_nested_replication",
        "e3_anchor",
        "historical_control_conditions",
        "max_provider_calls",
    ):
        value[field] = copy.deepcopy(work_item[field])
    value["record_kind"] = "execution"
    value["sample_role"] = "risk_enriched_repeatability"
    value["window_started_at"] = window_started_at
    value["window_completed_at"] = None
    value["returned_model_id"] = (
        value["returned_models"][0]
        if len(value.get("returned_models", [])) == 1
        else None
    )
    value["provider_call_count"] = len(value.get("provider_requests", []))
    if value["provider_call_count"] > int(work_item["max_provider_calls"]):
        raise E6CalibrationRunnerError("profile provider-call cap exceeded")
    attempt = int(value["attempt"])
    if value.get("response_obtained") is False:
        value["retry_eligible"] = attempt == 1
        value["included_in_primary_itt"] = attempt >= 2
        value["terminal_status"] = attempt >= 2
    else:
        value["retry_eligible"] = False
        value["included_in_primary_itt"] = True
        value["terminal_status"] = True
    value["provider_tools_enabled"] = False
    value["external_effects_enabled"] = False
    value["free_tier_attestation"] = (
        {
            "billing_tier": "free",
            "cost_usd": 0.0,
            "paid_fallback_enabled": False,
        }
        if work_item["provider_id"] == "gemini"
        else None
    )
    value.update(
        _public_result_fields(result)
        if result is not None
        else {
            "proposal_digest": None,
            "tool_category": None,
            "parameter_source_summary": {
                "available": False,
                "source_sha256": None,
                "reason": "no_runtime_result",
            },
            "guard_decision": None,
            "simulated_effect_receipt": None,
            "evaluator_verdict": {
                "unsafe_effect": False,
                "task_completion": False,
                "evaluation_details_sha256": None,
            },
        }
    )
    return value


def _selected_pending(
    provider_id: str,
    window: str,
    *,
    canary_only: bool,
    retry_failed_work_keys: Sequence[str],
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], int]]]:
    all_rows = _window_rows(provider_id, window)
    selected = (
        [row for row in all_rows if row["formal_prefix"] is True]
        if canary_only
        else all_rows
    )
    selected_keys = {str(row["work_key"]) for row in selected}
    retry_set = set(retry_failed_work_keys)
    if retry_set - selected_keys:
        raise E6CalibrationRunnerError("retry key is outside the selected window")
    latest = _latest_records(provider_id)
    unresolved = {
        str(row["work_key"])
        for row in selected
        if (
            (existing := latest.get(str(row["work_key"]))) is not None
            and not _is_terminal(existing)
            and existing.get("retry_eligible") is True
        )
    }
    if unresolved and not retry_set:
        raise E6CalibrationRunnerError(
            "response-less rows require explicit failed-key recovery before resume"
        )
    pending: list[tuple[dict[str, Any], int]] = []
    for row in selected:
        key = str(row["work_key"])
        existing = latest.get(key)
        if existing is None:
            if not retry_set:
                pending.append((row, 1))
            continue
        if key not in retry_set:
            continue
        if _is_terminal(existing) or existing.get("response_obtained") is True:
            raise E6CalibrationRunnerError("terminal E6 row cannot be retried")
        if existing.get("retry_eligible") is not True or int(
            existing["attempt"]
        ) != 1:
            raise E6CalibrationRunnerError("E6 row has exhausted its one recovery")
        pending.append((row, 2))
    return all_rows, pending


def evaluate_window_gate(provider_id: str, window: str) -> dict[str, Any]:
    plan_rows = _window_rows(provider_id, window)
    prefix = [row for row in plan_rows if row["formal_prefix"] is True]
    latest = _latest_records(provider_id)
    records = [latest.get(str(row["work_key"])) for row in prefix]
    actual = [dict(row) for row in records if isinstance(row, Mapping)]
    expected_model = EXPECTED_MODELS[provider_id]
    response_bearing = [
        row for row in actual if row.get("response_obtained") is True
    ]
    exact_model = bool(response_bearing) and all(
        row.get("returned_models") == [expected_model]
        and row.get("returned_model_id") == expected_model
        for row in response_bearing
    )
    complete_chain = len(actual) == PREFIX_ROWS and all(
        row.get("response_obtained") is True
        and isinstance(row.get("provider_requests"), list)
        and bool(row["provider_requests"])
        and all(
            request.get("local_request_id")
            and request.get("payload_sha256")
            and request.get("provider_response_id")
            and request.get("returned_model") == expected_model
            for request in row["provider_requests"]
        )
        for row in actual
    )
    parseable = sum(
        row.get("operational_status") == "completed" for row in actual
    )
    field_isolation = len(actual) == PREFIX_ROWS and all(
        row.get("online_forbidden_fields_present") is False for row in actual
    )
    no_tools_or_effects = len(actual) == PREFIX_ROWS and all(
        row.get("provider_tools_enabled") is False
        and row.get("external_effects_enabled") is False
        for row in actual
    )
    systemic = Counter(
        str(row.get("error_type"))
        for row in actual
        if row.get("operational_status")
        in {"pre_response_transport_failure", "post_response_runner_failure"}
    )
    no_repeated_systemic_error = max(systemic.values(), default=0) < 2
    free_tier = provider_id != "gemini" or (
        len(actual) == PREFIX_ROWS
        and all(
            row.get("cost")
            == {"currency": "USD", "amount": 0.0, "billing_tier": "free"}
            and row.get("free_tier_attestation")
            == {
                "billing_tier": "free",
                "cost_usd": 0.0,
                "paid_fallback_enabled": False,
            }
            for row in actual
        )
    )
    gate_passed = all(
        (
            len(actual) == PREFIX_ROWS,
            exact_model,
            complete_chain,
            parseable >= 9,
            field_isolation,
            no_tools_or_effects,
            no_repeated_systemic_error,
            free_tier,
        )
    )
    state_path = _window_state_path(provider_id, window)
    state = _read_json(state_path) if state_path.is_file() else {}
    value = {
        "schema_version": "m3-paper-v2-e6-window-gate-1.0",
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "replicate_window": window,
        "status": "passed" if gate_passed else "failed",
        "gate_passed": gate_passed,
        "planned_prefix_rows": PREFIX_ROWS,
        "observed_prefix_rows": len(actual),
        "parseable_terminal_rows": parseable,
        "exact_returned_model": exact_model,
        "complete_request_chain": complete_chain,
        "online_field_isolation": field_isolation,
        "provider_tools_and_external_effects_zero": no_tools_or_effects,
        "no_repeated_systemic_error": no_repeated_systemic_error,
        "gemini_free_tier_usd_zero": free_tier,
        "scientific_outcomes_inspected": False,
        "window_started_at": state.get("window_started_at"),
        "window_completed_at": None,
    }
    _write_json(_gate_path(provider_id, window), value)
    if gate_passed and provider_id == "gemini":
        lock_path = _identity_lock_path(provider_id)
        lock = {
            "schema_version": "m3-paper-v2-e6-model-lock-1.0",
            "provider_id": provider_id,
            "model_id": expected_model,
            "frozen_from_window": window,
        }
        if lock_path.is_file():
            observed = _read_json(lock_path)
            if (
                observed.get("provider_id") != provider_id
                or observed.get("model_id") != expected_model
            ):
                raise E6CalibrationRunnerError("Gemini model identity lock drift")
        else:
            _write_json(lock_path, lock)
    return value


def _technical_gate_failure_evidence(
    provider_id: str,
    window: str,
    *,
    latest: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return outcome-blind evidence that a failed prefix cannot be extended.

    A failed gate is administratively closable only after all twelve prefix
    executions have reached terminal records, or after one response-less
    prefix execution has exhausted its single recovery.  Administrative
    closure records are deliberately excluded from both predicates so quota
    sealing cannot be mistaken for a completed technical prefix.
    """

    gate = evaluate_window_gate(provider_id, window)
    observed = latest if latest is not None else _latest_records(provider_id)
    prefix = [
        observed.get(str(row["work_key"]))
        for row in _window_rows(provider_id, window)
        if row["formal_prefix"] is True
    ]
    executions = [
        row
        for row in prefix
        if isinstance(row, Mapping) and row.get("record_kind") == "execution"
    ]
    fully_attempted_terminal = len(executions) == PREFIX_ROWS and all(
        _is_terminal(row) for row in executions
    )
    exhausted_response_less_keys = sorted(
        str(row["work_key"])
        for row in executions
        if row.get("response_obtained") is False
        and _is_terminal(row)
        and row.get("retry_eligible") is not True
        and int(row.get("attempt", 0)) >= 2
    )
    failure_determined = bool(
        gate.get("gate_passed") is False
        and (fully_attempted_terminal or exhausted_response_less_keys)
    )
    reasons: list[str] = []
    if fully_attempted_terminal:
        reasons.append("all_formal_prefix_executions_terminal")
    if exhausted_response_less_keys:
        reasons.append("response_less_formal_prefix_recovery_exhausted")
    return {
        "failure_determined": failure_determined,
        "fully_attempted_terminal": fully_attempted_terminal,
        "exhausted_response_less_work_keys": exhausted_response_less_keys,
        "reasons": reasons,
        "gate": gate,
    }


def _require_window_gate(provider_id: str, window: str) -> dict[str, Any]:
    path = _gate_path(provider_id, window)
    if not path.is_file() or _read_json(path).get("gate_passed") is not True:
        raise E6CalibrationRunnerError(
            f"{provider_id}/{window}: formal prefix gate did not pass"
        )
    current = evaluate_window_gate(provider_id, window)
    if current.get("gate_passed") is not True:
        raise E6CalibrationRunnerError(
            f"{provider_id}/{window}: formal prefix evidence drift"
        )
    return current


def run_window(
    provider_id: str,
    window: str,
    *,
    canary_only: bool,
    config_path: Path | None = None,
    retry_failed_work_keys: Sequence[str] = (),
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[
        [lean.LeanPermit, str, Sequence[Mapping[str, Any]]], Any
    ]
    | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    stop_path = _provider_stop_path(provider_id)
    if stop_path.is_file():
        raise E6CalibrationRunnerError(
            f"{provider_id}: provider is stopped by a fatal contract boundary"
        )
    all_rows, pending = _selected_pending(
        provider_id,
        window,
        canary_only=canary_only,
        retry_failed_work_keys=retry_failed_work_keys,
    )
    if not canary_only:
        _require_window_gate(provider_id, window)
    if not pending:
        gate = (
            evaluate_window_gate(provider_id, window)
            if canary_only
            else _require_window_gate(provider_id, window)
        )
        return {
            "provider_id": provider_id,
            "replicate_window": window,
            "selected": PREFIX_ROWS if canary_only else len(all_rows),
            "executed": 0,
            "window_gate_passed": bool(gate["gate_passed"]),
            "raw_path": _display_path(_raw_path(provider_id)),
        }

    state = _ensure_window_started(
        provider_id, window, started_at=started_at
    )
    permit = _permit(provider_id, window, [row for row, _ in pending])
    permit = replace(
        permit,
        attempt_by_work_key={
            str(row["work_key"]): attempt for row, attempt in pending
        },
    )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    dispatcher = (
        dispatcher_factory(permit, provider_id, all_rows)
        if dispatcher_factory is not None
        else _dispatcher(
            provider_id,
            permit,
            values=values,
            all_rows=_load_plan(provider_id),
        )
    )

    executed = 0
    stopped = False
    for work_item, attempt in pending:
        trace_path = lean._provider_trace_path(
            permit, str(work_item["work_key"])
        )
        result: dict[str, Any] | None = None
        paused_error = False
        fatal_contract_error = False
        fatal_stop_payload: dict[str, Any] | None = None
        try:
            hydrated, online_state, digest = lean._hydrate_work_item(work_item)
            result = dict(dispatcher.execute(hydrated, online_state))
            base = lean._success_record(
                work_item,
                result,
                digest,
                attempt=attempt,
                trace_path=trace_path,
            )
        except Exception as exc:
            base = lean._failure_record(
                work_item,
                exc,
                attempt=attempt,
                trace_path=trace_path,
            )
            paused_error = isinstance(exc, ProviderPausedError)
            fatal_contract_error = _is_fatal_contract_error(exc)
            if paused_error:
                base["operational_status"] = "pre_response_rate_limited"
            elif fatal_contract_error:
                base["operational_status"] = "contract_failure"
            base["error_type"] = type(exc).__name__
            stopped = True
        record = _enrich_record(
            base,
            work_item,
            result=result,
            window_started_at=str(state["window_started_at"]),
        )
        if paused_error:
            record["retry_eligible"] = attempt == 1
            record["included_in_primary_itt"] = attempt >= 2
            record["terminal_status"] = attempt >= 2
        elif fatal_contract_error:
            record["retry_eligible"] = False
            record["included_in_primary_itt"] = True
            record["terminal_status"] = True
            fatal_stop_payload = {
                "schema_version": "m3-paper-v2-e6-provider-stop-1.0",
                "study_id": STUDY_ID,
                "provider_id": provider_id,
                "replicate_window": window,
                "work_key": work_item["work_key"],
                "error_type": record["error_type"],
                "recorded_at": record["recorded_at"],
                "status": "stopped_fatal_contract_boundary",
            }
        lean._append_jsonl(permit.raw_path, record)
        if fatal_stop_payload is not None:
            _write_json(stop_path, fatal_stop_payload)
        executed += 1
        if record.get("response_obtained") is False:
            stopped = True
        if stopped:
            break

    gate = (
        evaluate_window_gate(provider_id, window)
        if canary_only
        else _require_window_gate(provider_id, window)
    )
    return {
        "provider_id": provider_id,
        "replicate_window": window,
        "selected": PREFIX_ROWS if canary_only else len(all_rows),
        "executed": executed,
        "stopped_after_response_less_failure": stopped,
        "window_gate_passed": bool(gate["gate_passed"]),
        "raw_path": _display_path(_raw_path(provider_id)),
    }


def _gemini_window_paused(provider_id: str, window: str) -> bool:
    if provider_id != "gemini":
        return False
    call_path = (
        _provider_root(provider_id)
        / "internal"
        / f"gemini_call_events_{window}.jsonl"
    )
    return any(
        event.get("event_type") == "paused"
        for event in load_call_events(call_path)
    )


def _closure_record(
    work_item: Mapping[str, Any],
    existing: Mapping[str, Any] | None,
    *,
    window_started_at: str,
    window_completed_at: str,
    operational_status: str = "provider_window_unavailable",
    closure_reason: str = "provider_window_unavailable_before_execution",
) -> dict[str, Any]:
    if existing is not None:
        value = copy.deepcopy(dict(existing))
    else:
        value = {
            "schema_version": "m3-paper-v2-e6-raw-record-1.0",
            "study_id": work_item["study_id"],
            "run_id": work_item["run_id"],
            "work_key": work_item["work_key"],
            "case_id": work_item["case_id"],
            "benchmark": work_item["benchmark"],
            "evaluation_case_type": work_item["evaluation_case_type"],
            "condition_id": work_item["condition_id"],
            "authorization_regime": work_item["authorization_regime"],
            "sample_role": work_item["sample_role"],
            "formal_prefix": bool(work_item["formal_prefix"]),
            "provider_id": work_item["provider_id"],
            "configured_model": work_item["model_id"],
            "attempt": 0,
            "provider_requests": [],
            "response_obtained": False,
            "returned_models": [],
            "returned_model_id": None,
            "unsafe_effect": False,
            "task_completion": False,
            "ask_count": 0,
            "deny_count": 0,
            "latency_ms": {},
            "token_usage": {},
            "cost": (
                {
                    "currency": "USD",
                    "amount": 0.0,
                    "billing_tier": "free",
                }
                if work_item["provider_id"] == "gemini"
                else {"currency": "CNY", "amount": 0.0}
            ),
            "online_visible_field_digest_sha256": None,
            "online_forbidden_fields_present": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "proposal_digest": None,
            "tool_category": None,
            "parameter_source_summary": {
                "available": False,
                "source_sha256": None,
                "reason": closure_reason,
            },
            "guard_decision": None,
            "simulated_effect_receipt": None,
            "evaluator_verdict": {
                "unsafe_effect": False,
                "task_completion": False,
                "evaluation_details_sha256": None,
            },
        }
    for field in (
        "underlying_task_id",
        "condition_role",
        "condition_order_position",
        "replicate_window",
        "replicate_index",
        "gemini_nested_replication",
        "e3_anchor",
        "historical_control_conditions",
        "max_provider_calls",
    ):
        value[field] = copy.deepcopy(work_item[field])
    value.update(
        {
            "record_kind": "window_closure",
            "operational_status": operational_status,
            "closure_reason": closure_reason,
            "included_in_primary_itt": True,
            "retry_eligible": False,
            "terminal_status": True,
            "provider_call_count": len(value.get("provider_requests", [])),
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "free_tier_attestation": (
                {
                    "billing_tier": "free",
                    "cost_usd": 0.0,
                    "paid_fallback_enabled": False,
                }
                if work_item["provider_id"] == "gemini"
                else None
            ),
            "window_started_at": window_started_at,
            "window_completed_at": window_completed_at,
            "recorded_at": window_completed_at,
        }
    )
    return value


def seal_window(
    provider_id: str,
    window: str,
    *,
    completed_at: str | None = None,
) -> dict[str, Any]:
    existing_seal = _seal_path(provider_id, window)
    if existing_seal.is_file():
        value = _read_json(existing_seal)
        if (
            value.get("provider_id") != provider_id
            or value.get("replicate_window") != window
            or value.get("status") != "sealed"
        ):
            raise E6CalibrationRunnerError("existing window seal identity drift")
        return value
    state_path = _window_state_path(provider_id, window)
    if not state_path.is_file():
        raise E6CalibrationRunnerError("window has not started")
    state = _read_json(state_path)
    started = _parse_time(str(state["window_started_at"]))
    completed = _parse_time(completed_at or _now())
    if completed < started:
        raise E6CalibrationRunnerError("window completion precedes its start")
    duration = completed - started
    rows = _window_rows(provider_id, window)
    latest = _latest_records(provider_id)
    nonterminal = [
        row
        for row in rows
        if not _is_terminal(latest.get(str(row["work_key"]), {}))
    ]
    technical_gate = _technical_gate_failure_evidence(
        provider_id, window, latest=latest
    )
    close_for_technical_gate = bool(
        nonterminal and technical_gate["failure_determined"]
    )
    paused = _gemini_window_paused(provider_id, window)
    if provider_id == "deepseek" and nonterminal and not close_for_technical_gate:
        raise E6CalibrationRunnerError(
            "DeepSeek window cannot seal with nonterminal work items"
        )
    if (
        provider_id == "gemini"
        and nonterminal
        and not close_for_technical_gate
        and not paused
        and duration < timedelta(hours=12)
    ):
        raise E6CalibrationRunnerError(
            "Gemini pending rows may close only after 429 or twelve hours"
        )
    if close_for_technical_gate or provider_id == "gemini":
        operational_status = (
            "technical_gate_not_extended"
            if close_for_technical_gate
            else "provider_window_unavailable"
        )
        closure_reason = (
            "formal_prefix_technical_gate_failed_before_expansion"
            if close_for_technical_gate
            else "provider_window_unavailable_before_execution"
        )
        for row in nonterminal:
            key = str(row["work_key"])
            closure = _closure_record(
                row,
                latest.get(key),
                window_started_at=started.isoformat(),
                window_completed_at=completed.isoformat(),
                operational_status=operational_status,
                closure_reason=closure_reason,
            )
            lean._append_jsonl(_raw_path(provider_id), closure)
            latest[key] = closure
    latest_window = [latest[str(row["work_key"])] for row in rows]
    if not all(_is_terminal(row) for row in latest_window):
        raise E6CalibrationRunnerError("window closure left nonterminal rows")
    response_bearing = sum(
        row.get("response_obtained") is True for row in latest_window
    )
    by_condition: dict[str, dict[str, Any]] = {}
    for condition in E6_CALIBRATION_CONDITIONS:
        condition_rows = [
            row for row in latest_window if row["condition_id"] == condition
        ]
        condition_responses = sum(
            row.get("response_obtained") is True for row in condition_rows
        )
        by_condition[condition] = {
            "planned": len(condition_rows),
            "response_bearing": condition_responses,
            "response_bearing_fraction": condition_responses
            / len(condition_rows),
        }
    seal = {
        "schema_version": "m3-paper-v2-e6-window-seal-1.0",
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "replicate_window": window,
        "status": "sealed",
        "planned_rows": len(rows),
        "terminal_rows": len(latest_window),
        "response_bearing_rows": response_bearing,
        "response_bearing_fraction": response_bearing / len(rows),
        "condition_response_bearing": by_condition,
        "provider_window_unavailable_rows": sum(
            row.get("operational_status") == "provider_window_unavailable"
            for row in latest_window
        ),
        "technical_gate_not_extended_rows": sum(
            row.get("operational_status") == "technical_gate_not_extended"
            for row in latest_window
        ),
        "closure_mode": (
            "technical_gate_not_extended"
            if close_for_technical_gate
            else (
                "provider_window_unavailable"
                if nonterminal
                else "all_rows_terminal"
            )
        ),
        "technical_gate_failure_reasons": (
            technical_gate["reasons"] if close_for_technical_gate else []
        ),
        "paused_after_429": paused,
        "window_started_at": started.isoformat(),
        "window_completed_at": completed.isoformat(),
        "duration_hours": duration.total_seconds() / 3600.0,
        "within_twelve_hours": duration <= timedelta(hours=12),
        "gemini_formal_inference_window_eligible": (
            provider_id == "gemini"
            and response_bearing / len(rows) >= 0.75
            and all(
                value["response_bearing_fraction"] >= 0.75
                for value in by_condition.values()
            )
        ),
    }
    _write_json(_seal_path(provider_id, window), seal)
    state["window_completed_at"] = completed.isoformat()
    state["status"] = "sealed"
    _write_json(state_path, state)
    gate_path = _gate_path(provider_id, window)
    if gate_path.is_file():
        gate = _read_json(gate_path)
        gate["window_completed_at"] = completed.isoformat()
        _write_json(gate_path, gate)
    return seal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=tuple(EXPECTED_COUNTS), required=True)
    parser.add_argument("--window", choices=WINDOWS, required=True)
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--canary-only", action="store_true")
    stage.add_argument("--resume-pending-only", action="store_true")
    stage.add_argument("--seal-window", action="store_true")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--retry-failed-work-key", action="append", default=[])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.seal_window:
        if args.retry_failed_work_key:
            raise E6CalibrationRunnerError(
                "window sealing cannot retry execution rows"
            )
        result = seal_window(args.provider, args.window)
    else:
        result = run_window(
            args.provider,
            args.window,
            canary_only=args.canary_only,
            config_path=args.config,
            retry_failed_work_keys=args.retry_failed_work_key,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.canary_only and result.get("window_gate_passed") is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
