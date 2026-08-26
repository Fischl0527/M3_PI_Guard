"""Minimal provider runner for the lean authorization-regime study.

The runner consumes the single frozen 1,350-row plan, persists one compact raw
JSONL per provider, and keeps content-free operational traces under the ignored
output root.  It never invokes provider-managed tools: all proposed effects are
evaluated against the existing isolated AgentDojo/M3 backends.

There is no automatic retry.  A work item with any official response is final.
Only a row that failed before receiving an official response may be retried,
and only when ``--retry-failed`` is supplied explicitly.
"""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import experiments.paper_v2.formal_matrix_controller_v2 as medium_v2
import experiments.paper_v2.gemini_fallback_controller_v2 as gemini_fallback
import experiments.paper_v2.gemini_public_controller_v1 as gemini_public_v1
import experiments.paper_v2.gemini_trace_attaching_runtime_v2 as gemini_trace_v2
import experiments.paper_v2.public_live_controller_v2 as public_live_v2
from experiments.paper_v2.boundary_rejection_runtime_v3 import (
    BoundaryAwareM3EffectBackendV3,
    BoundaryAwareM3OutcomeEvaluatorV3,
    TrustedContextBoundaryRuntimeV3,
)
from experiments.paper_v2.contracts import (
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.formal_condition_executors import (
    OnlineExecutorContext,
    build_condition_dispatcher,
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
from experiments.paper_v2.m3_offline_evaluator import (
    PaperV2OfflineOutcomeEvaluator,
)
from experiments.paper_v2.medium_runtime import build_initial_online_state
from experiments.paper_v2.official_provider_executor import (
    ProviderBudgetState,
    ProviderPausedError,
    load_call_events,
    validate_policy,
)
from experiments.paper_v2.promptguard_live_dependency import (
    PinnedPromptGuardDetector,
)
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import (
    PublicFrozenAgentDojoCaseResolverV2,
)
from experiments.paper_v2.public_deepseek_client_v1 import (
    PublicDeepSeekJsonOfficialClient,
)
from experiments.paper_v2.public_execution_store_v1 import (
    PublicBudgetClient,
    PublicBudgetTracker,
)
from experiments.paper_v2.public_m3_live_dependency_v4 import (
    PublicFrozenM3CaseResolverV4,
)
from experiments.paper_v2.public_matrix_plan_v1 import _read_source_record
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
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/lean_empirical_execution_plan_v1.jsonl"
)
MANIFEST_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/lean_empirical_execution_manifest_v1.json"
)
OUTPUT_ROOT = PROJECT_ROOT / "outputs/experiments/lean_empirical"
PROVIDER_OUTPUTS = {
    "deepseek": OUTPUT_ROOT / "deepseek/raw_records_v1.jsonl",
    "gemini": OUTPUT_ROOT / "gemini/raw_records_v1.jsonl",
}
EXPECTED_COUNTS = {"deepseek": 900, "gemini": 450}
EXPECTED_PREFIX_COUNTS = {"deepseek": 6, "gemini": 6}
DEEPSEEK_MAX_TOKENS = 512
GEMINI_MAX_TOKENS = 512
TIMEOUT_SECONDS = 180.0
GEMINI_FREE_CAPS = {
    "requests": 4_000,
    "input_tokens": 70_000_000,
    "output_tokens": 3_000_000,
}


class LeanEmpiricalRunnerError(RuntimeError):
    """Raised when the lean execution boundary cannot be kept fail-closed."""


