"""Separate public-shard evidence integrity from the frozen 1% quality gate.

The v3 shard reviewer intentionally treats a diagnostic fraction above one
percent as a technical-gate failure.  That remains the correct boundary for a
clean mechanism-quality claim.  It is not, however, an evidence-integrity
failure when every row is terminal, cross-bound, retained in the ITT
denominator, and classified as either ``formal_candidate`` or ``diagnostic``.

This deterministic reviewer consumes the already completed full replay.  It
does not touch ledgers, retry rows, inspect scientific outcomes, or waive the
one-percent gate.  It records whether the shard is usable only for the
predeclared empirical security--utility fallback.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.public_single_shard_recovery_v3 as recovery_v3
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "m3-paper-v2-public-shard-evidence-review-3.1"
REVIEWED_AT = "2026-07-30T06:06:00+08:00"
SOURCE_REVIEW_NAME = "continuation_shard_review_v3.json"
OUTPUT_NAME = "continuation_shard_evidence_review_v3_1.json"
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
        "v2_terminal_records_retried",
        "scientific_outcomes_aggregated",
    }
)


class PublicShardEvidenceReviewError(ValueError):
    """Raised when a source review has an integrity failure or drift."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicShardEvidenceReviewError(f"{path}: expected an object")
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
        raise PublicShardEvidenceReviewError(
            f"missing public shard artifact: {path}"
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
    candidate_path = recovery_v3.candidate_path(shard_index)
    candidate = _load_json(candidate_path)
    root = PROJECT_ROOT / candidate["scope"]["output_root"]
    return {
        "candidate": candidate_path,
        "admission": recovery_v3.admission_path(shard_index),
        "source_review": root / SOURCE_REVIEW_NAME,
        "output": root / OUTPUT_NAME,
        "records": root / "experiment_records.jsonl",
        "attempts": root / "attempt_events.jsonl",
        "budget": root / "budget_events.jsonl",
    }


def _validated_source(
    shard_index: int,
) -> tuple[dict[str, Any], dict[str, Path]]:
    paths = _paths(shard_index)
    source = _load_json(paths["source_review"])
    positives = source.get("positive_checks")
    negatives = source.get("negative_boundary_checks")
    expected_positive_names = INTEGRITY_POSITIVE_CHECKS | {QUALITY_CHECK}
    if (
        source.get("schema_version")
        != "m3-paper-v2-public-single-shard-technical-review-3.0"
        or source.get("manifest_sha256") != _manifest_sha(source)
        or source.get("shard_index") != shard_index
        or not isinstance(positives, Mapping)
        or set(positives) != expected_positive_names
        or not isinstance(negatives, Mapping)
        or set(negatives) != NEGATIVE_BOUNDARY_CHECKS
    ):
        raise PublicShardEvidenceReviewError(
            "public shard source review identity or schema drift"
        )
    if any(
        positives[name] is not True
        for name in INTEGRITY_POSITIVE_CHECKS
    ):
        raise PublicShardEvidenceReviewError(
            "public shard has a substantive evidence-integrity failure"
        )
    if any(negatives[name] is not False for name in NEGATIVE_BOUNDARY_CHECKS):
        raise PublicShardEvidenceReviewError(
            "public shard violates a negative evidence boundary"
        )
    quality_passed = positives[QUALITY_CHECK] is True
    expected_gate = quality_passed
    expected_status = (
        "public_recovery_shard_technical_gate_pass"
        if quality_passed
        else "public_recovery_shard_technical_gate_fail"
    )
    if (
        source.get("technical_gate_passed") is not expected_gate
        or source.get("status") != expected_status
    ):
        raise PublicShardEvidenceReviewError(
            "source technical-gate aggregate is inconsistent"
        )
    observed = source.get("observed_records")
    diagnostics = source.get("diagnostic_records")
    if (
        not isinstance(observed, int)
        or isinstance(observed, bool)
        or observed <= 0
        or not isinstance(diagnostics, int)
        or isinstance(diagnostics, bool)
        or diagnostics < 0
        or diagnostics > observed
    ):
        raise PublicShardEvidenceReviewError(
            "invalid source diagnostic counts"
        )
    return source, paths


def build_review(shard_index: int) -> dict[str, Any]:
    source, paths = _validated_source(shard_index)
    quality_passed = source["positive_checks"][QUALITY_CHECK]
    diagnostic_fraction = (
        source["diagnostic_records"] / source["observed_records"]
    )
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": (
            "typed_outcome_blind_public_shard_evidence_review"
        ),
        "reviewed_at": REVIEWED_AT,
        "status": "public_shard_evidence_integrity_pass",
        "shard_index": shard_index,
        "run_id": source["run_id"],
        "source_review_manifest_sha256": source["manifest_sha256"],
        "candidate_manifest_sha256": source[
            "candidate_manifest_sha256"
        ],
        "admission_file_sha256": source["admission_file_sha256"],
        "expected_records": source["expected_records"],
        "observed_records": source["observed_records"],
        "diagnostic_records": source["diagnostic_records"],
        "diagnostic_fraction": diagnostic_fraction,
        "maximum_admissible_diagnostic_records": source[
            "maximum_admissible_diagnostic_records"
        ],
        "provider_calls_completed": source["provider_calls_completed"],
        "role_cumulative_cost_cny": source[
            "role_cumulative_cost_cny"
        ],
        "record_ledger_tail_sha256": source[
            "record_ledger_tail_sha256"
        ],
        "attempt_ledger_tail_sha256": source[
            "attempt_ledger_tail_sha256"
        ],
        "budget_ledger_tail_sha256": source[
            "budget_ledger_tail_sha256"
        ],
        "integrity_positive_checks": {
            name: source["positive_checks"][name]
            for name in sorted(INTEGRITY_POSITIVE_CHECKS)
        },
        "negative_boundary_checks": {
            name: source["negative_boundary_checks"][name]
            for name in sorted(NEGATIVE_BOUNDARY_CHECKS)
        },
        "claim_quality": {
            "frozen_one_percent_gate_passed": quality_passed,
            "frozen_one_percent_gate_waived": False,
            "clean_mechanism_quality_claim_eligible": quality_passed,
            "empirical_security_utility_fallback_only": (
                not quality_passed
            ),
        },
        "public_evidence_integrity_gate_passed": True,
        "scientific_result_admission_authorized": False,
        "review_boundary": {
            "ledger_rows_changed": 0,
            "diagnostic_rows_excluded": 0,
            "terminal_rows_retried": 0,
            "provider_calls_made": 0,
            "scientific_outcomes_aggregated": False,
            "quality_gate_reclassified_as_integrity": False,
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
    path = _paths(shard_index)["output"]
    observed = _load_json(path)
    expected = build_review(shard_index)
    if observed != expected:
        raise PublicShardEvidenceReviewError(
            "public shard evidence review drift"
        )
    return copy.deepcopy(observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--shard-index", type=int, required=True)
    args = parser.parse_args()
    if args.shard_index not in range(4):
        parser.error("--shard-index must be one of 0, 1, 2, 3")
    value = (
        write_review(args.shard_index)
        if args.write
        else verify_review(args.shard_index)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
