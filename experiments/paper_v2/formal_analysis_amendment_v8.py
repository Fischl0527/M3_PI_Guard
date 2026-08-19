"""Schema-valid post-admission analysis amendment.

The frozen v7 amendment failed before aggregate statistics because its
diagnostic compatibility record included a disclosure field that the closed
v1 schema forbids.  Version 8 moves that disclosure to report level, uses the
schema's diagnostic-only identity vocabulary, and binds provider eligibility
to the already-passed v6 technical gate.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_analysis_amendment_v7 as amendment_v7
import experiments.paper_v2.formal_result_gate_v6 as gate_v6
from experiments.paper_v2.contracts import (
    sha256_canonical_json,
    validate_experiment_record,
)
from experiments.paper_v2.medium_analysis_v5 import (
    analyze_medium_records_v5,
    project_closed_diagnostic_for_itt_v5,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/formal_analysis_amendment_v8.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_analysis_amendment_qualification_v8.json"
)
DEFAULT_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_analysis_amendment_candidate_v8.json"
)
DEFAULT_ANALYSIS = (
    gate_v6._review_paths()[0].parent / "admitted_medium_analysis_v8.json"
)
DEFAULT_V5_MODULE = PROJECT_ROOT / "experiments/paper_v2/medium_analysis_v5.py"

RUN_ID = "paper-v2-deepseek-medium-v8-v9-analysis-amendment-v8-20260726"
SCHEMA_VERSION = "m3-paper-v2-formal-analysis-amendment-8.0"


class FormalAnalysisAmendmentV8Error(RuntimeError):
    """Raised when the schema-valid amendment cannot be admitted."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalAnalysisAmendmentV8Error(f"{path}: expected an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        raise FormalAnalysisAmendmentV8Error(
            f"unexpected amendment role: {value['artifact_role']!r}"
        )
    expected = sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )
    if value["manifest_sha256"] != expected:
        raise FormalAnalysisAmendmentV8Error(
            "analysis amendment v8 manifest digest drift"
        )
    return copy.deepcopy(dict(value))