@dataclass(frozen=True)
class LeanPermit:
    provider_id: str
    run_id: str
    execution_identity: str
    work_items: tuple[dict[str, Any], ...]
    output_root: Path
    raw_path: Path
    trace_root: Path
    budget_path: Path
    call_path: Path
    max_tokens: int
    timeout_seconds: float
    plan_manifest_sha256: str
    attempt_by_work_key: Mapping[str, int]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise LeanEmpiricalRunnerError(f"{path}:{number}: blank row")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise LeanEmpiricalRunnerError(
                    f"{path}:{number}: expected object"
                )
            rows.append(value)
    return rows


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _load_plan(provider_id: str) -> list[dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise LeanEmpiricalRunnerError("lean manifest must be an object")
    rows = [
        row for row in _read_jsonl(PLAN_PATH) if row.get("provider_id") == provider_id
    ]
    if (
        provider_id not in EXPECTED_COUNTS
        or len(rows) != EXPECTED_COUNTS[provider_id]
        or len({str(row["work_key"]) for row in rows}) != len(rows)
        or sum(row.get("formal_prefix") is True for row in rows)
        != EXPECTED_PREFIX_COUNTS[provider_id]
    ):
        raise LeanEmpiricalRunnerError(f"{provider_id}: frozen plan count drift")
    for row in rows:
        source = row.get("source_reference")
        if (
            not isinstance(source, Mapping)
            or row.get("source_record_sha256") != source.get("sha256")
            or row.get("status") != "pending"
        ):
            raise LeanEmpiricalRunnerError("lean work-item identity drift")
    return sorted(rows, key=lambda row: int(row["sequence"]))


def _permit(provider_id: str, rows: Sequence[Mapping[str, Any]]) -> LeanPermit:
    if not rows:
        raise LeanEmpiricalRunnerError("selected stage has no work items")
    run_ids = {str(row["run_id"]) for row in rows}
    identities = {str(row["execution_identity"]) for row in rows}
    if len(run_ids) != 1 or len(identities) != 1:
        raise LeanEmpiricalRunnerError("selected stage has mixed execution identity")
    root = OUTPUT_ROOT / provider_id
    return LeanPermit(
        provider_id=provider_id,
        run_id=run_ids.pop(),
        execution_identity=identities.pop(),
        work_items=tuple(copy.deepcopy(dict(row)) for row in rows),
        output_root=root,
        raw_path=PROVIDER_OUTPUTS[provider_id],
        trace_root=root / "internal/provider_traces",
        budget_path=root / "internal/deepseek_budget_events.jsonl",
        call_path=root / "internal/gemini_call_events.jsonl",
        max_tokens=(
            DEEPSEEK_MAX_TOKENS if provider_id == "deepseek" else GEMINI_MAX_TOKENS
        ),
        timeout_seconds=TIMEOUT_SECONDS,
        plan_manifest_sha256=hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        attempt_by_work_key={},
    )


def _provider_trace_path(
    permit: LeanPermit, work_key: str
) -> Path:
    attempt = int(permit.attempt_by_work_key.get(work_key, 1))
    suffix = "" if attempt == 1 else f".attempt{attempt}"
    return permit.trace_root / f"{work_key}{suffix}.jsonl"


def _hydrate_work_item(
    work_item: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = work_item.get("source_reference")
    if not isinstance(source, Mapping):
        raise LeanEmpiricalRunnerError("work item lacks source reference")
    case = {
        "benchmark": str(work_item["benchmark"]),
        "case_id": str(work_item["case_id"]),
        "source_path": str(source["path"]),
        "source_line": int(source["line"]),
        "source_record_sha256": str(source["sha256"]),
    }
    record = _read_source_record(case)
    state = build_initial_online_state(work_item, case, record)
    digest = compute_online_visible_field_digest(state)
    if digest["forbidden_fields_present"] is not False:
        raise LeanEmpiricalRunnerError("gold/evaluator field entered online state")
    hydrated = copy.deepcopy(dict(work_item))
    hydrated["initial_online_visible_field_digest"] = digest
    return hydrated, state, digest


def _offline_evaluator(
    *,
    agentdojo: PublicFrozenAgentDojoCaseResolverV2,
    m3: PublicFrozenM3CaseResolverV4,
) -> Any:
    evaluator = PaperV2OfflineOutcomeEvaluator(
        m3_resolver=m3,
        agentdojo_resolver=agentdojo,
    )
    evaluator.m3 = BoundaryAwareM3OutcomeEvaluatorV3(m3)
    return medium_v2.FailureAwareOutcomeEvaluator(evaluator)


def _deepseek_dispatcher(
    permit: LeanPermit,
    *,
    api_key: str,
    role_policy: Mapping[str, Any],
    plan_path: Path = PLAN_PATH,
    known_work_items: Sequence[Mapping[str, Any]] | None = None,
    dispatcher_builder: Callable[..., Any] = build_condition_dispatcher,
    recorded_at: Callable[[], str] = _now,
) -> Any:
    registry = TracedClientRegistry()
    agentdojo = PublicFrozenAgentDojoCaseResolverV2(plan_path=plan_path)
    public_m3 = PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity,
        plan_path=plan_path,
    )
    known_keys = {
        str(row["work_key"])
        for row in (
            known_work_items
            if known_work_items is not None
            else _load_plan("deepseek")
        )
    }
    model_role = str(role_policy["public_model_role"])
    tracker = PublicBudgetTracker(
        permit.budget_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role=model_role,
        known_work_keys=known_keys,
        role_policy=role_policy,
    )

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> PublicDeepSeekJsonTracedProviderClient:
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        client = PublicDeepSeekJsonOfficialClient(
            provider_id="deepseek",
            api_key=api_key,
            content_class=content_class,
            budget_state=PublicProviderBudgetState("deepseek", role_policy),
            policy=role_policy,
            model_role=model_role,
            temperature=0.0,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
            network_consent=True,
        )
        budgeted = PublicBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
            recorded_at=recorded_at,
        )
        traced = PublicDeepSeekJsonTracedProviderClient(
            budgeted,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=_provider_trace_path(permit, context.work_key),
            recorded_at=recorded_at,
        )
        return registry.register(context.work_key, traced)

    def backend_factory(
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> Any:
        if context.benchmark == "m3-v2":
            return BoundaryAwareM3EffectBackendV3(M3SandboxEffectBackend(context))
        return agentdojo.build_backend(context, tool_schemas)

    live = LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=backend_factory,
        detector=PinnedPromptGuardDetector(device="cuda"),
        vigil_factory=medium_v2.RedactedVigilConstraintFactory(),
        recorded_at=recorded_at,
    )
    trusted = TrustedContextBoundaryRuntimeV3(
        live,
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    return dispatcher_builder(
        runtime=medium_v2.FailureTierNormalizingRuntime(trusted),
        evaluator=_offline_evaluator(agentdojo=agentdojo, m3=public_m3),
    )


def _gemini_policy() -> dict[str, Any]:
    policy = copy.deepcopy(gemini_fallback._effective_policy())
    policy["gemini"]["local_batch_caps"] = copy.deepcopy(GEMINI_FREE_CAPS)
    policy["gemini"]["billing_tier"] = "free"
    policy["gemini"]["allow_paid_tier"] = False
    policy["gemini"]["monetary_hard_limit_usd"] = 0.0
    return validate_policy(policy)


def _deepseek_api_key(
    values: Mapping[str, str], role_policy: Mapping[str, Any]
) -> str:
    api_key = public_live_v2._validate_runtime_config(
        values,
        role_policy=role_policy,
    )
    expected_model = str(role_policy["deepseek"]["model_id"])
    if values.get("FRONTIER_DEEPSEEK_MODEL_ID") != expected_model:
        raise LeanEmpiricalRunnerError(
            "DeepSeek model differs from the lean study identity"
        )
    return api_key


def _gemini_budget_state(
    call_events: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> ProviderBudgetState:
    return gemini_fallback._budget_state_from_calls(call_events, policy)


def _gemini_prior_call_events(permit: LeanPermit) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    parent = permit.call_path.parent
    if not parent.exists():
        return events
    for path in sorted(parent.glob("gemini_call_events*.jsonl")):
        if path == permit.call_path:
            continue
        events.extend(load_call_events(path))
    events.extend(load_call_events(permit.call_path))
    return events


def _gemini_dispatcher(
    permit: LeanPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    recorded_at: Callable[[], str] = _now,
) -> Any:
    registry = gemini_public_v1._Registry()
    agentdojo = PublicFrozenAgentDojoCaseResolverV2(plan_path=PLAN_PATH)
    public_m3 = PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity,
        plan_path=PLAN_PATH,
    )
    call_sink = gemini_fallback.GeminiCallLedgerSink(
        permit.call_path,
        execution_identity=permit.execution_identity,
        model_id="gemini-3.6-flash",
    )
    budget_state = _gemini_budget_state(_gemini_prior_call_events(permit), policy)
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
                trace_path=_provider_trace_path(permit, context.work_key),
                admission_manifest_sha256=permit.plan_manifest_sha256,
                recorded_at=recorded_at,
            ),
        )

    def backend_factory(
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> Any:
        if context.benchmark == "m3-v2":
            return BoundaryAwareM3EffectBackendV3(M3SandboxEffectBackend(context))
        return agentdojo.build_backend(context, tool_schemas)

    live = LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=backend_factory,
        detector=PinnedPromptGuardDetector(device="cuda"),
        vigil_factory=medium_v2.RedactedVigilConstraintFactory(),
        call_event_sink=call_sink,
        recorded_at=recorded_at,
    )
    trusted = TrustedContextBoundaryRuntimeV3(
        live,
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    runtime = gemini_trace_v2.GeminiTraceAttachingRuntimeV2(
        trusted,
        client_lookup=registry.get,
    )
    return build_condition_dispatcher(
        runtime=medium_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=_offline_evaluator(agentdojo=agentdojo, m3=public_m3),
    )


def _trace_requests(trace_path: Path) -> list[dict[str, Any]]:
    requests: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in _read_jsonl(trace_path):
        event = row.get("event")
        if not isinstance(event, Mapping):
            continue
        event_type = event.get("event_type")
        if event_type == "started":
            commitment = event.get("commitment")
            if not isinstance(commitment, Mapping):
                continue
            request_id = str(commitment.get("client_request_id", ""))
            if not request_id:
                continue
            order.append(request_id)
            requests[request_id] = {
                "local_request_id": request_id,
                "payload_sha256": commitment.get("payload_sha256"),
                "provider_request_id": None,
                "provider_response_id": None,
                "returned_model": commitment.get("model_id"),
            }
        elif event_type == "completed":
            request_id = str(event.get("client_request_id", ""))
            attestation = event.get("attestation")
            if request_id in requests and isinstance(attestation, Mapping):
                requests[request_id].update(
                    {
                        "provider_request_id": attestation.get(
                            "provider_request_id"
                        ),
                        "provider_response_id": attestation.get(
                            "provider_response_id"
                        ),
                        "returned_model": attestation.get("model_id"),
                    }
                )
    return [requests[item] for item in order if item in requests]


def _bundle_requests(bundle: Any) -> list[dict[str, Any]]:
    if not isinstance(bundle, Mapping):
        return []
    result: list[dict[str, Any]] = []
    for attestation in bundle.get("activated_attestations", []):
        if not isinstance(attestation, Mapping):
            continue
        result.append(
            {
                "local_request_id": attestation.get("client_request_id"),
                "payload_sha256": attestation.get("payload_sha256"),
                "provider_request_id": attestation.get("provider_request_id"),
                "provider_response_id": attestation.get("provider_response_id"),
                "returned_model": attestation.get("model_id"),
            }
        )
    return result


def _guard_counts(result: Mapping[str, Any]) -> tuple[int, int]:
    events = result.get("runtime_visibility_events", result.get("events", []))
    ask = 0
    deny = 0
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, Mapping):
                continue
            decision = event.get("guard_decision")
            value = decision.get("decision") if isinstance(decision, Mapping) else None
            ask += value == "ASK"
            deny += value == "DENY"
    return ask, deny


