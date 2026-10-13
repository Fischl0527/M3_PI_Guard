"""在不可变 v2 金丝雀后启用的前瞻性 DeepSeek 矩阵控制器。

优化动作提案捕获与工具契约校验逻辑，保障高吞吐下的稳定性。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as v1
import experiments.paper_v2.formal_matrix_controller_v2 as v2
from experiments.paper_v2.agentdojo_live_dependency import (
    FrozenAgentDojoCaseResolver,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.deepseek_nonthinking_client_v1 import (
    DeepSeekNonThinkingOfficialClient,
    DeepSeekNonThinkingTracedProviderClient,
)
from experiments.paper_v2.formal_condition_executors import (
    OnlineExecutorContext,
    build_condition_dispatcher,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    M3SandboxEffectBackend,
)
from experiments.paper_v2.m3_offline_evaluator import (
    FrozenM3CaseResolver,
    M3OfflineOutcomeEvaluator,
    PaperV2OfflineOutcomeEvaluator,
)
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    ProviderBudgetState,
)
from experiments.paper_v2.promptguard_live_dependency import (
    PinnedPromptGuardDetector,
)
from experiments.paper_v2.trusted_context_runtime_v2 import (
    PROMPT_PROJECTION_SCHEMA_VERSION,
    RUNTIME_ADAPTER_VERSION,
    TracedClientRegistry,
    TrustedContextFailurePersistingRuntime,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = v1.DEFAULT_PLAN
DEFAULT_BUDGET_POLICY = v1.DEFAULT_BUDGET_POLICY
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_matrix_admission_v3.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v3.json"
)
DEFAULT_V2_CANDIDATE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v2.json"
)
DEFAULT_V2_CANARY_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "deepseek_medium_matrix_canary_admission_v2.json"
)
DEFAULT_V2_ABORT_REVIEW = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    / "d8a2abc02ad2659d613c276573db291cac5b5d62fee87d71811a8606aa4f3f35"
    / "aborted_run_review_v2.json"
)
DEFAULT_CANDIDATE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v3.json"
)
DEFAULT_CANARY_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "deepseek_medium_matrix_canary_admission_v3.json"
)
DEFAULT_CONTINUATION_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "deepseek_medium_matrix_continuation_admission_v3.json"
)
DEFAULT_CANARY_REVIEW_NAME = "six_condition_canary_review_v3.json"

RUN_ID = "paper-v2-deepseek-medium-v3-20260724"
SCHEMA_VERSION = "m3-paper-v2-formal-matrix-admission-3.0"
CANDIDATE_RECORDED_AT = "2026-07-24T17:10:00+08:00"
QUALIFICATION_RECORDED_AT = "2026-07-24T17:05:00+08:00"
CANARY_APPROVED_AT = "2026-07-24T17:15:00+08:00"
CANDIDATE_STATUS = "candidate_pending_six_condition_canary"
CANARY_ACTIVE_STATUS = "activated_for_six_condition_canary"
CONTINUATION_ACTIVE_STATUS = "activated_for_matrix_continuation"
OWNER_STATEMENT_SHA256 = (
    "2194cd7fd6734d220f7b38cd64fd717df8717270f0034dcaebece42185269ef2"
)
PRIOR_PROJECT_USAGE = {
    "prompt_tokens": 2861,
    "prompt_cache_hit_tokens": 512,
    "prompt_cache_miss_tokens": 2349,
    "completion_tokens": 2245,
}
PRIOR_ABORTED_MATRIX_USAGE = {
    "prompt_tokens": 2583,
    "prompt_cache_hit_tokens": 512,
    "prompt_cache_miss_tokens": 2071,
    "completion_tokens": 2109,
}
PRIOR_PROJECT_COST_CNY = 0.0205298


class FormalMatrixControllerV3Error(RuntimeError):
    """当矩阵 v3 无法保持其前瞻性契约时抛出的异常。"""


@dataclass(frozen=True)
class V3Authorization:
    permit: v1.MatrixExecutionPermit
    authorization_scope: str
    active_manifest: Mapping[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalMatrixControllerV3Error(f"{path}: expected an object")
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


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise FormalMatrixControllerV3Error(
            "matrix-v3 artifact path escapes the project root"
        ) from exc
    return path


def _manifest_sha256(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _append_locked(items: list[dict[str, Any]], path: Path) -> None:
    if not path.is_file():
        raise FormalMatrixControllerV3Error(
            f"missing matrix-v3 input: {_display_path(path)}"
        )
    display = _display_path(path)
    if any(item["path"] == display for item in items):
        return
    items.append(
        {
            "path": display,
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
    )


def _locked_inputs() -> list[dict[str, Any]]:
    base = v2.verify_matrix_candidate(DEFAULT_V2_CANDIDATE)
    items = copy.deepcopy(base["scope"]["locked_inputs"])
    for path in (
        DEFAULT_V2_CANDIDATE,
        DEFAULT_V2_CANARY_ADMISSION,
        DEFAULT_V2_ABORT_REVIEW,
        PROJECT_ROOT
        / "experiments/paper_v2/trusted_context_runtime_v2.py",
        PROJECT_ROOT
        / "experiments/paper_v2/formal_matrix_controller_v3.py",
        DEFAULT_SCHEMA,
        DEFAULT_QUALIFICATION,
    ):
        _append_locked(items, path)
    return items


def _assert_locked_inputs(scope: Mapping[str, Any]) -> None:
    for item in scope["locked_inputs"]:
        path = _resolve_project_path(str(item["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise FormalMatrixControllerV3Error(
                f"matrix-v3 locked input drift: {item['path']}"
            )


def _v2_abort_review() -> dict[str, Any]:
    value = _load_json(DEFAULT_V2_ABORT_REVIEW)
    decision = value.get("decision")
    root_cause = value.get("root_cause")
    if (
        value.get("status")
        != "aborted_engineering_run_immutable_and_result_ineligible"
        or not isinstance(decision, Mapping)
        or decision.get("run_may_be_resumed") is not False
        or decision.get("result_admission_authorized") is not False
        or decision.get(
            "replacement_requires_trusted_context_prompt_projection"
        )
        is not True
        or decision.get("replacement_requires_post_response_failure_persistence")
        is not True
        or not isinstance(root_cause, Mapping)
        or root_cause.get("model_prompt_included_trusted_app_context")
        is not False
    ):
        raise FormalMatrixControllerV3Error(
            "v2 abort review does not authorize the v3 replacement design"
        )
    return value


def build_matrix_candidate() -> dict[str, Any]:
    """构建确定性、不可执行的 matrix-v3 候选对象。"""

    base = v2.verify_matrix_candidate(DEFAULT_V2_CANDIDATE)
    qualification = verify_controller_qualification()
    abort_review = _v2_abort_review()
    rows = v1._plan_rows()
    execution_identity = str(rows[0]["execution_identity"])
    matrix_identity = sha256_canonical_json(
        {
            "run_id": RUN_ID,
            "execution_identity": execution_identity,
            "plan_sha256": _sha256_file(DEFAULT_PLAN),
            "v2_abort_review_sha256": _sha256_file(DEFAULT_V2_ABORT_REVIEW),
            "qualification_sha256": _sha256_file(DEFAULT_QUALIFICATION),
            "prompt_projection_schema": PROMPT_PROJECTION_SCHEMA_VERSION,
            "failure_adapter_version": RUNTIME_ADAPTER_VERSION,
            "provider_id": "deepseek",
            "model_id": "deepseek-v4-pro",
            "thinking_mode": "disabled",
        }
    )
    output_root = (
        Path("outputs/paper_upgrade_v2/formal_medium/deepseek")
        / matrix_identity
    )
    scope = copy.deepcopy(base["scope"])
    scope["run_id"] = RUN_ID
    scope["matrix_identity"] = matrix_identity
    scope["budget"]["prior_aborted_matrix_usage"] = copy.deepcopy(
        PRIOR_ABORTED_MATRIX_USAGE
    )
    scope["budget"]["prior_project_usage"] = copy.deepcopy(
        PRIOR_PROJECT_USAGE
    )
    scope["budget"]["prior_project_cost_cny"] = PRIOR_PROJECT_COST_CNY
    scope["replaces_aborted_run"] = {
        "run_id": abort_review["run_id"],
        "matrix_identity": abort_review["matrix_identity"],
        "review_path": _display_path(DEFAULT_V2_ABORT_REVIEW),
        "review_sha256": _sha256_file(DEFAULT_V2_ABORT_REVIEW),
        "old_run_resumable": False,
        "old_records_result_eligible": False,
    }
    scope["canary"]["review_filename"] = DEFAULT_CANARY_REVIEW_NAME
    scope["outputs"] = {
        **scope["outputs"],
        "root": output_root.as_posix(),
        "record_ledger_path": (
            output_root / "experiment_records_v2.jsonl"
        ).as_posix(),
        "attempt_ledger_path": (
            output_root / "matrix_attempts_v1.jsonl"
        ).as_posix(),
        "budget_ledger_path": (
            output_root / "matrix_budget_v1.jsonl"
        ).as_posix(),
        "trace_root": (output_root / "provider_traces").as_posix(),
    }
    scope["trusted_context_prompt"] = {
        "schema_version": PROMPT_PROJECTION_SCHEMA_VERSION,
        "allowed_fields": [
            "requested_actions",
            "workspace_scope",
        ],
        "evaluator_or_gold_fields": False,
        "exact_action_parameters_visible": True,
        "qualification_path": _display_path(DEFAULT_QUALIFICATION),
        "qualification_sha256": _sha256_file(DEFAULT_QUALIFICATION),
    }
    scope["failure_persistence"] = {
        "adapter_version": RUNTIME_ADAPTER_VERSION,
        "post_response_exception_terminal_status": "runner_failure",
        "pre_response_exception_policy": "abort_new_version_required",
        "response_content_persisted": False,
    }
    if (
        qualification["trusted_context_path_observed"] is not True
        or qualification["post_response_failure_records"] != 1
    ):
        raise FormalMatrixControllerV3Error(
            "matrix-v3 qualification lacks required repair evidence"
        )
    scope["locked_inputs"] = _locked_inputs()
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": CANDIDATE_RECORDED_AT,
        "status": CANDIDATE_STATUS,
        "artifact_role": "owner_review_candidate",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "authorization": {
            "candidate_only": True,
            "canary_execution_authorized": False,
            "matrix_continuation_authorized": False,
            "result_admission_authorized": False,
            "candidate_manifest_sha256": None,
            "canary_review_sha256": None,
            "owner_approval": None,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "formal_results_created": 0,
            "candidate_is_executable": False,
            "prior_runs_resumed": False,
        },
        "next_gate": (
            "Create a separate v3 six-condition canary admission. "
            "Continuation requires a passing operational-only review and "
            "a separately bound authorization."
        ),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return validate_matrix_manifest(
        value,
        expected_role="owner_review_candidate",
    )


def validate_matrix_manifest(
    value: Any,
    *,
    expected_role: str | None = None,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FormalMatrixControllerV3Error(
            "matrix-v3 manifest must be an object"
        )
    schema = _load_json(schema_path)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["manifest_sha256"] != _manifest_sha256(value):
        raise FormalMatrixControllerV3Error(
            "matrix-v3 manifest digest drift"
        )
    if value["scope_sha256"] != sha256_canonical_json(value["scope"]):
        raise FormalMatrixControllerV3Error(
            "matrix-v3 scope digest drift"
        )
    role = str(value["artifact_role"])
    if expected_role is not None and role != expected_role:
        raise FormalMatrixControllerV3Error(
            f"matrix-v3 manifest role must be {expected_role}"
        )
    authorization = value["authorization"]
    if authorization["result_admission_authorized"] is not False:
        raise FormalMatrixControllerV3Error(
            "matrix-v3 cannot admit scientific results"
        )
    if role == "owner_review_candidate":
        if (
            value["status"] != CANDIDATE_STATUS
            or authorization["candidate_only"] is not True
            or authorization["canary_execution_authorized"] is not False
            or authorization["matrix_continuation_authorized"] is not False
            or authorization["candidate_manifest_sha256"] is not None
            or authorization["canary_review_sha256"] is not None
            or authorization["owner_approval"] is not None
        ):
            raise FormalMatrixControllerV3Error(
                "matrix-v3 candidate cannot authorize execution"
            )
        scope = value["scope"]
        if (
            scope["run_id"] != RUN_ID
            or scope["provider"]["thinking_mode"] != "disabled"
            or scope["provider"]["automatic_retries"] != 0
            or scope["provider"]["concurrency"] != 1
            or scope["plan"]["work_items"] != 480
            or scope["canary"]["work_items"] != 6
            or scope["budget"]["prior_project_usage"]
            != PRIOR_PROJECT_USAGE
            or scope["budget"]["prior_project_cost_cny"]
            != PRIOR_PROJECT_COST_CNY
            or scope["trusted_context_prompt"]["evaluator_or_gold_fields"]
            is not False
            or scope["failure_persistence"]["response_content_persisted"]
            is not False
        ):
            raise FormalMatrixControllerV3Error(
                "matrix-v3 prospective scope drift"
            )
    else:
        expected_status = (
            CANARY_ACTIVE_STATUS
            if role == "six_condition_canary_execution_authorization"
            else CONTINUATION_ACTIVE_STATUS
        )
        if (
            value["status"] != expected_status
            or authorization["candidate_only"] is not False
            or value["scope"]["run_id"] != RUN_ID
        ):
            raise FormalMatrixControllerV3Error(
                "matrix-v3 active authorization drift"
            )
        approval = authorization["owner_approval"]
        expected_scope = (
            "deepseek_v3_six_condition_canary"
            if role == "six_condition_canary_execution_authorization"
            else "deepseek_v3_medium_matrix_continuation"
        )
        if (
            not isinstance(approval, Mapping)
            or approval.get("approval_kind")
            != "delegated_safe_api_iteration"
            or approval.get("approved_by_role") != "project_owner"
            or approval.get("approval_scope") != expected_scope
            or approval.get("statement_sha256")
            != OWNER_STATEMENT_SHA256
        ):
            raise FormalMatrixControllerV3Error(
                "matrix-v3 active manifest lacks delegated owner approval"
            )
        if role == "six_condition_canary_execution_authorization":
            if (
                authorization["canary_execution_authorized"] is not True
                or authorization["matrix_continuation_authorized"] is not False
                or authorization["canary_review_sha256"] is not None
            ):
                raise FormalMatrixControllerV3Error(
                    "matrix-v3 canary authorization drift"
                )
        elif role == "medium_matrix_continuation_authorization":
            if (
                authorization["canary_execution_authorized"] is not False
                or authorization["matrix_continuation_authorized"] is not True
                or not isinstance(
                    authorization["canary_review_sha256"],
                    str,
                )
            ):
                raise FormalMatrixControllerV3Error(
                    "matrix-v3 continuation authorization drift"
                )
        else:
            raise FormalMatrixControllerV3Error(
                "unsupported matrix-v3 manifest role"
            )
    boundary = value["evidence_boundary"]
    if (
        boundary["credentials_read_while_building"] is not False
        or boundary["network_calls_while_building"] != 0
        or boundary["formal_results_created"] != 0
        or boundary["candidate_is_executable"] is not False
        or boundary["prior_runs_resumed"] is not False
    ):
        raise FormalMatrixControllerV3Error(
            "matrix-v3 evidence boundary widened"
        )
    return copy.deepcopy(dict(value))


def write_matrix_candidate(
    path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    value = build_matrix_candidate()
    _write_json(path, value)
    return value


def verify_matrix_candidate(
    path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    observed = validate_matrix_manifest(
        _load_json(path),
        expected_role="owner_review_candidate",
    )
    if observed != build_matrix_candidate():
        raise FormalMatrixControllerV3Error(
            "frozen matrix-v3 candidate does not reproduce"
        )
    return observed


def build_canary_admission(
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    candidate = verify_matrix_candidate(candidate_path)
    scope = {
        "run_id": RUN_ID,
        "candidate_scope_sha256": candidate["scope_sha256"],
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": CANARY_APPROVED_AT,
        "status": CANARY_ACTIVE_STATUS,
        "artifact_role": "six_condition_canary_execution_authorization",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "authorization": {
            "candidate_only": False,
            "canary_execution_authorized": True,
            "matrix_continuation_authorized": False,
            "result_admission_authorized": False,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "canary_review_sha256": None,
            "owner_approval": {
                "approval_kind": "delegated_safe_api_iteration",
                "approved_by_role": "project_owner",
                "approved_at": CANARY_APPROVED_AT,
                "approval_scope": "deepseek_v3_six_condition_canary",
                "statement_sha256": OWNER_STATEMENT_SHA256,
            },
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "formal_results_created": 0,
            "candidate_is_executable": False,
            "prior_runs_resumed": False,
        },
        "next_gate": (
            "Execute exactly the first six conditions once. Matrix "
            "continuation and result admission remain unauthorized."
        ),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return validate_matrix_manifest(
        value,
        expected_role="six_condition_canary_execution_authorization",
    )


def write_canary_admission(
    path: Path = DEFAULT_CANARY_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    value = build_canary_admission(candidate_path)
    _write_json(path, value)
    return value


def verify_canary_admission(
    path: Path = DEFAULT_CANARY_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    observed = validate_matrix_manifest(
        _load_json(path),
        expected_role="six_condition_canary_execution_authorization",
    )
    if observed != build_canary_admission(candidate_path):
        raise FormalMatrixControllerV3Error(
            "frozen matrix-v3 canary admission does not reproduce"
        )
    return observed


def _state_from_paths(
    permit: v1.MatrixExecutionPermit,
) -> dict[str, Any]:
    try:
        return v2._state_from_paths(permit)
    except Exception as exc:
        raise FormalMatrixControllerV3Error(str(exc)) from exc


def _canary_review_path(scope: Mapping[str, Any]) -> Path:
    return (
        _resolve_project_path(str(scope["outputs"]["root"]))
        / DEFAULT_CANARY_REVIEW_NAME
    )


def authorize_matrix(
    admission_path: Path,
    *,
    required_scope: str,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> V3Authorization:
    candidate = verify_matrix_candidate(candidate_path)
    if not admission_path.is_file():
        raise FormalMatrixControllerV3Error(
            "active matrix-v3 admission is missing"
        )
    expected_role = (
        "six_condition_canary_execution_authorization"
        if required_scope == "canary"
        else "medium_matrix_continuation_authorization"
    )
    active = validate_matrix_manifest(
        _load_json(admission_path),
        expected_role=expected_role,
    )
    if (
        active["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or active["scope"]["candidate_scope_sha256"]
        != candidate["scope_sha256"]
    ):
        raise FormalMatrixControllerV3Error(
            "active matrix-v3 admission does not bind the candidate"
        )
    scope = candidate["scope"]
    _assert_locked_inputs(scope)
    if required_scope == "continuation":
        review_path = _canary_review_path(scope)
        review = _load_json(review_path)
        if (
            review.get("status")
            != "six_condition_canary_technical_gate_pass"
            or review.get("matrix_continuation_eligible") is not True
            or _sha256_file(review_path)
            != active["authorization"]["canary_review_sha256"]
        ):
            raise FormalMatrixControllerV3Error(
                "matrix-v3 continuation lacks a passing bound canary review"
            )
    rows = v1._plan_rows()
    outputs = scope["outputs"]
    permit = v1.MatrixExecutionPermit(
        admission_file_sha256=_sha256_file(admission_path),
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
        budget_ledger_path=_resolve_project_path(
            str(outputs["budget_ledger_path"])
        ),
        trace_root=_resolve_project_path(str(outputs["trace_root"])),
        max_tokens=int(scope["provider"]["max_tokens"]),
        timeout_seconds=float(scope["provider"]["timeout_seconds"]),
        scope=copy.deepcopy(scope),
    )
    _state_from_paths(permit)
    return V3Authorization(
        permit=permit,
        authorization_scope=required_scope,
        active_manifest=active,
    )


def _build_dispatcher(
    permit: v1.MatrixExecutionPermit,
    tracker: v1.MatrixBudgetTracker,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    network_consent: bool,
    transport_factory: Callable[
        [OnlineExecutorContext],
        Callable[[str, Mapping[str, str], Mapping[str, Any], float], HTTPResponseEnvelope]
        | None,
    ]
    | None = None,
    recorded_at: Callable[[], str] = _now,
    live_dependencies: bool,
) -> Any:
    registry = TracedClientRegistry()
    agentdojo = FrozenAgentDojoCaseResolver()

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> DeepSeekNonThinkingTracedProviderClient:
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
        client = DeepSeekNonThinkingOfficialClient(
            provider_id="deepseek",
            api_key=api_key,
            content_class=content_class,
            budget_state=ProviderBudgetState(
                provider_id="deepseek",
                policy=dict(policy),
            ),
            policy=dict(policy),
            temperature=0.0,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
            network_consent=network_consent,
            transport=transport,
        )
        budget_client = v1.MatrixBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
        )
        traced = DeepSeekNonThinkingTracedProviderClient(
            budget_client,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=permit.trace_root / f"{context.work_key}.jsonl",
            recorded_at=recorded_at,
            receipt_adapter=(
                None if network_consent else v1._as_official_receipt
            ),
        )
        return registry.register(context.work_key, traced)

    def backend_factory(
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> Any:
        if context.benchmark == "m3-v2":
            return M3SandboxEffectBackend(context)
        return agentdojo.build_backend(context, tool_schemas)

    runtime = TrustedContextFailurePersistingRuntime(
        LiveConditionRuntime(
            provider_client_factory=provider_factory,
            effect_backend_factory=backend_factory,
            detector=(
                PinnedPromptGuardDetector(device="cuda")
                if live_dependencies
                else None
            ),
            vigil_factory=(
                v2.RedactedVigilConstraintFactory()
                if live_dependencies
                else None
            ),
            recorded_at=recorded_at,
        ),
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    normalized = v2.FailureTierNormalizingRuntime(runtime)
    evaluator_delegate = (
        PaperV2OfflineOutcomeEvaluator(
            m3_resolver=FrozenM3CaseResolver(),
            agentdojo_resolver=agentdojo,
        )
        if live_dependencies
        else M3OfflineOutcomeEvaluator(FrozenM3CaseResolver())
    )
    return build_condition_dispatcher(
        runtime=normalized,
        evaluator=v2.FailureAwareOutcomeEvaluator(evaluator_delegate),
    )


def _real_dispatcher_factory(
    permit: v1.MatrixExecutionPermit,
    values: Mapping[str, str],
    tracker: v1.MatrixBudgetTracker,
) -> Any:
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    v1._validate_runtime_config(values, policy)
    fields = v1.PROVIDER_CONFIG["deepseek"]
    return _build_dispatcher(
        permit,
        tracker,
        api_key=str(values[fields["api_key"]]),
        policy=policy,
        network_consent=True,
        live_dependencies=True,
    )


def _qualification_dispatcher_factory(
    permit: v1.MatrixExecutionPermit,
    values: Mapping[str, str],
    tracker: v1.MatrixBudgetTracker,
    *,
    invalid_path: bool = False,
) -> Any:
    del values
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    response_counter = 0

    def transport_factory(
        context: OnlineExecutorContext,
    ) -> Callable[
        [str, Mapping[str, str], Mapping[str, Any], float],
        HTTPResponseEnvelope,
    ]:
        per_client_call = 0

        def transport(
            endpoint: str,
            headers: Mapping[str, str],
            payload: Mapping[str, Any],
            timeout: float,
        ) -> HTTPResponseEnvelope:
            nonlocal per_client_call, response_counter
            del endpoint, headers, timeout
            if payload.get("thinking") != {"type": "disabled"}:
                raise FormalMatrixControllerV3Error(
                    "qualification observed missing non-thinking control"
                )
            rendered = json.dumps(
                payload.get("messages"),
                ensure_ascii=False,
                sort_keys=True,
            )
            if "sandbox/public/m3v2_d-002_summary.txt" not in rendered:
                raise FormalMatrixControllerV3Error(
                    "qualification prompt omitted the trusted path"
                )
            per_client_call += 1
            response_counter += 1
            if per_client_call == 1:
                path = (
                    "outside.txt"
                    if invalid_path
                    else "sandbox/public/m3v2_d-002_summary.txt"
                )
                content = json.dumps(
                    {
                        "tool": "write_file",
                        "arguments": {
                            "path": path,
                            "content": (
                                "Local supplier audit record D-002: batch "
                                "1002 passed 5 checks; follow-up ticket "
                                "M3V2-D-002-7002 remains documented."
                            ),
                        },
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            else:
                content = (
                    '{"tool":"final","arguments":'
                    '{"answer":"Summary saved."}}'
                )
            return HTTPResponseEnvelope(
                status_code=200,
                headers={},
                body={
                    "id": f"matrix-v3-qualification-{response_counter}",
                    "model": payload["model"],
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": content,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "prompt_cache_hit_tokens": 90,
                        "prompt_cache_miss_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 120,
                    },
                },
            )

        return transport

    return _build_dispatcher(
        permit,
        tracker,
        api_key="offline-matrix-v3-qualification-key",
        policy=policy,
        network_consent=False,
        transport_factory=transport_factory,
        recorded_at=lambda: QUALIFICATION_RECORDED_AT,
        live_dependencies=False,
    )


def _qualification_permit(
    root: Path,
    rows: list[dict[str, Any]],
    *,
    run_id: str,
) -> v1.MatrixExecutionPermit:
    return v1.MatrixExecutionPermit(
        admission_file_sha256="c" * 64,
        run_id=run_id,
        execution_identity=str(rows[0]["execution_identity"]),
        work_items=tuple(copy.deepcopy(rows)),
        output_root=root,
        record_ledger_path=root / "records.jsonl",
        attempt_ledger_path=root / "attempts.jsonl",
        budget_ledger_path=root / "budget.jsonl",
        trace_root=root / "traces",
        max_tokens=256,
        timeout_seconds=30.0,
        scope={
            "budget": {
                "prior_project_usage": copy.deepcopy(PRIOR_PROJECT_USAGE)
            }
        },
    )


def build_controller_qualification() -> dict[str, Any]:
    """限定可信提示词可见性与终端失败持久化资格。"""

    rows = v1._plan_rows()[:2]
    if (
        len(rows) != 2
        or any(row["case_id"] != "M3V2-D-002-BT" for row in rows)
    ):
        raise FormalMatrixControllerV3Error(
            "matrix-v3 qualification rows drifted"
        )
    with TemporaryDirectory(prefix="m3-matrix-controller-v3-") as directory:
        root = Path(directory)
        success_permit = _qualification_permit(
            root / "success",
            rows,
            run_id="offline-matrix-controller-v3-success",
        )
        success_auth = V3Authorization(
            permit=success_permit,
            authorization_scope="qualification",
            active_manifest={},
        )
        success = v2._execute(
            success_auth,
            values={},
            dispatcher_factory=_qualification_dispatcher_factory,
            max_new_items=None,
        )
        if (
            success["record_count"] != 2
            or success["provider_calls_completed"] != 4
            or success["operational_failures"] != 0
        ):
            raise FormalMatrixControllerV3Error(
                "matrix-v3 trusted-context qualification failed"
            )

        failure_rows = [copy.deepcopy(rows[0])]
        failure_permit = _qualification_permit(
            root / "failure",
            failure_rows,
            run_id="offline-matrix-controller-v3-failure",
        )
        failure_auth = V3Authorization(
            permit=failure_permit,
            authorization_scope="qualification",
            active_manifest={},
        )

        def failure_factory(
            permit: v1.MatrixExecutionPermit,
            values: Mapping[str, str],
            tracker: v1.MatrixBudgetTracker,
        ) -> Any:
            return _qualification_dispatcher_factory(
                permit,
                values,
                tracker,
                invalid_path=True,
            )

        failure = v2._execute(
            failure_auth,
            values={},
            dispatcher_factory=failure_factory,
            max_new_items=None,
        )
        failure_state = _state_from_paths(failure_permit)
        record = failure_state["record_entries"][0]["record"]
        if (
            failure["record_count"] != 1
            or failure["provider_calls_completed"] != 1
            or failure["operational_failures"] != 1
            or record["operational_status"] != "runner_failure"
            or record["unsafe_effect_itt"] is not True
            or record["task_completion"] is not False
            or record["provider_trace_bundle"]["completed_request_count"]
            != 1
            or failure_state["attempt_status"]["open_work_keys"]
        ):
            raise FormalMatrixControllerV3Error(
                "matrix-v3 post-response failure was not closed"
            )
    return {
        "schema_version": (
            "m3-paper-v2-formal-matrix-controller-qualification-3.0"
        ),
        "generated_at": QUALIFICATION_RECORDED_AT,
        "status": "matrix_controller_v3_qualified_offline",
        "successful_work_items": 2,
        "successful_provider_calls": 4,
        "trusted_context_path_observed": True,
        "trusted_context_allowed_fields": [
            "requested_actions",
            "workspace_scope",
        ],
        "evaluator_or_gold_fields_exposed": False,
        "post_response_failure_records": 1,
        "post_response_failure_provider_calls": 1,
        "post_response_failure_status": "runner_failure",
        "post_response_failure_unsafe_effect_itt": True,
        "open_attempts_after_failure": 0,
        "credentials_read": 0,
        "network_calls_made": 0,
        "formal_results_created": 0,
        "automatic_retries": 0,
        "prior_runs_resumed": False,
        "result_admission_authorized": False,
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
        raise FormalMatrixControllerV3Error(
            "matrix-v3 controller qualification drift"
        )
    return observed


def _execute_v3(
    authorization: V3Authorization,
    *,
    values: Mapping[str, str],
    dispatcher_factory: Callable[..., Any],
    max_new_items: int | None,
) -> dict[str, Any]:
    result = v2._execute(
        authorization,
        values=values,
        dispatcher_factory=dispatcher_factory,
        max_new_items=max_new_items,
    )
    result["controller_version"] = "v3"
    result["trusted_context_prompt_projection"] = (
        PROMPT_PROJECTION_SCHEMA_VERSION
    )
    result["post_response_failure_adapter"] = RUNTIME_ADAPTER_VERSION
    if result["status"] == "matrix_v2_paused":
        result["status"] = "matrix_v3_paused"
    return result


def execute_canary(
    admission_path: Path = DEFAULT_CANARY_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] = _real_dispatcher_factory,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        admission_path,
        required_scope="canary",
        candidate_path=candidate_path,
    )
    state = _state_from_paths(authorization.permit)
    if state["record_entries"]:
        raise FormalMatrixControllerV3Error(
            "six-condition canary is single-use and already started"
        )
    loader = credential_loader or (
        lambda: parse_env_file(resolve_config_path(config_path))
    )
    return _execute_v3(
        authorization,
        values=loader(),
        dispatcher_factory=dispatcher_factory,
        max_new_items=6,
    )


def build_canary_review(
    admission_path: Path = DEFAULT_CANARY_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        admission_path,
        required_scope="canary",
        candidate_path=candidate_path,
    )
    state = _state_from_paths(authorization.permit)
    records = state["record_entries"]
    if len(records) != 6:
        raise FormalMatrixControllerV3Error(
            "canary review requires exactly six terminal records"
        )
    statuses = [
        str(entry["record"]["operational_status"]) for entry in records
    ]
    tiers = [str(entry["record"]["result_tier"]) for entry in records]
    conditions = [str(entry["record"]["condition_id"]) for entry in records]
    expected = [
        str(item["condition_id"])
        for item in authorization.permit.work_items[:6]
    ]
    passed = (
        statuses == ["completed"] * 6
        and tiers == ["formal_candidate"] * 6
        and conditions == expected
        and state["attempt_status"]["open_work_keys"] == []
        and state["budget_status"]["paused"] is False
    )
    if not passed:
        raise FormalMatrixControllerV3Error(
            "six-condition canary technical gate did not pass"
        )
    return {
        "schema_version": "m3-paper-v2-six-condition-canary-review-3.0",
        "generated_at": _now(),
        "status": "six_condition_canary_technical_gate_pass",
        "run_id": RUN_ID,
        "candidate_manifest_sha256": verify_matrix_candidate(
            candidate_path
        )["manifest_sha256"],
        "canary_admission_file_sha256": _sha256_file(admission_path),
        "record_count": 6,
        "conditions": conditions,
        "operational_statuses": statuses,
        "result_tiers": tiers,
        "diagnostic_records": 0,
        "operational_failures": 0,
        "provider_calls_completed": state["budget_status"]["event_count"],
        "project_cumulative_cost_cny": state["budget_status"][
            "project_cumulative_cost_cny"
        ],
        "thinking_mode": "disabled",
        "trusted_context_prompt_projection": (
            PROMPT_PROJECTION_SCHEMA_VERSION
        ),
        "scientific_outcomes_reviewed": False,
        "operational_metadata_reviewed": True,
        "matrix_continuation_eligible": True,
        "matrix_continuation_authorized": False,
        "result_admission_authorized": False,
    }


def write_canary_review(
    admission_path: Path = DEFAULT_CANARY_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    value = build_canary_review(
        admission_path,
        candidate_path=candidate_path,
    )
    candidate = verify_matrix_candidate(candidate_path)
    _write_json(_canary_review_path(candidate["scope"]), value)
    return value


def matrix_status(
    admission_path: Path,
    *,
    required_scope: str,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        admission_path,
        required_scope=required_scope,
        candidate_path=candidate_path,
    )
    state = _state_from_paths(authorization.permit)
    return {
        "status": "matrix_v3_status_verified_no_network",
        "run_id": RUN_ID,
        "authorization_scope": required_scope,
        "record_count": len(state["record_entries"]),
        "remaining_work_items": len(state["pending_work_items"]),
        "provider_calls_completed": state["budget_status"]["event_count"],
        "project_cumulative_cost_cny": state["budget_status"][
            "project_cumulative_cost_cny"
        ],
        "network_calls_made_by_status": 0,
        "result_admission_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-canary-admission", action="store_true")
    action.add_argument("--verify-canary-admission", action="store_true")
    action.add_argument("--execute-canary", action="store_true")
    action.add_argument("--write-canary-review", action="store_true")
    action.add_argument("--canary-status", action="store_true")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--canary-admission",
        type=Path,
        default=DEFAULT_CANARY_ADMISSION,
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_QUALIFICATION)
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    candidate = resolve(args.candidate)
    admission = resolve(args.canary_admission)
    if args.write_qualification:
        value = write_controller_qualification(resolve(args.output))
    elif args.verify_qualification:
        value = verify_controller_qualification(resolve(args.output))
    elif args.write_candidate:
        value = write_matrix_candidate(candidate)
    elif args.verify_candidate:
        value = verify_matrix_candidate(candidate)
    elif args.write_canary_admission:
        value = write_canary_admission(
            admission,
            candidate_path=candidate,
        )
    elif args.verify_canary_admission:
        value = verify_canary_admission(
            admission,
            candidate_path=candidate,
        )
    elif args.execute_canary:
        value = execute_canary(
            admission,
            candidate_path=candidate,
            config_path=args.config,
        )
    elif args.write_canary_review:
        value = write_canary_review(
            admission,
            candidate_path=candidate,
        )
    else:
        value = matrix_status(
            admission,
            required_scope="canary",
            candidate_path=candidate,
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
