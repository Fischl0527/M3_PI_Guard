from __future__ import annotations

from collections import Counter, defaultdict

import pytest

from experiments.paper_v2 import incremental_empirical_plan_v1 as subject


def test_incremental_plan_counts_and_factor_cells() -> None:
    value = subject.build_all()

    assert value["manifest"]["planned_counts"] == {
        "factorial_api_rows": 720,
        "provenance_api_rows": 240,
        "provenance_offline_decisions": 480,
        "challenge_api_rows": 240,
        "flash_api_rows": 360,
        "adaptive_tail_tasks": 12,
        "adaptive_tail_max_queries": 3600,
        "regular_api_rows_total": 1560,
    }
    assert Counter(row["condition_cell"] for row in value["factorial"]) == Counter(
        {
            "policy_normal": 180,
            "policy_safe": 180,
            "full_normal": 180,
            "full_safe": 180,
        }
    )
    assert sum(row["formal_prefix"] is True for row in value["factorial"]) == 8
    assert sum(row["formal_prefix"] is True for row in value["flash"]) == 8
    assert sum(row["formal_prefix"] is True for row in value["challenge"]) == 8


def test_factorial_and_flash_case_balance() -> None:
    value = subject.build_all()
    factorial_cases = {
        (row["benchmark"], row["case_id"]) for row in value["factorial"]
    }
    flash_cases = {(row["benchmark"], row["case_id"]) for row in value["flash"]}

    assert len(factorial_cases) == 180
    assert Counter(row["evaluation_case_type"] for row in value["factorial"]) == Counter(
        {"attack": 400, "benign_tool": 240, "benign_no_tool": 80}
    )
    assert len(flash_cases) == 90
    assert Counter(row["evaluation_case_type"] for row in value["flash"]) == Counter(
        {"attack": 200, "benign_tool": 120, "benign_no_tool": 40}
    )
    assert all(isinstance(row.get("selection_id"), str) for row in value["factorial"])
    assert all(isinstance(row.get("selection_id"), str) for row in value["flash"])
    assert all(isinstance(row.get("selection_id"), str) for row in value["challenge"])


def test_challenge_is_balanced_and_explicitly_outcome_enriched() -> None:
    value = subject.build_all()
    cases = value["challenge_cases"]
    rows = value["challenge"]

    assert Counter(case["benchmark"] for case in cases) == Counter(
        {"agentdojo-v1": 30, "m3-v2": 30}
    )
    assert all(case["prior_unsafe_condition_count"] >= 1 for case in cases)
    assert all(case["prior_outcome_selected"] is True for case in cases)
    assert all(row["prior_outcome_selected"] is True for row in rows)
    assert all(row["sample_role"] == "risk_enriched" for row in rows)
    assert all(row["evaluation_case_type"] == "attack" for row in rows)


def test_provenance_pairs_change_only_declared_source_placement() -> None:
    value = subject.build_all()
    by_base: dict[str, list[dict[str, object]]] = defaultdict(list)
    for case in value["provenance_cases"]:
        by_base[str(case["base_task_id"])].append(case)

    assert len(by_base) == 60
    assert Counter(case["benchmark_origin"] for case in value["provenance_cases"]) == Counter(
        {"agentdojo-v1": 60, "m3-v2": 60}
    )
    assert Counter(case["scenario_relation"] for case in value["provenance_cases"]) == Counter(
        {"supporting": 60, "competing": 60}
    )
    for variants in by_base.values():
        assert len(variants) == 2
        trusted = next(
            row for row in variants if row["source_authority_variant"] == "trusted_origin"
        )
        untrusted = next(
            row for row in variants if row["source_authority_variant"] == "untrusted_origin"
        )
        assert trusted["pair_invariant_sha256"] == untrusted["pair_invariant_sha256"]
        assert trusted["proposition_text"] == untrusted["proposition_text"]
        assert trusted["proposition_value"] == untrusted["proposition_value"]
        assert trusted["authorization_manifest"] == untrusted["authorization_manifest"]
        assert trusted["context_block_index"] == untrusted["context_block_index"] == 1
        assert trusted["serialized_context_block"]["text"] == untrusted["serialized_context_block"]["text"]
        assert trusted["serialized_context_block"]["source_authority"] == "trusted_app_context"
        assert untrusted["serialized_context_block"]["source_authority"] == "untrusted_memory"


def test_provenance_execution_and_replay_cells_are_complete() -> None:
    value = subject.build_all()
    api_rows = value["provenance"]
    replay_rows = value["provenance_replay"]

    assert len({row["work_key"] for row in api_rows}) == 240
    assert len({row["work_key"] for row in replay_rows}) == 480
    assert Counter(row["module_factor"] for row in api_rows) == Counter(
        {"policy": 120, "full": 120}
    )
    assert Counter(row["proposal_role"] for row in replay_rows) == Counter(
        {"authorized": 240, "unauthorized": 240}
    )
    assert sum(row["formal_prefix"] is True for row in api_rows) == 8


def test_adaptive_tail_is_balanced_and_conditional() -> None:
    rows = subject.build_all()["adaptive_tail"]

    assert len(rows) == 12
    assert Counter(row["attack_family"] for row in rows) == Counter(
        {"A1": 4, "A2": 4, "A3": 4}
    )
    assert all(row["start_query"] == 201 for row in rows)
    assert all(row["end_query"] == 500 for row in rows)
    assert all(row["stop_after_first_unsafe_effect"] is True for row in rows)
    assert all(
        row["selection_condition"] == "no_unsafe_effect_through_query_200"
        for row in rows
    )
    assert sum(row["formal_prefix_query_count"] for row in rows) == 10


def test_frozen_incremental_plan_reproduces() -> None:
    observed = subject.verify_plan()
    assert observed["status"] == "design_frozen_execution_pending"
    assert observed["automatic_retries"] == 0
    assert observed["provider_tools_enabled"] is False
    assert observed["real_external_effects_enabled"] is False
    assert observed["gemini_execution_planned"] is False
    assert observed["budget_fuses_cny"] == {
        "pro": 8.0,
        "flash": 3.0,
        "adaptive": 5.0,
        "global": 16.0,
    }


def test_challenge_candidate_audit_fails_closed_on_condition_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "CHALLENGE_PRIOR_CONDITIONS", frozenset())
    with pytest.raises(subject.IncrementalPlanError, match="candidate audit drift"):
        subject._prior_unsafe_cells()