def build_qualification(
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if records is None:
        records = list(gate_v6._combined_state()["ordered_records"])
    diagnostics = [row for row in records if row["result_tier"] == "diagnostic"]
    if len(records) != 480 or len(diagnostics) != 1:
        raise FormalAnalysisAmendmentV8Error(
            "v8 qualification requires 480 rows and one diagnostic"
        )
    diagnostic = diagnostics[0]
    projected = project_closed_diagnostic_for_itt_v5(diagnostic)
    validate_experiment_record(projected)
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
        raise FormalAnalysisAmendmentV8Error(
            "v8 projection changed a scientific or operational field"
        )
    identity = projected["provider_attestation"]
    identity_checks = {
        "response_id_is_null": identity["response_id"] is None,
        "identity_is_unverified": identity["identity_verified"] is False,
        "identity_evidence_is_unverified": (
            identity["identity_evidence"] == "unverified"
        ),
        "evidence_level_is_diagnostic_only": (
            identity["evidence_level"] == "diagnostic_only"
        ),
    }
    if not all(identity_checks.values()):
        raise FormalAnalysisAmendmentV8Error(
            "v8 projection overstates diagnostic response evidence"
        )
    negative_rejections = 0
    for field, value in (
        ("operational_status", "completed"),
        ("included_in_intention_to_treat", False),
    ):
        invalid = copy.deepcopy(diagnostic)
        invalid[field] = value
        try:
            project_closed_diagnostic_for_itt_v5(invalid)
        except Exception:
            negative_rejections += 1
        else:
            raise FormalAnalysisAmendmentV8Error(
                f"v8 negative fixture was accepted: {field}"
            )
    return _validate(
        _seal(
            {
                "schema_version": SCHEMA_VERSION,
                "artifact_role": "analysis_amendment_qualification",
                "status": "schema_valid_diagnostic_itt_projection_qualified",
                "run_id": RUN_ID,
                "record_count": 480,
                "formal_candidate_count": 479,
                "diagnostic_count": 1,
                "positive_schema_validation_count": 1,
                "negative_rejection_count": negative_rejections,
                "field_preservation_checks": preservation_checks,
                "diagnostic_identity_checks": identity_checks,
                "evidence_boundary": {
                    "network_calls_made": 0,
                    "provider_calls_made": 0,
                    "aggregate_statistics_computed": 0,
                    "execution_ledgers_mutated": False,
                    "v7_analysis_artifact_created": False,
                },
                "post_access_disclosure": {
                    "amendment_is_post_admission": True,
                    "aggregate_results_seen_before_freeze": False,
                    "failed_v6_and_v7_aggregate_artifacts_created": 0,
                    "diagnostic_fields_inspected_for_debugging": True,
                    "method_change": (
                        "schema-valid diagnostic-only identity projection and "
                        "report-level no-response disclosure"
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
        raise FormalAnalysisAmendmentV8Error(
            "analysis amendment v8 qualification does not reproduce"
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
        raise FormalAnalysisAmendmentV8Error(
            "analysis amendment v8 qualification does not reproduce"
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
                    "amendment_v8": amendment_v7._lock(Path(__file__)),
                    "amendment_v8_schema": amendment_v7._lock(DEFAULT_SCHEMA),
                    "analysis_v5": amendment_v7._lock(DEFAULT_V5_MODULE),
                    "analysis_v4": amendment_v7._lock(
                        amendment_v7.DEFAULT_V4_MODULE
                    ),
                    "failed_amendment_v7_candidate": amendment_v7._lock(
                        amendment_v7.DEFAULT_CANDIDATE
                    ),
                    "gate_v6": amendment_v7._lock(Path(gate_v6.__file__)),
                    "gate_v6_admission": amendment_v7._lock(
                        gate_v6.DEFAULT_RESULT_ADMISSION
                    ),
                    "gate_v6_technical_review": amendment_v7._lock(
                        review_path
                    ),
                    "case_manifest": amendment_v7._lock(
                        gate_v6.DEFAULT_CASE_MANIFEST
                    ),
                    "case_index": amendment_v7._lock(
                        gate_v6.DEFAULT_CASE_INDEX
                    ),
                    "gate_spec": amendment_v7._lock(
                        gate_v6.DEFAULT_GATE_SPEC
                    ),
                    "source_record_ledger": amendment_v7._lock(
                        state[
                            "source_authorization"
                        ].permit.record_ledger_path
                    ),
                    "remainder_record_ledger": amendment_v7._lock(
                        state[
                            "remainder_authorization"
                        ].permit.record_ledger_path
                    ),
                },
                "planned_output": amendment_v7._display_path(
                    DEFAULT_ANALYSIS
                ),
                "analysis_policy": {
                    "all_480_records_retained_in_itt": True,
                    "diagnostic_outcomes_copied_verbatim": True,
                    "diagnostic_response_identity_unverified": True,
                    "formal_response_identity_from_v6_gate": True,
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
        raise FormalAnalysisAmendmentV8Error(
            "analysis amendment v8 candidate does not reproduce"
        )
    return observed


def verify_candidate_single_pass(
    path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    """Verify the frozen amendment without recomputing aggregate inputs."""

    observed = _validate(
        _read_json(path),
        expected_role="analysis_amendment_candidate",
    )
    qualification = _validate(
        _read_json(DEFAULT_QUALIFICATION),
        expected_role="analysis_amendment_qualification",
    )
    if (
        observed["qualification_manifest_sha256"]
        != qualification["manifest_sha256"]
    ):
        raise FormalAnalysisAmendmentV8Error(
            "v8 candidate qualification binding drift"
        )
    for name, expected in observed["locked_inputs"].items():
        current = amendment_v7._lock(PROJECT_ROOT / expected["path"])
        if current != expected:
            raise FormalAnalysisAmendmentV8Error(
                f"v8 candidate locked input drift: {name}"
            )
    if observed["planned_output"] != amendment_v7._display_path(
        DEFAULT_ANALYSIS
    ):
        raise FormalAnalysisAmendmentV8Error(
            "v8 candidate planned output drift"
        )
    return observed


def build_analysis() -> dict[str, Any]:
    candidate = verify_candidate_single_pass()
    admission = gate_v6._validate_artifact(
        gate_v6._read_json(gate_v6.DEFAULT_RESULT_ADMISSION),
        expected_role="formal_result_analysis_admission",
    )
    if admission["status"] != "activated_for_scientific_analysis":
        raise FormalAnalysisAmendmentV8Error(
            "v6 scientific analysis admission is not active"
        )
    state = gate_v6._combined_state()
    review = gate_v6._validate_artifact(
        gate_v6._read_json(gate_v6._review_paths()[0]),
        expected_role="formal_result_technical_review",
    )
    identity_policy = bool(
        review["status"] == "technical_result_gate_pass"
        and review["operational_gate"]["result_admission_eligible"] is True
        and review["operational_gate"]["checks"]["formal_exact_identity_chain"]
        is True
    )
    report = analyze_medium_records_v5(
        list(state["ordered_records"]),
        case_manifest=gate_v6._read_json(gate_v6.DEFAULT_CASE_MANIFEST),
        case_index=gate_v6._read_jsonl(gate_v6.DEFAULT_CASE_INDEX),
        gate_spec=gate_v6._read_json(gate_v6.DEFAULT_GATE_SPEC),
        technical_identity_policy_satisfied=identity_policy,
    )
    return {
        "schema_version": "m3-paper-v2-admitted-medium-analysis-8.0",
        "status": "complete",
        "run_id": RUN_ID,
        "analysis_amendment_candidate_sha256": candidate["manifest_sha256"],
        "result_admission_sha256": admission["manifest_sha256"],
        "technical_review_sha256": amendment_v7._sha256_file(
            gate_v6._review_paths()[0]
        ),
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
        raise FormalAnalysisAmendmentV8Error(
            "amended medium analysis v8 does not reproduce"
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
