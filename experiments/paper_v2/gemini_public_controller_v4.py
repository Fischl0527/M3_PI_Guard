"""Quota-day segmented Gemini public canary for the official free tier.

The twelve frozen canary work items are preserved in source order, but each
formal root is small enough that the sum of frozen per-work provider-call caps
does not exceed the local 18-request daily ceiling.  Every segment receives a
new execution identity and one append-only project-day reservation.
"""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.gemini_daily_quota_ledger_v1 as daily_quota
import experiments.paper_v2.gemini_public_controller_v1 as v1
import experiments.paper_v2.gemini_public_controller_v3 as v3
import experiments.paper_v2.gemini_trace_attaching_runtime_v1 as trace_runtime
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.gemini_public_execution_store_v1 import (
    append_execution_result,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderBudgetState,
    ProviderPausedError,
)
from experiments.paper_v2.provider_budget import validate_policy
from experiments.paper_v2.public_matrix_plan_v1 import (
    hydrate_public_work_item,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
SUPERSESSION_PATH = (
    PROTOCOL_ROOT / "gemini_public_canary_v3_supersession_review.json"
)
CANDIDATE_PATH = PROTOCOL_ROOT / "gemini_public_canary_candidate_v4.json"
AGGREGATE_REVIEW_PATH = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini/"
    "public-v4-canary-aggregate-review.json"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-public-canary-candidate-4.0"
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-canary-segment-admission-4.0"
)
REVIEW_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-canary-segment-review-4.0"
)
GENERATED_AT = "2026-08-02T12:02:19+08:00"
MODEL_ID = "gemini-3.6-flash"
OWNER_APPROVAL_STATEMENT = (
    "The project owner approved the 21-day closeout plan and exact Gemini "
    "research commands under the official free tier, USD 0 paid ceiling, "
    "zero automatic retries, no provider tools, no real effects, and "
    "automatic schedule extension when free-tier quota is unavailable."
)
OWNER_STATEMENT_SHA256 = hashlib.sha256(
    OWNER_APPROVAL_STATEMENT.encode("utf-8")
).hexdigest()


