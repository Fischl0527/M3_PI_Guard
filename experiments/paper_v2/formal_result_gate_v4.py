"""Prospective technical result gate for the DeepSeek v7 medium matrix.

Version 4 freezes its operational policy and v7 boundary-evidence consumers
before the first v7 API call.  The final gate candidate can only be written
after a passing six-condition technical canary review, while scientific
outcomes remain closed.
"""

from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v7 as matrix
import experiments.paper_v2.formal_result_gate_v2 as base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_result_gate_v4.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_result_gate_qualification_v4.json"
)
DEFAULT_GATE_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_result_gate_candidate_v4.json"
)
DEFAULT_RESULT_ADMISSION = (
    PROTOCOL_ROOT / "admissions/deepseek_medium_result_admission_v4.json"
)
DEFAULT_MATRIX_CANDIDATE = matrix.DEFAULT_CANDIDATE
DEFAULT_CONTINUATION_ADMISSION = matrix.DEFAULT_CONTINUATION_ADMISSION
DEFAULT_CASE_MANIFEST = base.DEFAULT_CASE_MANIFEST
DEFAULT_CASE_INDEX = base.DEFAULT_CASE_INDEX
DEFAULT_GATE_SPEC = base.DEFAULT_GATE_SPEC
DEFAULT_BUDGET_AUTHORIZATION = base.DEFAULT_BUDGET_AUTHORIZATION
DEFAULT_ANALYSIS_MODULE = base.DEFAULT_ANALYSIS_MODULE

RUN_ID = matrix.RUN_ID
SCHEMA_VERSION = "m3-paper-v2-formal-result-gate-4.0"
EXPECTED_RECORDS = base.EXPECTED_RECORDS
OWNER_APPROVAL_STATEMENT_SHA256 = matrix.OWNER_STATEMENT_SHA256

evaluate_operational_gate = base.evaluate_operational_gate
_fixture_record = base._fixture_record


