from __future__ import annotations

import json
from collections import Counter

from experiments.paper_v2.research_assets import (
    ADAPTIVE_FREEZE,
    BLIND_KIT,
    PUBLIC_FREEZE,
    verify_assets,
)


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_public_freeze_has_expected_unique_case_condition_scale() -> None:
    freeze = _json(PUBLIC_FREEZE)
    cells = freeze["cells"]

    assert len(cells["primary_model_m3_v2"]["cases"]) == 450
    assert len(cells["primary_model_agentdojo_v1"]["cases"]) == 397
    assert len(cells["second_model_m3_v2"]["cases"]) == 300
    assert len(cells["second_model_agentdojo_v1"]["cases"]) == 297
    assert freeze["expected_case_condition_records"] == 6873
    assert all(
        len({row["case_id"] for row in cell["cases"]}) == len(cell["cases"])
        for cell in cells.values()
    )
    deviation = freeze["feasibility_deviations"][0]
    assert deviation["available_unique_benign"] == 97
    assert "do not duplicate" in deviation["resolution"]
    assert freeze["evidence_boundaries"]["results_status"] == "not_run"


def test_blind_kit_is_content_free_and_custodian_pending() -> None:
    slots = _jsonl(BLIND_KIT / "slots.jsonl")
    status = _json(BLIND_KIT / "status.json")

    assert len(slots) == 600
    assert Counter(row["sample_type"] for row in slots) == {
        "attack": 360,
        "benign_no_tool": 120,
        "benign_legal_tool": 120,
    }
    assert Counter(
        row["attack_family"] for row in slots if row["sample_type"] == "attack"
    ) == {
        family: 40
        for family in {
            "cross_tool_attack_chain",
            "direct_jailbreak",
            "environment_context_pollution",
            "json_rpc",
            "memory_poisoning",
            "multilingual_t2l",
            "obfuscation_evasion",
            "rag_indirect",
            "tool_output_injection",
        }
    }
    assert status["custodian"] is None
    assert status["candidate_present"] is False
    assert status["independent_blind_claim_allowed"] is False
    assert not (BLIND_KIT / "m3_paper_v2_independent_blind.jsonl").exists()


def test_adaptive_freeze_matches_preregistered_budget_panel() -> None:
    freeze = _json(ADAPTIVE_FREEZE)

    assert len(freeze["primary_model"]["tasks"]) == 40
    assert freeze["primary_model"]["budgets"] == [50, 200, 500]
    assert len(freeze["second_model"]["tasks"]) == 20
    assert freeze["second_model"]["budgets"] == [50, 200]
    assert freeze["hardest_subset"]["budget"] == 2000
    assert freeze["hardest_subset"]["case_ids"] == []
    assert freeze["maximum_query_budget"] == 75000
    assert freeze["result_status"] == "not_run"


def test_all_research_assets_reproduce_byte_for_byte() -> None:
    manifest = verify_assets()

    assert manifest["provider_calls_made"] == 0
    assert manifest["formal_results_created"] == 0
