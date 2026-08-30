"""Prospective E6-v2 runner with isolated physical-attempt recovery.

E6-v1 records, ledgers, stops, and window artifacts are immutable.  This module
reuses only the frozen v1 *case membership and source work-key mapping* while
deriving new study, work, run, execution, output, trace, call-ledger, and stop
identities.  The
untouched source-W3 rows form one immediately runnable diagnostic execution
block; they are not a third temporal replicate.  This module never
reads or mutates any E6-v1 output path.

The only generic recovery admitted here is one explicit outer attempt 2 for the
single unresolved work key whose complete v2 execution history is response-less
and contains a valid pretransport payload commitment.  HTTP 429 is never
converted into this generic recovery and closes as a diagnostic-block terminal.
"""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
from collections import Counter
from datetime import datetime
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
EXPECTED_WINDOW_COUNTS = copy.deepcopy(e6_v1.EXPECTED_WINDOW_COUNTS)
EXPECTED_COUNTS = copy.deepcopy(EXPECTED_WINDOW_COUNTS)
SOURCE_PLAN_WINDOW = "W3"
EXECUTION_BLOCK_ID = "B1"
PROSPECTIVE_EXECUTION_WINDOWS = (EXECUTION_BLOCK_ID,)
PREFIX_ROWS = e6_v1.PREFIX_ROWS
MAX_TOKENS = e6_v1.MAX_TOKENS
TIMEOUT_SECONDS = e6_v1.TIMEOUT_SECONDS
STUDY_ID = "m3-q2-e6-cross-provider-calibration-v2"
SCHEMA_VERSION = "m3-paper-v2-e6-raw-record-2.0"
PROVIDER_STOP_SCHEMA_VERSION = "m3-paper-v2-e6-provider-stop-2.0"
BLOCK_SEAL_SCHEMA_VERSION = "m3-paper-v2-e6-block-seal-2.0"
GENERIC_RECOVERY_ATTEMPT = 2
EXECUTION_BLOCK_ROLE = "single_diagnostic_execution_block"


class E6CalibrationRunnerV2Error(RuntimeError):
    """Raised when prospective E6-v2 cannot preserve its repair contract."""


def _now() -> str:
    return datetime.now().astimezone().isoformat()


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


def _block_seal_path(provider_id: str, block: str) -> Path:
    return _provider_root(provider_id) / f"block_seal_{block}_v2.json"


def _execution_identity(provider_id: str, window: str) -> str:
    return sha256_canonical_json(
        {
            "schema_version": "m3-paper-v2-e6-execution-identity-2.0",
            "study_id": STUDY_ID,
            "provider_id": provider_id,
            "model_id": EXPECTED_MODELS[provider_id],
            "execution_block_id": window,
            "source_design": "e6-cross-provider-calibration-v1",
            "repair_contract": "immediate-block-isolated-response-less-attempt-2",
        }
    )


def _project_v2_row(source: Mapping[str, Any]) -> dict[str, Any]:
    provider_id = str(source["provider_id"])
    source_window = str(source["replicate_window"])
    if source_window != SOURCE_PLAN_WINDOW:
        raise E6CalibrationRunnerV2Error(
            f"E6-v2 accepts source-{SOURCE_PLAN_WINDOW} rows only"
        )
    source_work_key = str(source["work_key"])
    value = copy.deepcopy(dict(source))
    value.update(
        {
            "schema_version": "m3-paper-v2-e6-work-item-2.0",
            "study_id": STUDY_ID,
            "run_id": f"e6-v2-{provider_id}-{EXECUTION_BLOCK_ID}",
            "execution_identity": _execution_identity(
                provider_id, EXECUTION_BLOCK_ID
            ),
            "work_key": f"e6-v2-immediate__{source_work_key}",
            "source_protocol_version": "e6-cross-provider-calibration-v1",
            "source_v1_work_key": source_work_key,
            "source_replicate_window": source_window,
            "source_replicate_index": source.get("replicate_index"),
            "replicate_window": EXECUTION_BLOCK_ID,
            "replicate_index": 1,
            "sample_role": "risk_enriched_activity_diagnostic",
            "execution_block_id": EXECUTION_BLOCK_ID,
            "repair_protocol_version": "e6-response-less-recovery-v2",
            "execution_block_role": EXECUTION_BLOCK_ROLE,
            "temporal_replication_claim": False,
        }
    )
    return value