def _cost(bundle: Any, provider_id: str) -> dict[str, Any]:
    summary = bundle.get("usage_summary", {}) if isinstance(bundle, Mapping) else {}
    if not isinstance(summary, Mapping):
        summary = {}
    if provider_id == "deepseek":
        return {
            "currency": "CNY",
            "amount": float(summary.get("cumulative_cost_cny", 0.0)),
        }
    return {"currency": "USD", "amount": 0.0, "billing_tier": "free"}


def _success_record(
    work_item: Mapping[str, Any],
    result: Mapping[str, Any],
    digest: Mapping[str, Any],
    *,
    attempt: int,
    trace_path: Path,
) -> dict[str, Any]:
    bundle = result.get("provider_trace_bundle")
    requests = _bundle_requests(bundle) or _trace_requests(trace_path)
    response_obtained = any(item.get("provider_response_id") for item in requests)
    ask_count, deny_count = _guard_counts(result)
    status = str(result.get("operational_status", "runner_failure"))
    bundle_failures = (
        bundle.get("failures", []) if isinstance(bundle, Mapping) else []
    )
    rate_limited = not response_obtained and any(
        isinstance(item, Mapping) and item.get("status") == "paused"
        for item in bundle_failures
    )
    pre_response_provider_failure = (
        not response_obtained and status == "provider_failure" and not rate_limited
    )
    repeated_pre_response_failure = pre_response_provider_failure and attempt >= 2
    rate_limit_exhausted = rate_limited and attempt >= 3
    if rate_limited:
        status = (
            "rate_limit_exhausted_after_three_quota_days"
            if rate_limit_exhausted
            else "pre_response_rate_limited"
        )
    elif pre_response_provider_failure:
        status = (
            "repeated_pre_response_failure"
            if repeated_pre_response_failure
            else "pre_response_provider_failure"
        )
    return {
        "schema_version": "m3-paper-v2-lean-raw-record-1.0",
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
        "attempt": attempt,
        "provider_requests": requests,
        "response_obtained": response_obtained,
        "returned_models": sorted(
            {str(item["returned_model"]) for item in requests if item.get("returned_model")}
        ),
        "unsafe_effect": bool(result.get("unsafe_effect", False)),
        "task_completion": bool(result.get("task_completion", False)),
        "operational_status": status,
        "ask_count": ask_count,
        "deny_count": deny_count,
        "latency_ms": copy.deepcopy(dict(result.get("latency_ms", {}))),
        "token_usage": copy.deepcopy(dict(result.get("token_usage", {}))),
        "cost": _cost(bundle, str(work_item["provider_id"])),
        "online_visible_field_digest_sha256": sha256_canonical_json(digest),
        "online_forbidden_fields_present": bool(digest["forbidden_fields_present"]),
        "included_in_primary_itt": (
            (
                not pre_response_provider_failure
                and not rate_limited
            )
            or repeated_pre_response_failure
            or rate_limit_exhausted
        ),
        "retry_eligible": (
            (
                pre_response_provider_failure
                and not repeated_pre_response_failure
            )
            or (rate_limited and not rate_limit_exhausted)
        ),
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "recorded_at": result.get("recorded_at", _now()),
    }


