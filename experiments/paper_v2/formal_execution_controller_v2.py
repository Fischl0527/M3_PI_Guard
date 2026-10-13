"""面向单次前瞻性 DeepSeek paper-v2 先导实验的故障安全（Fail-Closed）控制器。

在遇到未捕获异常或策略冲突时默认拦截所有外部动作，保障沙箱安全。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    build_condition_dispatcher,
)
from experiments.paper_v2.formal_record_store_v2 import (
    append_execution_result,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    M3SandboxEffectBackend,
)
from experiments.paper_v2.m3_offline_evaluator import (
    FrozenM3CaseResolver,
    M3OfflineOutcomeEvaluator,
)
from experiments.paper_v2.medium_runtime import (
    reconstruct_initial_online_state,
)
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
)
from experiments.paper_v2.provider_live_qualification import (
    CONSENT_VALUE,
    PROVIDER_CONFIG,
)
from m3_core.project_config import (
    is_placeholder,
    parse_env_file,
    resolve_config_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/pilot_admission_manifest_v2.schema.json"
)
DEFAULT_PLAN = PROTOCOL_ROOT / "medium_execution_plan_v2.jsonl"
DEFAULT_PLAN_MANIFEST = PROTOCOL_ROOT / "medium_execution_manifest_v2.json"
DEFAULT_PREFLIGHT = PROTOCOL_ROOT / "medium_execution_manifest_v3_preflight.json"
DEFAULT_BUDGET_POLICY = PROTOCOL_ROOT / "dual_provider_budget_policy_v1.json"
DEFAULT_SAFETY_POLICY = PROTOCOL_ROOT / "provider_safety_policy_v1.json"
DEFAULT_TRACE_ACTIVATION = (
    PROTOCOL_ROOT / "provider_request_trace_activation_v2.json"
)
DEFAULT_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_pilot_admission_candidate_v2.json"
)
DEFAULT_ACTIVE_ADMISSION = (
    PROTOCOL_ROOT / "admissions/deepseek_pilot_admission_v2.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_execution_controller_qualification_v2.json"
)

SCHEMA_VERSION = "m3-paper-v2-pilot-admission-manifest-2.0"
CANDIDATE_STATUS = "candidate_pending_owner_activation"
ACTIVE_STATUS = "activated_for_single_deepseek_pilot"
PILOT_RUN_ID = "paper-v2-deepseek-pilot-20260724"
PILOT_SELECTOR = {
    "benchmark": "m3-v2",
    "condition_id": "no_defense",
    "evaluation_case_type": "benign_no_tool",
    "authorization_regime": "auto_compiled",
    "analysis_tier": "primary",
}
LOCKED_INPUTS = (
    DEFAULT_PLAN,
    DEFAULT_PLAN_MANIFEST,
    DEFAULT_PREFLIGHT,
    DEFAULT_BUDGET_POLICY,
    DEFAULT_SAFETY_POLICY,
    DEFAULT_TRACE_ACTIVATION,
    Path(__file__).resolve(),
    DEFAULT_SCHEMA,
    PROJECT_ROOT / "experiments/paper_v2/official_provider_executor.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_budget.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_safety.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_request_trace_candidate.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_request_trace_activation.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_trace_bundle.py",
    PROJECT_ROOT / "experiments/paper_v2/live_condition_runtime.py",
    PROJECT_ROOT / "experiments/paper_v2/formal_condition_executors.py",
    PROJECT_ROOT / "experiments/paper_v2/formal_record_store_v2.py",
    PROJECT_ROOT / "experiments/paper_v2/contracts_v2.py",
    PROJECT_ROOT / "experiments/paper_v2/post_pilot_evidence_review.py",
    PROJECT_ROOT / "schemas/paper_v2/experiment_record_v2.schema.json",
    PROJECT_ROOT / "schemas/paper_v2/provider_trace_bundle_v2.schema.json",
    PROJECT_ROOT / "schemas/paper_v2/provider_safety_receipt_v1.schema.json",
    PROJECT_ROOT / "schemas/paper_v2/post_pilot_review_v1.schema.json",
)


class FormalExecutionControllerV2Error(ValueError):
    """在凭据或网络访问前，当试验门禁失败时抛出的异常。"""


@dataclass(frozen=True)
class PilotExecutionPermit:
    """在凭据访问前生成的经过验证的单工作项许可。"""

    admission_manifest_sha256: str
    run_id: str
    work_item: dict[str, Any]
    trace_path: Path
    record_ledger_path: Path
    max_tokens: int
    timeout_seconds: float


CredentialLoader = Callable[[], Mapping[str, str]]
PathExists = Callable[[Path], bool]
ClientFactory = Callable[
    [Mapping[str, str], Mapping[str, Any], PilotExecutionPermit],
    OfficialProviderClient,
]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalExecutionControllerV2Error(
            f"{path}: expected a JSON object"
        )
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise FormalExecutionControllerV2Error(
                f"{path}:{line_number}: expected a JSON object"
            )
        rows.append(value)
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise FormalExecutionControllerV2Error(
            f"path escapes the project root: {path}"
        ) from exc


def _resolve_project_path(value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        raise FormalExecutionControllerV2Error(
            "pilot manifest paths must be project-relative"
        )
    resolved = (PROJECT_ROOT / raw).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise FormalExecutionControllerV2Error(
            "pilot manifest path escapes the project root"
        ) from exc
    return resolved


def _manifest_core(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(child)
        for key, child in value.items()
        if key != "manifest_sha256"
    }


def _manifest_sha256(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(_manifest_core(value))


def _load_schema(path: Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    schema = _load_json(path)
    if schema.get("$id") is None:
        raise FormalExecutionControllerV2Error(
            "pilot admission schema requires an identifier"
        )
    return schema


def validate_admission_manifest(
    value: Any,
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    expected_role: str | None = None,
) -> dict[str, Any]:
    """验证 Schema、自摘要以及角色专属的授权语义。"""

    if not isinstance(value, Mapping):
        raise FormalExecutionControllerV2Error(
            "pilot admission manifest must be an object"
        )
    Draft202012Validator(
        _load_schema(schema_path),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["manifest_sha256"] != _manifest_sha256(value):
        raise FormalExecutionControllerV2Error(
            "pilot admission manifest digest drift"
        )
    if value["scope_sha256"] != sha256_canonical_json(value["scope"]):
        raise FormalExecutionControllerV2Error(
            "pilot admission scope digest drift"
        )
    role = str(value["artifact_role"])
    if expected_role is not None and role != expected_role:
        raise FormalExecutionControllerV2Error(
            f"pilot admission role must be {expected_role}"
        )
    authorization = value["authorization"]
    if role == "owner_review_candidate":
        if (
            value["status"] != CANDIDATE_STATUS
            or authorization["candidate_only"] is not True
            or authorization["execution_authorized"] is not False
            or authorization["owner_approval"] is not None
            or authorization["candidate_manifest_sha256"] is not None
        ):
            raise FormalExecutionControllerV2Error(
                "owner-review candidate cannot authorize execution"
            )
    elif role == "single_pilot_execution_authorization":
        approval = authorization["owner_approval"]
        if (
            value["status"] != ACTIVE_STATUS
            or authorization["candidate_only"] is not False
            or authorization["execution_authorized"] is not True
            or not isinstance(approval, Mapping)
            or authorization["candidate_manifest_sha256"] is None
            or approval.get("approval_kind")
            != "explicit_project_owner_checkpoint"
            or approval.get("approved_by_role") != "project_owner"
        ):
            raise FormalExecutionControllerV2Error(
                "active pilot manifest lacks explicit owner authorization"
            )
    else:
        raise FormalExecutionControllerV2Error(
            "unsupported pilot admission artifact role"
        )
    if (
        authorization["formal_matrix_authorized"] is not False
        or authorization["result_admission_authorized"] is not False
        or value["evidence_boundary"]["credentials_read_while_building"]
        is not False
        or value["evidence_boundary"]["network_calls_while_building"]
        != 0
        or value["evidence_boundary"]["formal_results_created"] != 0
    ):
        raise FormalExecutionControllerV2Error(
            "pilot manifest attempts to widen the frozen evidence boundary"
        )
    return copy.deepcopy(dict(value))


def _selected_work_item(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    matches = [
        dict(row)
        for row in rows
        if all(row.get(key) == expected for key, expected in PILOT_SELECTOR.items())
        and row.get("primary_endpoint_eligible") is True
        and row.get("status") == "pending"
    ]
    if not matches:
        raise FormalExecutionControllerV2Error(
            "frozen plan has no eligible DeepSeek pilot work item"
        )
    matches.sort(key=lambda row: int(row["sequence"]))
    selected = matches[0]
    if selected.get("result_fields_present") is not False:
        raise FormalExecutionControllerV2Error(
            "pilot work item unexpectedly contains result fields"
        )
    return selected


def _locked_inputs() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in LOCKED_INPUTS:
        if not path.is_file():
            raise FormalExecutionControllerV2Error(
                f"missing pilot input: {_display_path(path)}"
            )
        result.append(
            {
                "path": _display_path(path),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return result


def build_admission_candidate() -> dict[str, Any]:
    """构建确定性、不可执行的所有者审查构件。"""

    plan_rows = _load_jsonl(DEFAULT_PLAN)
    if len(plan_rows) != 480:
        raise FormalExecutionControllerV2Error(
            "frozen medium plan must contain 480 work items"
        )
    item = _selected_work_item(plan_rows)
    plan_manifest = _load_json(DEFAULT_PLAN_MANIFEST)
    preflight = _load_json(DEFAULT_PREFLIGHT)
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    if (
        plan_manifest.get("execution_identity") != item["execution_identity"]
        or plan_manifest.get("plan_sha256") != _sha256_file(DEFAULT_PLAN)
    ):
        raise FormalExecutionControllerV2Error(
            "pilot work item differs from the frozen plan manifest"
        )
    if (
        preflight.get("execution_authorized") is not False
        or preflight.get("formal_execution_authorized") is not False
        or preflight.get("live_runtime_per_call_v2_qualified") is not True
    ):
        raise FormalExecutionControllerV2Error(
            "pilot candidate requires the closed, v2-qualified preflight"
        )
    deepseek = policy["deepseek"]
    work_key = str(item["work_key"])
    output_root = (
        Path("outputs/paper_upgrade_v2/formal_pilot/deepseek") / work_key
    )
    scope = {
        "run_id": PILOT_RUN_ID,
        "provider": {
            "provider_id": "deepseek",
            "endpoint_type": "official_api",
            "base_url": deepseek["base_url"],
            "model_id": deepseek["model_id"],
            "temperature": 0.0,
            "max_tokens": 512,
            "timeout_seconds": 120.0,
            "max_provider_calls": int(item["max_provider_calls"]),
            "automatic_retries": 0,
            "cross_provider_fallback": False,
            "provider_managed_tools": False,
        },
        "work_item": {
            "sequence": item["sequence"],
            "work_key": work_key,
            "execution_identity": item["execution_identity"],
            "selection_id": item["selection_id"],
            "case_id": item["case_id"],
            "benchmark": item["benchmark"],
            "condition_id": item["condition_id"],
            "evaluation_case_type": item["evaluation_case_type"],
            "authorization_regime": item["authorization_regime"],
            "analysis_tier": item["analysis_tier"],
            "source_record_sha256": item["source_record_sha256"],
            "work_item_sha256": sha256_canonical_json(item),
        },
        "locked_inputs": _locked_inputs(),
        "safety": {
            "policy_sha256": _sha256_file(DEFAULT_SAFETY_POLICY),
            "external_effects": False,
            "effect_backend": "m3_sandbox_fixture",
            "model_output_is_untrusted_proposal": True,
            "host_or_provider_tools": False,
            "allowed_payload_class": "synthetic_m3_case",
        },
        "budget": {
            "policy_sha256": _sha256_file(DEFAULT_BUDGET_POLICY),
            "hard_spend_limit_cny": deepseek["hard_spend_limit_cny"],
            "abort_ceiling_cny": deepseek["abort_ceiling_cny"],
            "pilot_work_items": 1,
            "max_provider_calls": int(item["max_provider_calls"]),
        },
        "outputs": {
            "single_use": True,
            "must_not_exist_before_execution": True,
            "provider_trace_path": (
                output_root / "provider_trace_v2.jsonl"
            ).as_posix(),
            "record_ledger_path": (
                output_root / "experiment_record_v2.jsonl"
            ).as_posix(),
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-07-24T09:00:00+08:00",
        "status": CANDIDATE_STATUS,
        "artifact_role": "owner_review_candidate",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "authorization": {
            "candidate_only": True,
            "execution_authorized": False,
            "formal_matrix_authorized": False,
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
            "The project owner must explicitly approve this exact one-work-item "
            "DeepSeek pilot checkpoint. A separately frozen active manifest is "
            "then required; this candidate is never executable."
        ),
    }
    candidate = {
        **core,
        "manifest_sha256": sha256_canonical_json(core),
    }
    return validate_admission_manifest(
        candidate,
        expected_role="owner_review_candidate",
    )


def verify_admission_candidate(
    path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    observed = validate_admission_manifest(
        _load_json(path),
        expected_role="owner_review_candidate",
    )
    expected = build_admission_candidate()
    if observed != expected:
        raise FormalExecutionControllerV2Error(
            "frozen pilot admission candidate does not reproduce"
        )
    return observed


def write_admission_candidate(
    path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    candidate = build_admission_candidate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return candidate


def _assert_locked_inputs(scope: Mapping[str, Any]) -> None:
    for item in scope["locked_inputs"]:
        path = _resolve_project_path(str(item["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise FormalExecutionControllerV2Error(
                f"pilot locked input drift: {item['path']}"
            )


def _assert_output_paths_unused(
    scope: Mapping[str, Any],
    *,
    path_exists: PathExists,
) -> tuple[Path, Path]:
    outputs = scope["outputs"]
    trace_path = _resolve_project_path(str(outputs["provider_trace_path"]))
    record_path = _resolve_project_path(str(outputs["record_ledger_path"]))
    allowed_root = (
        PROJECT_ROOT / "outputs/paper_upgrade_v2/formal_pilot/deepseek"
    ).resolve()
    for path in (trace_path, record_path):
        try:
            path.relative_to(allowed_root)
        except ValueError as exc:
            raise FormalExecutionControllerV2Error(
                "pilot output path escapes its dedicated root"
            ) from exc
        if path_exists(path):
            raise FormalExecutionControllerV2Error(
                "single-use pilot output already exists"
            )
    if trace_path.parent != record_path.parent:
        raise FormalExecutionControllerV2Error(
            "pilot trace and record ledger must share a work-item directory"
        )
    return trace_path, record_path


def authorize_single_pilot(
    admission_path: Path = DEFAULT_ACTIVE_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    path_exists: PathExists = Path.exists,
) -> PilotExecutionPermit:
    """验证所有非机密门禁并返回单项许可。

    此函数特意不执行凭据访问和网络操作。在调用凭据加载器之前必须完成此操作。
    """

    candidate = verify_admission_candidate(candidate_path)
    if not admission_path.is_file():
        raise FormalExecutionControllerV2Error(
            "active one-pilot admission manifest is missing"
        )
    active = validate_admission_manifest(
        _load_json(admission_path),
        expected_role="single_pilot_execution_authorization",
    )
    if (
        active["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or active["scope_sha256"] != candidate["scope_sha256"]
        or active["scope"] != candidate["scope"]
    ):
        raise FormalExecutionControllerV2Error(
            "active pilot admission does not bind the frozen candidate"
        )
    _assert_locked_inputs(active["scope"])
    rows = _load_jsonl(DEFAULT_PLAN)
    work_key = active["scope"]["work_item"]["work_key"]
    matches = [row for row in rows if row.get("work_key") == work_key]
    if len(matches) != 1:
        raise FormalExecutionControllerV2Error(
            "active pilot work key is not unique in the frozen plan"
        )
    work_item = matches[0]
    if (
        sha256_canonical_json(work_item)
        != active["scope"]["work_item"]["work_item_sha256"]
        or work_item["execution_identity"]
        != active["scope"]["work_item"]["execution_identity"]
    ):
        raise FormalExecutionControllerV2Error(
            "active pilot work item drifted from the frozen plan"
        )
    trace_path, record_path = _assert_output_paths_unused(
        active["scope"],
        path_exists=path_exists,
    )
    provider = active["scope"]["provider"]
    return PilotExecutionPermit(
        admission_manifest_sha256=_sha256_file(admission_path),
        run_id=str(active["scope"]["run_id"]),
        work_item=copy.deepcopy(work_item),
        trace_path=trace_path,
        record_ledger_path=record_path,
        max_tokens=int(provider["max_tokens"]),
        timeout_seconds=float(provider["timeout_seconds"]),
    )


def _load_local_credentials(
    config_path: Path | None = None,
) -> Mapping[str, str]:
    return parse_env_file(resolve_config_path(config_path))


def _validate_deepseek_runtime_config(
    values: Mapping[str, str],
    policy: Mapping[str, Any],
) -> None:
    fields = PROVIDER_CONFIG["deepseek"]
    if values.get("M3_FRONTIER_API_CONSENT") != CONSENT_VALUE:
        raise FormalExecutionControllerV2Error(
            "explicit local network consent is missing"
        )
    if is_placeholder(values.get(fields["api_key"])):
        raise FormalExecutionControllerV2Error(
            "DeepSeek API key is missing or a placeholder"
        )
    if values.get(fields["model_id"]) != policy["deepseek"]["model_id"]:
        raise FormalExecutionControllerV2Error(
            "DeepSeek model differs from the frozen policy"
        )
    if str(values.get(fields["base_url"], "")).rstrip("/") != str(
        policy["deepseek"]["base_url"]
    ).rstrip("/"):
        raise FormalExecutionControllerV2Error(
            "DeepSeek base URL differs from the frozen policy"
        )


def _real_client_factory(
    values: Mapping[str, str],
    policy: Mapping[str, Any],
    permit: PilotExecutionPermit,
) -> OfficialProviderClient:
    _validate_deepseek_runtime_config(values, policy)
    fields = PROVIDER_CONFIG["deepseek"]
    return OfficialProviderClient(
        provider_id="deepseek",
        api_key=str(values[fields["api_key"]]),
        content_class="synthetic_m3_case",
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


def execute_authorized_single_pilot(
    admission_path: Path = DEFAULT_ACTIVE_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    config_path: Path | None = None,
    credential_loader: CredentialLoader | None = None,
    client_factory: ClientFactory = _real_client_factory,
    path_exists: PathExists = Path.exists,
    provider_trace_receipt_adapter: (
        Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    """在所有非机密门禁通过后，执行确切的一个已准入试验。"""

    permit = authorize_single_pilot(
        admission_path,
        candidate_path=candidate_path,
        path_exists=path_exists,
    )
    loader = credential_loader or (lambda: _load_local_credentials(config_path))
    values = loader()
    return _execute_pilot_permit(
        permit,
        values=values,
        client_factory=client_factory,
        provider_trace_receipt_adapter=provider_trace_receipt_adapter,
    )


def _execute_pilot_permit(
    permit: PilotExecutionPermit,
    *,
    values: Mapping[str, str],
    client_factory: ClientFactory,
    provider_trace_receipt_adapter: (
        Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    """运行先前授权的许可；由实时和离线固件使用。"""

    policy = _load_json(DEFAULT_BUDGET_POLICY)
    client = client_factory(values, policy, permit)
    runtime = LiveConditionRuntime(
        provider_client_factory=lambda _context: client,
        effect_backend_factory=(
            lambda context, _schemas: M3SandboxEffectBackend(context)
        ),
        provider_trace_path_factory=lambda _context: permit.trace_path,
        provider_trace_receipt_adapter=provider_trace_receipt_adapter,
    )
    evaluator = M3OfflineOutcomeEvaluator(FrozenM3CaseResolver())
    dispatcher = build_condition_dispatcher(
        runtime=runtime,
        evaluator=evaluator,
    )
    initial_state = reconstruct_initial_online_state(permit.work_item)
    execution_result = dict(
        dispatcher.execute(permit.work_item, initial_state)
    )
    if execution_result.get("result_tier") not in {
        "formal_candidate",
        "diagnostic",
    }:
        raise FormalExecutionControllerV2Error(
            "pilot result exceeded its non-admitted evidence tier"
        )
    execution_result["admission_manifest_sha256"] = (
        permit.admission_manifest_sha256
    )
    entry = append_execution_result(
        permit.record_ledger_path,
        work_items=[permit.work_item],
        work_item=permit.work_item,
        initial_online_state=initial_state,
        execution_result=execution_result,
        execution_identity=str(permit.work_item["execution_identity"]),
        run_id=permit.run_id,
    )
    return {
        "status": "single_pilot_record_persisted",
        "run_id": permit.run_id,
        "work_key": permit.work_item["work_key"],
        "result_tier": entry["record"]["result_tier"],
        "operational_status": entry["record"]["operational_status"],
        "record_id": entry["record_id"],
        "record_sha256": entry["record_sha256"],
        "provider_trace_bundle_sha256": entry["record"][
            "provider_trace_bundle"
        ]["bundle_sha256"],
        "deepseek_usage_summary": copy.deepcopy(
            entry["record"]["provider_trace_bundle"]["usage_summary"]
        ),
        "admission_manifest_sha256": permit.admission_manifest_sha256,
        "network_provider": "deepseek",
        "formal_matrix_authorized": False,
        "result_admitted": False,
    }


def _qualification_active_manifest(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    value = copy.deepcopy(dict(candidate))
    value["generated_at"] = "2026-07-24T09:05:00+08:00"
    value["status"] = ACTIVE_STATUS
    value["artifact_role"] = "single_pilot_execution_authorization"
    value["authorization"] = {
        "candidate_only": False,
        "execution_authorized": True,
        "formal_matrix_authorized": False,
        "result_admission_authorized": False,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "owner_approval": {
            "approval_kind": "explicit_project_owner_checkpoint",
            "approved_by_role": "project_owner",
            "approved_at": "2026-07-24T09:05:00+08:00",
            "approval_scope": "one_deepseek_pilot_work_item",
            "statement_sha256": hashlib.sha256(
                b"offline-controller-qualification-only"
            ).hexdigest(),
        },
    }
    value["evidence_boundary"]["candidate_is_executable"] = False
    value["next_gate"] = (
        "Offline qualification fixture only; no credential, network, or "
        "experiment execution is authorized."
    )
    value["manifest_sha256"] = _manifest_sha256(value)
    return validate_admission_manifest(
        value,
        expected_role="single_pilot_execution_authorization",
    )


def build_controller_qualification() -> dict[str, Any]:
    """以零凭据和零网络执行准入排序演练。"""

    candidate = build_admission_candidate()
    credential_reads = 0
    rejected_path_client_creations = 0
    negative_cases: list[str] = []

    def credential_spy() -> Mapping[str, str]:
        nonlocal credential_reads
        credential_reads += 1
        return {}

    def client_spy(
        _values: Mapping[str, str],
        _policy: Mapping[str, Any],
        _permit: PilotExecutionPermit,
    ) -> OfficialProviderClient:
        nonlocal rejected_path_client_creations
        rejected_path_client_creations += 1
        raise AssertionError("client factory must not run in negative probes")

    with TemporaryDirectory(prefix="m3-pilot-controller-v2-") as directory:
        root = Path(directory)
        candidate_path = root / "candidate.json"
        candidate_path.write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        missing = root / "missing-active.json"
        try:
            execute_authorized_single_pilot(
                missing,
                candidate_path=candidate_path,
                credential_loader=credential_spy,
                client_factory=client_spy,
            )
        except FormalExecutionControllerV2Error:
            negative_cases.append("missing_active_admission")

        try:
            execute_authorized_single_pilot(
                candidate_path,
                candidate_path=candidate_path,
                credential_loader=credential_spy,
                client_factory=client_spy,
            )
        except FormalExecutionControllerV2Error:
            negative_cases.append("candidate_cannot_self_authorize")

        active = _qualification_active_manifest(candidate)
        active_path = root / "active.json"
        active_path.write_text(
            json.dumps(active, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        drifted = copy.deepcopy(active)
        drifted["scope"]["work_item"]["work_key"] = "0" * 64
        drifted["scope_sha256"] = sha256_canonical_json(drifted["scope"])
        drifted["manifest_sha256"] = _manifest_sha256(drifted)
        drifted_path = root / "drifted.json"
        drifted_path.write_text(
            json.dumps(
                drifted, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            execute_authorized_single_pilot(
                drifted_path,
                candidate_path=candidate_path,
                credential_loader=credential_spy,
                client_factory=client_spy,
            )
        except FormalExecutionControllerV2Error:
            negative_cases.append("scope_identity_drift")

        output_paths = {
            _resolve_project_path(
                active["scope"]["outputs"]["provider_trace_path"]
            )
        }
        try:
            execute_authorized_single_pilot(
                active_path,
                candidate_path=candidate_path,
                credential_loader=credential_spy,
                client_factory=client_spy,
                path_exists=lambda path: path in output_paths,
            )
        except FormalExecutionControllerV2Error:
            negative_cases.append("single_use_output_exists")

        permit = authorize_single_pilot(
            active_path,
            candidate_path=candidate_path,
            path_exists=lambda _path: False,
        )
        if permit.work_item["work_key"] != candidate["scope"]["work_item"][
            "work_key"
        ]:
            raise FormalExecutionControllerV2Error(
                "qualification permit work item drift"
            )
        fixture_permit = PilotExecutionPermit(
            admission_manifest_sha256="f" * 64,
            run_id="offline-controller-e2e-qualification",
            work_item=permit.work_item,
            trace_path=root / "e2e-provider-trace.jsonl",
            record_ledger_path=root / "e2e-record-ledger.jsonl",
            max_tokens=64,
            timeout_seconds=30.0,
        )
        injected_transport_calls = 0

        def fixture_client_factory(
            _values: Mapping[str, str],
            policy: Mapping[str, Any],
            active_permit: PilotExecutionPermit,
        ) -> OfficialProviderClient:
            def transport(
                endpoint: str,
                headers: Mapping[str, str],
                payload: Mapping[str, Any],
                timeout: float,
            ) -> HTTPResponseEnvelope:
                nonlocal injected_transport_calls
                del endpoint, headers, timeout
                injected_transport_calls += 1
                return HTTPResponseEnvelope(
                    status_code=200,
                    headers={},
                    body={
                        "id": "offline-controller-response-1",
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
                            "prompt_tokens": 40,
                            "completion_tokens": 8,
                            "total_tokens": 48,
                            "prompt_cache_hit_tokens": 32,
                            "prompt_cache_miss_tokens": 8,
                        },
                    },
                )

            return OfficialProviderClient(
                provider_id="deepseek",
                api_key="offline-controller-qualification-key",
                content_class="synthetic_m3_case",
                budget_state=ProviderBudgetState(
                    provider_id="deepseek",
                    policy=policy,
                ),
                policy=policy,
                temperature=0.0,
                max_tokens=active_permit.max_tokens,
                timeout=active_permit.timeout_seconds,
                transport=transport,
            )

        def fixture_receipt_adapter(
            receipt: Mapping[str, Any],
        ) -> Mapping[str, Any]:
            value = copy.deepcopy(dict(receipt))
            value["evidence"]["transport_kind"] = "official_network"
            value["evidence_sha256"] = sha256_canonical_json(
                value["evidence"]
            )
            return value

        e2e = _execute_pilot_permit(
            fixture_permit,
            values={},
            client_factory=fixture_client_factory,
            provider_trace_receipt_adapter=fixture_receipt_adapter,
        )
        if (
            injected_transport_calls != 1
            or e2e["result_tier"] != "formal_candidate"
            or e2e["operational_status"] != "completed"
            or e2e["deepseek_usage_summary"]["completed_call_count"] != 1
            or e2e["deepseek_usage_summary"][
                "cache_accounting_complete"
            ]
            is not True
            or e2e["deepseek_usage_summary"]["within_abort_ceiling"]
            is not True
        ):
            raise FormalExecutionControllerV2Error(
                "offline controller end-to-end qualification drift"
            )

    expected_negatives = {
        "missing_active_admission",
        "candidate_cannot_self_authorize",
        "scope_identity_drift",
        "single_use_output_exists",
    }
    if set(negative_cases) != expected_negatives:
        raise FormalExecutionControllerV2Error(
            "controller negative probes were incomplete"
        )
    if credential_reads or rejected_path_client_creations:
        raise FormalExecutionControllerV2Error(
            "rejected controller paths crossed the credential/network boundary"
        )
    return {
        "schema_version": (
            "m3-paper-v2-formal-execution-controller-qualification-2.0"
        ),
        "generated_at": "2026-07-24T09:10:00+08:00",
        "status": "single_pilot_controller_qualified_offline",
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "selected_work_key": candidate["scope"]["work_item"]["work_key"],
        "selected_case_id": candidate["scope"]["work_item"]["case_id"],
        "selected_condition_id": candidate["scope"]["work_item"][
            "condition_id"
        ],
        "positive_offline_authorization_checks": 1,
        "negative_cases_rejected": sorted(negative_cases),
        "negative_case_count": len(negative_cases),
        "credentials_read": credential_reads,
        "rejected_path_client_creations": rejected_path_client_creations,
        "injected_fixture_client_creations": 1,
        "injected_fixture_transport_calls": 1,
        "network_calls_made": 0,
        "offline_e2e_records_created_in_temporary_directory": 1,
        "completed_calls_with_cache_cost_evidence": 1,
        "cache_accounting_complete": True,
        "within_abort_ceiling": True,
        "qualification_cumulative_cost_cny": e2e[
            "deepseek_usage_summary"
        ]["cumulative_cost_cny"],
        "formal_results_created": 0,
        "candidate_can_self_authorize": False,
        "active_manifest_generated_for_project": False,
        "formal_matrix_authorized": False,
        "result_admission_authorized": False,
        "qualification_boundary": (
            "Temporary active data is a test fixture only. The project still "
            "requires an explicit owner checkpoint and a separately frozen "
            "run-specific active manifest before any credential read or API call."
        ),
    }


def write_controller_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    value = build_controller_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_controller_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_controller_qualification()
    if observed != expected:
        raise FormalExecutionControllerV2Error(
            "formal execution controller qualification does not reproduce"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--active-admission",
        type=Path,
        default=DEFAULT_ACTIVE_ADMISSION,
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--write-candidate", action="store_true")
    parser.add_argument("--verify-candidate", action="store_true")
    parser.add_argument("--verify-admission", action="store_true")
    parser.add_argument("--execute-admitted-pilot", action="store_true")
    parser.add_argument("--write-qualification", action="store_true")
    parser.add_argument("--verify-qualification", action="store_true")
    args = parser.parse_args()
    modes = (
        args.write_candidate,
        args.verify_candidate,
        args.verify_admission,
        args.execute_admitted_pilot,
        args.write_qualification,
        args.verify_qualification,
    )
    if sum(bool(item) for item in modes) != 1:
        raise FormalExecutionControllerV2Error(
            "choose exactly one candidate, admission, execution, or "
            "qualification mode"
        )
    candidate_path = (
        args.candidate
        if args.candidate.is_absolute()
        else PROJECT_ROOT / args.candidate
    )
    admission_path = (
        args.active_admission
        if args.active_admission.is_absolute()
        else PROJECT_ROOT / args.active_admission
    )
    if args.write_candidate:
        value = write_admission_candidate(candidate_path)
    elif args.verify_candidate:
        value = verify_admission_candidate(candidate_path)
    elif args.verify_admission:
        permit = authorize_single_pilot(
            admission_path,
            candidate_path=candidate_path,
        )
        value = {
            "status": "single_pilot_admission_verified_no_execution",
            "work_key": permit.work_item["work_key"],
            "credentials_read": False,
            "network_calls_made": 0,
        }
    elif args.execute_admitted_pilot:
        value = execute_authorized_single_pilot(
            admission_path,
            candidate_path=candidate_path,
            config_path=args.config,
        )
    elif args.write_qualification:
        value = write_controller_qualification()
    else:
        value = verify_controller_qualification()
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