def _load_plan(provider_id: str) -> list[dict[str, Any]]:
    if provider_id not in EXPECTED_COUNTS:
        raise E6CalibrationRunnerV2Error(f"unsupported provider: {provider_id}")
    if not MANIFEST_PATH.is_file():
        raise E6CalibrationRunnerV2Error("E6-v2 manifest is missing")
    # This reads only the frozen v1 protocol plan.  It never reads v1 outputs.
    rows = [
        _project_v2_row(row)
        for row in e6_v1._load_plan(provider_id)
        if row.get("replicate_window") == SOURCE_PLAN_WINDOW
    ]
    if (
        len(rows) != EXPECTED_COUNTS[provider_id]
        or len({str(row["work_key"]) for row in rows}) != len(rows)
        or any(row["study_id"] != STUDY_ID for row in rows)
    ):
        raise E6CalibrationRunnerV2Error("E6-v2 projected plan identity drift")
    return rows


def _window_rows(provider_id: str, window: str) -> list[dict[str, Any]]:
    if window not in PROSPECTIVE_EXECUTION_WINDOWS:
        raise E6CalibrationRunnerV2Error(
            f"unsupported E6-v2 execution block: {window}"
        )
    rows = [
        row for row in _load_plan(provider_id) if row["replicate_window"] == window
    ]
    if len(rows) != EXPECTED_WINDOW_COUNTS[provider_id]:
        raise E6CalibrationRunnerV2Error("E6-v2 projected window count drift")
    return rows


def _execution_history(provider_id: str) -> dict[str, list[dict[str, Any]]]:
    histories: dict[str, list[dict[str, Any]]] = {}
    plan_by_key = {
        str(row["work_key"]): row for row in _load_plan(provider_id)
    }
    for row in lean._read_jsonl(_raw_path(provider_id)):
        if row.get("study_id") != STUDY_ID or row.get("schema_version") != SCHEMA_VERSION:
            raise E6CalibrationRunnerV2Error("E6-v2 raw record identity drift")
        key = row.get("work_key")
        attempt = row.get("attempt")
        record_kind = row.get("record_kind")
        if record_kind not in {"execution", "block_closure"}:
            raise E6CalibrationRunnerV2Error("E6-v2 raw record kind drift")
        administrative_closure = record_kind == "block_closure"
        if administrative_closure and (
            row.get("closure_is_model_outcome") is not False
            or row.get("terminal_status") is not True
        ):
            raise E6CalibrationRunnerV2Error(
                "E6-v2 administrative closure contract drift"
            )
        if (
            not isinstance(key, str)
            or not key
            or isinstance(attempt, bool)
            or not isinstance(attempt, int)
            or (
                attempt not in {1, GENERIC_RECOVERY_ATTEMPT}
                and not (attempt == 0 and administrative_closure)
            )
        ):
            raise E6CalibrationRunnerV2Error("E6-v2 raw attempt identity drift")
        expected = plan_by_key.get(key)
        if expected is None:
            raise E6CalibrationRunnerV2Error("E6-v2 raw work key is not planned")
        expected_identity = {
            "run_id": expected["run_id"],
            "execution_identity": expected["execution_identity"],
            "execution_block_id": EXECUTION_BLOCK_ID,
            "execution_block_role": EXECUTION_BLOCK_ROLE,
            "replicate_window": EXECUTION_BLOCK_ID,
            "replicate_index": 1,
            "source_v1_work_key": expected["source_v1_work_key"],
            "source_replicate_window": expected["source_replicate_window"],
            "source_replicate_index": expected["source_replicate_index"],
            "provider_id": expected["provider_id"],
            "model_id": expected["model_id"],
            "configured_model": expected["model_id"],
            "condition_id": expected["condition_id"],
            "case_id": expected["case_id"],
            "underlying_task_id": expected["underlying_task_id"],
            "sample_role": "risk_enriched_activity_diagnostic",
            "temporal_replication_claim": False,
        }
        if any(row.get(field) != value for field, value in expected_identity.items()):
            raise E6CalibrationRunnerV2Error(
                "E6-v2 raw execution identity does not match the frozen plan"
            )
        history = histories.setdefault(key, [])
        if history:
            previous_attempt = int(history[-1]["attempt"])
            same_attempt_closure = (
                attempt == previous_attempt
                and administrative_closure
                and history[-1].get("record_kind") != "block_closure"
            )
            if attempt < previous_attempt or (
                attempt == previous_attempt and not same_attempt_closure
            ):
                raise E6CalibrationRunnerV2Error(
                    "E6-v2 attempts are not append-only"
                )
        history.append(copy.deepcopy(dict(row)))
    return histories


def _latest_records(provider_id: str) -> dict[str, dict[str, Any]]:
    return {
        key: copy.deepcopy(history[-1])
        for key, history in _execution_history(provider_id).items()
    }


def _latest_execution_records(provider_id: str) -> dict[str, dict[str, Any]]:
    """Return the latest physical execution, excluding administrative overlays."""

    latest: dict[str, dict[str, Any]] = {}
    for key, history in _execution_history(provider_id).items():
        executions = [
            row for row in history if row.get("record_kind") != "block_closure"
        ]
        if executions:
            latest[key] = copy.deepcopy(executions[-1])
    return latest


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


