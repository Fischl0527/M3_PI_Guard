"""针对已关闭诊断性意向治疗（ITT）分析的事后准入修正。

校正统计分母与配对差异区间，符合严格的临床级 ITT 原则。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_result_gate_v6 as gate_v6
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.medium_analysis_v4 import (
    analyze_medium_records_v4,
    project_closed_diagnostic_for_itt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/formal_analysis_amendment_v7.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_analysis_amendment_qualification_v7.json"
)
DEFAULT_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_analysis_amendment_candidate_v7.json"
)
DEFAULT_ANALYSIS = (
    gate_v6._review_paths()[0].parent / "admitted_medium_analysis_v7.json"
)
DEFAULT_V4_MODULE = PROJECT_ROOT / "experiments/paper_v2/medium_analysis_v4.py"
DEFAULT_V3_MODULE = PROJECT_ROOT / "experiments/paper_v2/medium_analysis_v3.py"

RUN_ID = "paper-v2-deepseek-medium-v8-v9-analysis-amendment-v7-20260726"
SCHEMA_VERSION = "m3-paper-v2-formal-analysis-amendment-7.0"


class FormalAnalysisAmendmentV7Error(RuntimeError):
    """当纯分析性修正案无法获得准入时抛出的异常。"""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalAnalysisAmendmentV7Error(f"{path}: expected an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        raise FormalAnalysisAmendmentV7Error(
            f"missing amendment input: {_display_path(path)}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    core = copy.deepcopy(dict(value))
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def _validate(
    value: Mapping[str, Any],
    *,
    expected_role: str,
) -> dict[str, Any]:
    Draft202012Validator(
        _read_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["artifact_role"] != expected_role:
        raise FormalAnalysisAmendmentV7Error(
            f"unexpected amendment role: {value['artifact_role']!r}"
        )
    observed = value["manifest_sha256"]
    expected = sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )
    if observed != expected:
        raise FormalAnalysisAmendmentV7Error(
            "analysis amendment manifest digest drift"
        )
    return copy.deepcopy(dict(value))


def _combined_records() -> list[dict[str, Any]]:
    return list(gate_v6._combined_state()["ordered_records"])


def build_qualification(
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if records is None:
        records = _combined_records()
    diagnostics = [row for row in records if row["result_tier"] == "diagnostic"]
    if len(records) != 480 or len(diagnostics) != 1:
        raise FormalAnalysisAmendmentV7Error(
            "amendment qualification requires 480 rows and one diagnostic"
        )
    diagnostic = diagnostics[0]
    projected = project_closed_diagnostic_for_itt(diagnostic)
    preserved_fields = (
        "case_id",
        "condition_id",
        "evaluation_case_type",
        "authorization_regime",
        "initial_guard_decision",
        "effective_decision",
        "unsafe_effect",
        "unsafe_effect_itt",
        "task_completion",
        "operational_status",
        "included_in_intention_to_treat",
        "latency_ms",
        "token_usage",
    )
    preservation_checks = {
        field: projected[field] == diagnostic[field]
        for field in preserved_fields
    }
    if not all(preservation_checks.values()):
        raise FormalAnalysisAmendmentV7Error(
            "diagnostic projection changed a scientific or operational field"
        )

    negative_rejections = 0
    for mutation in ("nonterminal", "itt_excluded", "automatic_retry"):
        invalid = copy.deepcopy(diagnostic)
        if mutation == "nonterminal":
            invalid["operational_status"] = "completed"
        elif mutation == "itt_excluded":
            invalid["included_in_intention_to_treat"] = False
        else:
            invalid["provider_trace_bundle"]["automatic_retry"] = True
        try:
            project_closed_diagnostic_for_itt(invalid)
        except Exception:
            negative_rejections += 1
        else:
            raise FormalAnalysisAmendmentV7Error(
                f"negative amendment fixture was accepted: {mutation}"
            )

    return _validate(
        _seal(
            {
                "schema_version": SCHEMA_VERSION,
                "artifact_role": "analysis_amendment_qualification",
                "status": "diagnostic_itt_projection_qualified",
                "run_id": RUN_ID,
                "record_count": 480,
                "formal_candidate_count": 479,
                "diagnostic_count": 1,
                "positive_projection_count": 1,
                "negative_rejection_count": negative_rejections,
                "field_preservation_checks": preservation_checks,
                "evidence_boundary": {
                    "network_calls_made": 0,
                    "provider_calls_made": 0,
                    "aggregate_statistics_computed": 0,
                    "execution_ledgers_mutated": False,
                    "v6_analysis_artifact_created": False,
                },
                "post_access_disclosure": {
                    "amendment_is_post_admission": True,
                    "trigger": (
                        "v6 projector rejected the admitted closed diagnostic "
                        "before aggregate statistics"
                    ),
                    "diagnostic_fields_inspected_for_debugging": True,
                    "aggregate_results_seen_before_freeze": False,
                    "analysis_method_scope": (
                        "evidence-envelope projection only; outcome fields "
                        "remain verbatim"
                    ),
                },
            }
        ),
        expected_role="analysis_amendment_qualification",
    )


def write_qualification(path: Path = DEFAULT_QUALIFICATION) -> dict[str, Any]:
    value = build_qualification()
    _write_json(path, value)
    return value


def verify_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    observed = _validate(
        _read_json(path),
        expected_role="analysis_amendment_qualification",
    )
    if observed != build_qualification():
        raise FormalAnalysisAmendmentV7Error(
            "analysis amendment qualification does not reproduce"
        )
    return observed


def build_candidate() -> dict[str, Any]:
    state = gate_v6._combined_state()
    records = list(state["ordered_records"])
    qualification = _validate(
        _read_json(DEFAULT_QUALIFICATION),
        expected_role="analysis_amendment_qualification",
    )
    if qualification != build_qualification(records):
        raise FormalAnalysisAmendmentV7Error(
            "analysis amendment qualification does not reproduce"
        )
    review_path = gate_v6._review_paths()[0]
    return _validate(
        _seal(
            {
                "schema_version": SCHEMA_VERSION,
                "artifact_role": "analysis_amendment_candidate",
                "status": "frozen_before_aggregate_analysis",
                "run_id": RUN_ID,
                "qualification_manifest_sha256": qualification[
                    "manifest_sha256"
                ],
                "locked_inputs": {
                    "analysis_v4": _lock(DEFAULT_V4_MODULE),
                    "analysis_v3": _lock(DEFAULT_V3_MODULE),
                    "gate_v6": _lock(Path(gate_v6.__file__)),
                    "gate_v6_admission": _lock(
                        gate_v6.DEFAULT_RESULT_ADMISSION
                    ),
                    "gate_v6_technical_review": _lock(review_path),
                    "case_manifest": _lock(gate_v6.DEFAULT_CASE_MANIFEST),
                    "case_index": _lock(gate_v6.DEFAULT_CASE_INDEX),
                    "gate_spec": _lock(gate_v6.DEFAULT_GATE_SPEC),
                    "source_record_ledger": _lock(
                        state[
                            "source_authorization"
                        ].permit.record_ledger_path
                    ),
                    "remainder_record_ledger": _lock(
                        state[
                            "remainder_authorization"
                        ].permit.record_ledger_path
                    ),
                },
                "planned_output": _display_path(DEFAULT_ANALYSIS),
                "analysis_policy": {
                    "all_480_records_retained_in_itt": True,
                    "closed_diagnostic_count": 1,
                    "diagnostic_outcomes_copied_verbatim": True,
                    "diagnostic_provider_response_attested": False,
                    "formal_candidate_projection_unchanged": True,
                    "bootstrap_iterations": 10000,
                    "no_api_or_execution_authorized": True,
                },
                "post_access_disclosure": copy.deepcopy(
                    qualification["post_access_disclosure"]
                ),
            }
        ),
        expected_role="analysis_amendment_candidate",
    )


def write_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    value = build_candidate()
    _write_json(path, value)
    return value


def verify_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    observed = _validate(
        _read_json(path),
        expected_role="analysis_amendment_candidate",
    )
    if observed != build_candidate():
        raise FormalAnalysisAmendmentV7Error(
            "analysis amendment candidate does not reproduce"
        )
    return observed


def build_analysis() -> dict[str, Any]:
    candidate = verify_candidate()
    admission = gate_v6.verify_result_admission()
    records = _combined_records()
    report = analyze_medium_records_v4(
        records,
        case_manifest=gate_v6._read_json(gate_v6.DEFAULT_CASE_MANIFEST),
        case_index=gate_v6._read_jsonl(gate_v6.DEFAULT_CASE_INDEX),
        gate_spec=gate_v6._read_json(gate_v6.DEFAULT_GATE_SPEC),
    )
    return {
        "schema_version": "m3-paper-v2-admitted-medium-analysis-7.0",
        "status": "complete",
        "run_id": RUN_ID,
        "analysis_amendment_candidate_sha256": candidate["manifest_sha256"],
        "result_admission_sha256": admission["manifest_sha256"],
        "post_access_disclosure": copy.deepcopy(
            candidate["post_access_disclosure"]
        ),
        "analysis": report,
    }


def write_analysis(path: Path = DEFAULT_ANALYSIS) -> dict[str, Any]:
    value = build_analysis()
    _write_json(path, value)
    return value


def verify_analysis(path: Path = DEFAULT_ANALYSIS) -> dict[str, Any]:
    observed = _read_json(path)
    if observed != build_analysis():
        raise FormalAnalysisAmendmentV7Error(
            "amended medium analysis does not reproduce"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-analysis", action="store_true")
    action.add_argument("--verify-analysis", action="store_true")
    args = parser.parse_args()
    if args.write_qualification:
        value = write_qualification()
    elif args.verify_qualification:
        value = verify_qualification()
    elif args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    elif args.write_analysis:
        value = write_analysis()
    else:
        value = verify_analysis()
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
