"""Prospective combined result gate for frozen v8 plus remainder v9.

The gate treats v8 and v9 as two immutable shards of one prespecified
480-work-item matrix.  It inspects only operational metadata until a separate
analysis admission is written.  Scientific outcome fields are first consumed
by ``build_admitted_analysis`` after that admission verifies.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as matrix_v1
import experiments.paper_v2.formal_matrix_controller_v8 as source
import experiments.paper_v2.formal_matrix_remainder_controller_v9 as remainder
import experiments.paper_v2.formal_result_gate_v2 as base
from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_result_gate_v6.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_result_gate_qualification_v6.json"
)
DEFAULT_GATE_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_combined_result_gate_candidate_v6.json"
)
DEFAULT_RESULT_ADMISSION = (
    PROTOCOL_ROOT
    / "admissions/deepseek_medium_combined_result_admission_v6.json"
)
DEFAULT_GATE_SPEC = base.DEFAULT_GATE_SPEC
DEFAULT_ANALYSIS_MODULE = base.DEFAULT_ANALYSIS_MODULE
DEFAULT_CASE_MANIFEST = base.DEFAULT_CASE_MANIFEST
DEFAULT_CASE_INDEX = base.DEFAULT_CASE_INDEX

RUN_ID = "paper-v2-deepseek-medium-v8-v9-combined-20260726"
SCHEMA_VERSION = "m3-paper-v2-formal-result-gate-6.0"
EXPECTED_RECORDS = 480
SOURCE_RECORDS = 303
REMAINDER_RECORDS = 177
OWNER_APPROVAL_STATEMENT_SHA256 = remainder.OWNER_STATEMENT_SHA256


class FormalResultGateV6Error(RuntimeError):
    """Raised when combined evidence cannot cross the prospective gate."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalResultGateV6Error(f"{path}: expected an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            raise FormalResultGateV6Error(
                f"{path}:{line_number}: blank JSONL row"
            )
        value = json.loads(line)
        if not isinstance(value, dict):
            raise FormalResultGateV6Error(
                f"{path}:{line_number}: expected an object"
            )
        rows.append(value)
    return rows


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


