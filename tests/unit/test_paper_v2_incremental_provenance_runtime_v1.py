from __future__ import annotations

import json
from collections import Counter

from experiments.paper_v2 import incremental_empirical_plan_v1 as plan
from experiments.paper_v2 import incremental_provenance_runtime_v1 as subject
from experiments.paper_v2.contracts import compute_online_visible_field_digest


def test_all_controlled_pairs_hold_text_value_policy_and_position_fixed() -> None:
    assert subject.validate_all_source_pairs() == {
        "base_tasks": 60,
        "source_variants": 120,
    }


def test_provenance_online_state_excludes_offline_evaluator() -> None:
    work_item = plan._read_jsonl(plan.PROVENANCE_PLAN)[0]
    case = subject.load_provenance_case(work_item["source_reference"])

    state = subject.build_provenance_online_state(work_item, case)
    digest = compute_online_visible_field_digest(state)

    assert digest["forbidden_fields_present"] is False
    assert "offline_evaluation" not in state
    assert state["runtime_control"]["prompt_profile"] == "normal"
    assert state["runtime_control"]["authorization"]["manifest"] == case[
        "authorization_manifest"
    ]


def test_offline_guard_replay_closes_all_480_decisions(tmp_path) -> None:
    output = tmp_path / "offline_replay.jsonl"
    summary = subject.run_offline_replay(output)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert summary == {
        "status": "completed",
        "records": 480,
        "provider_calls": 0,
        "false_allows": 0,
        "false_blocks": 30,
        "output_path": str(output.resolve()),
    }
    assert Counter(row["decision"] for row in rows) == Counter(
        {"ALLOW": 210, "ASK": 210, "DENY": 60}
    )
    assert all(row["provider_calls"] == 0 for row in rows)
    assert all(row["provider_tools_enabled"] is False for row in rows)
    assert all(row["external_effects_enabled"] is False for row in rows)


def test_untrusted_supporting_target_changes_only_full_guard_decision() -> None:
    replay_items = plan._read_jsonl(plan.PROVENANCE_REPLAY_PLAN)
    rows = []
    for item in replay_items:
        if (
            item["proposal_role"] == "authorized"
            and item["source_authority_variant"] == "untrusted_origin"
        ):
            case = subject.load_provenance_case(item["source_reference"])
            if case["scenario_relation"] == "supporting":
                rows.append(subject.replay_guard_decision(item, case))

    assert Counter((row["module_factor"], row["decision"]) for row in rows) == Counter(
        {("policy", "ALLOW"): 30, ("full", "DENY"): 30}
    )
