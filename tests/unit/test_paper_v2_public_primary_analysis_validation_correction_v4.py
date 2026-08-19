from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

import experiments.paper_v2.public_primary_analysis_validation_correction_v4 as correction
import experiments.paper_v2.public_primary_analysis_v4 as analysis_v4
from experiments.paper_v2.formal_record_store import _load_plan
from experiments.paper_v2.formal_record_store_v2 import (
    _qualification_record,
)


def test_v4_candidate_separates_analysis_and_chain_integrity(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        correction.admission_v1,
        "validate_admission",
        lambda value: {"manifest_sha256": "a" * 64},
    )
    monkeypatch.setattr(
        correction.previous,
        "verify_candidate",
        lambda: {"manifest_sha256": "b" * 64},
    )
    monkeypatch.setattr(
        correction.previous,
        "validate_admission",
        lambda value: {"manifest_sha256": "c" * 64},
    )
    merge = {
        "manifest_sha256": "d" * 64,
        "coverage": {
            "primary_records": 5082,
            "diagnostic_records": 76,
        },
        "operational_totals": {},
        "authorization": {"primary_evidence_integrity_complete": True},
        "artifact_locks": [],
    }
    monkeypatch.setattr(
        correction.merge_v2,
        "verify_primary_merge_review",
        lambda: merge,
    )

    candidate = correction.build_candidate()

    assert candidate["scope"]["record_count"] == 5082
    assert candidate["scope"]["diagnostic_record_count"] == 76
    assert candidate["scope"]["statistics_changed"] is False
    assert candidate["scope"]["records_changed"] is False
    assert candidate["scope"]["denominator_changed"] is False
    assert candidate["authorization"][
        "diagnostic_exclusion_authorized"
    ] is False
    assert "public_primary_analysis_v4" in correction.canonical_command()


def test_projection_safe_reader_checks_outcomes_without_cost_replay(
    tmp_path,
) -> None:
    record, _events = _qualification_record(
        tmp_path,
        item=_load_plan()[0],
        run_id="projection-safe-reader-test",
        index=1,
    )

    analysis_v4._validate_analysis_record(record)

    inconsistent = copy.deepcopy(record)
    inconsistent["unsafe_effect"] = True
    inconsistent["unsafe_effect_itt"] = False
    with pytest.raises(ValueError):
        analysis_v4._validate_analysis_record(inconsistent)


def test_projection_safe_reader_rejects_tier_status_drift(
    tmp_path,
) -> None:
    record, _events = _qualification_record(
        tmp_path,
        item=_load_plan()[0],
        run_id="projection-safe-tier-test",
        index=1,
    )
    record["result_tier"] = "diagnostic"
    record["operational_status"] = "provider_failure"

    with pytest.raises(ValidationError):
        analysis_v4._validate_analysis_record(record)