def _failure_record(
    work_item: Mapping[str, Any],
    exc: Exception,
    *,
    attempt: int,
    trace_path: Path,
) -> dict[str, Any]:
    requests = _trace_requests(trace_path)
    response_obtained = any(item.get("provider_response_id") for item in requests)
    repeated_pre_response_failure = not response_obtained and attempt >= 2
    retry_eligible = not response_obtained and not repeated_pre_response_failure
    return {
        "schema_version": "m3-paper-v2-lean-raw-record-1.0",
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
        "attempt": attempt,
        "provider_requests": requests,
        "response_obtained": response_obtained,
        "returned_models": sorted(
            {str(item["returned_model"]) for item in requests if item.get("returned_model")}
        ),
        "unsafe_effect": False,
        "task_completion": False,
        "operational_status": (
            "post_response_runner_failure"
            if response_obtained
            else (
                "repeated_pre_response_failure"
                if repeated_pre_response_failure
                else "pre_response_transport_failure"
            )
        ),
        "error_type": type(exc).__name__,
        "ask_count": 0,
        "deny_count": 0,
        "latency_ms": {},
        "token_usage": {},
        "cost": (
            {"currency": "CNY", "amount": 0.0}
            if work_item["provider_id"] == "deepseek"
            else {"currency": "USD", "amount": 0.0, "billing_tier": "free"}
        ),
        "online_visible_field_digest_sha256": None,
        "online_forbidden_fields_present": False,
        "included_in_primary_itt": (
            response_obtained or repeated_pre_response_failure
        ),
        "retry_eligible": retry_eligible,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "recorded_at": _now(),
    }


