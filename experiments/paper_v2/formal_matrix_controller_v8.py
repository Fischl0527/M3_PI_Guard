"""绑定执行生命周期适配器的 DeepSeek v8 控制器。

提供对实验初始化、提案生成、安全仲裁和事后判分各阶段的全生命周期钩子。
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
import experiments.paper_v2.formal_matrix_controller_v7 as previous
from experiments.paper_v2.boundary_rejection_runtime_v3 import (
    ADAPTER_VERSION,
    BOUNDARY_REJECTION_REASON,
    PROPOSAL_EFFECT_REJECTION_MESSAGES,
    PROPOSAL_MESSAGE_DIGESTS,
    BoundaryAwareM3EffectBackendV3,
    validate_boundary_rejections_v3,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_matrix_abort_review_v3 import (
    verify_abort_review,
)
from experiments.paper_v2.provider_safety import ProviderSafetyError
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_BUDGET_POLICY = previous.DEFAULT_BUDGET_POLICY
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_matrix_admission_v8.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_matrix_controller_qualification_v8.json"
)
DEFAULT_PREVIOUS_CANDIDATE = previous.DEFAULT_CANDIDATE
DEFAULT_PREVIOUS_ABORT_REVIEW = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    / "a34fe5b87607cb48144b0d36da282accc25d33cd18706351eb39dd25ebe04c75"
    / "formal_matrix_abort_review_v3.json"
)
DEFAULT_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_matrix_candidate_v8.json"
)
DEFAULT_CANARY_ADMISSION = (
    PROTOCOL_ROOT
    / "admissions/deepseek_medium_matrix_canary_admission_v8.json"
)
DEFAULT_CONTINUATION_ADMISSION = (
    PROTOCOL_ROOT
    / "admissions/deepseek_medium_matrix_continuation_admission_v8.json"
)
DEFAULT_CANARY_REVIEW_NAME = "six_condition_canary_review_v8.json"

RUN_ID = "paper-v2-deepseek-medium-v8-20260726"
SCHEMA_VERSION = "m3-paper-v2-formal-matrix-admission-8.0"
QUALIFICATION_RECORDED_AT = "2026-07-26T11:20:00+08:00"
CANDIDATE_RECORDED_AT = "2026-07-26T11:25:00+08:00"
CANARY_APPROVED_AT = "2026-07-26T11:30:00+08:00"
CONTINUATION_APPROVED_AT = "2026-07-26T11:35:00+08:00"
CANDIDATE_STATUS = "candidate_pending_six_condition_canary"
CANARY_ACTIVE_STATUS = "activated_for_six_condition_canary"
CONTINUATION_ACTIVE_STATUS = "activated_for_matrix_continuation"
OWNER_STATEMENT_SHA256 = previous.OWNER_STATEMENT_SHA256
PRIOR_PROJECT_USAGE = {
    "completion_tokens": 67985,
    "prompt_cache_hit_tokens": 473600,
    "prompt_cache_miss_tokens": 162643,
    "prompt_tokens": 636243,
}
PRIOR_PROJECT_COST_CNY = 0.907679
LIFECYCLE_BINDING = "full_execute_scope"


class FormalMatrixControllerV8Error(RuntimeError):
    """当 v8 无法保持其前瞻性契约时抛出的异常。"""


def _now() -> str:
    return previous._now()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalMatrixControllerV8Error(f"{path}: expected an object")
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
        raise FormalMatrixControllerV8Error(
            "matrix-v8 artifact path escapes the project root"
        ) from exc
    return path


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _artifact_lock(path: Path) -> dict[str, Any]:
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _append_lock(items: list[dict[str, Any]], path: Path) -> None:
    display = _display_path(path)
    if any(item["path"] == display for item in items):
        return
    items.append(_artifact_lock(path))


def validate_matrix_manifest(
    value: Any,
    *,
    expected_role: str | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FormalMatrixControllerV8Error(
            "matrix-v8 manifest must be an object"
        )
    Draft202012Validator(
        _load_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["manifest_sha256"] != _manifest_sha(value):
        raise FormalMatrixControllerV8Error("matrix-v8 manifest digest drift")
    if value["scope_sha256"] != sha256_canonical_json(value["scope"]):
        raise FormalMatrixControllerV8Error("matrix-v8 scope digest drift")
    role = str(value["artifact_role"])
    if expected_role is not None and role != expected_role:
        raise FormalMatrixControllerV8Error(
            f"matrix-v8 manifest role must be {expected_role}"
        )
    authorization = value["authorization"]
    if authorization["result_admission_authorized"] is not False:
        raise FormalMatrixControllerV8Error(
            "matrix-v8 cannot admit scientific results"
        )
    if role == "owner_review_candidate":
        scope = value["scope"]
        boundary = scope["boundary_rejection_semantics"]
        repair = scope["lifecycle_binding_repair"]
        if (
            value["status"] != CANDIDATE_STATUS
            or authorization["candidate_only"] is not True
            or authorization["canary_execution_authorized"] is not False
            or authorization["matrix_continuation_authorized"] is not False
            or scope["run_id"] != RUN_ID
            or scope["plan"]["work_items"] != 480
            or scope["canary"]["work_items"] != 6
            or scope["provider"]["automatic_retries"] != 0
            or scope["budget"]["prior_project_usage"] != PRIOR_PROJECT_USAGE
            or scope["budget"]["prior_project_cost_cny"]
            != PRIOR_PROJECT_COST_CNY
            or boundary["adapter_version"] != ADAPTER_VERSION
            or boundary["qualification_path"]
            != _display_path(DEFAULT_QUALIFICATION)
            or boundary["qualification_sha256"]
            != _sha256_file(DEFAULT_QUALIFICATION)
            or boundary["proposal_message_digests"]
            != sorted(PROPOSAL_MESSAGE_DIGESTS)
            or boundary["rejected_effect_executed"] is not False
            or scope["failure_persistence"]["adapter_version"]
            != ADAPTER_VERSION
            or repair["binding_scope"] != LIFECYCLE_BINDING
            or repair["lazy_backend_resolution_qualified"] is not True
            or repair["v7_resumable"] is not False
        ):
            raise FormalMatrixControllerV8Error(
                "matrix-v8 prospective scope drift"
            )
    else:
        canary = role == "six_condition_canary_execution_authorization"
        expected_status = (
            CANARY_ACTIVE_STATUS if canary else CONTINUATION_ACTIVE_STATUS
        )
        expected_scope = (
            "deepseek_v8_six_condition_canary"
            if canary
            else "deepseek_v8_medium_matrix_continuation"
        )
        approval = authorization["owner_approval"]
        if (
            value["status"] != expected_status
            or value["scope"]["run_id"] != RUN_ID
            or authorization["candidate_only"] is not False
            or authorization["canary_execution_authorized"] is not canary
            or authorization["matrix_continuation_authorized"] is canary
            or not isinstance(approval, Mapping)
            or approval.get("approval_scope") != expected_scope
            or approval.get("statement_sha256") != OWNER_STATEMENT_SHA256
        ):
            raise FormalMatrixControllerV8Error(
                "matrix-v8 active authorization drift"
            )
    evidence = value["evidence_boundary"]
    if (
        evidence["credentials_read_while_building"] is not False
        or evidence["network_calls_while_building"] != 0
        or evidence["formal_results_created"] != 0
        or evidence["candidate_is_executable"] is not False
        or evidence["prior_runs_resumed"] is not False
    ):
        raise FormalMatrixControllerV8Error(
            "matrix-v8 evidence boundary widened"
        )
    return copy.deepcopy(dict(value))


class _RejectingDelegate:
    backend_id = "m3_sandbox_fixture"

    def __init__(self, message: str) -> None:
        self.message = message

    def execute(self, tool: str, arguments: Mapping[str, Any]) -> Any:
        del tool, arguments
        raise ProviderSafetyError(self.message)

    def evaluator_material(self) -> Mapping[str, Any]:
        return {"qualification": True}

    def close(self) -> None:
        return None


@contextmanager
def _adapter_binding() -> Iterator[None]:
    with previous._adapter_binding():
        yield


def _delayed_backend(message: str) -> Any:
    backend_class = previous.previous.base.BoundaryAwareM3EffectBackend
    return backend_class(_RejectingDelegate(message))


def build_controller_qualification() -> dict[str, Any]:
    verified = 0
    for message in sorted(PROPOSAL_EFFECT_REJECTION_MESSAGES):
        with _adapter_binding():
            backend = _delayed_backend(message)
            result = backend.execute(
                "synthetic_tool",
                {"nested": {"value": 1}, "items": ["a", "b"]},
            )
            material = backend.evaluator_material()
        if (
            not isinstance(backend, BoundaryAwareM3EffectBackendV3)
            or result.get("effect_applied") is not False
            or result.get("error") != BOUNDARY_REJECTION_REASON
            or validate_boundary_rejections_v3(material) != 1
        ):
            raise FormalMatrixControllerV8Error(
                "delayed backend lifecycle qualification failed"
            )
        verified += 1
    return {
        "schema_version": (
            "m3-paper-v2-formal-matrix-controller-qualification-8.0"
        ),
        "generated_at": QUALIFICATION_RECORDED_AT,
        "status": "matrix_controller_v8_qualified_offline",
        "boundary_adapter_version": ADAPTER_VERSION,
        "boundary_rejection_reason": BOUNDARY_REJECTION_REASON,
        "adapter_binding_scope": LIFECYCLE_BINDING,
        "proposal_effect_rejection_messages_qualified": sorted(
            PROPOSAL_EFFECT_REJECTION_MESSAGES
        ),
        "proposal_message_digests_qualified": sorted(
            PROPOSAL_MESSAGE_DIGESTS
        ),
        "delayed_backend_resolution_scenarios": verified,
        "network_calls_made": 0,
        "credentials_read": False,
        "formal_results_created": 0,
        "scientific_outcomes_read": 0,
        "automatic_retries": 0,
        "prior_runs_resumed": False,
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
        raise FormalMatrixControllerV8Error(
            "matrix-v8 controller qualification drift"
        )
    return observed


def _new_matrix_identity(previous_candidate: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            "run_id": RUN_ID,
            "plan_sha256": previous_candidate["scope"]["plan"]["sha256"],
            "previous_candidate_sha256": previous_candidate[
                "manifest_sha256"
            ],
            "adapter_version": ADAPTER_VERSION,
            "adapter_binding_scope": LIFECYCLE_BINDING,
        }
    )


def build_matrix_candidate() -> dict[str, Any]:
    prior = previous.verify_matrix_candidate(DEFAULT_PREVIOUS_CANDIDATE)
    abort_review = verify_abort_review(DEFAULT_PREVIOUS_ABORT_REVIEW)
    verify_controller_qualification()
    scope = copy.deepcopy(prior["scope"])
    identity = _new_matrix_identity(prior)
    output_root = (
        PROJECT_ROOT
        / "outputs/paper_upgrade_v2/formal_medium/deepseek"
        / identity
    )
    scope["run_id"] = RUN_ID
    scope["matrix_identity"] = identity
    scope["outputs"] = {
        "root": _display_path(output_root),
        "record_ledger_path": _display_path(
            output_root / "experiment_records_v2.jsonl"
        ),
        "attempt_ledger_path": _display_path(
            output_root / "matrix_attempts_v1.jsonl"
        ),
        "budget_ledger_path": _display_path(
            output_root / "matrix_budget_v1.jsonl"
        ),
        "trace_root": _display_path(output_root / "provider_traces"),
        "single_trace_per_work_item": True,
        "automatic_resume_of_open_attempts": False,
    }
    scope["budget"]["prior_project_usage"] = copy.deepcopy(
        PRIOR_PROJECT_USAGE
    )
    scope["budget"]["prior_project_cost_cny"] = PRIOR_PROJECT_COST_CNY
    scope["replaces_aborted_run"] = {
        "run_id": previous.RUN_ID,
        "matrix_identity": prior["scope"]["matrix_identity"],
        "review_path": _display_path(DEFAULT_PREVIOUS_ABORT_REVIEW),
        "review_sha256": _sha256_file(DEFAULT_PREVIOUS_ABORT_REVIEW),
        "old_run_resumable": False,
        "old_records_result_eligible": False,
    }
    scope["canary"]["review_filename"] = DEFAULT_CANARY_REVIEW_NAME
    boundary = scope["boundary_rejection_semantics"]
    boundary.pop("v6_abort_review_path", None)
    boundary.pop("v6_abort_review_sha256", None)
    boundary.update(
        {
            "adapter_version": ADAPTER_VERSION,
            "qualification_path": _display_path(DEFAULT_QUALIFICATION),
            "qualification_sha256": _sha256_file(DEFAULT_QUALIFICATION),
            "reason_code": BOUNDARY_REJECTION_REASON,
            "proposal_effect_rejection_messages": sorted(
                PROPOSAL_EFFECT_REJECTION_MESSAGES
            ),
            "proposal_message_digests": sorted(PROPOSAL_MESSAGE_DIGESTS),
            "end_to_end_evidence_validation": True,
            "nonproposal_integrity_errors_reclassified": False,
            "rejected_effect_executed": False,
            "unsafe_effect_itt": True,
            "task_completion": False,
            "online_guard_decision_preserved": True,
            "v7_abort_review_path": _display_path(
                DEFAULT_PREVIOUS_ABORT_REVIEW
            ),
            "v7_abort_review_sha256": _sha256_file(
                DEFAULT_PREVIOUS_ABORT_REVIEW
            ),
        }
    )
    scope["failure_persistence"]["adapter_version"] = ADAPTER_VERSION
    scope["lifecycle_binding_repair"] = {
        "binding_scope": LIFECYCLE_BINDING,
        "lazy_backend_resolution_qualified": True,
        "v7_resumable": False,
        "v7_record_count": abort_review["operational_summary"][
            "record_count"
        ],
        "v7_open_attempt_count": abort_review["operational_summary"][
            "open_attempt_count"
        ],
        "v7_provider_calls_completed": abort_review[
            "operational_summary"
        ]["provider_calls_completed"],
        "scientific_outcomes_read": False,
    }
    locked = scope["locked_inputs"]
    for path in (
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/boundary_rejection_runtime_v3.py",
        PROJECT_ROOT
        / "experiments/paper_v2/formal_matrix_abort_review_v3.py",
        DEFAULT_PREVIOUS_ABORT_REVIEW,
        DEFAULT_SCHEMA,
        DEFAULT_QUALIFICATION,
        PROTOCOL_ROOT / "provider_budget_authorization_v3.json",
    ):
        _append_lock(locked, path)
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
            "Execute exactly one separately admitted v8 six-condition "
            "canary. No continuation or result admission is implied."
        ),
    }
    return validate_matrix_manifest(
        {**core, "manifest_sha256": _manifest_sha(core)},
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
    if observed != build_matrix_candidate():
        raise FormalMatrixControllerV8Error(
            "frozen matrix-v8 candidate does not reproduce"
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
                    "deepseek_v8_six_condition_canary"
                    if canary
                    else "deepseek_v8_medium_matrix_continuation"
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
            "Execute exactly six v8 canary items once."
            if canary
            else "Execute the remaining frozen v8 matrix once."
        ),
    }
    return validate_matrix_manifest(
        {**core, "manifest_sha256": _manifest_sha(core)},
        expected_role=role,
    )


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
) -> dict[str, Any]:
    value = build_canary_admission()
    _write_json(path, value)
    return value


def verify_canary_admission(
    path: Path = DEFAULT_CANARY_ADMISSION,
) -> dict[str, Any]:
    observed = validate_matrix_manifest(
        _load_json(path),
        expected_role="six_condition_canary_execution_authorization",
    )
    if observed != build_canary_admission():
        raise FormalMatrixControllerV8Error(
            "matrix-v8 canary admission drift"
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
            raise FormalMatrixControllerV8Error(
                f"matrix-v8 locked input drift: {item['path']}"
            )


def _state_from_paths(permit: v1.MatrixExecutionPermit) -> dict[str, Any]:
    try:
        with previous.previous.base._budget_policy_binding():
            return previous.previous.base.v2._state_from_paths(permit)
    except Exception as exc:
        raise FormalMatrixControllerV8Error(str(exc)) from exc


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
) -> previous.previous.base.V5Authorization:
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
        raise FormalMatrixControllerV8Error(
            "active matrix-v8 admission does not bind the candidate"
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
            raise FormalMatrixControllerV8Error(
                "matrix-v8 continuation lacks a passing canary review"
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
    return previous.previous.base.V5Authorization(
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
        return previous.previous.base._real_dispatcher_factory(
            permit,
            values,
            tracker,
        )


def _execute(
    authorization: previous.previous.base.V5Authorization,
    *,
    values: Mapping[str, str],
    dispatcher_factory: Callable[..., Any],
    max_new_items: int | None,
) -> dict[str, Any]:
    with (
        _adapter_binding(),
        previous.previous.base._budget_policy_binding(),
    ):
        result = previous.previous.base.v2._execute(
            authorization,
            values=values,
            dispatcher_factory=dispatcher_factory,
            max_new_items=max_new_items,
        )
    result["controller_version"] = "v8"
    result["boundary_adapter_version"] = ADAPTER_VERSION
    result["adapter_binding_scope"] = LIFECYCLE_BINDING
    if result["status"] == "matrix_v2_paused":
        result["status"] = "matrix_v8_paused"
    return result


def execute_canary(
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] = _real_dispatcher_factory,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        DEFAULT_CANARY_ADMISSION,
        required_scope="canary",
    )
    state = _state_from_paths(authorization.permit)
    if state["record_entries"] or state["attempt_events"]:
        raise FormalMatrixControllerV8Error(
            "six-condition v8 canary is already started"
        )
    loader = credential_loader or (
        lambda: parse_env_file(resolve_config_path(config_path))
    )
    return _execute(
        authorization,
        values=loader(),
        dispatcher_factory=dispatcher_factory,
        max_new_items=6,
    )


def build_canary_review() -> dict[str, Any]:
    authorization = authorize_matrix(
        DEFAULT_CANARY_ADMISSION,
        required_scope="canary",
    )
    state = _state_from_paths(authorization.permit)
    entries = state["record_entries"]
    if len(entries) != 6:
        raise FormalMatrixControllerV8Error(
            "v8 canary review requires exactly six records"
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
        raise FormalMatrixControllerV8Error(
            "six-condition v8 canary technical gate did not pass"
        )
    return {
        "schema_version": "m3-paper-v2-six-condition-canary-review-8.0",
        "generated_at": _now(),
        "status": "six_condition_canary_technical_gate_pass",
        "run_id": RUN_ID,
        "candidate_manifest_sha256": verify_matrix_candidate()[
            "manifest_sha256"
        ],
        "canary_admission_file_sha256": _sha256_file(
            DEFAULT_CANARY_ADMISSION
        ),
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
        "rejected_effects_executed": 0,
        "scientific_outcomes_reviewed": False,
        "operational_metadata_reviewed": True,
        "matrix_continuation_eligible": True,
        "matrix_continuation_authorized": False,
        "result_admission_authorized": False,
    }


def write_canary_review() -> dict[str, Any]:
    value = build_canary_review()
    candidate = verify_matrix_candidate()
    _write_json(_canary_review_path(candidate["scope"]), value)
    return value


def build_continuation_admission() -> dict[str, Any]:
    candidate = verify_matrix_candidate()
    review_path = _canary_review_path(candidate["scope"])
    review = _load_json(review_path)
    if (
        review.get("status")
        != "six_condition_canary_technical_gate_pass"
        or review.get("matrix_continuation_eligible") is not True
    ):
        raise FormalMatrixControllerV8Error(
            "passing v8 canary review is required"
        )
    return _active_manifest(
        role="medium_matrix_continuation_authorization",
        candidate=candidate,
        approved_at=CONTINUATION_APPROVED_AT,
        canary_review_sha256=_sha256_file(review_path),
    )


def write_continuation_admission(
    path: Path = DEFAULT_CONTINUATION_ADMISSION,
) -> dict[str, Any]:
    value = build_continuation_admission()
    _write_json(path, value)
    return value


def verify_continuation_admission(
    path: Path = DEFAULT_CONTINUATION_ADMISSION,
) -> dict[str, Any]:
    observed = validate_matrix_manifest(
        _load_json(path),
        expected_role="medium_matrix_continuation_authorization",
    )
    if observed != build_continuation_admission():
        raise FormalMatrixControllerV8Error(
            "matrix-v8 continuation admission drift"
        )
    return observed


def execute_continuation(
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] = _real_dispatcher_factory,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        DEFAULT_CONTINUATION_ADMISSION,
        required_scope="continuation",
    )
    if len(_state_from_paths(authorization.permit)["record_entries"]) != 6:
        raise FormalMatrixControllerV8Error(
            "matrix-v8 continuation requires six canary records"
        )
    loader = credential_loader or (
        lambda: parse_env_file(resolve_config_path(config_path))
    )
    return _execute(
        authorization,
        values=loader(),
        dispatcher_factory=dispatcher_factory,
        max_new_items=None,
    )


def matrix_status(
    admission_path: Path,
    *,
    required_scope: str,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        admission_path,
        required_scope=required_scope,
    )
    state = _state_from_paths(authorization.permit)
    return {
        "status": "matrix_v8_status_verified_no_network",
        "run_id": RUN_ID,
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
    action.add_argument(
        "--verify-continuation-admission",
        action="store_true",
    )
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
