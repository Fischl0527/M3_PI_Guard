from __future__ import annotations

import experiments.paper_v2.adaptive_cost_canary_abort_review_v1 as abort_v1


def test_adaptive_v1_abort_review_is_outcome_blind_and_nonresumable() -> None:
    value = abort_v1.build_abort_review()

    assert value["status"] == (
        "adaptive_v1_aborted_after_one_terminal_query_result_ineligible"
    )
    assert value["operational_summary"]["terminal_query_count"] == 1
    assert value["operational_summary"]["provider_calls_completed"] == 1
    assert value["operational_summary"]["open_query_count"] == 0
    assert value["integrity_checks"]["query_and_provider_call_cross_bound"]
    assert value["evidence_boundary"]["old_root_resumable"] is False
    assert (
        value["evidence_boundary"]["old_query_reusable_in_fresh_result"]
        is False
    )
    assert (
        value["evidence_boundary"]["scientific_outcomes_aggregated"]
        is False
    )
    assert (
        value["evidence_boundary"]["scientific_outcome_fields_reported"]
        is False
    )
