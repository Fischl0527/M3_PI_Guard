from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.adaptive_cost_canary_plan_v1 import (
    MAX_QUERIES,
    AdaptiveCostCanaryPlanError,
    all_query_work_keys,
    build_query_work_item_and_state,
    resolve_candidate_task,
    verify_candidate,
)
from experiments.paper_v2.contracts import (
    compute_online_visible_field_digest,
    sha256_canonical_json,
)


def test_adaptive_cost_candidate_is_frozen_and_family_balanced() -> None:
    candidate = verify_candidate()
    tasks = candidate["scope"]["tasks"]

    assert candidate["execution_authorization"] == {
        "canary_execution_authorized": False,
        "credentials_read": False,
        "formal_continuation_authorized": False,
        "network_calls_made": 0,
        "result_admission_authorized": False,
    }
    assert len(tasks) == 8
    assert len({task["attack_family"] for task in tasks}) == 8
    assert len(all_query_work_keys(tasks)) == MAX_QUERIES
    assert len(set(all_query_work_keys(tasks))) == MAX_QUERIES


def test_adaptive_query_changes_only_untrusted_content() -> None:
    candidate = verify_candidate()
    case_id = candidate["scope"]["tasks"][0]["case_id"]
    _, source = resolve_candidate_task(candidate, case_id)
    trusted_before = sha256_canonical_json(
        {
            "trusted_user_request": source["trusted_user_request"],
            "trusted_app_context": source["trusted_app_context"],
            "untrusted_memory": source["untrusted_memory"],
        }
    )

    work_item, state = build_query_work_item_and_state(
        candidate,
        case_id=case_id,
        query_index=1,
        mutated_payload="OUTCOME-BLIND ADAPTIVE MUTATION",
    )

    assert state["agent_input"]["untrusted_content"] == (
        "OUTCOME-BLIND ADAPTIVE MUTATION"
    )
    assert sha256_canonical_json(
        {
            "trusted_user_request": state["agent_input"][
                "trusted_user_request"
            ],
            "trusted_app_context": state["agent_input"][
                "trusted_app_context"
            ],
            "untrusted_memory": state["agent_input"][
                "untrusted_memory"
            ],
        }
    ) == trusted_before
    assert state["runtime_control"]["authorization"][
        "authorization_regime"
    ] == "auto_compiled"
    assert compute_online_visible_field_digest(state)[
        "forbidden_fields_present"
    ] is False
    assert work_item["initial_online_visible_field_digest"] == (
        compute_online_visible_field_digest(state)
    )


def test_adaptive_query_rejects_out_of_range_index() -> None:
    candidate = verify_candidate()
    case_id = candidate["scope"]["tasks"][0]["case_id"]

    with pytest.raises(
        AdaptiveCostCanaryPlanError,
        match="out of range",
    ):
        build_query_work_item_and_state(
            candidate,
            case_id=case_id,
            query_index=51,
            mutated_payload="mutation",
        )


def test_adaptive_candidate_verification_rejects_drift(
    tmp_path,
) -> None:
    candidate = verify_candidate()
    drifted = copy.deepcopy(candidate)
    drifted["scope"]["maximum_queries"] = 401
    path = tmp_path / "candidate.json"
    import json

    path.write_text(
        json.dumps(drifted, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(
        AdaptiveCostCanaryPlanError,
        match="candidate drift",
    ):
        verify_candidate(path)
