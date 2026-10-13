"""面向固化的 DeepSeek paper-v2 中等规模矩阵的故障安全（Fail-Closed）控制器。

调度多模型、多条件的完整评测矩阵，严格限制 API 调用配额并记录审计日志。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from experiments.paper_v2.agentdojo_live_dependency import (
    FrozenAgentDojoCaseResolver,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    OnlineExecutorContext,
    build_condition_dispatcher,
)
from experiments.paper_v2.formal_record_store_v2 import (
    append_execution_result,
    load_record_entries,
    validate_record_entries,
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
from experiments.paper_v2.medium_runtime import reconstruct_initial_online_state
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    OfficialProviderCompletion,
    ProviderBudgetState,
    ProviderPausedError,
)
from experiments.paper_v2.promptguard_live_dependency import (
    PinnedPromptGuardDetector,
)
from experiments.paper_v2.provider_budget import (
    BudgetPolicyError,
    check_deepseek_headroom,
    deepseek_cost_cny,
    validate_deepseek_usage,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    validate_trace_rows,
)
from experiments.paper_v2.provider_live_qualification import (
    CONSENT_VALUE,
    PROVIDER_CONFIG,
)
from experiments.paper_v2.vigil_live_dependency import (
    VigilOfficialConstraintFactory,
)
from m3_core.project_config import (
    is_placeholder,
    parse_env_file,
    resolve_config_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_execution_plan_v2.jsonl"
)
DEFAULT_EXECUTION_MANIFEST = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_execution_manifest_v2.json"
)
DEFAULT_PREFLIGHT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/medium_execution_manifest_v3_preflight.json"
)
DEFAULT_BUDGET_POLICY = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"
)
DEFAULT_SAFETY_POLICY = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/provider_safety_policy_v1.json"
)
DEFAULT_TRACE_ACTIVATION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/provider_request_trace_activation_v2.json"
)
DEFAULT_PILOT_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions/deepseek_pilot_admission_v2.json"
)
DEFAULT_PILOT_REVIEW = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_pilot/deepseek"
    / "fd89c79707414a035a9d4309c3c3125bde14f7260c0e4c9cd66088164076fbe7"
    / "post_pilot_review_v1.json"
)
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_matrix_admission_v1.schema.json"
)
DEFAULT_CANDIDATE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v1.json"
)
DEFAULT_ACTIVE_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "deepseek_medium_matrix_admission_v1.json"
)
DEFAULT_QUALIFICATION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v1.json"
)
RUN_ID = "paper-v2-deepseek-medium-v1-20260724"
CANDIDATE_RECORDED_AT = "2026-07-24T15:40:00+08:00"
SCHEMA_VERSION = "m3-paper-v2-formal-matrix-admission-1.0"
CANDIDATE_STATUS = "candidate_pending_owner_activation"
ACTIVE_STATUS = "activated_for_deepseek_medium_matrix"
ATTEMPT_SCHEMA_VERSION = "m3-paper-v2-matrix-attempt-event-1.0"
BUDGET_SCHEMA_VERSION = "m3-paper-v2-matrix-budget-event-1.0"
QUALIFICATION_RECORDED_AT = "2026-07-24T15:45:00+08:00"
PRIOR_PILOT_USAGE = {
    "prompt_tokens": 278,
    "prompt_cache_hit_tokens": 0,
    "prompt_cache_miss_tokens": 278,
    "completion_tokens": 136,
}

LOCKED_INPUTS = (
    DEFAULT_PLAN,
    DEFAULT_EXECUTION_MANIFEST,
    DEFAULT_PREFLIGHT,
    DEFAULT_BUDGET_POLICY,
    DEFAULT_SAFETY_POLICY,
    DEFAULT_TRACE_ACTIVATION,
    DEFAULT_PILOT_ADMISSION,
    DEFAULT_PILOT_REVIEW,
    PROJECT_ROOT / "experiments/paper_v2/formal_matrix_controller_v1.py",
    PROJECT_ROOT / "schemas/paper_v2/formal_matrix_admission_v1.schema.json",
    PROJECT_ROOT / "experiments/paper_v2/live_condition_runtime.py",
    PROJECT_ROOT / "experiments/paper_v2/formal_condition_executors.py",
    PROJECT_ROOT / "experiments/paper_v2/formal_record_store_v2.py",
    PROJECT_ROOT / "experiments/paper_v2/contracts_v2.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_trace_bundle.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_request_trace_candidate.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_request_trace_activation.py",
    PROJECT_ROOT / "experiments/paper_v2/official_provider_executor.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_budget.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_safety.py",
    PROJECT_ROOT / "experiments/paper_v2/promptguard_live_dependency.py",
    PROJECT_ROOT / "experiments/paper_v2/agentdojo_live_dependency.py",
    PROJECT_ROOT / "experiments/paper_v2/m3_offline_evaluator.py",
    PROJECT_ROOT / "experiments/paper_v2/vigil_live_dependency.py",
    PROJECT_ROOT / "schemas/paper_v2/experiment_record_v2.schema.json",
    PROJECT_ROOT / "schemas/paper_v2/provider_trace_bundle_v2.schema.json",
    PROJECT_ROOT / "schemas/paper_v2/provider_safety_receipt_v1.schema.json",
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/promptguard_live_dependency_qualification_v1.json",
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/agentdojo_live_dependency_qualification_v1.json",
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/vigil_live_dependency_qualification_v1.json",
    DEFAULT_QUALIFICATION,
)

ATTEMPT_EVENT_FIELDS = {
    "schema_version",
    "ledger_sequence",
    "previous_event_sha256",
    "run_id",
    "execution_identity",
    "work_key",
    "attempt_id",
    "event_type",
    "recorded_at",
    "record_entry_sha256",
    "event_sha256",
}
BUDGET_EVENT_FIELDS = {
    "schema_version",
    "ledger_sequence",
    "previous_event_sha256",
    "run_id",
    "execution_identity",
    "work_key",
    "call_index",
    "provider_response_id",
    "usage",
    "request_cost_cny",
    "project_cumulative_usage",
    "project_cumulative_cost_cny",
    "budget_status_after_request",
    "recorded_at",
    "event_sha256",
}


class FormalMatrixControllerError(RuntimeError):
    """在矩阵边界被拓宽或论据损坏前抛出的异常。"""


@dataclass(frozen=True)
class MatrixExecutionPermit:
    admission_file_sha256: str
    run_id: str
    execution_identity: str
    work_items: tuple[dict[str, Any], ...]
    output_root: Path
    record_ledger_path: Path
    attempt_ledger_path: Path
    budget_ledger_path: Path
    trace_root: Path
    max_tokens: int
    timeout_seconds: float
    scope: Mapping[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalMatrixControllerError(f"{path}: expected a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise FormalMatrixControllerError(
                    f"{path}:{line_number}: blank JSONL row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise FormalMatrixControllerError(
                    f"{path}:{line_number}: expected an object"
                )
            rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FormalMatrixControllerError(
            f"{path}: invalid UTF-8 JSONL"
        ) from exc
    return rows


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise FormalMatrixControllerError(
            "matrix artifact path escapes the project root"
        ) from exc
    return path


def _manifest_sha256(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _event_sha256(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "event_sha256"}
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _locked_inputs() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in LOCKED_INPUTS:
        if not path.is_file():
            raise FormalMatrixControllerError(
                f"missing matrix input: {_display_path(path)}"
            )
        result.append(
            {
                "path": _display_path(path),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return result


def _assert_locked_inputs(scope: Mapping[str, Any]) -> None:
    for item in scope["locked_inputs"]:
        path = _resolve_project_path(str(item["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise FormalMatrixControllerError(
                f"matrix locked input drift: {item['path']}"
            )


def _plan_rows(path: Path = DEFAULT_PLAN) -> list[dict[str, Any]]:
    rows = _load_jsonl(path)
    if len(rows) != 480:
        raise FormalMatrixControllerError("matrix plan must contain 480 items")
    if [row.get("sequence") for row in rows] != list(range(1, 481)):
        raise FormalMatrixControllerError("matrix plan sequence drift")
    identities = {str(row.get("execution_identity")) for row in rows}
    if len(identities) != 1:
        raise FormalMatrixControllerError(
            "matrix plan must use one execution identity"
        )
    keys = [str(row.get("work_key")) for row in rows]
    if len(keys) != len(set(keys)):
        raise FormalMatrixControllerError("matrix work keys are not unique")
    if sum(int(row["max_provider_calls"]) for row in rows) != 4416:
        raise FormalMatrixControllerError("matrix provider-call bound drift")
    return rows


def _validate_pilot_review() -> dict[str, Any]:
    review = _load_json(DEFAULT_PILOT_REVIEW)
    decision = review.get("decision")
    observations = review.get("observations")
    if (
        review.get("status") != "official_pilot_technical_gate_pass"
        or not isinstance(decision, Mapping)
        or decision.get("official_evidence_gate_passed") is not True
        or decision.get("ready_for_owner_matrix_review") is not True
        or decision.get("formal_matrix_authorized") is not False
        or decision.get("result_admission_authorized") is not False
        or not isinstance(observations, Mapping)
        or observations.get("provider_id") != "deepseek"
        or observations.get("model_id") != "deepseek-v4-pro"
        or observations.get("provider_managed_tools_enabled") is not False
        or observations.get("external_connectors_enabled") is not False
        or observations.get("within_abort_ceiling") is not True
    ):
        raise FormalMatrixControllerError(
            "official pilot review does not authorize a matrix-design review"
        )
    checks = review.get("checks")
    if (
        not isinstance(checks, list)
        or len(checks) != 15
        or any(item.get("passed") is not True for item in checks)
    ):
        raise FormalMatrixControllerError(
            "official pilot review checks are incomplete"
        )
    return review


def build_matrix_candidate() -> dict[str, Any]:
    """构建确定性、不可执行的所有者审查候选对象。"""

    rows = _plan_rows()
    review = _validate_pilot_review()
    execution_identity = str(rows[0]["execution_identity"])
    matrix_identity = sha256_canonical_json(
        {
            "run_id": RUN_ID,
            "execution_identity": execution_identity,
            "plan_sha256": _sha256_file(DEFAULT_PLAN),
            "pilot_review_sha256": _sha256_file(DEFAULT_PILOT_REVIEW),
            "provider_id": "deepseek",
            "model_id": "deepseek-v4-pro",
        }
    )
    output_root = (
        Path("outputs/paper_upgrade_v2/formal_medium/deepseek")
        / matrix_identity
    )
    prior_cost = float(
        deepseek_cost_cny(
            _load_json(DEFAULT_BUDGET_POLICY),
            cache_hit_input_tokens=PRIOR_PILOT_USAGE[
                "prompt_cache_hit_tokens"
            ],
            cache_miss_input_tokens=PRIOR_PILOT_USAGE[
                "prompt_cache_miss_tokens"
            ],
            output_tokens=PRIOR_PILOT_USAGE["completion_tokens"],
        )
    )
    scope = {
        "run_id": RUN_ID,
        "matrix_identity": matrix_identity,
        "provider": {
            "provider_id": "deepseek",
            "endpoint_type": "official_api",
            "base_url": "https://api.deepseek.com",
            "model_id": "deepseek-v4-pro",
            "temperature": 0.0,
            "max_tokens": 512,
            "timeout_seconds": 120.0,
            "concurrency": 1,
            "automatic_retries": 0,
            "cross_provider_fallback": False,
            "provider_managed_tools": False,
        },
        "plan": {
            "path": _display_path(DEFAULT_PLAN),
            "sha256": _sha256_file(DEFAULT_PLAN),
            "execution_identity": execution_identity,
            "work_items": len(rows),
            "primary_records": sum(
                row["analysis_tier"] == "primary" for row in rows
            ),
            "authorization_regime_probes": sum(
                row["analysis_tier"] == "authorization_regime_probe"
                for row in rows
            ),
            "provider_calls_upper_bound": sum(
                int(row["max_provider_calls"]) for row in rows
            ),
            "work_key_sequence_sha256": sha256_canonical_json(
                [row["work_key"] for row in rows]
            ),
        },
        "pilot_review": {
            "path": _display_path(DEFAULT_PILOT_REVIEW),
            "file_sha256": _sha256_file(DEFAULT_PILOT_REVIEW),
            "review_sha256": review["review_sha256"],
            "status": review["status"],
            "checks_passed": len(review["checks"]),
            "ready_for_owner_matrix_review": True,
        },
        "budget": {
            "policy_path": _display_path(DEFAULT_BUDGET_POLICY),
            "policy_sha256": _sha256_file(DEFAULT_BUDGET_POLICY),
            "hard_spend_limit_cny": 30.0,
            "abort_ceiling_cny": 27.0,
            "prior_official_pilot_usage": copy.deepcopy(PRIOR_PILOT_USAGE),
            "prior_official_pilot_cost_cny": prior_cost,
            "check_before_every_provider_call": True,
            "usage_ledger_fsync_after_every_completed_call": True,
        },
        "safety": {
            "policy_path": _display_path(DEFAULT_SAFETY_POLICY),
            "policy_sha256": _sha256_file(DEFAULT_SAFETY_POLICY),
            "allowed_payload_classes": [
                "synthetic_m3_case",
                "public_benchmark_case",
            ],
            "effect_backends": [
                "m3_sandbox_fixture",
                "agentdojo_in_memory_copy",
            ],
            "external_effects": False,
            "host_or_provider_tools": False,
            "external_connectors": False,
            "model_output_is_untrusted_proposal": True,
        },
        "outputs": {
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
            "single_trace_per_work_item": True,
            "automatic_resume_of_open_attempts": False,
        },
        "locked_inputs": _locked_inputs(),
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": CANDIDATE_RECORDED_AT,
        "status": CANDIDATE_STATUS,
        "artifact_role": "owner_review_candidate",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "authorization": {
            "candidate_only": True,
            "matrix_execution_authorized": False,
            "result_admission_authorized": False,
            "candidate_manifest_sha256": None,
            "owner_approval": None,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "formal_results_created": 0,
            "candidate_is_executable": False,
        },
        "next_gate": (
            "Bind the project owner's delegated continuation statement in a "
            "separate active manifest. Matrix completion remains result-"
            "ineligible until an independent analysis/admission review."
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
    schema_path: Path = DEFAULT_SCHEMA,
    expected_role: str | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FormalMatrixControllerError("matrix manifest must be an object")
    schema = _load_json(schema_path)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["manifest_sha256"] != _manifest_sha256(value):
        raise FormalMatrixControllerError("matrix manifest digest drift")
    if value["scope_sha256"] != sha256_canonical_json(value["scope"]):
        raise FormalMatrixControllerError("matrix scope digest drift")
    role = str(value["artifact_role"])
    if expected_role is not None and role != expected_role:
        raise FormalMatrixControllerError(
            f"matrix manifest role must be {expected_role}"
        )
    authorization = value["authorization"]
    if role == "owner_review_candidate":
        if (
            value["status"] != CANDIDATE_STATUS
            or authorization["candidate_only"] is not True
            or authorization["matrix_execution_authorized"] is not False
            or authorization["candidate_manifest_sha256"] is not None
            or authorization["owner_approval"] is not None
        ):
            raise FormalMatrixControllerError(
                "matrix candidate cannot authorize execution"
            )
    elif role == "deepseek_medium_matrix_execution_authorization":
        approval = authorization["owner_approval"]
        if (
            value["status"] != ACTIVE_STATUS
            or authorization["candidate_only"] is not False
            or authorization["matrix_execution_authorized"] is not True
            or authorization["candidate_manifest_sha256"] is None
            or not isinstance(approval, Mapping)
            or approval.get("approval_kind")
            != "delegated_safe_api_iteration"
            or approval.get("approved_by_role") != "project_owner"
            or approval.get("approval_scope")
            != "deepseek_frozen_480_item_medium_matrix"
        ):
            raise FormalMatrixControllerError(
                "active matrix manifest lacks delegated owner authorization"
            )
    else:
        raise FormalMatrixControllerError("unsupported matrix manifest role")
    if (
        authorization["result_admission_authorized"] is not False
        or value["evidence_boundary"]["credentials_read_while_building"]
        is not False
        or value["evidence_boundary"]["network_calls_while_building"] != 0
        or value["evidence_boundary"]["formal_results_created"] != 0
        or value["evidence_boundary"]["candidate_is_executable"] is not False
    ):
        raise FormalMatrixControllerError(
            "matrix manifest widens the evidence boundary"
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
    expected = build_matrix_candidate()
    if observed != expected:
        raise FormalMatrixControllerError(
            "frozen matrix candidate does not reproduce"
        )
    return observed


def _attempt_id(run_id: str, work_key: str) -> str:
    return "matrix-attempt-" + sha256_canonical_json(
        {"run_id": run_id, "work_key": work_key}
    )[:24]


def validate_attempt_events(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    execution_identity: str,
    known_work_keys: set[str],
) -> dict[str, Any]:
    previous: str | None = None
    started: dict[str, str] = {}
    terminal: dict[str, str] = {}
    for sequence, event in enumerate(events, start=1):
        if not isinstance(event, Mapping) or set(event) != ATTEMPT_EVENT_FIELDS:
            raise FormalMatrixControllerError(
                f"attempt event {sequence} fields drift"
            )
        work_key = str(event["work_key"])
        event_type = str(event["event_type"])
        if (
            event["schema_version"] != ATTEMPT_SCHEMA_VERSION
            or event["ledger_sequence"] != sequence
            or event["previous_event_sha256"] != previous
            or event["run_id"] != run_id
            or event["execution_identity"] != execution_identity
            or work_key not in known_work_keys
            or event["attempt_id"] != _attempt_id(run_id, work_key)
            or event["event_sha256"] != _event_sha256(event)
        ):
            raise FormalMatrixControllerError(
                f"attempt event {sequence} identity/hash drift"
            )
        if event_type == "started":
            if work_key in started or work_key in terminal:
                raise FormalMatrixControllerError(
                    "matrix work item cannot start twice"
                )
            if event["record_entry_sha256"] is not None:
                raise FormalMatrixControllerError(
                    "started attempt cannot bind a record"
                )
            started[work_key] = str(event["attempt_id"])
        elif event_type in {"completed", "diagnostic"}:
            if (
                work_key not in started
                or work_key in terminal
                or not isinstance(event["record_entry_sha256"], str)
            ):
                raise FormalMatrixControllerError(
                    "terminal attempt lacks one started event"
                )
            terminal[work_key] = event_type
        else:
            raise FormalMatrixControllerError(
                "unsupported matrix attempt event"
            )
        previous = str(event["event_sha256"])
    return {
        "event_count": len(events),
        "started_work_keys": sorted(started),
        "terminal_by_work_key": terminal,
        "open_work_keys": sorted(set(started) - set(terminal)),
        "tail_sha256": previous,
    }


def _append_attempt_event(
    path: Path,
    *,
    run_id: str,
    execution_identity: str,
    known_work_keys: set[str],
    work_key: str,
    event_type: str,
    record_entry_sha256: str | None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    events = _load_jsonl(path)
    status = validate_attempt_events(
        events,
        run_id=run_id,
        execution_identity=execution_identity,
        known_work_keys=known_work_keys,
    )
    core = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "ledger_sequence": len(events) + 1,
        "previous_event_sha256": status["tail_sha256"],
        "run_id": run_id,
        "execution_identity": execution_identity,
        "work_key": work_key,
        "attempt_id": _attempt_id(run_id, work_key),
        "event_type": event_type,
        "recorded_at": recorded_at or _now(),
        "record_entry_sha256": record_entry_sha256,
    }
    event = {**core, "event_sha256": sha256_canonical_json(core)}
    validate_attempt_events(
        [*events, event],
        run_id=run_id,
        execution_identity=execution_identity,
        known_work_keys=known_work_keys,
    )
    _append_fsynced(path, event)
    return event


def _normalized_usage(value: Mapping[str, Any]) -> dict[str, int]:
    return validate_deepseek_usage(dict(value))


def _cost(policy: Mapping[str, Any], usage: Mapping[str, int]) -> float:
    return float(
        deepseek_cost_cny(
            dict(policy),
            cache_hit_input_tokens=usage["prompt_cache_hit_tokens"],
            cache_miss_input_tokens=usage["prompt_cache_miss_tokens"],
            output_tokens=usage["completion_tokens"],
        )
    )


def _add_usage(
    left: Mapping[str, int],
    right: Mapping[str, int],
) -> dict[str, int]:
    return {
        key: int(left[key]) + int(right[key])
        for key in PRIOR_PILOT_USAGE
    }


def validate_budget_events(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    execution_identity: str,
    known_work_keys: set[str],
    policy: Mapping[str, Any],
    prior_usage: Mapping[str, int],
) -> dict[str, Any]:
    previous: str | None = None
    cumulative = _normalized_usage(prior_usage)
    response_ids: set[str] = set()
    paused = False
    for sequence, event in enumerate(events, start=1):
        if not isinstance(event, Mapping) or set(event) != BUDGET_EVENT_FIELDS:
            raise FormalMatrixControllerError(
                f"budget event {sequence} fields drift"
            )
        work_key = str(event["work_key"])
        usage = _normalized_usage(event["usage"])
        response_id = str(event["provider_response_id"])
        if (
            event["schema_version"] != BUDGET_SCHEMA_VERSION
            or event["ledger_sequence"] != sequence
            or event["previous_event_sha256"] != previous
            or event["run_id"] != run_id
            or event["execution_identity"] != execution_identity
            or work_key not in known_work_keys
            or isinstance(event["call_index"], bool)
            or not isinstance(event["call_index"], int)
            or event["call_index"] < 1
            or not response_id
            or response_id in response_ids
            or event["event_sha256"] != _event_sha256(event)
        ):
            raise FormalMatrixControllerError(
                f"budget event {sequence} identity/hash drift"
            )
        cumulative = _add_usage(cumulative, usage)
        expected_cost = _cost(policy, cumulative)
        expected_request_cost = _cost(policy, usage)
        status = "continue"
        try:
            check_deepseek_headroom(dict(policy), cumulative)
        except BudgetPolicyError:
            status = "pause_before_next_request"
            paused = True
        if (
            event["request_cost_cny"] != expected_request_cost
            or dict(event["project_cumulative_usage"]) != cumulative
            or event["project_cumulative_cost_cny"] != expected_cost
            or event["budget_status_after_request"] != status
        ):
            raise FormalMatrixControllerError(
                f"budget event {sequence} arithmetic drift"
            )
        response_ids.add(response_id)
        previous = str(event["event_sha256"])
    return {
        "event_count": len(events),
        "project_cumulative_usage": cumulative,
        "project_cumulative_cost_cny": _cost(policy, cumulative),
        "paused": paused,
        "provider_response_ids": sorted(response_ids),
        "tail_sha256": previous,
    }


class MatrixBudgetTracker:
    """所有矩阵工作项共享的 fsync 项目级预算状态。"""

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        execution_identity: str,
        known_work_keys: set[str],
        policy: Mapping[str, Any],
        prior_usage: Mapping[str, int],
    ) -> None:
        self.path = path
        self.run_id = run_id
        self.execution_identity = execution_identity
        self.known_work_keys = set(known_work_keys)
        self.policy = copy.deepcopy(dict(policy))
        self.prior_usage = _normalized_usage(prior_usage)
        self.events = _load_jsonl(path)
        self.status = validate_budget_events(
            self.events,
            run_id=run_id,
            execution_identity=execution_identity,
            known_work_keys=self.known_work_keys,
            policy=self.policy,
            prior_usage=self.prior_usage,
        )

    def assert_before_request(self) -> None:
        if self.status["paused"]:
            raise ProviderPausedError(
                "matrix budget ledger is paused before the next request"
            )
        try:
            check_deepseek_headroom(
                self.policy,
                dict(self.status["project_cumulative_usage"]),
            )
        except BudgetPolicyError as exc:
            raise ProviderPausedError(str(exc)) from exc

    def record_completion(
        self,
        *,
        work_key: str,
        call_index: int,
        completion: OfficialProviderCompletion,
        recorded_at: str | None = None,
    ) -> dict[str, Any]:
        evidence = completion.receipt.get("evidence")
        if not isinstance(evidence, Mapping):
            raise FormalMatrixControllerError(
                "provider completion lacks safe evidence"
            )
        usage_raw = evidence.get("usage")
        if not isinstance(usage_raw, Mapping):
            raise FormalMatrixControllerError(
                "provider completion lacks DeepSeek usage"
            )
        usage = _normalized_usage(usage_raw)
        response_id = evidence.get("response_id")
        if not isinstance(response_id, str) or not response_id:
            raise FormalMatrixControllerError(
                "provider completion lacks official response identity"
            )
        cumulative = _add_usage(
            self.status["project_cumulative_usage"],
            usage,
        )
        status = "continue"
        try:
            check_deepseek_headroom(self.policy, cumulative)
        except BudgetPolicyError:
            status = "pause_before_next_request"
        core = {
            "schema_version": BUDGET_SCHEMA_VERSION,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "call_index": call_index,
            "provider_response_id": response_id,
            "usage": usage,
            "request_cost_cny": _cost(self.policy, usage),
            "project_cumulative_usage": cumulative,
            "project_cumulative_cost_cny": _cost(self.policy, cumulative),
            "budget_status_after_request": status,
            "recorded_at": recorded_at or _now(),
        }
        event = {**core, "event_sha256": sha256_canonical_json(core)}
        new_events = [*self.events, event]
        new_status = validate_budget_events(
            new_events,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            known_work_keys=self.known_work_keys,
            policy=self.policy,
            prior_usage=self.prior_usage,
        )
        _append_fsynced(self.path, event)
        self.events = new_events
        self.status = new_status
        return copy.deepcopy(event)


class MatrixBudgetClient:
    """围绕单个工作项客户端添加项目级预算账本。"""

    def __init__(
        self,
        client: OfficialProviderClient,
        *,
        tracker: MatrixBudgetTracker,
        work_key: str,
    ) -> None:
        self._client = client
        self._tracker = tracker
        self._work_key = work_key

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
        self._tracker.assert_before_request()
        completion = self._client.complete(
            messages,
            case=case,
            step=step,
            observations=observations,
        )
        self._tracker.record_completion(
            work_key=self._work_key,
            call_index=step,
            completion=completion,
        )
        return completion


def _trace_rows(path: Path) -> list[dict[str, Any]]:
    rows = _load_jsonl(path)
    validate_trace_rows(rows)
    return rows


def _cross_bind_budget_and_records(
    *,
    budget_events: Sequence[Mapping[str, Any]],
    record_entries: Sequence[Mapping[str, Any]],
    trace_root: Path,
) -> None:
    budget_by_response = {
        str(event["provider_response_id"]): event for event in budget_events
    }
    observed: dict[str, Mapping[str, Any]] = {}
    for entry in record_entries:
        record = entry["record"]
        bundle = record["provider_trace_bundle"]
        trace_path = trace_root / f"{entry['work_key']}.jsonl"
        if not trace_path.is_file():
            raise FormalMatrixControllerError(
                "completed matrix record lacks its independent trace"
            )
        if _trace_rows(trace_path) != bundle["trace_rows"]:
            raise FormalMatrixControllerError(
                "matrix trace file differs from its record bundle"
            )
        for item in bundle["usage_evidence"]:
            response_id = str(item["provider_response_id"])
            if response_id in observed:
                raise FormalMatrixControllerError(
                    "provider response identity is reused across records"
                )
            observed[response_id] = item
    if set(observed) != set(budget_by_response):
        raise FormalMatrixControllerError(
            "matrix budget ledger does not exactly bind completed record calls"
        )
    for response_id, item in observed.items():
        event = budget_by_response[response_id]
        if (
            dict(event["usage"])
            != {
                key: item[key]
                for key in PRIOR_PILOT_USAGE
            }
            or event["work_key"]
            != next(
                entry["work_key"]
                for entry in record_entries
                if any(
                    usage["provider_response_id"] == response_id
                    for usage in entry["record"][
                        "provider_trace_bundle"
                    ]["usage_evidence"]
                )
            )
        ):
            raise FormalMatrixControllerError(
                "matrix budget usage drifted from provider evidence"
            )


def _state_from_paths(
    *,
    permit: MatrixExecutionPermit,
    reconcile: bool = False,
) -> dict[str, Any]:
    del reconcile
    keys = {str(item["work_key"]) for item in permit.work_items}
    records = load_record_entries(permit.record_ledger_path)
    record_status = validate_record_entries(
        records,
        work_items=permit.work_items,
        execution_identity=permit.execution_identity,
        run_id=permit.run_id,
    )
    attempts = _load_jsonl(permit.attempt_ledger_path)
    attempt_status = validate_attempt_events(
        attempts,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
    )
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    budget = _load_jsonl(permit.budget_ledger_path)
    budget_status = validate_budget_events(
        budget,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
        policy=policy,
        prior_usage=permit.scope["budget"][
            "prior_official_pilot_usage"
        ],
    )
    terminal_keys = set(record_status["terminal_work_keys"])
    attempt_terminal = set(attempt_status["terminal_by_work_key"])
    if terminal_keys != attempt_terminal:
        raise FormalMatrixControllerError(
            "matrix attempt and record ledgers are not terminally aligned"
        )
    if attempt_status["open_work_keys"]:
        raise FormalMatrixControllerError(
            "open matrix attempt requires explicit recovery; automatic retry is forbidden"
        )
    _cross_bind_budget_and_records(
        budget_events=budget,
        record_entries=records,
        trace_root=permit.trace_root,
    )
    for item in permit.work_items:
        key = str(item["work_key"])
        trace_path = permit.trace_root / f"{key}.jsonl"
        if key not in terminal_keys and trace_path.exists():
            raise FormalMatrixControllerError(
                "pending matrix item has an existing trace; automatic resume is forbidden"
            )
    return {
        "record_entries": records,
        "record_status": record_status,
        "attempt_events": attempts,
        "attempt_status": attempt_status,
        "budget_events": budget,
        "budget_status": budget_status,
        "pending_work_items": [
            copy.deepcopy(dict(item))
            for item in permit.work_items
            if str(item["work_key"]) not in terminal_keys
        ],
    }


def authorize_matrix(
    admission_path: Path = DEFAULT_ACTIVE_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> MatrixExecutionPermit:
    """验证所有非机密门禁并返回可恢复的矩阵许可。"""

    candidate = verify_matrix_candidate(candidate_path)
    if not admission_path.is_file():
        raise FormalMatrixControllerError(
            "active DeepSeek matrix admission is missing"
        )
    active = validate_matrix_manifest(
        _load_json(admission_path),
        expected_role="deepseek_medium_matrix_execution_authorization",
    )
    if (
        active["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or active["scope_sha256"] != candidate["scope_sha256"]
        or active["scope"] != candidate["scope"]
    ):
        raise FormalMatrixControllerError(
            "active matrix admission does not bind the frozen candidate"
        )
    _assert_locked_inputs(active["scope"])
    _validate_pilot_review()
    rows = _plan_rows()
    if (
        _sha256_file(DEFAULT_PLAN) != active["scope"]["plan"]["sha256"]
        or rows[0]["execution_identity"]
        != active["scope"]["plan"]["execution_identity"]
    ):
        raise FormalMatrixControllerError("matrix plan identity drift")
    outputs = active["scope"]["outputs"]
    output_root = _resolve_project_path(str(outputs["root"]))
    allowed_root = (
        PROJECT_ROOT / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    ).resolve()
    try:
        output_root.relative_to(allowed_root)
    except ValueError as exc:
        raise FormalMatrixControllerError(
            "matrix output root escapes its dedicated directory"
        ) from exc
    permit = MatrixExecutionPermit(
        admission_file_sha256=_sha256_file(admission_path),
        run_id=str(active["scope"]["run_id"]),
        execution_identity=str(
            active["scope"]["plan"]["execution_identity"]
        ),
        work_items=tuple(copy.deepcopy(rows)),
        output_root=output_root,
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
        max_tokens=int(active["scope"]["provider"]["max_tokens"]),
        timeout_seconds=float(
            active["scope"]["provider"]["timeout_seconds"]
        ),
        scope=copy.deepcopy(active["scope"]),
    )
    _state_from_paths(permit=permit)
    return permit


def _load_local_credentials(
    config_path: Path | None = None,
) -> Mapping[str, str]:
    return parse_env_file(resolve_config_path(config_path))


def _validate_runtime_config(
    values: Mapping[str, str],
    policy: Mapping[str, Any],
) -> None:
    fields = PROVIDER_CONFIG["deepseek"]
    if values.get("M3_FRONTIER_API_CONSENT") != CONSENT_VALUE:
        raise FormalMatrixControllerError(
            "explicit local network consent is missing"
        )
    if is_placeholder(values.get(fields["api_key"])):
        raise FormalMatrixControllerError(
            "DeepSeek API key is missing or a placeholder"
        )
    if values.get(fields["model_id"]) != policy["deepseek"]["model_id"]:
        raise FormalMatrixControllerError(
            "DeepSeek model differs from the frozen policy"
        )
    if str(values.get(fields["base_url"], "")).rstrip("/") != str(
        policy["deepseek"]["base_url"]
    ).rstrip("/"):
        raise FormalMatrixControllerError(
            "DeepSeek base URL differs from the frozen policy"
        )


RuntimeFactory = Callable[
    [MatrixExecutionPermit, Mapping[str, str], MatrixBudgetTracker],
    Any,
]


def _real_dispatcher_factory(
    permit: MatrixExecutionPermit,
    values: Mapping[str, str],
    tracker: MatrixBudgetTracker,
) -> Any:
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    _validate_runtime_config(values, policy)
    fields = PROVIDER_CONFIG["deepseek"]
    api_key = str(values[fields["api_key"]])
    agentdojo = FrozenAgentDojoCaseResolver()
    evaluator = PaperV2OfflineOutcomeEvaluator(
        m3_resolver=FrozenM3CaseResolver(),
        agentdojo_resolver=agentdojo,
    )
    detector = PinnedPromptGuardDetector(device="cuda")
    vigil_factory = VigilOfficialConstraintFactory()

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> MatrixBudgetClient:
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        client = OfficialProviderClient(
            provider_id="deepseek",
            api_key=api_key,
            content_class=content_class,
            budget_state=ProviderBudgetState(
                provider_id="deepseek",
                policy=policy,
            ),
            policy=policy,
            temperature=0.0,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
            network_consent=True,
        )
        return MatrixBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
        )

    def backend_factory(
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> Any:
        if context.benchmark == "m3-v2":
            return M3SandboxEffectBackend(context)
        return agentdojo.build_backend(context, tool_schemas)

    runtime = LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=backend_factory,
        detector=detector,
        vigil_factory=vigil_factory,
        provider_trace_path_factory=(
            lambda context: permit.trace_root
            / f"{context.work_key}.jsonl"
        ),
    )
    return build_condition_dispatcher(runtime=runtime, evaluator=evaluator)


def _execute_matrix_permit(
    permit: MatrixExecutionPermit,
    *,
    values: Mapping[str, str],
    dispatcher_factory: RuntimeFactory = _real_dispatcher_factory,
) -> dict[str, Any]:
    """按固化顺序执行待处理项，在首次暂停时停止。"""

    initial_state = _state_from_paths(permit=permit)
    keys = {str(item["work_key"]) for item in permit.work_items}
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    tracker = MatrixBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
        policy=policy,
        prior_usage=permit.scope["budget"][
            "prior_official_pilot_usage"
        ],
    )
    dispatcher = dispatcher_factory(permit, values, tracker)
    completed_this_process = 0
    for item in initial_state["pending_work_items"]:
        try:
            tracker.assert_before_request()
        except ProviderPausedError:
            break
        work_key = str(item["work_key"])
        _append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type="started",
            record_entry_sha256=None,
        )
        online_state = reconstruct_initial_online_state(item)
        execution_result = dict(dispatcher.execute(item, online_state))
        if execution_result.get("result_tier") not in {
            "formal_candidate",
            "diagnostic",
        }:
            raise FormalMatrixControllerError(
                "matrix result exceeded the non-admitted evidence tier"
            )
        execution_result["admission_manifest_sha256"] = (
            permit.admission_file_sha256
        )
        entry = append_execution_result(
            permit.record_ledger_path,
            work_items=permit.work_items,
            work_item=item,
            initial_online_state=online_state,
            execution_result=execution_result,
            execution_identity=permit.execution_identity,
            run_id=permit.run_id,
        )
        tier = str(entry["record"]["result_tier"])
        _append_attempt_event(
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
        current = _state_from_paths(permit=permit)
        if tier == "diagnostic" or current["budget_status"]["paused"]:
            break
    final = _state_from_paths(permit=permit)
    remaining = len(final["pending_work_items"])
    diagnostic = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in final["record_entries"]
    )
    status = (
        "matrix_execution_complete_candidate_records_unadmitted"
        if remaining == 0
        else (
            "matrix_paused_after_diagnostic"
            if diagnostic
            else "matrix_paused_by_budget"
        )
    )
    return {
        "status": status,
        "run_id": permit.run_id,
        "work_items": len(permit.work_items),
        "record_count": len(final["record_entries"]),
        "formal_candidate_records": (
            len(final["record_entries"]) - diagnostic
        ),
        "diagnostic_records": diagnostic,
        "remaining_work_items": remaining,
        "completed_this_process": completed_this_process,
        "provider_calls_completed": final["budget_status"]["event_count"],
        "project_cumulative_usage": final["budget_status"][
            "project_cumulative_usage"
        ],
        "project_cumulative_cost_cny": final["budget_status"][
            "project_cumulative_cost_cny"
        ],
        "within_abort_ceiling": (
            final["budget_status"]["project_cumulative_cost_cny"]
            <= permit.scope["budget"]["abort_ceiling_cny"]
        ),
        "formal_matrix_execution_authorized": True,
        "result_admission_authorized": False,
        "network_provider": "deepseek",
        "automatic_retries": 0,
        "cross_provider_fallback": False,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }


def execute_admitted_matrix(
    admission_path: Path = DEFAULT_ACTIVE_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: RuntimeFactory = _real_dispatcher_factory,
) -> dict[str, Any]:
    permit = authorize_matrix(
        admission_path,
        candidate_path=candidate_path,
    )
    loader = credential_loader or (
        lambda: _load_local_credentials(config_path)
    )
    values = loader()
    return _execute_matrix_permit(
        permit,
        values=values,
        dispatcher_factory=dispatcher_factory,
    )


def matrix_status(
    admission_path: Path = DEFAULT_ACTIVE_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    permit = authorize_matrix(
        admission_path,
        candidate_path=candidate_path,
    )
    state = _state_from_paths(permit=permit)
    diagnostic = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in state["record_entries"]
    )
    return {
        "status": "matrix_status_verified_no_network",
        "run_id": permit.run_id,
        "record_count": len(state["record_entries"]),
        "formal_candidate_records": len(state["record_entries"]) - diagnostic,
        "diagnostic_records": diagnostic,
        "remaining_work_items": len(state["pending_work_items"]),
        "provider_calls_completed": state["budget_status"]["event_count"],
        "project_cumulative_usage": state["budget_status"][
            "project_cumulative_usage"
        ],
        "project_cumulative_cost_cny": state["budget_status"][
            "project_cumulative_cost_cny"
        ],
        "network_calls_made_by_status": 0,
        "result_admission_authorized": False,
    }


def _fixture_dispatcher_factory(
    permit: MatrixExecutionPermit,
    values: Mapping[str, str],
    tracker: MatrixBudgetTracker,
) -> Any:
    del values
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    response_counter = 0

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> MatrixBudgetClient:
        nonlocal response_counter

        def transport(
            endpoint: str,
            headers: Mapping[str, str],
            payload: Mapping[str, Any],
            timeout: float,
        ) -> HTTPResponseEnvelope:
            nonlocal response_counter
            del endpoint, headers, timeout
            response_counter += 1
            return HTTPResponseEnvelope(
                status_code=200,
                headers={},
                body={
                    "id": f"matrix-qualification-response-{response_counter}",
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
                        "prompt_cache_hit_tokens": 90,
                        "prompt_cache_miss_tokens": 10,
                        "completion_tokens": 12,
                        "total_tokens": 112,
                    },
                },
            )

        client = OfficialProviderClient(
            provider_id="deepseek",
            api_key="offline-matrix-qualification-key",
            content_class="synthetic_m3_case",
            budget_state=ProviderBudgetState(
                provider_id="deepseek",
                policy=policy,
            ),
            policy=policy,
            temperature=0.0,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
            transport=transport,
        )
        return MatrixBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
        )

    runtime = LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=(
            lambda context, _schemas: M3SandboxEffectBackend(context)
        ),
        provider_trace_path_factory=(
            lambda context: permit.trace_root
            / f"{context.work_key}.jsonl"
        ),
        provider_trace_receipt_adapter=_as_official_receipt,
        recorded_at=lambda: QUALIFICATION_RECORDED_AT,
    )
    evaluator = M3OfflineOutcomeEvaluator(FrozenM3CaseResolver())
    return build_condition_dispatcher(runtime=runtime, evaluator=evaluator)


def _as_official_receipt(
    receipt: Mapping[str, Any],
) -> Mapping[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value["evidence"]["transport_kind"] = "official_network"
    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def build_controller_qualification() -> dict[str, Any]:
    """离线演练两个连续工作项和安全闭合恢复路径。"""

    rows = [
        row
        for row in _plan_rows()
        if row["benchmark"] == "m3-v2"
        and row["condition_id"] == "no_defense"
    ][:2]
    if len(rows) != 2:
        raise FormalMatrixControllerError(
            "qualification lacks two no-defense M3 items"
        )
    rejected: list[str] = []
    with TemporaryDirectory(prefix="m3-matrix-controller-v1-") as directory:
        root = Path(directory)
        scope = {
            "budget": {
                "prior_official_pilot_usage": copy.deepcopy(
                    PRIOR_PILOT_USAGE
                ),
                "abort_ceiling_cny": 27.0,
            }
        }
        permit = MatrixExecutionPermit(
            admission_file_sha256="a" * 64,
            run_id="offline-matrix-controller-qualification",
            execution_identity=str(rows[0]["execution_identity"]),
            work_items=tuple(copy.deepcopy(rows)),
            output_root=root,
            record_ledger_path=root / "records.jsonl",
            attempt_ledger_path=root / "attempts.jsonl",
            budget_ledger_path=root / "budget.jsonl",
            trace_root=root / "traces",
            max_tokens=64,
            timeout_seconds=30.0,
            scope=scope,
        )
        result = _execute_matrix_permit(
            permit,
            values={},
            dispatcher_factory=_fixture_dispatcher_factory,
        )
        if (
            result["record_count"] != 2
            or result["provider_calls_completed"] != 2
            or result["remaining_work_items"] != 0
            or result["diagnostic_records"] != 0
        ):
            raise FormalMatrixControllerError(
                "offline matrix qualification did not complete two items"
            )
        state = _state_from_paths(permit=permit)
        if (
            len(state["attempt_events"]) != 4
            or len(state["budget_events"]) != 2
        ):
            raise FormalMatrixControllerError(
                "offline matrix ledgers are incomplete"
            )

        trace_reuse_root = root / "trace-reuse"
        trace_reuse_permit = MatrixExecutionPermit(
            **{
                **permit.__dict__,
                "output_root": trace_reuse_root,
                "record_ledger_path": trace_reuse_root / "records.jsonl",
                "attempt_ledger_path": trace_reuse_root / "attempts.jsonl",
                "budget_ledger_path": trace_reuse_root / "budget.jsonl",
                "trace_root": trace_reuse_root / "traces",
                "work_items": (copy.deepcopy(rows[0]),),
            }
        )
        trace_reuse_permit.trace_root.mkdir(parents=True, exist_ok=True)
        (trace_reuse_permit.trace_root / f"{rows[0]['work_key']}.jsonl").write_text(
            "{}\n",
            encoding="utf-8",
        )
        try:
            _state_from_paths(permit=trace_reuse_permit)
        except FormalMatrixControllerError:
            rejected.append("pending_trace_reuse")
        else:
            raise FormalMatrixControllerError(
                "pending trace reuse was accepted"
            )

        open_root = root / "open-attempt"
        open_permit = MatrixExecutionPermit(
            **{
                **permit.__dict__,
                "output_root": open_root,
                "record_ledger_path": open_root / "records.jsonl",
                "attempt_ledger_path": open_root / "attempts.jsonl",
                "budget_ledger_path": open_root / "budget.jsonl",
                "trace_root": open_root / "traces",
                "work_items": (copy.deepcopy(rows[0]),),
            }
        )
        _append_attempt_event(
            open_permit.attempt_ledger_path,
            run_id=open_permit.run_id,
            execution_identity=open_permit.execution_identity,
            known_work_keys={str(rows[0]["work_key"])},
            work_key=str(rows[0]["work_key"]),
            event_type="started",
            record_entry_sha256=None,
            recorded_at=QUALIFICATION_RECORDED_AT,
        )
        try:
            _state_from_paths(permit=open_permit)
        except FormalMatrixControllerError:
            rejected.append("open_attempt_auto_resume")
        else:
            raise FormalMatrixControllerError(
                "open attempt automatic resume was accepted"
            )

        tampered = copy.deepcopy(state["budget_events"])
        tampered[0]["project_cumulative_cost_cny"] = 99.0
        try:
            validate_budget_events(
                tampered,
                run_id=permit.run_id,
                execution_identity=permit.execution_identity,
                known_work_keys={str(item["work_key"]) for item in rows},
                policy=_load_json(DEFAULT_BUDGET_POLICY),
                prior_usage=PRIOR_PILOT_USAGE,
            )
        except FormalMatrixControllerError:
            rejected.append("budget_cost_tamper")
        else:
            raise FormalMatrixControllerError(
                "matrix budget cost tamper was accepted"
            )
    expected = {
        "pending_trace_reuse",
        "open_attempt_auto_resume",
        "budget_cost_tamper",
    }
    if set(rejected) != expected:
        raise FormalMatrixControllerError(
            "matrix qualification negative coverage drift"
        )
    return {
        "schema_version": "m3-paper-v2-formal-matrix-controller-qualification-1.0",
        "generated_at": QUALIFICATION_RECORDED_AT,
        "status": "matrix_controller_qualified_offline",
        "work_items_executed": 2,
        "provider_calls_completed": 2,
        "record_entries_written": 2,
        "attempt_events_written": 4,
        "budget_events_written": 2,
        "negative_cases_rejected": sorted(rejected),
        "credentials_read": 0,
        "network_calls_made": 0,
        "project_matrix_records_created": 0,
        "formal_results_created": 0,
        "automatic_retries": 0,
        "cross_provider_fallback": False,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
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
    expected = build_controller_qualification()
    if observed != expected:
        raise FormalMatrixControllerError(
            "matrix controller qualification drift"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--status", action="store_true")
    action.add_argument("--execute-admitted-matrix", action="store_true")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--active-admission",
        type=Path,
        default=DEFAULT_ACTIVE_ADMISSION,
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_QUALIFICATION)
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    candidate_path = resolve(args.candidate)
    admission_path = resolve(args.active_admission)
    if args.write_qualification:
        value = write_controller_qualification(resolve(args.output))
    elif args.verify_qualification:
        value = verify_controller_qualification(resolve(args.output))
    elif args.write_candidate:
        value = write_matrix_candidate(candidate_path)
    elif args.verify_candidate:
        value = verify_matrix_candidate(candidate_path)
    elif args.verify_admission:
        permit = authorize_matrix(
            admission_path,
            candidate_path=candidate_path,
        )
        value = {
            "status": "matrix_admission_verified_no_execution",
            "run_id": permit.run_id,
            "work_items": len(permit.work_items),
            "credentials_read": False,
            "network_calls_made": 0,
            "result_admission_authorized": False,
        }
    elif args.status:
        value = matrix_status(
            admission_path,
            candidate_path=candidate_path,
        )
    else:
        value = execute_admitted_matrix(
            admission_path,
            candidate_path=candidate_path,
            config_path=args.config,
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
