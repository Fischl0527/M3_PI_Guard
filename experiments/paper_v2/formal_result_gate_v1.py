"""Prospective technical admission gate for the DeepSeek v4 medium matrix.

The gate is intentionally blind to scientific outcomes until a complete,
hash-verified, operationally clean matrix has been admitted.  It never mutates
the append-only execution ledgers and makes no network calls.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from experiments.paper_v2.contracts import (
    OPERATIONAL_FAILURE_STATUSES,
    canonical_json_bytes,
)
from experiments.paper_v2.formal_matrix_controller_v4 import (
    DEFAULT_CANDIDATE as DEFAULT_MATRIX_CANDIDATE,
)
from experiments.paper_v2.formal_matrix_controller_v4 import (
    DEFAULT_CONTINUATION_ADMISSION,
    RUN_ID,
    authorize_matrix,
)
from experiments.paper_v2.medium_analysis_v2 import analyze_medium_records_v2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_result_gate_v1.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_result_gate_qualification_v1.json"
)
DEFAULT_GATE_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_result_gate_candidate_v1.json"
)
DEFAULT_RESULT_ADMISSION = (
    PROTOCOL_ROOT
    / "admissions/deepseek_medium_result_admission_v1.json"
)
DEFAULT_CASE_MANIFEST = PROTOCOL_ROOT / "medium_case_manifest_v1.json"
DEFAULT_CASE_INDEX = PROTOCOL_ROOT / "medium_case_index_v1.jsonl"
DEFAULT_GATE_SPEC = PROTOCOL_ROOT / "medium_gate_spec_v1.json"
DEFAULT_MEDIUM_ANALYSIS_MODULE = (
    PROJECT_ROOT / "experiments/paper_v2/medium_analysis_v2.py"
)
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    / "dd794dd88eade41166bdafb7cb191898d7d19a5d8df737340f6acc3daac4504f"
)
DEFAULT_TECHNICAL_REVIEW = (
    DEFAULT_OUTPUT_ROOT / "formal_result_technical_review_v1.json"
)
DEFAULT_ANALYSIS = DEFAULT_OUTPUT_ROOT / "admitted_medium_analysis_v2.json"

SCHEMA_VERSION = "m3-paper-v2-formal-result-gate-1.0"
EXPECTED_RECORDS = 480
EXPECTED_PROVIDER = "deepseek"
EXPECTED_MODEL = "deepseek-v4-pro"
EXPECTED_TRACE_ATTESTATION_LEVEL = "prospective_formal_trace_eligible_v2"
OWNER_APPROVAL_STATEMENT_SHA256 = (
    "2194cd7fd6734d220f7b38cd64fd717df8717270f0034dcaebece42185269ef2"
)


class FormalResultGateError(RuntimeError):
    """Raised when result evidence cannot cross the prospective gate."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalResultGateError(f"{path}: expected a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise FormalResultGateError(
                    f"{path}:{line_number}: blank JSONL row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise FormalResultGateError(
                    f"{path}:{line_number}: expected an object"
                )
            values.append(value)
    return values


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {key: item for key, item in value.items() if key != "manifest_sha256"}
        )
    ).hexdigest()


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    result["manifest_sha256"] = _manifest_sha(result)
    return result


def _validate_artifact(
    value: Mapping[str, Any],
    *,
    expected_role: str,
) -> dict[str, Any]:
    schema = _read_json(DEFAULT_SCHEMA)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(value)
    if value.get("artifact_role") != expected_role:
        raise FormalResultGateError(
            f"expected artifact role {expected_role!r}"
        )
    if value.get("manifest_sha256") != _manifest_sha(value):
        raise FormalResultGateError("formal result artifact digest drift")
    return copy.deepcopy(dict(value))


