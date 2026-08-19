from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.adaptive_cost_canary_controller_v1 import (
    adaptive_role_policy,
)
from experiments.paper_v2.adaptive_cost_canary_plan_v1 import (
    build_query_work_item_and_state,
    verify_candidate,
)
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    cross_bind_query_and_call_ledgers,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    _QualificationEvaluator,
    _QualificationRuntime,
    build_condition_dispatcher,
)
from experiments.paper_v2.incremental_live_ledgers_v1 import (
    IncrementalAdaptiveQueryLedger,
    IncrementalAttemptLedger,
    IncrementalPublicBudgetTracker,
    IncrementalPublicRecordLedger,
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
    assemble_public_experiment_record,
    cross_bind_public_budget_and_records,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_PLAN,
    hydrate_public_work_item,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicProviderBudgetState,
    build_role_policy,
    load_public_policy,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    PublicDeepSeekJsonTracedProviderClient,
)


RECORDED_AT = "2026-07-30T02:55:00+08:00"


def _transport_factory() -> Any:
    state = {"calls": 0}

    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> HTTPResponseEnvelope:
        del endpoint, headers, timeout
        state["calls"] += 1
        suffix = state["calls"]
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-request-id": f"incremental-request-{suffix}"},
            body={
                "id": f"incremental-response-{suffix}",
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

    return transport


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


def _client(
    *,
    policy: Mapping[str, Any],
    content_class: str,
) -> PublicDeepSeekJsonOfficialClient:
    return PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-incremental-key",
        content_class=content_class,
        budget_state=PublicProviderBudgetState("deepseek", policy),
        policy=policy,
        model_role="primary",
        transport=_transport_factory(),
    )


def _execution_result(
    work_item: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    traced: PublicDeepSeekJsonTracedProviderClient,
) -> dict[str, Any]:
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
    return result


def test_incremental_public_ledgers_match_full_replay(
    tmp_path: Path,
) -> None:
    compact = json.loads(
        DEFAULT_PLAN.read_text(encoding="utf-8").splitlines()[0]
    )
    work_item, state = hydrate_public_work_item(compact)
    policy = build_role_policy(load_public_policy(), "primary")
    work_key = str(work_item["work_key"])
    tracker = IncrementalPublicBudgetTracker(
        tmp_path / "budget.jsonl",
        run_id="incremental-public-run",
        execution_identity=str(work_item["execution_identity"]),
        model_role="primary",
        known_work_keys={work_key},
        role_policy=policy,
    )
    trace_root = tmp_path / "traces"
    trace_root.mkdir()
    traced = PublicDeepSeekJsonTracedProviderClient(
        PublicBudgetClient(
            _client(
                policy=policy,
                content_class="public_benchmark_case",
            ),
            tracker=tracker,
            work_key=work_key,
            recorded_at=lambda: RECORDED_AT,
        ),
        execution_identity=str(work_item["execution_identity"]),
        work_key=work_key,
        trace_path=trace_root / f"{work_key}.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
    )
    traced.complete([{"role": "user", "content": "qualification"}])
    result = _execution_result(work_item, state, traced=traced)
    attempts = IncrementalAttemptLedger(
        tmp_path / "attempts.jsonl",
        run_id="incremental-public-run",
        execution_identity=str(work_item["execution_identity"]),
        known_work_keys={work_key},
    )
    records = IncrementalPublicRecordLedger(
        tmp_path / "records.jsonl",
        work_items=[compact],
        execution_identity=str(work_item["execution_identity"]),
        run_id="incremental-public-run",
        role_policy=policy,
    )

    attempts.append(
        work_key=work_key,
        event_type="started",
        record_entry_sha256=None,
        recorded_at=RECORDED_AT,
    )
    entry = records.append(
        work_item=work_item,
        initial_online_state=state,
        execution_result=result,
    )
    attempts.append(
        work_key=work_key,
        event_type="completed",
        record_entry_sha256=str(entry["entry_sha256"]),
        recorded_at=RECORDED_AT,
    )

    assert tracker.full_validate()["event_count"] == 1
    assert records.full_validate()["entry_count"] == 1
    assert attempts.full_validate()["open_work_keys"] == []
    cross_bind_public_budget_and_records(
        budget_events=tracker.events,
        record_entries=records.entries,
        trace_root=trace_root,
        role_policy=policy,
    )


def test_incremental_adaptive_ledger_matches_full_replay(
    tmp_path: Path,
) -> None:
    candidate = verify_candidate()
    case_id = str(candidate["scope"]["tasks"][0]["case_id"])
    work_item, state = build_query_work_item_and_state(
        candidate,
        case_id=case_id,
        query_index=1,
        mutated_payload="incremental adaptive qualification",
    )
    work_key = str(work_item["work_key"])
    policy = adaptive_role_policy()
    tracker = IncrementalPublicBudgetTracker(
        tmp_path / "budget.jsonl",
        run_id="adaptive-cost-canary-primary-v1",
        execution_identity=str(candidate["execution_identity"]),
        model_role="primary",
        known_work_keys={work_key},
        role_policy=policy,
    )
    trace_root = tmp_path / "traces"
    trace_root.mkdir()
    traced = PublicDeepSeekJsonTracedProviderClient(
        PublicBudgetClient(
            _client(policy=policy, content_class="synthetic_m3_case"),
            tracker=tracker,
            work_key=work_key,
            recorded_at=lambda: RECORDED_AT,
        ),
        execution_identity=str(candidate["execution_identity"]),
        work_key=work_key,
        trace_path=trace_root / f"{work_key}.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
    )
    traced.complete([{"role": "user", "content": "qualification"}])
    result = _execution_result(work_item, state, traced=traced)
    record = assemble_public_experiment_record(
        work_item,
        state,
        result,
        run_id="adaptive-cost-canary-primary-v1",
        role_policy=policy,
    )
    ledger = IncrementalAdaptiveQueryLedger(
        tmp_path / "query.jsonl",
        run_id="adaptive-cost-canary-primary-v1",
        execution_identity=str(candidate["execution_identity"]),
        known_work_keys={work_key},
        role_policy=policy,
    )

    ledger.append_started(
        work_key=work_key,
        case_id=case_id,
        query_index=1,
        prompt_sha256=str(work_item["mutated_payload_sha256"]),
        recorded_at=RECORDED_AT,
    )
    ledger.append_terminal(
        work_key=work_key,
        case_id=case_id,
        query_index=1,
        prompt_sha256=str(work_item["mutated_payload_sha256"]),
        record=record,
        recorded_at=RECORDED_AT,
    )

    assert tracker.full_validate()["event_count"] == 1
    assert ledger.full_validate()["terminal_query_count"] == 1
    cross_bind_query_and_call_ledgers(
        query_events=ledger.events,
        budget_events=tracker.events,
        trace_root=trace_root,
        role_policy=policy,
    )