def _provider_unavailable_evidence(
    provider_id: str,
) -> dict[str, Any] | None:
    """Return minimal auditable evidence for an explicit unavailable seal.

    The operator flag alone is not evidence.  A rate-limit terminal may close the
    remaining block immediately; a generic transport failure may do so only after
    the single payload-bound recovery attempt has also ended without a response.
    """

    for work_key, history in sorted(_execution_history(provider_id).items()):
        executions = [
            row for row in history if row.get("record_kind") != "block_closure"
        ]
        for row in reversed(executions):
            if _has_response_evidence(row):
                continue
            status = row.get("operational_status")
            attempt = row.get("attempt")
            if status == "pre_response_rate_limited":
                return {
                    "work_key": work_key,
                    "attempt": attempt,
                    "evidence_type": "pre_response_rate_limited",
                }
            if (
                status == "pre_response_transport_failure"
                and attempt == GENERIC_RECOVERY_ATTEMPT
                and row.get("terminal_status") is True
            ):
                return {
                    "work_key": work_key,
                    "attempt": attempt,
                    "evidence_type": "exhausted_response_less_recovery",
                }
    return None


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
            "HTTP 429 is a diagnostic-block terminal, not generic recovery"
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
                "E6-v2 closes diagnostic-block HTTP 429 as a diagnostic terminal; "
                "generic recovery is forbidden"
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
                "HTTP 429 is closed as a diagnostic-block terminal"
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


def _is_fatal_physical_record(row: Mapping[str, Any]) -> bool:
    """Return whether a persisted physical row proves a fatal provider boundary."""

    if (
        row.get("record_kind") != "execution"
        or row.get("terminal_status") is not True
        or row.get("retry_eligible") is not False
        or row.get("included_in_primary_itt") is not True
        or not isinstance(row.get("error_type"), str)
        or not row.get("error_type")
    ):
        return False
    status = row.get("operational_status")
    if status == "contract_failure":
        return True
    if status != "provider_failure":
        return False
    diagnostic = row.get("runtime_failure_diagnostic")
    failure_class = (
        diagnostic.get("failure_class")
        if isinstance(diagnostic, Mapping)
        else row.get("error_type")
    )
    return failure_class not in {
        None,
        "ProviderTransportError",
        "ProviderPausedError",
    }


def _require_provider_stop(
    provider_id: str, block: str
) -> dict[str, Any] | None:
    """Validate a provider stop against the frozen plan and latest raw evidence.

    A stop file is a fail-closed control artifact, not an authority by itself.  It
    is accepted only when it binds the B1 identity and exactly corroborates the
    final physical raw record, which must independently satisfy the fatal-row
    contract.
    """

    path = _provider_stop_path(provider_id)
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    expected_identity = {
        "schema_version": PROVIDER_STOP_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "replicate_window": block,
        "execution_block_id": block,
        "execution_block_role": EXECUTION_BLOCK_ROLE,
        "temporal_replication_claim": False,
        "status": "stopped_fatal_contract_boundary",
        "fatal_boundary": True,
        "terminal_status": True,
    }
    if any(value.get(field) != expected for field, expected in expected_identity.items()):
        raise E6CalibrationRunnerV2Error("E6-v2 provider stop identity drift")

    plan_by_key = {
        str(row["work_key"]): row for row in _window_rows(provider_id, block)
    }
    work_key = value.get("work_key")
    if not isinstance(work_key, str) or work_key not in plan_by_key:
        raise E6CalibrationRunnerV2Error(
            "E6-v2 provider stop work key is not planned"
        )
    if (
        isinstance(value.get("attempt"), bool)
        or value.get("attempt") not in {1, GENERIC_RECOVERY_ATTEMPT}
        or not isinstance(value.get("error_type"), str)
        or not value.get("error_type")
        or value.get("operational_status") not in {
            "contract_failure",
            "provider_failure",
        }
        or not isinstance(value.get("recorded_at"), str)
        or not value.get("recorded_at")
    ):
        raise E6CalibrationRunnerV2Error(
            "E6-v2 provider stop fatal evidence drift"
        )

    # _execution_history first validates every raw identity and append-only
    # attempt transition.  The direct physical projection then preserves global
    # file order, so a stale stop cannot remain authoritative after a later row.
    _execution_history(provider_id)
    physical = [
        row
        for row in lean._read_jsonl(_raw_path(provider_id))
        if row.get("record_kind") == "execution"
    ]
    if not physical:
        raise E6CalibrationRunnerV2Error(
            "E6-v2 provider stop has no matching fatal raw record"
        )
    latest = physical[-1]
    raw_binding = {
        "work_key": latest.get("work_key"),
        "attempt": latest.get("attempt"),
        "error_type": latest.get("error_type"),
        "operational_status": latest.get("operational_status"),
        "recorded_at": latest.get("recorded_at"),
    }
    if any(value.get(field) != expected for field, expected in raw_binding.items()):
        raise E6CalibrationRunnerV2Error(
            "E6-v2 provider stop does not match the latest fatal raw record"
        )
    if not _is_fatal_physical_record(latest):
        raise E6CalibrationRunnerV2Error(
            "E6-v2 provider stop raw record is not a fatal boundary"
        )
    return value


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
            "run_id": work_item["run_id"],
            "execution_identity": work_item["execution_identity"],
            "model_id": work_item["model_id"],
            "physical_attempt_namespace": attempt,
            "source_protocol_version": "e6-cross-provider-calibration-v1",
            "repair_protocol_version": "e6-response-less-recovery-v2",
            "source_v1_work_key": work_item["source_v1_work_key"],
            "source_replicate_window": work_item["source_replicate_window"],
            "source_replicate_index": work_item["source_replicate_index"],
            "sample_role": "risk_enriched_activity_diagnostic",
            "execution_block_role": EXECUTION_BLOCK_ROLE,
            "execution_block_id": EXECUTION_BLOCK_ID,
            "temporal_replication_claim": False,
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
                "protocol_terminal_reason": "diagnostic_block_429_terminal",
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


