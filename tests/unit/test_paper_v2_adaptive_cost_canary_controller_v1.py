from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import pytest

from experiments.paper_v2.adaptive_cost_canary_controller_v1 import (
    AdaptiveCostCanaryControllerError,
    AdaptiveExecutionPermit,
    AdaptiveM3CaseResolver,
    _build_executor,
    adaptive_role_policy,
    build_canary_admission,
    canonical_canary_command,
    validate_canary_admission,
)
from experiments.paper_v2.adaptive_cost_canary_plan_v1 import (
    build_query_work_item_and_state,
    verify_candidate,
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
        headers={"x-request-id": "adaptive-bridge-request"},
        body={
            "id": "adaptive-bridge-response",
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
    evidence["requested_at"] = "2026-07-28T05:20:00+08:00"
    evidence["model_latency_ms"] = 0.0
    value["evidence_sha256"] = sha256_canonical_json(evidence)
    return value


def test_adaptive_canary_admission_binds_exact_command_and_cost() -> None:
    value = build_canary_admission(
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-28T05:00:00+08:00",
    )

    assert value["scope"]["exact_command"] == canonical_canary_command()
    assert value["scope"]["model_id"] == "deepseek-v4-pro"
    assert value["scope"]["maximum_queries"] == 400
    assert value["scope"]["hard_limit_cny"] == 5.0
    assert value["authorization"]["canary_execution_authorized"] is True
    assert value["authorization"]["formal_continuation_authorized"] is False
    assert value["authorization"]["result_admission_authorized"] is False
    assert validate_canary_admission(value) == value


def test_adaptive_canary_admission_rejects_command_drift() -> None:
    value = build_canary_admission(
        owner_statement_sha256="b" * 64,
        approved_at="2026-07-28T05:00:00+08:00",
    )
    drifted = copy.deepcopy(value)
    drifted["scope"]["exact_command"] += " --unsafe"

    with pytest.raises(
        AdaptiveCostCanaryControllerError,
        match="digest/scope drift",
    ):
        validate_canary_admission(drifted)


def test_adaptive_role_policy_has_independent_cny5_fuse() -> None:
    policy = adaptive_role_policy()

    assert policy["deepseek"]["model_id"] == "deepseek-v4-pro"
    assert policy["deepseek"]["abort_ceiling_cny"] == 5.0
    assert policy["common_controls"]["canary_concurrency"] == 1
    assert policy["common_controls"]["automatic_retries"] == 0


def test_adaptive_resolver_binds_dynamic_query_to_frozen_labels() -> None:
    candidate = verify_candidate()
    case_id = candidate["scope"]["tasks"][0]["case_id"]
    resolver = AdaptiveM3CaseResolver(candidate)

    binding = resolver.resolve(
        f"adaptive-cost-v1__{case_id}__q00001"
    )

    assert binding.case_id == case_id
    assert binding.execution_identity == candidate["execution_identity"]
    assert binding.offline_evaluation["offline_only"] is True


def test_adaptive_official_bridge_qualifies_with_injected_transport(
    tmp_path: Path,
) -> None:
    candidate = verify_candidate()
    case_id = candidate["scope"]["tasks"][0]["case_id"]
    work_item, state = build_query_work_item_and_state(
        candidate,
        case_id=case_id,
        query_index=1,
        mutated_payload="offline bridge qualification",
    )
    policy = adaptive_role_policy()
    permit = AdaptiveExecutionPermit(
        run_id="adaptive-cost-canary-primary-v1",
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

    executor = _build_executor(
        permit,
        tracker,
        api_key="offline-adaptive-bridge-key",
        role_policy=policy,
        recorded_at=lambda: "2026-07-28T05:20:00+08:00",
        client_factory=client_factory,
        receipt_adapter=_as_official_receipt,
    )

    result = executor(work_item, state)

    assert result["result_tier"] == "formal_candidate"
    assert result["provider_trace_bundle"]["completed_request_count"] == 1
    assert result["provider_trace_bundle"][
        "prompt_or_response_content_stored"
    ] is False
    assert tracker.status["event_count"] == 1
