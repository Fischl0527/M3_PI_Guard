import pytest

from experiments.paper_v2.authorization_usability_diagnostics_v1 import (
    approval_probes,
    constraint_probes,
    latest_rows,
    provenance_probes,
    read_rows,
    summarize,
)
from experiments.paper_v2.incremental_empirical_plan_v1 import PROVENANCE_CASES


def record(key="a", attempt=1, response=True, **extra):
    return dict(
        work_key=key,
        attempt=attempt,
        response_obtained=response,
        operational_status="completed",
        task_completion=False,
        **extra,
    )


def test_latest_preserves_denominator_and_rejects_duplicate_attempt():
    rows = [record(response=False), record(attempt=2)]
    assert len(latest_rows(rows)) == 1
    with pytest.raises(ValueError, match="duplicate"):
        latest_rows([record(), record()])
    with pytest.raises(ValueError, match="response-bearing"):
        latest_rows([record(), record(attempt=2)])


def test_unobserved_reason_and_action_counts_are_not_fabricated():
    result = summarize([record(ask_count=1), record(key="b", deny_count=1)], 3)
    assert result["missing_planned"] == 1
    cell = result["cells"][0]
    assert cell["denominator"] == 2
    assert cell["reason_trace_available"] == cell["action_count_available"] == 0
    assert sum(cell["observed_partition"].values()) == 2
    assert "not_available" in result["guard_reason_retrospective_attribution"]


def test_probes_leave_frozen_cases_unchanged():
    cases = read_rows(PROVENANCE_CASES)
    import copy

    before = copy.deepcopy(cases)
    probes = constraint_probes(cases)
    assert len(probes) == 480
    assert cases == before
    assert all(p["provider_calls"] == p["real_effects"] == 0 for p in probes)
    nuisance = [
        p
        for p in probes
        if p["probe_family"] == "nuisance_content_changed" and p["module"] == "policy"
    ]
    assert all(p["decision"] == "ASK" for p in nuisance)


def test_literal_attribution_is_not_authorization_or_causal_provenance():
    probes = provenance_probes()
    assert len(probes) == 28
    negative = next(
        p
        for p in probes
        if p["probe_family"] == "negated_trusted_mention"
        and p["policy_granularity"] == "exact_target"
        and p["module"] == "full"
    )
    assert negative["argument_source_summary"]["arguments.to"] == "trusted_user"
    assert negative["decision"] == "ASK"
    assert not negative["unauthorized_allow"]
    broad = next(
        p
        for p in probes
        if p["probe_family"] == "negated_trusted_mention"
        and p["policy_granularity"] == "broad_target"
        and p["module"] == "full"
    )
    assert broad["unauthorized_allow"]


def test_legacy_approval_limitations_are_observed_not_hidden():
    probes = approval_probes()
    assert probes[0]["decision"] == "ASK"
    assert all(p["decision"] == "ALLOW" for p in probes[1:])
    assert all(p["evidence_layer"].startswith("new_deterministic") for p in probes)
