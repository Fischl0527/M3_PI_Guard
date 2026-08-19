from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import pytest

import experiments.paper_v2.adaptive_cost_canary_controller_v2 as canary_v2
import experiments.paper_v2.adaptive_cost_canary_plan_v1 as plan_v1
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    AdaptiveQueryLedger,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
)
from experiments.paper_v2.public_deepseek_client_v1 import (
    PublicDeepSeekJsonOfficialClient,
)
from experiments.paper_v2.public_execution_store_v1 import (
    PublicBudgetTracker,
)


def _transport(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> HTTPResponseEnvelope:
    del endpoint, headers, timeout
    return HTTPResponseEnvelope(
        status_code=200,
        headers={"x-request-id": "adaptive-v2-request"},
        body={
            "id": "adaptive-v2-response",
            "model": payload["model"],
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"tool":"final","arguments":'
                            '{"answer":"QUALIFIED"}}'
                        )
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 20,
            },
        },
    )


def _as_official_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    value = copy.deepcopy(dict(receipt))
    evidence = value["evidence"]
    evidence["transport_kind"] = "official_network"
    evidence["identity_verified"] = True
    evidence["request_trace_complete"] = True
    evidence["evidence_level"] = (
        "official_exact_model_with_request_and_response_ids"
    )
    evidence["requested_at"] = "2026-07-30T02:05:00+08:00"
    evidence["model_latency_ms"] = 0.0
    value["evidence_sha256"] = sha256_canonical_json(evidence)
    return value


def test_fresh_candidate_excludes_v1_query_record() -> None:
    value = canary_v2.build_candidate()

    assert value["scope"]["run_id"] == "adaptive-cost-canary-primary-v2"
    assert value["scope"]["output_root"].endswith(
        "adaptive_cost_canary_v2/primary"
    )
    assert value["scope"]["recovery"]["old_v1_query_records_reused"] is False
    assert value["scope"]["recovery"]["decision_field"] == (
        "initial_guard_decision"
    )
    assert value["scope"]["budget"][
        "projected_adaptive_total_ceiling_cny"
    ] == 5.002271
    assert value["authorization"]["canary_execution_authorized"] is False


@pytest.mark.parametrize("decision", ["ALLOW", "ASK", "DENY"])
def test_oracle_decision_uses_record_contract_field(decision: str) -> None:
    record = {
        "result_tier": "formal_candidate",
        "initial_guard_decision": decision,
        "effective_guard_decision": "INVALID-LEGACY-FIELD",
    }

    assert canary_v2._oracle_decision(record) == decision


def test_oracle_decision_rejects_legacy_field_only() -> None:
    with pytest.raises(
        canary_v2.AdaptiveCostCanaryV2Error,
        match="initial guard decision",
    ):
        canary_v2._oracle_decision(
            {
                "result_tier": "formal_candidate",
                "effective_guard_decision": "ALLOW",
            }
        )


def test_admission_binds_exact_fresh_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = canary_v2.build_candidate()
    monkeypatch.setattr(
        canary_v2,
        "verify_candidate",
        lambda: copy.deepcopy(candidate),
    )

    value = canary_v2.build_canary_admission(
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-30T02:10:00+08:00",
    )

    assert value["scope"]["run_id"] == "adaptive-cost-canary-primary-v2"
    assert "--execute-canary" in value["scope"]["exact_command"]
    assert "controller_v2" in value["scope"]["exact_command"]
    assert value["evidence_boundary"]["automatic_retries"] == 0
    assert value["evidence_boundary"]["old_v1_query_records_reused"] is False
    assert value["authorization"]["result_admission_authorized"] is False


def test_v2_oracle_qualifies_end_to_end_without_network(
    tmp_path: Path,
) -> None:
    candidate = canary_v2.build_candidate()
    case_id = candidate["scope"]["tasks"][0]["case_id"]
    work_item, _ = plan_v1.build_query_work_item_and_state(
        candidate,
        case_id=case_id,
        query_index=1,
        mutated_payload="offline adaptive-v2 qualification",
    )
    policy = canary_v2.canary_v1.adaptive_role_policy()
    permit = canary_v2.canary_v1.AdaptiveExecutionPermit(
        run_id=canary_v2.RUN_ID,
        execution_identity=candidate["execution_identity"],
        tasks=tuple(candidate["scope"]["tasks"]),
        known_work_keys=frozenset({work_item["work_key"]}),
        output_root=tmp_path,
        query_ledger_path=tmp_path / "query.jsonl",
        budget_ledger_path=tmp_path / "budget.jsonl",
        trace_root=tmp_path / "traces",
        checkpoint_root=tmp_path / "checkpoints",
        admission_file_sha256="a" * 64,
        candidate=candidate,
        admission={},
    )
    tracker = PublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys={work_item["work_key"]},
        role_policy=policy,
    )

    def client_factory(**kwargs: Any) -> PublicDeepSeekJsonOfficialClient:
        return PublicDeepSeekJsonOfficialClient(
            **kwargs,
            transport=_transport,
        )

    executor = canary_v2.canary_v1._build_executor(
        permit,
        tracker,
        api_key="offline-adaptive-v2-key",
        role_policy=policy,
        recorded_at=lambda: "2026-07-30T02:05:00+08:00",
        client_factory=client_factory,
        receipt_adapter=_as_official_receipt,
    )
    ledger = AdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys={work_item["work_key"]},
        role_policy=policy,
    )
    oracle = canary_v2._AdaptiveOfficialOracleV2(
        permit=permit,
        case_id=case_id,
        executor=executor,
        query_ledger=ledger,
        tracker=tracker,
        role_policy=policy,
        recorded_at=lambda: "2026-07-30T02:05:00+08:00",
    )

    result = oracle("offline adaptive-v2 qualification", 1)

    assert result.decision in {"ALLOW", "ASK", "DENY"}
    assert ledger.status["terminal_query_count"] == 1
    assert ledger.status["open_query_work_keys"] == []
    assert tracker.status["event_count"] == 1
