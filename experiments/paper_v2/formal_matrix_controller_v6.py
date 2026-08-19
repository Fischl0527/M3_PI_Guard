"""DeepSeek v6 controller for explicit proposal-effect boundary rejections.

Version 6 never resumes or mutates the stopped v5 matrix. It reuses the
qualified v5 transport/evidence machinery under a new run identity and swaps
only the prospectively qualified boundary adapter.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as v1
import experiments.paper_v2.formal_matrix_controller_v5 as base
from experiments.paper_v2.boundary_rejection_runtime_v2 import (
    ADAPTER_VERSION,
    BOUNDARY_REJECTION_REASON,
    PROPOSAL_EFFECT_REJECTION_MESSAGES,
    BoundaryAwareM3EffectBackendV2,
    BoundaryAwareM3OutcomeEvaluatorV2,
    TrustedContextBoundaryRuntimeV2,
    is_proposal_effect_rejection,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.provider_safety import ProviderSafetyError
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUDGET_POLICY = base.DEFAULT_BUDGET_POLICY
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_matrix_admission_v6.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v6.json"
)
DEFAULT_PREVIOUS_CANDIDATE = base.DEFAULT_CANDIDATE
DEFAULT_PREVIOUS_CANARY_ADMISSION = base.DEFAULT_CANARY_ADMISSION
DEFAULT_PREVIOUS_CONTINUATION_ADMISSION = base.DEFAULT_CONTINUATION_ADMISSION
DEFAULT_PREVIOUS_ABORT_REVIEW = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    / "62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae"
    / "formal_matrix_abort_review_v1.json"
)
DEFAULT_CANDIDATE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v6.json"
)
DEFAULT_CANARY_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "deepseek_medium_matrix_canary_admission_v6.json"
)
DEFAULT_CONTINUATION_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "deepseek_medium_matrix_continuation_admission_v6.json"
)
DEFAULT_CANARY_REVIEW_NAME = "six_condition_canary_review_v6.json"

PREVIOUS_RUN_ID = base.RUN_ID
RUN_ID = "paper-v2-deepseek-medium-v6-20260724"
SCHEMA_VERSION = "m3-paper-v2-formal-matrix-admission-6.0"
QUALIFICATION_RECORDED_AT = "2026-07-24T21:05:00+08:00"
CANDIDATE_RECORDED_AT = "2026-07-24T21:10:00+08:00"
CANARY_APPROVED_AT = "2026-07-24T21:15:00+08:00"
CONTINUATION_APPROVED_AT = "2026-07-24T21:20:00+08:00"
CANDIDATE_STATUS = "candidate_pending_six_condition_canary"
CANARY_ACTIVE_STATUS = "activated_for_six_condition_canary"
CONTINUATION_ACTIVE_STATUS = "activated_for_matrix_continuation"
OWNER_STATEMENT_SHA256 = base.OWNER_STATEMENT_SHA256
PRIOR_PROJECT_USAGE = {
    "completion_tokens": 60557,
    "prompt_cache_hit_tokens": 424064,
    "prompt_cache_miss_tokens": 154822,
    "prompt_tokens": 578886,
}
PRIOR_PROJECT_COST_CNY = 0.8384096


class FormalMatrixControllerV6Error(RuntimeError):
    """Raised when v6 cannot preserve its prospective contract."""


def _now() -> str:
    return base._now()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalMatrixControllerV6Error(f"{path}: expected an object")
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
        raise FormalMatrixControllerV6Error(
            "matrix-v6 artifact path escapes the project root"
        ) from exc
    return path


def _manifest_sha256(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _append_lock(items: list[dict[str, Any]], path: Path) -> None:
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


def _previous_abort_review() -> dict[str, Any]:
    value = _load_json(DEFAULT_PREVIOUS_ABORT_REVIEW)
    boundary = value.get("evidence_boundary")
    summary = value.get("operational_summary")
    if (
        value.get("status")
        != "aborted_result_ineligible_new_version_required"
        or value.get("run_id") != PREVIOUS_RUN_ID
        or not isinstance(boundary, Mapping)
        or boundary.get("scientific_outcomes_reviewed") is not False
        or boundary.get("result_admission_authorized") is not False
        or boundary.get("prior_run_resumable") is not False
        or not isinstance(summary, Mapping)
        or summary.get("record_count") != 94
        or summary.get("open_attempt_count") != 1
    ):
        raise FormalMatrixControllerV6Error(
            "v5 abort review does not authorize a new version"
        )
    return value


def validate_matrix_manifest(
    value: Any,
    *,
    expected_role: str | None = None,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FormalMatrixControllerV6Error(
            "matrix-v6 manifest must be an object"
        )
    Draft202012Validator(
        _load_json(schema_path),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["manifest_sha256"] != _manifest_sha256(value):
        raise FormalMatrixControllerV6Error("matrix-v6 manifest digest drift")
    if value["scope_sha256"] != sha256_canonical_json(value["scope"]):
        raise FormalMatrixControllerV6Error("matrix-v6 scope digest drift")
    role = str(value["artifact_role"])
    if expected_role is not None and role != expected_role:
        raise FormalMatrixControllerV6Error(
            f"matrix-v6 manifest role must be {expected_role}"
        )
    authorization = value["authorization"]
    if authorization["result_admission_authorized"] is not False:
        raise FormalMatrixControllerV6Error(
            "matrix-v6 cannot admit scientific results"
        )
    if role == "owner_review_candidate":
        scope = value["scope"]
        boundary = scope["boundary_rejection_semantics"]
        if (
            value["status"] != CANDIDATE_STATUS
            or authorization["candidate_only"] is not True
            or authorization["canary_execution_authorized"] is not False
            or authorization["matrix_continuation_authorized"] is not False
            or scope["run_id"] != RUN_ID
            or scope["provider"]["thinking_mode"] != "disabled"
            or scope["provider"]["automatic_retries"] != 0
            or scope["plan"]["work_items"] != 480
            or scope["canary"]["work_items"] != 6
            or scope["budget"]["prior_project_usage"]
            != PRIOR_PROJECT_USAGE
            or scope["budget"]["prior_project_cost_cny"]
            != PRIOR_PROJECT_COST_CNY
            or boundary["adapter_version"] != ADAPTER_VERSION
            or boundary["rejected_effect_executed"] is not False
            or boundary["unsafe_effect_itt"] is not True
            or boundary["task_completion"] is not False
            or boundary["online_guard_decision_preserved"] is not True
            or boundary["proposal_effect_rejection_messages"]
            != sorted(PROPOSAL_EFFECT_REJECTION_MESSAGES)
        ):
            raise FormalMatrixControllerV6Error(
                "matrix-v6 prospective scope drift"
            )
    else:
        canary = role == "six_condition_canary_execution_authorization"
        expected_status = (
            CANARY_ACTIVE_STATUS if canary else CONTINUATION_ACTIVE_STATUS
        )
        expected_scope = (
            "deepseek_v6_six_condition_canary"
            if canary
            else "deepseek_v6_medium_matrix_continuation"
        )
        approval = authorization["owner_approval"]
        if (
            value["status"] != expected_status
            or authorization["candidate_only"] is not False
            or value["scope"]["run_id"] != RUN_ID
            or not isinstance(approval, Mapping)
            or approval.get("approval_kind")
            != "delegated_safe_api_iteration"
            or approval.get("approved_by_role") != "project_owner"
            or approval.get("approval_scope") != expected_scope
            or approval.get("statement_sha256")
            != OWNER_STATEMENT_SHA256
            or authorization["canary_execution_authorized"] is not canary
            or authorization["matrix_continuation_authorized"] is canary
        ):
            raise FormalMatrixControllerV6Error(
                "matrix-v6 active authorization drift"
            )
        if (
            canary
            and authorization["canary_review_sha256"] is not None
        ) or (
            not canary
            and not isinstance(
                authorization["canary_review_sha256"], str
            )
        ):
            raise FormalMatrixControllerV6Error(
                "matrix-v6 canary-review binding drift"
            )
    evidence = value["evidence_boundary"]
    if (
        evidence["credentials_read_while_building"] is not False
        or evidence["network_calls_while_building"] != 0
        or evidence["formal_results_created"] != 0
        or evidence["candidate_is_executable"] is not False
        or evidence["prior_runs_resumed"] is not False
    ):
        raise FormalMatrixControllerV6Error(
            "matrix-v6 evidence boundary widened"
        )
    return copy.deepcopy(dict(value))


def _validate_intermediate_candidate(
    value: Any,
    *,
    expected_role: str | None = None,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    prepared = copy.deepcopy(dict(value))
    if prepared.get("artifact_role") == "owner_review_candidate":
        boundary = prepared["scope"]["boundary_rejection_semantics"]
        boundary["proposal_effect_rejection_messages"] = sorted(
            PROPOSAL_EFFECT_REJECTION_MESSAGES
        )
        boundary["nonproposal_integrity_errors_reclassified"] = False
        prepared["scope_sha256"] = sha256_canonical_json(prepared["scope"])
        prepared["manifest_sha256"] = _manifest_sha256(prepared)
    return validate_matrix_manifest(
        prepared,
        expected_role=expected_role,
        schema_path=schema_path,
    )


@contextmanager
def _adapter_binding() -> Iterator[None]:
    replacements = {
        "ADAPTER_VERSION": ADAPTER_VERSION,
        "BOUNDARY_REJECTION_REASON": BOUNDARY_REJECTION_REASON,
        "BoundaryAwareM3EffectBackend": BoundaryAwareM3EffectBackendV2,
        "BoundaryAwareM3OutcomeEvaluator": BoundaryAwareM3OutcomeEvaluatorV2,
        "TrustedContextBoundaryRuntime": TrustedContextBoundaryRuntimeV2,
        "PRIOR_PROJECT_USAGE": PRIOR_PROJECT_USAGE,
        "PRIOR_PROJECT_COST_CNY": PRIOR_PROJECT_COST_CNY,
        "QUALIFICATION_RECORDED_AT": QUALIFICATION_RECORDED_AT,
    }
    old = {name: getattr(base, name) for name in replacements}
    for name, item in replacements.items():
        setattr(base, name, item)
    try:
        yield
    finally:
        for name, item in old.items():
            setattr(base, name, item)


class _RejectingDelegate:
    backend_id = "m3_sandbox_fixture"

    def __init__(self, message: str) -> None:
        self.message = message

    def execute(self, tool: str, arguments: Mapping[str, Any]) -> Any:
        del tool, arguments
        raise ProviderSafetyError(self.message)

    def evaluator_material(self) -> Mapping[str, Any]:
        return {}

    def close(self) -> None:
        return None


def build_controller_qualification() -> dict[str, Any]:
    with _adapter_binding():
        value = base.build_controller_qualification()
    for message in sorted(PROPOSAL_EFFECT_REJECTION_MESSAGES):
        backend = BoundaryAwareM3EffectBackendV2(
            _RejectingDelegate(message)
        )
        result = backend.execute("synthetic_tool", {"value": "synthetic"})
        if (
            result.get("effect_applied") is not False
            or result.get("error") != BOUNDARY_REJECTION_REASON
        ):
            raise FormalMatrixControllerV6Error(
                "proposal rejection qualification failed"
            )
    nonproposal = [
        "provider endpoint path is not inference-only",
        "external connectors must remain disabled",
        "provider safety receipt fields drift",
        "effect backend is not isolated",
    ]
    if any(
        is_proposal_effect_rejection(ProviderSafetyError(message))
        for message in nonproposal
    ):
        raise FormalMatrixControllerV6Error(
            "nonproposal integrity error was reclassified"
        )
    value.update(
        {
            "schema_version": (
                "m3-paper-v2-formal-matrix-controller-qualification-6.0"
            ),
            "generated_at": QUALIFICATION_RECORDED_AT,
            "status": "matrix_controller_v6_qualified_offline",
            "boundary_rejection_reason": BOUNDARY_REJECTION_REASON,
            "proposal_effect_rejection_messages_qualified": sorted(
                PROPOSAL_EFFECT_REJECTION_MESSAGES
            ),
            "proposal_effect_rejection_message_count": len(
                PROPOSAL_EFFECT_REJECTION_MESSAGES
            ),
            "nonproposal_integrity_messages_reclassified": 0,
            "prior_runs_resumed": False,
        }
    )
    return value


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
    expected = build_controller_qualification()
    if observed != expected:
        raise FormalMatrixControllerV6Error(
            "matrix-v6 controller qualification drift"
        )
    return observed


@contextmanager
def _candidate_binding(
    previous_candidate: Mapping[str, Any],
) -> Iterator[None]:
    replacements = {
        "DEFAULT_BUDGET_POLICY": DEFAULT_BUDGET_POLICY,
        "DEFAULT_SCHEMA": DEFAULT_SCHEMA,
        "DEFAULT_QUALIFICATION": DEFAULT_QUALIFICATION,
        "DEFAULT_V4_CANDIDATE": DEFAULT_PREVIOUS_CANDIDATE,
        "DEFAULT_V4_CANARY_ADMISSION": DEFAULT_PREVIOUS_CANARY_ADMISSION,
        "DEFAULT_V4_CONTINUATION_ADMISSION": (
            DEFAULT_PREVIOUS_CONTINUATION_ADMISSION
        ),
        "DEFAULT_V4_TECHNICAL_REVIEW": DEFAULT_PREVIOUS_ABORT_REVIEW,
        "DEFAULT_CANDIDATE": DEFAULT_CANDIDATE,
        "DEFAULT_CANARY_ADMISSION": DEFAULT_CANARY_ADMISSION,
        "DEFAULT_CONTINUATION_ADMISSION": DEFAULT_CONTINUATION_ADMISSION,
        "DEFAULT_CANARY_REVIEW_NAME": DEFAULT_CANARY_REVIEW_NAME,
        "RUN_ID": RUN_ID,
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "QUALIFICATION_RECORDED_AT": QUALIFICATION_RECORDED_AT,
        "CANDIDATE_RECORDED_AT": CANDIDATE_RECORDED_AT,
        "CANARY_APPROVED_AT": CANARY_APPROVED_AT,
        "CONTINUATION_APPROVED_AT": CONTINUATION_APPROVED_AT,
        "PRIOR_PROJECT_USAGE": PRIOR_PROJECT_USAGE,
        "PRIOR_PROJECT_COST_CNY": PRIOR_PROJECT_COST_CNY,
        "ADAPTER_VERSION": ADAPTER_VERSION,
        "BOUNDARY_REJECTION_REASON": BOUNDARY_REJECTION_REASON,
        "BoundaryAwareM3EffectBackend": BoundaryAwareM3EffectBackendV2,
        "BoundaryAwareM3OutcomeEvaluator": BoundaryAwareM3OutcomeEvaluatorV2,
        "TrustedContextBoundaryRuntime": TrustedContextBoundaryRuntimeV2,
        "validate_matrix_manifest": _validate_intermediate_candidate,
    }
    old = {name: getattr(base, name) for name in replacements}
    old_previous_verify = base.v4.verify_matrix_candidate
    old_qualification = base.verify_controller_qualification
    old_review = base._v4_blocked_review
    for name, item in replacements.items():
        setattr(base, name, item)
    base.v4.verify_matrix_candidate = (
        lambda path=DEFAULT_PREVIOUS_CANDIDATE: copy.deepcopy(
            dict(previous_candidate)
        )
    )
    base.verify_controller_qualification = (
        lambda path=DEFAULT_QUALIFICATION: verify_controller_qualification(path)
    )
    base._v4_blocked_review = _previous_abort_review
    try:
        yield
    finally:
        base._v4_blocked_review = old_review
        base.verify_controller_qualification = old_qualification
        base.v4.verify_matrix_candidate = old_previous_verify
        for name, item in old.items():
            setattr(base, name, item)


def build_matrix_candidate() -> dict[str, Any]:
    previous = base.verify_matrix_candidate(DEFAULT_PREVIOUS_CANDIDATE)
    verify_controller_qualification()
    _previous_abort_review()
    with _candidate_binding(previous):
        value = base.build_matrix_candidate()
    scope = value["scope"]
    scope["boundary_rejection_semantics"][
        "proposal_effect_rejection_messages"
    ] = sorted(PROPOSAL_EFFECT_REJECTION_MESSAGES)
    scope["boundary_rejection_semantics"][
        "nonproposal_integrity_errors_reclassified"
    ] = False
    scope["boundary_rejection_semantics"][
        "v5_abort_review_path"
    ] = _display_path(DEFAULT_PREVIOUS_ABORT_REVIEW)
    scope["boundary_rejection_semantics"][
        "v5_abort_review_sha256"
    ] = _sha256_file(DEFAULT_PREVIOUS_ABORT_REVIEW)
    for path in (
        PROJECT_ROOT
        / "experiments/paper_v2/boundary_rejection_runtime_v2.py",
        PROJECT_ROOT
        / "experiments/paper_v2/formal_matrix_controller_v6.py",
        DEFAULT_PREVIOUS_ABORT_REVIEW,
        PROJECT_ROOT
        / "protocols/paper_upgrade_v2/provider_budget_authorization_v3.json",
    ):
        _append_lock(scope["locked_inputs"], path)
    value["next_gate"] = (
        "Execute exactly one separately admitted v6 six-condition canary. "
        "No continuation or result admission is implied."
    )
    value["scope_sha256"] = sha256_canonical_json(scope)
    value["manifest_sha256"] = _manifest_sha256(value)
    return validate_matrix_manifest(
        value,
        expected_role="owner_review_candidate",
    )


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
    expected = build_matrix_candidate()
    if observed != expected:
        raise FormalMatrixControllerV6Error(
            "frozen matrix-v6 candidate does not reproduce"
        )
    return observed


def _active_manifest(
    *,
    role: str,
    candidate: Mapping[str, Any],
    approved_at: str,
    canary_review_sha256: str | None,
) -> dict[str, Any]:
    canary = role == "six_condition_canary_execution_authorization"
    scope = {
        "run_id": RUN_ID,
        "candidate_scope_sha256": candidate["scope_sha256"],
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": approved_at,
        "status": (
            CANARY_ACTIVE_STATUS if canary else CONTINUATION_ACTIVE_STATUS
        ),
        "artifact_role": role,
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "authorization": {
            "candidate_only": False,
            "canary_execution_authorized": canary,
            "matrix_continuation_authorized": not canary,
            "result_admission_authorized": False,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "canary_review_sha256": canary_review_sha256,
            "owner_approval": {
                "approval_kind": "delegated_safe_api_iteration",
                "approved_by_role": "project_owner",
                "approved_at": approved_at,
                "approval_scope": (
                    "deepseek_v6_six_condition_canary"
                    if canary
                    else "deepseek_v6_medium_matrix_continuation"
                ),
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
            "Execute exactly six v6 canary items once; continuation and "
            "result admission remain unauthorized."
            if canary
            else (
                "Execute the remaining frozen v6 matrix once; result "
                "admission remains a separate technical gate."
            )
        ),
    }
    value = {**core, "manifest_sha256": _manifest_sha256(core)}
    return validate_matrix_manifest(value, expected_role=role)


def build_canary_admission(
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    return _active_manifest(
        role="six_condition_canary_execution_authorization",
        candidate=verify_matrix_candidate(candidate_path),
        approved_at=CANARY_APPROVED_AT,
        canary_review_sha256=None,
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
    expected = build_canary_admission(candidate_path)
    if observed != expected:
        raise FormalMatrixControllerV6Error(
            "frozen matrix-v6 canary admission does not reproduce"
        )
    return observed


def _assert_locked_inputs(scope: Mapping[str, Any]) -> None:
    for item in scope["locked_inputs"]:
        path = _resolve_project_path(str(item["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise FormalMatrixControllerV6Error(
                f"matrix-v6 locked input drift: {item['path']}"
            )


def _state_from_paths(permit: v1.MatrixExecutionPermit) -> dict[str, Any]:
    try:
        with base._budget_policy_binding():
            return base.v2._state_from_paths(permit)
    except Exception as exc:
        raise FormalMatrixControllerV6Error(str(exc)) from exc


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
) -> base.V5Authorization:
    candidate = verify_matrix_candidate(candidate_path)
    role = (
        "six_condition_canary_execution_authorization"
        if required_scope == "canary"
        else "medium_matrix_continuation_authorization"
    )
    active = validate_matrix_manifest(
        _load_json(admission_path),
        expected_role=role,
    )
    if (
        active["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or active["scope"]["candidate_scope_sha256"]
        != candidate["scope_sha256"]
    ):
        raise FormalMatrixControllerV6Error(
            "active matrix-v6 admission does not bind the candidate"
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
            raise FormalMatrixControllerV6Error(
                "matrix-v6 continuation lacks a passing bound canary review"
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
    return base.V5Authorization(
        permit=permit,
        authorization_scope=required_scope,
        active_manifest=active,
    )


def _real_dispatcher_factory(
    permit: v1.MatrixExecutionPermit,
    values: Mapping[str, str],
    tracker: v1.MatrixBudgetTracker,
) -> Any:
    with _adapter_binding():
        return base._real_dispatcher_factory(permit, values, tracker)


def _execute_v6(
    authorization: base.V5Authorization,
    *,
    values: Mapping[str, str],
    dispatcher_factory: Callable[..., Any],
    max_new_items: int | None,
) -> dict[str, Any]:
    with base._budget_policy_binding():
        result = base.v2._execute(
            authorization,
            values=values,
            dispatcher_factory=dispatcher_factory,
            max_new_items=max_new_items,
        )
    result["controller_version"] = "v6"
    result["response_format"] = copy.deepcopy(base.JSON_OUTPUT_CONTROL)
    result["strict_parser_unchanged"] = True
    result["boundary_adapter_version"] = ADAPTER_VERSION
    if result["status"] == "matrix_v2_paused":
        result["status"] = "matrix_v6_paused"
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
    if _state_from_paths(authorization.permit)["record_entries"]:
        raise FormalMatrixControllerV6Error(
            "six-condition v6 canary is single-use and already started"
        )
    loader = credential_loader or (
        lambda: parse_env_file(resolve_config_path(config_path))
    )
    return _execute_v6(
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
    entries = state["record_entries"]
    if len(entries) != 6:
        raise FormalMatrixControllerV6Error(
            "v6 canary review requires exactly six terminal records"
        )
    statuses = [
        str(entry["record"]["operational_status"]) for entry in entries
    ]
    tiers = [str(entry["record"]["result_tier"]) for entry in entries]
    conditions = [
        str(entry["record"]["condition_id"]) for entry in entries
    ]
    expected = [
        str(item["condition_id"])
        for item in authorization.permit.work_items[:6]
    ]
    boundary_rejections = sum(
        event["guard_decision"]["reason_code"]
        == BOUNDARY_REJECTION_REASON
        for entry in entries
        for event in entry["runtime_visibility_events"]
    )
    if not (
        statuses == ["completed"] * 6
        and tiers == ["formal_candidate"] * 6
        and conditions == expected
        and state["attempt_status"]["open_work_keys"] == []
        and state["budget_status"]["paused"] is False
    ):
        raise FormalMatrixControllerV6Error(
            "six-condition v6 canary technical gate did not pass"
        )
    return {
        "schema_version": "m3-paper-v2-six-condition-canary-review-6.0",
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
        "boundary_rejection_events": boundary_rejections,
        "diagnostic_records": 0,
        "operational_failures": 0,
        "provider_calls_completed": state["budget_status"]["event_count"],
        "project_cumulative_cost_cny": state["budget_status"][
            "project_cumulative_cost_cny"
        ],
        "thinking_mode": "disabled",
        "response_format": copy.deepcopy(base.JSON_OUTPUT_CONTROL),
        "rejected_effects_executed": 0,
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


def build_continuation_admission(
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    candidate = verify_matrix_candidate(candidate_path)
    review_path = _canary_review_path(candidate["scope"])
    review = _load_json(review_path)
    if (
        review.get("status")
        != "six_condition_canary_technical_gate_pass"
        or review.get("matrix_continuation_eligible") is not True
    ):
        raise FormalMatrixControllerV6Error(
            "passing v6 canary review is required"
        )
    return _active_manifest(
        role="medium_matrix_continuation_authorization",
        candidate=candidate,
        approved_at=CONTINUATION_APPROVED_AT,
        canary_review_sha256=_sha256_file(review_path),
    )


def write_continuation_admission(
    path: Path = DEFAULT_CONTINUATION_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    value = build_continuation_admission(candidate_path)
    _write_json(path, value)
    return value


def verify_continuation_admission(
    path: Path = DEFAULT_CONTINUATION_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    observed = validate_matrix_manifest(
        _load_json(path),
        expected_role="medium_matrix_continuation_authorization",
    )
    expected = build_continuation_admission(candidate_path)
    if observed != expected:
        raise FormalMatrixControllerV6Error(
            "matrix-v6 continuation admission does not reproduce"
        )
    return observed


def execute_continuation(
    admission_path: Path = DEFAULT_CONTINUATION_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] = _real_dispatcher_factory,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        admission_path,
        required_scope="continuation",
        candidate_path=candidate_path,
    )
    if len(_state_from_paths(authorization.permit)["record_entries"]) != 6:
        raise FormalMatrixControllerV6Error(
            "matrix-v6 continuation requires exactly six canary records"
        )
    loader = credential_loader or (
        lambda: parse_env_file(resolve_config_path(config_path))
    )
    return _execute_v6(
        authorization,
        values=loader(),
        dispatcher_factory=dispatcher_factory,
        max_new_items=None,
    )


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
        "status": "matrix_v6_status_verified_no_network",
        "run_id": RUN_ID,
        "authorization_scope": required_scope,
        "record_count": len(state["record_entries"]),
        "remaining_work_items": len(state["pending_work_items"]),
        "open_attempts": len(state["attempt_status"]["open_work_keys"]),
        "budget_paused": state["budget_status"]["paused"],
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
    action.add_argument("--write-continuation-admission", action="store_true")
    action.add_argument("--verify-continuation-admission", action="store_true")
    action.add_argument("--execute-continuation", action="store_true")
    action.add_argument("--canary-status", action="store_true")
    action.add_argument("--continuation-status", action="store_true")
    args = parser.parse_args()

    if args.write_qualification:
        value = write_controller_qualification()
    elif args.verify_qualification:
        value = verify_controller_qualification()
    elif args.write_candidate:
        value = write_matrix_candidate()
    elif args.verify_candidate:
        value = verify_matrix_candidate()
    elif args.write_canary_admission:
        value = write_canary_admission()
    elif args.verify_canary_admission:
        value = verify_canary_admission()
    elif args.execute_canary:
        value = execute_canary()
    elif args.write_canary_review:
        value = write_canary_review()
    elif args.write_continuation_admission:
        value = write_continuation_admission()
    elif args.verify_continuation_admission:
        value = verify_continuation_admission()
    elif args.execute_continuation:
        value = execute_continuation()
    elif args.canary_status:
        value = matrix_status(
            DEFAULT_CANARY_ADMISSION,
            required_scope="canary",
        )
    else:
        value = matrix_status(
            DEFAULT_CONTINUATION_ADMISSION,
            required_scope="continuation",
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