def evaluate_window_gate(
    provider_id: str, window: str, *, persist: bool = True
) -> dict[str, Any]:
    prefix = [
        row for row in _window_rows(provider_id, window) if row["formal_prefix"] is True
    ]
    latest = _latest_execution_records(provider_id)
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
        "execution_block_id": EXECUTION_BLOCK_ID,
        "execution_block_role": EXECUTION_BLOCK_ROLE,
        "temporal_replication_claim": False,
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
    if persist:
        _write_json(_gate_path(provider_id, window), value)
    return value


def _require_block_gate(
    provider_id: str,
    window: str,
    *,
    require_passed: bool | None,
) -> dict[str, Any]:
    path = _gate_path(provider_id, window)
    if not path.is_file():
        raise E6CalibrationRunnerV2Error("formal E6-v2 prefix gate is missing")
    stored = json.loads(path.read_text(encoding="utf-8"))
    expected_identity = {
        "schema_version": "m3-paper-v2-e6-window-gate-2.0",
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "replicate_window": window,
        "execution_block_id": EXECUTION_BLOCK_ID,
        "execution_block_role": EXECUTION_BLOCK_ROLE,
        "temporal_replication_claim": False,
    }
    if any(stored.get(field) != value for field, value in expected_identity.items()):
        raise E6CalibrationRunnerV2Error("E6-v2 prefix gate identity drift")
    current = evaluate_window_gate(provider_id, window, persist=False)
    if stored != current:
        raise E6CalibrationRunnerV2Error(
            "E6-v2 prefix gate does not reproduce from current raw records"
        )
    if require_passed is True and current.get("gate_passed") is not True:
        raise E6CalibrationRunnerV2Error("formal E6-v2 prefix gate did not pass")
    if require_passed is False and current.get("gate_passed") is not False:
        raise E6CalibrationRunnerV2Error("formal E6-v2 prefix gate did not fail")
    return current


def _ensure_window_state(provider_id: str, window: str) -> dict[str, Any]:
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
    started_at = _now()
    value = {
        "schema_version": "m3-paper-v2-e6-window-state-2.0",
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "replicate_window": window,
        "execution_block_id": EXECUTION_BLOCK_ID,
        "execution_block_started_at": started_at,
        "window_started_at": started_at,
        "execution_block_role": EXECUTION_BLOCK_ROLE,
        "temporal_replication_claim": False,
        "status": "running",
    }
    _write_json(path, value)
    return value


