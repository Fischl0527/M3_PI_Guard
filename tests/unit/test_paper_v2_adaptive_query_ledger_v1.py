from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import pytest

from experiments.paper_v2.adaptive_cost_canary_controller_v1 import (
    adaptive_role_policy,
)
from experiments.paper_v2.adaptive_cost_canary_plan_v1 import (
    build_query_work_item_and_state,
    verify_candidate,
)
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    AdaptiveQueryLedger,
    AdaptiveQueryLedgerError,
    cross_bind_query_and_call_ledgers,
    validate_query_events,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    _QualificationEvaluator,
    _QualificationRuntime,
    build_condition_dispatcher,
)
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
)
from experiments.paper_v2.provider_safety import build_safety_receipt
from experiments.paper_v2.public_deepseek_client_v1 import (
    PublicDeepSeekJsonOfficialClient,
)
from experiments.paper_v2.public_execution_store_v1 import (
    PublicBudgetClient,
    PublicBudgetTracker,
    assemble_public_experiment_record,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicProviderBudgetState,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    PublicDeepSeekJsonTracedProviderClient,
)


RECORDED_AT = "2026-07-28T05:10:00+08:00"


def _transport(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> HTTPResponseEnvelope:
    del endpoint, headers, timeout
    return HTTPResponseEnvelope(
        status_code=200,
        headers={"x-request-id": "adaptive-ledger-request"},
        body={
            "id": "adaptive-ledger-response",
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
    evidence["requested_at"] = RECORDED_AT
    evidence["model_latency_ms"] = 0.0
    value["evidence_sha256"] = sha256_canonical_json(evidence)
    return value


def _record_and_call_evidence(
    tmp_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    PublicBudgetTracker,
    Path,
]:
    candidate = verify_candidate()
    case_id = candidate["scope"]["tasks"][0]["case_id"]
    work_item, state = build_query_work_item_and_state(
        candidate,
        case_id=case_id,
        query_index=1,
        mutated_payload="adaptive ledger qualification",
    )
    policy = adaptive_role_policy()
    trace_root = tmp_path / "traces"
    trace_root.mkdir()
    tracker = PublicBudgetTracker(
        tmp_path / "budget.jsonl",
        run_id="adaptive-cost-canary-primary-v1",
        execution_identity=candidate["execution_identity"],
        model_role="primary",
        known_work_keys={work_item["work_key"]},
        role_policy=policy,
    )
    client = PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-adaptive-ledger-key",
        content_class="synthetic_m3_case",
        budget_state=PublicProviderBudgetState("deepseek", policy),
        policy=policy,
        model_role="primary",
        transport=_transport,
    )
    traced = PublicDeepSeekJsonTracedProviderClient(
        PublicBudgetClient(
            client,
            tracker=tracker,
            work_key=work_item["work_key"],
            recorded_at=lambda: RECORDED_AT,
        ),
        execution_identity=candidate["execution_identity"],
        work_key=work_item["work_key"],
        trace_path=trace_root / f"{work_item['work_key']}.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
    )
    traced.complete(
        [{"role": "user", "content": "offline adaptive qualification"}]
    )
    dispatcher = build_condition_dispatcher(
        runtime=_QualificationRuntime(),
        evaluator=_QualificationEvaluator(),
    )
    result = dict(dispatcher.execute(work_item, state))
    result["result_tier"] = "formal_candidate"
    result["provider_trace_bundle"] = traced.build_bundle()
    result["safety_receipt"] = build_safety_receipt(
        provider_id="deepseek",
        endpoint_url="https://api.deepseek.com/chat/completions",
        effect_backend="no_effect",
        tool="final",
        arguments={"answer": "OFFLINE_QUALIFICATION"},
    )
    record = assemble_public_experiment_record(
        work_item,
        state,
        result,
        run_id="adaptive-cost-canary-primary-v1",
        role_policy=policy,
    )
    return work_item, state, record, tracker, trace_root


def test_adaptive_query_ledger_cross_binds_provider_calls(
    tmp_path: Path,
) -> None:
    work_item, _, record, tracker, trace_root = (
        _record_and_call_evidence(tmp_path)
    )
    policy = adaptive_role_policy()
    ledger = AdaptiveQueryLedger(
        tmp_path / "query.jsonl",
        run_id="adaptive-cost-canary-primary-v1",
        execution_identity=work_item["execution_identity"],
        known_work_keys={work_item["work_key"]},
        role_policy=policy,
    )

    ledger.append_started(
        work_key=work_item["work_key"],
        case_id=work_item["case_id"],
        query_index=1,
        prompt_sha256=work_item["mutated_payload_sha256"],
        recorded_at=RECORDED_AT,
    )
    ledger.append_terminal(
        work_key=work_item["work_key"],
        case_id=work_item["case_id"],
        query_index=1,
        prompt_sha256=work_item["mutated_payload_sha256"],
        record=record,
        recorded_at=RECORDED_AT,
    )

    assert ledger.status["terminal_query_count"] == 1
    assert ledger.status["completed_provider_call_count"] == 1
    assert ledger.status["scientific_outcomes_aggregated"] is False
    cross_bind_query_and_call_ledgers(
        query_events=ledger.events,
        budget_events=tracker.events,
        trace_root=trace_root,
        role_policy=policy,
    )


def test_adaptive_query_ledger_rejects_tampering(tmp_path: Path) -> None:
    work_item, _, _, _, _ = _record_and_call_evidence(tmp_path)
    policy = adaptive_role_policy()
    ledger = AdaptiveQueryLedger(
        tmp_path / "query.jsonl",
        run_id="adaptive-cost-canary-primary-v1",
        execution_identity=work_item["execution_identity"],
        known_work_keys={work_item["work_key"]},
        role_policy=policy,
    )
    ledger.append_started(
        work_key=work_item["work_key"],
        case_id=work_item["case_id"],
        query_index=1,
        prompt_sha256=work_item["mutated_payload_sha256"],
        recorded_at=RECORDED_AT,
    )
    drifted = copy.deepcopy(ledger.events)
    drifted[0]["prompt_sha256"] = "0" * 64

    with pytest.raises(
        AdaptiveQueryLedgerError,
        match="identity/hash drift",
    ):
        validate_query_events(
            drifted,
            run_id="adaptive-cost-canary-primary-v1",
            execution_identity=work_item["execution_identity"],
            known_work_keys={work_item["work_key"]},
            role_policy=policy,
        )


def test_adaptive_query_ledger_blocks_second_start_when_open(
    tmp_path: Path,
) -> None:
    candidate = verify_candidate()
    tasks = candidate["scope"]["tasks"]
    first, _ = build_query_work_item_and_state(
        candidate,
        case_id=tasks[0]["case_id"],
        query_index=1,
        mutated_payload="first",
    )
    second, _ = build_query_work_item_and_state(
        candidate,
        case_id=tasks[1]["case_id"],
        query_index=1,
        mutated_payload="second",
    )
    policy = adaptive_role_policy()
    ledger = AdaptiveQueryLedger(
        tmp_path / "query.jsonl",
        run_id="adaptive-cost-canary-primary-v1",
        execution_identity=candidate["execution_identity"],
        known_work_keys={first["work_key"], second["work_key"]},
        role_policy=policy,
    )
    ledger.append_started(
        work_key=first["work_key"],
        case_id=first["case_id"],
        query_index=1,
        prompt_sha256=first["mutated_payload_sha256"],
        recorded_at=RECORDED_AT,
    )

    with pytest.raises(
        AdaptiveQueryLedgerError,
        match="open adaptive query",
    ):
        ledger.append_started(
            work_key=second["work_key"],
            case_id=second["case_id"],
            query_index=1,
            prompt_sha256=second["mutated_payload_sha256"],
            recorded_at=RECORDED_AT,
        )
