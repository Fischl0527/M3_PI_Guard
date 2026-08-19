from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

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
    PublicExecutionStoreError,
    append_public_execution_result,
    cross_bind_public_budget_and_records,
    load_public_record_entries,
    validate_public_budget_events,
    validate_public_record_entries,
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


def _transport(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> HTTPResponseEnvelope:
    del endpoint, headers, timeout
    return HTTPResponseEnvelope(
        status_code=200,
        headers={"x-request-id": "public-store-request"},
        body={
            "id": "public-store-response",
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


def _as_official_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    import copy

    value = copy.deepcopy(dict(receipt))
    evidence = value["evidence"]
    evidence["transport_kind"] = "official_network"
    evidence["identity_verified"] = True
    evidence["request_trace_complete"] = True
    evidence["evidence_level"] = (
        "official_exact_model_with_request_and_response_ids"
    )
    evidence["requested_at"] = "2026-07-28T00:35:00+08:00"
    evidence["model_latency_ms"] = 0.0
    value["evidence_sha256"] = sha256_canonical_json(evidence)
    return value


def test_public_budget_ledger_is_append_only_and_reconstructable(
    tmp_path: Path,
) -> None:
    policy = build_role_policy(load_public_policy(), "primary")
    work_key = "public-store-work"
    tracker = PublicBudgetTracker(
        tmp_path / "budget.jsonl",
        run_id="public-store-run",
        execution_identity="public-store-identity",
        model_role="primary",
        known_work_keys={work_key},
        role_policy=policy,
    )
    client = PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-public-store-key",
        content_class="public_benchmark_case",
        budget_state=PublicProviderBudgetState("deepseek", policy),
        policy=policy,
        model_role="primary",
        transport=_transport,
    )
    wrapped = PublicBudgetClient(
        client,
        tracker=tracker,
        work_key=work_key,
        recorded_at=lambda: "2026-07-28T00:35:00+08:00",
    )

    wrapped.complete(
        [{"role": "user", "content": "offline public store qualification"}]
    )

    assert tracker.status["event_count"] == 1
    assert tracker.status["role_cumulative_usage"]["prompt_tokens"] == 100
    assert tracker.status["role_cumulative_cost_cny"] > 0
    assert validate_public_budget_events(
        tracker.events,
        run_id="public-store-run",
        execution_identity="public-store-identity",
        model_role="primary",
        known_work_keys={work_key},
        role_policy=policy,
    ) == tracker.status


def test_public_budget_ledger_rejects_hash_drift(tmp_path: Path) -> None:
    policy = build_role_policy(load_public_policy(), "primary")
    tracker = PublicBudgetTracker(
        tmp_path / "budget.jsonl",
        run_id="public-store-run",
        execution_identity="public-store-identity",
        model_role="primary",
        known_work_keys={"public-store-work"},
        role_policy=policy,
    )
    assert tracker.events == []

    with pytest.raises(PublicExecutionStoreError):
        validate_public_budget_events(
            [
                {
                    "schema_version": "m3-paper-v2-public-budget-event-1.0",
                    "event_sha256": "0" * 64
                }
            ],
            run_id="public-store-run",
            execution_identity="public-store-identity",
            model_role="primary",
            known_work_keys={"public-store-work"},
            role_policy=policy,
        )


def test_public_cross_binding_rejects_unmatched_budget_event(
    tmp_path: Path,
) -> None:
    policy = build_role_policy(load_public_policy(), "primary")

    with pytest.raises(
        PublicExecutionStoreError,
        match="does not bind",
    ):
        cross_bind_public_budget_and_records(
            budget_events=[
                {
                    "provider_response_id": "unmatched",
                }
            ],
            record_entries=[],
            trace_root=tmp_path,
            role_policy=policy,
        )


def test_public_record_budget_and_trace_ledgers_cross_bind(
    tmp_path: Path,
) -> None:
    import json

    compact = json.loads(
        DEFAULT_PLAN.read_text(encoding="utf-8").splitlines()[0]
    )
    work_item, state = hydrate_public_work_item(compact)
    role_policy = build_role_policy(load_public_policy(), "primary")
    budget_path = tmp_path / "budget.jsonl"
    trace_root = tmp_path / "traces"
    tracker = PublicBudgetTracker(
        budget_path,
        run_id="public-record-run",
        execution_identity=work_item["execution_identity"],
        model_role="primary",
        known_work_keys={work_item["work_key"]},
        role_policy=role_policy,
    )
    client = PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-public-record-key",
        content_class="public_benchmark_case",
        budget_state=PublicProviderBudgetState("deepseek", role_policy),
        policy=role_policy,
        model_role="primary",
        transport=_transport,
    )
    budget_client = PublicBudgetClient(
        client,
        tracker=tracker,
        work_key=work_item["work_key"],
        recorded_at=lambda: "2026-07-28T00:35:00+08:00",
    )
    trace_root.mkdir()
    traced = PublicDeepSeekJsonTracedProviderClient(
        budget_client,
        execution_identity=work_item["execution_identity"],
        work_key=work_item["work_key"],
        trace_path=trace_root / f"{work_item['work_key']}.jsonl",
        recorded_at=lambda: "2026-07-28T00:35:00+08:00",
        receipt_adapter=_as_official_receipt,
    )
    traced.complete(
        [{"role": "user", "content": "offline public record qualification"}]
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
    record_path = tmp_path / "records.jsonl"

    append_public_execution_result(
        record_path,
        work_items=[compact],
        work_item=work_item,
        initial_online_state=state,
        execution_result=result,
        execution_identity=work_item["execution_identity"],
        run_id="public-record-run",
        role_policy=role_policy,
    )
    entries = load_public_record_entries(record_path)

    assert validate_public_record_entries(
        entries,
        work_items=[compact],
        execution_identity=work_item["execution_identity"],
        run_id="public-record-run",
        role_policy=role_policy,
    )["entry_count"] == 1
    cross_bind_public_budget_and_records(
        budget_events=tracker.events,
        record_entries=entries,
        trace_root=trace_root,
        role_policy=role_policy,
    )