class GeminiPublicControllerV4Error(RuntimeError):
    """Raised when segmented Gemini canary evidence cannot remain formal."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicControllerV4Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise GeminiPublicControllerV4Error(f"{path}: expected object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiPublicControllerV4Error(f"missing frozen input: {path}")
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise GeminiPublicControllerV4Error("artifact lock escapes project") from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise GeminiPublicControllerV4Error(f"artifact lock drift: {path}")


def build_v3_supersession_review() -> dict[str, Any]:
    candidate = v3.verify_canary_candidate()
    admission = v3.validate_canary_admission(_read_json(v3.DEFAULT_ADMISSION))
    files = []
    if v3.OUTPUT_ROOT.exists():
        files = [
            path
            for path in v3.OUTPUT_ROOT.rglob("*")
            if path.is_file() and path.stat().st_size
        ]
    if files:
        raise GeminiPublicControllerV4Error(
            "Gemini v3 has evidence and cannot be superseded as unexecuted"
        )
    core = {
        "schema_version": "m3-paper-v2-gemini-public-supersession-review-3.0",
        "status": "v3_superseded_before_execution",
        "reason": "single_root_canary_did_not_enforce_project_daily_rpd",
        "v3_run_id": v3.RUN_ID,
        "v3_candidate_manifest_sha256": candidate["manifest_sha256"],
        "v3_candidate_file_sha256": _sha256_file(v3.DEFAULT_CANDIDATE),
        "v3_admission_manifest_sha256": admission["manifest_sha256"],
        "v3_admission_file_sha256": _sha256_file(v3.DEFAULT_ADMISSION),
        "v3_nonempty_output_files": 0,
        "network_calls_made": 0,
        "provider_calls_made": 0,
        "scientific_outcomes_read": 0,
        "deletion_performed": False,
        "replacement_schema_version": SCHEMA_VERSION,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_v3_supersession_review() -> dict[str, Any]:
    value = build_v3_supersession_review()
    _write_json(SUPERSESSION_PATH, value)
    return value


def verify_v3_supersession_review() -> dict[str, Any]:
    observed = _read_json(SUPERSESSION_PATH)
    expected = build_v3_supersession_review()
    if observed != expected:
        raise GeminiPublicControllerV4Error("Gemini v3 supersession drift")
    return observed


def _pack_rows(rows: Sequence[Mapping[str, Any]]) -> list[list[dict[str, Any]]]:
    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    used = 0
    for original in rows:
        row = copy.deepcopy(dict(original))
        maximum = row.get("max_provider_calls")
        if (
            isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or maximum < 1
            or maximum > daily_quota.LOCAL_REQUEST_CAP
        ):
            raise GeminiPublicControllerV4Error(
                "canary work item has unsafe provider-call cap"
            )
        if current and used + maximum > daily_quota.LOCAL_REQUEST_CAP:
            segments.append(current)
            current = []
            used = 0
        current.append(row)
        used += maximum
    if current:
        segments.append(current)
    return segments


def _source_rows() -> list[dict[str, Any]]:
    rows = v1._canary_rows()
    segments = _pack_rows(rows)
    flattened = [row for segment in segments for row in segment]
    if flattened != rows or len(rows) != 12 or len(segments) != 8:
        raise GeminiPublicControllerV4Error("canary segmentation drift")
    return rows


def build_candidate() -> dict[str, Any]:
    source = v3.verify_canary_candidate()
    supersession = verify_v3_supersession_review()
    snapshot = daily_quota.verify_quota_snapshot()
    packed = _pack_rows(_source_rows())
    segments: list[dict[str, Any]] = []
    for index, rows in enumerate(packed):
        keys = [str(row["work_key"]) for row in rows]
        maximum = sum(int(row["max_provider_calls"]) for row in rows)
        identity = sha256_canonical_json(
            {
                "schema_version": "m3-paper-v2-gemini-public-segment-identity-4.0",
                "source_candidate_manifest_sha256": source["manifest_sha256"],
                "quota_snapshot_sha256": _sha256_file(
                    daily_quota.QUOTA_SNAPSHOT_PATH
                ),
                "segment_index": index,
                "work_keys": keys,
                "maximum_provider_requests": maximum,
            }
        )
        segments.append(
            {
                "segment_index": index,
                "run_id": f"paper-v2-public-gemini-canary-v4-s{index}",
                "execution_identity": identity,
                "work_keys": keys,
                "work_key_sequence_sha256": sha256_canonical_json(keys),
                "record_count": len(rows),
                "maximum_provider_requests": maximum,
                "output_root": (
                    "outputs/paper_upgrade_v2/formal_public/gemini/"
                    f"public-v4-canary-s{index}-{identity}"
                ),
            }
        )
    scope = {
        "provider_id": "gemini",
        "model_id": MODEL_ID,
        "model_role": "second",
        "source_v3_candidate_manifest_sha256": source["manifest_sha256"],
        "supersession_manifest_sha256": supersession["manifest_sha256"],
        "plan_manifest_sha256": source["plan_manifest_sha256"],
        "canary_records": 12,
        "segment_count": len(segments),
        "segments": segments,
        "quota": {
            "billing_tier": "free",
            "paid_ceiling_usd": 0.0,
            "provider_requests_per_day": snapshot["active_limits"][
                "requests_per_day"
            ],
            "local_requests_per_day": daily_quota.LOCAL_REQUEST_CAP,
            "reserved_requests_per_day": daily_quota.RESERVED_REQUESTS,
            "quota_timezone": daily_quota.QUOTA_TIMEZONE,
            "one_formal_segment_per_quota_day": True,
            "automatic_retries": 0,
        },
        "max_tokens": source["max_tokens"],
        "timeout_seconds": source["timeout_seconds"],
    }
    paths = [
        Path(__file__),
        v3.DEFAULT_CANDIDATE,
        v3.DEFAULT_ADMISSION,
        SUPERSESSION_PATH,
        daily_quota.QUOTA_SNAPSHOT_PATH,
        PROJECT_ROOT / "experiments/paper_v2/gemini_daily_quota_ledger_v1.py",
        PROJECT_ROOT / "experiments/paper_v2/gemini_json_client_v1.py",
        Path(trace_runtime.__file__),
        v1.GEMINI_PUBLIC_PLAN,
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "quota_day_segmented_canary_candidate",
        "generated_at": GENERATED_AT,
        "status": "candidate_pending_per_day_exact_command_admissions",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_lock(path) for path in paths],
        "authorization": {
            "candidate_only": True,
            "segment_execution_authorized": False,
            "matrix_continuation_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "v3_outputs_mutated": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicControllerV4Error("Gemini v4 candidate must be object")
    scope = value.get("scope")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("canary_records") != 12
        or scope.get("segment_count") != 8
        or scope.get("quota", {}).get("billing_tier") != "free"
        or scope.get("quota", {}).get("paid_ceiling_usd") != 0.0
        or scope.get("quota", {}).get("local_requests_per_day")
        != daily_quota.LOCAL_REQUEST_CAP
        or scope.get("quota", {}).get("automatic_retries") != 0
        or value.get("authorization", {}).get("segment_execution_authorized")
        is not False
    ):
        raise GeminiPublicControllerV4Error("Gemini v4 candidate drift")
    segments = scope.get("segments")
    if not isinstance(segments, list) or len(segments) != 8:
        raise GeminiPublicControllerV4Error("Gemini v4 segment cap drift")
    source_by_key = {
        str(row["work_key"]): row for row in _source_rows()
    }
    flattened: list[str] = []
    run_ids: set[str] = set()
    identities: set[str] = set()
    roots: set[str] = set()
    for index, segment in enumerate(segments):
        keys = segment.get("work_keys")
        if not isinstance(keys, list) or not keys:
            raise GeminiPublicControllerV4Error(
                "Gemini v4 segment work keys drift"
            )
        try:
            rows = [source_by_key[str(key)] for key in keys]
        except KeyError as exc:
            raise GeminiPublicControllerV4Error(
                "Gemini v4 segment contains an unknown work key"
            ) from exc
        maximum = sum(int(row["max_provider_calls"]) for row in rows)
        run_id = str(segment.get("run_id", ""))
        identity = str(segment.get("execution_identity", ""))
        root = str(segment.get("output_root", ""))
        if (
            segment.get("segment_index") != index
            or segment.get("record_count") != len(keys)
            or segment.get("maximum_provider_requests") != maximum
            or maximum > daily_quota.LOCAL_REQUEST_CAP
            or segment.get("work_key_sequence_sha256")
            != sha256_canonical_json(keys)
            or not run_id
            or run_id in run_ids
            or not identity
            or identity in identities
            or not root
            or root in roots
        ):
            raise GeminiPublicControllerV4Error(
                "Gemini v4 segment identity or cap drift"
            )
        flattened.extend(str(key) for key in keys)
        run_ids.add(run_id)
        identities.add(identity)
        roots.add(root)
    expected_keys = [str(row["work_key"]) for row in _source_rows()]
    if flattened != expected_keys or len(set(flattened)) != len(flattened):
        raise GeminiPublicControllerV4Error(
            "Gemini v4 segments do not form the frozen canary partition"
        )
    for lock in value.get("artifact_locks", []):
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def verify_candidate() -> dict[str, Any]:
    observed = validate_candidate(_read_json(CANDIDATE_PATH))
    expected = build_candidate()
    if observed != expected:
        raise GeminiPublicControllerV4Error("Gemini v4 candidate artifact drift")
    return observed


def admission_path(segment_index: int, quota_day: str) -> Path:
    return (
        PROTOCOL_ROOT
        / "admissions"
        / f"gemini_public_canary_v4_s{segment_index}_{quota_day}_admission.json"
    )


def canonical_segment_command(segment_index: int, quota_day: str) -> str:
    path = admission_path(segment_index, quota_day).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.gemini_public_controller_v4 "
        f"--execute-segment --segment-index {segment_index} "
        f"--quota-day {quota_day} --admission {path} "
        r"--config config\project.local.env"
    )


def build_segment_admission(
    segment_index: int,
    *,
    quota_day: str,
    approved_at: str,
    owner_statement_sha256: str,
) -> dict[str, Any]:
    candidate = verify_candidate()
    if owner_statement_sha256 != OWNER_STATEMENT_SHA256:
        raise GeminiPublicControllerV4Error("owner authorization digest drift")
    try:
        segment = candidate["scope"]["segments"][segment_index]
    except (IndexError, TypeError) as exc:
        raise GeminiPublicControllerV4Error("segment index out of range") from exc
    command = canonical_segment_command(segment_index, quota_day)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "one_exact_gemini_quota_day_segment_authorization",
        "status": "activated_for_one_exact_free_tier_quota_day",
        "approved_at": approved_at,
        "quota_day": quota_day,
        "quota_timezone": daily_quota.QUOTA_TIMEZONE,
        "segment_index": segment_index,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "owner_statement_sha256": owner_statement_sha256,
        "run_id": segment["run_id"],
        "execution_identity": segment["execution_identity"],
        "work_key_sequence_sha256": segment["work_key_sequence_sha256"],
        "maximum_provider_requests": segment["maximum_provider_requests"],
        "declared_other_project_requests": 0,
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "authorization": {
            "segment_execution_authorized": True,
            "same_day_other_formal_gemini_work_authorized": False,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "paid_ceiling_usd": 0.0,
            "result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_segment_admission(
    segment_index: int,
    *,
    quota_day: str,
    approved_at: str,
    owner_statement_sha256: str,
) -> dict[str, Any]:
    value = build_segment_admission(
        segment_index,
        quota_day=quota_day,
        approved_at=approved_at,
        owner_statement_sha256=owner_statement_sha256,
    )
    _write_json(admission_path(segment_index, quota_day), value)
    return value


def validate_segment_admission(
    value: Any, *, segment_index: int, quota_day: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicControllerV4Error("Gemini segment admission missing")
    expected = build_segment_admission(
        segment_index,
        quota_day=quota_day,
        approved_at=str(value.get("approved_at", "")),
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
    )
    if dict(value) != expected:
        raise GeminiPublicControllerV4Error("Gemini segment admission drift")
    return copy.deepcopy(dict(value))


def _segment_rows(candidate: Mapping[str, Any], index: int) -> list[dict[str, Any]]:
    source = {str(row["work_key"]): row for row in _source_rows()}
    segment = candidate["scope"]["segments"][index]
    rows = [copy.deepcopy(source[key]) for key in segment["work_keys"]]
    for row in rows:
        row["execution_identity"] = segment["execution_identity"]
    return rows


def _permit(
    *, segment_index: int, quota_day: str, selected_admission: Path
) -> v1.GeminiPublicPermit:
    expected_path = admission_path(segment_index, quota_day)
    if selected_admission.resolve() != expected_path.resolve():
        raise GeminiPublicControllerV4Error("segment admission path is not frozen")
    candidate = verify_candidate()
    admission = validate_segment_admission(
        _read_json(selected_admission),
        segment_index=segment_index,
        quota_day=quota_day,
    )
    segment = candidate["scope"]["segments"][segment_index]
    output = PROJECT_ROOT / str(segment["output_root"])
    return v1.GeminiPublicPermit(
        run_id=str(segment["run_id"]),
        execution_identity=str(segment["execution_identity"]),
        work_items=tuple(_segment_rows(candidate, segment_index)),
        output_root=output,
        record_ledger_path=output / "experiment_records_v1.jsonl",
        attempt_ledger_path=output / "attempt_events_v1.jsonl",
        call_ledger_path=output / "provider_call_events_v1.jsonl",
        trace_root=output / "provider_traces",
        admission_file_sha256=_sha256_file(selected_admission),
        max_tokens=int(candidate["scope"]["max_tokens"]),
        timeout_seconds=float(candidate["scope"]["timeout_seconds"]),
        candidate=copy.deepcopy(candidate),
        admission=copy.deepcopy(admission),
    )


def _daily_policy(maximum_provider_requests: int) -> dict[str, Any]:
    policy = copy.deepcopy(v1.fallback._effective_policy())
    policy["gemini"]["local_batch_caps"] = {
        "requests": maximum_provider_requests,
        "input_tokens": daily_quota.LOCAL_INPUT_TOKEN_CAP,
        "output_tokens": daily_quota.LOCAL_OUTPUT_TOKEN_CAP,
    }
    return validate_policy(policy)


def _build_dispatcher(
    permit: v1.GeminiPublicPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    call_sink: Any,
    budget_state: ProviderBudgetState,
    recorded_at: Callable[[], str] = _now,
) -> Any:
    """Build the prospective Gemini dispatcher with explicit bundle attachment."""

    registry = v1._Registry()
    agentdojo = v1.PublicFrozenAgentDojoCaseResolverV2(
        plan_path=v1.GEMINI_PUBLIC_PLAN
    )
    public_m3 = v1.PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity,
        plan_path=v1.GEMINI_PUBLIC_PLAN,
    )
    usage_registry = v3.GeminiUsageRegistry()
    traced_factory = functools.partial(
        v3.GeminiJsonTracedProviderClient,
        usage_registry=usage_registry,
    )

    def provider_factory(context: Any) -> Any:
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        client = v3.GeminiJsonOfficialClient(
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
            traced_factory(
                client,
                execution_identity=context.execution_identity,
                work_key=context.work_key,
                trace_path=permit.trace_root / f"{context.work_key}.jsonl",
                admission_manifest_sha256=permit.admission_file_sha256,
                recorded_at=recorded_at,
            ),
        )

    def backend_factory(context: Any, tool_schemas: Mapping[str, Any]) -> Any:
        if context.benchmark == "m3-v2":
            return v1.BoundaryAwareM3EffectBackendV3(
                v1.M3SandboxEffectBackend(context)
            )
        return agentdojo.build_backend(context, tool_schemas)

    live = v1.LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=backend_factory,
        detector=v1.PinnedPromptGuardDetector(device="cuda"),
        vigil_factory=v1.matrix_v2.RedactedVigilConstraintFactory(),
        call_event_sink=call_sink,
        recorded_at=recorded_at,
    )
    trusted = v1.TrustedContextBoundaryRuntimeV3(
        live,
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    runtime = trace_runtime.GeminiTraceAttachingRuntimeV1(
        trusted,
        client_lookup=registry.get,
    )
    evaluator = v1.PaperV2OfflineOutcomeEvaluator(
        m3_resolver=public_m3,
        agentdojo_resolver=agentdojo,
    )
    evaluator.m3 = v1.BoundaryAwareM3OutcomeEvaluatorV3(public_m3)
    return v1.build_condition_dispatcher(
        runtime=v1.matrix_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=v1.matrix_v2.FailureAwareOutcomeEvaluator(evaluator),
    )


def execute_segment(
    segment_index: int,
    *,
    quota_day: str,
    selected_admission: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] = _build_dispatcher,
) -> dict[str, Any]:
    permit = _permit(
        segment_index=segment_index,
        quota_day=quota_day,
        selected_admission=selected_admission,
    )
    initial = v1._state(permit)
    if initial["records"] or initial["attempts"] or initial["calls"]:
        raise GeminiPublicControllerV4Error(
            "Gemini segment already started; automatic retry is forbidden"
        )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    policy = _daily_policy(
        int(permit.admission["maximum_provider_requests"])
    )
    v1.fallback._validate_runtime_config(values, policy)
    api_key = str(values[v1.PROVIDER_CONFIG["gemini"]["api_key"]])
    reservation = daily_quota.reserve_formal_day(
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        workload=f"public_canary_segment_{segment_index}",
        maximum_provider_requests=int(
            permit.admission["maximum_provider_requests"]
        ),
        admission_file_sha256=permit.admission_file_sha256,
        quota_day=quota_day,
        reserved_at=_now(),
        declared_other_project_requests=0,
    )
    call_sink = v1.fallback.GeminiCallLedgerSink(
        permit.call_ledger_path,
        execution_identity=permit.execution_identity,
        model_id=MODEL_ID,
    )
    budget_state = ProviderBudgetState(
        provider_id="gemini", policy=policy
    )
    dispatcher = dispatcher_factory(
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
        v1.matrix_v1._append_attempt_event(
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
        v1.matrix_v1._append_attempt_event(
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
    final = v1._state(permit)
    return {
        "status": (
            "gemini_public_v4_segment_complete_unadmitted"
            if not final["pending"]
            else "gemini_public_v4_segment_sealed"
        ),
        "segment_index": segment_index,
        "quota_day": quota_day,
        "quota_reservation_sha256": reservation["event_sha256"],
        "record_count": len(final["records"]),
        "remaining_records": len(final["pending"]),
        "provider_calls_completed": final["call_status"]["completed_calls"],
        "completed_this_process": completed,
        "billing_tier": "free",
        "charged_usd": 0.0,
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def review_path(segment_index: int) -> Path:
    candidate = verify_candidate()
    output = PROJECT_ROOT / str(
        candidate["scope"]["segments"][segment_index]["output_root"]
    )
    return output / "technical_segment_review_v4.json"


def build_segment_review(segment_index: int, *, quota_day: str) -> dict[str, Any]:
    permit = _permit(
        segment_index=segment_index,
        quota_day=quota_day,
        selected_admission=admission_path(segment_index, quota_day),
    )
    state = v1._state(permit)
    records = state["records"]
    expected = int(permit.admission["maximum_provider_requests"])
    bundles = [entry["record"]["provider_trace_bundle"] for entry in records]
    calls = state["call_status"]["completed_calls"]
    trace_calls = sum(
        int(bundle["completed_request_count"]) for bundle in bundles
    )
    checks = {
        "exact_record_count": len(records) == len(permit.work_items),
        "all_attempts_terminal": not state["attempt_status"]["open_work_keys"],
        "all_call_attempts_terminal": state["call_status"]["open_attempts"] == 0,
        "all_records_formal_candidates": all(
            entry["record"]["result_tier"] == "formal_candidate"
            for entry in records
        ),
        "provider_call_cap_respected": calls <= expected,
        "call_ledger_matches_trace_bundles": calls == trace_calls,
        "all_trace_bundles_complete": all(
            bundle["bundle_status"] == "completed"
            and bundle["provider_id"] == "gemini"
            and bundle["model_id"] == MODEL_ID
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
    core = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "artifact_role": "outcome_blind_gemini_canary_segment_review",
        "reviewed_at": _now(),
        "status": (
            "gemini_public_v4_segment_technical_gate_pass"
            if passed
            else "gemini_public_v4_segment_technical_gate_fail"
        ),
        "segment_index": segment_index,
        "quota_day": quota_day,
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "admission_file_sha256": permit.admission_file_sha256,
        "expected_records": len(permit.work_items),
        "observed_records": len(records),
        "provider_calls_completed": calls,
        "provider_trace_calls_completed": trace_calls,
        "maximum_provider_requests": expected,
        "work_keys": [str(item["work_key"]) for item in permit.work_items],
        "checks": checks,
        "technical_gate_passed": passed,
        "scientific_outcomes_accessed": False,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_segment_review(segment_index: int, *, quota_day: str) -> dict[str, Any]:
    value = build_segment_review(segment_index, quota_day=quota_day)
    _write_json(review_path(segment_index), value)
    return value


def build_aggregate_review() -> dict[str, Any]:
    candidate = verify_candidate()
    reviews: list[dict[str, Any]] = []
    for segment in candidate["scope"]["segments"]:
        path = review_path(int(segment["segment_index"]))
        review = _read_json(path)
        if (
            review.get("manifest_sha256") != _manifest_sha(review)
            or review.get("technical_gate_passed") is not True
            or review.get("execution_identity") != segment["execution_identity"]
        ):
            raise GeminiPublicControllerV4Error(
                "Gemini canary segment review not admitted"
            )
        reviews.append(review)
    keys = [key for review in reviews for key in review["work_keys"]]
    expected_keys = [str(row["work_key"]) for row in _source_rows()]
    checks = {
        "all_eight_segment_gates_passed": len(reviews) == 8,
        "exact_twelve_canary_records": sum(
            int(review["observed_records"]) for review in reviews
        )
        == 12,
        "source_order_complete_and_disjoint": keys == expected_keys
        and len(set(keys)) == 12,
        "distinct_quota_days": len({review["quota_day"] for review in reviews})
        == 8,
        "all_free_tier_daily_caps_respected": all(
            review["provider_calls_completed"]
            <= review["maximum_provider_requests"]
            <= daily_quota.LOCAL_REQUEST_CAP
            for review in reviews
        ),
    }
    passed = all(checks.values())
    core = {
        "schema_version": "m3-paper-v2-gemini-public-canary-aggregate-review-4.0",
        "artifact_role": "outcome_blind_segmented_canary_aggregate_review",
        "reviewed_at": _now(),
        "status": (
            "gemini_public_v4_canary_technical_gate_pass"
            if passed
            else "gemini_public_v4_canary_technical_gate_fail"
        ),
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "segment_review_manifest_sha256": [
            review["manifest_sha256"] for review in reviews
        ],
        "observed_records": sum(
            int(review["observed_records"]) for review in reviews
        ),
        "provider_calls_completed": sum(
            int(review["provider_calls_completed"]) for review in reviews
        ),
        "checks": checks,
        "matrix_continuation_eligible": passed,
        "scientific_outcomes_accessed": False,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_aggregate_review() -> dict[str, Any]:
    value = build_aggregate_review()
    _write_json(AGGREGATE_REVIEW_PATH, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-supersession", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-segment", action="store_true")
    action.add_argument("--write-segment-review", action="store_true")
    action.add_argument("--write-aggregate-review", action="store_true")
    parser.add_argument("--segment-index", type=int)
    parser.add_argument("--quota-day")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--approved-at")
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.write_supersession:
        value = write_v3_supersession_review()
    elif args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    elif args.write_aggregate_review:
        value = write_aggregate_review()
    else:
        if args.segment_index is None or not args.quota_day:
            parser.error("segment action requires --segment-index and --quota-day")
        selected = args.admission or admission_path(
            args.segment_index, args.quota_day
        )
        if args.write_admission:
            if not args.approved_at or not args.owner_statement_sha256:
                parser.error("admission requires approval time and owner digest")
            value = write_segment_admission(
                args.segment_index,
                quota_day=args.quota_day,
                approved_at=args.approved_at,
                owner_statement_sha256=args.owner_statement_sha256,
            )
        elif args.verify_admission:
            value = validate_segment_admission(
                _read_json(selected),
                segment_index=args.segment_index,
                quota_day=args.quota_day,
            )
        elif args.execute_segment:
            value = execute_segment(
                args.segment_index,
                quota_day=args.quota_day,
                selected_admission=selected,
                config_path=args.config,
            )
        else:
            value = write_segment_review(
                args.segment_index, quota_day=args.quota_day
            )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