def _artifact_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FormalResultGateV6Error(
            f"missing combined-gate input: {_display_path(path)}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    core = copy.deepcopy(dict(value))
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def _validate_artifact(
    value: Mapping[str, Any],
    *,
    expected_role: str,
) -> dict[str, Any]:
    Draft202012Validator(
        _read_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["artifact_role"] != expected_role:
        raise FormalResultGateV6Error(
            f"expected combined-gate role {expected_role!r}"
        )
    if value["manifest_sha256"] != _manifest_sha(value):
        raise FormalResultGateV6Error(
            "combined result artifact digest drift"
        )
    return copy.deepcopy(dict(value))


def _review_paths() -> tuple[Path, Path]:
    candidate = remainder._load_json(remainder.DEFAULT_CANDIDATE)
    root = PROJECT_ROOT / candidate["scope"]["outputs"]["root"]
    return (
        root / "formal_result_technical_review_v6.json",
        root / "admitted_medium_analysis_v6.json",
    )


def _evidence_locks(permit: Any) -> dict[str, Any]:
    return {
        "record_ledger": _artifact_lock(permit.record_ledger_path),
        "attempt_ledger": _artifact_lock(permit.attempt_ledger_path),
        "budget_ledger": _artifact_lock(permit.budget_ledger_path),
        "provider_traces": base._trace_inventory(permit.trace_root),
    }


def _combined_state() -> dict[str, Any]:
    source_authorization = source.authorize_matrix(
        source.DEFAULT_CONTINUATION_ADMISSION,
        required_scope="continuation",
    )
    source_state = source._state_from_paths(source_authorization.permit)
    remainder_authorization = remainder.authorize_remainder_shard()
    remainder_state = remainder._state_from_paths(
        remainder_authorization.permit
    )
    source_entries = source_state["record_entries"]
    remainder_entries = remainder_state["record_entries"]
    source_keys = {str(entry["work_key"]) for entry in source_entries}
    remainder_keys = {str(entry["work_key"]) for entry in remainder_entries}
    selected_remainder_keys = {
        str(row["work_key"])
        for row in remainder_authorization.permit.work_items
    }
    plan_rows = matrix_v1._plan_rows()
    plan_keys = {str(row["work_key"]) for row in plan_rows}
    duplicate_keys = source_keys & remainder_keys
    terminal_keys = source_keys | remainder_keys
    unknown_keys = terminal_keys - plan_keys
    missing_keys = plan_keys - terminal_keys
    selection_overlap = source_keys & selected_remainder_keys
    selection_union = source_keys | selected_remainder_keys
    records_by_key = {
        str(entry["work_key"]): entry["record"]
        for entry in [*source_entries, *remainder_entries]
    }
    ordered_records = [
        records_by_key[str(row["work_key"])]
        for row in plan_rows
        if str(row["work_key"]) in records_by_key
    ]
    coverage = {
        "expected_records": EXPECTED_RECORDS,
        "source_records": len(source_entries),
        "remainder_records": len(remainder_entries),
        "combined_records": len(ordered_records),
        "combined_remaining_work_items": len(missing_keys),
        "duplicate_terminal_work_keys": len(duplicate_keys),
        "unknown_terminal_work_keys": len(unknown_keys),
        "source_remainder_selection_overlap": len(selection_overlap),
        "source_plus_remainder_selection_count": len(selection_union),
        "source_plus_remainder_selection_full_plan": (
            selection_union == plan_keys
        ),
        "combined_terminal_full_plan": terminal_keys == plan_keys,
        "source_open_attempts": len(
            source_state["attempt_status"]["open_work_keys"]
        ),
        "remainder_open_attempts": len(
            remainder_state["attempt_status"]["open_work_keys"]
        ),
    }
    if (
        len(source_entries) != SOURCE_RECORDS
        or selection_overlap
        or selection_union != plan_keys
        or unknown_keys
    ):
        raise FormalResultGateV6Error(
            "combined shard selection or immutable source drift"
        )
    return {
        "source_authorization": source_authorization,
        "source_state": source_state,
        "remainder_authorization": remainder_authorization,
        "remainder_state": remainder_state,
        "ordered_records": ordered_records,
        "coverage": coverage,
    }


def build_qualification() -> dict[str, Any]:
    base_qualification = base.build_qualification()
    plan_keys = {str(row["work_key"]) for row in matrix_v1._plan_rows()}
    source_fixture = set(sorted(plan_keys)[:SOURCE_RECORDS])
    remainder_fixture = plan_keys - source_fixture
    checks = {
        "source_count": len(source_fixture) == SOURCE_RECORDS,
        "remainder_count": len(remainder_fixture) == REMAINDER_RECORDS,
        "no_overlap": not (source_fixture & remainder_fixture),
        "full_coverage": source_fixture | remainder_fixture == plan_keys,
        "base_gate_positive": base_qualification[
            "positive_scenarios"
        ]
        == 1,
        "base_gate_negatives": base_qualification[
            "negative_scenarios"
        ]
        >= 4,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise FormalResultGateV6Error(
            f"combined gate qualification failed: {failed}"
        )
    return {
        "schema_version": (
            "m3-paper-v2-formal-result-gate-qualification-6.0"
        ),
        "status": "combined_v8_v9_result_gate_qualified_offline",
        "expected_records": EXPECTED_RECORDS,
        "source_records": SOURCE_RECORDS,
        "remainder_records": REMAINDER_RECORDS,
        "positive_scenarios": 1,
        "negative_scenarios": base_qualification["negative_scenarios"] + 3,
        "qualified_checks": checks,
        "diagnostic_rows_retained_in_itt": True,
        "network_calls_made": 0,
        "scientific_outcomes_read": 0,
        "append_only_execution_ledgers_mutated": False,
        "result_admission_authorized": False,
    }


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
    if observed != build_qualification():
        raise FormalResultGateV6Error(
            "combined result gate qualification drift"
        )
    return observed


def _candidate_locked_inputs() -> list[dict[str, Any]]:
    paths = (
        Path(__file__),
        DEFAULT_SCHEMA,
        DEFAULT_QUALIFICATION,
        PROJECT_ROOT
        / "experiments/paper_v2/formal_matrix_remainder_controller_v9.py",
        remainder.DEFAULT_SCHEMA,
        remainder.DEFAULT_QUALIFICATION,
        remainder.DEFAULT_CANDIDATE,
        remainder.DEFAULT_ADMISSION,
        PROJECT_ROOT / "experiments/paper_v2/formal_matrix_controller_v8.py",
        source.DEFAULT_CANDIDATE,
        source.DEFAULT_CONTINUATION_ADMISSION,
        DEFAULT_GATE_SPEC,
        DEFAULT_ANALYSIS_MODULE,
        DEFAULT_CASE_MANIFEST,
        DEFAULT_CASE_INDEX,
    )
    return [_artifact_lock(path) for path in paths]


def _verify_remainder_candidate_single_pass() -> tuple[
    dict[str, Any], dict[str, Any]
]:
    candidate = remainder._validate_manifest(
        remainder._load_json(remainder.DEFAULT_CANDIDATE),
        expected_role="owner_review_candidate",
    )
    scope = candidate["scope"]
    remainder._assert_locked_inputs(scope)
    source_snapshot, pending_rows = remainder._source_snapshot()
    qualification = remainder.verify_controller_qualification()
    pending_keys = {str(row["work_key"]) for row in pending_rows}
    expected_identity = sha256_canonical_json(
        {
            "run_id": remainder.RUN_ID,
            "source_technical_snapshot_sha256": source_snapshot[
                "technical_snapshot_sha256"
            ],
            "pending_rows_sha256": source_snapshot["pending_rows_sha256"],
            "qualification_sha256": _sha256_file(
                remainder.DEFAULT_QUALIFICATION
            ),
            "controller_sha256": _sha256_file(
                PROJECT_ROOT
                / "experiments/paper_v2/"
                "formal_matrix_remainder_controller_v9.py"
            ),
            "schema_sha256": _sha256_file(remainder.DEFAULT_SCHEMA),
        }
    )
    checks = {
        "source_snapshot": scope["source_v8"] == source_snapshot,
        "qualification": scope["qualification"] == qualification,
        "pending_rows": (
            scope["selection"]["pending_rows_sha256"]
            == remainder._rows_sha256(pending_rows)
        ),
        "pending_keys": (
            scope["selection"]["pending_work_keys_sha256"]
            == remainder._keys_sha256(pending_keys)
        ),
        "pending_count": (
            len(pending_rows) == REMAINDER_RECORDS
            and scope["selection"]["work_items"] == REMAINDER_RECORDS
        ),
        "matrix_identity": scope["matrix_identity"] == expected_identity,
        "output_identity": (
            Path(scope["outputs"]["root"]).name == expected_identity
        ),
        "result_closed": (
            scope["result_boundary"]["result_admission_authorized"] is False
            and scope["result_boundary"]["scientific_outcomes_reviewed"]
            is False
        ),
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise FormalResultGateV6Error(
            f"single-pass remainder candidate checks failed: {failed}"
        )
    admission = remainder._validate_manifest(
        remainder._load_json(remainder.DEFAULT_ADMISSION),
        expected_role="remainder_shard_execution_authorization",
    )
    if (
        admission["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or admission["scope"]["candidate_scope_sha256"]
        != candidate["scope_sha256"]
        or admission["scope"]["pending_work_keys_sha256"]
        != scope["selection"]["pending_work_keys_sha256"]
    ):
        raise FormalResultGateV6Error(
            "remainder admission does not bind the frozen candidate"
        )
    return candidate, admission


def build_gate_candidate() -> dict[str, Any]:
    qualification = verify_qualification()
    remainder_candidate, remainder_admission = (
        _verify_remainder_candidate_single_pass()
    )
    source_snapshot = remainder_candidate["scope"]["source_v8"]
    if (
        source_snapshot["record_count"] != SOURCE_RECORDS
        or remainder_candidate["scope"]["selection"]["work_items"]
        != REMAINDER_RECORDS
        or remainder_candidate["scope"]["selection"][
            "combined_expected_records"
        ]
        != EXPECTED_RECORDS
    ):
        raise FormalResultGateV6Error(
            "combined gate candidate shard counts drift"
        )
    review_path, analysis_path = _review_paths()
    return _validate_artifact(
        _seal(
            {
                "schema_version": SCHEMA_VERSION,
                "artifact_role": "prospective_result_gate_candidate",
                "status": (
                    "frozen_before_remainder_execution_and_"
                    "scientific_outcome_access"
                ),
                "run_id": RUN_ID,
                "expected_records": EXPECTED_RECORDS,
                "source_record_count": SOURCE_RECORDS,
                "remainder_record_count": REMAINDER_RECORDS,
                "source_v8_candidate_manifest_sha256": source_snapshot[
                    "candidate_manifest_sha256"
                ],
                "remainder_v9_candidate_manifest_sha256": (
                    remainder_candidate["manifest_sha256"]
                ),
                "remainder_v9_admission_manifest_sha256": (
                    remainder_admission["manifest_sha256"]
                ),
                "coverage_contract": {
                    "source_terminal_work_keys_sha256": source_snapshot[
                        "terminal_work_keys_sha256"
                    ],
                    "remainder_selected_work_keys_sha256": (
                        remainder_candidate["scope"]["selection"][
                            "pending_work_keys_sha256"
                        ]
                    ),
                    "remainder_selected_rows_sha256": (
                        remainder_candidate["scope"]["selection"][
                            "pending_rows_sha256"
                        ]
                    ),
                    "duplicate_work_keys_allowed": 0,
                    "unknown_work_keys_allowed": 0,
                    "missing_work_keys_allowed": 0,
                    "terminal_source_items_retryable": False,
                },
                "qualification": qualification,
                "locked_inputs": _candidate_locked_inputs(),
                "source_v8_evidence_locks": copy.deepcopy(
                    source_snapshot["evidence_locks"]
                ),
                "technical_policy": copy.deepcopy(
                    _read_json(DEFAULT_GATE_SPEC)[
                        "technical_result_admission"
                    ]
                ),
                "planned_outputs": {
                    "technical_review": _display_path(review_path),
                    "result_admission": _display_path(
                        DEFAULT_RESULT_ADMISSION
                    ),
                    "analysis": _display_path(analysis_path),
                },
                "evidence_boundary": {
                    "network_calls_made": 0,
                    "scientific_outcomes_reviewed": False,
                    "source_v8_mutated": False,
                    "remainder_v9_executed_while_building": False,
                    "result_admission_authorized": False,
                    "analysis_authorized": False,
                },
            }
        ),
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
        raise FormalResultGateV6Error(
            "combined result gate candidate drift"
        )
    return observed


def build_technical_review(
    *,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    candidate = verify_gate_candidate(candidate_path)
    state = _combined_state()
    coverage = state["coverage"]
    records = state["ordered_records"]
    source_state = state["source_state"]
    remainder_state = state["remainder_state"]
    open_attempts = (
        coverage["source_open_attempts"]
        + coverage["remainder_open_attempts"]
    )
    budget_paused = bool(
        source_state["budget_status"]["paused"]
        or remainder_state["budget_status"]["paused"]
    )
    gate = base.evaluate_operational_gate(
        records,
        expected_records=EXPECTED_RECORDS,
        remaining_work_items=coverage["combined_remaining_work_items"],
        open_attempts=open_attempts,
        budget_paused=budget_paused,
        gate_spec=_read_json(DEFAULT_GATE_SPEC),
    )
    if (
        coverage["duplicate_terminal_work_keys"]
        or coverage["unknown_terminal_work_keys"]
        or coverage["source_remainder_selection_overlap"]
        or not coverage["source_plus_remainder_selection_full_plan"]
    ):
        gate["result_admission_eligible"] = False
        gate["status"] = "technical_result_gate_blocked"
        gate["checks"]["combined_shard_coverage"] = False
    else:
        gate["checks"]["combined_shard_coverage"] = True
    source_permit = state["source_authorization"].permit
    remainder_permit = state["remainder_authorization"].permit
    return _validate_artifact(
        _seal(
            {
                "schema_version": SCHEMA_VERSION,
                "artifact_role": "formal_result_technical_review",
                "status": gate["status"],
                "run_id": RUN_ID,
                "candidate_manifest_sha256": candidate["manifest_sha256"],
                "remainder_admission_sha256": _sha256_file(
                    remainder.DEFAULT_ADMISSION
                ),
                "coverage": coverage,
                "operational_gate": gate,
                "evidence_locks": {
                    "source_v8": _evidence_locks(source_permit),
                    "remainder_v9": _evidence_locks(remainder_permit),
                },
                "budget_summary": {
                    "source_provider_calls_completed": source_state[
                        "budget_status"
                    ]["event_count"],
                    "remainder_provider_calls_completed": remainder_state[
                        "budget_status"
                    ]["event_count"],
                    "combined_provider_calls_completed": source_state[
                        "budget_status"
                    ]["event_count"]
                    + remainder_state["budget_status"]["event_count"],
                    "project_cumulative_cost_cny": remainder_state[
                        "budget_status"
                    ]["project_cumulative_cost_cny"],
                    "project_cumulative_usage": remainder_state[
                        "budget_status"
                    ]["project_cumulative_usage"],
                    "paused": budget_paused,
                },
                "evidence_boundary": {
                    "network_calls_made_by_review": 0,
                    "scientific_outcomes_reviewed": False,
                    "operational_metadata_reviewed": True,
                    "source_v8_mutated": False,
                    "remainder_v9_mutated": False,
                    "result_admission_authorized": False,
                    "analysis_authorized": False,
                },
            }
        ),
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
        raise FormalResultGateV6Error(
            "combined technical review does not reproduce"
        )
    return observed


def build_result_admission(
    *,
    review_path: Path | None = None,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    target = _review_paths()[0] if review_path is None else review_path
    candidate = verify_gate_candidate(candidate_path)
    review = verify_technical_review(target)
    if (
        review["status"] != "technical_result_gate_pass"
        or review["operational_gate"]["result_admission_eligible"] is not True
    ):
        raise FormalResultGateV6Error(
            "combined technical review does not authorize analysis"
        )
    return _validate_artifact(
        _seal(
            {
                "schema_version": SCHEMA_VERSION,
                "artifact_role": "formal_result_analysis_admission",
                "status": "activated_for_scientific_analysis",
                "run_id": RUN_ID,
                "candidate_manifest_sha256": candidate["manifest_sha256"],
                "technical_review_sha256": _sha256_file(target),
                "evidence_locks": copy.deepcopy(review["evidence_locks"]),
                "authorization": {
                    "result_admission_authorized": True,
                    "analysis_authorized": True,
                    "execution_continuation_authorized": False,
                    "provider_calls_authorized": False,
                    "owner_approval": {
                        "approval_kind": (
                            "delegated_safe_iteration_and_analysis"
                        ),
                        "approved_by_role": "project_owner",
                        "statement_sha256": (
                            OWNER_APPROVAL_STATEMENT_SHA256
                        ),
                    },
                },
                "evidence_boundary": {
                    "network_calls_made_by_admission": 0,
                    "scientific_outcomes_reviewed_while_building": False,
                    "append_only_execution_ledgers_mutated": False,
                },
            }
        ),
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
        raise FormalResultGateV6Error(
            "combined result analysis admission drift"
        )
    return observed


def build_admitted_analysis(
    *,
    admission_path: Path = DEFAULT_RESULT_ADMISSION,
) -> dict[str, Any]:
    admission = verify_result_admission(admission_path)
    state = _combined_state()
    if state["coverage"]["combined_remaining_work_items"] != 0:
        raise FormalResultGateV6Error(
            "combined analysis requires complete matrix coverage"
        )
    analysis = base.analyze_medium_records_v3(
        state["ordered_records"],
        case_manifest=_read_json(DEFAULT_CASE_MANIFEST),
        case_index=_read_jsonl(DEFAULT_CASE_INDEX),
        gate_spec=_read_json(DEFAULT_GATE_SPEC),
    )
    return {
        "schema_version": "m3-paper-v2-admitted-medium-analysis-6.0",
        "status": "complete",
        "run_id": RUN_ID,
        "result_admission_sha256": admission["manifest_sha256"],
        "record_ledger_sha256": {
            "source_v8": admission["evidence_locks"]["source_v8"][
                "record_ledger"
            ]["sha256"],
            "remainder_v9": admission["evidence_locks"]["remainder_v9"][
                "record_ledger"
            ]["sha256"],
        },
        "analysis": analysis,
    }


def write_admitted_analysis(path: Path | None = None) -> dict[str, Any]:
    target = _review_paths()[1] if path is None else path
    value = build_admitted_analysis()
    _write_json(target, value)
    return value


def verify_admitted_analysis(path: Path | None = None) -> dict[str, Any]:
    target = _review_paths()[1] if path is None else path
    observed = _read_json(target)
    if observed != build_admitted_analysis():
        raise FormalResultGateV6Error(
            "combined admitted analysis does not reproduce"
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
