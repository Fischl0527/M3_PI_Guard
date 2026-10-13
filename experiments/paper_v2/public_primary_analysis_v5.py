"""通过已验证的 v1 统计分析引擎分析公开主要证据。

调用经过严格数学审计的纯净统计例程生成可复现的论文终稿表格。
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.public_primary_analysis_v1 as base
import experiments.paper_v2.public_primary_analysis_validation_correction_v2 as correction_v2
import experiments.paper_v2.public_primary_analysis_validation_correction_v3 as correction_v3
import experiments.paper_v2.public_primary_analysis_validation_correction_v4 as correction_v4
import experiments.paper_v2.public_primary_analysis_validation_correction_v5 as correction
import experiments.paper_v2.public_primary_analysis_v4 as analysis_v4
from experiments.paper_v2.contracts import (
    EXPERIMENT_RECORD_SCHEMA_VERSION,
    canonical_json_bytes,
    sha256_canonical_json,
    validate_experiment_record,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = correction.ANALYSIS_OUTPUT_ROOT
SUMMARY_NAME = "public_primary_analysis_summary_v5.json"
CONDITION_CSV_NAME = "public_primary_condition_summary_v5.csv"
SCHEMA_VERSION = "m3-paper-v2-public-primary-analysis-5.0"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise base.PublicPrimaryAnalysisError(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _project_record_for_statistics(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    analysis_v4._validate_analysis_record(record)
    bundle = record["provider_trace_bundle"]
    diagnostic = record["result_tier"] == "diagnostic"
    attestations = bundle["activated_attestations"]
    last = attestations[-1] if attestations else None
    if not diagnostic and last is None:
        raise base.PublicPrimaryAnalysisError(
            "formal Public record lacks an activated provider response"
        )
    excluded = {"provider_trace_bundle", "provider_safety_receipt"}
    projected = {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key not in excluded
    }
    projected["schema_version"] = EXPERIMENT_RECORD_SCHEMA_VERSION
    projected["provider_attestation"] = {
        "endpoint_type": "official_api",
        "provider_name": "DeepSeek",
        "upstream_provider": "DeepSeek",
        "model_id": bundle["model_id"],
        "model_revision": "provider_managed",
        "request_id": (
            str(last["client_request_id"])
            if last is not None
            else f"diagnostic-bundle:{bundle['bundle_sha256']}"
        ),
        "response_id": (
            str(last["provider_response_id"])
            if last is not None
            else None
        ),
        "requested_at": record["recorded_at"],
        "parameters_sha256": bundle["trace_rows_sha256"],
        "prompt_rewrite_declaration": "none_declared",
        "identity_evidence": (
            "unverified" if diagnostic else "official_response"
        ),
        "identity_verified": not diagnostic,
        "evidence_level": (
            "diagnostic_only" if diagnostic else "formal_candidate"
        ),
    }
    validate_experiment_record(projected)
    return projected


def _configure(
    correction_admission: Mapping[str, Any],
) -> None:
    base.validate_experiment_record = analysis_v4._validate_analysis_record
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    base.SUMMARY_NAME = SUMMARY_NAME
    base.CONDITION_CSV_NAME = CONDITION_CSV_NAME
    base.SCHEMA_VERSION = SCHEMA_VERSION
    if getattr(base, "_m3_statistics_projection_v5", False):
        return
    legacy_analyze = base.analyze_medium_records
    original_report = base._analysis_report

    def projected_analyze(
        records: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return legacy_analyze(
            [_project_record_for_statistics(row) for row in records],
            **kwargs,
        )

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
        core["prior_failed_correction_admission_sha256es"] = [
            _load_json(path)["manifest_sha256"]
            for path in (
                correction_v2.ADMISSION_PATH,
                correction_v3.ADMISSION_PATH,
                correction_v4.ADMISSION_PATH,
            )
        ]
        core["statistics_envelope_projection"] = {
            "source_schema": "m3-paper-v2-experiment-record-2.2",
            "helper_schema": "m3-paper-v2-experiment-record-1.0",
            "outcome_fields_copied_verbatim": True,
            "diagnostic_identity_verified": False,
            "diagnostic_records_excluded": 0,
        }
        return {
            **core,
            "manifest_sha256": sha256_canonical_json(core),
        }, rows

    base.analyze_medium_records = projected_analyze
    base._analysis_report = corrected_report
    base._m3_statistics_projection_v5 = True


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
    manifest_core["statistics_envelope_projection"] = True
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
        or manifest.get("statistics_envelope_projection") is not True
    ):
        raise base.PublicPrimaryAnalysisError(
            "statistics-envelope projection provenance drift"
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
