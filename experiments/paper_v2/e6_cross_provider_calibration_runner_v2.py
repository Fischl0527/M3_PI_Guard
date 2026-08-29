"""Prospective E6-v2 runner with isolated physical-attempt recovery.

E6-v1 records, ledgers, stops, and window artifacts are immutable.  This module
reuses only the frozen v1 *case membership and logical work keys* while deriving
new study, run, execution, output, trace, call-ledger, and stop identities.  It
reads the immutable v1 W2 seal solely as a fail-closed W3 timing prerequisite;
it never mutates any E6-v1 output path.

The only generic recovery admitted here is one explicit outer attempt 2 for the
single unresolved work key whose complete v2 execution history is response-less
and contains a valid pretransport payload commitment.  HTTP 429 is never
converted into this generic recovery and closes as a W3 diagnostic terminal.
"""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.e6_cross_provider_calibration_runner_v1 as e6_v1
import experiments.paper_v2.deepseek_json_client_v2 as deepseek_json
import experiments.paper_v2.formal_matrix_controller_v2 as medium_v2
import experiments.paper_v2.gemini_json_client_v1 as gemini_json
import experiments.paper_v2.incremental_study_runner_v1 as incremental
import experiments.paper_v2.lean_empirical_runner as lean
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
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
    ProviderPayloadError,
    ProviderTransportError,
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
SOURCE_PROTOCOL_ROOT = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/e6_cross_provider_calibration_v1"
)
PROTOCOL_ROOT = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/e6_cross_provider_calibration_v2"
)
MANIFEST_PATH = PROTOCOL_ROOT / "manifest_v2.json"
OUTPUT_ROOT = PROJECT_ROOT / "outputs/experiments/e6_cross_provider_calibration_v2"
SOURCE_PLAN_PATHS = copy.deepcopy(e6_v1.PLAN_PATHS)
PROVIDER_ROOT_NAMES = copy.deepcopy(e6_v1.PROVIDER_ROOT_NAMES)
EXPECTED_MODELS = copy.deepcopy(e6_v1.EXPECTED_MODELS)
EXPECTED_COUNTS = copy.deepcopy(e6_v1.EXPECTED_COUNTS)
EXPECTED_WINDOW_COUNTS = copy.deepcopy(e6_v1.EXPECTED_WINDOW_COUNTS)
WINDOWS = e6_v1.WINDOWS
PROSPECTIVE_EXECUTION_WINDOWS = ("W3",)
PREFIX_ROWS = e6_v1.PREFIX_ROWS
MAX_TOKENS = e6_v1.MAX_TOKENS
TIMEOUT_SECONDS = e6_v1.TIMEOUT_SECONDS
STUDY_ID = "m3-q2-e6-cross-provider-calibration-v2"
SCHEMA_VERSION = "m3-paper-v2-e6-raw-record-2.0"
GENERIC_RECOVERY_ATTEMPT = 2
MIN_PREDECESSOR_START_DELTA = timedelta(hours=18)
MAX_PREDECESSOR_START_DELTA = timedelta(hours=30)
MAX_WINDOW_DURATION = timedelta(hours=12)
V1_W2_SEAL_PATHS = {
    provider_id: e6_v1._seal_path(provider_id, "W2")
    for provider_id in EXPECTED_MODELS
}


