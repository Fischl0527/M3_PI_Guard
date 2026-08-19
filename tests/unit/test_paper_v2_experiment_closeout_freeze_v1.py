from __future__ import annotations

import copy
import hashlib
from collections import Counter

import experiments.paper_v2.experiment_closeout_freeze_v1 as freeze
from experiments.paper_v2.contracts import canonical_json_bytes


def test_gemini_public_plan_is_an_exact_paired_mirror() -> None:
    source = freeze._public_source_rows()
    rows = freeze.build_gemini_public_plan()

    assert len(rows) == 1791
    assert len({row["work_key"] for row in rows}) == 1791
    assert [row["source_work_key"] for row in rows] == [
        row["work_key"] for row in source
    ]
    assert [row["sequence"] for row in rows] == [
        row["sequence"] for row in source
    ]
    assert all(row["provider_id"] == "gemini" for row in rows)
    assert all(row["model_id"] == "gemini-3.6-flash" for row in rows)
    for source_row, mirrored in zip(source, rows, strict=True):
        assert freeze._paired_projection(source_row) == freeze._paired_projection(
            mirrored
        )


def test_gemini_public_counts_and_policy_are_frozen() -> None:
    manifest = freeze.build_gemini_public_manifest()

    assert manifest["counts"] == {
        "records": 1791,
        "conditions": {
            "m3_full": 597,
            "m3_policy_only": 597,
            "strongest_peer_reviewed_structural_baseline": 597,
        },
        "benchmarks": {"agentdojo-v1": 891, "m3-v2": 900},
        "record_kinds": {"attack": 1200, "benign": 591},
        "evaluation_case_types": {
            "attack": 1200,
            "benign_no_tool": 156,
            "benign_tool": 435,
        },
    }
    assert manifest["execution_policy"]["canary_records"] == 12
    assert manifest["execution_policy"]["maximum_shards"] == 4
    assert manifest["execution_policy"]["paid_ceiling_usd"] == 0
    assert manifest["execution_policy"]["automatic_retries"] == 0
    assert manifest["network_calls_made"] == 0


def test_adaptive_v1_is_not_mutated_and_v2_adds_only_paired_gemini_tasks() -> None:
    before = freeze.ADAPTIVE_V1.read_bytes()
    base = freeze._read_json(freeze.ADAPTIVE_V1)
    extension = freeze.build_adaptive_extension()
    after = freeze.ADAPTIVE_V1.read_bytes()

    assert before == after
    assert hashlib.sha256(before).hexdigest() == extension["base_freeze"]["sha256"]
    assert extension["maximum_query_budget"] == 79000
    assert len(extension["models"]["deepseek_pro"]["tasks"]) == 40
    assert len(extension["models"]["deepseek_flash"]["tasks"]) == 20
    assert extension["models"]["gemini_flash"]["tasks"] == base["second_model"]["tasks"]
    assert extension["formal_prefix"]["terminal_query_count"] == 374
    assert sorted(extension["formal_prefix"]["query_counts_by_case"].values()) == [
        24,
        50,
        50,
        50,
        50,
        50,
        50,
        50,
    ]
    assert extension["provider_policy"]["automatic_retries"] == 0
    assert extension["provider_policy"]["external_effects_enabled"] is False


def test_historical_v7_is_verified_without_mutation_or_resume() -> None:
    before = freeze.V7_ABORT_REVIEW.read_bytes()
    audit = freeze.build_v7_immutable_audit()

    assert freeze.V7_ABORT_REVIEW.read_bytes() == before
    assert audit["status"] == "verified_historical_failure_closed_nonresumable"
    assert audit["record_count"] == 0
    assert audit["open_attempt_count"] == 1
    assert audit["provider_calls_completed"] == 2
    assert audit["prior_run_resumable"] is False
    assert audit["rerun_authorized"] is False
    assert audit["network_calls_made"] == 0


def test_blind_interface_has_600_slots_but_no_developer_authored_candidate() -> None:
    interface = freeze.build_blind_interface()
    slots = freeze._read_jsonl(freeze.BLIND_KIT / "slots.jsonl")

    assert len(slots) == 600
    assert Counter(row["sample_type"] for row in slots) == {
        "attack": 360,
        "benign_legal_tool": 120,
        "benign_no_tool": 120,
    }
    assert Counter(row["independent_author_group"] for row in slots) == {
        1: 300,
        2: 300,
    }
    assert interface["status"].startswith("blocked_external_custodian")
    assert interface["slot_counts"]["closeout_strata"] == {
        "attack": 360,
        "benign_tool": 120,
        "benign_no_tool": 120,
    }
    assert interface["execution_contract"]["expected_records"] == 3600
    assert interface["claim_policy"]["independent_blind_claim_allowed_now"] is False


def test_manifest_hashes_are_content_bound() -> None:
    for value in (
        freeze.build_gemini_public_manifest(),
        freeze.build_adaptive_extension(),
        freeze.build_v7_immutable_audit(),
        freeze.build_blind_interface(),
        freeze.build_closeout_candidate(),
    ):
        observed = value["manifest_sha256"]
        core = copy.deepcopy(value)
        del core["manifest_sha256"]
        expected = hashlib.sha256(canonical_json_bytes(core)).hexdigest()
        assert observed == expected
