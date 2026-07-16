from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_final_analysis import generate_final_analysis
from scripts.validate_final_statistics import (
    audit_final_analysis,
    independent_holm,
    independent_mcnemar_exact,
    validate_statistical_contract,
)
from tests.unit.test_build_final_analysis import (
    _install_synthetic_corrected_e17_loader,
    _make_repository,
)


@pytest.fixture(autouse=True)
def _synthetic_corrected_e17_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_synthetic_corrected_e17_loader(monkeypatch)


def _representative_statistics() -> dict:
    return {
        "comparisons": [
            {
                "paired_statistics": {
                    "ASR_mcnemar": {
                        "method": "mcnemar_exact",
                        "pairs": 10,
                        "baseline_only_event": 3,
                        "treatment_only_event": 0,
                        "discordant_pairs": 3,
                        "p_value": 0.25,
                        "holm_adjusted_p": 0.25,
                    },
                    "ASR_bootstrap_guard_minus_baseline": {
                        "method": "clustered_paired_bootstrap",
                        "iterations": 10_000,
                        "seed": 42,
                        "clusters": 2,
                        "pairs": 10,
                        "estimate": -0.3,
                        "ci_low": -0.5,
                        "ci_high": -0.1,
                    },
                    "latency_wilcoxon": {
                        "method": "wilcoxon_signed_rank_exact",
                        "pairs": 4,
                        "nonzero_pairs": 3,
                        "zero_pairs": 1,
                        "w_plus": 5.0,
                        "w_minus": 1.0,
                        "statistic": 1.0,
                        "p_value": 0.25,
                        "rank_biserial": 2.0 / 3.0,
                    },
                }
            }
        ],
        "holm_correction": [
            {"test": "ASR_mcnemar", "p_value": 0.25, "holm_adjusted_p": 0.25},
            {"test": "latency_wilcoxon", "p_value": 0.05, "holm_adjusted_p": 0.10},
        ],
    }


def test_independent_exact_mcnemar_and_holm_recomputations() -> None:
    assert independent_mcnemar_exact(3, 0) == 0.25
    adjusted = independent_holm([0.25, 0.05])
    assert adjusted == [0.25, 0.10]


def test_full_paired_statistics_contract_passes() -> None:
    result = validate_statistical_contract(_representative_statistics())
    assert result["status"] == "pass"
    assert result["method_counts"] == {
        "mcnemar": 1,
        "bootstrap": 1,
        "wilcoxon": 1,
        "holm_families": 1,
    }
    assert {row["check"] for row in result["findings"]} == {
        "mcnemar_exact_recompute",
        "clustered_paired_bootstrap_contract",
        "wilcoxon_algebra_and_effect_contract",
        "holm_family_recompute",
    }


def test_contract_rejects_corrupt_mcnemar_and_holm_values() -> None:
    payload = _representative_statistics()
    paired = payload["comparisons"][0]["paired_statistics"]
    paired["ASR_mcnemar"]["p_value"] = 0.50
    payload["holm_correction"][1]["holm_adjusted_p"] = 0.05
    result = validate_statistical_contract(payload)
    assert result["status"] == "fail"
    failures = [row for row in result["findings"] if row["status"] == "fail"]
    assert {row["check"] for row in failures} == {
        "mcnemar_exact_recompute",
        "holm_family_recompute",
    }


def test_audit_emits_material_passport_key_recomputations_and_11_fallacies(
    tmp_path: Path,
) -> None:
    root, registry = _make_repository(tmp_path)
    output = root / "final"
    generate_final_analysis(registry_path=registry, repository_root=root, output_dir=output)
    before_manifest = (output / "manifest.json").read_bytes()

    report = audit_final_analysis(analysis_dir=output, repository_root=root)

    assert report["verification_status"]["label"] == "PASS_WITH_LIMITATIONS"
    assert report["material_passport"]["reproducibility"]["input_bundle_read_only"] is True
    assert report["material_passport"]["reproducibility"][
        "independent_of_synthesis_builder_imports"
    ] is True
    assert report["checks"]["final_artifact_integrity"]["status"] == "pass"
    assert report["checks"]["input_ledger_integrity"]["status"] == "pass"
    assert report["key_recomputations"]["E9_unresolved_denominator"] == {
        "status": "pass",
        "source": "evidence/E9/context_position.csv",
        "unresolved_runs": 5,
        "case_runs": 20,
        "rate": 0.25,
    }
    assert report["key_recomputations"]["E13_frozen_threshold_constraints"][
        "all_constraints_pass"
    ] is True
    assert report["key_recomputations"]["acceptance_matrix"]["status"] == "pass"
    assert len(report["statistical_fallacy_audit"]) == 11
    assert [item["id"] for item in report["statistical_fallacy_audit"]] == [
        f"SF{index:02d}" for index in range(1, 12)
    ]
    assert (output / "manifest.json").read_bytes() == before_manifest


def test_material_passport_is_json_serializable(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    output = root / "final"
    generate_final_analysis(registry_path=registry, repository_root=root, output_dir=output)
    report = audit_final_analysis(analysis_dir=output, repository_root=root)
    rendered = json.dumps(report, ensure_ascii=False)
    assert '"material_passport"' in rendered
    assert '"verification_status"' in rendered
