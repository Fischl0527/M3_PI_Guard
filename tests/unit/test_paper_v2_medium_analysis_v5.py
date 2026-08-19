import json
from pathlib import Path

from experiments.paper_v2.contracts import validate_experiment_record
from experiments.paper_v2.medium_analysis_v5 import (
    analyze_medium_records_v5,
    project_closed_diagnostic_for_itt_v5,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_LEDGER = (
    ROOT
    / "outputs/paper_upgrade_v2/formal_medium/deepseek"
    / "8d08cab3febccdf5a4360d208766c39cef851fa9ec8b9c15799ee30171a213bf"
    / "experiment_records_v2.jsonl"
)
CASE_MANIFEST = (
    ROOT / "protocols/paper_upgrade_v2/medium_case_manifest_v1.json"
)
CASE_INDEX = ROOT / "protocols/paper_upgrade_v2/medium_case_index_v1.jsonl"
GATE_SPEC = ROOT / "protocols/paper_upgrade_v2/medium_gate_spec_v2.json"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _diagnostic_record():
    records = [
        entry["record"]
        for entry in _jsonl(SOURCE_LEDGER)
        if entry["record"]["result_tier"] == "diagnostic"
    ]
    assert len(records) == 1
    return records[0]


def test_v5_diagnostic_projection_is_schema_valid_and_truthful() -> None:
    source = _diagnostic_record()
    projected = project_closed_diagnostic_for_itt_v5(source)

    validate_experiment_record(projected)
    assert projected["unsafe_effect_itt"] == source["unsafe_effect_itt"]
    assert projected["task_completion"] == source["task_completion"]
    assert projected["provider_attestation"]["response_id"] is None
    assert projected["provider_attestation"]["identity_verified"] is False
    assert projected["provider_attestation"]["identity_evidence"] == "unverified"
    assert projected["provider_attestation"]["evidence_level"] == "diagnostic_only"
    assert "analysis_projection" not in projected


def test_empty_v5_analysis_preserves_pending_state() -> None:
    report = analyze_medium_records_v5(
        [],
        case_manifest=_json(CASE_MANIFEST),
        case_index=_jsonl(CASE_INDEX),
        gate_spec=_json(GATE_SPEC),
        technical_identity_policy_satisfied=True,
        bootstrap_iterations=1,
    )

    assert report["status"] == "results_pending"
    assert report["diagnostic_itt_projection"]["projected_record_count"] == 0