class E6CalibrationRunnerV2Error(RuntimeError):
    """Raised when prospective E6-v2 cannot preserve its repair contract."""


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _parse_aware_timestamp(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise E6CalibrationRunnerV2Error(
            f"E6-v2 prerequisite has no valid {field_name}"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise E6CalibrationRunnerV2Error(
            f"E6-v2 prerequisite has invalid {field_name}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise E6CalibrationRunnerV2Error(
            f"E6-v2 prerequisite {field_name} must be timezone-aware"
        )
    return parsed


def _validate_w3_predecessor_seal(provider_id: str) -> dict[str, Any]:
    """Require an immutable v1 W2 seal and the frozen 18--30 hour start gap."""

    try:
        seal_path = V1_W2_SEAL_PATHS[provider_id]
    except KeyError as exc:
        raise E6CalibrationRunnerV2Error(
            f"unsupported E6-v2 provider: {provider_id}"
        ) from exc
    if not seal_path.is_file():
        raise E6CalibrationRunnerV2Error(
            f"{provider_id}: immutable E6-v1 W2 seal is absent; W3 is not eligible"
        )
    try:
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise E6CalibrationRunnerV2Error(
            f"{provider_id}: immutable E6-v1 W2 seal is unreadable"
        ) from exc
    if (
        seal.get("study_id") != e6_v1.STUDY_ID
        or seal.get("provider_id") != provider_id
        or seal.get("replicate_window") != "W2"
        or seal.get("status") != "sealed"
    ):
        raise E6CalibrationRunnerV2Error(
            f"{provider_id}: immutable E6-v1 W2 seal identity/status mismatch"
        )
    predecessor_started = _parse_aware_timestamp(
        seal.get("window_started_at"), field_name="W2 window_started_at"
    )
    current_time = _parse_aware_timestamp(_now(), field_name="current time")
    state_path = _window_state_path(provider_id, "W3")
    existing_state: dict[str, Any] | None = None
    if state_path.is_file():
        try:
            existing_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise E6CalibrationRunnerV2Error(
                f"{provider_id}: existing E6-v2 W3 state is unreadable"
            ) from exc
        if (
            existing_state.get("study_id") != STUDY_ID
            or existing_state.get("provider_id") != provider_id
            or existing_state.get("replicate_window") != "W3"
            or existing_state.get("status") != "running"
        ):
            raise E6CalibrationRunnerV2Error(
                f"{provider_id}: existing E6-v2 W3 state identity/status mismatch"
            )
    prospective_started = _parse_aware_timestamp(
        (
            existing_state.get("window_started_at")
            if existing_state is not None
            else current_time.isoformat()
        ),
        field_name="prospective W3 window_started_at",
    )
    start_delta = prospective_started - predecessor_started
    if not MIN_PREDECESSOR_START_DELTA <= start_delta <= MAX_PREDECESSOR_START_DELTA:
        raise E6CalibrationRunnerV2Error(
            f"{provider_id}: W3 start is outside the frozen 18-30 hour interval"
        )
    if existing_state is not None:
        elapsed = current_time - prospective_started
        if not timedelta(0) <= elapsed <= MAX_WINDOW_DURATION:
            raise E6CalibrationRunnerV2Error(
                f"{provider_id}: existing W3 state is outside the 12-hour window duration"
            )
    return {
        "provider_id": provider_id,
        "predecessor_window": "W2",
        "predecessor_status": "sealed",
        "prospective_window_started_at": prospective_started.isoformat(),
        "resuming_existing_window": existing_state is not None,
        "start_delta_seconds": start_delta.total_seconds(),
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _provider_root(provider_id: str) -> Path:
    try:
        return OUTPUT_ROOT / PROVIDER_ROOT_NAMES[provider_id]
    except KeyError as exc:
        raise E6CalibrationRunnerV2Error(
            f"unsupported E6-v2 provider: {provider_id}"
        ) from exc


def _raw_path(provider_id: str) -> Path:
    return _provider_root(provider_id) / "raw_records_v2.jsonl"


def _gate_path(provider_id: str, window: str) -> Path:
    return _provider_root(provider_id) / f"window_gate_{window}_v2.json"


def _window_state_path(provider_id: str, window: str) -> Path:
    return _provider_root(provider_id) / "internal" / f"window_state_{window}_v2.json"


def _provider_stop_path(provider_id: str) -> Path:
    return _provider_root(provider_id) / "internal/provider_stop_v2.json"


def _execution_identity(provider_id: str, window: str) -> str:
    return sha256_canonical_json(
        {
            "schema_version": "m3-paper-v2-e6-execution-identity-2.0",
            "study_id": STUDY_ID,
            "provider_id": provider_id,
            "model_id": EXPECTED_MODELS[provider_id],
            "replicate_window": window,
            "source_design": "e6-cross-provider-calibration-v1",
            "repair_contract": "isolated-generic-response-less-attempt-2",
        }
    )


def _project_v2_row(source: Mapping[str, Any]) -> dict[str, Any]:
    provider_id = str(source["provider_id"])
    window = str(source["replicate_window"])
    value = copy.deepcopy(dict(source))
    value.update(
        {
            "schema_version": "m3-paper-v2-e6-work-item-2.0",
            "study_id": STUDY_ID,
            "run_id": f"e6-v2-{provider_id}-{window}",
            "execution_identity": _execution_identity(provider_id, window),
            "source_protocol_version": "e6-cross-provider-calibration-v1",
            "source_v1_work_key": str(source["work_key"]),
            "repair_protocol_version": "e6-response-less-recovery-v2",
        }
    )
    return value


def _load_plan(provider_id: str) -> list[dict[str, Any]]:
    if provider_id not in EXPECTED_COUNTS:
        raise E6CalibrationRunnerV2Error(f"unsupported provider: {provider_id}")
    if not MANIFEST_PATH.is_file():
        raise E6CalibrationRunnerV2Error("E6-v2 manifest is missing")
    # This reads only the frozen v1 protocol plan.  It never reads v1 outputs.
    rows = [_project_v2_row(row) for row in e6_v1._load_plan(provider_id)]
    if (
        len(rows) != EXPECTED_COUNTS[provider_id]
        or len({str(row["work_key"]) for row in rows}) != len(rows)
        or any(row["study_id"] != STUDY_ID for row in rows)
    ):
        raise E6CalibrationRunnerV2Error("E6-v2 projected plan identity drift")
    return rows


def _window_rows(provider_id: str, window: str) -> list[dict[str, Any]]:
    if window not in WINDOWS:
        raise E6CalibrationRunnerV2Error(f"unsupported E6-v2 window: {window}")
    rows = [
        row for row in _load_plan(provider_id) if row["replicate_window"] == window
    ]
    if len(rows) != EXPECTED_WINDOW_COUNTS[provider_id]:
        raise E6CalibrationRunnerV2Error("E6-v2 projected window count drift")
    return rows


def _execution_history(provider_id: str) -> dict[str, list[dict[str, Any]]]:
    histories: dict[str, list[dict[str, Any]]] = {}
    for row in lean._read_jsonl(_raw_path(provider_id)):
        if row.get("study_id") != STUDY_ID or row.get("schema_version") != SCHEMA_VERSION:
            raise E6CalibrationRunnerV2Error("E6-v2 raw record identity drift")
        key = row.get("work_key")
        attempt = row.get("attempt")
        if (
            not isinstance(key, str)
            or not key
            or isinstance(attempt, bool)
            or not isinstance(attempt, int)
            or attempt not in {1, GENERIC_RECOVERY_ATTEMPT}
        ):
            raise E6CalibrationRunnerV2Error("E6-v2 raw attempt identity drift")
        history = histories.setdefault(key, [])
        if history and attempt <= int(history[-1]["attempt"]):
            raise E6CalibrationRunnerV2Error("E6-v2 attempts are not append-only")
        history.append(copy.deepcopy(dict(row)))
    return histories


def _latest_records(provider_id: str) -> dict[str, dict[str, Any]]:
    return {
        key: copy.deepcopy(history[-1])
        for key, history in _execution_history(provider_id).items()
    }


def _is_terminal(row: Mapping[str, Any]) -> bool:
    return row.get("terminal_status") is True


def _has_response_evidence(row: Mapping[str, Any]) -> bool:
    if row.get("response_obtained") is True:
        return True
    requests = row.get("provider_requests")
    return isinstance(requests, list) and any(
        isinstance(request, Mapping)
        and bool(
            request.get("provider_response_id")
            or request.get("response_id")
        )
        for request in requests
    )


def _is_manual_429(row: Mapping[str, Any]) -> bool:
    return bool(
        row.get("manual_429_recovery_required") is True
        or row.get("operational_status") == "pre_response_rate_limited"
        or row.get("error_type") == "ProviderPausedError"
    )


def _payload_commitments(row: Mapping[str, Any]) -> dict[int, str] | None:
    requests = row.get("provider_requests")
    if not isinstance(requests, list) or not requests:
        return None
    commitments: dict[int, str] = {}
    for index, request in enumerate(requests, start=1):
        digest = request.get("payload_sha256") if isinstance(request, Mapping) else None
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            return None
        commitments[index] = digest
    return commitments


def _validate_generic_recovery_history(
    history: Sequence[Mapping[str, Any]],
) -> None:
    if len(history) != 1:
        raise E6CalibrationRunnerV2Error(
            "generic recovery requires exactly one prior outer attempt"
        )
    latest = history[-1]
    if int(latest.get("attempt", 0)) != 1:
        raise E6CalibrationRunnerV2Error("generic recovery requires latest attempt 1")
    if _is_manual_429(latest):
        raise E6CalibrationRunnerV2Error(
            "HTTP 429 is a W3 diagnostic terminal, not generic recovery"
        )
    if _is_terminal(latest) or latest.get("retry_eligible") is not True:
        raise E6CalibrationRunnerV2Error("generic recovery is not eligible")
    if any(_has_response_evidence(row) for row in history):
        raise E6CalibrationRunnerV2Error(
            "response-bearing work cannot enter generic recovery"
        )
    if _payload_commitments(latest) is None:
        raise E6CalibrationRunnerV2Error(
            "generic recovery requires a valid pretransport payload commitment"
        )


def _expected_recovery_payloads(permit: lean.LeanPermit) -> dict[int, str]:
    if _physical_attempt_namespace(permit) != GENERIC_RECOVERY_ATTEMPT:
        return {}
    work_key = str(permit.work_items[0]["work_key"])
    history = _execution_history(permit.provider_id).get(work_key, [])
    _validate_generic_recovery_history(history)
    commitments = _payload_commitments(history[-1])
    if commitments is None:  # guarded above; retain a local fail-closed assertion
        raise E6CalibrationRunnerV2Error(
            "generic recovery payload commitment disappeared"
        )
    return commitments


class _PayloadBoundRecoveryClient:
    """Fail before transport if outer attempt 2 changes canonical payload."""

    def __init__(
        self,
        client: Any,
        *,
        expected_payloads: Mapping[int, str],
        payload_digest: Callable[[Sequence[Mapping[str, str]]], str],
    ) -> None:
        self._client = client
        self._expected_payloads = dict(expected_payloads)
        self._payload_digest = payload_digest

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> Any:
        expected = self._expected_payloads.get(step)
        if expected is None:
            raise ProviderPayloadError(
                "recovery call has no attempt-1 payload commitment"
            )
        if self._payload_digest(messages) != expected:
            raise ProviderPayloadError(
                "recovery canonical payload differs from attempt 1"
            )
        return self._client.complete(
            messages,
            case=case,
            step=step,
            observations=observations,
        )


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
    selected_by_key = {str(row["work_key"]): row for row in selected}
    retry_keys = tuple(dict.fromkeys(retry_failed_work_keys))
    if len(retry_keys) != len(tuple(retry_failed_work_keys)):
        raise E6CalibrationRunnerV2Error("duplicate retry key")
    if set(retry_keys) - set(selected_by_key):
        raise E6CalibrationRunnerV2Error("retry key is outside the selected window")

    histories = _execution_history(provider_id)
    unresolved = {
        key
        for key, history in histories.items()
        if key in selected_by_key and not _is_terminal(history[-1])
    }
    if retry_keys:
        if (
            len(retry_keys) == 1
            and retry_keys[0] in histories
            and _is_manual_429(histories[retry_keys[0]][-1])
        ):
            raise E6CalibrationRunnerV2Error(
                "E6-v2 closes W3 HTTP 429 as diagnostic terminal; generic recovery is forbidden"
            )
        if len(retry_keys) != 1 or unresolved != set(retry_keys):
            raise E6CalibrationRunnerV2Error(
                "generic recovery requires the unique unresolved work key"
            )
        key = retry_keys[0]
        _validate_generic_recovery_history(histories[key])
        return all_rows, [(selected_by_key[key], GENERIC_RECOVERY_ATTEMPT)]
    if unresolved:
        if any(_is_manual_429(histories[key][-1]) for key in unresolved):
            raise E6CalibrationRunnerV2Error(
                "HTTP 429 is closed as a W3 diagnostic terminal"
            )
        raise E6CalibrationRunnerV2Error(
            "response-less row requires explicit unique-key recovery"
        )

    pending = [
        (row, 1)
        for row in selected
        if str(row["work_key"]) not in histories
    ]
    return all_rows, pending


def _physical_attempt_namespace(permit: lean.LeanPermit) -> int:
    values = {int(value) for value in permit.attempt_by_work_key.values()}
    if len(values) != 1:
        raise E6CalibrationRunnerV2Error(
            "one dispatcher may serve only one physical attempt namespace"
        )
    namespace = values.pop()
    if namespace not in {1, GENERIC_RECOVERY_ATTEMPT}:
        raise E6CalibrationRunnerV2Error("unsupported physical attempt namespace")
    return namespace


def _attempt_paths(
    provider_id: str,
    window: str,
    attempts: Mapping[str, int],
) -> tuple[Path, Path, Path]:
    namespaces = set(attempts.values())
    if len(namespaces) != 1:
        raise E6CalibrationRunnerV2Error("mixed physical attempt namespaces")
    namespace = namespaces.pop()
    root = _provider_root(provider_id) / "internal"
    if namespace == 1:
        return (
            root / "provider_traces" / window / "attempt1",
            root / "budget_ledgers" / f"{window}_attempt1.jsonl",
            root / "call_ledgers" / f"{window}_attempt1.jsonl",
        )
    if len(attempts) != 1:
        raise E6CalibrationRunnerV2Error(
            "generic attempt 2 must have exactly one work key"
        )
    work_key = next(iter(attempts))
    recovery = root / "generic_recovery_attempt2" / window / work_key
    return (
        recovery / "provider_traces",
        recovery / "budget_events.jsonl",
        recovery / "call_events.jsonl",
    )


def _permit(
    provider_id: str,
    window: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    attempts: Mapping[str, int],
) -> lean.LeanPermit:
    if not rows or set(attempts) != {str(row["work_key"]) for row in rows}:
        raise E6CalibrationRunnerV2Error("permit attempt map does not bind its rows")
    run_ids = {str(row["run_id"]) for row in rows}
    identities = {str(row["execution_identity"]) for row in rows}
    if len(run_ids) != 1 or len(identities) != 1:
        raise E6CalibrationRunnerV2Error("permit rows mix v2 execution identity")
    trace_root, budget_path, call_path = _attempt_paths(
        provider_id, window, attempts
    )
    return lean.LeanPermit(
        provider_id=provider_id,
        run_id=run_ids.pop(),
        execution_identity=identities.pop(),
        work_items=tuple(copy.deepcopy(dict(row)) for row in rows),
        output_root=_provider_root(provider_id),
        raw_path=_raw_path(provider_id),
        trace_root=trace_root,
        budget_path=budget_path,
        call_path=call_path,
        max_tokens=MAX_TOKENS,
        timeout_seconds=TIMEOUT_SECONDS,
        plan_manifest_sha256=hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        attempt_by_work_key=copy.deepcopy(dict(attempts)),
    )


def _deepseek_spend_cny() -> float:
    total = 0.0
    for row in _latest_records("deepseek").values():
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
        raise E6CalibrationRunnerV2Error("DeepSeek policy is missing")
    remaining = 1_000.0 - _deepseek_spend_cny()
    if remaining <= 0:
        raise E6CalibrationRunnerV2Error("E6-v2 runaway protection is exhausted")
    deepseek["hard_spend_limit_cny"] = remaining
    deepseek["abort_ceiling_cny"] = remaining
    deepseek["abort_at_fraction"] = 1.0
    return policy


def _allow_pinned_synthetic_labels(benchmark: str) -> bool:
    if benchmark == "agentdojo-v1":
        return True
    if benchmark == "m3-v2":
        return False
    raise E6CalibrationRunnerV2Error(
        f"unsupported benchmark for source-pinned label policy: {benchmark}"
    )


def _deepseek_dispatcher(
    permit: lean.LeanPermit,
    *,
    api_key: str,
    role_policy: Mapping[str, Any],
    known_work_items: Sequence[Mapping[str, Any]],
    recorded_at: Callable[[], str] = _now,
) -> Any:
    namespace = _physical_attempt_namespace(permit)
    expected_payloads = _expected_recovery_payloads(permit)
    registry = lean.TracedClientRegistry()
    plan_path = SOURCE_PLAN_PATHS["deepseek"]
    agentdojo = PublicFrozenAgentDojoCaseResolverV2(plan_path=plan_path)
    public_m3 = PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity, plan_path=plan_path
    )
    known_keys = {str(row["work_key"]) for row in known_work_items}
    model_role = str(role_policy["public_model_role"])
    tracker = lean.PublicBudgetTracker(
        permit.budget_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role=model_role,
        known_work_keys=known_keys,
        role_policy=role_policy,
    )

    def provider_factory(context: OnlineExecutorContext) -> Any:
        allow_pinned_labels = _allow_pinned_synthetic_labels(context.benchmark)
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        client = lean.PublicDeepSeekJsonOfficialClient(
            provider_id="deepseek",
            api_key=api_key,
            content_class=content_class,
            budget_state=lean.PublicProviderBudgetState("deepseek", role_policy),
            policy=role_policy,
            model_role=model_role,
            temperature=0.0,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
            network_consent=True,
            allow_pinned_synthetic_credential_labels=allow_pinned_labels,
        )
        budgeted = lean.PublicBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
            recorded_at=recorded_at,
        )
        traced: Any = lean.PublicDeepSeekJsonTracedProviderClient(
            budgeted,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=lean._provider_trace_path(permit, context.work_key),
            recorded_at=recorded_at,
            physical_attempt_namespace=namespace,
        )
        if expected_payloads:
            traced = _PayloadBoundRecoveryClient(
                traced,
                expected_payloads=expected_payloads,
                payload_digest=lambda messages: sha256_canonical_json(
                    deepseek_json._payload(budgeted, messages)
                ),
            )
        return registry.register(context.work_key, traced)

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
        detector=lean.PinnedPromptGuardDetector(device="cuda"),
        vigil_factory=medium_v2.RedactedVigilConstraintFactory(),
        recorded_at=recorded_at,
        physical_attempt_namespace=namespace,
    )
    trusted = lean.TrustedContextBoundaryRuntimeV3(
        live, client_lookup=registry.get, recorded_at=recorded_at
    )
    return build_e6_calibration_condition_dispatcher(
        runtime=medium_v2.FailureTierNormalizingRuntime(trusted),
        evaluator=lean._offline_evaluator(agentdojo=agentdojo, m3=public_m3),
    )


