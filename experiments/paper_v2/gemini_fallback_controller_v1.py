"""Prospective Gemini replication of the paper-v2 empirical fallback.

The controller derives, without outcome access, the frozen second-model subset
from the 480-row medium plan: the strongest peer-reviewed structural baseline,
M3 policy-only, and M3 full for every selected case and authorization probe.
It executes one official Gemini model with no retry, no provider tools, and
only in-memory/sandbox effects.  Provider calls, records, attempts, and safety
cross-bindings are append-only and fsynced.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as matrix_v1
import experiments.paper_v2.formal_matrix_controller_v2 as matrix_v2
from experiments.paper_v2.agentdojo_live_dependency import (
    FrozenAgentDojoCaseResolver,
)
from experiments.paper_v2.boundary_rejection_runtime_v3 import (
    ADAPTER_VERSION,
    BoundaryAwareM3EffectBackendV3,
    BoundaryAwareM3OutcomeEvaluatorV3,
    TrustedContextBoundaryRuntimeV3,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    OnlineExecutorContext,
    build_condition_dispatcher,
)
from experiments.paper_v2.formal_record_store import (
    append_record_entry,
    load_record_entries,
    validate_record_entries,
)
from experiments.paper_v2.gemini_evidence_store_v1 import (
    append_evidence_entry,
    load_evidence_entries,
    validate_evidence_entries,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    M3SandboxEffectBackend,
)
from experiments.paper_v2.m3_offline_evaluator import (
    FrozenM3CaseResolver,
    PaperV2OfflineOutcomeEvaluator,
)
from experiments.paper_v2.medium_runtime import reconstruct_initial_online_state
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    OfficialProviderCompletion,
    ProviderBudgetState,
    load_call_events,
    provider_receipt_to_attestation,
    validate_call_events,
    validate_provider_receipt,
)
from experiments.paper_v2.provider_budget import (
    check_gemini_free_batch,
    validate_policy,
)
from experiments.paper_v2.provider_live_qualification import (
    CONSENT_VALUE,
    PROVIDER_CONFIG,
)
from experiments.paper_v2.provider_safety import build_safety_receipt
from m3_core.project_config import (
    is_placeholder,
    parse_env_file,
    resolve_config_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SOURCE_PLAN = (
    PROTOCOL_ROOT / "medium_execution_plan_v2.jsonl"
)
DEFAULT_PLAN = PROTOCOL_ROOT / "gemini_fallback_plan_v1.jsonl"
DEFAULT_BASE_POLICY = (
    PROTOCOL_ROOT / "dual_provider_budget_policy_v2.json"
)
DEFAULT_BUDGET_OVERRIDE = (
    PROTOCOL_ROOT / "gemini_fallback_budget_override_v1.json"
)
DEFAULT_SAFETY_POLICY = (
    PROTOCOL_ROOT / "provider_safety_policy_v1.json"
)
DEFAULT_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/gemini_fallback_admission_v1.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "gemini_fallback_controller_qualification_v1.json"
)
DEFAULT_CANDIDATE = (
    PROTOCOL_ROOT / "gemini_fallback_candidate_v1.json"
)
DEFAULT_CANARY_ADMISSION = (
    PROTOCOL_ROOT
    / "admissions/gemini_fallback_canary_admission_v1.json"
)
DEFAULT_CONTINUATION_ADMISSION = (
    PROTOCOL_ROOT
    / "admissions/gemini_fallback_continuation_admission_v1.json"
)

RUN_ID = "paper-v2-gemini-fallback-v1-20260726"
MODEL_ID = "gemini-3.6-flash"
PROVIDER_ID = "gemini"
SCHEMA_VERSION = "m3-paper-v2-gemini-fallback-admission-1.0"
PLAN_SCHEMA_VERSION = "m3-paper-v2-gemini-fallback-work-item-1.0"
QUALIFICATION_RECORDED_AT = "2026-07-26T23:25:00+08:00"
CANDIDATE_RECORDED_AT = "2026-07-26T23:30:00+08:00"
CANARY_APPROVED_AT = "2026-07-26T23:35:00+08:00"
CONTINUATION_APPROVED_AT = "2026-07-26T23:40:00+08:00"
CANARY_REVIEW_NAME = "gemini_three_condition_canary_review_v1.json"
SELECTED_CONDITIONS = (
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_full",
)
EXPECTED_ROWS = 264
EXPECTED_PRIMARY_ROWS = 216
EXPECTED_PROBE_ROWS = 48
CANARY_ROWS = 3
OWNER_APPROVAL_STATEMENT = (
    "The project owner authorized unrestricted safe research use of the "
    "configured official DeepSeek and Gemini APIs, while retaining the "
    "no-dangerous-operation and no-service-exhaustion boundaries."
)
OWNER_STATEMENT_SHA256 = hashlib.sha256(
    OWNER_APPROVAL_STATEMENT.encode("utf-8")
).hexdigest()


class GeminiFallbackControllerError(RuntimeError):
    """Raised when the prospective Gemini evidence boundary cannot hold."""


@dataclass(frozen=True)
class GeminiExecutionPermit:
    admission_file_sha256: str
    authorization_scope: str
    run_id: str
    execution_identity: str
    work_items: tuple[dict[str, Any], ...]
    output_root: Path
    record_ledger_path: Path
    attempt_ledger_path: Path
    call_ledger_path: Path
    evidence_ledger_path: Path
    max_tokens: int
    timeout_seconds: float
    scope: Mapping[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GeminiFallbackControllerError(f"{path}: expected an object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise GeminiFallbackControllerError(
                        f"{path}:{line_number}: blank JSONL row"
                    )
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise GeminiFallbackControllerError(
                        f"{path}:{line_number}: expected an object"
                    )
                rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiFallbackControllerError(
            f"{path}: invalid UTF-8 JSONL"
        ) from exc
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
        stream.flush()
        os.fsync(stream.fileno())


def _append_fsynced(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise GeminiFallbackControllerError(
            "Gemini artifact path escapes the project root"
        ) from exc
    return path


def _artifact_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiFallbackControllerError(
            f"missing Gemini input: {_display_path(path)}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _effective_policy() -> dict[str, Any]:
    policy = _load_json(DEFAULT_BASE_POLICY)
    override = _load_json(DEFAULT_BUDGET_OVERRIDE)
    if (
        override.get("schema_version")
        != "m3-paper-v2-gemini-fallback-budget-override-1.0"
        or override.get("approved_by_project_owner") is not True
        or override.get("provider_id") != PROVIDER_ID
        or override.get("model_id") != MODEL_ID
        or override.get("billing_tier") != "free"
        or override.get("allow_paid_tier") is not False
        or override.get("monetary_hard_limit_usd") != 0.0
    ):
        raise GeminiFallbackControllerError(
            "Gemini budget override is not fail-closed"
        )
    controls = override.get("execution_controls")
    if not isinstance(controls, Mapping) or (
        controls.get("concurrency") != 1
        or controls.get("automatic_retries") != 0
        or controls.get("first_http_429") != "pause"
        or controls.get("cross_provider_fallback") is not False
        or controls.get("provider_managed_tools") is not False
        or controls.get("external_effects") is not False
        or controls.get("chargeable_features") is not False
        or controls.get("provider_search_grounding") is not False
    ):
        raise GeminiFallbackControllerError(
            "Gemini execution controls widened"
        )
    caps = override.get("local_batch_caps")
    if not isinstance(caps, Mapping):
        raise GeminiFallbackControllerError(
            "Gemini local caps are missing"
        )
    policy["gemini"]["local_batch_caps"] = {
        "requests": int(caps["requests"]),
        "input_tokens": int(caps["input_tokens"]),
        "output_tokens": int(caps["output_tokens"]),
    }
    return validate_policy(policy)


def build_plan_rows() -> list[dict[str, Any]]:
    """Derive the second-model subset without reading any prior outcome."""

    source = _load_jsonl(DEFAULT_SOURCE_PLAN)
    selected = [
        copy.deepcopy(row)
        for row in source
        if row.get("condition_id") in SELECTED_CONDITIONS
    ]
    if (
        len(source) != 480
        or len(selected) != EXPECTED_ROWS
        or sum(row["analysis_tier"] == "primary" for row in selected)
        != EXPECTED_PRIMARY_ROWS
        or sum(
            row["analysis_tier"] == "authorization_regime_probe"
            for row in selected
        )
        != EXPECTED_PROBE_ROWS
    ):
        raise GeminiFallbackControllerError(
            "Gemini outcome-blind subset selection drift"
        )
    execution_identity = sha256_canonical_json(
        {
            "schema_version": PLAN_SCHEMA_VERSION,
            "source_plan_sha256": _sha256_file(DEFAULT_SOURCE_PLAN),
            "provider_id": PROVIDER_ID,
            "model_id": MODEL_ID,
            "selected_conditions": list(SELECTED_CONDITIONS),
            "selection_rule": "all_rows_with_selected_condition_ids",
        }
    )
    result: list[dict[str, Any]] = []
    for sequence, row in enumerate(selected, start=1):
        source_work_key = str(row["work_key"])
        row["schema_version"] = PLAN_SCHEMA_VERSION
        row["source_work_key"] = source_work_key
        row["source_execution_identity"] = str(row["execution_identity"])
        row["execution_identity"] = execution_identity
        row["sequence"] = sequence
        row["work_key"] = sha256_canonical_json(
            {
                "execution_identity": execution_identity,
                "source_work_key": source_work_key,
                "provider_id": PROVIDER_ID,
                "model_id": MODEL_ID,
            }
        )
        result.append(row)
    if len({row["work_key"] for row in result}) != EXPECTED_ROWS:
        raise GeminiFallbackControllerError(
            "Gemini work keys are not unique"
        )
    return result


def write_plan(path: Path = DEFAULT_PLAN) -> list[dict[str, Any]]:
    rows = build_plan_rows()
    _write_jsonl(path, rows)
    return rows


def verify_plan(path: Path = DEFAULT_PLAN) -> list[dict[str, Any]]:
    observed = _load_jsonl(path)
    expected = build_plan_rows()
    if observed != expected:
        raise GeminiFallbackControllerError(
            "frozen Gemini plan does not reproduce"
        )
    return observed


class GeminiCallLedgerSink:
    """Fsynced, provider-generic call ledger used by the live runtime."""

    def __init__(
        self,
        path: Path,
        *,
        execution_identity: str,
        model_id: str = MODEL_ID,
    ) -> None:
        self.path = path
        self.execution_identity = execution_identity
        self.model_id = model_id
        validate_call_events(
            load_call_events(path),
            execution_identity=execution_identity,
            provider_id=PROVIDER_ID,
            model_id=model_id,
        )

    def append(self, event: Mapping[str, Any]) -> None:
        prior = load_call_events(self.path)
        validate_call_events(
            [*prior, dict(event)],
            execution_identity=self.execution_identity,
            provider_id=PROVIDER_ID,
            model_id=self.model_id,
        )
        _append_fsynced(self.path, dict(event))

    def events(self) -> list[dict[str, Any]]:
        events = load_call_events(self.path)
        validate_call_events(
            events,
            execution_identity=self.execution_identity,
            provider_id=PROVIDER_ID,
            model_id=self.model_id,
        )
        return events

    def events_for(self, work_key: str) -> list[dict[str, Any]]:
        return [
            event
            for event in self.events()
            if event["work_key"] == work_key
        ]


class GeminiEvidenceClient:
    """Proxy one official client and expose a content-free failure bundle."""

    def __init__(
        self,
        client: OfficialProviderClient,
        *,
        work_key: str,
        call_sink: GeminiCallLedgerSink,
        receipt_adapter: (
            Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
        ) = None,
    ) -> None:
        self._client = client
        self._work_key = work_key
        self._call_sink = call_sink
        self._receipt_adapter = receipt_adapter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> OfficialProviderCompletion:
        completion = self._client.complete(
            messages,
            case=case,
            step=step,
            observations=observations,
        )
        if self._receipt_adapter is None:
            return completion
        receipt = dict(self._receipt_adapter(completion.receipt))
        validate_provider_receipt(receipt)
        return replace(completion, receipt=receipt)

    def build_bundle(self) -> dict[str, Any]:
        events = self._call_sink.events_for(self._work_key)
        status = validate_call_events(
            events,
            execution_identity=self._call_sink.execution_identity,
            provider_id=PROVIDER_ID,
            model_id=MODEL_ID,
        )
        completed = [
            event for event in events if event["event_type"] == "completed"
        ]
        receipts = [event["receipt"] for event in completed]
        prompt_tokens = sum(
            int(receipt["evidence"]["usage"]["prompt_tokens"])
            for receipt in receipts
        )
        completion_tokens = sum(
            int(receipt["evidence"]["usage"]["completion_tokens"])
            for receipt in receipts
        )
        formal = bool(
            receipts
            and status["open_attempts"] == 0
            and status["paused_calls"] == 0
            and status["failed_calls"] == 0
            and all(
                provider_receipt_to_attestation(receipt)["evidence_level"]
                == "formal_candidate"
                for receipt in receipts
            )
        )
        return {
            "schema_version": "m3-paper-v2-gemini-failure-bundle-1.0",
            "provider_id": PROVIDER_ID,
            "model_id": MODEL_ID,
            "completed_request_count": len(completed),
            "open_request_count": status["open_attempts"],
            "result_tier_ceiling": (
                "formal_candidate" if formal else "diagnostic"
            ),
            "usage_summary": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            "trace_rows": [
                {
                    "event": {
                        "event_type": event["event_type"],
                        "provider_receipt_sha256": (
                            sha256_canonical_json(event["receipt"])
                            if event["event_type"] == "completed"
                            else None
                        ),
                    }
                }
                for event in events
            ],
        }


class _ClientRegistry:
    def __init__(self) -> None:
        self.clients: dict[str, GeminiEvidenceClient] = {}

    def register(
        self,
        work_key: str,
        client: GeminiEvidenceClient,
    ) -> GeminiEvidenceClient:
        if work_key in self.clients:
            raise GeminiFallbackControllerError(
                "work item attempted to replace its Gemini client"
            )
        self.clients[work_key] = client
        return client

    def get(self, work_key: str) -> GeminiEvidenceClient | None:
        return self.clients.get(str(work_key))


def _as_official_receipt(
    receipt: Mapping[str, Any],
) -> Mapping[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value["evidence"]["transport_kind"] = "official_network"
    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def _validate_runtime_config(
    values: Mapping[str, str],
    policy: Mapping[str, Any],
) -> None:
    fields = PROVIDER_CONFIG[PROVIDER_ID]
    if values.get("M3_FRONTIER_API_CONSENT") != CONSENT_VALUE:
        raise GeminiFallbackControllerError(
            "explicit local network consent is missing"
        )
    if is_placeholder(values.get(fields["api_key"])):
        raise GeminiFallbackControllerError(
            "Gemini API key is missing or a placeholder"
        )
    if values.get(fields["model_id"]) != policy["gemini"]["model_id"]:
        raise GeminiFallbackControllerError(
            "Gemini model differs from the frozen policy"
        )
    if str(values.get(fields["base_url"], "")).rstrip("/") != str(
        policy["gemini"]["base_url"]
    ).rstrip("/"):
        raise GeminiFallbackControllerError(
            "Gemini base URL differs from the frozen policy"
        )


def _budget_state_from_calls(
    call_events: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> ProviderBudgetState:
    completed = [
        event for event in call_events if event["event_type"] == "completed"
    ]
    state = ProviderBudgetState(provider_id=PROVIDER_ID, policy=policy)
    state.gemini_requests = len(completed)
    state.gemini_input_tokens = sum(
        int(event["receipt"]["evidence"]["usage"]["prompt_tokens"])
        for event in completed
    )
    state.gemini_output_tokens = sum(
        int(event["receipt"]["evidence"]["usage"]["completion_tokens"])
        for event in completed
    )
    check_gemini_free_batch(
        dict(policy),
        requests=state.gemini_requests,
        input_tokens=state.gemini_input_tokens,
        output_tokens=state.gemini_output_tokens,
        charged_usd=0.0,
        billing_tier="free",
    )
    return state


def _build_dispatcher(
    permit: GeminiExecutionPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    call_sink: GeminiCallLedgerSink,
    budget_state: ProviderBudgetState,
    network_consent: bool,
    transport_factory: Callable[
        [OnlineExecutorContext],
        Callable[
            [str, Mapping[str, str], Mapping[str, Any], float],
            HTTPResponseEnvelope,
        ]
        | None,
    ]
    | None = None,
    receipt_adapter: (
        Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
    ) = None,
    recorded_at: Callable[[], str] = _now,
) -> Any:
    registry = _ClientRegistry()
    agentdojo = FrozenAgentDojoCaseResolver()

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> GeminiEvidenceClient:
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        transport = (
            transport_factory(context)
            if transport_factory is not None
            else None
        )
        client = OfficialProviderClient(
            provider_id=PROVIDER_ID,
            api_key=api_key,
            content_class=content_class,
            budget_state=budget_state,
            policy=policy,
            temperature=0.0,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
            network_consent=network_consent,
            transport=transport,
        )
        return registry.register(
            context.work_key,
            GeminiEvidenceClient(
                client,
                work_key=context.work_key,
                call_sink=call_sink,
                receipt_adapter=receipt_adapter,
            ),
        )

    def backend_factory(
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> Any:
        if context.benchmark == "m3-v2":
            return BoundaryAwareM3EffectBackendV3(
                M3SandboxEffectBackend(context)
            )
        return agentdojo.build_backend(context, tool_schemas)

    runtime = TrustedContextBoundaryRuntimeV3(
        LiveConditionRuntime(
            provider_client_factory=provider_factory,
            effect_backend_factory=backend_factory,
            vigil_factory=matrix_v2.RedactedVigilConstraintFactory(),
            call_event_sink=call_sink,
            recorded_at=recorded_at,
        ),
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    evaluator = PaperV2OfflineOutcomeEvaluator(
        m3_resolver=FrozenM3CaseResolver(),
        agentdojo_resolver=agentdojo,
    )
    evaluator.m3 = BoundaryAwareM3OutcomeEvaluatorV3(
        FrozenM3CaseResolver()
    )
    return build_condition_dispatcher(
        runtime=matrix_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=matrix_v2.FailureAwareOutcomeEvaluator(evaluator),
    )


def _state_from_permit(permit: GeminiExecutionPermit) -> dict[str, Any]:
    keys = {str(item["work_key"]) for item in permit.work_items}
    records = load_record_entries(permit.record_ledger_path)
    record_status = validate_record_entries(
        records,
        work_items=permit.work_items,
        execution_identity=permit.execution_identity,
        run_id=permit.run_id,
    )
    attempts = matrix_v1._load_jsonl(permit.attempt_ledger_path)
    attempt_status = matrix_v1.validate_attempt_events(
        attempts,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
    )
    calls = load_call_events(permit.call_ledger_path)
    call_status = validate_call_events(
        calls,
        execution_identity=permit.execution_identity,
        provider_id=PROVIDER_ID,
        model_id=MODEL_ID,
    )
    evidence = load_evidence_entries(permit.evidence_ledger_path)
    evidence_status = validate_evidence_entries(
        evidence,
        record_entries=records,
        call_events=calls,
        execution_identity=permit.execution_identity,
        run_id=permit.run_id,
        model_id=MODEL_ID,
    )
    if len(records) != len(evidence):
        raise GeminiFallbackControllerError(
            "Gemini record/evidence ledgers are not atomically aligned"
        )
    terminal = set(record_status["terminal_work_keys"])
    attempt_terminal = set(attempt_status["terminal_by_work_key"])
    if terminal != attempt_terminal:
        raise GeminiFallbackControllerError(
            "Gemini attempt/record terminal sets differ"
        )
    call_work_keys = {str(event["work_key"]) for event in calls}
    if not call_work_keys.issubset(set(attempt_status["started_work_keys"])):
        raise GeminiFallbackControllerError(
            "Gemini call ledger references an unstarted work item"
        )
    return {
        "record_entries": records,
        "record_status": record_status,
        "attempt_events": attempts,
        "attempt_status": attempt_status,
        "call_events": calls,
        "call_status": call_status,
        "evidence_entries": evidence,
        "evidence_status": evidence_status,
        "pending_work_items": [
            copy.deepcopy(item)
            for item in permit.work_items
            if str(item["work_key"]) not in terminal
        ],
    }


def _build_fixture_transport_factory() -> Callable[
    [OnlineExecutorContext],
    Callable[
        [str, Mapping[str, str], Mapping[str, Any], float],
        HTTPResponseEnvelope,
    ],
]:
    counter = {"value": 0}

    def factory(
        _context: OnlineExecutorContext,
    ) -> Callable[
        [str, Mapping[str, str], Mapping[str, Any], float],
        HTTPResponseEnvelope,
    ]:
        def transport(
            endpoint: str,
            headers: Mapping[str, str],
            payload: Mapping[str, Any],
            timeout: float,
        ) -> HTTPResponseEnvelope:
            del endpoint, headers, timeout
            counter["value"] += 1
            return HTTPResponseEnvelope(
                status_code=200,
                headers={
                    "x-goog-request-id": (
                        f"fixture-gemini-request-{counter['value']}"
                    )
                },
                body={
                    "id": f"fixture-gemini-response-{counter['value']}",
                    "model": payload["model"],
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    '{"tool":"final","arguments":'
                                    '{"answer":"QUALIFIED"}}'
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 12,
                        "total_tokens": 112,
                    },
                },
            )

        return transport

    return factory


def _execute(
    permit: GeminiExecutionPermit,
    *,
    values: Mapping[str, str],
    max_new_items: int | None,
    transport_factory: Callable[
        [OnlineExecutorContext],
        Callable[
            [str, Mapping[str, str], Mapping[str, Any], float],
            HTTPResponseEnvelope,
        ]
        | None,
    ]
    | None = None,
    receipt_adapter: (
        Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
    ) = None,
    recorded_at: Callable[[], str] = _now,
) -> dict[str, Any]:
    state = _state_from_permit(permit)
    if (
        state["attempt_status"]["open_work_keys"]
        or state["call_status"]["open_attempts"]
    ):
        raise GeminiFallbackControllerError(
            "Gemini run has an open commitment and cannot auto-resume"
        )
    policy = _effective_policy()
    if transport_factory is None:
        _validate_runtime_config(values, policy)
        api_key = str(values[PROVIDER_CONFIG[PROVIDER_ID]["api_key"]])
        network_consent = True
    else:
        api_key = "offline-gemini-qualification-key"
        network_consent = False
    call_sink = GeminiCallLedgerSink(
        permit.call_ledger_path,
        execution_identity=permit.execution_identity,
    )
    budget_state = _budget_state_from_calls(
        state["call_events"],
        policy,
    )
    dispatcher = _build_dispatcher(
        permit,
        api_key=api_key,
        policy=policy,
        call_sink=call_sink,
        budget_state=budget_state,
        network_consent=network_consent,
        transport_factory=transport_factory,
        receipt_adapter=receipt_adapter,
        recorded_at=recorded_at,
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
    completed_this_process = 0
    for item in state["pending_work_items"]:
        if (
            max_new_items is not None
            and completed_this_process >= max_new_items
        ):
            break
        budget_state.assert_before_request()
        work_key = str(item["work_key"])
        matrix_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type="started",
            record_entry_sha256=None,
            recorded_at=recorded_at(),
        )
        online_state = reconstruct_initial_online_state(item)
        try:
            execution_result = dict(
                dispatcher.execute(item, online_state)
            )
        except Exception as exc:
            current_calls = call_sink.events()
            call_status = validate_call_events(
                current_calls,
                execution_identity=permit.execution_identity,
                provider_id=PROVIDER_ID,
                model_id=MODEL_ID,
            )
            if call_status["open_attempts"]:
                raise
            completed = [
                event
                for event in current_calls
                if event["work_key"] == work_key
                and event["event_type"] == "completed"
            ]
            if not completed:
                raise
            receipts = [event["receipt"] for event in completed]
            usage = {
                "input": sum(
                    int(r["evidence"]["usage"]["prompt_tokens"])
                    for r in receipts
                ),
                "output": sum(
                    int(r["evidence"]["usage"]["completion_tokens"])
                    for r in receipts
                ),
            }
            receipt_sha = sha256_canonical_json(receipts[-1])
            details = {
                "exception_type": type(exc).__name__,
                "failure_stage": "post_response_dispatch_or_evaluation",
                "provider_calls_completed": len(completed),
            }
            execution_result = {
                "initial_guard_decision": "DENY",
                "ask_reason": None,
                "confirmation_result": "not_requested",
                "unsafe_effect": None,
                "task_completion": False,
                "operational_status": "runner_failure",
                "provider_attestation": provider_receipt_to_attestation(
                    receipts[-1]
                ),
                "result_tier": (
                    "formal_candidate"
                    if all(
                        provider_receipt_to_attestation(r)[
                            "evidence_level"
                        ]
                        == "formal_candidate"
                        for r in receipts
                    )
                    else "diagnostic"
                ),
                "safety_receipt": build_safety_receipt(
                    provider_id=PROVIDER_ID,
                    endpoint_url=(
                        policy["gemini"]["base_url"].rstrip("/")
                        + "/chat/completions"
                    ),
                    effect_backend="no_effect",
                    tool="final",
                    arguments={"answer": ""},
                ),
                "latency_ms": {
                    "total": 0.0,
                    "model": 0.0,
                    "guard": 0.0,
                    "tool": 0.0,
                },
                "token_usage": {
                    **usage,
                    "total": usage["input"] + usage["output"],
                    "available": True,
                },
                "runtime_visibility_events": [
                    {
                        "step": 1,
                        "parse_ok": False,
                        "parse_error_code": (
                            "post_response_runner_failure"
                        ),
                        "action_proposal": {
                            "tool": "final",
                            "arguments": {"answer": ""},
                            "arguments_sha256": sha256_canonical_json(
                                {"answer": ""}
                            ),
                        },
                        "guard_decision": {
                            "decision": "DENY",
                            "reason_code": (
                                "post_response_runner_failure"
                            ),
                            "violated_constraints": [
                                "post_response_runner_failure"
                            ],
                        },
                        "controller_evidence": {
                            "controller_id": (
                                "gemini_failure_adapter_v1"
                            ),
                            "decision": "DENY",
                            "score": None,
                            "threshold": None,
                            "scan_count": 0,
                            "source_sha256": None,
                            "details_sha256": sha256_canonical_json(
                                details
                            ),
                        },
                        "execution_attempted": False,
                        "execution_succeeded": False,
                        "response_text_sha256": hashlib.sha256(
                            b""
                        ).hexdigest(),
                        "response_text_bytes": 0,
                        "observation_sha256": sha256_canonical_json(
                            {
                                "status": "runner_failure",
                                "error_type": type(exc).__name__,
                            }
                        ),
                        "observation_bytes": len(
                            json.dumps(
                                {
                                    "status": "runner_failure",
                                    "error_type": type(exc).__name__,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode("utf-8")
                        ),
                        "provider_receipt_sha256": receipt_sha,
                    }
                ],
                "recorded_at": recorded_at(),
            }
        if execution_result.get("result_tier") not in {
            "formal_candidate",
            "diagnostic",
        }:
            raise GeminiFallbackControllerError(
                "Gemini result exceeded its non-admitted evidence tier"
            )
        execution_result["admission_manifest_sha256"] = (
            permit.admission_file_sha256
        )
        append_record_entry(
            permit.record_ledger_path,
            work_items=permit.work_items,
            work_item=item,
            initial_online_state=online_state,
            execution_result=execution_result,
            execution_identity=permit.execution_identity,
            run_id=permit.run_id,
        )
        records = load_record_entries(permit.record_ledger_path)
        append_evidence_entry(
            permit.evidence_ledger_path,
            record_entries=records,
            execution_result=execution_result,
            call_events=call_sink.events(),
            execution_identity=permit.execution_identity,
            run_id=permit.run_id,
            model_id=MODEL_ID,
        )
        entry = records[-1]
        tier = str(entry["record"]["result_tier"])
        matrix_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type=(
                "diagnostic" if tier == "diagnostic" else "completed"
            ),
            record_entry_sha256=str(entry["entry_sha256"]),
            recorded_at=recorded_at(),
        )
        completed_this_process += 1
        if tier == "diagnostic":
            break
    final = _state_from_permit(permit)
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in final["record_entries"]
    )
    remaining = len(final["pending_work_items"])
    return {
        "status": (
            "gemini_fallback_complete_candidate_records_unadmitted"
            if remaining == 0
            else (
                "gemini_fallback_paused_after_diagnostic"
                if diagnostics
                else "gemini_fallback_canary_complete"
            )
        ),
        "run_id": permit.run_id,
        "work_items": len(permit.work_items),
        "record_count": len(final["record_entries"]),
        "formal_candidate_records": (
            len(final["record_entries"]) - diagnostics
        ),
        "diagnostic_records": diagnostics,
        "remaining_work_items": remaining,
        "completed_this_process": completed_this_process,
        "provider_calls_completed": final["call_status"][
            "completed_calls"
        ],
        "usage": final["evidence_status"]["usage"],
        "billing_tier": "free",
        "charged_usd": 0.0,
        "automatic_retries": 0,
        "cross_provider_fallback": False,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def build_controller_qualification() -> dict[str, Any]:
    rows = [
        row
        for row in build_plan_rows()
        if row["condition_id"] in {"m3_policy_only", "m3_full"}
        and row["benchmark"] == "m3-v2"
    ][:2]
    if len(rows) != 2:
        raise GeminiFallbackControllerError(
            "Gemini qualification rows are missing"
        )
    with TemporaryDirectory(
        prefix="m3-gemini-fallback-qualification-"
    ) as directory:
        root = Path(directory)
        permit = GeminiExecutionPermit(
            admission_file_sha256="a" * 64,
            authorization_scope="qualification",
            run_id="offline-gemini-fallback-qualification",
            execution_identity=str(rows[0]["execution_identity"]),
            work_items=tuple(copy.deepcopy(rows)),
            output_root=root,
            record_ledger_path=root / "records.jsonl",
            attempt_ledger_path=root / "attempts.jsonl",
            call_ledger_path=root / "calls.jsonl",
            evidence_ledger_path=root / "evidence.jsonl",
            max_tokens=64,
            timeout_seconds=30.0,
            scope={},
        )
        result = _execute(
            permit,
            values={},
            max_new_items=None,
            transport_factory=_build_fixture_transport_factory(),
            receipt_adapter=_as_official_receipt,
            recorded_at=lambda: QUALIFICATION_RECORDED_AT,
        )
        state = _state_from_permit(permit)
        if (
            result["record_count"] != 2
            or result["diagnostic_records"] != 0
            or result["remaining_work_items"] != 0
            or len(state["evidence_entries"]) != 2
            or state["call_status"]["open_attempts"] != 0
        ):
            raise GeminiFallbackControllerError(
                "offline Gemini end-to-end qualification failed"
            )
    return {
        "schema_version": (
            "m3-paper-v2-gemini-fallback-controller-qualification-1.0"
        ),
        "generated_at": QUALIFICATION_RECORDED_AT,
        "status": "gemini_fallback_controller_qualified_offline",
        "derived_work_items": EXPECTED_ROWS,
        "offline_records": 2,
        "offline_evidence_entries": 2,
        "offline_diagnostics": 0,
        "boundary_adapter_version": ADAPTER_VERSION,
        "network_calls_made": 0,
        "credentials_read": False,
        "scientific_outcomes_read": 0,
        "formal_results_created": 0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }


def write_controller_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    value = build_controller_qualification()
    _write_json(path, value)
    return value


def verify_controller_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    observed = _load_json(path)
    if observed != build_controller_qualification():
        raise GeminiFallbackControllerError(
            "Gemini controller qualification drift"
        )
    return observed


def _locked_inputs() -> list[dict[str, Any]]:
    paths = (
        DEFAULT_SOURCE_PLAN,
        DEFAULT_PLAN,
        DEFAULT_BASE_POLICY,
        DEFAULT_BUDGET_OVERRIDE,
        DEFAULT_SAFETY_POLICY,
        DEFAULT_SCHEMA,
        DEFAULT_QUALIFICATION,
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/gemini_evidence_store_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/official_provider_executor.py",
        PROJECT_ROOT
        / "experiments/paper_v2/live_condition_runtime.py",
        PROJECT_ROOT
        / "experiments/paper_v2/formal_record_store.py",
        PROJECT_ROOT
        / "experiments/paper_v2/formal_condition_executors.py",
        PROJECT_ROOT
        / "experiments/paper_v2/boundary_rejection_runtime_v3.py",
        PROJECT_ROOT
        / "experiments/paper_v2/trusted_context_runtime_v2.py",
        PROJECT_ROOT
        / "schemas/paper_v2/experiment_record_v1.schema.json",
        PROJECT_ROOT
        / "schemas/paper_v2/provider_safety_receipt_v1.schema.json",
    )
    return [_artifact_lock(path) for path in paths]


def _assert_locked_inputs(scope: Mapping[str, Any]) -> None:
    for item in scope["locked_inputs"]:
        path = _resolve_project_path(str(item["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or _sha256_file(path) != item["sha256"]
        ):
            raise GeminiFallbackControllerError(
                f"Gemini locked input drift: {item['path']}"
            )


def validate_manifest(
    value: Mapping[str, Any],
    *,
    expected_role: str,
) -> dict[str, Any]:
    Draft202012Validator(
        _load_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["artifact_role"] != expected_role:
        raise GeminiFallbackControllerError(
            f"expected Gemini artifact role {expected_role}"
        )
    if value["manifest_sha256"] != _manifest_sha(value):
        raise GeminiFallbackControllerError(
            "Gemini manifest digest drift"
        )
    if value["scope_sha256"] != sha256_canonical_json(value["scope"]):
        raise GeminiFallbackControllerError(
            "Gemini scope digest drift"
        )
    authorization = value["authorization"]
    if authorization["result_admission_authorized"] is not False:
        raise GeminiFallbackControllerError(
            "Gemini execution manifest cannot admit results"
        )
    if expected_role == "owner_review_candidate":
        checks = (
            value["status"] == "candidate_frozen_non_executable",
            authorization["candidate_only"] is True,
            authorization["canary_execution_authorized"] is False,
            authorization["continuation_execution_authorized"] is False,
            authorization["candidate_manifest_sha256"] is None,
            authorization["owner_approval"] is None,
        )
    else:
        approval = authorization["owner_approval"]
        checks = (
            authorization["candidate_only"] is False,
            isinstance(
                authorization["candidate_manifest_sha256"], str
            ),
            isinstance(approval, Mapping),
            approval.get("statement_sha256") == OWNER_STATEMENT_SHA256,
            approval.get("approved_by_role") == "project_owner",
        )
        if expected_role == "three_condition_canary_authorization":
            checks += (
                value["status"] == "activated_for_three_condition_canary",
                authorization["canary_execution_authorized"] is True,
                authorization["continuation_execution_authorized"] is False,
            )
        else:
            checks += (
                value["status"] == "activated_for_continuation",
                authorization["canary_execution_authorized"] is False,
                authorization["continuation_execution_authorized"] is True,
                isinstance(authorization["canary_review_sha256"], str),
            )
    if not all(checks):
        raise GeminiFallbackControllerError(
            "Gemini authorization semantics drift"
        )
    boundary = value["evidence_boundary"]
    if (
        boundary["credentials_read_while_building"] is not False
        or boundary["network_calls_while_building"] != 0
        or boundary["scientific_outcomes_read_while_building"] != 0
        or boundary["formal_results_created"] != 0
    ):
        raise GeminiFallbackControllerError(
            "Gemini evidence boundary widened"
        )
    return copy.deepcopy(dict(value))


def build_candidate() -> dict[str, Any]:
    rows = verify_plan()
    qualification = verify_controller_qualification()
    execution_identity = str(rows[0]["execution_identity"])
    matrix_identity = sha256_canonical_json(
        {
            "run_id": RUN_ID,
            "execution_identity": execution_identity,
            "plan_sha256": _sha256_file(DEFAULT_PLAN),
            "provider_id": PROVIDER_ID,
            "model_id": MODEL_ID,
            "qualification_sha256": _sha256_file(DEFAULT_QUALIFICATION),
        }
    )
    output_root = (
        PROJECT_ROOT
        / "outputs/paper_upgrade_v2/formal_medium/gemini"
        / matrix_identity
    )
    scope = {
        "run_id": RUN_ID,
        "matrix_identity": matrix_identity,
        "execution_identity": execution_identity,
        "research_route": (
            "authorization_leakage_uncertainty_empirical_fallback"
        ),
        "provider": {
            "provider_id": PROVIDER_ID,
            "endpoint_type": "official_api",
            "base_url": (
                "https://generativelanguage.googleapis.com/"
                "v1beta/openai/"
            ),
            "model_id": MODEL_ID,
            "temperature": 0.0,
            "max_tokens": 512,
            "timeout_seconds": 120.0,
            "billing_tier": "free",
            "monetary_hard_limit_usd": 0.0,
            "concurrency": 1,
            "automatic_retries": 0,
            "cross_provider_fallback": False,
            "provider_managed_tools": False,
        },
        "selection": {
            "source_plan_path": _display_path(DEFAULT_SOURCE_PLAN),
            "source_plan_sha256": _sha256_file(DEFAULT_SOURCE_PLAN),
            "plan_path": _display_path(DEFAULT_PLAN),
            "plan_sha256": _sha256_file(DEFAULT_PLAN),
            "selection_rule": "all_rows_with_selected_condition_ids",
            "selected_conditions": list(SELECTED_CONDITIONS),
            "work_items": len(rows),
            "primary_rows": EXPECTED_PRIMARY_ROWS,
            "authorization_regime_probe_rows": EXPECTED_PROBE_ROWS,
            "work_key_sequence_sha256": sha256_canonical_json(
                [row["work_key"] for row in rows]
            ),
            "provider_calls_upper_bound": sum(
                int(row["max_provider_calls"]) for row in rows
            ),
            "prior_scientific_outcomes_used_for_selection": False,
        },
        "budget": {
            "base_policy_path": _display_path(DEFAULT_BASE_POLICY),
            "base_policy_sha256": _sha256_file(DEFAULT_BASE_POLICY),
            "override_path": _display_path(DEFAULT_BUDGET_OVERRIDE),
            "override_sha256": _sha256_file(DEFAULT_BUDGET_OVERRIDE),
            "local_batch_caps": copy.deepcopy(
                _effective_policy()["gemini"]["local_batch_caps"]
            ),
            "first_http_429": "pause",
            "free_only": True,
            "charged_usd_ceiling": 0.0,
        },
        "safety": {
            "allowed_payloads": [
                "synthetic_m3_case",
                "public_benchmark_case",
            ],
            "effect_backends": [
                "m3_sandbox_fixture",
                "agentdojo_in_memory_copy",
            ],
            "external_effects": False,
            "provider_tools": False,
            "external_connectors": False,
            "model_output_is_untrusted_proposal": True,
        },
        "canary": {
            "work_items": CANARY_ROWS,
            "conditions": [
                row["condition_id"] for row in rows[:CANARY_ROWS]
            ],
            "work_key_sequence_sha256": sha256_canonical_json(
                [row["work_key"] for row in rows[:CANARY_ROWS]]
            ),
            "technical_review_before_continuation": True,
            "scientific_outcomes_reviewed": False,
            "review_filename": CANARY_REVIEW_NAME,
        },
        "qualification": {
            "path": _display_path(DEFAULT_QUALIFICATION),
            "sha256": _sha256_file(DEFAULT_QUALIFICATION),
            "status": qualification["status"],
        },
        "outputs": {
            "root": _display_path(output_root),
            "record_ledger_path": _display_path(
                output_root / "experiment_records_v1.jsonl"
            ),
            "attempt_ledger_path": _display_path(
                output_root / "matrix_attempts_v1.jsonl"
            ),
            "call_ledger_path": _display_path(
                output_root / "provider_calls_v1.jsonl"
            ),
            "evidence_ledger_path": _display_path(
                output_root / "gemini_evidence_v1.jsonl"
            ),
        },
        "locked_inputs": _locked_inputs(),
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": CANDIDATE_RECORDED_AT,
        "status": "candidate_frozen_non_executable",
        "artifact_role": "owner_review_candidate",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "authorization": {
            "candidate_only": True,
            "canary_execution_authorized": False,
            "continuation_execution_authorized": False,
            "result_admission_authorized": False,
            "candidate_manifest_sha256": None,
            "canary_review_sha256": None,
            "owner_approval": None,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "scientific_outcomes_read_while_building": 0,
            "formal_results_created": 0,
        },
    }
    return validate_manifest(
        {**core, "manifest_sha256": sha256_canonical_json(core)},
        expected_role="owner_review_candidate",
    )


def write_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    value = build_candidate()
    _write_json(path, value)
    return value


def verify_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    observed = validate_manifest(
        _load_json(path),
        expected_role="owner_review_candidate",
    )
    if observed != build_candidate():
        raise GeminiFallbackControllerError(
            "frozen Gemini candidate does not reproduce"
        )
    return observed


def _active_manifest(
    *,
    role: str,
    status: str,
    canary: bool,
    canary_review_sha256: str | None,
) -> dict[str, Any]:
    candidate = verify_candidate()
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (
            CANARY_APPROVED_AT if canary else CONTINUATION_APPROVED_AT
        ),
        "status": status,
        "artifact_role": role,
        "scope": copy.deepcopy(candidate["scope"]),
        "scope_sha256": candidate["scope_sha256"],
        "authorization": {
            "candidate_only": False,
            "canary_execution_authorized": canary,
            "continuation_execution_authorized": not canary,
            "result_admission_authorized": False,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "canary_review_sha256": canary_review_sha256,
            "owner_approval": {
                "approval_kind": "delegated_safe_api_iteration",
                "approved_by_role": "project_owner",
                "statement_sha256": OWNER_STATEMENT_SHA256,
                "scope": (
                    "gemini_three_condition_canary"
                    if canary
                    else "gemini_264_item_fallback_continuation"
                ),
            },
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "scientific_outcomes_read_while_building": 0,
            "formal_results_created": 0,
        },
    }
    return validate_manifest(
        {**core, "manifest_sha256": sha256_canonical_json(core)},
        expected_role=role,
    )


def build_canary_admission() -> dict[str, Any]:
    return _active_manifest(
        role="three_condition_canary_authorization",
        status="activated_for_three_condition_canary",
        canary=True,
        canary_review_sha256=None,
    )


def write_canary_admission(
    path: Path = DEFAULT_CANARY_ADMISSION,
) -> dict[str, Any]:
    value = build_canary_admission()
    _write_json(path, value)
    return value


def _review_path(scope: Mapping[str, Any]) -> Path:
    return (
        _resolve_project_path(str(scope["outputs"]["root"]))
        / CANARY_REVIEW_NAME
    )


def build_canary_review() -> dict[str, Any]:
    permit = authorize(
        DEFAULT_CANARY_ADMISSION,
        required_scope="canary",
    )
    state = _state_from_permit(permit)
    entries = state["record_entries"]
    if len(entries) != CANARY_ROWS:
        raise GeminiFallbackControllerError(
            "Gemini canary review requires exactly three records"
        )
    records = [entry["record"] for entry in entries]
    checks = {
        "record_count": len(records) == CANARY_ROWS,
        "condition_order": [
            record["condition_id"] for record in records
        ]
        == list(SELECTED_CONDITIONS),
        "formal_candidate_identity": all(
            record["result_tier"] == "formal_candidate"
            and record["provider_attestation"]["evidence_level"]
            == "formal_candidate"
            for record in records
        ),
        "no_provider_or_runner_failure": all(
            record["operational_status"]
            not in {"provider_failure", "runner_failure", "timeout"}
            for record in records
        ),
        "record_evidence_alignment": (
            len(state["evidence_entries"]) == CANARY_ROWS
        ),
        "no_open_attempts": not state["attempt_status"]["open_work_keys"],
        "no_open_provider_calls": (
            state["call_status"]["open_attempts"] == 0
        ),
        "no_retry": (
            state["call_status"]["manual_resumed_calls"] == 0
        ),
        "no_paid_usage": True,
        "no_tools_or_external_effects": True,
    }
    if not all(checks.values()):
        failed = sorted(
            name for name, passed in checks.items() if not passed
        )
        raise GeminiFallbackControllerError(
            f"Gemini canary technical gate failed: {failed}"
        )
    return {
        "schema_version": (
            "m3-paper-v2-gemini-three-condition-canary-review-1.0"
        ),
        "generated_at": _now(),
        "status": "gemini_three_condition_canary_technical_gate_pass",
        "run_id": RUN_ID,
        "candidate_manifest_sha256": verify_candidate()[
            "manifest_sha256"
        ],
        "canary_admission_file_sha256": _sha256_file(
            DEFAULT_CANARY_ADMISSION
        ),
        "technical_checks": checks,
        "record_count": len(records),
        "conditions": [record["condition_id"] for record in records],
        "operational_statuses": [
            record["operational_status"] for record in records
        ],
        "provider_calls_completed": state["call_status"][
            "completed_calls"
        ],
        "usage": state["evidence_status"]["usage"],
        "billing_tier": "free",
        "charged_usd": 0.0,
        "scientific_outcomes_reviewed": False,
        "continuation_eligible": True,
        "continuation_authorized": False,
        "result_admission_authorized": False,
    }


def write_canary_review() -> dict[str, Any]:
    candidate = verify_candidate()
    value = build_canary_review()
    _write_json(_review_path(candidate["scope"]), value)
    return value


def build_continuation_admission() -> dict[str, Any]:
    candidate = verify_candidate()
    review_path = _review_path(candidate["scope"])
    review = _load_json(review_path)
    if (
        review.get("status")
        != "gemini_three_condition_canary_technical_gate_pass"
        or review.get("continuation_eligible") is not True
        or review.get("scientific_outcomes_reviewed") is not False
    ):
        raise GeminiFallbackControllerError(
            "passing outcome-blind Gemini canary review is required"
        )
    return _active_manifest(
        role="continuation_execution_authorization",
        status="activated_for_continuation",
        canary=False,
        canary_review_sha256=_sha256_file(review_path),
    )


def write_continuation_admission(
    path: Path = DEFAULT_CONTINUATION_ADMISSION,
) -> dict[str, Any]:
    value = build_continuation_admission()
    _write_json(path, value)
    return value


def authorize(
    admission_path: Path,
    *,
    required_scope: str,
) -> GeminiExecutionPermit:
    candidate = verify_candidate()
    role = (
        "three_condition_canary_authorization"
        if required_scope == "canary"
        else "continuation_execution_authorization"
    )
    active = validate_manifest(
        _load_json(admission_path),
        expected_role=role,
    )
    if (
        active["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or active["scope"] != candidate["scope"]
    ):
        raise GeminiFallbackControllerError(
            "Gemini admission does not bind the frozen candidate"
        )
    _assert_locked_inputs(active["scope"])
    if required_scope == "continuation":
        review_path = _review_path(candidate["scope"])
        if (
            _sha256_file(review_path)
            != active["authorization"]["canary_review_sha256"]
        ):
            raise GeminiFallbackControllerError(
                "Gemini continuation review hash drift"
            )
    rows = verify_plan()
    outputs = candidate["scope"]["outputs"]
    permit = GeminiExecutionPermit(
        admission_file_sha256=_sha256_file(admission_path),
        authorization_scope=required_scope,
        run_id=RUN_ID,
        execution_identity=str(rows[0]["execution_identity"]),
        work_items=tuple(copy.deepcopy(rows)),
        output_root=_resolve_project_path(str(outputs["root"])),
        record_ledger_path=_resolve_project_path(
            str(outputs["record_ledger_path"])
        ),
        attempt_ledger_path=_resolve_project_path(
            str(outputs["attempt_ledger_path"])
        ),
        call_ledger_path=_resolve_project_path(
            str(outputs["call_ledger_path"])
        ),
        evidence_ledger_path=_resolve_project_path(
            str(outputs["evidence_ledger_path"])
        ),
        max_tokens=int(candidate["scope"]["provider"]["max_tokens"]),
        timeout_seconds=float(
            candidate["scope"]["provider"]["timeout_seconds"]
        ),
        scope=copy.deepcopy(candidate["scope"]),
    )
    state = _state_from_permit(permit)
    if (
        state["attempt_status"]["open_work_keys"]
        or state["call_status"]["open_attempts"]
    ):
        raise GeminiFallbackControllerError(
            "Gemini run has an open commitment"
        )
    return permit


def execute_canary(
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    permit = authorize(
        DEFAULT_CANARY_ADMISSION,
        required_scope="canary",
    )
    if _state_from_permit(permit)["record_entries"]:
        raise GeminiFallbackControllerError(
            "Gemini canary is already started"
        )
    loader = credential_loader or (
        lambda: parse_env_file(resolve_config_path(config_path))
    )
    return _execute(
        permit,
        values=loader(),
        max_new_items=CANARY_ROWS,
    )


def execute_continuation(
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    permit = authorize(
        DEFAULT_CONTINUATION_ADMISSION,
        required_scope="continuation",
    )
    if len(_state_from_permit(permit)["record_entries"]) != CANARY_ROWS:
        raise GeminiFallbackControllerError(
            "Gemini continuation requires exactly three canary records"
        )
    loader = credential_loader or (
        lambda: parse_env_file(resolve_config_path(config_path))
    )
    return _execute(
        permit,
        values=loader(),
        max_new_items=None,
    )


def status() -> dict[str, Any]:
    admission = (
        DEFAULT_CONTINUATION_ADMISSION
        if DEFAULT_CONTINUATION_ADMISSION.is_file()
        else DEFAULT_CANARY_ADMISSION
    )
    permit = authorize(
        admission,
        required_scope=(
            "continuation"
            if admission == DEFAULT_CONTINUATION_ADMISSION
            else "canary"
        ),
    )
    state = _state_from_permit(permit)
    diagnostic = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in state["record_entries"]
    )
    return {
        "status": "gemini_fallback_status_verified_no_network",
        "run_id": RUN_ID,
        "record_count": len(state["record_entries"]),
        "formal_candidate_records": (
            len(state["record_entries"]) - diagnostic
        ),
        "diagnostic_records": diagnostic,
        "remaining_work_items": len(state["pending_work_items"]),
        "provider_calls_completed": state["call_status"][
            "completed_calls"
        ],
        "usage": state["evidence_status"]["usage"],
        "open_attempts": len(
            state["attempt_status"]["open_work_keys"]
        ),
        "open_provider_calls": state["call_status"]["open_attempts"],
        "network_calls_made_by_status": 0,
        "result_admission_authorized": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write-plan", action="store_true"
    )
    parser.add_argument(
        "--write-qualification", action="store_true"
    )
    parser.add_argument(
        "--write-candidate", action="store_true"
    )
    parser.add_argument(
        "--write-canary-admission", action="store_true"
    )
    parser.add_argument(
        "--execute-canary", action="store_true"
    )
    parser.add_argument(
        "--write-canary-review", action="store_true"
    )
    parser.add_argument(
        "--write-continuation-admission", action="store_true"
    )
    parser.add_argument(
        "--execute-continuation", action="store_true"
    )
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--verify-frozen", action="store_true")
    parser.add_argument("--config", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    actions = [
        args.write_plan,
        args.write_qualification,
        args.write_candidate,
        args.write_canary_admission,
        args.execute_canary,
        args.write_canary_review,
        args.write_continuation_admission,
        args.execute_continuation,
        args.status,
        args.verify_frozen,
    ]
    if sum(bool(action) for action in actions) != 1:
        raise SystemExit("select exactly one Gemini controller action")
    if args.write_plan:
        value: Any = {"work_items": len(write_plan())}
    elif args.write_qualification:
        value = write_controller_qualification()
    elif args.write_candidate:
        value = write_candidate()
    elif args.write_canary_admission:
        value = write_canary_admission()
    elif args.execute_canary:
        value = execute_canary(args.config)
    elif args.write_canary_review:
        value = write_canary_review()
    elif args.write_continuation_admission:
        value = write_continuation_admission()
    elif args.execute_continuation:
        value = execute_continuation(args.config)
    elif args.status:
        value = status()
    else:
        value = {
            "plan_rows": len(verify_plan()),
            "qualification": verify_controller_qualification()["status"],
            "candidate_manifest_sha256": verify_candidate()[
                "manifest_sha256"
            ],
            "canary_admission_manifest_sha256": validate_manifest(
                _load_json(DEFAULT_CANARY_ADMISSION),
                expected_role="three_condition_canary_authorization",
            )["manifest_sha256"],
            "network_calls_made": 0,
        }
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
