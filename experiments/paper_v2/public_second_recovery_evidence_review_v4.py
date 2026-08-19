"""Separate Flash recovery evidence integrity from its frozen quality gate.

Recovery-v3 completed both append-only shards, but its aggregate technical
review mixed positive checks with the negative fact
``source_terminal_records_retried=false`` and then called ``all``.  This
prospective reviewer does not rewrite that historical artifact.  It replays the
ledgers, keeps the one-percent claim-quality result unchanged, and records a
typed evidence-integrity decision suitable only for a later independent result
admission.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.public_second_continuation_recovery_v3 as recovery_v3
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "m3-paper-v2-public-second-recovery-evidence-review-4.0"
REVIEWED_AT = "2026-08-04T01:35:00+08:00"
SOURCE_REVIEW_NAME = "recovery_shard_review_v3.json"
OUTPUT_NAME = "recovery_shard_evidence_review_v4.json"
QUALITY_CHECK = "diagnostic_fraction_within_frozen_bound"
INTEGRITY_POSITIVE_CHECKS = frozenset(
    {
        "exact_record_count",
        "all_attempts_terminal",
        "record_attempt_terminal_sets_equal",
        "all_tiers_candidate_or_diagnostic",
        "all_records_in_itt",
        "budget_not_paused",
        "budget_record_trace_cross_binding_complete",
    }
)
NEGATIVE_BOUNDARY_CHECKS = frozenset(
    {
        "source_terminal_records_retried",
        "scientific_outcomes_aggregated",
    }
)


class PublicSecondRecoveryEvidenceReviewV4Error(ValueError):
    """Raised when Flash recovery evidence cannot be typed safely."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            f"{path}: expected object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


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
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            f"missing Flash evidence artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def _paths(shard_index: int) -> dict[str, Path]:
    candidate = recovery_v3.verify_candidate()
    shard = recovery_v3._candidate_shard(candidate, shard_index)
    root = PROJECT_ROOT / str(shard["output_root"])
    return {
        "candidate": recovery_v3.CANDIDATE_PATH,
        "admission": recovery_v3.admission_path(shard_index),
        "source_review": root / SOURCE_REVIEW_NAME,
        "output": root / OUTPUT_NAME,
        "records": root / "experiment_records.jsonl",
        "attempts": root / "attempt_events.jsonl",
        "budget": root / "budget_events.jsonl",
    }


def _validate_source_review(
    source: Mapping[str, Any], *, shard_index: int
) -> tuple[bool, dict[str, bool], dict[str, bool]]:
    checks = source.get("checks")
    expected_names = (
        INTEGRITY_POSITIVE_CHECKS
        | NEGATIVE_BOUNDARY_CHECKS
        | {QUALITY_CHECK}
    )
    if (
        source.get("schema_version")
        != "m3-paper-v2-public-second-recovery-review-3.0"
        or source.get("manifest_sha256") != _manifest_sha(source)
        or source.get("shard_index") != shard_index
        or not isinstance(checks, Mapping)
        or set(checks) != expected_names
    ):
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            "Flash recovery-v3 review identity or check set drift"
        )
    positives = {
        name: checks[name] is True
        for name in sorted(INTEGRITY_POSITIVE_CHECKS)
    }
    negatives = {
        name: checks[name] is False
        for name in sorted(NEGATIVE_BOUNDARY_CHECKS)
    }
    if not all(positives.values()):
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            "Flash recovery has a substantive evidence-integrity failure"
        )
    if not all(negatives.values()):
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            "Flash recovery violates a negative evidence boundary"
        )
    quality_passed = checks[QUALITY_CHECK] is True
    legacy_aggregate = all(bool(value) for value in checks.values())
    if (
        source.get("technical_gate_passed") is not legacy_aggregate
        or source.get("status")
        != (
            "flash_recovery_shard_technical_gate_pass"
            if legacy_aggregate
            else "flash_recovery_shard_technical_gate_fail"
        )
    ):
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            "Flash recovery-v3 aggregate does not match its stored checks"
        )
    return quality_passed, positives, negatives


