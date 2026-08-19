"""Freeze the content-free abort review for public continuation-v1 shards."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as medium_v1
import experiments.paper_v2.public_sharded_continuation_v1 as continuation_v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.public_execution_store_v1 import (
    cross_bind_public_budget_and_records,
    load_public_record_entries,
    validate_public_budget_events,
    validate_public_record_entries,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    PublicProviderTraceError,
    build_public_usage_summary,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/"
    "public_primary_continuation_abort_review_v1.json"
)
RUNTIME_LOG_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/public_primary_continuation_runtime_20260730"
)
GENERATED_AT = "2026-07-30T01:05:00+08:00"
EXPECTED_ERROR = "public usage summary drift"


class PublicShardedContinuationAbortReviewError(ValueError):
    """Raised when the stopped continuation-v1 evidence has drifted."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicShardedContinuationAbortReviewError(
            f"{path}: expected an object"
        )
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicShardedContinuationAbortReviewError(
            f"missing continuation-v1 abort evidence: {path}"
        )
    return {
        "path": _display_path(path),
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


def _validated_admission(
    *,
    candidate: Mapping[str, Any],
    shard_index: int,
) -> tuple[dict[str, Any], Path]:
    path = continuation_v1.admission_path("primary", shard_index)
    value = _load_json(path)
    Draft202012Validator(
        continuation_v1._load_json(continuation_v1.ADMISSION_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(value)
    shard = candidate["scope"]["shards"][shard_index]
    command = continuation_v1.canonical_shard_command(
        "primary",
        shard_index,
    )
    if (
        value["scope_sha256"]
        != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"]
        != continuation_v1._manifest_sha(value)
        or value["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or value["scope"]["shard_index"] != shard_index
        or value["scope"]["run_id"] != shard["run_id"]
        or value["scope"]["execution_identity"]
        != shard["execution_identity"]
        or value["scope"]["records"] != shard["records"]
        or value["scope"]["work_key_sequence_sha256"]
        != shard["work_key_sequence_sha256"]
        or value["scope"]["output_root"] != shard["output_root"]
        or value["scope"]["hard_spend_limit_cny"] != 4.9
        or value["scope"]["exact_command"] != command
        or value["scope"]["exact_command_sha256"]
        != hashlib.sha256(command.encode("utf-8")).hexdigest()
        or value["authorization"]["shard_execution_authorized"] is not True
        or value["authorization"]["result_admission_authorized"] is not False
    ):
        raise PublicShardedContinuationAbortReviewError(
            f"continuation-v1 shard {shard_index} admission drift"
        )
    return value, path


def _stderr_matches(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return (
        EXPECTED_ERROR in text
        and "PublicProviderTraceError" in text
        and "unsafe_effect" not in text
        and "task_completion" not in text
    )


def build_abort_review() -> dict[str, Any]:
    candidate = continuation_v1.verify_candidate("primary")
    shard_policy = continuation_v1._shard_role_policy("primary")
    global_policy = build_role_policy(load_public_policy(), "primary")
    artifact_paths: list[Path] = [
        Path(__file__),
        continuation_v1.candidate_path("primary"),
        continuation_v1.ADMISSION_SCHEMA,
        PROJECT_ROOT
        / "experiments/paper_v2/public_sharded_continuation_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_live_controller_v2.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_execution_store_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_provider_trace_v1.py",
    ]
    shard_summaries: list[dict[str, Any]] = []
    total_calls = 0
    total_cost = 0.0
    total_usage = {
        "prompt_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
        "completion_tokens": 0,
    }

    for shard_index, shard in enumerate(candidate["scope"]["shards"]):
        admission, admission_path = _validated_admission(
            candidate=candidate,
            shard_index=shard_index,
        )
        rows = continuation_v1._shard_rows(
            candidate,
            "primary",
            shard_index,
        )
        known_keys = {str(item["work_key"]) for item in rows}
        root = PROJECT_ROOT / str(shard["output_root"])
        attempt_path = root / "attempt_events.jsonl"
        record_path = root / "experiment_records.jsonl"
        budget_path = root / "budget_events.jsonl"
        trace_root = root / "provider_traces"
        stderr_path = RUNTIME_LOG_ROOT / f"shard_{shard_index}.stderr.log"
        stdout_path = RUNTIME_LOG_ROOT / f"shard_{shard_index}.stdout.log"

        attempts = medium_v1._load_jsonl(attempt_path)
        attempt_status = medium_v1.validate_attempt_events(
            attempts,
            run_id=str(shard["run_id"]),
            execution_identity=str(shard["execution_identity"]),
            known_work_keys=known_keys,
        )
        if (
            len(attempts) != 2
            or attempt_status["open_work_keys"]
            or len(attempt_status["terminal_by_work_key"]) != 1
        ):
            raise PublicShardedContinuationAbortReviewError(
                f"continuation-v1 shard {shard_index} attempt boundary drift"
            )

        budget_events = medium_v1._load_jsonl(budget_path)
        budget_status = validate_public_budget_events(
            budget_events,
            run_id=str(shard["run_id"]),
            execution_identity=str(shard["execution_identity"]),
            model_role="primary",
            known_work_keys=known_keys,
            role_policy=shard_policy,
        )
        record_entries = load_public_record_entries(record_path)
        record_status = validate_public_record_entries(
            record_entries,
            work_items=rows,
            execution_identity=str(shard["execution_identity"]),
            run_id=str(shard["run_id"]),
            role_policy=shard_policy,
        )
        if (
            len(record_entries) != 1
            or record_status["remaining_work_items"] != len(rows) - 1
            or set(record_status["terminal_work_keys"])
            != set(attempt_status["terminal_by_work_key"])
            or budget_status["paused"]
        ):
            raise PublicShardedContinuationAbortReviewError(
                f"continuation-v1 shard {shard_index} record boundary drift"
            )
        cross_bind_public_budget_and_records(
            budget_events=budget_events,
            record_entries=record_entries,
            trace_root=trace_root,
            role_policy=shard_policy,
        )

        record = record_entries[0]["record"]
        bundle = record["provider_trace_bundle"]
        stored_summary = bundle["usage_summary"]
        shard_summary = build_public_usage_summary(
            bundle["usage_evidence"],
            role_policy=shard_policy,
        )
        global_summary = build_public_usage_summary(
            bundle["usage_evidence"],
            role_policy=global_policy,
        )
        try:
            validate_public_record_entries(
                record_entries,
                work_items=rows,
                execution_identity=str(shard["execution_identity"]),
                run_id=str(shard["run_id"]),
                role_policy=global_policy,
            )
        except PublicProviderTraceError as exc:
            global_rejection = str(exc) == EXPECTED_ERROR
        else:
            global_rejection = False
        trace_files = sorted(trace_root.glob("*.jsonl"))
        if (
            record["result_tier"] != "formal_candidate"
            or stored_summary != shard_summary
            or stored_summary["abort_ceiling_cny"] != 4.9
            or global_summary["abort_ceiling_cny"] != 20.0
            or not global_rejection
            or len(trace_files) != 1
            or not _stderr_matches(stderr_path)
            or stdout_path.stat().st_size != 0
        ):
            raise PublicShardedContinuationAbortReviewError(
                f"continuation-v1 shard {shard_index} failure classification drift"
            )

        calls = int(stored_summary["completed_call_count"])
        cost = float(stored_summary["cumulative_cost_cny"])
        total_calls += calls
        total_cost = round(total_cost + cost, 12)
        for field in total_usage:
            total_usage[field] += int(stored_summary[field])
        shard_summaries.append(
            {
                "shard_index": shard_index,
                "run_id": shard["run_id"],
                "expected_records": len(rows),
                "record_count": 1,
                "terminal_attempt_count": 1,
                "open_attempt_count": 0,
                "remaining_records": len(rows) - 1,
                "provider_calls_completed": calls,
                "cumulative_cost_cny": cost,
                "stored_abort_ceiling_cny": 4.9,
                "generic_state_abort_ceiling_cny": 20.0,
                "generic_state_rejection": EXPECTED_ERROR,
                "automatic_retry_used": False,
                "result_admission_authorized": False,
                "run_resumable": False,
                "admission_manifest_sha256": admission["manifest_sha256"],
            }
        )
        artifact_paths.extend(
            [
                admission_path,
                attempt_path,
                record_path,
                budget_path,
                stderr_path,
                stdout_path,
                *trace_files,
            ]
        )

    if (
        total_calls != 13
        or total_cost != 0.014446
        or sum(item["record_count"] for item in shard_summaries) != 4
        or sum(item["remaining_records"] for item in shard_summaries) != 5054
    ):
        raise PublicShardedContinuationAbortReviewError(
            "continuation-v1 aggregate operational summary drift"
        )

    core: dict[str, Any] = {
        "schema_version": (
            "m3-paper-v2-public-sharded-continuation-abort-review-1.0"
        ),
        "generated_at": GENERATED_AT,
        "status": "four_shards_aborted_after_first_record_result_ineligible",
        "model_role": "primary",
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "stop_reason": "shard_policy_not_forwarded_to_generic_state_recovery",
        "operational_summary": {
            "expected_records": 5058,
            "record_count": 4,
            "remaining_records": 5054,
            "attempt_event_count": 8,
            "terminal_attempt_count": 4,
            "open_attempt_count": 0,
            "provider_calls_completed": total_calls,
            "role_cumulative_usage": total_usage,
            "role_cumulative_cost_cny": total_cost,
            "automatic_retries": 0,
            "live_processes_remaining": 0,
        },
        "root_cause": {
            "record_build_policy_abort_ceiling_cny": 4.9,
            "post_append_generic_state_abort_ceiling_cny": 20.0,
            "record_usage_and_cost_arithmetic_valid_under_shard_policy": True,
            "generic_state_rejection": EXPECTED_ERROR,
            "provider_usage_anomaly_observed": False,
            "remediation": (
                "A fresh version must pass the exact shard role policy into "
                "every state reconstruction and use new run, execution, "
                "admission, and output identities."
            ),
        },
        "shards": shard_summaries,
        "integrity_checks": {
            "candidate_and_four_admissions_bound": True,
            "attempt_chains_valid": True,
            "all_attempts_terminal": True,
            "record_chains_valid_under_shard_policy": True,
            "budget_chains_valid_under_shard_policy": True,
            "budget_record_trace_cross_binding_valid": True,
            "four_independent_stderr_failures_match": True,
            "automatic_retry_used": False,
            "provider_tools_enabled": False,
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
            "condition_effects_compared": False,
            "result_admission_authorized": False,
            "analysis_authorized": False,
            "old_roots_resumable": False,
            "old_records_reusable_in_fresh_result": False,
            "selective_retry_authorized": False,
            "network_calls_made_by_review": 0,
            "append_only_ledgers_mutated_by_review": False,
        },
        "supersession_requirement": (
            "Any further primary continuation requires a fresh full-partition "
            "revision with new identities, a policy-aware state resolver, "
            "offline qualification, new candidate, and new single-use admissions."
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
        raise PublicShardedContinuationAbortReviewError(
            "continuation-v1 abort review drift"
        )
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
