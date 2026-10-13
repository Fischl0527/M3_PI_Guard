"""在不可变 v1 中止后启用的替代性 DeepSeek 矩阵控制器。

修复前序批次的超时与连接问题，以全新会话继续推进矩阵实验。
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as v1
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
    ProviderBudgetState,
    ProviderPausedError,
)
from experiments.paper_v2.promptguard_live_dependency import (
    PinnedPromptGuardDetector,
)
from experiments.paper_v2.vigil_live_dependency import (
    VigilOfficialConstraintFactory,
)
from m3_core.project_config import (
    parse_env_file,
    resolve_config_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = v1.DEFAULT_PLAN
DEFAULT_BUDGET_POLICY = v1.DEFAULT_BUDGET_POLICY
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_matrix_admission_v2.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v2.json"
)
DEFAULT_CLIENT_QUALIFICATION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/deepseek_nonthinking_client_qualification_v1.json"
)
DEFAULT_V1_CANDIDATE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v1.json"
)
DEFAULT_V1_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_admission_v1.json"
)
DEFAULT_V1_ABORT_REVIEW = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    / "c4e6a8eddd73b8ab8fab735cd2720653a909d3dd3040c6acdebee6ec996cbd4d"
    / "aborted_run_review_v1.json"
)
DEFAULT_CANDIDATE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v2.json"
)
DEFAULT_CANARY_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "deepseek_medium_matrix_canary_admission_v2.json"
)
DEFAULT_CONTINUATION_ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions"
    / "deepseek_medium_matrix_continuation_admission_v2.json"
)
DEFAULT_CANARY_REVIEW_NAME = "six_condition_canary_review_v2.json"

RUN_ID = "paper-v2-deepseek-medium-v2-20260724"
SCHEMA_VERSION = "m3-paper-v2-formal-matrix-admission-2.0"
CANDIDATE_RECORDED_AT = "2026-07-24T16:35:00+08:00"
QUALIFICATION_RECORDED_AT = "2026-07-24T16:34:00+08:00"
CANDIDATE_STATUS = "candidate_pending_six_condition_canary"
CANARY_ACTIVE_STATUS = "activated_for_six_condition_canary"
CONTINUATION_ACTIVE_STATUS = "activated_for_matrix_continuation"
FAILURE_STATUSES = frozenset(
    {
        "timeout",
        "parse_failure",
        "max_steps",
        "provider_failure",
        "runner_failure",
    }
)
PRIOR_PROJECT_USAGE = {
    "prompt_tokens": 2585,
    "prompt_cache_hit_tokens": 256,
    "prompt_cache_miss_tokens": 2329,
    "completion_tokens": 2184,
}
PRIOR_ABORTED_MATRIX_USAGE = {
    "prompt_tokens": 2307,
    "prompt_cache_hit_tokens": 256,
    "prompt_cache_miss_tokens": 2051,
    "completion_tokens": 2048,
}


class FormalMatrixControllerV2Error(RuntimeError):
    """当替换运行无法保持前瞻性时抛出的异常。"""


@dataclass(frozen=True)
class V2Authorization:
    permit: v1.MatrixExecutionPermit
    authorization_scope: str
    active_manifest: Mapping[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalMatrixControllerV2Error(f"{path}: expected an object")
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
        raise FormalMatrixControllerV2Error(
            "matrix-v2 artifact path escapes the project root"
        ) from exc
    return path


def _manifest_sha256(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _append_locked(
    items: list[dict[str, Any]],
    path: Path,
) -> None:
    if not path.is_file():
        raise FormalMatrixControllerV2Error(
            f"missing matrix-v2 input: {_display_path(path)}"
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
    base_candidate = v1.verify_matrix_candidate(DEFAULT_V1_CANDIDATE)
    items = copy.deepcopy(base_candidate["scope"]["locked_inputs"])
    for path in (
        DEFAULT_V1_CANDIDATE,
        DEFAULT_V1_ADMISSION,
        DEFAULT_V1_ABORT_REVIEW,
        PROJECT_ROOT
        / "experiments/paper_v2/deepseek_nonthinking_client_v1.py",
        DEFAULT_CLIENT_QUALIFICATION,
        PROJECT_ROOT
        / "experiments/paper_v2/formal_matrix_controller_v2.py",
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
            raise FormalMatrixControllerV2Error(
                f"matrix-v2 locked input drift: {item['path']}"
            )


def _v1_abort_review() -> dict[str, Any]:
    review = _load_json(DEFAULT_V1_ABORT_REVIEW)
    decision = review.get("decision")
    if (
        review.get("status")
        != "aborted_engineering_run_immutable_and_result_ineligible"
        or not isinstance(decision, Mapping)
        or decision.get("result_admission_authorized") is not False
        or decision.get("run_may_be_resumed") is not False
        or decision.get("replacement_requires_non_thinking_payload_commitment")
        is not True
        or decision.get("replacement_requires_failure_persistence_qualification")
        is not True
        or decision.get("replacement_requires_six_condition_canary")
        is not True
    ):
        raise FormalMatrixControllerV2Error(
            "v1 abort review does not authorize a replacement design"
        )
    return review


def build_matrix_candidate() -> dict[str, Any]:
    """构建确定性、不可执行的替换候选对象。"""

    base_candidate = v1.verify_matrix_candidate(DEFAULT_V1_CANDIDATE)
    rows = v1._plan_rows()
    abort_review = _v1_abort_review()
    client_qualification = _load_json(DEFAULT_CLIENT_QUALIFICATION)
    if (
        client_qualification.get("status")
        != "deepseek_nonthinking_client_qualified_offline"
        or client_qualification.get("thinking_mode_persisted") != "disabled"
        or client_qualification.get("network_calls_made") != 0
    ):
        raise FormalMatrixControllerV2Error(
            "non-thinking client qualification is incomplete"
        )
    execution_identity = str(rows[0]["execution_identity"])
    matrix_identity = sha256_canonical_json(
        {
            "run_id": RUN_ID,
            "execution_identity": execution_identity,
            "plan_sha256": _sha256_file(DEFAULT_PLAN),
            "aborted_run_review_sha256": _sha256_file(
                DEFAULT_V1_ABORT_REVIEW
            ),
            "client_qualification_sha256": _sha256_file(
                DEFAULT_CLIENT_QUALIFICATION
            ),
            "provider_id": "deepseek",
            "model_id": "deepseek-v4-pro",
            "thinking_mode": "disabled",
        }
    )
    output_root = (
        Path("outputs/paper_upgrade_v2/formal_medium/deepseek")
        / matrix_identity
    )
    scope = copy.deepcopy(base_candidate["scope"])
    scope["run_id"] = RUN_ID
    scope["matrix_identity"] = matrix_identity
    scope["provider"]["thinking_mode"] = "disabled"
    scope["budget"] = {
        **scope["budget"],
        "prior_official_pilot_usage": copy.deepcopy(v1.PRIOR_PILOT_USAGE),
        "prior_aborted_matrix_usage": copy.deepcopy(
            PRIOR_ABORTED_MATRIX_USAGE
        ),
        "prior_project_usage": copy.deepcopy(PRIOR_PROJECT_USAGE),
        "prior_project_cost_cny": v1._cost(
            _load_json(DEFAULT_BUDGET_POLICY),
            PRIOR_PROJECT_USAGE,
        ),
    }
    scope["replaces_aborted_run"] = {
        "run_id": abort_review["run_id"],
        "matrix_identity": abort_review["matrix_identity"],
        "review_path": _display_path(DEFAULT_V1_ABORT_REVIEW),
        "review_sha256": _sha256_file(DEFAULT_V1_ABORT_REVIEW),
        "old_run_resumable": False,
        "old_records_result_eligible": False,
    }
    scope["canary"] = {
        "work_items": 6,
        "conditions": [
            str(row["condition_id"]) for row in rows[:6]
        ],
        "work_key_sequence_sha256": sha256_canonical_json(
            [row["work_key"] for row in rows[:6]]
        ),
        "required_before_continuation": True,
        "automatic_continuation": False,
        "review_filename": DEFAULT_CANARY_REVIEW_NAME,
    }
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
            "v1_run_resumed": False,
        },
        "next_gate": (
            "Create a separate six-condition canary admission. Matrix "
            "continuation requires a passing canary review and another "
            "authorization artifact; results remain unadmitted."
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
        raise FormalMatrixControllerV2Error(
            "matrix-v2 manifest must be an object"
        )
    schema = _load_json(schema_path)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["manifest_sha256"] != _manifest_sha256(value):
        raise FormalMatrixControllerV2Error(
            "matrix-v2 manifest digest drift"
        )
    if value["scope_sha256"] != sha256_canonical_json(value["scope"]):
        raise FormalMatrixControllerV2Error("matrix-v2 scope digest drift")
    role = str(value["artifact_role"])
    if expected_role is not None and role != expected_role:
        raise FormalMatrixControllerV2Error(
            f"matrix-v2 manifest role must be {expected_role}"
        )
    authorization = value["authorization"]
    if authorization["result_admission_authorized"] is not False:
        raise FormalMatrixControllerV2Error(
            "matrix-v2 cannot admit scientific results"
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
            raise FormalMatrixControllerV2Error(
                "matrix-v2 candidate cannot authorize execution"
            )
    elif role == "six_condition_canary_execution_authorization":
        if (
            value["status"] != CANARY_ACTIVE_STATUS
            or authorization["candidate_only"] is not False
            or authorization["canary_execution_authorized"] is not True
            or authorization["matrix_continuation_authorized"] is not False
            or authorization["canary_review_sha256"] is not None
        ):
            raise FormalMatrixControllerV2Error(
                "matrix-v2 canary authorization drift"
            )
    elif role == "medium_matrix_continuation_authorization":
        if (
            value["status"] != CONTINUATION_ACTIVE_STATUS
            or authorization["candidate_only"] is not False
            or authorization["canary_execution_authorized"] is not False
            or authorization["matrix_continuation_authorized"] is not True
            or not isinstance(
                authorization["canary_review_sha256"], str
            )
        ):
            raise FormalMatrixControllerV2Error(
                "matrix-v2 continuation authorization drift"
            )
    else:
        raise FormalMatrixControllerV2Error(
            "unsupported matrix-v2 manifest role"
        )
    if role != "owner_review_candidate":
        approval = authorization["owner_approval"]
        if (
            not isinstance(approval, Mapping)
            or approval.get("approval_kind")
            != "delegated_safe_api_iteration"
            or approval.get("approved_by_role") != "project_owner"
            or approval.get("statement_sha256")
            != "2194cd7fd6734d220f7b38cd64fd717df8717270f0034dcaebece42185269ef2"
        ):
            raise FormalMatrixControllerV2Error(
                "matrix-v2 active manifest lacks delegated owner approval"
            )
    scope = value["scope"]
    if role == "owner_review_candidate":
        if (
            scope["run_id"] != RUN_ID
            or scope["provider"]["provider_id"] != "deepseek"
            or scope["provider"]["model_id"] != "deepseek-v4-pro"
            or scope["provider"]["thinking_mode"] != "disabled"
            or scope["provider"]["automatic_retries"] != 0
            or scope["provider"]["concurrency"] != 1
            or scope["plan"]["work_items"] != 480
            or scope["canary"]["work_items"] != 6
            or scope["replaces_aborted_run"]["old_run_resumable"]
            is not False
            or scope["replaces_aborted_run"][
                "old_records_result_eligible"
            ]
            is not False
            or scope["budget"]["prior_project_usage"]
            != PRIOR_PROJECT_USAGE
        ):
            raise FormalMatrixControllerV2Error(
                "matrix-v2 prospective scope drift"
            )
    elif (
        scope["run_id"] != RUN_ID
        or not isinstance(scope["candidate_scope_sha256"], str)
    ):
        raise FormalMatrixControllerV2Error(
            "matrix-v2 active scope reference drift"
        )
    boundary = value["evidence_boundary"]
    if (
        boundary["credentials_read_while_building"] is not False
        or boundary["network_calls_while_building"] != 0
        or boundary["formal_results_created"] != 0
        or boundary["candidate_is_executable"] is not False
        or boundary["v1_run_resumed"] is not False
    ):
        raise FormalMatrixControllerV2Error(
            "matrix-v2 evidence boundary widened"
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
        raise FormalMatrixControllerV2Error(
            "frozen matrix-v2 candidate does not reproduce"
        )
    return observed


class FailureAwareOutcomeEvaluator:
    """在 ITT 分母中保留显式运行时失败。"""

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate

    def evaluate(
        self,
        work_item: Mapping[str, Any],
        raw_trace: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        status = str(raw_trace.get("operational_status", "runner_failure"))
        if status in FAILURE_STATUSES:
            return {
                "unsafe_effect": None,
                "task_completion": False,
                "metric_semantics": (
                    "operational_failure_retained_in_itt_v1"
                ),
            }
        return self.delegate.evaluate(work_item, raw_trace)


class FailureTierNormalizingRuntime:
    """将完整追踪包与响应后运行时失败对齐。"""

    def __init__(self, delegate: LiveConditionRuntime) -> None:
        self.delegate = delegate

    def execute(self, context: Any, profile: Any) -> Mapping[str, Any]:
        value = copy.deepcopy(dict(self.delegate.execute(context, profile)))
        bundle = value.get("provider_trace_bundle")
        if (
            value.get("operational_status") in FAILURE_STATUSES
            and isinstance(bundle, Mapping)
            and bundle.get("result_tier_ceiling") == "formal_candidate"
        ):
            value["result_tier"] = "formal_candidate"
        return value


class RedactedVigilConstraintFactory:
    """丢弃源 VIGIL 的原始响应控制台回退诊断。"""

    provider_calls_consumed = 1

    def __init__(self) -> None:
        self.delegate = VigilOfficialConstraintFactory()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return self.delegate(*args, **kwargs)


RuntimeFactory = Callable[
    [v1.MatrixExecutionPermit, Mapping[str, str], v1.MatrixBudgetTracker],
    Any,
]


def _real_dispatcher_factory(
    permit: v1.MatrixExecutionPermit,
    values: Mapping[str, str],
    tracker: v1.MatrixBudgetTracker,
) -> Any:
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    v1._validate_runtime_config(values, policy)
    fields = v1.PROVIDER_CONFIG["deepseek"]
    api_key = str(values[fields["api_key"]])
    agentdojo = FrozenAgentDojoCaseResolver()
    evaluator = FailureAwareOutcomeEvaluator(
        PaperV2OfflineOutcomeEvaluator(
            m3_resolver=FrozenM3CaseResolver(),
            agentdojo_resolver=agentdojo,
        )
    )
    detector = PinnedPromptGuardDetector(device="cuda")
    vigil_factory = RedactedVigilConstraintFactory()

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> DeepSeekNonThinkingTracedProviderClient:
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        client = DeepSeekNonThinkingOfficialClient(
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
        budget_client = v1.MatrixBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
        )
        return DeepSeekNonThinkingTracedProviderClient(
            budget_client,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=permit.trace_root / f"{context.work_key}.jsonl",
            recorded_at=_now,
        )

    def backend_factory(
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> Any:
        if context.benchmark == "m3-v2":
            return M3SandboxEffectBackend(context)
        return agentdojo.build_backend(context, tool_schemas)

    runtime = FailureTierNormalizingRuntime(
        LiveConditionRuntime(
            provider_client_factory=provider_factory,
            effect_backend_factory=backend_factory,
            detector=detector,
            vigil_factory=vigil_factory,
        )
    )
    return build_condition_dispatcher(
        runtime=runtime,
        evaluator=evaluator,
    )


def _state_from_paths(
    permit: v1.MatrixExecutionPermit,
) -> dict[str, Any]:
    keys = {str(item["work_key"]) for item in permit.work_items}
    records = load_record_entries(permit.record_ledger_path)
    record_status = validate_record_entries(
        records,
        work_items=permit.work_items,
        execution_identity=permit.execution_identity,
        run_id=permit.run_id,
    )
    attempts = v1._load_jsonl(permit.attempt_ledger_path)
    attempt_status = v1.validate_attempt_events(
        attempts,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
    )
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    budget = v1._load_jsonl(permit.budget_ledger_path)
    budget_status = v1.validate_budget_events(
        budget,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
        policy=policy,
        prior_usage=permit.scope["budget"]["prior_project_usage"],
    )
    terminal_keys = set(record_status["terminal_work_keys"])
    attempt_terminal = set(attempt_status["terminal_by_work_key"])
    if terminal_keys != attempt_terminal:
        raise FormalMatrixControllerV2Error(
            "matrix-v2 attempt and record ledgers are not aligned"
        )
    if attempt_status["open_work_keys"]:
        raise FormalMatrixControllerV2Error(
            "open matrix-v2 attempt requires a new version; automatic retry is forbidden"
        )
    v1._cross_bind_budget_and_records(
        budget_events=budget,
        record_entries=records,
        trace_root=permit.trace_root,
    )
    for item in permit.work_items:
        key = str(item["work_key"])
        if (
            key not in terminal_keys
            and (permit.trace_root / f"{key}.jsonl").exists()
        ):
            raise FormalMatrixControllerV2Error(
                "pending matrix-v2 item already has a trace"
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


def _canary_review_path(scope: Mapping[str, Any]) -> Path:
    return _resolve_project_path(
        str(scope["outputs"]["root"])
    ) / DEFAULT_CANARY_REVIEW_NAME


def authorize_matrix(
    admission_path: Path,
    *,
    required_scope: str,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> V2Authorization:
    candidate = verify_matrix_candidate(candidate_path)
    if not admission_path.is_file():
        raise FormalMatrixControllerV2Error(
            "active matrix-v2 admission is missing"
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
        raise FormalMatrixControllerV2Error(
            "active matrix-v2 admission does not bind the candidate"
        )
    candidate_scope = candidate["scope"]
    _assert_locked_inputs(candidate_scope)
    if required_scope == "continuation":
        review_path = _canary_review_path(candidate_scope)
        review = _load_json(review_path)
        if (
            review.get("status")
            != "six_condition_canary_technical_gate_pass"
            or review.get("matrix_continuation_eligible") is not True
            or _sha256_file(review_path)
            != active["authorization"]["canary_review_sha256"]
        ):
            raise FormalMatrixControllerV2Error(
                "matrix-v2 continuation lacks a passing bound canary review"
            )
    rows = v1._plan_rows()
    outputs = candidate_scope["outputs"]
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
        max_tokens=int(candidate_scope["provider"]["max_tokens"]),
        timeout_seconds=float(
            candidate_scope["provider"]["timeout_seconds"]
        ),
        scope=copy.deepcopy(candidate_scope),
    )
    _state_from_paths(permit)
    return V2Authorization(
        permit=permit,
        authorization_scope=required_scope,
        active_manifest=active,
    )


def _execute(
    authorization: V2Authorization,
    *,
    values: Mapping[str, str],
    dispatcher_factory: RuntimeFactory,
    max_new_items: int | None,
) -> dict[str, Any]:
    permit = authorization.permit
    initial = _state_from_paths(permit)
    keys = {str(item["work_key"]) for item in permit.work_items}
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    tracker = v1.MatrixBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
        policy=policy,
        prior_usage=permit.scope["budget"]["prior_project_usage"],
    )
    dispatcher = dispatcher_factory(permit, values, tracker)
    completed_this_process = 0
    for item in initial["pending_work_items"]:
        if (
            max_new_items is not None
            and completed_this_process >= max_new_items
        ):
            break
        try:
            tracker.assert_before_request()
        except ProviderPausedError:
            break
        work_key = str(item["work_key"])
        v1._append_attempt_event(
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
            raise FormalMatrixControllerV2Error(
                "matrix-v2 result exceeded the evidence tier"
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
        v1._append_attempt_event(
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
        current = _state_from_paths(permit)
        if tier == "diagnostic" or current["budget_status"]["paused"]:
            break
    final = _state_from_paths(permit)
    diagnostic = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in final["record_entries"]
    )
    failures = sum(
        entry["record"]["operational_status"] in FAILURE_STATUSES
        for entry in final["record_entries"]
    )
    remaining = len(final["pending_work_items"])
    return {
        "status": (
            "six_condition_canary_segment_complete"
            if authorization.authorization_scope == "canary"
            and completed_this_process == 6
            and len(final["record_entries"]) == 6
            else (
                "matrix_execution_complete_candidate_records_unadmitted"
                if remaining == 0
                else "matrix_v2_paused"
            )
        ),
        "run_id": permit.run_id,
        "authorization_scope": authorization.authorization_scope,
        "record_count": len(final["record_entries"]),
        "diagnostic_records": diagnostic,
        "operational_failures": failures,
        "remaining_work_items": remaining,
        "completed_this_process": completed_this_process,
        "provider_calls_completed": final["budget_status"]["event_count"],
        "project_cumulative_usage": final["budget_status"][
            "project_cumulative_usage"
        ],
        "project_cumulative_cost_cny": final["budget_status"][
            "project_cumulative_cost_cny"
        ],
        "thinking_mode": "disabled",
        "automatic_retries": 0,
        "cross_provider_fallback": False,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def execute_canary(
    admission_path: Path = DEFAULT_CANARY_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: RuntimeFactory = _real_dispatcher_factory,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        admission_path,
        required_scope="canary",
        candidate_path=candidate_path,
    )
    state = _state_from_paths(authorization.permit)
    if state["record_entries"]:
        raise FormalMatrixControllerV2Error(
            "six-condition canary is single-use and already started"
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


def execute_continuation(
    admission_path: Path = DEFAULT_CONTINUATION_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: RuntimeFactory = _real_dispatcher_factory,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        admission_path,
        required_scope="continuation",
        candidate_path=candidate_path,
    )
    state = _state_from_paths(authorization.permit)
    if len(state["record_entries"]) != 6:
        raise FormalMatrixControllerV2Error(
            "matrix-v2 continuation requires exactly six canary records"
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
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    authorization = authorize_matrix(
        admission_path,
        required_scope=required_scope,
        candidate_path=candidate_path,
    )
    state = _state_from_paths(authorization.permit)
    return {
        "status": "matrix_v2_status_verified_no_network",
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


def _fixture_dispatcher_factory(
    permit: v1.MatrixExecutionPermit,
    values: Mapping[str, str],
    tracker: v1.MatrixBudgetTracker,
) -> Any:
    del values
    policy = _load_json(DEFAULT_BUDGET_POLICY)
    response_counter = 0

    def provider_factory(
        context: OnlineExecutorContext,
    ) -> DeepSeekNonThinkingTracedProviderClient:
        nonlocal response_counter

        def transport(
            endpoint: str,
            headers: Mapping[str, str],
            payload: Mapping[str, Any],
            timeout: float,
        ) -> HTTPResponseEnvelope:
            nonlocal response_counter
            del endpoint, headers, timeout
            if payload.get("thinking") != {"type": "disabled"}:
                raise FormalMatrixControllerV2Error(
                    "fixture observed missing non-thinking commitment"
                )
            response_counter += 1
            return HTTPResponseEnvelope(
                status_code=200,
                headers={},
                body={
                    "id": f"matrix-v2-qualification-{response_counter}",
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

        client = DeepSeekNonThinkingOfficialClient(
            provider_id="deepseek",
            api_key="offline-matrix-v2-qualification-key",
            content_class="synthetic_m3_case",
            budget_state=ProviderBudgetState(
                provider_id="deepseek",
                policy=policy,
            ),
            policy=policy,
            max_tokens=permit.max_tokens,
            timeout=permit.timeout_seconds,
            transport=transport,
        )
        budget_client = v1.MatrixBudgetClient(
            client,
            tracker=tracker,
            work_key=context.work_key,
        )
        return DeepSeekNonThinkingTracedProviderClient(
            budget_client,
            execution_identity=context.execution_identity,
            work_key=context.work_key,
            trace_path=permit.trace_root / f"{context.work_key}.jsonl",
            recorded_at=lambda: QUALIFICATION_RECORDED_AT,
            receipt_adapter=v1._as_official_receipt,
        )

    runtime = FailureTierNormalizingRuntime(
        LiveConditionRuntime(
            provider_client_factory=provider_factory,
            effect_backend_factory=(
                lambda context, _schemas: M3SandboxEffectBackend(context)
            ),
            recorded_at=lambda: QUALIFICATION_RECORDED_AT,
        )
    )
    evaluator = FailureAwareOutcomeEvaluator(
        M3OfflineOutcomeEvaluator(FrozenM3CaseResolver())
    )
    return build_condition_dispatcher(runtime=runtime, evaluator=evaluator)


def build_controller_qualification() -> dict[str, Any]:
    """在无网络环境下演练顺序执行与失败保留。"""

    rows = [
        row
        for row in v1._plan_rows()
        if row["benchmark"] == "m3-v2"
        and row["condition_id"] == "no_defense"
    ][:2]
    if len(rows) != 2:
        raise FormalMatrixControllerV2Error(
            "matrix-v2 qualification lacks two fixture rows"
        )
    with TemporaryDirectory(prefix="m3-matrix-controller-v2-") as directory:
        root = Path(directory)
        scope = {
            "budget": {
                "prior_project_usage": copy.deepcopy(PRIOR_PROJECT_USAGE),
            }
        }
        permit = v1.MatrixExecutionPermit(
            admission_file_sha256="b" * 64,
            run_id="offline-matrix-controller-v2-qualification",
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
        authorization = V2Authorization(
            permit=permit,
            authorization_scope="qualification",
            active_manifest={},
        )
        result = _execute(
            authorization,
            values={},
            dispatcher_factory=_fixture_dispatcher_factory,
            max_new_items=None,
        )
        if (
            result["record_count"] != 2
            or result["provider_calls_completed"] != 2
            or result["diagnostic_records"] != 0
        ):
            raise FormalMatrixControllerV2Error(
                "matrix-v2 offline sequence did not complete"
            )

        class RejectingDelegate:
            def evaluate(self, *_args: Any, **_kwargs: Any) -> Any:
                raise AssertionError(
                    "failure-aware evaluator invoked its delegate"
                )

        failure_outcome = FailureAwareOutcomeEvaluator(
            RejectingDelegate()
        ).evaluate(
            rows[0],
            {"operational_status": "provider_failure"},
        )
        if failure_outcome != {
            "unsafe_effect": None,
            "task_completion": False,
            "metric_semantics": "operational_failure_retained_in_itt_v1",
        }:
            raise FormalMatrixControllerV2Error(
                "failure-aware ITT outcome drift"
            )
    return {
        "schema_version": (
            "m3-paper-v2-formal-matrix-controller-qualification-2.0"
        ),
        "generated_at": QUALIFICATION_RECORDED_AT,
        "status": "matrix_controller_v2_qualified_offline",
        "work_items_executed": 2,
        "provider_calls_completed": 2,
        "nonthinking_payloads_observed": 2,
        "operational_failure_delegate_calls": 0,
        "operational_failure_retained_for_itt": True,
        "credentials_read": 0,
        "network_calls_made": 0,
        "formal_results_created": 0,
        "automatic_retries": 0,
        "cross_provider_fallback": False,
        "v1_run_resumed": False,
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
        raise FormalMatrixControllerV2Error(
            "matrix-v2 controller qualification drift"
        )
    return observed


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
        raise FormalMatrixControllerV2Error(
            "canary review requires exactly six terminal records"
        )
    statuses = [
        str(entry["record"]["operational_status"])
        for entry in records
    ]
    tiers = [str(entry["record"]["result_tier"]) for entry in records]
    conditions = [str(entry["record"]["condition_id"]) for entry in records]
    expected_conditions = [
        str(item["condition_id"])
        for item in authorization.permit.work_items[:6]
    ]
    passed = (
        statuses == ["completed"] * 6
        and tiers == ["formal_candidate"] * 6
        and conditions == expected_conditions
        and state["attempt_status"]["open_work_keys"] == []
        and state["budget_status"]["paused"] is False
    )
    if not passed:
        raise FormalMatrixControllerV2Error(
            "six-condition canary technical gate did not pass"
        )
    return {
        "schema_version": "m3-paper-v2-six-condition-canary-review-2.0",
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
    _write_json(
        _canary_review_path(
            verify_matrix_candidate(candidate_path)["scope"]
        ),
        value,
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--verify-canary-admission", action="store_true")
    action.add_argument("--execute-canary", action="store_true")
    action.add_argument("--write-canary-review", action="store_true")
    action.add_argument("--verify-continuation-admission", action="store_true")
    action.add_argument("--execute-continuation", action="store_true")
    action.add_argument("--canary-status", action="store_true")
    action.add_argument("--continuation-status", action="store_true")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--canary-admission",
        type=Path,
        default=DEFAULT_CANARY_ADMISSION,
    )
    parser.add_argument(
        "--continuation-admission",
        type=Path,
        default=DEFAULT_CONTINUATION_ADMISSION,
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_QUALIFICATION)
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    candidate = resolve(args.candidate)
    canary_admission = resolve(args.canary_admission)
    continuation_admission = resolve(args.continuation_admission)
    if args.write_qualification:
        value = write_controller_qualification(resolve(args.output))
    elif args.verify_qualification:
        value = verify_controller_qualification(resolve(args.output))
    elif args.write_candidate:
        value = write_matrix_candidate(candidate)
    elif args.verify_candidate:
        value = verify_matrix_candidate(candidate)
    elif args.verify_canary_admission:
        authorization = authorize_matrix(
            canary_admission,
            required_scope="canary",
            candidate_path=candidate,
        )
        value = {
            "status": "matrix_v2_canary_admission_verified_no_execution",
            "run_id": authorization.permit.run_id,
            "work_items": 6,
            "credentials_read": False,
            "network_calls_made": 0,
            "result_admission_authorized": False,
        }
    elif args.execute_canary:
        value = execute_canary(
            canary_admission,
            candidate_path=candidate,
            config_path=args.config,
        )
    elif args.write_canary_review:
        value = write_canary_review(
            canary_admission,
            candidate_path=candidate,
        )
    elif args.verify_continuation_admission:
        authorization = authorize_matrix(
            continuation_admission,
            required_scope="continuation",
            candidate_path=candidate,
        )
        value = {
            "status": (
                "matrix_v2_continuation_admission_verified_no_execution"
            ),
            "run_id": authorization.permit.run_id,
            "remaining_work_items": len(
                _state_from_paths(
                    authorization.permit
                )["pending_work_items"]
            ),
            "credentials_read": False,
            "network_calls_made": 0,
            "result_admission_authorized": False,
        }
    elif args.execute_continuation:
        value = execute_continuation(
            continuation_admission,
            candidate_path=candidate,
            config_path=args.config,
        )
    elif args.canary_status:
        value = matrix_status(
            canary_admission,
            required_scope="canary",
            candidate_path=candidate,
        )
    else:
        value = matrix_status(
            continuation_admission,
            required_scope="continuation",
            candidate_path=candidate,
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
