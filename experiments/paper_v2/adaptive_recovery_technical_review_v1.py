"""修正自适应 V3 技术审查布尔值标记（在不篡改底层证据的前提下）。

规范技术复核元数据字段，使其与全局审计验证规范完全对齐。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.adaptive_cost_canary_recovery_v3 as recovery_v3
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_REVIEW = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary"
    / recovery_v3.TECHNICAL_REVIEW_NAME
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary"
    / "technical_cost_review_v3_1.json"
)
SCHEMA_VERSION = "m3-paper-v2-adaptive-technical-review-3.1"
REVIEWED_AT = "2026-07-30T02:58:00+08:00"
POSITIVE_CHECKS = frozenset(
    {
        "all_queries_terminal",
        "all_eight_tasks_terminal",
        "all_checkpoint_dual_hash_bindings_verified",
        "query_call_cross_binding_complete",
        "budget_event_count_matches_provider_calls",
        "budget_not_paused",
        "hard_cost_limit_respected",
        "diagnostic_fraction_within_frozen_bound",
    }
)
NEGATIVE_CHECKS = frozenset(
    {
        "scientific_outcomes_aggregated",
        "v2_terminal_queries_retried",
    }
)


class AdaptiveRecoveryTechnicalReviewError(ValueError):
    """当源审查结果不符合精确的纯布尔缺陷规范时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdaptiveRecoveryTechnicalReviewError(
            f"{path}: expected an object"
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
        raise AdaptiveRecoveryTechnicalReviewError(
            f"missing adaptive review artifact: {path}"
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


def _validated_source() -> dict[str, Any]:
    source = _load_json(SOURCE_REVIEW)
    if (
        source.get("schema_version")
        != "m3-paper-v2-adaptive-technical-review-3.0"
        or source.get("manifest_sha256") != _manifest_sha(source)
        or source.get("technical_gate_passed") is not False
        or source.get("status")
        != "adaptive_recovery_technical_gate_fail"
    ):
        raise AdaptiveRecoveryTechnicalReviewError(
            "adaptive source review is not the frozen false aggregate"
        )
    checks = source.get("checks")
    if (
        not isinstance(checks, Mapping)
        or set(checks) != POSITIVE_CHECKS | NEGATIVE_CHECKS
        or any(checks[key] is not True for key in POSITIVE_CHECKS)
        or any(checks[key] is not False for key in NEGATIVE_CHECKS)
    ):
        raise AdaptiveRecoveryTechnicalReviewError(
            "adaptive source review has a substantive failed check"
        )
    return source


def build_review() -> dict[str, Any]:
    source = _validated_source()
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "typed_outcome_blind_adaptive_technical_review",
        "reviewed_at": REVIEWED_AT,
        "status": "adaptive_recovery_technical_gate_pass",
        "source_review_manifest_sha256": source["manifest_sha256"],
        "run_id": source["run_id"],
        "execution_identity": source["execution_identity"],
        "candidate_manifest_sha256": source[
            "candidate_manifest_sha256"
        ],
        "admission_file_sha256": source["admission_file_sha256"],
        "terminal_query_count": source["terminal_query_count"],
        "completed_provider_call_count": source[
            "completed_provider_call_count"
        ],
        "diagnostic_query_count": source["diagnostic_query_count"],
        "maximum_admissible_diagnostic_queries": source[
            "maximum_admissible_diagnostic_queries"
        ],
        "terminal_task_count": source["terminal_task_count"],
        "expected_task_count": source["expected_task_count"],
        "cumulative_cost_cny": source["cumulative_cost_cny"],
        "hard_limit_cny": source["hard_limit_cny"],
        "query_ledger_tail_sha256": source[
            "query_ledger_tail_sha256"
        ],
        "budget_ledger_tail_sha256": source[
            "budget_ledger_tail_sha256"
        ],
        "task_ledger_tail_sha256": source[
            "task_ledger_tail_sha256"
        ],
        "positive_checks": {
            key: source["checks"][key] for key in sorted(POSITIVE_CHECKS)
        },
        "negative_boundary_checks": {
            key: source["checks"][key] for key in sorted(NEGATIVE_CHECKS)
        },
        "technical_gate_passed": True,
        "scientific_result_admission_authorized": False,
        "correction_scope": {
            "evidence_rows_changed": 0,
            "ledger_rows_changed": 0,
            "checkpoint_rows_changed": 0,
            "provider_calls_made": 0,
            "scientific_outcomes_aggregated": False,
            "only_boolean_aggregation_semantics_corrected": True,
        },
        "artifact_locks": [
            _lock(SOURCE_REVIEW),
            _lock(recovery_v3.CANDIDATE_PATH),
            _lock(recovery_v3.ADMISSION_PATH),
            _lock(
                PROJECT_ROOT
                / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2"
                / "primary/query_ledger.jsonl"
            ),
            _lock(
                PROJECT_ROOT
                / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2"
                / "primary/provider_budget_ledger.jsonl"
            ),
            _lock(
                PROJECT_ROOT
                / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2"
                / "primary/continuation_task_events_v3.jsonl"
            ),
        ],
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_review()
    _write_json(path, value)
    return value


def verify_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_review()
    if observed != expected:
        raise AdaptiveRecoveryTechnicalReviewError(
            "adaptive typed technical review drift"
        )
    return copy.deepcopy(observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write == args.verify:
        parser.error("choose exactly one of --write or --verify")
    value = write_review() if args.write else verify_review()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