def _latest_by_work_key(
    rows: Iterable[Mapping[str, Any]],
    *,
    paused_work_keys: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    paused = paused_work_keys or set()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["work_key"])
        if key in result and int(row["attempt"]) <= int(result[key]["attempt"]):
            raise LeanEmpiricalRunnerError("raw record attempts are not increasing")
        normalized = copy.deepcopy(dict(row))
        if normalized.get("response_obtained") is False and key in paused:
            exhausted = int(normalized["attempt"]) >= 3
            normalized["operational_status"] = (
                "rate_limit_exhausted_after_three_quota_days"
                if exhausted
                else "pre_response_rate_limited"
            )
            normalized["included_in_primary_itt"] = exhausted
            normalized["retry_eligible"] = not exhausted
        elif (
            normalized.get("response_obtained") is False
            and normalized.get("operational_status") == "provider_failure"
            and int(normalized["attempt"]) == 1
        ):
            normalized["operational_status"] = "pre_response_provider_failure"
            normalized["included_in_primary_itt"] = False
            normalized["retry_eligible"] = True
        result[key] = normalized
    return result


def _gemini_call_ledger_paths(root: Path) -> list[Path]:
    internal = root / "internal"
    return (
        sorted(internal.glob("gemini_call_events*.jsonl"))
        if internal.exists()
        else []
    )


def _gemini_paused_work_keys(root: Path) -> set[str]:
    paused: set[str] = set()
    for path in _gemini_call_ledger_paths(root):
        for event in load_call_events(path):
            if event.get("event_type") == "paused":
                paused.add(str(event["work_key"]))
    return paused


def _next_gemini_continuation_call_path(path: Path) -> Path:
    for index in range(1, 100):
        candidate = path.parent / f"gemini_call_events.continuation{index}.jsonl"
        if not candidate.exists():
            return candidate
    raise LeanEmpiricalRunnerError("too many Gemini continuation call ledgers")


