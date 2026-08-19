"""Independently review the Public-family-validator analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import experiments.paper_v2.public_primary_analysis_review_v1 as base
import experiments.paper_v2.public_primary_analysis_validation_correction_v3 as correction
import experiments.paper_v2.public_primary_analysis_v3 as analysis_v3
from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    analysis_v3.DEFAULT_OUTPUT / "independent_analysis_review_v3.json"
)
SCHEMA_VERSION = "m3-paper-v2-public-primary-analysis-review-3.0"
REVIEWED_AT = "2026-07-30T08:35:00+08:00"


def _configure() -> dict[str, Any]:
    admitted = correction.validate_admission(
        correction._load_json(correction.ADMISSION_PATH)
    )
    base.validate_experiment_record = analysis_v3._validate_public_record
    base.ANALYSIS_ROOT = analysis_v3.DEFAULT_OUTPUT
    base.SUMMARY_PATH = base.ANALYSIS_ROOT / analysis_v3.SUMMARY_NAME
    base.CONDITION_CSV_PATH = (
        base.ANALYSIS_ROOT / analysis_v3.CONDITION_CSV_NAME
    )
    base.ANALYSIS_MANIFEST_PATH = (
        base.ANALYSIS_ROOT / base.ANALYSIS_MANIFEST_PATH.name
    )
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    base.SCHEMA_VERSION = SCHEMA_VERSION
    base.REVIEWED_AT = REVIEWED_AT
    base.__file__ = str(Path(__file__).resolve())
    if getattr(base, "_m3_public_validator_review_v3", False):
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
        return {
            **core,
            "manifest_sha256": sha256_canonical_json(core),
        }

    base.build_review = corrected_build_review
    base._m3_public_validator_review_v3 = True
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
    ):
        raise base.PublicPrimaryAnalysisReviewError(
            "independent Public validator correction admission drift"
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
