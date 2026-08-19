"""Freeze the content-free abort review for the Public-v3 primary canary."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import formal_matrix_controller_v1 as medium_v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.medium_runtime import DEFAULT_V2_PLAN
from experiments.paper_v2.public_execution_store_v1 import (
    cross_bind_public_budget_and_records,
    load_public_record_entries,
    validate_public_budget_events,
    validate_public_record_entries,
)
from experiments.paper_v2.public_live_controller_v3 import (
    canonical_canary_command,
)
from experiments.paper_v2.public_m3_live_dependency_v3 import (
    PublicFrozenM3CaseResolverV3,
)
from experiments.paper_v2.public_matrix_controller_v3 import (
    DEFAULT_CANDIDATE,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_PLAN,
    _canary_items,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions/"
    "deepseek_public_primary_canary_admission_v3.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v3.json"
)
GENERATED_AT = "2026-07-29T01:30:00+08:00"
OPEN_WORK_KEY = (
    "22e6848e56bd68430295f2ffac68d82508121577a2c547b72077c4e8acac5f7c"
)


class PublicAbortReviewV3Error(ValueError):
    """Raised when the frozen Public-v3 abort evidence drifts."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicAbortReviewV3Error(f"{path}: expected an object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicAbortReviewV3Error(f"missing abort evidence: {path}")
    return {
        "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                key: item
                for key, item in value.items()
                if key != "manifest_sha256"
            }
        )
    ).hexdigest()


def _plan_work_keys(path: Path) -> set[str]:
    return {
        str(row["work_key"])
        for row in medium_v1._load_jsonl(path)
    }


def _validate_frozen_candidate(value: dict[str, Any]) -> dict[str, Any]:
    if (
        value.get("schema_version")
        != "m3-paper-v2-public-matrix-candidate-3.0"
        or value.get("scope_sha256")
        != sha256_canonical_json(value.get("scope"))
        or value.get("manifest_sha256") != _manifest_sha(value)
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 frozen candidate digest drift"
        )
    for item in value.get("artifact_locks", []):
        path = (PROJECT_ROOT / str(item["path"])).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise PublicAbortReviewV3Error(
                "Public-v3 candidate lock escapes project"
            ) from exc
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise PublicAbortReviewV3Error(
                f"Public-v3 candidate lock drift: {item['path']}"
            )
    return value


