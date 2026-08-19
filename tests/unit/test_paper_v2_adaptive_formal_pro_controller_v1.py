from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import experiments.paper_v2.adaptive_formal_plan_v2 as plan
import experiments.paper_v2.adaptive_formal_pro_controller_v1 as controller
from experiments.paper_v2.contracts import sha256_canonical_json


def test_pro_50_candidate_authorizes_only_untouched_tasks() -> None:
    candidate = controller.build_stage_candidate("pro_50")
    scope = candidate["scope"]
    prefix_cases = set(controller._base_checkpoint_locks())

    assert scope["target_budget"] == 50
    assert scope["authorized_task_count"] == 32
    assert not prefix_cases.intersection(scope["authorized_case_ids"])
    assert scope["cumulative_diagnostic_case_ids"] == ["M3V2-D-050-A1"]
    assert scope["historical_prefix_cost_cny"] == 0.552805
    assert scope["projected_pro_ceiling_cny"] < 180.0
    assert scope["reserved_flash_stage_ceiling_cny"] > 0
    assert scope["projected_total_ceiling_cny"] == 180.0
    assert candidate["execution_controls"]["automatic_retries"] == 0
    assert candidate["execution_controls"]["external_effects_enabled"] is False


def test_stage_command_and_admission_bind_the_approved_boundary() -> None:
    controller.write_stage_candidate("pro_50")
    admission = controller.build_stage_admission(
        "pro_50",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
        approved_at="2026-08-02T03:05:00+08:00",
    )

    assert "--stage pro_50" in admission["exact_command"]
    assert "--execute-stage" in admission["exact_command"]
    assert admission["authorization"]["terminal_query_replay_authorized"] is False
    assert admission["authorization"]["provider_tools_enabled"] is False
    assert admission["authorization"]["result_admission_authorized"] is False


def test_stage_candidate_rejects_scope_tampering() -> None:
    candidate = controller.build_stage_candidate("pro_50")
    tampered = copy.deepcopy(candidate)
    tampered["scope"]["stage_hard_limit_cny"] = 181.0
    tampered["scope_sha256"] = sha256_canonical_json(tampered["scope"])
    core = {key: value for key, value in tampered.items() if key != "manifest_sha256"}
    tampered["manifest_sha256"] = sha256_canonical_json(core)

    with pytest.raises(controller.AdaptiveFormalProControllerV1Error):
        controller.validate_stage_candidate(tampered, stage="pro_50")


def test_role_policy_expands_only_the_cost_ceiling() -> None:
    policy = controller.adaptive_role_policy("pro_50")

    assert policy["deepseek"]["model_id"] == plan.MODEL_ID
    assert policy["deepseek"]["hard_spend_limit_cny"] == 10.0
    assert policy["deepseek"]["abort_ceiling_cny"] == 10.0
    assert policy["common_controls"]["automatic_retries"] == 0


def test_pro_technical_gate_requires_affirmative_outcome_boundary() -> None:
    assert controller._technical_checks_pass(
        {
            "all_authorized_tasks_terminal": True,
            "scientific_outcomes_not_aggregated": True,
        }
    )

    with pytest.raises(
        controller.AdaptiveFormalProControllerV1Error,
        match="affirmative invariants",
    ):
        controller._technical_checks_pass(
            {
                "all_authorized_tasks_terminal": True,
                "scientific_outcomes_aggregated": False,
            }
        )


def _checkpoint(path: Path, *, first_success: int | None, count: int = 500) -> None:
    queries = [
        {"query": index, "unsafe_effect": index == first_success}
        for index in range(1, count + 1)
    ]
    path.write_text(
        json.dumps(
            {"queries": queries, "first_success_query": first_success},
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_hardest_amendment_is_bound_before_new_outcomes() -> None:
    amendment = controller.verify_hardest_amendment()

    assert amendment["manifest_sha256"] == (
        controller.HARDEST_AMENDMENT_MANIFEST_SHA256
    )
    assert amendment["outcome_controls"][
        "scientific_outcomes_read_before_freeze"
    ] is False
    assert amendment["eligible_population"][
        "terminal_queries_may_be_retried"
    ] is False


def test_hardest_ranking_excludes_diagnostic_and_replenishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(controller, "PROJECT_ROOT", tmp_path)
    paths = {}
    for case_id, first in {
        "no-success-a": None,
        "no-success-b": None,
        "late-success": 499,
        "early-success": 400,
        "diagnostic": None,
    }.items():
        path = tmp_path / f"{case_id}.json"
        _checkpoint(path, first_success=first)
        paths[case_id] = controller._checkpoint_lock(path)

    ranked = controller._rank_hardest_checkpoints(
        list(paths.values()),
        diagnostic_case_ids=["diagnostic"],
        tie_break_seed="fixed-seed",
    )

    assert {row["case_id"] for row in ranked[:2]} == {
        "no-success-a",
        "no-success-b",
    }
    assert [row["case_id"] for row in ranked[2:]] == [
        "late-success",
        "early-success",
    ]
    assert "diagnostic" not in {row["case_id"] for row in ranked}
    assert [row["rank"] for row in ranked] == [1, 2, 3, 4]


def test_hardest_ranking_rejects_incomplete_no_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(controller, "PROJECT_ROOT", tmp_path)
    path = tmp_path / "incomplete.json"
    _checkpoint(path, first_success=None, count=499)

    with pytest.raises(
        controller.AdaptiveFormalProControllerV1Error,
        match="incomplete no-success checkpoint",
    ):
        controller._rank_hardest_checkpoints(
            [controller._checkpoint_lock(path)],
            diagnostic_case_ids=[],
            tie_break_seed="fixed-seed",
        )
