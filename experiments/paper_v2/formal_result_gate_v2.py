"""Prospective technical result gate for the DeepSeek v5 medium matrix.

The gate is blind to scientific outcomes until execution evidence has passed a
separate integrity review. Known protocol terminal states remain in the ITT
denominator. They do not become runner crashes merely because their scientific
outcomes are unfavorable.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v5 as matrix
from experiments.paper_v2.contracts import canonical_json_bytes
from experiments.paper_v2.medium_analysis_v3 import analyze_medium_records_v3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/formal_result_gate_v2.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_result_gate_qualification_v2.json"
)
DEFAULT_GATE_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_result_gate_candidate_v2.json"
)
DEFAULT_RESULT_ADMISSION = (
    PROTOCOL_ROOT / "admissions/deepseek_medium_result_admission_v2.json"
)
DEFAULT_MATRIX_CANDIDATE = matrix.DEFAULT_CANDIDATE
DEFAULT_CONTINUATION_ADMISSION = matrix.DEFAULT_CONTINUATION_ADMISSION
DEFAULT_CASE_MANIFEST = PROTOCOL_ROOT / "medium_case_manifest_v1.json"
DEFAULT_CASE_INDEX = PROTOCOL_ROOT / "medium_case_index_v1.jsonl"
DEFAULT_GATE_SPEC = PROTOCOL_ROOT / "medium_gate_spec_v2.json"
DEFAULT_BUDGET_AUTHORIZATION = (
    PROTOCOL_ROOT / "provider_budget_authorization_v3.json"
)
DEFAULT_ANALYSIS_MODULE = (
    PROJECT_ROOT / "experiments/paper_v2/medium_analysis_v3.py"
)

RUN_ID = matrix.RUN_ID
SCHEMA_VERSION = "m3-paper-v2-formal-result-gate-2.0"
EXPECTED_RECORDS = 480
EXPECTED_PROVIDER = "deepseek"
EXPECTED_MODEL = "deepseek-v4-pro"
EXPECTED_TRACE_ATTESTATION_LEVEL = "prospective_formal_trace_eligible_v2"
OWNER_APPROVAL_STATEMENT_SHA256 = matrix.OWNER_STATEMENT_SHA256


class FormalResultGateV2Error(RuntimeError):
    """Raised when v5 evidence cannot cross the prospective result gate."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalResultGateV2Error(f"{path}: expected a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise FormalResultGateV2Error(
                    f"{path}:{line_number}: blank JSONL row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise FormalResultGateV2Error(
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
    Draft202012Validator(
        _read_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(value)
    if value.get("artifact_role") != expected_role:
        raise FormalResultGateV2Error(
            f"expected artifact role {expected_role!r}"
        )
    if value.get("manifest_sha256") != _manifest_sha(value):
        raise FormalResultGateV2Error("formal result artifact digest drift")
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
        "inventory_sha256": hashlib.sha256(
            canonical_json_bytes(rows)
        ).hexdigest(),
    }


def _formal_trace_ok(record: Mapping[str, Any]) -> bool:
    bundle = record["provider_trace_bundle"]
    attestations = bundle["activated_attestations"]
    if not attestations:
        return False
    identity_ok = all(
        (
            attestation["provider_id"] == EXPECTED_PROVIDER
            and attestation["model_id"] == EXPECTED_MODEL
            and attestation["official_network"] is True
            and attestation["exact_model_identity"] is True
            and attestation["evidence_level"]
            == EXPECTED_TRACE_ATTESTATION_LEVEL
            and attestation["v2_trace_eligible"] is True
            and attestation["prompt_or_response_content_stored"] is False
            and attestation["retroactive_upgrade_allowed"] is False
        )
        for attestation in attestations
    )
    return bool(
        identity_ok
        and bundle["bundle_status"] == "completed"
        and bundle["open_request_count"] == 0
        and bundle["completed_request_count"] == bundle["request_count"]
        and bundle["result_tier_ceiling"] == "formal_candidate"
    )


def _diagnostic_trace_ok(record: Mapping[str, Any]) -> bool:
    bundle = record["provider_trace_bundle"]
    failures = bundle.get("failures", [])
    failure_count = len(failures)
    return bool(
        record["operational_status"] in {"provider_failure", "timeout"}
        and bundle["provider_id"] == EXPECTED_PROVIDER
        and bundle["model_id"] == EXPECTED_MODEL
        and bundle["bundle_status"]
        in {"incomplete_provider_failure", "incomplete_paused"}
        and bundle["result_tier_ceiling"] == "diagnostic"
        and failure_count >= 1
        and bundle["open_request_count"] == failure_count
        and bundle["completed_request_count"] + failure_count
        == bundle["request_count"]
        and all(
            failure.get("status") in {"provider_failure", "paused"}
            for failure in failures
        )
    )


def _isolation_ok(record: Mapping[str, Any]) -> bool:
    bundle = record["provider_trace_bundle"]
    receipt = record["provider_safety_receipt"]
    evidence = receipt["evidence"]
    return bool(
        receipt["credentials_stored"] is False
        and evidence["provider_id"] == EXPECTED_PROVIDER
        and evidence["external_connectors_enabled"] is False
        and evidence["provider_managed_tools_enabled"] is False
        and evidence["decision"] == "ALLOW_ISOLATED_SIMULATION_ONLY"
        and bundle["prompt_or_response_content_stored"] is False
        and bundle["provider_tools_declared"] is False
        and bundle["external_effects_enabled"] is False
        and bundle["automatic_retry"] is False
    )


def evaluate_operational_gate(
    records: Sequence[Mapping[str, Any]],
    *,
    expected_records: int,
    remaining_work_items: int,
    open_attempts: int,
    budget_paused: bool,
    gate_spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate technical evidence only, without accessing scientific outcomes."""

    policy = gate_spec["technical_result_admission"]
    statuses = Counter(str(record["operational_status"]) for record in records)
    tiers = Counter(str(record["result_tier"]) for record in records)
    allowed_statuses = set(policy["allowed_terminal_statuses"])
    allowed_tiers = set(policy["allowed_result_tiers"])
    diagnostics = tiers["diagnostic"]
    diagnostic_ceiling = math.floor(
        expected_records * float(policy["diagnostic_records_max_fraction"])
    )
    runner_failures = statuses["runner_failure"]
    formal_records = [
        record for record in records if record["result_tier"] == "formal_candidate"
    ]
    diagnostic_records = [
        record for record in records if record["result_tier"] == "diagnostic"
    ]
    formal_trace_ok = all(_formal_trace_ok(record) for record in formal_records)
    diagnostic_trace_ok = all(
        _diagnostic_trace_ok(record) for record in diagnostic_records
    )
    isolation_ok = all(_isolation_ok(record) for record in records)
    checks = {
        "complete_record_matrix": (
            len(records) == expected_records and remaining_work_items == 0
        ),
        "no_open_attempts": open_attempts == 0,
        "all_records_in_itt": all(
            record["included_in_intention_to_treat"] is True
            for record in records
        ),
        "only_prespecified_terminal_statuses": set(statuses) <= allowed_statuses,
        "no_unknown_result_tiers": set(tiers) <= allowed_tiers,
        "runner_failure_ceiling": (
            runner_failures <= int(policy["runner_failure_max_count"])
        ),
        "diagnostic_ceiling": diagnostics <= diagnostic_ceiling,
        "formal_exact_identity_chain": formal_trace_ok,
        "diagnostic_closed_failure_trace": diagnostic_trace_ok,
        "isolated_effect_boundary": isolation_ok,
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
        "result_tier_counts": dict(sorted(tiers.items())),
        "runner_failure_count": runner_failures,
        "diagnostic_count": diagnostics,
        "diagnostic_count_ceiling": diagnostic_ceiling,
        "formal_candidate_count": len(formal_records),
        "checks": checks,
    }


def build_gate_candidate() -> dict[str, Any]:
    matrix_candidate = matrix.verify_matrix_candidate(DEFAULT_MATRIX_CANDIDATE)
    canary_review = (
        PROJECT_ROOT
        / matrix_candidate["scope"]["outputs"]["root"]
        / matrix.DEFAULT_CANARY_REVIEW_NAME
    )
    qualification = verify_qualification()
    gate_spec = _read_json(DEFAULT_GATE_SPEC)
    locked = [
        Path(__file__),
        DEFAULT_SCHEMA,
        DEFAULT_QUALIFICATION,
        DEFAULT_MATRIX_CANDIDATE,
        canary_review,
        DEFAULT_ANALYSIS_MODULE,
        DEFAULT_CASE_MANIFEST,
        DEFAULT_CASE_INDEX,
        DEFAULT_GATE_SPEC,
        DEFAULT_BUDGET_AUTHORIZATION,
    ]
    scope = matrix_candidate["scope"]
    output_root = PROJECT_ROOT / scope["outputs"]["root"]
    return _seal(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_role": "prospective_result_gate_candidate",
            "status": "frozen_before_scientific_outcome_access",
            "run_id": RUN_ID,
            "expected_records": EXPECTED_RECORDS,
            "matrix_candidate_manifest_sha256": matrix_candidate[
                "manifest_sha256"
            ],
            "canary_review_sha256": _sha256_file(canary_review),
            "qualification": qualification,
            "locked_inputs": [_artifact_lock(path) for path in locked],
            "technical_policy": copy.deepcopy(
                gate_spec["technical_result_admission"]
            ),
            "planned_outputs": {
                "technical_review": _display_path(
                    output_root / "formal_result_technical_review_v2.json"
                ),
                "result_admission": _display_path(DEFAULT_RESULT_ADMISSION),
                "analysis": _display_path(
                    output_root / "admitted_medium_analysis_v3.json"
                ),
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
        raise FormalResultGateV2Error(
            "prospective result gate candidate drift"
        )
    return observed


def _review_paths() -> tuple[Path, Path]:
    candidate = matrix.verify_matrix_candidate(DEFAULT_MATRIX_CANDIDATE)
    output_root = PROJECT_ROOT / candidate["scope"]["outputs"]["root"]
    return (
        output_root / "formal_result_technical_review_v2.json",
        output_root / "admitted_medium_analysis_v3.json",
    )


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
    authorization = matrix.authorize_matrix(
        continuation_admission_path,
        required_scope="continuation",
        candidate_path=DEFAULT_MATRIX_CANDIDATE,
    )
    state = matrix._state_from_paths(authorization.permit)
    records = [entry["record"] for entry in state["record_entries"]]
    gate_spec = _read_json(DEFAULT_GATE_SPEC)
    gate = evaluate_operational_gate(
        records,
        expected_records=EXPECTED_RECORDS,
        remaining_work_items=len(state["pending_work_items"]),
        open_attempts=len(state["attempt_status"]["open_work_keys"]),
        budget_paused=bool(state["budget_status"]["paused"]),
        gate_spec=gate_spec,
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
    path: Path | None = None,
    *,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    target = _review_paths()[0] if path is None else path
    value = build_technical_review(candidate_path=candidate_path)
    _write_json(target, value)
    return value


def verify_technical_review(
    path: Path | None = None,
    *,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    target = _review_paths()[0] if path is None else path
    observed = _validate_artifact(
        _read_json(target),
        expected_role="formal_result_technical_review",
    )
    expected = build_technical_review(candidate_path=candidate_path)
    if observed != expected:
        raise FormalResultGateV2Error(
            "technical result review does not reproduce"
        )
    return observed


def build_result_admission(
    *,
    review_path: Path | None = None,
    candidate_path: Path = DEFAULT_GATE_CANDIDATE,
) -> dict[str, Any]:
    target = _review_paths()[0] if review_path is None else review_path
    candidate = verify_gate_candidate(candidate_path)
    review = verify_technical_review(
        target,
        candidate_path=candidate_path,
    )
    if (
        review["status"] != "technical_result_gate_pass"
        or review["operational_gate"]["result_admission_eligible"] is not True
    ):
        raise FormalResultGateV2Error(
            "technical review does not authorize scientific analysis"
        )
    return _seal(
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
    expected = build_result_admission()
    if observed != expected:
        raise FormalResultGateV2Error("result analysis admission drift")
    return observed


def build_admitted_analysis(
    *,
    admission_path: Path = DEFAULT_RESULT_ADMISSION,
) -> dict[str, Any]:
    admission = verify_result_admission(admission_path)
    authorization = matrix.authorize_matrix(
        DEFAULT_CONTINUATION_ADMISSION,
        required_scope="continuation",
        candidate_path=DEFAULT_MATRIX_CANDIDATE,
    )
    state = matrix._state_from_paths(authorization.permit)
    records = [entry["record"] for entry in state["record_entries"]]
    analysis = analyze_medium_records_v3(
        records,
        case_manifest=_read_json(DEFAULT_CASE_MANIFEST),
        case_index=_read_jsonl(DEFAULT_CASE_INDEX),
        gate_spec=_read_json(DEFAULT_GATE_SPEC),
    )
    return {
        "schema_version": "m3-paper-v2-admitted-medium-analysis-3.0",
        "status": "complete",
        "run_id": RUN_ID,
        "result_admission_sha256": admission["manifest_sha256"],
        "record_ledger_sha256": admission["evidence_locks"][
            "record_ledger"
        ]["sha256"],
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
    expected = build_admitted_analysis()
    if observed != expected:
        raise FormalResultGateV2Error(
            "admitted medium analysis does not reproduce"
        )
    return observed


def _fixture_record(
    *,
    status: str = "completed",
    tier: str = "formal_candidate",
    official: bool = True,
) -> dict[str, Any]:
    diagnostic = tier == "diagnostic"
    failure_count = 1 if diagnostic else 0
    return {
        "operational_status": status,
        "result_tier": tier,
        "included_in_intention_to_treat": True,
        "provider_trace_bundle": {
            "provider_id": EXPECTED_PROVIDER,
            "model_id": EXPECTED_MODEL,
            "activated_attestations": (
                []
                if diagnostic
                else [
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
                ]
            ),
            "bundle_status": (
                "incomplete_provider_failure" if diagnostic else "completed"
            ),
            "open_request_count": failure_count,
            "completed_request_count": 0 if diagnostic else 1,
            "request_count": 1,
            "result_tier_ceiling": tier,
            "prompt_or_response_content_stored": False,
            "provider_tools_declared": False,
            "external_effects_enabled": False,
            "automatic_retry": False,
            "failures": (
                [{"status": "provider_failure"}] if diagnostic else []
            ),
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
    spec = _read_json(DEFAULT_GATE_SPEC)
    passing = [_fixture_record(), _fixture_record(status="refusal")]
    pass_gate = evaluate_operational_gate(
        passing,
        expected_records=2,
        remaining_work_items=0,
        open_attempts=0,
        budget_paused=False,
        gate_spec=spec,
    )
    negatives = {
        "incomplete_matrix": evaluate_operational_gate(
            passing[:1],
            expected_records=2,
            remaining_work_items=1,
            open_attempts=0,
            budget_paused=False,
            gate_spec=spec,
        ),
        "runner_failure": evaluate_operational_gate(
            [passing[0], _fixture_record(status="runner_failure")],
            expected_records=2,
            remaining_work_items=0,
            open_attempts=0,
            budget_paused=False,
            gate_spec=spec,
        ),
        "unverified_identity": evaluate_operational_gate(
            [passing[0], _fixture_record(official=False)],
            expected_records=2,
            remaining_work_items=0,
            open_attempts=0,
            budget_paused=False,
            gate_spec=spec,
        ),
        "diagnostic_wrong_status": evaluate_operational_gate(
            [passing[0], _fixture_record(status="parse_failure", tier="diagnostic")],
            expected_records=2,
            remaining_work_items=0,
            open_attempts=0,
            budget_paused=False,
            gate_spec=spec,
        ),
    }
    if not pass_gate["result_admission_eligible"]:
        raise FormalResultGateV2Error(
            "positive qualification scenario failed"
        )
    if any(
        gate["result_admission_eligible"] for gate in negatives.values()
    ):
        raise FormalResultGateV2Error(
            "negative qualification scenario passed"
        )
    return {
        "schema_version": (
            "m3-paper-v2-formal-result-gate-qualification-2.0"
        ),
        "status": "formal_result_gate_v2_qualified_offline",
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
        raise FormalResultGateV2Error(
            "formal result gate v2 qualification drift"
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
