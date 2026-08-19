"""Admission-gated official DeepSeek canary for public matrix v4.

Public-v4 uses fresh identities and injects the active execution identity into
the public M3 resolver before the real offline evaluator is constructed.  The
module remains inert without a separately written exact-command admission.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as medium_v1
import experiments.paper_v2.formal_matrix_controller_v2 as medium_v2
import experiments.paper_v2.public_live_controller_v3 as v3
from experiments.paper_v2.boundary_rejection_runtime_v3 import (
    BoundaryAwareM3EffectBackendV3,
    BoundaryAwareM3OutcomeEvaluatorV3,
    TrustedContextBoundaryRuntimeV3,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    OnlineExecutorContext,
    build_condition_dispatcher,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    M3SandboxEffectBackend,
)
from experiments.paper_v2.m3_offline_evaluator import (
    PaperV2OfflineOutcomeEvaluator,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
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
    append_public_execution_result,
)
from experiments.paper_v2.public_m3_live_dependency_v4 import (
    PublicFrozenM3CaseResolverV4,
)
from experiments.paper_v2.public_matrix_controller_v4 import (
    PROJECT_ROOT,
    verify_candidate,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_PLAN,
    _canary_items,
    hydrate_public_work_item,
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
from m3_core.project_config import parse_env_file, resolve_config_path


DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/public_matrix_admission_v4.schema.json"
)
ADMISSION_PATHS = {
    role: (
        PROJECT_ROOT
        / "protocols/paper_upgrade_v2/admissions"
        / f"deepseek_public_{role}_canary_admission_v4.json"
    )
    for role in ("primary", "second")
}
SCHEMA_VERSION = "m3-paper-v2-public-matrix-admission-4.0"
ADMISSION_STATUS = "activated_for_one_model_role_technical_canary"
TECHNICAL_REVIEW_NAME = "technical_canary_review_v4.json"


class PublicLiveControllerV4Error(ValueError):
    """Raised when official Public-v4 execution cannot be authorized."""


PublicExecutionPermit = v3.PublicExecutionPermit


def _now() -> str:
    return v3._now()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicLiveControllerV4Error(f"{path}: expected an object")
    return value


def _load_plan(path: Path = DEFAULT_PLAN) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            raise PublicLiveControllerV4Error(
                f"{path}:{number}: blank row"
            )
        value = json.loads(line)
        if not isinstance(value, dict):
            raise PublicLiveControllerV4Error(
                f"{path}:{number}: expected an object"
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
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def canonical_canary_command(model_role: str) -> str:
    if model_role not in ADMISSION_PATHS:
        raise PublicLiveControllerV4Error(
            "unsupported public model role"
        )
    admission = ADMISSION_PATHS[model_role].relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.public_live_controller_v4 "
        f"--execute-canary --model-role {model_role} "
        f"--admission {admission} --config config\\project.local.env"
    )


def _canary_rows(model_role: str) -> list[dict[str, Any]]:
    selected = copy.deepcopy(
        _canary_items(_load_plan(), model_role)
    )
    expected = 24 if model_role == "primary" else 12
    if len(selected) != expected:
        raise PublicLiveControllerV4Error(
            f"{model_role} public canary size drift"
        )
    execution_identity = verify_candidate()["scope"]["model_roles"][
        model_role
    ]["execution_identity"]
    for item in selected:
        item["execution_identity"] = execution_identity
    return selected


def build_canary_admission(
    model_role: str,
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
        raise PublicLiveControllerV4Error(
            "owner statement digest must be lowercase SHA-256"
        )
    candidate = verify_candidate()
    rows = _canary_rows(model_role)
    role = candidate["scope"]["model_roles"][model_role]
    run = candidate["scope"]["runs"][model_role]
    command = canonical_canary_command(model_role)
    scope = {
        "model_role": model_role,
        "run_id": run["run_id"],
        "execution_identity": role["execution_identity"],
        "model_id": role["model_id"],
        "canary_records": len(rows),
        "canary_work_key_sequence_sha256": sha256_canonical_json(
            [item["work_key"] for item in rows]
        ),
        "output_root": run["output_root"],
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(
            command.encode("utf-8")
        ).hexdigest(),
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "technical_canary_execution_authorization",
        "approved_at": approved_at,
        "status": ADMISSION_STATUS,
        "scope": scope,
        "authorization": {
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "candidate_scope_sha256": candidate["scope_sha256"],
            "owner_statement_sha256": owner_statement_sha256,
            "canary_execution_authorized": True,
            "matrix_continuation_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "technical_gate_only": True,
            "scientific_outcomes_may_be_reviewed": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return validate_canary_admission(value, model_role=model_role)


def validate_canary_admission(
    value: Any,
    *,
    model_role: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicLiveControllerV4Error(
            "public admission must be an object"
        )
    Draft202012Validator(
        _load_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    command = canonical_canary_command(model_role)
    if (
        value["scope_sha256"] != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"] != _manifest_sha(value)
        or value["scope"]["model_role"] != model_role
        or value["scope"]["exact_command"] != command
        or value["scope"]["exact_command_sha256"]
        != hashlib.sha256(command.encode("utf-8")).hexdigest()
    ):
        raise PublicLiveControllerV4Error(
            "public admission digest/scope drift"
        )
    candidate = verify_candidate()
    rows = _canary_rows(model_role)
    role = candidate["scope"]["model_roles"][model_role]
    run = candidate["scope"]["runs"][model_role]
    if (
        value["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or value["authorization"]["candidate_scope_sha256"]
        != candidate["scope_sha256"]
        or value["scope"]["execution_identity"]
        != role["execution_identity"]
        or value["scope"]["model_id"] != role["model_id"]
        or value["scope"]["run_id"] != run["run_id"]
        or value["scope"]["output_root"] != run["output_root"]
        or value["scope"]["canary_records"] != len(rows)
        or value["scope"]["canary_work_key_sequence_sha256"]
        != sha256_canonical_json(
            [item["work_key"] for item in rows]
        )
    ):
        raise PublicLiveControllerV4Error(
            "public admission does not bind the current candidate"
        )
    return copy.deepcopy(dict(value))


def write_canary_admission(
    model_role: str,
    *,
    owner_statement_sha256: str,
    approved_at: str,
    path: Path | None = None,
) -> dict[str, Any]:
    target = path or ADMISSION_PATHS[model_role]
    value = build_canary_admission(
        model_role,
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(target, value)
    return value


def authorize_canary(
    model_role: str,
    *,
    admission_path: Path,
) -> PublicExecutionPermit:
    candidate = verify_candidate()
    admission = validate_canary_admission(
        _load_json(admission_path),
        model_role=model_role,
    )
    rows = _canary_rows(model_role)
    run = candidate["scope"]["runs"][model_role]
    root = (PROJECT_ROOT / run["output_root"]).resolve()
    try:
        root.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicLiveControllerV4Error(
            "public output root escapes project"
        ) from exc
    permit = PublicExecutionPermit(
        model_role=model_role,
        run_id=run["run_id"],
        execution_identity=candidate["scope"]["model_roles"][model_role][
            "execution_identity"
        ],
        work_items=tuple(copy.deepcopy(rows)),
        output_root=root,
        record_ledger_path=root / "experiment_records.jsonl",
        attempt_ledger_path=root / "attempt_events.jsonl",
        budget_ledger_path=root / "budget_events.jsonl",
        trace_root=root / "provider_traces",
        admission_file_sha256=_sha256_file(admission_path),
        max_tokens=int(candidate["scope"]["provider"]["max_tokens"]),
        timeout_seconds=float(
            candidate["scope"]["provider"]["timeout_seconds"]
        ),
        candidate=copy.deepcopy(candidate),
        admission=copy.deepcopy(admission),
    )
    v3.v2._state_from_paths(permit)
    return permit


def _build_public_offline_evaluator(
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


def _build_dispatcher(
    permit: PublicExecutionPermit,
    tracker: PublicBudgetTracker,
    *,
    api_key: str,
    role_policy: Mapping[str, Any],
    recorded_at: Callable[[], str] = _now,
) -> Any:
    registry = TracedClientRegistry()
    agentdojo = PublicFrozenAgentDojoCaseResolverV2()
    public_m3 = PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity
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
            budget_state=PublicProviderBudgetState(
                "deepseek",
                role_policy,
            ),
            policy=role_policy,
            model_role=permit.model_role,
            temperature=0.0,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
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
        )
        return registry.register(context.work_key, traced)

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
            detector=PinnedPromptGuardDetector(device="cuda"),
            vigil_factory=medium_v2.RedactedVigilConstraintFactory(),
            recorded_at=recorded_at,
        ),
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    return build_condition_dispatcher(
        runtime=medium_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=_build_public_offline_evaluator(
            agentdojo=agentdojo,
            m3=public_m3,
        ),
    )


def execute_canary(
    model_role: str,
    *,
    admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    permit = authorize_canary(
        model_role,
        admission_path=admission_path,
    )
    initial = v3.v2._state_from_paths(permit)
    if initial["records"] or initial["attempts"]:
        raise PublicLiveControllerV4Error(
            "public canary already started; automatic rerun is forbidden"
        )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    role_policy = build_role_policy(load_public_policy(), model_role)
    api_key = v3.v2._validate_runtime_config(
        values,
        role_policy=role_policy,
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
    tracker = PublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role=model_role,
        known_work_keys=keys,
        role_policy=role_policy,
    )
    factory = dispatcher_factory or _build_dispatcher
    dispatcher = factory(
        permit,
        tracker,
        api_key=api_key,
        role_policy=role_policy,
    )
    completed_this_process = 0
    for compact in permit.work_items:
        try:
            tracker.assert_before_request()
        except ProviderPausedError:
            break
        work_key = str(compact["work_key"])
        medium_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type="started",
            record_entry_sha256=None,
        )
        work_item, state = hydrate_public_work_item(compact)
        result = dict(dispatcher.execute(work_item, state))
        if result.get("result_tier") not in {
            "formal_candidate",
            "diagnostic",
        }:
            raise PublicLiveControllerV4Error(
                "public canary result exceeded candidate tier"
            )
        result["admission_manifest_sha256"] = (
            permit.admission_file_sha256
        )
        entry = append_public_execution_result(
            permit.record_ledger_path,
            work_items=permit.work_items,
            work_item=work_item,
            initial_online_state=state,
            execution_result=result,
            execution_identity=permit.execution_identity,
            run_id=permit.run_id,
            role_policy=role_policy,
        )
        tier = str(entry["record"]["result_tier"])
        medium_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type=(
                "diagnostic" if tier == "diagnostic" else "completed"
            ),
            record_entry_sha256=str(entry["entry_sha256"]),
        )
        completed_this_process += 1
        current = v3.v2._state_from_paths(permit)
        if tier == "diagnostic" or current["budget_status"]["paused"]:
            break
    final = v3.v2._state_from_paths(permit)
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in final["records"]
    )
    remaining = len(final["pending"])
    return {
        "status": (
            "public_canary_complete_candidate_records_unadmitted"
            if remaining == 0
            else (
                "public_canary_paused_after_diagnostic"
                if diagnostics
                else "public_canary_paused_by_budget"
            )
        ),
        "model_role": model_role,
        "run_id": permit.run_id,
        "canary_records": len(permit.work_items),
        "record_count": len(final["records"]),
        "formal_candidate_records": len(final["records"]) - diagnostics,
        "diagnostic_records": diagnostics,
        "remaining_records": remaining,
        "completed_this_process": completed_this_process,
        "provider_calls_completed": final["budget_status"]["event_count"],
        "role_cumulative_usage": final["budget_status"][
            "role_cumulative_usage"
        ],
        "role_cumulative_cost_cny": final["budget_status"][
            "role_cumulative_cost_cny"
        ],
        "result_admission_authorized": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }


def build_canary_technical_review(
    model_role: str,
    *,
    admission_path: Path,
) -> dict[str, Any]:
    permit = authorize_canary(
        model_role,
        admission_path=admission_path,
    )
    state = v3.v2._state_from_paths(permit)
    records = state["records"]
    expected = 24 if model_role == "primary" else 12
    statuses = [
        str(entry["record"]["operational_status"]) for entry in records
    ]
    tiers = [str(entry["record"]["result_tier"]) for entry in records]
    bundles = [
        entry["record"]["provider_trace_bundle"] for entry in records
    ]
    safety = [
        entry["record"]["provider_safety_receipt"]["evidence"]
        for entry in records
    ]
    exact_model = permit.candidate["scope"]["model_roles"][model_role][
        "model_id"
    ]
    checks = {
        "exact_record_count": len(records) == expected,
        "all_attempts_terminal": not state["attempt_status"][
            "open_work_keys"
        ],
        "all_operational_status_completed": statuses == ["completed"] * expected,
        "all_result_tiers_formal_candidate": tiers
        == ["formal_candidate"] * expected,
        "all_trace_bundles_completed": all(
            bundle["bundle_status"] == "completed"
            and bundle["result_tier_ceiling"] == "formal_candidate"
            and bundle["model_id"] == exact_model
            for bundle in bundles
        ),
        "all_provider_requests_completed": all(
            bundle["request_count"] == bundle["completed_request_count"]
            and bundle["open_request_count"] == 0
            for bundle in bundles
        ),
        "all_safety_receipts_isolated": all(
            item["provider_managed_tools_enabled"] is False
            and item["external_connectors_enabled"] is False
            for item in safety
        ),
        "budget_not_paused": state["budget_status"]["paused"] is False,
        "budget_and_records_cross_bound": True,
    }
    passed = all(checks.values())
    return {
        "schema_version": (
            "m3-paper-v2-public-canary-technical-review-4.0"
        ),
        "generated_at": _now(),
        "status": (
            "public_canary_technical_gate_pass"
            if passed
            else "public_canary_technical_gate_fail"
        ),
        "model_role": model_role,
        "run_id": permit.run_id,
        "candidate_manifest_sha256": permit.candidate["manifest_sha256"],
        "admission_file_sha256": permit.admission_file_sha256,
        "expected_records": expected,
        "observed_records": len(records),
        "provider_calls_completed": state["budget_status"]["event_count"],
        "role_cumulative_usage": state["budget_status"][
            "role_cumulative_usage"
        ],
        "role_cumulative_cost_cny": state["budget_status"][
            "role_cumulative_cost_cny"
        ],
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


def write_canary_technical_review(
    model_role: str,
    *,
    admission_path: Path,
) -> dict[str, Any]:
    permit = authorize_canary(
        model_role,
        admission_path=admission_path,
    )
    value = build_canary_technical_review(
        model_role,
        admission_path=admission_path,
    )
    _write_json(permit.output_root / TECHNICAL_REVIEW_NAME, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-canary", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument(
        "--model-role",
        choices=tuple(ADMISSION_PATHS),
        required=True,
    )
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    admission_path = args.admission or ADMISSION_PATHS[args.model_role]
    if args.write_admission:
        if not args.owner_statement_sha256 or not args.approved_at:
            parser.error(
                "--write-admission requires --owner-statement-sha256 "
                "and --approved-at"
            )
        value = write_canary_admission(
            args.model_role,
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
            path=admission_path,
        )
    elif args.verify_admission:
        value = validate_canary_admission(
            _load_json(admission_path),
            model_role=args.model_role,
        )
    elif args.execute_canary:
        value = execute_canary(
            args.model_role,
            admission_path=admission_path,
            config_path=args.config,
        )
    else:
        value = write_canary_technical_review(
            args.model_role,
            admission_path=admission_path,
        )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