class FormalResultGateV4Error(RuntimeError):
    """Raised when v7 evidence cannot cross the prospective result gate."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalResultGateV4Error(f"{path}: expected a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    base._write_json(path, value)


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    return base._seal(value)


def _display_path(path: Path) -> str:
    return base._display_path(path)


def _artifact_lock(path: Path) -> dict[str, Any]:
    return base._artifact_lock(path)


def _validate_artifact(
    value: Mapping[str, Any],
    *,
    expected_role: str,
) -> dict[str, Any]:
    Draft202012Validator(
        _read_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(value)
    if value.get("artifact_role") != expected_role:
        raise FormalResultGateV4Error(
            f"expected artifact role {expected_role!r}"
        )
    if value.get("manifest_sha256") != base._manifest_sha(value):
        raise FormalResultGateV4Error("formal result artifact digest drift")
    return copy.deepcopy(dict(value))


def _append_lock(items: list[dict[str, Any]], path: Path) -> None:
    display = _display_path(path)
    if any(item["path"] == display for item in items):
        return
    items.append(_artifact_lock(path))


def _precanary_lock_paths() -> tuple[Path, ...]:
    return (
        Path(__file__),
        DEFAULT_SCHEMA,
        PROJECT_ROOT
        / "experiments/paper_v2/formal_matrix_controller_v7.py",
        PROJECT_ROOT
        / "experiments/paper_v2/boundary_rejection_runtime_v3.py",
        DEFAULT_MATRIX_CANDIDATE,
        matrix.DEFAULT_CANARY_ADMISSION,
        DEFAULT_GATE_SPEC,
        DEFAULT_ANALYSIS_MODULE,
    )


def build_qualification() -> dict[str, Any]:
    candidate = matrix.verify_matrix_candidate(DEFAULT_MATRIX_CANDIDATE)
    admission = matrix.verify_canary_admission(
        matrix.DEFAULT_CANARY_ADMISSION
    )
    value = base.build_qualification()
    value["schema_version"] = (
        "m3-paper-v2-formal-result-gate-qualification-4.0"
    )
    value["status"] = (
        "formal_result_gate_v4_qualified_and_frozen_precanary"
    )
    value["bound_matrix_run_id"] = RUN_ID
    value["matrix_candidate_manifest_sha256"] = candidate[
        "manifest_sha256"
    ]
    value["canary_admission_manifest_sha256"] = admission[
        "manifest_sha256"
    ]
    value["boundary_rejection_contract"] = {
        "adapter_version": candidate["scope"][
            "boundary_rejection_semantics"
        ]["adapter_version"],
        "reason_code": candidate["scope"][
            "boundary_rejection_semantics"
        ]["reason_code"],
        "proposal_message_digests": copy.deepcopy(
            candidate["scope"]["boundary_rejection_semantics"][
                "proposal_message_digests"
            ]
        ),
    }
    value["precanary_locked_inputs"] = [
        _artifact_lock(path) for path in _precanary_lock_paths()
    ]
    value["gate_candidate_requires_passing_canary_review"] = True
    value["scientific_outcomes_read"] = 0
    value["network_calls_made"] = 0
    value["append_only_execution_ledgers_mutated"] = False
    return value


def write_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    value = build_qualification()
    _write_json(path, value)
    return value


def verify_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    observed = _read_json(path)
    expected = build_qualification()
    if observed != expected:
        raise FormalResultGateV4Error(
            "formal result gate v4 qualification drift"
        )
    return observed


@contextmanager
def _binding() -> Iterator[None]:
    replacements = {
        "matrix": matrix,
        "DEFAULT_SCHEMA": DEFAULT_SCHEMA,
        "DEFAULT_QUALIFICATION": DEFAULT_QUALIFICATION,
        "DEFAULT_GATE_CANDIDATE": DEFAULT_GATE_CANDIDATE,
        "DEFAULT_RESULT_ADMISSION": DEFAULT_RESULT_ADMISSION,
        "DEFAULT_MATRIX_CANDIDATE": DEFAULT_MATRIX_CANDIDATE,
        "DEFAULT_CONTINUATION_ADMISSION": DEFAULT_CONTINUATION_ADMISSION,
        "DEFAULT_CASE_MANIFEST": DEFAULT_CASE_MANIFEST,
        "DEFAULT_CASE_INDEX": DEFAULT_CASE_INDEX,
        "DEFAULT_GATE_SPEC": DEFAULT_GATE_SPEC,
        "DEFAULT_BUDGET_AUTHORIZATION": DEFAULT_BUDGET_AUTHORIZATION,
        "DEFAULT_ANALYSIS_MODULE": DEFAULT_ANALYSIS_MODULE,
        "RUN_ID": RUN_ID,
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "OWNER_APPROVAL_STATEMENT_SHA256": (
            OWNER_APPROVAL_STATEMENT_SHA256
        ),
        "verify_qualification": verify_qualification,
        "verify_gate_candidate": verify_gate_candidate,
        "verify_technical_review": verify_technical_review,
        "verify_result_admission": verify_result_admission,
    }
    old = {name: getattr(base, name) for name in replacements}
    for name, item in replacements.items():
        setattr(base, name, item)
    try:
        yield
    finally:
        for name, item in old.items():
            setattr(base, name, item)


def _review_paths() -> tuple[Path, Path]:
    candidate = matrix.verify_matrix_candidate(DEFAULT_MATRIX_CANDIDATE)
    output_root = PROJECT_ROOT / candidate["scope"]["outputs"]["root"]
    return (
        output_root / "formal_result_technical_review_v4.json",
        output_root / "admitted_medium_analysis_v4.json",
    )


def _canary_review_path() -> Path:
    candidate = matrix.verify_matrix_candidate(DEFAULT_MATRIX_CANDIDATE)
    return (
        PROJECT_ROOT
        / candidate["scope"]["outputs"]["root"]
        / matrix.DEFAULT_CANARY_REVIEW_NAME
    )


def _verify_canary_review(path: Path | None = None) -> dict[str, Any]:
    target = _canary_review_path() if path is None else path
    if not target.is_file():
        raise FormalResultGateV4Error(
            "passing v7 canary technical review is required before "
            "freezing the result-gate candidate"
        )
    value = _read_json(target)
    candidate = matrix.verify_matrix_candidate(DEFAULT_MATRIX_CANDIDATE)
    admission_sha = base._sha256_file(matrix.DEFAULT_CANARY_ADMISSION)
    canary_scope = candidate["scope"]["canary"]
    expected_conditions = [
        str(condition) for condition in canary_scope["conditions"]
    ]
    checks = {
        "status": (
            value.get("status")
            == "six_condition_canary_technical_gate_pass"
        ),
        "run_id": value.get("run_id") == RUN_ID,
        "candidate": (
            value.get("candidate_manifest_sha256")
            == candidate["manifest_sha256"]
        ),
        "admission": (
            value.get("canary_admission_file_sha256") == admission_sha
        ),
        "record_count": value.get("record_count") == 6,
        "planned_work_items": canary_scope["work_items"] == 6,
        "conditions": value.get("conditions") == expected_conditions,
        "statuses": value.get("operational_statuses") == ["completed"] * 6,
        "tiers": value.get("result_tiers") == ["formal_candidate"] * 6,
        "diagnostics": value.get("diagnostic_records") == 0,
        "operational_failures": value.get("operational_failures") == 0,
        "rejected_effects_executed": (
            value.get("rejected_effects_executed") == 0
        ),
        "outcomes_closed": (
            value.get("scientific_outcomes_reviewed") is False
        ),
        "continuation_eligible": (
            value.get("matrix_continuation_eligible") is True
        ),
        "continuation_closed": (
            value.get("matrix_continuation_authorized") is False
        ),
        "results_closed": (
            value.get("result_admission_authorized") is False
        ),
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise FormalResultGateV4Error(
            f"v7 canary technical review failed checks: {failed}"
        )
    return value


def build_gate_candidate() -> dict[str, Any]:
    matrix.verify_matrix_candidate(DEFAULT_MATRIX_CANDIDATE)
    qualification = verify_qualification()
    canary_review = _verify_canary_review()
    with _binding():
        value = base.build_gate_candidate()
    value["qualification"] = qualification
    value["planned_outputs"]["technical_review"] = _display_path(
        _review_paths()[0]
    )
    value["planned_outputs"]["result_admission"] = _display_path(
        DEFAULT_RESULT_ADMISSION
    )
    value["planned_outputs"]["analysis"] = _display_path(_review_paths()[1])
    value["canary_technical_boundary"] = {
        "review_sha256": base._sha256_file(_canary_review_path()),
        "scientific_outcomes_reviewed": canary_review[
            "scientific_outcomes_reviewed"
        ],
        "operational_failures": canary_review["operational_failures"],
        "diagnostic_records": canary_review["diagnostic_records"],
    }
    for path in (
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/formal_matrix_controller_v7.py",
        PROJECT_ROOT
        / "experiments/paper_v2/boundary_rejection_runtime_v3.py",
        matrix.DEFAULT_CANARY_ADMISSION,
    ):
        _append_lock(value["locked_inputs"], path)
    return _validate_artifact(
        _seal(value),
        expected_role="prospective_result_gate_candidate",
    )


def write_gate_candidate(
    path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    value = build_gate_candidate()
    _write_json(path, value)
    return value


def verify_gate_candidate(
    path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    observed = _validate_artifact(
        _read_json(path),
        expected_role="prospective_result_gate_candidate",
    )
    if observed != build_gate_candidate():
        raise FormalResultGateV4Error(
            "prospective result gate candidate drift"
        )
    return observed


def build_technical_review(
    *,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
    continuation_admission_path: Path = DEFAULT_CONTINUATION_ADMISSION,
) -> dict[str, Any]:
    with _binding():
        value = base.build_technical_review(
            candidate_path=candidate_path,
            continuation_admission_path=continuation_admission_path,
        )
    return _validate_artifact(
        value,
        expected_role="formal_result_technical_review",
    )


def write_technical_review(path: Path | None = None) -> dict[str, Any]:
    target = _review_paths()[0] if path is None else path
    value = build_technical_review()
    _write_json(target, value)
    return value


def verify_technical_review(path: Path | None = None) -> dict[str, Any]:
    target = _review_paths()[0] if path is None else path
    observed = _validate_artifact(
        _read_json(target),
        expected_role="formal_result_technical_review",
    )
    if observed != build_technical_review():
        raise FormalResultGateV4Error(
            "technical result review does not reproduce"
        )
    return observed


def build_result_admission(
    *,
    review_path: Path | None = None,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    target = _review_paths()[0] if review_path is None else review_path
    with _binding():
        value = base.build_result_admission(
            review_path=target,
            candidate_path=candidate_path,
        )
    return _validate_artifact(
        value,
        expected_role="formal_result_analysis_admission",
    )


def write_result_admission(
    path: Path = DEFAULT_RESULT_ADMISSION,
) -> dict[str, Any]:
    value = build_result_admission()
    _write_json(path, value)
    return value


def verify_result_admission(
    path: Path = DEFAULT_RESULT_ADMISSION,
) -> dict[str, Any]:
    observed = _validate_artifact(
        _read_json(path),
        expected_role="formal_result_analysis_admission",
    )
    if observed != build_result_admission():
        raise FormalResultGateV4Error("result analysis admission drift")
    return observed


def build_admitted_analysis(
    *,
    admission_path: Path = DEFAULT_RESULT_ADMISSION,
) -> dict[str, Any]:
    with _binding():
        value = base.build_admitted_analysis(
            admission_path=admission_path
        )
    value["result_gate_version"] = SCHEMA_VERSION
    return value


def write_admitted_analysis(path: Path | None = None) -> dict[str, Any]:
    target = _review_paths()[1] if path is None else path
    value = build_admitted_analysis()
    _write_json(target, value)
    return value


def verify_admitted_analysis(path: Path | None = None) -> dict[str, Any]:
    target = _review_paths()[1] if path is None else path
    observed = _read_json(target)
    if observed != build_admitted_analysis():
        raise FormalResultGateV4Error(
            "admitted medium analysis does not reproduce"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-review", action="store_true")
    action.add_argument("--verify-review", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--write-analysis", action="store_true")
    action.add_argument("--verify-analysis", action="store_true")
    args = parser.parse_args()

    if args.write_qualification:
        value = write_qualification()
    elif args.verify_qualification:
        value = verify_qualification()
    elif args.write_candidate:
        value = write_gate_candidate()
    elif args.verify_candidate:
        value = verify_gate_candidate()
    elif args.write_review:
        value = write_technical_review()
    elif args.verify_review:
        value = verify_technical_review()
    elif args.write_admission:
        value = write_result_admission()
    elif args.verify_admission:
        value = verify_result_admission()
    elif args.write_analysis:
        value = write_admitted_analysis()
    else:
        value = verify_admitted_analysis()
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