def build_review(shard_index: int) -> dict[str, Any]:
    if shard_index not in range(recovery_v3.SHARD_COUNT):
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            "Flash shard index out of range"
        )
    paths = _paths(shard_index)
    source = _load_json(paths["source_review"])
    quality_passed, positives, negatives = _validate_source_review(
        source, shard_index=shard_index
    )
    permit, _, records, attempts, tracker = recovery_v3._permit_and_state(
        shard_index,
        selected_admission_path=paths["admission"],
        require_unstarted=False,
    )
    record_status = records.full_validate()
    attempt_status = attempts.full_validate()
    budget_status = tracker.full_validate()
    recovery_v3.cross_bind_public_budget_and_records(
        budget_events=tracker.events,
        record_entries=records.entries,
        trace_root=permit.trace_root,
        role_policy=records.role_policy,
    )
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in records.entries
    )
    if (
        len(records.entries) != source.get("observed_records")
        or len(records.entries) != source.get("expected_records")
        or diagnostics != source.get("diagnostic_records")
        or budget_status["event_count"]
        != source.get("provider_calls_completed")
        or budget_status["role_cumulative_cost_cny"]
        != source.get("role_cumulative_cost_cny")
        or attempt_status["open_work_keys"]
        or set(record_status["terminal_work_keys"])
        != set(attempt_status["terminal_by_work_key"])
    ):
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            "Flash recovery ledgers drifted from the source review"
        )
    expected_quality = diagnostics <= int(
        source["maximum_admissible_diagnostic_records"]
    )
    if quality_passed is not expected_quality:
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            "Flash recovery quality result drift"
        )
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": (
            "typed_outcome_blind_flash_recovery_evidence_review"
        ),
        "reviewed_at": REVIEWED_AT,
        "status": "flash_recovery_evidence_integrity_pass",
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "source_review_manifest_sha256": source["manifest_sha256"],
        "candidate_manifest_sha256": source[
            "candidate_manifest_sha256"
        ],
        "admission_file_sha256": source["admission_file_sha256"],
        "expected_records": int(source["expected_records"]),
        "observed_records": len(records.entries),
        "diagnostic_records": diagnostics,
        "diagnostic_fraction": diagnostics / len(records.entries),
        "maximum_admissible_diagnostic_records": int(
            source["maximum_admissible_diagnostic_records"]
        ),
        "provider_calls_completed": int(budget_status["event_count"]),
        "role_cumulative_cost_cny": budget_status[
            "role_cumulative_cost_cny"
        ],
        "record_ledger_tail_sha256": record_status["tail_sha256"],
        "attempt_ledger_tail_sha256": attempt_status["tail_sha256"],
        "budget_ledger_tail_sha256": budget_status["tail_sha256"],
        "integrity_positive_checks": positives,
        "negative_boundary_checks": negatives,
        "claim_quality": {
            "frozen_one_percent_gate_passed": quality_passed,
            "frozen_one_percent_gate_waived": False,
            "clean_mechanism_quality_claim_eligible": quality_passed,
            "empirical_security_utility_fallback_only": not quality_passed,
        },
        "legacy_review": {
            "technical_gate_passed": source["technical_gate_passed"],
            "negative_boolean_mixed_into_all": True,
            "historical_artifact_rewritten": False,
        },
        "public_evidence_integrity_gate_passed": True,
        "scientific_result_admission_authorized": False,
        "review_boundary": {
            "ledger_rows_changed": 0,
            "diagnostic_rows_excluded": 0,
            "terminal_rows_retried": 0,
            "provider_calls_made": 0,
            "scientific_outcomes_aggregated": False,
            "quality_gate_waived": False,
            "integrity_and_claim_quality_separated": True,
        },
        "artifact_locks": [
            _lock(paths["source_review"]),
            _lock(paths["candidate"]),
            _lock(paths["admission"]),
            _lock(paths["records"]),
            _lock(paths["attempts"]),
            _lock(paths["budget"]),
        ],
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_review(shard_index: int) -> dict[str, Any]:
    value = build_review(shard_index)
    _write_json(_paths(shard_index)["output"], value)
    return value


def verify_review(shard_index: int) -> dict[str, Any]:
    observed = _load_json(_paths(shard_index)["output"])
    expected = build_review(shard_index)
    if observed != expected:
        raise PublicSecondRecoveryEvidenceReviewV4Error(
            "Flash recovery evidence review drift"
        )
    return copy.deepcopy(observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--shard-index", type=int, required=True)
    args = parser.parse_args()
    value = (
        write_review(args.shard_index)
        if args.write
        else verify_review(args.shard_index)
    )
    print(
        json.dumps(
            {
                "status": value["status"],
                "shard_index": value["shard_index"],
                "evidence_integrity": value[
                    "public_evidence_integrity_gate_passed"
                ],
                "quality_passed": value["claim_quality"][
                    "frozen_one_percent_gate_passed"
                ],
                "manifest_sha256": value["manifest_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
