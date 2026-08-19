"""Run the admitted Public primary analysis with v2.2 record validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.public_primary_analysis_v1 as base
import experiments.paper_v2.public_primary_analysis_validation_correction_v2 as correction
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.contracts_v2 import validate_experiment_record_v2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = correction.ANALYSIS_OUTPUT_ROOT
SUMMARY_NAME = "public_primary_analysis_summary_v2.json"
CONDITION_CSV_NAME = "public_primary_condition_summary_v2.csv"
SCHEMA_VERSION = "m3-paper-v2-public-primary-analysis-2.0"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise base.PublicPrimaryAnalysisError(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _configure(
    correction_admission: Mapping[str, Any],
) -> None:
    base.validate_experiment_record = validate_experiment_record_v2
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    base.SUMMARY_NAME = SUMMARY_NAME
    base.CONDITION_CSV_NAME = CONDITION_CSV_NAME
    base.SCHEMA_VERSION = SCHEMA_VERSION
    if getattr(base, "_m3_validator_correction_v2", False):
        return
    original_report = base._analysis_report

    def corrected_report(*args: Any, **kwargs: Any) -> Any:
        summary, rows = original_report(*args, **kwargs)
        core = {
            key: child
            for key, child in summary.items()
            if key != "manifest_sha256"
        }
        core["analysis_validation_correction_admission_sha256"] = (
            correction_admission["manifest_sha256"]
        )
        return {
            **core,
            "manifest_sha256": sha256_canonical_json(core),
        }, rows

    base._analysis_report = corrected_report
    base._m3_validator_correction_v2 = True


def analyze(
    *,
    correction_admission_path: Path,
    output_root: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    admitted = correction.validate_admission(
        _load_json(correction_admission_path)
    )
    _configure(admitted)
    manifest = base.analyze(
        admission_path=base.admission_v1.ADMISSION_PATH,
        output_root=output_root,
    )
    manifest_core = {
        key: child
        for key, child in manifest.items()
        if key != "manifest_sha256"
    }
    manifest_core[
        "analysis_validation_correction_admission_sha256"
    ] = admitted["manifest_sha256"]
    corrected_manifest = {
        **manifest_core,
        "manifest_sha256": sha256_canonical_json(manifest_core),
    }
    _write_json(output_root / base.MANIFEST_NAME, corrected_manifest)
    return corrected_manifest


def verify_analysis(
    *,
    correction_admission_path: Path,
    output_root: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    admitted = correction.validate_admission(
        _load_json(correction_admission_path)
    )
    _configure(admitted)
    manifest = base.verify_analysis(
        admission_path=base.admission_v1.ADMISSION_PATH,
        output_root=output_root,
    )
    if (
        manifest.get(
            "analysis_validation_correction_admission_sha256"
        )
        != admitted["manifest_sha256"]
    ):
        raise base.PublicPrimaryAnalysisError(
            "analysis validator correction admission drift"
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--analyze", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    admission_path = (
        args.admission
        if args.admission.is_absolute()
        else PROJECT_ROOT / args.admission
    )
    output_root = (
        args.output_root
        if args.output_root.is_absolute()
        else PROJECT_ROOT / args.output_root
    )
    value = (
        analyze(
            correction_admission_path=admission_path,
            output_root=output_root,
        )
        if args.analyze
        else verify_analysis(
            correction_admission_path=admission_path,
            output_root=output_root,
        )
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