def _gemini_dispatcher(
    permit: lean.LeanPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    recorded_at: Callable[[], str] = _now,
) -> Any:
    namespace = _physical_attempt_namespace(permit)
    expected_payloads = _expected_recovery_payloads(permit)
    registry = lean.gemini_public_v1._Registry()
    plan_path = SOURCE_PLAN_PATHS["gemini"]
    agentdojo = PublicFrozenAgentDojoCaseResolverV2(plan_path=plan_path)
    public_m3 = PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity, plan_path=plan_path
    )
    call_sink = lean.gemini_fallback.GeminiCallLedgerSink(
        permit.call_path,
        execution_identity=permit.execution_identity,
        model_id=EXPECTED_MODELS["gemini"],
    )
    budget_events = load_call_events(permit.call_path)
    if namespace == GENERIC_RECOVERY_ATTEMPT:
        attempt1_path = (
            _provider_root("gemini")
            / "internal/call_ledgers"
            / f"{str(permit.work_items[0]['replicate_window'])}_attempt1.jsonl"
        )
        budget_events = [*load_call_events(attempt1_path), *budget_events]
    budget_state = lean._gemini_budget_state(budget_events, policy)
    usage_registry = GeminiUsageRegistry()
    traced_factory = functools.partial(
        GeminiJsonTracedProviderClient,
        usage_registry=usage_registry,
        physical_attempt_namespace=namespace,
    )

    def provider_factory(context: OnlineExecutorContext) -> Any:
        allow_pinned_labels = _allow_pinned_synthetic_labels(context.benchmark)
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
            allow_pinned_synthetic_credential_labels=allow_pinned_labels,
        )
        traced: Any = traced_factory(
            client,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=lean._provider_trace_path(permit, context.work_key),
            admission_manifest_sha256=permit.plan_manifest_sha256,
            recorded_at=recorded_at,
        )
        if expected_payloads:
            traced = _PayloadBoundRecoveryClient(
                traced,
                expected_payloads=expected_payloads,
                payload_digest=lambda messages: sha256_canonical_json(
                    gemini_json._payload(client, messages)
                ),
            )
        return registry.register(context.work_key, traced)

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
        physical_attempt_namespace=namespace,
    )
    trusted = lean.TrustedContextBoundaryRuntimeV3(
        live, client_lookup=registry.get, recorded_at=recorded_at
    )
    runtime = lean.gemini_trace_v2.GeminiTraceAttachingRuntimeV2(
        trusted, client_lookup=registry.get
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
        return _deepseek_dispatcher(
            permit,
            api_key=api_key,
            role_policy=policy,
            known_work_items=all_rows,
        )
    policy = lean._gemini_policy()
    lean.gemini_fallback._validate_runtime_config(values, policy)
    if values.get("FRONTIER_GEMINI_MODEL_ID") != EXPECTED_MODELS["gemini"]:
        raise E6CalibrationRunnerV2Error("Gemini model identity drift")
    key_field = lean.gemini_fallback.PROVIDER_CONFIG["gemini"]["api_key"]
    return _gemini_dispatcher(
        permit,
        api_key=str(values[key_field]),
        policy=policy,
    )


def _is_fatal_contract_error(exc: Exception) -> bool:
    if isinstance(exc, ProviderPausedError):
        return False
    return not isinstance(exc, ProviderTransportError)


def _is_fatal_runtime_failure(result: Mapping[str, Any]) -> bool:
    if result.get("operational_status") != "provider_failure":
        return False
    diagnostic = _runtime_failure_diagnostic(result)
    if diagnostic is None:
        return True
    return diagnostic.get("failure_class") not in {
        "ProviderTransportError",
        "ProviderPausedError",
    }


def _runtime_failure_diagnostic(result: Mapping[str, Any]) -> dict[str, Any] | None:
    supplied = result.get("runtime_failure_diagnostic")
    if isinstance(supplied, Mapping):
        return {
            "failure_stage": supplied.get("failure_stage"),
            "failure_class": supplied.get("failure_class"),
            "provider_call_index": supplied.get("provider_call_index"),
            "http_category": supplied.get(
                "http_category", supplied.get("http_status_class")
            ),
        }
    top_level_fields = (
        "failure_stage",
        "failure_class",
        "provider_call_index",
        "http_category",
    )
    if all(field in result for field in top_level_fields):
        return {field: result[field] for field in top_level_fields}
    events = result.get("runtime_visibility_events")
    if not isinstance(events, list):
        return None
    for event in reversed(events):
        if not isinstance(event, Mapping):
            continue
        observation = event.get("observation")
        if (
            event.get("parse_error_code") != "provider_failure"
            and not (
                isinstance(observation, Mapping)
                and observation.get("status") == "provider_failure"
            )
        ):
            continue
        error_class = (
            observation.get("error_type")
            if isinstance(observation, Mapping)
            else None
        )
        return {
            "failure_stage": "provider_call",
            "failure_class": error_class or "provider_failure",
            "provider_call_index": event.get("provider_call_index", event.get("step")),
            "http_category": event.get("http_category", "not_observed"),
        }
    return None


def _enrich_record(
    base: Mapping[str, Any],
    work_item: Mapping[str, Any],
    *,
    result: Mapping[str, Any] | None,
    attempt: int,
    paused: bool,
    fatal: bool,
    window_started_at: str,
) -> dict[str, Any]:
    value = e6_v1._enrich_record(
        base,
        work_item,
        result=result,
        window_started_at=window_started_at,
    )
    value.update(
        {
            "schema_version": SCHEMA_VERSION,
            "study_id": STUDY_ID,
            "physical_attempt_namespace": attempt,
            "source_protocol_version": "e6-cross-provider-calibration-v1",
            "repair_protocol_version": "e6-response-less-recovery-v2",
            "manual_429_recovery_required": False,
            "underlying_manual_429_ledger_semantics_unchanged": paused,
        }
    )
    if result is not None:
        diagnostic = _runtime_failure_diagnostic(result)
        if diagnostic is not None:
            value["runtime_failure_diagnostic"] = diagnostic
    response_less = not _has_response_evidence(value)
    if fatal:
        value.update(
            {
                "retry_eligible": False,
                "included_in_primary_itt": True,
                "terminal_status": True,
            }
        )
    elif paused:
        value.update(
            {
                "retry_eligible": False,
                "included_in_primary_itt": True,
                "terminal_status": True,
                "protocol_terminal_reason": "w3_429_diagnostic_terminal",
            }
        )
    elif response_less:
        has_payload_commitment = _payload_commitments(value) is not None
        retry_eligible = attempt == 1 and has_payload_commitment
        value.update(
            {
                "retry_eligible": retry_eligible,
                "included_in_primary_itt": not retry_eligible,
                "terminal_status": not retry_eligible,
            }
        )
        if attempt == 1 and not has_payload_commitment:
            value["protocol_terminal_reason"] = (
                "no_pretransport_payload_commitment"
            )
    else:
        value.update(
            {
                "retry_eligible": False,
                "included_in_primary_itt": True,
                "terminal_status": True,
            }
        )
    return value


def _systemic_failure_key(row: Mapping[str, Any]) -> str | None:
    status = str(row.get("operational_status", ""))
    if status == "provider_failure":
        diagnostic = row.get("runtime_failure_diagnostic")
        failure_class = (
            diagnostic.get("failure_class")
            if isinstance(diagnostic, Mapping)
            else None
        )
        return f"runtime_provider_failure:{failure_class or 'unknown'}"
    if status in {
        "pre_response_transport_failure",
        "post_response_runner_failure",
        "contract_failure",
    }:
        return f"{status}:{row.get('error_type') or 'unknown'}"
    return None


def evaluate_window_gate(provider_id: str, window: str) -> dict[str, Any]:
    prefix = [
        row for row in _window_rows(provider_id, window) if row["formal_prefix"] is True
    ]
    latest = _latest_records(provider_id)
    actual = [latest[str(row["work_key"])] for row in prefix if str(row["work_key"]) in latest]
    expected_model = EXPECTED_MODELS[provider_id]
    response_bearing = [row for row in actual if _has_response_evidence(row)]
    exact_model = bool(response_bearing) and all(
        row.get("returned_models") == [expected_model]
        and row.get("returned_model_id") == expected_model
        for row in response_bearing
    )
    complete_chain = len(actual) == PREFIX_ROWS and all(
        _has_response_evidence(row)
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
    parseable = sum(row.get("operational_status") == "completed" for row in actual)
    field_isolation = len(actual) == PREFIX_ROWS and all(
        row.get("online_forbidden_fields_present") is False for row in actual
    )
    no_tools_or_effects = len(actual) == PREFIX_ROWS and all(
        row.get("provider_tools_enabled") is False
        and row.get("external_effects_enabled") is False
        for row in actual
    )
    systemic = Counter(
        key for row in actual if (key := _systemic_failure_key(row)) is not None
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
    value = {
        "schema_version": "m3-paper-v2-e6-window-gate-2.0",
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
        "systemic_failure_counts": dict(sorted(systemic.items())),
        "runtime_provider_failure_rows": sum(
            row.get("operational_status") == "provider_failure" for row in actual
        ),
        "gemini_free_tier_usd_zero": free_tier,
        "scientific_outcomes_inspected": False,
    }
    _write_json(_gate_path(provider_id, window), value)
    return value


def _ensure_window_state(
    provider_id: str, window: str, *, window_started_at: str
) -> dict[str, Any]:
    path = _window_state_path(provider_id, window)
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8"))
        if (
            value.get("study_id") != STUDY_ID
            or value.get("provider_id") != provider_id
            or value.get("replicate_window") != window
        ):
            raise E6CalibrationRunnerV2Error("E6-v2 window-state identity drift")
        return value
    value = {
        "schema_version": "m3-paper-v2-e6-window-state-2.0",
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "replicate_window": window,
        "window_started_at": window_started_at,
        "status": "running",
    }
    _write_json(path, value)
    return value


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
) -> dict[str, Any]:
    if window not in PROSPECTIVE_EXECUTION_WINDOWS:
        raise E6CalibrationRunnerV2Error(
            "E6-v2 provider execution is prospective W3-only; W1/W2 remain immutable"
        )
    prerequisite = _validate_w3_predecessor_seal(provider_id)
    stop_path = _provider_stop_path(provider_id)
    if stop_path.is_file():
        raise E6CalibrationRunnerV2Error(
            f"{provider_id}: E6-v2 provider is stopped by a fatal boundary"
        )
    all_rows, pending = _selected_pending(
        provider_id,
        window,
        canary_only=canary_only,
        retry_failed_work_keys=retry_failed_work_keys,
    )
    if not canary_only:
        gate_path = _gate_path(provider_id, window)
        if not gate_path.is_file() or json.loads(
            gate_path.read_text(encoding="utf-8")
        ).get("gate_passed") is not True:
            raise E6CalibrationRunnerV2Error("formal E6-v2 prefix gate did not pass")
    if not pending:
        gate = evaluate_window_gate(provider_id, window)
        return {
            "provider_id": provider_id,
            "replicate_window": window,
            "executed": 0,
            "window_gate_passed": bool(gate["gate_passed"]),
        }

    state = _ensure_window_state(
        provider_id,
        window,
        window_started_at=str(prerequisite["prospective_window_started_at"]),
    )
    attempts = {str(row["work_key"]): attempt for row, attempt in pending}
    permit = _permit(
        provider_id,
        window,
        [row for row, _ in pending],
        attempts=attempts,
    )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    dispatcher = (
        dispatcher_factory(permit, provider_id, all_rows)
        if dispatcher_factory is not None
        else _dispatcher(provider_id, permit, values=values, all_rows=all_rows)
    )

    executed = 0
    stopped_after_response_less = False
    for work_item, attempt in pending:
        trace_path = lean._provider_trace_path(permit, str(work_item["work_key"]))
        result: dict[str, Any] | None = None
        paused = False
        fatal = False
        try:
            hydrated, online_state, digest = lean._hydrate_work_item(work_item)
            result = dict(dispatcher.execute(hydrated, online_state))
            fatal = _is_fatal_runtime_failure(result)
            base = lean._success_record(
                work_item,
                result,
                digest,
                attempt=attempt,
                trace_path=trace_path,
            )
            if fatal:
                diagnostic = _runtime_failure_diagnostic(result)
                base["error_type"] = (
                    diagnostic.get("failure_class")
                    if diagnostic is not None
                    else "UnclassifiedRuntimeProviderFailure"
                )
        except Exception as exc:
            base = lean._failure_record(
                work_item, exc, attempt=attempt, trace_path=trace_path
            )
            paused = isinstance(exc, ProviderPausedError)
            fatal = _is_fatal_contract_error(exc)
            if paused:
                base["operational_status"] = "pre_response_rate_limited"
            elif fatal:
                base["operational_status"] = "contract_failure"
            else:
                base["operational_status"] = "pre_response_transport_failure"
            base["error_type"] = type(exc).__name__
        record = _enrich_record(
            base,
            work_item,
            result=result,
            attempt=attempt,
            paused=paused,
            fatal=fatal,
            window_started_at=str(state["window_started_at"]),
        )
        lean._append_jsonl(_raw_path(provider_id), record)
        if fatal:
            _write_json(
                stop_path,
                {
                    "schema_version": "m3-paper-v2-e6-provider-stop-2.0",
                    "study_id": STUDY_ID,
                    "provider_id": provider_id,
                    "replicate_window": window,
                    "work_key": work_item["work_key"],
                    "error_type": record.get("error_type"),
                    "status": "stopped_fatal_contract_boundary",
                    "recorded_at": record.get("recorded_at"),
                },
            )
        executed += 1
        if not _has_response_evidence(record):
            stopped_after_response_less = True
            break

    gate = evaluate_window_gate(provider_id, window)
    return {
        "provider_id": provider_id,
        "replicate_window": window,
        "selected": PREFIX_ROWS if canary_only else len(all_rows),
        "executed": executed,
        "stopped_after_response_less_failure": stopped_after_response_less,
        "window_gate_passed": bool(gate["gate_passed"]),
        "raw_path": str(_raw_path(provider_id)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=tuple(EXPECTED_COUNTS), required=True)
    parser.add_argument(
        "--window", choices=PROSPECTIVE_EXECUTION_WINDOWS, required=True
    )
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--canary-only", action="store_true")
    stage.add_argument("--resume-pending-only", action="store_true")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--retry-failed-work-key", action="append", default=[])
    return parser


def main() -> int:
    args = build_parser().parse_args()
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
