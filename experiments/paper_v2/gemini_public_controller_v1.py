"""面向 1,791 行公开矩阵的带准入门禁官方 Gemini 金丝雀控制器。

在启动大规模公开矩阵评测前执行前置连通性与格式合规性金丝雀测试。
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

import experiments.paper_v2.formal_matrix_controller_v1 as matrix_v1
import experiments.paper_v2.formal_matrix_controller_v2 as matrix_v2
import experiments.paper_v2.gemini_fallback_controller_v2 as fallback
from experiments.paper_v2.boundary_rejection_runtime_v3 import (
    BoundaryAwareM3EffectBackendV3,
    BoundaryAwareM3OutcomeEvaluatorV3,
    TrustedContextBoundaryRuntimeV3,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.experiment_closeout_freeze_v1 import (
    GEMINI_MODEL_ID,
    GEMINI_PUBLIC_MANIFEST,
    GEMINI_PUBLIC_PLAN,
    build_gemini_public_manifest,
    build_gemini_public_plan,
)
from experiments.paper_v2.formal_condition_executors import (
    OnlineExecutorContext,
    build_condition_dispatcher,
)
from experiments.paper_v2.gemini_public_execution_store_v1 import (
    append_execution_result,
    load_record_entries,
    validate_record_entries,
)
from experiments.paper_v2.gemini_public_trace_v1 import (
    GeminiPublicTracedProviderClient,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    M3SandboxEffectBackend,
)
from experiments.paper_v2.m3_offline_evaluator import (
    PaperV2OfflineOutcomeEvaluator,
)
from experiments.paper_v2.official_provider_executor import (
    OfficialProviderClient,
    ProviderBudgetState,
    ProviderPausedError,
    load_call_events,
    validate_call_events,
)
from experiments.paper_v2.promptguard_live_dependency import (
    PinnedPromptGuardDetector,
)
from experiments.paper_v2.provider_live_qualification import (
    PROVIDER_CONFIG,
)
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import (
    PublicFrozenAgentDojoCaseResolverV2,
)
from experiments.paper_v2.public_m3_live_dependency_v4 import (
    PublicFrozenM3CaseResolverV4,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    _canary_items,
    hydrate_public_work_item,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "gemini_public_controller_qualification_v1.json"
)
DEFAULT_CANDIDATE = PROTOCOL_ROOT / "gemini_public_canary_candidate_v1.json"
DEFAULT_ADMISSION = (
    PROTOCOL_ROOT / "admissions/gemini_public_canary_admission_v1.json"
)
RUN_ID = "paper-v2-public-gemini-canary-v1-20260802"
OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini/public-v1-canary"
)
CANARY_SIZE = 12
OWNER_APPROVAL_STATEMENT = (
    "The project owner approved the frozen Gemini 3.6 Flash public canary "
    "and later pending-only shards under the official free tier, USD 0 paid "
    "ceiling, zero automatic retries, no provider tools, and no real effects."
)
OWNER_STATEMENT_SHA256 = hashlib.sha256(
    OWNER_APPROVAL_STATEMENT.encode("utf-8")
).hexdigest()


class GeminiPublicControllerV1Error(RuntimeError):
    """当 Gemini 公开执行无法保持安全闭合时抛出的异常。"""


@dataclass(frozen=True)
class GeminiPublicPermit:
    run_id: str
    execution_identity: str
    work_items: tuple[dict[str, Any], ...]
    output_root: Path
    record_ledger_path: Path
    attempt_ledger_path: Path
    call_ledger_path: Path
    trace_root: Path
    admission_file_sha256: str
    max_tokens: int
    timeout_seconds: float
    candidate: Mapping[str, Any]
    admission: Mapping[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GeminiPublicControllerV1Error(f"{path}: expected object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            raise GeminiPublicControllerV1Error(
                f"{path}:{line_number}: blank JSONL row"
            )
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise GeminiPublicControllerV1Error(
                f"{path}:{line_number}: expected object"
            )
        rows.append(value)
    return rows


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
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _verify_frozen_plan() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _read_jsonl(GEMINI_PUBLIC_PLAN)
    if rows != build_gemini_public_plan():
        raise GeminiPublicControllerV1Error("Gemini public plan drift")
    manifest = _read_json(GEMINI_PUBLIC_MANIFEST)
    if manifest != build_gemini_public_manifest():
        raise GeminiPublicControllerV1Error("Gemini public manifest drift")
    if manifest["plan_sha256"] != _sha256_file(GEMINI_PUBLIC_PLAN):
        raise GeminiPublicControllerV1Error(
            "Gemini public plan file hash drift"
        )
    return rows, manifest


def _canary_rows() -> list[dict[str, Any]]:
    rows, _ = _verify_frozen_plan()
    selected = _canary_items(rows, "second")
    if len(selected) != CANARY_SIZE:
        raise GeminiPublicControllerV1Error("Gemini canary size drift")
    return copy.deepcopy(selected)


def build_offline_qualification() -> dict[str, Any]:
    rows, manifest = _verify_frozen_plan()
    canary = _canary_rows()
    agentdojo = PublicFrozenAgentDojoCaseResolverV2(
        plan_path=GEMINI_PUBLIC_PLAN
    )
    m3 = PublicFrozenM3CaseResolverV4(
        execution_identity=str(manifest["execution_identity"]),
        plan_path=GEMINI_PUBLIC_PLAN,
    )
    probes: list[dict[str, Any]] = []
    for benchmark, resolver in (("agentdojo-v1", agentdojo), ("m3-v2", m3)):
        for category in ("attack", "benign"):
            item = next(
                row
                for row in rows
                if row["benchmark"] == benchmark
                and (row["evaluation_case_type"] == "attack")
                is (category == "attack")
            )
            binding = resolver.resolve(str(item["work_key"]))
            probes.append(
                {
                    "benchmark": benchmark,
                    "category": category,
                    "work_key": item["work_key"],
                    "binding_sha256": (
                        binding.binding_sha256
                        if hasattr(binding, "binding_sha256")
                        else binding.work_key_sha256
                    ),
                }
            )
    return {
        "schema_version": "m3-paper-v2-gemini-public-qualification-1.0",
        "status": "offline_interfaces_qualified_live_canary_pending",
        "generated_at": "2026-08-02T00:00:00+08:00",
        "plan_manifest_sha256": manifest["manifest_sha256"],
        "plan_records": len(rows),
        "canary_records": len(canary),
        "canary_work_key_sequence_sha256": sha256_canonical_json(
            [row["work_key"] for row in canary]
        ),
        "resolver_probes": probes,
        "resolver_probe_count": len(probes),
        "controls": {
            "billing_tier": "free",
            "paid_ceiling_usd": 0.0,
            "automatic_retries": 0,
            "provider_managed_tools_enabled": False,
            "external_effects_enabled": False,
            "first_http_429": "seal_current_run",
        },
        "network_calls_made": 0,
        "credentials_read": False,
        "scientific_outcomes_read": 0,
    }


def write_offline_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    value = build_offline_qualification()
    _write_json(path, value)
    return value


def verify_offline_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    observed = _read_json(path)
    if observed != build_offline_qualification():
        raise GeminiPublicControllerV1Error(
            "Gemini public offline qualification drift"
        )
    return observed


def canonical_canary_command() -> str:
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.gemini_public_controller_v1 "
        "--execute-canary --admission "
        "protocols\\paper_upgrade_v2\\admissions\\"
        "gemini_public_canary_admission_v1.json "
        r"--config config\project.local.env"
    )


def build_canary_candidate() -> dict[str, Any]:
    _, manifest = _verify_frozen_plan()
    qualification = verify_offline_qualification()
    rows = _canary_rows()
    execution_identity = sha256_canonical_json(
        {
            "schema_version": "m3-paper-v2-gemini-public-canary-identity-1.0",
            "plan_manifest_sha256": manifest["manifest_sha256"],
            "run_id": RUN_ID,
            "work_keys": [row["work_key"] for row in rows],
        }
    )
    core = {
        "schema_version": "m3-paper-v2-gemini-public-canary-candidate-1.0",
        "status": "candidate_pending_exact_command_admission",
        "run_id": RUN_ID,
        "execution_identity": execution_identity,
        "provider_id": "gemini",
        "model_id": GEMINI_MODEL_ID,
        "model_role": "second",
        "plan_manifest_sha256": manifest["manifest_sha256"],
        "qualification_sha256": _sha256_file(DEFAULT_QUALIFICATION),
        "canary_records": CANARY_SIZE,
        "canary_source_work_keys": [row["work_key"] for row in rows],
        "canary_work_key_sequence_sha256": sha256_canonical_json(
            [row["work_key"] for row in rows]
        ),
        "output_root": OUTPUT_ROOT.relative_to(PROJECT_ROOT).as_posix(),
        "max_tokens": 512,
        "timeout_seconds": 120.0,
        "controls": copy.deepcopy(qualification["controls"]),
        "exact_command": canonical_canary_command(),
        "result_admission_authorized": False,
        "scientific_outcomes_read": 0,
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def write_canary_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    value = build_canary_candidate()
    _write_json(path, value)
    return value


def verify_canary_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    observed = _read_json(path)
    if observed != build_canary_candidate():
        raise GeminiPublicControllerV1Error("Gemini canary candidate drift")
    return observed


def build_canary_admission(
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    candidate = verify_canary_candidate()
    if owner_statement_sha256 != OWNER_STATEMENT_SHA256:
        raise GeminiPublicControllerV1Error(
            "Gemini canary owner authorization digest drift"
        )
    core = {
        "schema_version": "m3-paper-v2-gemini-public-canary-admission-1.0",
        "status": "activated_for_one_technical_canary",
        "approved_at": approved_at,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "owner_statement_sha256": owner_statement_sha256,
        "exact_command": candidate["exact_command"],
        "exact_command_sha256": hashlib.sha256(
            candidate["exact_command"].encode("utf-8")
        ).hexdigest(),
        "run_id": candidate["run_id"],
        "execution_identity": candidate["execution_identity"],
        "canary_records": candidate["canary_records"],
        "canary_work_key_sequence_sha256": candidate[
            "canary_work_key_sequence_sha256"
        ],
        "authorization": {
            "canary_execution_authorized": True,
            "matrix_continuation_authorized": False,
            "result_admission_authorized": False,
        },
        "controls": copy.deepcopy(candidate["controls"]),
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def write_canary_admission(
    *,
    owner_statement_sha256: str,
    approved_at: str,
    path: Path = DEFAULT_ADMISSION,
) -> dict[str, Any]:
    value = build_canary_admission(
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(path, value)
    return value


def validate_canary_admission(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicControllerV1Error("Gemini admission must be an object")
    expected = build_canary_admission(
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise GeminiPublicControllerV1Error("Gemini canary admission drift")
    controls = value["controls"]
    if (
        controls["billing_tier"] != "free"
        or controls["paid_ceiling_usd"] != 0.0
        or controls["automatic_retries"] != 0
        or controls["provider_managed_tools_enabled"] is not False
        or controls["external_effects_enabled"] is not False
    ):
        raise GeminiPublicControllerV1Error("Gemini admission widened controls")
    return copy.deepcopy(dict(value))


def _permit(admission_path: Path) -> GeminiPublicPermit:
    candidate = verify_canary_candidate()
    admission = validate_canary_admission(_read_json(admission_path))
    identity = str(candidate["execution_identity"])
    rows = _canary_rows()
    for row in rows:
        row["execution_identity"] = identity
    return GeminiPublicPermit(
        run_id=RUN_ID,
        execution_identity=identity,
        work_items=tuple(rows),
        output_root=OUTPUT_ROOT,
        record_ledger_path=OUTPUT_ROOT / "experiment_records_v1.jsonl",
        attempt_ledger_path=OUTPUT_ROOT / "attempt_events_v1.jsonl",
        call_ledger_path=OUTPUT_ROOT / "provider_call_events_v1.jsonl",
        trace_root=OUTPUT_ROOT / "provider_traces",
        admission_file_sha256=_sha256_file(admission_path),
        max_tokens=int(candidate["max_tokens"]),
        timeout_seconds=float(candidate["timeout_seconds"]),
        candidate=copy.deepcopy(candidate),
        admission=copy.deepcopy(admission),
    )


def _state(permit: GeminiPublicPermit) -> dict[str, Any]:
    records = load_record_entries(permit.record_ledger_path)
    record_status = validate_record_entries(
        records,
        work_items=permit.work_items,
        execution_identity=permit.execution_identity,
        run_id=permit.run_id,
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
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
        provider_id="gemini",
        model_id=GEMINI_MODEL_ID,
    )
    terminal = set(record_status["terminal_work_keys"])
    if terminal != set(attempt_status["terminal_by_work_key"]):
        raise GeminiPublicControllerV1Error(
            "Gemini record and attempt terminal sets differ"
        )
    if attempt_status["open_work_keys"] or call_status["open_attempts"]:
        raise GeminiPublicControllerV1Error(
            "Gemini run has an open attempt and is sealed"
        )
    return {
        "records": records,
        "record_status": record_status,
        "attempts": attempts,
        "attempt_status": attempt_status,
        "calls": calls,
        "call_status": call_status,
        "pending": [
            copy.deepcopy(item)
            for item in permit.work_items
            if str(item["work_key"]) not in terminal
        ],
    }


class _Registry:
    def __init__(self) -> None:
        self.clients: dict[str, GeminiPublicTracedProviderClient] = {}

    def register(
        self,
        work_key: str,
        client: GeminiPublicTracedProviderClient,
    ) -> GeminiPublicTracedProviderClient:
        if work_key in self.clients:
            raise GeminiPublicControllerV1Error(
                "Gemini public client replacement attempted"
            )
        self.clients[work_key] = client
        return client

    def get(self, work_key: str) -> GeminiPublicTracedProviderClient | None:
        return self.clients.get(str(work_key))


def _build_dispatcher(
    permit: GeminiPublicPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    call_sink: fallback.GeminiCallLedgerSink,
    budget_state: ProviderBudgetState,
    recorded_at: Callable[[], str] = _now,
    official_client_class: type[OfficialProviderClient] = OfficialProviderClient,
    traced_client_class: type[
        GeminiPublicTracedProviderClient
    ] = GeminiPublicTracedProviderClient,
) -> Any:
    registry = _Registry()
    agentdojo = PublicFrozenAgentDojoCaseResolverV2(
        plan_path=GEMINI_PUBLIC_PLAN
    )
    public_m3 = PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity,
        plan_path=GEMINI_PUBLIC_PLAN,
    )

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> GeminiPublicTracedProviderClient:
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        client = official_client_class(
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
            traced_client_class(
                client,
                execution_identity=context.execution_identity,
                work_key=context.work_key,
                trace_path=permit.trace_root / f"{context.work_key}.jsonl",
                admission_manifest_sha256=permit.admission_file_sha256,
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

    runtime = TrustedContextBoundaryRuntimeV3(
        LiveConditionRuntime(
            provider_client_factory=provider_factory,
            effect_backend_factory=backend_factory,
            detector=PinnedPromptGuardDetector(device="cuda"),
            vigil_factory=matrix_v2.RedactedVigilConstraintFactory(),
            call_event_sink=call_sink,
            recorded_at=recorded_at,
        ),
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    evaluator = PaperV2OfflineOutcomeEvaluator(
        m3_resolver=public_m3,
        agentdojo_resolver=agentdojo,
    )
    evaluator.m3 = BoundaryAwareM3OutcomeEvaluatorV3(public_m3)
    return build_condition_dispatcher(
        runtime=matrix_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=matrix_v2.FailureAwareOutcomeEvaluator(evaluator),
    )


def execute_canary(
    *,
    admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] | None = None,
    permit_loader: Callable[[Path], GeminiPublicPermit] = _permit,
) -> dict[str, Any]:
    permit = permit_loader(admission_path)
    supersession = (
        PROTOCOL_ROOT / "gemini_public_canary_v1_supersession_review.json"
    )
    if permit.run_id == RUN_ID and supersession.is_file():
        raise GeminiPublicControllerV1Error(
            "Gemini public-v1 was superseded before execution"
        )
    initial = _state(permit)
    if initial["records"] or initial["attempts"] or initial["calls"]:
        raise GeminiPublicControllerV1Error(
            "Gemini canary already started; automatic retry is forbidden"
        )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    policy = fallback._effective_policy()
    fallback._validate_runtime_config(values, policy)
    api_key = str(values[PROVIDER_CONFIG["gemini"]["api_key"]])
    call_sink = fallback.GeminiCallLedgerSink(
        permit.call_ledger_path,
        execution_identity=permit.execution_identity,
        model_id=GEMINI_MODEL_ID,
    )
    budget_state = fallback._budget_state_from_calls([], policy)
    dispatcher = (dispatcher_factory or _build_dispatcher)(
        permit,
        api_key=api_key,
        policy=policy,
        call_sink=call_sink,
        budget_state=budget_state,
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
    completed = 0
    for compact in permit.work_items:
        try:
            budget_state.assert_before_request()
        except ProviderPausedError:
            break
        work_key = str(compact["work_key"])
        matrix_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type="started",
            record_entry_sha256=None,
        )
        work_item, online_state = hydrate_public_work_item(compact)
        result = dict(dispatcher.execute(work_item, online_state))
        result["admission_manifest_sha256"] = permit.admission_file_sha256
        entry = append_execution_result(
            permit.record_ledger_path,
            work_items=permit.work_items,
            work_item=work_item,
            initial_online_state=online_state,
            execution_result=result,
            execution_identity=permit.execution_identity,
            run_id=permit.run_id,
        )
        tier = str(entry["record"]["result_tier"])
        matrix_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type="diagnostic" if tier == "diagnostic" else "completed",
            record_entry_sha256=str(entry["entry_sha256"]),
        )
        completed += 1
        if tier == "diagnostic":
            break
    final = _state(permit)
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in final["records"]
    )
    return {
        "status": (
            "gemini_public_canary_complete_unadmitted"
            if not final["pending"]
            else "gemini_public_canary_sealed_after_diagnostic"
        ),
        "run_id": permit.run_id,
        "record_count": len(final["records"]),
        "diagnostic_records": diagnostics,
        "remaining_records": len(final["pending"]),
        "completed_this_process": completed,
        "provider_calls_completed": final["call_status"]["completed_calls"],
        "billing_tier": "free",
        "charged_usd": 0.0,
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def build_technical_review(
    *,
    admission_path: Path = DEFAULT_ADMISSION,
) -> dict[str, Any]:
    permit = _permit(admission_path)
    state = _state(permit)
    records = state["records"]
    bundles = [entry["record"]["provider_trace_bundle"] for entry in records]
    checks = {
        "exact_record_count": len(records) == CANARY_SIZE,
        "all_attempts_terminal": not state["attempt_status"]["open_work_keys"],
        "all_call_attempts_terminal": state["call_status"]["open_attempts"] == 0,
        "all_records_formal_candidates": all(
            entry["record"]["result_tier"] == "formal_candidate"
            for entry in records
        ),
        "all_trace_bundles_complete": all(
            bundle["bundle_status"] == "completed"
            and bundle["result_tier_ceiling"] == "formal_candidate"
            and bundle["provider_id"] == "gemini"
            and bundle["model_id"] == GEMINI_MODEL_ID
            for bundle in bundles
        ),
        "all_free_tier_zero_charge": all(
            bundle["usage_summary"]["billing_tier"] == "free"
            and bundle["usage_summary"]["charged_usd"] == 0.0
            and bundle["usage_summary"]["paid_ceiling_usd"] == 0.0
            for bundle in bundles
        ),
        "all_effects_isolated": all(
            entry["record"]["provider_safety_receipt"]["evidence"][
                "external_connectors_enabled"
            ]
            is False
            for entry in records
        ),
    }
    passed = all(checks.values())
    return {
        "schema_version": "m3-paper-v2-gemini-public-technical-review-1.0",
        "generated_at": _now(),
        "status": (
            "gemini_public_canary_technical_gate_pass"
            if passed
            else "gemini_public_canary_technical_gate_fail"
        ),
        "run_id": permit.run_id,
        "expected_records": CANARY_SIZE,
        "observed_records": len(records),
        "provider_calls_completed": state["call_status"]["completed_calls"],
        "checks": checks,
        "matrix_continuation_eligible": passed,
        "review_boundary": {
            "scientific_outcomes_accessed": False,
            "unsafe_effect_aggregated": False,
            "task_completion_aggregated": False,
            "condition_effects_compared": False,
            "result_admission_authorized": False,
        },
    }


def write_technical_review(
    *,
    admission_path: Path = DEFAULT_ADMISSION,
) -> dict[str, Any]:
    value = build_technical_review(admission_path=admission_path)
    _write_json(OUTPUT_ROOT / "technical_canary_review_v1.json", value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write-qualification", action="store_true")
    actions.add_argument("--verify-qualification", action="store_true")
    actions.add_argument("--write-candidate", action="store_true")
    actions.add_argument("--verify-candidate", action="store_true")
    actions.add_argument("--write-admission", action="store_true")
    actions.add_argument("--verify-admission", action="store_true")
    actions.add_argument("--execute-canary", action="store_true")
    actions.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--admission", type=Path, default=DEFAULT_ADMISSION)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.write_qualification:
        value = write_offline_qualification()
    elif args.verify_qualification:
        value = verify_offline_qualification()
    elif args.write_candidate:
        value = write_canary_candidate()
    elif args.verify_candidate:
        value = verify_canary_candidate()
    elif args.write_admission:
        if not args.owner_statement_sha256 or not args.approved_at:
            parser.error(
                "--write-admission requires --owner-statement-sha256 and --approved-at"
            )
        value = write_canary_admission(
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
            path=args.admission,
        )
    elif args.verify_admission:
        value = validate_canary_admission(_read_json(args.admission))
    elif args.execute_canary:
        value = execute_canary(
            admission_path=args.admission,
            config_path=args.config,
        )
    else:
        value = write_technical_review(admission_path=args.admission)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