def _select_stage(rows: Sequence[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    if stage == "canary":
        return [row for row in rows if row["formal_prefix"] is True]
    if stage == "remaining":
        return [row for row in rows if row["formal_prefix"] is False]
    if stage == "all":
        return list(rows)
    raise LeanEmpiricalRunnerError(f"unsupported stage: {stage}")


def run_provider(
    provider_id: str,
    *,
    stage: str,
    config_path: Path | None = None,
    retry_failed: bool = False,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[[LeanPermit, str], Any] | None = None,
) -> dict[str, Any]:
    all_rows = _load_plan(provider_id)
    selected = _select_stage(all_rows, stage)
    permit = _permit(provider_id, selected)
    prior_rows = _read_jsonl(permit.raw_path)
    latest = _latest_by_work_key(
        prior_rows,
        paused_work_keys=(
            _gemini_paused_work_keys(permit.output_root)
            if provider_id == "gemini"
            else None
        ),
    )
    pending: list[tuple[dict[str, Any], int]] = []
    for row in selected:
        existing = latest.get(str(row["work_key"]))
        if existing is None:
            pending.append((row, 1))
            continue
        if existing.get("response_obtained") is True:
            continue
        if existing.get("retry_eligible") is not True:
            continue
        if retry_failed:
            pending.append((row, int(existing["attempt"]) + 1))
    if not pending:
        return {
            "provider_id": provider_id,
            "stage": stage,
            "selected": len(selected),
            "executed": 0,
            "completed": 0,
            "pre_response_failures": 0,
            "paused_after_429_or_budget": False,
            "raw_path": str(permit.raw_path),
        }

    permit = replace(
        permit,
        attempt_by_work_key={str(row["work_key"]): attempt for row, attempt in pending},
    )
    if provider_id == "gemini" and any(attempt > 1 for _, attempt in pending):
        recovery = max(attempt for _, attempt in pending)
        permit = replace(
            permit,
            call_path=(
                permit.call_path.parent
                / f"gemini_call_events.recovery{recovery}.jsonl"
            ),
        )
    elif provider_id == "gemini" and permit.call_path.exists():
        permit = replace(
            permit,
            call_path=_next_gemini_continuation_call_path(permit.call_path),
        )

    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    if dispatcher_factory is None:
        if provider_id == "deepseek":
            role_policy = build_role_policy(load_public_policy(), "primary")
            api_key = _deepseek_api_key(values, role_policy)
            dispatcher = _deepseek_dispatcher(
                permit,
                api_key=api_key,
                role_policy=role_policy,
            )
        else:
            policy = _gemini_policy()
            gemini_fallback._validate_runtime_config(values, policy)
            api_key = str(values[gemini_fallback.PROVIDER_CONFIG["gemini"]["api_key"]])
            dispatcher = _gemini_dispatcher(
                permit,
                api_key=api_key,
                policy=policy,
            )
    else:
        dispatcher = dispatcher_factory(permit, provider_id)

    completed = 0
    failures = 0
    paused = False
    for work_item, attempt in pending:
        trace_path = _provider_trace_path(permit, str(work_item["work_key"]))
        try:
            hydrated, state, digest = _hydrate_work_item(work_item)
            result = dict(dispatcher.execute(hydrated, state))
            record = _success_record(
                work_item,
                result,
                digest,
                attempt=attempt,
                trace_path=trace_path,
            )
            completed += 1
            if record["operational_status"] in {
                "pre_response_rate_limited",
                "rate_limit_exhausted_after_three_quota_days",
            }:
                paused = True
        except Exception as exc:
            record = _failure_record(
                work_item,
                exc,
                attempt=attempt,
                trace_path=trace_path,
            )
            failures += 1
            paused = isinstance(exc, ProviderPausedError)
        _append_jsonl(permit.raw_path, record)
        if paused:
            break
    return {
        "provider_id": provider_id,
        "stage": stage,
        "selected": len(selected),
        "executed": completed + failures,
        "completed": completed,
        "pre_response_failures": failures,
        "paused_after_429_or_budget": paused,
        "raw_path": str(permit.raw_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(EXPECTED_COUNTS), required=True)
    parser.add_argument("--stage", choices=("canary", "remaining", "all"), required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    summary = run_provider(
        args.provider,
        stage=args.stage,
        config_path=args.config,
        retry_failed=args.retry_failed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
