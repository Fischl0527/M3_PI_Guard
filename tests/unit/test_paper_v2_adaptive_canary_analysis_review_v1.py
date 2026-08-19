from __future__ import annotations

import experiments.paper_v2.adaptive_canary_analysis_review_v1 as review


def test_adaptive_canary_analysis_integrity_review_passes() -> None:
    value = review.verify_review()

    assert value["status"] == "adaptive_canary_analysis_integrity_pass"
    assert all(value["checks"].values())
    assert value["task_count"] == 8
    assert value["unsafe_effect_successes"] == 0
    assert value["unsafe_effect_rate_at_50"]["value"] == 0.0
    assert value["interpretation_boundary"]["sota_claim_authorized"] is False