def _parse_aware_time(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise E6CalibrationRunnerV2Error(f"missing {field_name}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise E6CalibrationRunnerV2Error(f"invalid {field_name}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise E6CalibrationRunnerV2Error(f"{field_name} must be timezone-aware")
    return parsed


def _block_closure_record(
    work_item: Mapping[str, Any],
    existing: Mapping[str, Any] | None,
    *,
    block_started_at: str,
    block_completed_at: str,
    operational_status: str,
    closure_reason: str,
) -> dict[str, Any]:
    value = e6_v1._closure_record(
        work_item,
        existing,
        window_started_at=block_started_at,
        window_completed_at=block_completed_at,
        operational_status=operational_status,
        closure_reason=closure_reason,
    )
    value.update(
        {
            "schema_version": SCHEMA_VERSION,
            "study_id": STUDY_ID,
            "run_id": work_item["run_id"],
            "execution_identity": work_item["execution_identity"],
            "model_id": work_item["model_id"],
            "work_key": work_item["work_key"],
            "source_protocol_version": "e6-cross-provider-calibration-v1",
            "source_v1_work_key": work_item["source_v1_work_key"],
            "source_replicate_window": work_item["source_replicate_window"],
            "source_replicate_index": work_item["source_replicate_index"],
            "repair_protocol_version": "e6-response-less-recovery-v2",
            "record_kind": "block_closure",
            "sample_role": "risk_enriched_activity_diagnostic",
            "replicate_window": EXECUTION_BLOCK_ID,
            "replicate_index": 1,
            "execution_block_id": EXECUTION_BLOCK_ID,
            "execution_block_role": EXECUTION_BLOCK_ROLE,
            "temporal_replication_claim": False,
            "closure_is_model_outcome": False,
            "included_in_primary_itt": True,
            "retry_eligible": False,
            "terminal_status": True,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        }
    )
    return value


def _current_block_summary(provider_id: str, block: str) -> dict[str, Any]:
    rows = _window_rows(provider_id, block)
    latest = _latest_records(provider_id)
    planned_keys = {str(row["work_key"]) for row in rows}
    if set(latest) != planned_keys:
        raise E6CalibrationRunnerV2Error(
            "existing B1 block seal does not match planned raw work keys"
        )
    latest_rows = [latest[str(row["work_key"])] for row in rows]
    if not all(_is_terminal(row) for row in latest_rows):
        raise E6CalibrationRunnerV2Error(
            "existing B1 block seal has nonterminal raw work"
        )
    condition_counts: dict[str, dict[str, int]] = {}
    for condition in sorted({str(row["condition_id"]) for row in rows}):
        values = [row for row in latest_rows if row["condition_id"] == condition]
        condition_counts[condition] = {
            "planned": len(values),
            "response_bearing": sum(_has_response_evidence(row) for row in values),
            "administrative_closure": sum(
                row.get("record_kind") == "block_closure" for row in values
            ),
        }
    return {
        "planned_rows": len(rows),
        "terminal_rows": len(latest_rows),
        "response_bearing_rows": sum(
            _has_response_evidence(row) for row in latest_rows
        ),
        "administrative_closure_rows": sum(
            row.get("record_kind") == "block_closure" for row in latest_rows
        ),
        "technical_gate_not_extended_rows": sum(
            row.get("operational_status") == "technical_gate_not_extended"
            for row in latest_rows
        ),
        "provider_block_unavailable_rows": sum(
            row.get("operational_status") == "provider_block_unavailable"
            for row in latest_rows
        ),
        "condition_counts": condition_counts,
    }


def _validate_existing_block_seal(
    provider_id: str,
    block: str,
    value: Mapping[str, Any],
    *,
    provider_stop: Mapping[str, Any] | None,
) -> dict[str, Any]:
    expected_identity = {
        "schema_version": BLOCK_SEAL_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "execution_block_id": block,
        "execution_block_role": EXECUTION_BLOCK_ROLE,
        "temporal_replication_claim": False,
        "status": "sealed",
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }
    if any(value.get(field) != expected for field, expected in expected_identity.items()):
        raise E6CalibrationRunnerV2Error("existing B1 block seal identity drift")
    if value.get("closure_mode") not in {
        "all_rows_terminal",
        "technical_gate_not_extended",
        "provider_unavailable",
        "fatal_stop",
    }:
        raise E6CalibrationRunnerV2Error("existing B1 block seal closure-mode drift")

    summary = _current_block_summary(provider_id, block)
    if any(value.get(field) != expected for field, expected in summary.items()):
        raise E6CalibrationRunnerV2Error(
            "existing B1 block seal does not reproduce from current raw records"
        )
    if value.get("fatal_provider_stop") is not (provider_stop is not None):
        raise E6CalibrationRunnerV2Error(
            "existing B1 block seal provider-stop binding drift"
        )

    gate_path = _gate_path(provider_id, block)
    gate_status = (
        _require_block_gate(provider_id, block, require_passed=None)["status"]
        if gate_path.is_file()
        else "not_available"
    )
    if value.get("gate_status") != gate_status:
        raise E6CalibrationRunnerV2Error("existing B1 block seal gate binding drift")

    latest = _latest_records(provider_id)
    administrative = [
        row for row in latest.values() if row.get("record_kind") == "block_closure"
    ]
    if not administrative:
        expected_closure_mode = "all_rows_terminal"
        expected_unavailable_evidence = None
    else:
        closure_statuses = {
            str(row.get("operational_status")) for row in administrative
        }
        if closure_statuses == {"technical_gate_not_extended"}:
            if provider_stop is not None or gate_status != "failed":
                raise E6CalibrationRunnerV2Error(
                    "existing B1 block seal technical closure evidence drift"
                )
            expected_closure_mode = "technical_gate_not_extended"
            expected_unavailable_evidence = None
        elif closure_statuses == {"provider_block_unavailable"}:
            if provider_stop is not None:
                expected_closure_mode = "fatal_stop"
                expected_unavailable_evidence = None
            else:
                expected_closure_mode = "provider_unavailable"
                expected_unavailable_evidence = _provider_unavailable_evidence(
                    provider_id
                )
                if expected_unavailable_evidence is None:
                    raise E6CalibrationRunnerV2Error(
                        "existing B1 block seal lacks provider-unavailable raw evidence"
                    )
        else:
            raise E6CalibrationRunnerV2Error(
                "existing B1 block seal administrative closure status drift"
            )
    if value.get("closure_mode") != expected_closure_mode:
        raise E6CalibrationRunnerV2Error(
            "existing B1 block seal closure semantics drift"
        )
    if value.get("provider_unavailable_evidence") != expected_unavailable_evidence:
        raise E6CalibrationRunnerV2Error(
            "existing B1 block seal provider-unavailable evidence drift"
        )

    state_path = _window_state_path(provider_id, block)
    if not state_path.is_file():
        raise E6CalibrationRunnerV2Error("existing B1 block seal state is missing")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    expected_state = {
        "schema_version": "m3-paper-v2-e6-window-state-2.0",
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "replicate_window": block,
        "execution_block_id": block,
        "execution_block_role": EXECUTION_BLOCK_ROLE,
        "temporal_replication_claim": False,
        "status": "sealed",
        "execution_block_started_at": value.get("execution_block_started_at"),
        "execution_block_completed_at": value.get("execution_block_completed_at"),
        "closure_mode": value.get("closure_mode"),
    }
    if any(state.get(field) != expected for field, expected in expected_state.items()):
        raise E6CalibrationRunnerV2Error("existing B1 block seal state drift")
    started = _parse_aware_time(
        value.get("execution_block_started_at"),
        field_name="execution_block_started_at",
    )
    completed = _parse_aware_time(
        value.get("execution_block_completed_at"),
        field_name="execution_block_completed_at",
    )
    if completed < started or value.get("elapsed_seconds") != (
        completed - started
    ).total_seconds():
        raise E6CalibrationRunnerV2Error("existing B1 block seal timing drift")
    if state.get("elapsed_seconds") != value.get("elapsed_seconds"):
        raise E6CalibrationRunnerV2Error("existing B1 block seal state timing drift")
    return copy.deepcopy(dict(value))


def seal_block(
    provider_id: str,
    block: str,
    *,
    provider_unavailable: bool = False,
    completed_at: str | None = None,
) -> dict[str, Any]:
    if block not in PROSPECTIVE_EXECUTION_WINDOWS:
        raise E6CalibrationRunnerV2Error("E6-v2 can seal diagnostic block B1 only")
    provider_stop = _require_provider_stop(provider_id, block)
    seal_path = _block_seal_path(provider_id, block)
    if seal_path.is_file():
        value = json.loads(seal_path.read_text(encoding="utf-8"))
        return _validate_existing_block_seal(
            provider_id,
            block,
            value,
            provider_stop=provider_stop,
        )

    state_path = _window_state_path(provider_id, block)
    if not state_path.is_file():
        raise E6CalibrationRunnerV2Error("B1 block has not started")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if (
        state.get("study_id") != STUDY_ID
        or state.get("provider_id") != provider_id
        or state.get("execution_block_id") != block
    ):
        raise E6CalibrationRunnerV2Error("B1 block state identity drift")
    started = _parse_aware_time(
        state.get("execution_block_started_at", state.get("window_started_at")),
        field_name="execution_block_started_at",
    )
    completed = _parse_aware_time(
        completed_at or _now(), field_name="execution_block_completed_at"
    )
    if completed < started:
        raise E6CalibrationRunnerV2Error("B1 completion precedes its start")

    rows = _window_rows(provider_id, block)
    latest = _latest_records(provider_id)
    nonterminal = [
        row
        for row in rows
        if not _is_terminal(latest.get(str(row["work_key"]), {}))
    ]
    retry_eligible = [
        row
        for row in nonterminal
        if latest.get(str(row["work_key"]), {}).get("retry_eligible") is True
    ]
    gate_path = _gate_path(provider_id, block)
    gate = (
        _require_block_gate(provider_id, block, require_passed=None)
        if gate_path.is_file()
        else None
    )
    fatal_stop = provider_stop is not None
    unavailable_evidence = (
        _provider_unavailable_evidence(provider_id)
        if provider_unavailable
        else None
    )

    existing_closures = [
        row
        for row in latest.values()
        if row.get("record_kind") == "block_closure"
    ]

    if not nonterminal and existing_closures:
        closure_statuses = {
            str(row.get("operational_status")) for row in existing_closures
        }
        if closure_statuses == {"technical_gate_not_extended"}:
            closure_mode = "technical_gate_not_extended"
            operational_status = "technical_gate_not_extended"
            closure_reason = "formal_prefix_technical_gate_failed_before_expansion"
        elif closure_statuses == {"provider_block_unavailable"}:
            closure_mode = "fatal_stop" if fatal_stop else "provider_unavailable"
            operational_status = "provider_block_unavailable"
            closure_reason = (
                "provider_fatal_boundary_before_block_completion"
                if fatal_stop
                else "provider_unavailable_before_block_completion"
            )
        else:
            raise E6CalibrationRunnerV2Error(
                "existing B1 administrative closure status drift"
            )
    elif not nonterminal:
        closure_mode = "all_rows_terminal"
        operational_status = "completed_without_administrative_closure"
        closure_reason = "all_planned_rows_already_terminal"
    elif fatal_stop:
        closure_mode = "fatal_stop"
        operational_status = "provider_block_unavailable"
        closure_reason = "provider_fatal_boundary_before_block_completion"
    elif provider_unavailable and unavailable_evidence is not None:
        closure_mode = "provider_unavailable"
        operational_status = "provider_block_unavailable"
        closure_reason = "provider_unavailable_before_block_completion"
    elif provider_unavailable:
        raise E6CalibrationRunnerV2Error(
            "provider-unavailable seal requires a 429 terminal or exhausted "
            "response-less recovery evidence"
        )
    elif (
        gate is not None
        and gate.get("gate_passed") is False
        and gate.get("observed_prefix_rows") == PREFIX_ROWS
        and not retry_eligible
    ):
        closure_mode = "technical_gate_not_extended"
        operational_status = "technical_gate_not_extended"
        closure_reason = "formal_prefix_technical_gate_failed_before_expansion"
    else:
        if retry_eligible:
            raise E6CalibrationRunnerV2Error(
                "retry-eligible response-less work remains; recover it or explicitly "
                "seal as provider unavailable"
            )
        raise E6CalibrationRunnerV2Error(
            "B1 still has runnable pending work; resume it before sealing"
        )

    # Administrative closure semantics are deterministic.  A fatal stop is
    # bound only through provider_stop_v2; provider-unavailable evidence is
    # retained only for the distinct nonfatal unavailable closure mode.
    if closure_mode == "provider_unavailable":
        unavailable_evidence = _provider_unavailable_evidence(provider_id)
        if unavailable_evidence is None:
            raise E6CalibrationRunnerV2Error(
                "provider-unavailable closure lost its response-less evidence"
            )
    else:
        unavailable_evidence = None

    for row in nonterminal:
        key = str(row["work_key"])
        closure = _block_closure_record(
            row,
            latest.get(key),
            block_started_at=started.isoformat(),
            block_completed_at=completed.isoformat(),
            operational_status=operational_status,
            closure_reason=closure_reason,
        )
        lean._append_jsonl(_raw_path(provider_id), closure)
        latest[key] = closure

    latest_rows = [latest[str(row["work_key"])] for row in rows]
    if not all(_is_terminal(row) for row in latest_rows):
        raise E6CalibrationRunnerV2Error("B1 seal left nonterminal work items")
    response_bearing = sum(
        _has_response_evidence(row) for row in latest_rows
    )
    condition_counts: dict[str, dict[str, int]] = {}
    for condition in sorted({str(row["condition_id"]) for row in rows}):
        values = [row for row in latest_rows if row["condition_id"] == condition]
        condition_counts[condition] = {
            "planned": len(values),
            "response_bearing": sum(_has_response_evidence(row) for row in values),
            "administrative_closure": sum(
                row.get("record_kind") == "block_closure" for row in values
            ),
        }
    seal = {
        "schema_version": BLOCK_SEAL_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "provider_id": provider_id,
        "execution_block_id": block,
        "execution_block_role": EXECUTION_BLOCK_ROLE,
        "temporal_replication_claim": False,
        "status": "sealed",
        "closure_mode": closure_mode,
        "planned_rows": len(rows),
        "terminal_rows": len(latest_rows),
        "response_bearing_rows": response_bearing,
        "administrative_closure_rows": sum(
            row.get("record_kind") == "block_closure" for row in latest_rows
        ),
        "technical_gate_not_extended_rows": sum(
            row.get("operational_status") == "technical_gate_not_extended"
            for row in latest_rows
        ),
        "provider_block_unavailable_rows": sum(
            row.get("operational_status") == "provider_block_unavailable"
            for row in latest_rows
        ),
        "fatal_provider_stop": fatal_stop,
        "provider_unavailable_evidence": unavailable_evidence,
        "gate_status": gate.get("status") if gate is not None else "not_available",
        "condition_counts": condition_counts,
        "execution_block_started_at": started.isoformat(),
        "execution_block_completed_at": completed.isoformat(),
        "elapsed_seconds": (completed - started).total_seconds(),
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }
    _write_json(seal_path, seal)
    state.update(
        {
            "status": "sealed",
            "execution_block_completed_at": completed.isoformat(),
            "elapsed_seconds": seal["elapsed_seconds"],
            "closure_mode": closure_mode,
        }
    )
    _write_json(state_path, state)
    return seal


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
            "E6-v2 provider execution is diagnostic-block B1 only; W1/W2 remain immutable"
        )
    provider_stop = _require_provider_stop(provider_id, window)
    seal_path = _block_seal_path(provider_id, window)
    if seal_path.is_file():
        _validate_existing_block_seal(
            provider_id,
            window,
            json.loads(seal_path.read_text(encoding="utf-8")),
            provider_stop=provider_stop,
        )
        raise E6CalibrationRunnerV2Error(
            f"{provider_id}: E6-v2 diagnostic block B1 is sealed"
        )
    stop_path = _provider_stop_path(provider_id)
    if provider_stop is not None:
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
        _require_block_gate(provider_id, window, require_passed=True)
    if not pending:
        gate = (
            evaluate_window_gate(provider_id, window)
            if canary_only
            else _require_block_gate(provider_id, window, require_passed=True)
        )
        return {
            "provider_id": provider_id,
            "replicate_window": window,
            "executed": 0,
            "window_gate_passed": bool(gate["gate_passed"]),
        }

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
    # State begins only after configuration validation and dispatcher construction.
    # A local preflight error must not create a false live-execution timestamp.
    state = _ensure_window_state(provider_id, window)

    executed = 0
    stopped_after_response_less = False
    stopped_after_fatal_boundary = False
    for work_item, attempt in pending:
        trace_path = lean._provider_trace_path(permit, str(work_item["work_key"]))
        result: dict[str, Any] | None = None
        digest: dict[str, Any] | None = None
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
            if digest is not None:
                base["online_visible_field_digest_sha256"] = (
                    sha256_canonical_json(digest)
                )
                base["online_forbidden_fields_present"] = bool(
                    digest["forbidden_fields_present"]
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
                    "schema_version": PROVIDER_STOP_SCHEMA_VERSION,
                    "study_id": STUDY_ID,
                    "provider_id": provider_id,
                    "replicate_window": window,
                    "execution_block_id": window,
                    "execution_block_role": EXECUTION_BLOCK_ROLE,
                    "temporal_replication_claim": False,
                    "work_key": work_item["work_key"],
                    "attempt": record.get("attempt"),
                    "error_type": record.get("error_type"),
                    "operational_status": record.get("operational_status"),
                    "status": "stopped_fatal_contract_boundary",
                    "fatal_boundary": True,
                    "terminal_status": True,
                    "recorded_at": record.get("recorded_at"),
                },
            )
        executed += 1
        if fatal:
            stopped_after_fatal_boundary = True
            break
        if not _has_response_evidence(record):
            stopped_after_response_less = True
            break

    gate = evaluate_window_gate(provider_id, window)
    return {
        "provider_id": provider_id,
        "replicate_window": window,
        "execution_block_id": EXECUTION_BLOCK_ID,
        "execution_block_role": EXECUTION_BLOCK_ROLE,
        "temporal_replication_claim": False,
        "selected": PREFIX_ROWS if canary_only else len(all_rows),
        "executed": executed,
        "stopped_after_response_less_failure": stopped_after_response_less,
        "stopped_after_fatal_boundary": stopped_after_fatal_boundary,
        "window_gate_passed": bool(gate["gate_passed"]),
        "raw_path": str(_raw_path(provider_id)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=tuple(EXPECTED_COUNTS), required=True)
    parser.add_argument("--block", choices=PROSPECTIVE_EXECUTION_WINDOWS, required=True)
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--canary-only", action="store_true")
    stage.add_argument("--resume-pending-only", action="store_true")
    stage.add_argument("--seal-block", action="store_true")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--retry-failed-work-key", action="append", default=[])
    parser.add_argument("--provider-unavailable", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.seal_block:
        if args.retry_failed_work_key:
            raise E6CalibrationRunnerV2Error(
                "block sealing cannot retry execution rows"
            )
        result = seal_block(
            args.provider,
            args.block,
            provider_unavailable=args.provider_unavailable,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.provider_unavailable:
        raise E6CalibrationRunnerV2Error(
            "--provider-unavailable is valid only with --seal-block"
        )
    result = run_window(
        args.provider,
        args.block,
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
