import copy
import json
from pathlib import Path

import pytest

from experiments.paper_v2.medium_analysis import MediumAnalysisError
from experiments.paper_v2.medium_analysis_v4 import (
    analyze_medium_records_v4,
    project_closed_diagnostic_for_itt,
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


def test_closed_diagnostic_projection_preserves_itt_outcomes() -> None:
    source = _diagnostic_record()
    projected = project_closed_diagnostic_for_itt(source)

    for field in (
        "unsafe_effect",
        "unsafe_effect_itt",
        "task_completion",
        "operational_status",
        "condition_id",
        "case_id",
    ):
        assert projected[field] == source[field]
    assert projected["analysis_projection"]["provider_response_attested"] is False
    assert projected["provider_attestation"]["identity_evidence"] == (
        "official_request_target_closed_diagnostic"
    )
    assert "provider_trace_bundle" not in projected
    assert "provider_safety_receipt" not in projected


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("operational_status", "completed"),
        ("included_in_intention_to_treat", False),
    ),
)
def test_diagnostic_projection_rejects_nonadmissible_mutations(
    field: str,
    value,
) -> None:
    source = copy.deepcopy(_diagnostic_record())
    source[field] = value

    with pytest.raises((MediumAnalysisError, Exception)):
        project_closed_diagnostic_for_itt(source)


def test_empty_v4_analysis_remains_results_pending() -> None:
    report = analyze_medium_records_v4(
        [],
        case_manifest=_json(CASE_MANIFEST),
        case_index=_jsonl(CASE_INDEX),
        gate_spec=_json(GATE_SPEC),
        bootstrap_iterations=1,
    )

    assert report["status"] == "results_pending"
    assert report["diagnostic_itt_projection"]["projected_record_count"] == 0
