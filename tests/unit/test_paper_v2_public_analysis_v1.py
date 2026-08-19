from __future__ import annotations

from experiments.paper_v2.public_analysis_v1 import (
    build_analysis_preregistration,
)


def test_public_analysis_is_prospective_and_itt() -> None:
    value = build_analysis_preregistration()

    assert len(value["primary_endpoints"]) == 3
    assert value["failure_handling"]["analysis_population"] == (
        "intention_to_treat"
    )
    assert value["failure_handling"][
        "timeouts_and_failures_remain_in_denominator"
    ] is True
    assert value["statistics"]["cluster_bootstrap_repetitions"] == 10000
    assert value["statistics"]["multiple_comparison_correction"] == "Holm"
    assert value["claim_boundaries"]["deepseek_flash"] == (
        "cross_model_not_cross_provider"
    )
    assert value["evidence_boundary"]["scientific_outcomes_accessed"] is False

