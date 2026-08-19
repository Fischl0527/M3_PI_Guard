"""Prospective technical result gate for the DeepSeek v6 medium matrix.

Version 3 binds the already frozen v6 matrix and its six-condition canary. It
reuses the qualified v2 operational checks while keeping scientific outcomes
closed until the complete 480-record evidence chain passes technical review.
"""

from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v6 as matrix
import experiments.paper_v2.formal_result_gate_v2 as base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_result_gate_v3.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_result_gate_qualification_v3.json"
)
DEFAULT_GATE_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_result_gate_candidate_v3.json"
)
DEFAULT_RESULT_ADMISSION = (
    PROTOCOL_ROOT / "admissions/deepseek_medium_result_admission_v3.json"
)
DEFAULT_MATRIX_CANDIDATE = matrix.DEFAULT_CANDIDATE
DEFAULT_CONTINUATION_ADMISSION = matrix.DEFAULT_CONTINUATION_ADMISSION
DEFAULT_CASE_MANIFEST = base.DEFAULT_CASE_MANIFEST
DEFAULT_CASE_INDEX = base.DEFAULT_CASE_INDEX
DEFAULT_GATE_SPEC = base.DEFAULT_GATE_SPEC
DEFAULT_BUDGET_AUTHORIZATION = base.DEFAULT_BUDGET_AUTHORIZATION
DEFAULT_ANALYSIS_MODULE = base.DEFAULT_ANALYSIS_MODULE

RUN_ID = matrix.RUN_ID
SCHEMA_VERSION = "m3-paper-v2-formal-result-gate-3.0"
EXPECTED_RECORDS = base.EXPECTED_RECORDS
OWNER_APPROVAL_STATEMENT_SHA256 = matrix.OWNER_STATEMENT_SHA256

evaluate_operational_gate = base.evaluate_operational_gate
_fixture_record = base._fixture_record


class FormalResultGateV3Error(RuntimeError):
    """Raised when v6 evidence cannot cross the prospective result gate."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalResultGateV3Error(f"{path}: expected a JSON object")
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
        raise FormalResultGateV3Error(
            f"expected artifact role {expected_role!r}"
        )
    if value.get("manifest_sha256") != base._manifest_sha(value):
        raise FormalResultGateV3Error("formal result artifact digest drift")
    return copy.deepcopy(dict(value))


def _append_lock(items: list[dict[str, Any]], path: Path) -> None:
    display = _display_path(path)
    if any(item["path"] == display for item in items):
        return
    items.append(_artifact_lock(path))


def build_qualification() -> dict[str, Any]:
    value = base.build_qualification()
    value["schema_version"] = (
        "m3-paper-v2-formal-result-gate-qualification-3.0"
    )
    value["status"] = "formal_result_gate_v3_qualified_offline"
    value["bound_matrix_run_id"] = RUN_ID
    value["scientific_outcomes_read"] = 0
    value["network_calls_made"] = 0
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
        raise FormalResultGateV3Error(
            "formal result gate v3 qualification drift"
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
        output_root / "formal_result_technical_review_v3.json",
        output_root / "admitted_medium_analysis_v3.json",
    )


def build_gate_candidate() -> dict[str, Any]:
    matrix.verify_matrix_candidate(DEFAULT_MATRIX_CANDIDATE)
    verify_qualification()
    with _binding():
        value = base.build_gate_candidate()
    value["qualification"] = verify_qualification()
    value["planned_outputs"]["technical_review"] = _display_path(
        _review_paths()[0]
    )
    value["planned_outputs"]["result_admission"] = _display_path(
        DEFAULT_RESULT_ADMISSION
    )
    value["planned_outputs"]["analysis"] = _display_path(_review_paths()[1])
    for path in (
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/formal_matrix_controller_v6.py",
        PROJECT_ROOT
        / "experiments/paper_v2/boundary_rejection_runtime_v2.py",
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
        raise FormalResultGateV3Error(
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
        raise FormalResultGateV3Error(
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
        raise FormalResultGateV3Error("result analysis admission drift")
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
        raise FormalResultGateV3Error(
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
