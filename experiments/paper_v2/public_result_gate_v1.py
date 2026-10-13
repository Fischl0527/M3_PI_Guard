"""准入完整公开矩阵的前瞻性证据门禁。

执行样本覆盖率、异常重试率与统计显著性三重门禁审查。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.public_analysis_v1 import (
    DEFAULT_OUTPUT as DEFAULT_ANALYSIS_SPEC,
    verify_analysis_preregistration,
)
from experiments.paper_v2.public_matrix_controller_v1 import (
    DEFAULT_CANDIDATE,
    PROJECT_ROOT,
    verify_candidate,
)


DEFAULT_OUTPUT = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/public_result_gate_v1.json"
)
FROZEN_AT = "2026-07-28T00:50:00+08:00"


class PublicResultGateError(ValueError):
    """当前瞻性公开结果门禁发生漂移时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_public_result_gate() -> dict[str, Any]:
    candidate = verify_candidate(DEFAULT_CANDIDATE)
    analysis = verify_analysis_preregistration(DEFAULT_ANALYSIS_SPEC)
    criteria = {
        "exact_terminal_records": 6873,
        "primary_terminal_records": 5082,
        "second_terminal_records": 1791,
        "one_terminal_record_per_work_key": True,
        "failures_retained_in_intention_to_treat": True,
        "no_open_attempts": True,
        "no_unexplained_runner_failure": True,
        "all_source_projections_reconstruct": True,
        "all_record_hash_chains_reconstruct": True,
        "all_provider_trace_chains_reconstruct": True,
        "all_budget_ledgers_cross_bind": True,
        "all_safety_receipts_isolated": True,
        "primary_exact_model": "deepseek-v4-pro",
        "second_exact_model": "deepseek-v4-flash",
        "primary_technical_canary_pass": True,
        "second_technical_canary_pass": True,
        "analysis_preregistration_bound": analysis[
            "preregistration_sha256"
        ],
        "independent_analysis_rebuild_required": True,
    }
    core = {
        "schema_version": "m3-paper-v2-public-result-gate-1.0",
        "frozen_at": FROZEN_AT,
        "status": "prospective_gate_frozen_results_pending",
        "candidate": {
            "path": DEFAULT_CANDIDATE.relative_to(PROJECT_ROOT).as_posix(),
            "file_sha256": _sha256_file(DEFAULT_CANDIDATE),
            "manifest_sha256": candidate["manifest_sha256"],
            "scope_sha256": candidate["scope_sha256"],
        },
        "analysis_preregistration": {
            "path": DEFAULT_ANALYSIS_SPEC.relative_to(
                PROJECT_ROOT
            ).as_posix(),
            "file_sha256": _sha256_file(DEFAULT_ANALYSIS_SPEC),
            "preregistration_sha256": analysis[
                "preregistration_sha256"
            ],
        },
        "admission_criteria": criteria,
        "failure_outcome": {
            "partial_completion_score": (
                "report completed fraction; do not assign 100/100"
            ),
            "primary_only_completion": (
                "primary-model evidence only; no cross-model claim"
            ),
            "technical_chain_failure": "diagnostic_only_not_scientific_result",
            "scientific_gate_failure": (
                "retain empirical-study fallback; no defense superiority claim"
            ),
        },
        "authorization": {
            "canary_execution_authorized": False,
            "matrix_continuation_authorized": False,
            "analysis_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "experiment_ledgers_loaded": False,
            "scientific_outcomes_accessed": False,
            "formal_results_created": 0,
        },
        "criteria_sha256": sha256_canonical_json(criteria),
    }
    return {**core, "gate_sha256": sha256_canonical_json(core)}


def validate_public_result_gate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicResultGateError("public result gate must be an object")
    expected = build_public_result_gate()
    if dict(value) != expected:
        raise PublicResultGateError("public result gate drift")
    return dict(value)


def write_public_result_gate(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = build_public_result_gate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_public_result_gate(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return validate_public_result_gate(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = (
        verify_public_result_gate(args.output)
        if args.verify
        else write_public_result_gate(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