def _validate_frozen_admission(
    value: dict[str, Any],
    *,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    command = canonical_canary_command("primary")
    role = candidate["scope"]["model_roles"]["primary"]
    run = candidate["scope"]["runs"]["primary"]
    if (
        value.get("schema_version")
        != "m3-paper-v2-public-matrix-admission-3.0"
        or value.get("scope_sha256")
        != sha256_canonical_json(value.get("scope"))
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or value["authorization"]["candidate_scope_sha256"]
        != candidate["scope_sha256"]
        or value["scope"]["execution_identity"]
        != role["execution_identity"]
        or value["scope"]["model_id"] != role["model_id"]
        or value["scope"]["run_id"] != run["run_id"]
        or value["scope"]["output_root"] != run["output_root"]
        or value["scope"]["exact_command"] != command
        or value["scope"]["exact_command_sha256"]
        != hashlib.sha256(command.encode("utf-8")).hexdigest()
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 frozen admission/candidate binding drift"
        )
    return value


def build_abort_review() -> dict[str, Any]:
    candidate = _validate_frozen_candidate(
        _load_json(DEFAULT_CANDIDATE)
    )
    admission = _validate_frozen_admission(
        _load_json(ADMISSION),
        candidate=candidate,
    )
    run_id = str(admission["scope"]["run_id"])
    execution_identity = str(admission["scope"]["execution_identity"])
    rows = copy.deepcopy(
        _canary_items(
            medium_v1._load_jsonl(DEFAULT_PLAN),
            "primary",
        )
    )
    if len(rows) != 24:
        raise PublicAbortReviewV3Error("Public-v3 canary size drift")
    for item in rows:
        item["execution_identity"] = execution_identity
    if (
        admission["scope"]["canary_records"] != len(rows)
        or admission["scope"]["canary_work_key_sequence_sha256"]
        != sha256_canonical_json([item["work_key"] for item in rows])
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 frozen canary sequence drift"
        )
    known_keys = {str(item["work_key"]) for item in rows}
    root = PROJECT_ROOT / str(admission["scope"]["output_root"])
    attempt_path = root / "attempt_events.jsonl"
    budget_path = root / "budget_events.jsonl"
    record_path = root / "experiment_records.jsonl"
    trace_root = root / "provider_traces"

    attempts = medium_v1._load_jsonl(attempt_path)
    attempt_status = medium_v1.validate_attempt_events(
        attempts,
        run_id=run_id,
        execution_identity=execution_identity,
        known_work_keys=known_keys,
    )
    open_keys = set(attempt_status["open_work_keys"])
    terminal_attempts = set(attempt_status["terminal_by_work_key"])
    if (
        len(attempts) != 25
        or open_keys != {OPEN_WORK_KEY}
        or len(terminal_attempts) != 12
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 attempt ledger differs from the stopped canary"
        )

    role_policy = build_role_policy(load_public_policy(), "primary")
    budget_events = medium_v1._load_jsonl(budget_path)
    budget_status = validate_public_budget_events(
        budget_events,
        run_id=run_id,
        execution_identity=execution_identity,
        model_role="primary",
        known_work_keys=known_keys,
        role_policy=role_policy,
    )
    expected_usage = {
        "prompt_tokens": 26184,
        "completion_tokens": 2534,
        "prompt_cache_hit_tokens": 22656,
        "prompt_cache_miss_tokens": 3528,
    }
    if (
        len(budget_events) != 33
        or budget_status["paused"]
        or budget_status["role_cumulative_usage"] != expected_usage
        or budget_status["role_cumulative_cost_cny"] != 0.0263544
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 budget ledger differs from the stopped canary"
        )

    record_entries = load_public_record_entries(record_path)
    record_status = validate_public_record_entries(
        record_entries,
        work_items=rows,
        execution_identity=execution_identity,
        run_id=run_id,
        role_policy=role_policy,
    )
    record_keys = {str(entry["work_key"]) for entry in record_entries}
    if (
        len(record_entries) != 12
        or record_keys != terminal_attempts
        or OPEN_WORK_KEY in record_keys
        or record_status["remaining_work_items"] != 12
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 record/attempt boundary drift"
        )

    open_budget_events = [
        event
        for event in budget_events
        if str(event["work_key"]) == OPEN_WORK_KEY
    ]
    completed_budget_events = [
        event
        for event in budget_events
        if str(event["work_key"]) != OPEN_WORK_KEY
    ]
    if (
        len(open_budget_events) != 2
        or [event["call_index"] for event in open_budget_events] != [1, 2]
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 orphaned-call boundary drift"
        )
    cross_bind_public_budget_and_records(
        budget_events=completed_budget_events,
        record_entries=record_entries,
        trace_root=trace_root,
        role_policy=role_policy,
    )

    open_trace_path = trace_root / f"{OPEN_WORK_KEY}.jsonl"
    open_trace = medium_v1._trace_rows(open_trace_path)
    completed_trace = [
        row
        for row in open_trace
        if row["event"]["event_type"] == "completed"
    ]
    trace_response_ids = {
        str(row["event"]["attestation"]["provider_response_id"])
        for row in completed_trace
    }
    budget_response_ids = {
        str(event["provider_response_id"])
        for event in open_budget_events
    }
    if (
        len(open_trace) != 4
        or [row["event"]["event_type"] for row in open_trace]
        != ["started", "completed", "started", "completed"]
        or any(row["event"]["automatic_retry"] for row in open_trace)
        or trace_response_ids != budget_response_ids
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 open-attempt trace drift"
        )

    public_keys = _plan_work_keys(DEFAULT_PLAN)
    medium_keys = _plan_work_keys(DEFAULT_V2_PLAN)
    open_item = next(
        item for item in rows if str(item["work_key"]) == OPEN_WORK_KEY
    )
    binding = PublicFrozenM3CaseResolverV3().resolve(OPEN_WORK_KEY)
    active_material_digest = sha256_canonical_json(
        {
            "execution_identity": execution_identity,
            "work_key": OPEN_WORK_KEY,
        }
    )
    if (
        open_item["benchmark"] != "m3-v2"
        or OPEN_WORK_KEY not in public_keys
        or OPEN_WORK_KEY in medium_keys
        or binding.execution_identity == execution_identity
        or binding.work_key_sha256 == active_material_digest
    ):
        raise PublicAbortReviewV3Error(
            "Public-v3 execution-identity mismatch classification drift"
        )

    response_ids = [
        str(event["provider_response_id"])
        for event in budget_events
    ]
    artifact_paths = [
        DEFAULT_CANDIDATE,
        ADMISSION,
        attempt_path,
        budget_path,
        record_path,
        *sorted(trace_root.glob("*.jsonl")),
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/public_m3_live_dependency_v4.py",
        PROJECT_ROOT
        / "protocols/paper_upgrade_v2/"
        "public_m3_live_dependency_qualification_v4.json",
    ]
    core: dict[str, Any] = {
        "schema_version": "m3-paper-v2-public-canary-abort-review-3.0",
        "generated_at": GENERATED_AT,
        "status": "aborted_partial_records_result_ineligible",
        "run_id": run_id,
        "execution_identity": execution_identity,
        "candidate_manifest_sha256": admission["authorization"][
            "candidate_manifest_sha256"
        ],
        "admission_manifest_sha256": admission["manifest_sha256"],
        "admission_file_sha256": _sha256_file(ADMISSION),
        "stop_reason": "public_m3_binding_used_stale_execution_identity",
        "operational_summary": {
            "expected_records": 24,
            "record_count": len(record_entries),
            "remaining_work_items": record_status["remaining_work_items"],
            "attempt_event_count": len(attempts),
            "terminal_attempt_count": len(terminal_attempts),
            "open_attempt_count": len(open_keys),
            "untouched_work_item_count": (
                len(rows) - len(record_entries) - len(open_keys)
            ),
            "provider_calls_completed": len(budget_events),
            "record_bound_provider_calls": len(completed_budget_events),
            "orphaned_completed_provider_calls": len(open_budget_events),
            "provider_response_ids_sha256": sha256_canonical_json(
                response_ids
            ),
            "role_cumulative_usage": budget_status[
                "role_cumulative_usage"
            ],
            "role_cumulative_cost_cny": budget_status[
                "role_cumulative_cost_cny"
            ],
            "budget_status": "continue",
        },
        "root_cause": {
            "open_work_key": OPEN_WORK_KEY,
            "benchmark": "m3-v2",
            "active_execution_identity_sha256": hashlib.sha256(
                execution_identity.encode("utf-8")
            ).hexdigest(),
            "resolver_execution_identity_sha256": hashlib.sha256(
                binding.execution_identity.encode("utf-8")
            ).hexdigest(),
            "active_material_work_key_sha256": active_material_digest,
            "resolver_binding_work_key_sha256": binding.work_key_sha256,
            "binding_digest_matches_active_material": False,
            "v4_remediation_qualified_offline": True,
        },
        "integrity_checks": {
            "candidate_and_admission_bound": True,
            "attempt_chain_valid": True,
            "budget_chain_valid": True,
            "record_chain_valid": True,
            "terminal_attempts_equal_record_keys": True,
            "open_attempt_disjoint_from_records": True,
            "completed_record_budget_trace_cross_bound": True,
            "orphan_trace_calls_equal_open_budget_calls": True,
            "official_response_ids_present": True,
            "automatic_retry_used": False,
            "public_m3_key_absent_from_medium_resolver_plan": True,
            "active_identity_differs_from_v3_resolver_binding": True,
            "external_effects_enabled": False,
        },
        "artifact_locks": [
            _lock(path)
            for path in sorted(
                set(artifact_paths),
                key=lambda item: item.as_posix(),
            )
        ],
        "evidence_boundary": {
            "scientific_outcomes_aggregated": False,
            "scientific_outcome_fields_reported": False,
            "result_admission_authorized": False,
            "analysis_authorized": False,
            "run_resumable": False,
            "open_attempt_retry_authorized": False,
            "network_calls_made_by_review": 0,
            "append_only_ledgers_mutated_by_review": False,
        },
        "supersession_requirement": (
            "Any further execution requires a new run, execution identity, "
            "candidate, admission, and owner confirmation after the active-"
            "identity-aware public M3 evaluator path is fully qualified."
        ),
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def write_abort_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_abort_review()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_abort_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_abort_review()
    if observed != expected:
        raise PublicAbortReviewV3Error("Public-v3 abort review drift")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    value = (
        write_abort_review(args.output)
        if args.write
        else verify_abort_review(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
