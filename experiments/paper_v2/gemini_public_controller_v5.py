"""Prospective Gemini canary recovery under the local-precommit v2 contract.

The historical v4 segment-0 record and segment-1 abort remain immutable.  This
controller selects only the ten untouched canary work keys, assigns fresh run
and execution identities, uses the v2 trace-attaching runtime, and keeps each
free-tier segment behind a separate exact-command admission.
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
import experiments.paper_v2.gemini_local_precommit_contract_v2_candidate as contract_v2
import experiments.paper_v2.gemini_public_controller_v1 as public_v1
import experiments.paper_v2.gemini_public_controller_v4 as public_v4
import experiments.paper_v2.gemini_public_segment_abort_review_v1 as abort_v1
import experiments.paper_v2.gemini_public_technical_review_v5 as historical_v5
import experiments.paper_v2.gemini_trace_attaching_runtime_v2 as trace_runtime_v2
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.gemini_public_execution_store_v1 import (
    append_execution_result,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderBudgetState,
    ProviderPausedError,
)
from experiments.paper_v2.public_matrix_plan_v1 import hydrate_public_work_item
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
CANDIDATE_PATH = PROTOCOL_ROOT / "gemini_public_canary_recovery_candidate_v5.json"
AGGREGATE_REVIEW_PATH = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini/"
    "public-v5-canary-recovery-aggregate-review-v1.json"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-public-canary-recovery-candidate-5.0"
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-canary-recovery-segment-admission-5.0"
)
REVIEW_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-canary-recovery-segment-review-6.0"
)
AGGREGATE_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-canary-recovery-aggregate-review-1.0"
)
GENERATED_AT = "2026-08-04T03:00:00+08:00"
MODEL_ID = "gemini-3.6-flash"
HISTORICAL_S0_QUOTA_DAY = "2026-08-02"
HISTORICAL_S1_QUOTA_DAY = "2026-08-03"
OWNER_APPROVAL_STATEMENT = (
    "The project owner approved the 21-day closeout plan and future exact "
    "Gemini research commands under the official free tier, USD 0 paid "
    "ceiling, zero automatic retries, no provider tools, no real effects, "
    "and no retry of historical terminal or aborted work items."
)
OWNER_STATEMENT_SHA256 = hashlib.sha256(
    OWNER_APPROVAL_STATEMENT.encode("utf-8")
).hexdigest()


class GeminiPublicControllerV5Error(RuntimeError):
    """Raised when prospective Gemini recovery cannot remain fail closed."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicControllerV5Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise GeminiPublicControllerV5Error(f"{path}: expected object")
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


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiPublicControllerV5Error(f"missing candidate input: {path}")
    return {
        "path": _display(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(value: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(value.get("path", ""))).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise GeminiPublicControllerV5Error(
            "candidate lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != value.get("bytes")
        or _sha256_file(path) != value.get("sha256")
    ):
        raise GeminiPublicControllerV5Error(f"candidate lock drift: {path}")


def _validated_contract_candidate() -> dict[str, Any]:
    return contract_v2.validate_candidate(
        _read_json(contract_v2.DEFAULT_OUTPUT)
    )


def _historical_boundary() -> dict[str, Any]:
    source = _read_json(public_v4.CANDIDATE_PATH)
    contract = _validated_contract_candidate()
    segment0_review = _read_json(historical_v5.review_path(0))
    abort = _read_json(abort_v1.DEFAULT_OUTPUT)
    if (
        source.get("schema_version") != public_v4.SCHEMA_VERSION
        or source.get("manifest_sha256") != public_v4._manifest_sha(source)
        or source.get("authorization", {}).get("segment_execution_authorized")
        is not False
    ):
        raise GeminiPublicControllerV5Error(
            "historical Gemini v4 candidate drift"
        )
    for lock in source.get("artifact_locks", []):
        if not isinstance(lock, Mapping):
            raise GeminiPublicControllerV5Error(
                "historical Gemini v4 candidate lock drift"
            )
        _verify_lock(lock)
    if (
        segment0_review.get("manifest_sha256")
        != historical_v5._manifest_sha(segment0_review)
        or segment0_review.get("status")
        != "gemini_public_v5_segment_technical_gate_pass"
        or segment0_review.get("technical_gate_passed") is not True
        or segment0_review.get("scientific_outcomes_accessed") is not False
        or segment0_review.get("result_admission_authorized") is not False
        or not all(segment0_review.get("checks", {}).values())
    ):
        raise GeminiPublicControllerV5Error(
            "historical Gemini segment-0 review drift"
        )
    for lock in segment0_review.get("source_locks", []):
        if not isinstance(lock, Mapping):
            raise GeminiPublicControllerV5Error(
                "historical Gemini segment-0 lock drift"
            )
        _verify_lock(lock)
    abort_core = {
        key: child for key, child in abort.items() if key != "manifest_sha256"
    }
    if (
        abort.get("manifest_sha256") != sha256_canonical_json(abort_core)
        or abort.get("status")
        != "aborted_result_ineligible_contract_revision_required"
        or abort.get("disposition", {}).get("same_work_item_retry_allowed")
        is not False
        or abort.get("disposition", {}).get("orphan_response_promotable")
        is not False
        or abort.get("evidence_boundary", {}).get("scientific_outcomes_read")
        != 0
        or not all(abort.get("technical_checks", {}).values())
    ):
        raise GeminiPublicControllerV5Error(
            "historical Gemini segment-1 abort drift"
        )
    for lock in abort.get("locked_evidence", []):
        if not isinstance(lock, Mapping):
            raise GeminiPublicControllerV5Error(
                "historical Gemini segment-1 lock drift"
            )
        _verify_lock(lock)
    segments = source["scope"]["segments"]
    s0_key = str(segments[0]["work_keys"][0])
    s1_first_key = str(segments[1]["work_keys"][0])
    reconciled = segment0_review["reconciliation"]["reconciled_calls"]
    if (
        segment0_review.get("technical_gate_passed") is not True
        or len(reconciled) != 1
        or reconciled[0].get("work_key") != s0_key
    ):
        raise GeminiPublicControllerV5Error(
            "historical Gemini terminal boundary drift"
        )
    segment1 = segments[1]
    admission_path = public_v4.admission_path(1, HISTORICAL_S1_QUOTA_DAY)
    admission = _read_json(admission_path)
    admission_core = {
        key: child
        for key, child in admission.items()
        if key != "manifest_sha256"
    }
    if (
        admission.get("manifest_sha256")
        != sha256_canonical_json(admission_core)
        or admission.get("candidate_manifest_sha256")
        != source["manifest_sha256"]
        or admission.get("execution_identity")
        != segment1["execution_identity"]
        or admission.get("run_id") != segment1["run_id"]
        or admission.get("authorization", {}).get("automatic_retries") != 0
    ):
        raise GeminiPublicControllerV5Error(
            "historical Gemini segment-1 admission drift"
        )
    attempt_path = (
        PROJECT_ROOT / str(segment1["output_root"]) / "attempt_events_v1.jsonl"
    )
    attempts = public_v1.matrix_v1._load_jsonl(attempt_path)
    attempt_status = public_v1.matrix_v1.validate_attempt_events(
        attempts,
        run_id=str(segment1["run_id"]),
        execution_identity=str(segment1["execution_identity"]),
        known_work_keys={str(key) for key in segment1["work_keys"]},
    )
    if (
        attempt_status["open_work_keys"] != [s1_first_key]
        or attempt_status["terminal_by_work_key"]
        or len(attempts) != 1
    ):
        raise GeminiPublicControllerV5Error(
            "historical aborted work-key boundary drift"
        )
    return {
        "source_candidate_manifest_sha256": source["manifest_sha256"],
        "contract_candidate_manifest_sha256": contract["manifest_sha256"],
        "historical_s0_review_manifest_sha256": segment0_review[
            "manifest_sha256"
        ],
        "historical_s1_abort_manifest_sha256": abort["manifest_sha256"],
        "historical_terminal_record_work_key": s0_key,
        "historical_aborted_work_key": s1_first_key,
        "historical_slots": 2,
        "historical_records": 1,
        "historical_aborts_retained_in_itt": 1,
        "source_max_tokens": source["scope"]["max_tokens"],
        "source_timeout_seconds": source["scope"]["timeout_seconds"],
    }


def _pending_source_rows(
    boundary: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    observed = dict(boundary or _historical_boundary())
    unavailable = {
        str(observed["historical_terminal_record_work_key"]),
        str(observed["historical_aborted_work_key"]),
    }
    source = public_v4._source_rows()
    pending = [
        copy.deepcopy(row)
        for row in source
        if str(row["work_key"]) not in unavailable
    ]
    if (
        len(source) != 12
        or len(pending) != 10
        or len({str(row["work_key"]) for row in source}) != 12
        or any(str(row["work_key"]) in unavailable for row in pending)
    ):
        raise GeminiPublicControllerV5Error(
            "prospective canary pending partition drift"
        )
    return pending


def build_candidate() -> dict[str, Any]:
    boundary = _historical_boundary()
    rows = _pending_source_rows(boundary)
    packed = public_v4._pack_rows(rows)
    contract_manifest = str(boundary["contract_candidate_manifest_sha256"])
    segments: list[dict[str, Any]] = []
    for index, segment_rows in enumerate(packed):
        keys = [str(row["work_key"]) for row in segment_rows]
        maximum = sum(int(row["max_provider_calls"]) for row in segment_rows)
        identity = sha256_canonical_json(
            {
                "schema_version": (
                    "m3-paper-v2-gemini-public-canary-recovery-identity-5.0"
                ),
                "contract_candidate_manifest_sha256": contract_manifest,
                "source_candidate_manifest_sha256": boundary[
                    "source_candidate_manifest_sha256"
                ],
                "segment_index": index,
                "work_keys": keys,
                "maximum_provider_requests": maximum,
            }
        )
        segments.append(
            {
                "segment_index": index,
                "run_id": f"paper-v2-public-gemini-canary-recovery-v5-s{index}",
                "execution_identity": identity,
                "work_keys": keys,
                "work_key_sequence_sha256": sha256_canonical_json(keys),
                "record_count": len(keys),
                "maximum_provider_requests": maximum,
                "output_root": (
                    "outputs/paper_upgrade_v2/formal_public/gemini/"
                    f"public-v5-canary-recovery-s{index}-{identity}"
                ),
            }
        )
    scope = {
        "provider_id": "gemini",
        "model_id": MODEL_ID,
        "model_role": "second",
        "historical_boundary": boundary,
        "combined_canary_slots": 12,
        "pending_records": 10,
        "segment_count": len(segments),
        "segments": segments,
        "quota": {
            "billing_tier": "free",
            "paid_ceiling_usd": 0.0,
            "local_requests_per_day": daily_quota.LOCAL_REQUEST_CAP,
            "quota_timezone": daily_quota.QUOTA_TIMEZONE,
            "one_formal_segment_per_quota_day": True,
            "automatic_retries": 0,
        },
        "max_tokens": boundary["source_max_tokens"],
        "timeout_seconds": boundary["source_timeout_seconds"],
    }
    paths = [
        Path(__file__),
        PROJECT_ROOT / "tests/unit/test_paper_v2_gemini_public_controller_v5.py",
        Path(trace_runtime_v2.__file__),
        contract_v2.DEFAULT_OUTPUT,
        public_v4.CANDIDATE_PATH,
        historical_v5.review_path(0),
        abort_v1.DEFAULT_OUTPUT,
        Path(daily_quota.__file__),
        PROJECT_ROOT / "experiments/paper_v2/gemini_json_client_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/gemini_public_execution_store_v1.py",
        public_v1.GEMINI_PUBLIC_PLAN,
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "untouched_only_canary_recovery_candidate",
        "generated_at": GENERATED_AT,
        "status": "candidate_pending_fresh_harness_and_daily_admissions",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_lock(path) for path in paths],
        "authorization": {
            "candidate_only": True,
            "segment_execution_authorized": False,
            "historical_retry_authorized": False,
            "matrix_continuation_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "historical_files_mutated": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicControllerV5Error("Gemini v5 candidate must be object")
    scope = value.get("scope")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("combined_canary_slots") != 12
        or scope.get("pending_records") != 10
        or scope.get("quota", {}).get("billing_tier") != "free"
        or scope.get("quota", {}).get("paid_ceiling_usd") != 0.0
        or scope.get("quota", {}).get("automatic_retries") != 0
        or value.get("authorization", {}).get("segment_execution_authorized")
        is not False
        or value.get("authorization", {}).get("historical_retry_authorized")
        is not False
    ):
        raise GeminiPublicControllerV5Error("Gemini v5 candidate drift")
    boundary = scope.get("historical_boundary")
    if not isinstance(boundary, Mapping):
        raise GeminiPublicControllerV5Error("historical boundary missing")
    pending = _pending_source_rows(boundary)
    source_by_key = {str(row["work_key"]): row for row in pending}
    segments = scope.get("segments")
    if not isinstance(segments, list) or not segments:
        raise GeminiPublicControllerV5Error("Gemini v5 segment set missing")
    flattened: list[str] = []
    run_ids: set[str] = set()
    identities: set[str] = set()
    roots: set[str] = set()
    for index, segment in enumerate(segments):
        keys = segment.get("work_keys")
        if not isinstance(keys, list) or not keys:
            raise GeminiPublicControllerV5Error("Gemini v5 work keys drift")
        try:
            rows = [source_by_key[str(key)] for key in keys]
        except KeyError as exc:
            raise GeminiPublicControllerV5Error(
                "Gemini v5 segment contains unavailable work key"
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
            raise GeminiPublicControllerV5Error(
                "Gemini v5 segment identity or cap drift"
            )
        flattened.extend(str(key) for key in keys)
        run_ids.add(run_id)
        identities.add(identity)
        roots.add(root)
    expected = [str(row["work_key"]) for row in pending]
    if flattened != expected or len(set(flattened)) != 10:
        raise GeminiPublicControllerV5Error(
            "Gemini v5 segments do not partition untouched canary work"
        )
    locks = value.get("artifact_locks")
    if not isinstance(locks, list) or len(locks) != 11:
        raise GeminiPublicControllerV5Error("Gemini v5 lock set drift")
    for lock in locks:
        if not isinstance(lock, Mapping):
            raise GeminiPublicControllerV5Error("Gemini v5 lock invalid")
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    observed = validate_candidate(_read_json(CANDIDATE_PATH))
    expected = build_candidate()
    if observed != expected:
        raise GeminiPublicControllerV5Error(
            "Gemini v5 candidate does not reproduce"
        )
    return observed


def admission_path(segment_index: int, quota_day: str) -> Path:
    return (
        PROTOCOL_ROOT
        / "admissions"
        / f"gemini_public_canary_recovery_v5_s{segment_index}_"
        f"{quota_day}_admission.json"
    )


def canonical_segment_command(segment_index: int, quota_day: str) -> str:
    path = admission_path(segment_index, quota_day).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.gemini_public_controller_v5 "
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
        raise GeminiPublicControllerV5Error("owner authorization digest drift")
    try:
        segment = candidate["scope"]["segments"][segment_index]
    except (IndexError, TypeError) as exc:
        raise GeminiPublicControllerV5Error("segment index out of range") from exc
    command = canonical_segment_command(segment_index, quota_day)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "one_exact_prospective_gemini_segment_authorization",
        "status": "activated_for_one_exact_free_tier_quota_day",
        "approved_at": approved_at,
        "quota_day": quota_day,
        "quota_timezone": daily_quota.QUOTA_TIMEZONE,
        "segment_index": segment_index,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "contract_candidate_manifest_sha256": candidate["scope"][
            "historical_boundary"
        ]["contract_candidate_manifest_sha256"],
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
    value: Any,
    *,
    segment_index: int,
    quota_day: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicControllerV5Error("Gemini v5 admission missing")
    expected = build_segment_admission(
        segment_index,
        quota_day=quota_day,
        approved_at=str(value.get("approved_at", "")),
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
    )
    if dict(value) != expected:
        raise GeminiPublicControllerV5Error("Gemini v5 admission drift")
    return copy.deepcopy(dict(value))


def _segment_rows(
    candidate: Mapping[str, Any], segment_index: int
) -> list[dict[str, Any]]:
    source = {
        str(row["work_key"]): row
        for row in _pending_source_rows(
            candidate["scope"]["historical_boundary"]
        )
    }
    segment = candidate["scope"]["segments"][segment_index]
    rows = [copy.deepcopy(source[key]) for key in segment["work_keys"]]
    for row in rows:
        row["execution_identity"] = segment["execution_identity"]
    return rows


def _permit(
    *,
    segment_index: int,
    quota_day: str,
    selected_admission: Path,
) -> public_v1.GeminiPublicPermit:
    expected_path = admission_path(segment_index, quota_day)
    if selected_admission.resolve() != expected_path.resolve():
        raise GeminiPublicControllerV5Error(
            "segment admission path is not frozen"
        )
    candidate = verify_candidate()
    admission = validate_segment_admission(
        _read_json(selected_admission),
        segment_index=segment_index,
        quota_day=quota_day,
    )
    segment = candidate["scope"]["segments"][segment_index]
    output = PROJECT_ROOT / str(segment["output_root"])
    return public_v1.GeminiPublicPermit(
        run_id=str(segment["run_id"]),
        execution_identity=str(segment["execution_identity"]),
        work_items=tuple(_segment_rows(candidate, segment_index)),
        output_root=output,
        record_ledger_path=output / "experiment_records_v2_contract.jsonl",
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
    return public_v4._daily_policy(maximum_provider_requests)


def _build_dispatcher(
    permit: public_v1.GeminiPublicPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    call_sink: Any,
    budget_state: ProviderBudgetState,
    recorded_at: Callable[[], str] = _now,
) -> Any:
    registry = public_v1._Registry()
    agentdojo = public_v1.PublicFrozenAgentDojoCaseResolverV2(
        plan_path=public_v1.GEMINI_PUBLIC_PLAN
    )
    public_m3 = public_v1.PublicFrozenM3CaseResolverV4(
        execution_identity=permit.execution_identity,
        plan_path=public_v1.GEMINI_PUBLIC_PLAN,
    )
    usage_registry = public_v4.v3.GeminiUsageRegistry()
    traced_factory = functools.partial(
        public_v4.v3.GeminiJsonTracedProviderClient,
        usage_registry=usage_registry,
    )

    def provider_factory(context: Any) -> Any:
        content_class = (
            "synthetic_m3_case"
            if context.benchmark == "m3-v2"
            else "public_benchmark_case"
        )
        client = public_v4.v3.GeminiJsonOfficialClient(
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
            return public_v1.BoundaryAwareM3EffectBackendV3(
                public_v1.M3SandboxEffectBackend(context)
            )
        return agentdojo.build_backend(context, tool_schemas)

    live = public_v1.LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=backend_factory,
        detector=public_v1.PinnedPromptGuardDetector(device="cuda"),
        vigil_factory=public_v1.matrix_v2.RedactedVigilConstraintFactory(),
        call_event_sink=call_sink,
        recorded_at=recorded_at,
    )
    trusted = public_v1.TrustedContextBoundaryRuntimeV3(
        live,
        client_lookup=registry.get,
        recorded_at=recorded_at,
    )
    runtime = trace_runtime_v2.GeminiTraceAttachingRuntimeV2(
        trusted,
        client_lookup=registry.get,
    )
    evaluator = public_v1.PaperV2OfflineOutcomeEvaluator(
        m3_resolver=public_m3,
        agentdojo_resolver=agentdojo,
    )
    evaluator.m3 = public_v1.BoundaryAwareM3OutcomeEvaluatorV3(public_m3)
    return public_v1.build_condition_dispatcher(
        runtime=public_v1.matrix_v2.FailureTierNormalizingRuntime(runtime),
        evaluator=public_v1.matrix_v2.FailureAwareOutcomeEvaluator(evaluator),
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
    initial = public_v1._state(permit)
    if initial["records"] or initial["attempts"] or initial["calls"]:
        raise GeminiPublicControllerV5Error(
            "Gemini v5 segment already started; retry is forbidden"
        )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    policy = _daily_policy(int(permit.admission["maximum_provider_requests"]))
    public_v1.fallback._validate_runtime_config(values, policy)
    api_key = str(values[public_v1.PROVIDER_CONFIG["gemini"]["api_key"]])
    reservation = daily_quota.reserve_formal_day(
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        workload=f"public_canary_recovery_v5_segment_{segment_index}",
        maximum_provider_requests=int(
            permit.admission["maximum_provider_requests"]
        ),
        admission_file_sha256=permit.admission_file_sha256,
        quota_day=quota_day,
        reserved_at=_now(),
        declared_other_project_requests=0,
    )
    call_sink = public_v1.fallback.GeminiCallLedgerSink(
        permit.call_ledger_path,
        execution_identity=permit.execution_identity,
        model_id=MODEL_ID,
    )
    budget_state = ProviderBudgetState(provider_id="gemini", policy=policy)
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
        public_v1.matrix_v1._append_attempt_event(
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
        public_v1.matrix_v1._append_attempt_event(
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
    final = public_v1._state(permit)
    return {
        "status": (
            "gemini_public_v5_recovery_segment_complete_unadmitted"
            if not final["pending"]
            else "gemini_public_v5_recovery_segment_sealed"
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
    return output / "technical_segment_review_v6.json"


def _attestation_matches_contract(record: Mapping[str, Any]) -> bool:
    bundle = record["provider_trace_bundle"]
    activated = bundle["activated_attestations"]
    attestation = record["provider_attestation"]
    if not activated:
        return False
    last = activated[-1]
    return bool(
        attestation.get("formal_evidence_contract")
        == trace_runtime_v2.CONTRACT_ID
        and attestation.get("client_request_id")
        == last["client_request_id"]
        and attestation.get("request_identity_mode") == last["trace_mode"]
        and attestation.get("request_id") == last["provider_request_id"]
        and attestation.get("provider_request_id_available")
        is (last["provider_request_id"] is not None)
        and attestation.get("response_id") == last["provider_response_id"]
        and attestation.get("parameters_sha256") == last["payload_sha256"]
    )


def build_segment_review(
    segment_index: int,
    *,
    quota_day: str,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    permit = _permit(
        segment_index=segment_index,
        quota_day=quota_day,
        selected_admission=admission_path(segment_index, quota_day),
    )
    state = public_v1._state(permit)
    records = state["records"]
    record_values = [entry["record"] for entry in records]
    bundles = [record["provider_trace_bundle"] for record in record_values]
    reconciliation = historical_v5.reconcile_post_response_calls(
        calls=state["calls"],
        records=records,
    )
    trace_calls = sum(
        int(bundle["completed_request_count"]) for bundle in bundles
    )
    reconciled = int(reconciliation["reconciled_post_response_failure_count"])
    call_status = state["call_status"]
    runner_failures = sum(
        record["operational_status"] == "runner_failure"
        for record in record_values
    )
    maximum = int(permit.admission["maximum_provider_requests"])
    checks = {
        "exact_record_count": len(records) == len(permit.work_items),
        "all_attempts_terminal": not state["attempt_status"]["open_work_keys"],
        "all_call_attempts_terminal": call_status["open_attempts"] == 0,
        "provider_call_cap_respected": call_status["call_count"] <= maximum,
        "provider_attempt_count_matches_trace": call_status["call_count"]
        == trace_calls,
        "completed_plus_reconciled_matches_trace": call_status[
            "completed_calls"
        ]
        + reconciled
        == trace_calls,
        "all_failed_calls_exactly_reconciled": call_status["failed_calls"]
        == reconciled,
        "no_paused_calls": call_status["paused_calls"] == 0,
        "per_work_terminal_count_matches_trace": bool(
            reconciliation[
                "per_work_terminal_count_matches_completed_trace_count"
            ]
        ),
        "all_records_formal_candidates": all(
            record["result_tier"] == "formal_candidate"
            for record in record_values
        ),
        "all_v2_contract_attestations": all(
            _attestation_matches_contract(record) for record in record_values
        ),
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
        "all_records_retained_in_itt": all(
            record["included_in_intention_to_treat"] is True
            for record in record_values
        ),
        "all_runner_failures_reconciled": runner_failures == reconciled,
        "all_effects_isolated": all(
            record["provider_safety_receipt"]["evidence"][
                "external_connectors_enabled"
            ]
            is False
            and record["provider_safety_receipt"]["evidence"][
                "provider_managed_tools_enabled"
            ]
            is False
            for record in record_values
        ),
    }
    passed = bool(checks) and all(checks.values())
    core = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "artifact_role": "outcome_blind_gemini_v2_contract_segment_review",
        "reviewed_at": reviewed_at or _now(),
        "status": (
            "gemini_public_v5_recovery_segment_gate_pass"
            if passed
            else "gemini_public_v5_recovery_segment_gate_fail"
        ),
        "segment_index": segment_index,
        "quota_day": quota_day,
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "candidate_manifest_sha256": permit.candidate["manifest_sha256"],
        "admission_file_sha256": permit.admission_file_sha256,
        "expected_records": len(permit.work_items),
        "observed_records": len(records),
        "provider_call_attempts": call_status["call_count"],
        "provider_transport_completions": trace_calls,
        "runtime_runner_failures_retained_in_itt": runner_failures,
        "reconciliation": reconciliation,
        "checks": checks,
        "technical_gate_passed": passed,
        "matrix_continuation_eligible": passed,
        "scientific_outcomes_accessed": False,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_segment_review(segment_index: int, *, quota_day: str) -> dict[str, Any]:
    value = build_segment_review(segment_index, quota_day=quota_day)
    _write_json(review_path(segment_index), value)
    return value


def build_aggregate_review(
    quota_days: Sequence[str],
    *,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    candidate = verify_candidate()
    segments = candidate["scope"]["segments"]
    if len(quota_days) != len(segments):
        raise GeminiPublicControllerV5Error("quota-day list length drift")
    reviews: list[dict[str, Any]] = []
    for segment, quota_day in zip(segments, quota_days, strict=True):
        path = review_path(int(segment["segment_index"]))
        review = _read_json(path)
        if (
            review.get("manifest_sha256") != _manifest_sha(review)
            or review.get("technical_gate_passed") is not True
            or review.get("execution_identity") != segment["execution_identity"]
            or review.get("quota_day") != quota_day
        ):
            raise GeminiPublicControllerV5Error(
                "Gemini v5 segment review not admitted"
            )
        reviews.append(review)
    boundary = candidate["scope"]["historical_boundary"]
    new_keys = [key for segment in segments for key in segment["work_keys"]]
    combined_keys = [
        boundary["historical_terminal_record_work_key"],
        boundary["historical_aborted_work_key"],
        *new_keys,
    ]
    expected_keys = [str(row["work_key"]) for row in public_v4._source_rows()]
    total_new_records = sum(int(review["observed_records"]) for review in reviews)
    all_days = [HISTORICAL_S0_QUOTA_DAY, HISTORICAL_S1_QUOTA_DAY, *quota_days]
    checks = {
        "all_new_segment_gates_passed": len(reviews) == len(segments),
        "exact_ten_new_records": total_new_records == 10,
        "exact_twelve_slots_with_one_abort": (
            boundary["historical_records"]
            + boundary["historical_aborts_retained_in_itt"]
            + total_new_records
            == 12
        ),
        "source_order_complete_and_disjoint": combined_keys == expected_keys
        and len(set(combined_keys)) == 12,
        "distinct_quota_days": len(set(all_days)) == len(all_days),
        "all_daily_caps_respected": all(
            review["provider_call_attempts"]
            <= candidate["scope"]["segments"][index][
                "maximum_provider_requests"
            ]
            <= daily_quota.LOCAL_REQUEST_CAP
            for index, review in enumerate(reviews)
        ),
    }
    passed = all(checks.values())
    core = {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "artifact_role": "outcome_blind_combined_historical_and_v2_canary_review",
        "reviewed_at": reviewed_at or _now(),
        "status": (
            "gemini_public_v5_combined_canary_gate_pass"
            if passed
            else "gemini_public_v5_combined_canary_gate_fail"
        ),
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "historical_boundary": copy.deepcopy(boundary),
        "new_segment_review_manifests": [
            review["manifest_sha256"] for review in reviews
        ],
        "new_records": total_new_records,
        "historical_records": boundary["historical_records"],
        "historical_aborts_retained_in_itt": boundary[
            "historical_aborts_retained_in_itt"
        ],
        "checks": checks,
        "technical_gate_passed": passed,
        "matrix_continuation_eligible": passed,
        "scientific_outcomes_accessed": False,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_aggregate_review(quota_days: Sequence[str]) -> dict[str, Any]:
    value = build_aggregate_review(quota_days)
    _write_json(AGGREGATE_REVIEW_PATH, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-segment", action="store_true")
    action.add_argument("--write-segment-review", action="store_true")
    action.add_argument("--write-aggregate-review", action="store_true")
    parser.add_argument("--segment-index", type=int)
    parser.add_argument("--quota-day")
    parser.add_argument("--quota-days", nargs="*")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--approved-at")
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    elif args.write_aggregate_review:
        value = write_aggregate_review(args.quota_days or [])
    else:
        if args.segment_index is None or not args.quota_day:
            raise GeminiPublicControllerV5Error(
                "segment index and quota day are required"
            )
        if args.write_admission:
            if not args.approved_at or not args.owner_statement_sha256:
                raise GeminiPublicControllerV5Error(
                    "admission approval fields are required"
                )
            value = write_segment_admission(
                args.segment_index,
                quota_day=args.quota_day,
                approved_at=args.approved_at,
                owner_statement_sha256=args.owner_statement_sha256,
            )
        elif args.verify_admission:
            path = args.admission or admission_path(
                args.segment_index, args.quota_day
            )
            value = validate_segment_admission(
                _read_json(path),
                segment_index=args.segment_index,
                quota_day=args.quota_day,
            )
        elif args.execute_segment:
            if args.admission is None:
                raise GeminiPublicControllerV5Error(
                    "exact admission path is required"
                )
            value = execute_segment(
                args.segment_index,
                quota_day=args.quota_day,
                selected_admission=args.admission,
                config_path=args.config,
            )
        else:
            value = write_segment_review(
                args.segment_index,
                quota_day=args.quota_day,
            )
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
