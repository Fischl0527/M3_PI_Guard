from __future__ import annotations

import experiments.paper_v2.public_primary_analysis_validation_correction_v5 as correction
import experiments.paper_v2.public_primary_analysis_v5 as analysis_v5
from experiments.paper_v2.formal_record_store import _load_plan
from experiments.paper_v2.formal_record_store_v2 import (
    _qualification_record,
)


def test_v5_candidate_preserves_outcomes_and_denominator(
    monkeypatch,
    tmp_path,
) -> None:
    prospective_root = (
        correction.PROJECT_ROOT
        / "outputs"
        / "verification"
        / "unit-test-prospective-analysis-v5"
        / tmp_path.parent.name
        / tmp_path.name
    )
    monkeypatch.setattr(
        correction,
        "ANALYSIS_OUTPUT_ROOT",
        prospective_root,
    )
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
        "authorization": {"primary_evidence_integrity_complete": True},
    }
    monkeypatch.setattr(
        correction.merge_v2,
        "verify_primary_merge_review",
        lambda: merge,
    )

    candidate = correction.build_candidate()

    assert candidate["scope"]["statistics_changed"] is False
    assert candidate["scope"]["records_changed"] is False
    assert candidate["scope"]["denominator_changed"] is False
    assert "unsafe effect and ITT unsafe effect" in candidate["scope"][
        "verbatim_fields"
    ]
    assert candidate["authorization"][
        "diagnostic_exclusion_authorized"
    ] is False
    assert "public_primary_analysis_v5" in correction.canonical_command()


def test_formal_projection_copies_scientific_fields_verbatim(
    tmp_path,
) -> None:
    record, _events = _qualification_record(
        tmp_path,
        item=_load_plan()[0],
        run_id="public-analysis-projection-test",
        index=1,
    )

    projected = analysis_v5._project_record_for_statistics(record)

    for field in (
        "case_id",
        "condition_id",
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
    ):
        assert projected[field] == record[field]
    assert "provider_trace_bundle" not in projected
    assert "provider_safety_receipt" not in projected
    assert projected["provider_attestation"]["identity_verified"] is True
    assert projected["provider_attestation"]["response_id"]
