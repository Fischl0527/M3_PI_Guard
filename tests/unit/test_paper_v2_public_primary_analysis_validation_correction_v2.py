from __future__ import annotations

import experiments.paper_v2.public_primary_analysis_v1 as base
import experiments.paper_v2.public_primary_analysis_validation_correction_v2 as correction
import experiments.paper_v2.public_primary_analysis_v2 as analysis_v2
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.contracts_v2 import validate_experiment_record_v2


def test_correction_candidate_is_bounded_and_uses_new_output_root(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        correction.admission_v1,
        "validate_admission",
        lambda value: {"manifest_sha256": "a" * 64},
    )
    monkeypatch.setattr(
        correction.admission_v1,
        "verify_candidate",
        lambda: {"manifest_sha256": "b" * 64},
    )
    monkeypatch.setattr(
        correction.admission_v1,
        "_record_paths",
        lambda: [],
    )
    candidate = correction.build_candidate()

    assert candidate["scope"]["record_count"] == 5082
    assert candidate["scope"]["source_record_schema"].endswith("2.2")
    assert candidate["authorization"] == {
        "candidate_only": True,
        "corrected_analysis_authorized": False,
        "new_provider_execution_authorized": False,
        "record_mutation_authorized": False,
        "automatic_retries": 0,
    }
    assert candidate["scope"]["analysis_output_root"].endswith(
        "primary_analysis_v2"
    )
    assert "public_primary_analysis_v2" in correction.canonical_command()


def test_analysis_wrapper_changes_only_validation_and_provenance(
    monkeypatch,
) -> None:
    admission_sha = "a" * 64

    def fake_report(*args, **kwargs):
        del args, kwargs
        core = {"schema_version": "old", "status": "complete"}
        return {
            **core,
            "manifest_sha256": sha256_canonical_json(core),
        }, [{"condition_id": "m3_full"}]

    monkeypatch.setattr(base, "_analysis_report", fake_report)
    monkeypatch.setattr(
        base,
        "_m3_validator_correction_v2",
        False,
        raising=False,
    )

    analysis_v2._configure({"manifest_sha256": admission_sha})
    summary, rows = base._analysis_report([], [], admission={}, candidate={}, merge={})

    assert base.validate_experiment_record is validate_experiment_record_v2
    assert base.SCHEMA_VERSION == analysis_v2.SCHEMA_VERSION
    assert summary[
        "analysis_validation_correction_admission_sha256"
    ] == admission_sha
    assert summary["manifest_sha256"] == sha256_canonical_json(
        {
            key: value
            for key, value in summary.items()
            if key != "manifest_sha256"
        }
    )
    assert rows == [{"condition_id": "m3_full"}]