def _artifact_lock(path: Path) -> dict[str, Any]:
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _trace_inventory(trace_root: Path) -> dict[str, Any]:
    rows = [
        {
            "path": path.relative_to(trace_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in sorted(trace_root.glob("*.jsonl"))
    ]
    return {
        "file_count": len(rows),
        "total_bytes": sum(int(row["bytes"]) for row in rows),
        "inventory_sha256": hashlib.sha256(canonical_json_bytes(rows)).hexdigest(),
    }


def evaluate_operational_gate(
    records: Sequence[Mapping[str, Any]],
    *,
    expected_records: int,
    remaining_work_items: int,
    open_attempts: int,
    budget_paused: bool,
) -> dict[str, Any]:
    """Evaluate only technical/evidence fields, never scientific outcomes."""

    statuses = Counter(str(record["operational_status"]) for record in records)
    tiers = Counter(str(record["result_tier"]) for record in records)
    failures = sum(
        count
        for status, count in statuses.items()
        if status in OPERATIONAL_FAILURE_STATUSES
    )
    attestation_count = 0
    official_identity_ok = True
    isolation_ok = True
    trace_bundle_ok = True
    for record in records:
        bundle = record["provider_trace_bundle"]
        attestations = bundle["activated_attestations"]
        attestation_count += len(attestations)
        official_identity_ok = official_identity_ok and bool(attestations)
        for attestation in attestations:
            official_identity_ok = official_identity_ok and all(
                (
                    attestation["provider_id"] == EXPECTED_PROVIDER,
                    attestation["model_id"] == EXPECTED_MODEL,
                    attestation["official_network"] is True,
                    attestation["exact_model_identity"] is True,
                    attestation["evidence_level"]
                    == EXPECTED_TRACE_ATTESTATION_LEVEL,
                    attestation["v2_trace_eligible"] is True,
                    attestation["prompt_or_response_content_stored"] is False,
                    attestation["retroactive_upgrade_allowed"] is False,
                )
            )
        receipt = record["provider_safety_receipt"]
        evidence = receipt["evidence"]
        isolation_ok = isolation_ok and all(
            (
                receipt["credentials_stored"] is False,
                evidence["provider_id"] == EXPECTED_PROVIDER,
                evidence["external_connectors_enabled"] is False,
                evidence["provider_managed_tools_enabled"] is False,
                evidence["decision"] == "ALLOW_ISOLATED_SIMULATION_ONLY",
            )
        )
        trace_bundle_ok = trace_bundle_ok and all(
            (
                bundle["bundle_status"] == "completed",
                bundle["open_request_count"] == 0,
                bundle["completed_request_count"] == bundle["request_count"],
                bundle["result_tier_ceiling"] == "formal_candidate",
                bundle["prompt_or_response_content_stored"] is False,
                bundle["provider_tools_declared"] is False,
                bundle["external_effects_enabled"] is False,
                bundle["automatic_retry"] is False,
            )
        )

    checks = {
        "complete_record_matrix": (
            len(records) == expected_records and remaining_work_items == 0
        ),
        "no_open_attempts": open_attempts == 0,
        "all_records_formal_candidate": (
            tiers == Counter({"formal_candidate": expected_records})
        ),
        "zero_operational_failures": failures == 0,
        "official_exact_identity_chain": official_identity_ok,
        "isolated_effect_boundary": isolation_ok,
        "complete_trace_bundles": trace_bundle_ok,
        "budget_not_paused": budget_paused is False,
    }
    eligible = all(checks.values())
    return {
        "status": (
            "technical_result_gate_pass"
            if eligible
            else "technical_result_gate_blocked"
        ),
        "result_admission_eligible": eligible,
        "record_count": len(records),
        "remaining_work_items": remaining_work_items,
        "open_attempts": open_attempts,
        "operational_status_counts": dict(sorted(statuses.items())),
        "operational_failure_count": failures,
        "result_tier_counts": dict(sorted(tiers.items())),
        "activated_attestation_count": attestation_count,
        "checks": checks,
    }


def build_gate_candidate() -> dict[str, Any]:
    locked = [
        Path(__file__),
        DEFAULT_SCHEMA,
        DEFAULT_QUALIFICATION,
        DEFAULT_MATRIX_CANDIDATE,
        DEFAULT_CONTINUATION_ADMISSION,
        DEFAULT_MEDIUM_ANALYSIS_MODULE,
        DEFAULT_CASE_MANIFEST,
        DEFAULT_CASE_INDEX,
        DEFAULT_GATE_SPEC,
    ]
    return _seal(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_role": "prospective_result_gate_candidate",
            "status": "frozen_before_scientific_outcome_access",
            "run_id": RUN_ID,
            "expected_records": EXPECTED_RECORDS,
            "locked_inputs": [_artifact_lock(path) for path in locked],
            "planned_outputs": {
                "technical_review": _display_path(DEFAULT_TECHNICAL_REVIEW),
                "result_admission": _display_path(DEFAULT_RESULT_ADMISSION),
                "analysis": _display_path(DEFAULT_ANALYSIS),
            },
            "evidence_boundary": {
                "network_calls_made": 0,
                "scientific_outcomes_reviewed": False,
                "result_admission_authorized": False,
                "analysis_authorized": False,
                "append_only_execution_ledgers_mutated": False,
            },
        }
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
        raise FormalResultGateError("prospective result gate candidate drift")
    return observed


def _review_evidence_locks(permit: Any) -> dict[str, Any]:
    return {
        "record_ledger": _artifact_lock(permit.record_ledger_path),
        "attempt_ledger": _artifact_lock(permit.attempt_ledger_path),
        "budget_ledger": _artifact_lock(permit.budget_ledger_path),
        "provider_traces": _trace_inventory(permit.trace_root),
    }


def build_technical_review(
    *,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
    continuation_admission_path: Path = DEFAULT_CONTINUATION_ADMISSION,
) -> dict[str, Any]:
    candidate = verify_gate_candidate(candidate_path)
    authorization = authorize_matrix(
        continuation_admission_path,
        required_scope="continuation",
        candidate_path=DEFAULT_MATRIX_CANDIDATE,
    )
    # authorize_matrix has already replayed and cross-bound every append-only
    # execution ledger. Re-read through the same validated state for summary.
    from experiments.paper_v2.formal_matrix_controller_v4 import _state_from_paths

    state = _state_from_paths(authorization.permit)
    records = [entry["record"] for entry in state["record_entries"]]
    gate = evaluate_operational_gate(
        records,
        expected_records=EXPECTED_RECORDS,
        remaining_work_items=len(state["pending_work_items"]),
        open_attempts=len(state["attempt_status"]["open_work_keys"]),
        budget_paused=bool(state["budget_status"]["paused"]),
    )
    return _seal(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_role": "formal_result_technical_review",
            "status": gate["status"],
            "run_id": RUN_ID,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "continuation_admission_sha256": _sha256_file(
                continuation_admission_path
            ),
            "operational_gate": gate,
            "evidence_locks": _review_evidence_locks(authorization.permit),
            "budget_summary": {
                "provider_calls_completed": state["budget_status"]["event_count"],
                "project_cumulative_cost_cny": state["budget_status"][
                    "project_cumulative_cost_cny"
                ],
                "project_cumulative_usage": state["budget_status"][
                    "project_cumulative_usage"
                ],
                "paused": state["budget_status"]["paused"],
            },
            "evidence_boundary": {
                "network_calls_made_by_review": 0,
                "scientific_outcomes_reviewed": False,
                "operational_metadata_reviewed": True,
                "result_admission_authorized": False,
                "analysis_authorized": False,
                "append_only_execution_ledgers_mutated": False,
            },
        }
    )


def write_technical_review(
    path: Path = DEFAULT_TECHNICAL_REVIEW,
    *,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    value = build_technical_review(candidate_path=candidate_path)
    _write_json(path, value)
    return value


def verify_technical_review(
    path: Path = DEFAULT_TECHNICAL_REVIEW,
    *,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    observed = _validate_artifact(
        _read_json(path),
        expected_role="formal_result_technical_review",
    )
    expected = build_technical_review(candidate_path=candidate_path)
    if observed != expected:
        raise FormalResultGateError("technical result review does not reproduce")
    return observed


def build_result_admission(
    *,
    review_path: Path = DEFAULT_TECHNICAL_REVIEW,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    candidate = verify_gate_candidate(candidate_path)
    review = verify_technical_review(
        review_path,
        candidate_path=candidate_path,
    )
    if (
        review["status"] != "technical_result_gate_pass"
        or review["operational_gate"]["result_admission_eligible"] is not True
    ):
        raise FormalResultGateError(
            "technical review does not authorize scientific analysis"
        )
    return _seal(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_role": "formal_result_analysis_admission",
            "status": "activated_for_scientific_analysis",
            "run_id": RUN_ID,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "technical_review_sha256": _sha256_file(review_path),
            "evidence_locks": copy.deepcopy(review["evidence_locks"]),
            "authorization": {
                "result_admission_authorized": True,
                "analysis_authorized": True,
                "execution_continuation_authorized": False,
                "provider_calls_authorized": False,
                "owner_approval": {
                    "approval_kind": "delegated_safe_iteration_and_analysis",
                    "approved_by_role": "project_owner",
                    "statement_sha256": OWNER_APPROVAL_STATEMENT_SHA256,
                },
            },
            "evidence_boundary": {
                "network_calls_made_by_admission": 0,
                "scientific_outcomes_reviewed_while_building": False,
                "append_only_execution_ledgers_mutated": False,
            },
        }
    )


def write_result_admission(
    path: Path = DEFAULT_RESULT_ADMISSION,
    *,
    review_path: Path = DEFAULT_TECHNICAL_REVIEW,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    value = build_result_admission(
        review_path=review_path,
        candidate_path=candidate_path,
    )
    _write_json(path, value)
    return value


def verify_result_admission(
    path: Path = DEFAULT_RESULT_ADMISSION,
    *,
    review_path: Path = DEFAULT_TECHNICAL_REVIEW,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    observed = _validate_artifact(
        _read_json(path),
        expected_role="formal_result_analysis_admission",
    )
    expected = build_result_admission(
        review_path=review_path,
        candidate_path=candidate_path,
    )
    if observed != expected:
        raise FormalResultGateError("result analysis admission drift")
    return observed


def build_admitted_analysis(
    *,
    admission_path: Path = DEFAULT_RESULT_ADMISSION,
    review_path: Path = DEFAULT_TECHNICAL_REVIEW,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    admission = verify_result_admission(
        admission_path,
        review_path=review_path,
        candidate_path=candidate_path,
    )
    authorization = authorize_matrix(
        DEFAULT_CONTINUATION_ADMISSION,
        required_scope="continuation",
        candidate_path=DEFAULT_MATRIX_CANDIDATE,
    )
    from experiments.paper_v2.formal_matrix_controller_v4 import _state_from_paths

    state = _state_from_paths(authorization.permit)
    records = [entry["record"] for entry in state["record_entries"]]
    analysis = analyze_medium_records_v2(
        records,
        case_manifest=_read_json(DEFAULT_CASE_MANIFEST),
        case_index=_read_jsonl(DEFAULT_CASE_INDEX),
        gate_spec=_read_json(DEFAULT_GATE_SPEC),
    )
    return {
        "schema_version": "m3-paper-v2-admitted-medium-analysis-2.0",
        "status": "complete",
        "run_id": RUN_ID,
        "result_admission_sha256": admission["manifest_sha256"],
        "record_ledger_sha256": admission["evidence_locks"][
            "record_ledger"
        ]["sha256"],
        "analysis": analysis,
    }


def write_admitted_analysis(
    path: Path = DEFAULT_ANALYSIS,
) -> dict[str, Any]:
    value = build_admitted_analysis()
    _write_json(path, value)
    return value


def verify_admitted_analysis(
    path: Path = DEFAULT_ANALYSIS,
) -> dict[str, Any]:
    observed = _read_json(path)
    expected = build_admitted_analysis()
    if observed != expected:
        raise FormalResultGateError("admitted medium analysis does not reproduce")
    return observed


def _fixture_record(
    *,
    status: str = "completed",
    tier: str = "formal_candidate",
    official: bool = True,
) -> dict[str, Any]:
    return {
        "operational_status": status,
        "result_tier": tier,
        "provider_trace_bundle": {
            "activated_attestations": [
                {
                    "provider_id": EXPECTED_PROVIDER,
                    "model_id": EXPECTED_MODEL,
                    "official_network": official,
                    "exact_model_identity": official,
                    "evidence_level": (
                        EXPECTED_TRACE_ATTESTATION_LEVEL
                        if official
                        else "diagnostic_only"
                    ),
                    "v2_trace_eligible": official,
                    "prompt_or_response_content_stored": False,
                    "retroactive_upgrade_allowed": False,
                }
            ],
            "bundle_status": "completed",
            "open_request_count": 0,
            "completed_request_count": 1,
            "request_count": 1,
            "result_tier_ceiling": "formal_candidate",
            "prompt_or_response_content_stored": False,
            "provider_tools_declared": False,
            "external_effects_enabled": False,
            "automatic_retry": False,
        },
        "provider_safety_receipt": {
            "credentials_stored": False,
            "evidence": {
                "provider_id": EXPECTED_PROVIDER,
                "external_connectors_enabled": False,
                "provider_managed_tools_enabled": False,
                "decision": "ALLOW_ISOLATED_SIMULATION_ONLY",
            },
        },
    }


def build_qualification() -> dict[str, Any]:
    passing = [_fixture_record(), _fixture_record(status="refusal")]
    pass_gate = evaluate_operational_gate(
        passing,
        expected_records=2,
        remaining_work_items=0,
        open_attempts=0,
        budget_paused=False,
    )
    negatives = {
        "incomplete_matrix": evaluate_operational_gate(
            passing[:1],
            expected_records=2,
            remaining_work_items=1,
            open_attempts=0,
            budget_paused=False,
        ),
        "diagnostic_tier": evaluate_operational_gate(
            [passing[0], _fixture_record(tier="diagnostic")],
            expected_records=2,
            remaining_work_items=0,
            open_attempts=0,
            budget_paused=False,
        ),
        "operational_failure": evaluate_operational_gate(
            [passing[0], _fixture_record(status="provider_failure")],
            expected_records=2,
            remaining_work_items=0,
            open_attempts=0,
            budget_paused=False,
        ),
        "unverified_identity": evaluate_operational_gate(
            [passing[0], _fixture_record(official=False)],
            expected_records=2,
            remaining_work_items=0,
            open_attempts=0,
            budget_paused=False,
        ),
    }
    if not pass_gate["result_admission_eligible"]:
        raise FormalResultGateError("positive qualification scenario failed")
    if any(
        gate["result_admission_eligible"] for gate in negatives.values()
    ):
        raise FormalResultGateError("negative qualification scenario passed")
    return {
        "schema_version": "m3-paper-v2-formal-result-gate-qualification-1.0",
        "status": "formal_result_gate_qualified_offline",
        "positive_scenarios": 1,
        "negative_scenarios": len(negatives),
        "negative_scenario_ids": sorted(negatives),
        "network_calls_made": 0,
        "scientific_outcomes_read": 0,
        "append_only_execution_ledgers_mutated": False,
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
    expected = build_qualification()
    if observed != expected:
        raise FormalResultGateError("formal result gate qualification drift")
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
