from __future__ import annotations

from experiments.paper_v2.provider_trace_runtime_qualification import (
    build_qualification,
)


def test_live_per_call_v2_wiring_is_zero_network_and_itt_complete() -> None:
    value = build_qualification()

    assert value["status"] == "live_per_call_v2_wiring_qualified"
    assert value["scenario_count"] == 4
    assert value["formal_candidate_records"] == 2
    assert value["diagnostic_itt_failure_records"] == 2
    assert value["vigil_success_request_count"] == 2
    assert value["completed_calls_with_cache_cost_evidence"] == 3
    assert value["all_completed_calls_have_cache_cost_evidence"] is True
    assert value["vigil_preparation_failure_retained"] is True
    assert value["agent_provider_failure_retained"] is True
    assert value["append_flush_fsync_before_every_transport"] is True
    assert value["automatic_retry"] is False
    assert value["hash_chain_complete"] is True
    assert value["network_calls_made"] == 0
    assert value["external_effects"] is False
    assert value["formal_results_created"] == 0
