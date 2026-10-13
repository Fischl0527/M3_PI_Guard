"""独立审查具备投影安全保障的公开主分析结果（版本 V4）。

确保所有投影到运行时的输入数据均不存在先验真值泄露。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import experiments.paper_v2.public_primary_analysis_review_v1 as base
import experiments.paper_v2.public_primary_analysis_validation_correction_v4 as correction
import experiments.paper_v2.public_primary_analysis_v4 as analysis_v4
from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    analysis_v4.DEFAULT_OUTPUT / "independent_analysis_review_v4.json"
)
SCHEMA_VERSION = "m3-paper-v2-public-primary-analysis-review-4.0"
REVIEWED_AT = "2026-07-30T09:55:00+08:00"


def _configure() -> dict[str, Any]:
    admitted = correction.validate_admission(
        correction._load_json(correction.ADMISSION_PATH)
    )
    base.validate_experiment_record = analysis_v4._validate_analysis_record
    base.ANALYSIS_ROOT = analysis_v4.DEFAULT_OUTPUT
    base.SUMMARY_PATH = base.ANALYSIS_ROOT / analysis_v4.SUMMARY_NAME
    base.CONDITION_CSV_PATH = (
        base.ANALYSIS_ROOT / analysis_v4.CONDITION_CSV_NAME
    )
    base.ANALYSIS_MANIFEST_PATH = (
        base.ANALYSIS_ROOT / base.ANALYSIS_MANIFEST_PATH.name
    )
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    base.SCHEMA_VERSION = SCHEMA_VERSION
    base.REVIEWED_AT = REVIEWED_AT
    base.__file__ = str(Path(__file__).resolve())
    if getattr(base, "_m3_projection_safe_review_v4", False):
        return admitted
    original_build_review = base.build_review

    def corrected_build_review() -> dict[str, Any]:
        value = original_build_review()
        core = {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
        core["analysis_validation_correction_admission_sha256"] = (
            admitted["manifest_sha256"]
        )
        core["provider_chain_integrity_inherited_from_locked_merge"] = True
        return {
            **core,
            "manifest_sha256": sha256_canonical_json(core),
        }

    base.build_review = corrected_build_review
    base._m3_projection_safe_review_v4 = True
    return admitted


def write_review() -> dict[str, Any]:
    _configure()
    return base.write_review(DEFAULT_OUTPUT)


def verify_review() -> dict[str, Any]:
    admitted = _configure()
    value = base.verify_review(DEFAULT_OUTPUT)
    if (
        value.get("analysis_validation_correction_admission_sha256")
        != admitted["manifest_sha256"]
        or value.get(
            "provider_chain_integrity_inherited_from_locked_merge"
        )
        is not True
    ):
        raise base.PublicPrimaryAnalysisReviewError(
            "independent projection-safe review provenance drift"
        )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = write_review() if args.write else verify_review()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
