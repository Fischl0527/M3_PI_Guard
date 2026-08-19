from __future__ import annotations

import experiments.paper_v2.public_primary_analysis_v1 as base
import experiments.paper_v2.public_primary_analysis_validation_correction_v3 as correction
import experiments.paper_v2.public_primary_analysis_v3 as analysis_v3


def test_v3_candidate_selects_public_validator_without_provider_actions(
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
    candidate = correction.build_candidate()

    assert candidate["scope"]["record_count"] == 5082
    assert candidate["scope"]["corrected_validator"].endswith(
        "validate_public_experiment_record"
    )
    assert candidate["scope"]["role_policy_builder"].endswith(
        "build_role_policy(primary)"
    )
    assert candidate["authorization"] == {
        "candidate_only": True,
        "corrected_analysis_authorized": False,
        "new_provider_execution_authorized": False,
        "record_mutation_authorized": False,
        "automatic_retries": 0,
    }
    assert "public_primary_analysis_v3" in correction.canonical_command()


def test_v3_record_validator_uses_frozen_primary_role_policy(
    monkeypatch,
) -> None:
    observed = {}

    def fake_validate(record, *, role_policy):
        observed["record"] = record
        observed["role_policy"] = role_policy

    monkeypatch.setattr(
        analysis_v3,
        "validate_public_experiment_record",
        fake_validate,
    )
    analysis_v3._validate_public_record({"record_id": "record-1"})

    assert observed["record"] == {"record_id": "record-1"}
    assert observed["role_policy"]["public_model_role"] == "primary"
    assert observed["role_policy"]["deepseek"]["model_id"] == "deepseek-v4-pro"


def test_v3_configures_new_output_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        base,
        "_m3_public_validator_correction_v3",
        True,
        raising=False,
    )
    analysis_v3._configure({"manifest_sha256": "d" * 64})

    assert base.validate_experiment_record is analysis_v3._validate_public_record
    assert base.SUMMARY_NAME == analysis_v3.SUMMARY_NAME
    assert base.CONDITION_CSV_NAME == analysis_v3.CONDITION_CSV_NAME
    assert base.SCHEMA_VERSION == analysis_v3.SCHEMA_VERSION
