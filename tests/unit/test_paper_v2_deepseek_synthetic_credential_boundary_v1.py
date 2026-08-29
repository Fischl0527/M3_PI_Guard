from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from experiments.paper_v2 import (
    e6_cross_provider_calibration_runner_v1 as e6_v1,
)
from experiments.paper_v2 import lean_empirical_runner as lean
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.deepseek_json_client_v2 import (
    DeepSeekJsonOfficialClient,
)
from experiments.paper_v2.deepseek_nonthinking_client_v1 import (
    DeepSeekNonThinkingOfficialClient,
)
from experiments.paper_v2.official_provider_executor import (
    DEFAULT_BUDGET_POLICY,
    HTTPResponseEnvelope,
    ProviderBudgetState,
    ProviderPayloadError,
    validate_messages,
)
from experiments.paper_v2.formal_condition_executors import (
    CONDITION_PROFILES,
    OnlineExecutorContext,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    _jsonable,
)
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import (
    PublicFrozenAgentDojoCaseResolverV2,
)


ACTIVE_TEST_KEY = "active-unit-test-credential-value"
SYNTHETIC_AGENTDOJO_MESSAGES = [
    {
        "role": "system",
        "content": "Return one simulated tool proposal as JSON.",
    },
    {
        "role": "user",
        "content": (
            "Frozen public benchmark observation: "
            "api_key=synthetic_fixture_label_001. "
            "Do not perform any real external action."
        ),
    },
]


def _policy() -> dict[str, Any]:
    return json.loads(DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8"))


def _transport(
    captured_payloads: list[dict[str, Any]],
) -> Callable[..., HTTPResponseEnvelope]:
    def transport(_endpoint, _headers, payload, _timeout):
        captured_payloads.append(dict(payload))
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-request-id": "synthetic-boundary-request"},
            body={
                "id": "synthetic-boundary-response",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"tool":"final","arguments":'
                                '{"answer":"SAFE"}}'
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 40,
                    "prompt_cache_hit_tokens": 32,
                    "prompt_cache_miss_tokens": 8,
                    "completion_tokens": 8,
                    "total_tokens": 48,
                },
            },
        )

    return transport


def _client(
    client_type: type[DeepSeekNonThinkingOfficialClient],
    captured_payloads: list[dict[str, Any]],
    *,
    content_class: str = "public_benchmark_case",
    allow_labels: bool = False,
) -> DeepSeekNonThinkingOfficialClient:
    policy = _policy()
    return client_type(
        provider_id="deepseek",
        api_key=ACTIVE_TEST_KEY,
        content_class=content_class,
        budget_state=ProviderBudgetState(
            provider_id="deepseek",
            policy=policy,
        ),
        policy=policy,
        transport=_transport(captured_payloads),
        allow_pinned_synthetic_credential_labels=allow_labels,
    )


@pytest.mark.parametrize(
    "client_type",
    [DeepSeekNonThinkingOfficialClient, DeepSeekJsonOfficialClient],
)
def test_public_pinned_synthetic_label_is_opt_in_and_payload_has_no_tools(
    client_type: type[DeepSeekNonThinkingOfficialClient],
) -> None:
    default_payloads: list[dict[str, Any]] = []
    default_client = _client(client_type, default_payloads)
    with pytest.raises(ProviderPayloadError, match="credential-like"):
        default_client.complete(SYNTHETIC_AGENTDOJO_MESSAGES)
    assert default_payloads == []

    allowed_payloads: list[dict[str, Any]] = []
    allowed_client = _client(
        client_type,
        allowed_payloads,
        allow_labels=True,
    )
    allowed_client.complete(SYNTHETIC_AGENTDOJO_MESSAGES)

    assert len(allowed_payloads) == 1
    assert "tools" not in allowed_payloads[0]
    assert "tool_choice" not in allowed_payloads[0]
    assert allowed_client.last_request_metadata[
        "pinned_synthetic_credential_labels_allowed"
    ] is True
    assert ACTIVE_TEST_KEY not in repr(allowed_client.last_request_metadata)
    assert "synthetic_fixture_label_001" not in repr(
        allowed_client.last_request_metadata
    )


def test_synthetic_label_allowance_is_restricted_to_public_benchmark() -> None:
    payloads: list[dict[str, Any]] = []
    client = _client(
        DeepSeekJsonOfficialClient,
        payloads,
        content_class="synthetic_m3_case",
        allow_labels=True,
    )
    with pytest.raises(ProviderPayloadError, match="credential-like"):
        client.complete(SYNTHETIC_AGENTDOJO_MESSAGES)
    assert payloads == []


@pytest.mark.parametrize(
    "credential_text",
    [
        ACTIVE_TEST_KEY,
        "sk-abcdefghijklmnop",
        "AQ.abcdefghijklmnop",
        "-----BEGIN PRIVATE KEY-----",
    ],
)
def test_public_allowance_never_accepts_active_or_high_confidence_credentials(
    credential_text: str,
) -> None:
    payloads: list[dict[str, Any]] = []
    client = _client(
        DeepSeekJsonOfficialClient,
        payloads,
        allow_labels=True,
    )
    messages = [
        {
            "role": "user",
            "content": f"Frozen benchmark text: {credential_text}",
        }
    ]

    with pytest.raises(ProviderPayloadError) as caught:
        client.complete(messages)

    assert credential_text not in str(caught.value)
    assert payloads == []


def test_frozen_agentdojo_user_task_16_second_turn_observation_is_qualified() -> None:
    row = next(
        item
        for item in e6_v1._load_plan("deepseek")
        if item["replicate_window"] == "W2"
        and item["case_id"]
        == "agentdojo:v1:workspace:user_task_16:injection_task_1"
        and item["condition_id"] == "no_defense"
    )
    hydrated, online_state, _ = lean._hydrate_work_item(row)
    context = OnlineExecutorContext(
        execution_identity=str(hydrated["execution_identity"]),
        work_key=str(hydrated["work_key"]),
        benchmark=str(hydrated["benchmark"]),
        condition_id=str(hydrated["condition_id"]),
        max_provider_calls=int(hydrated["max_provider_calls"]),
        online_state=online_state,
    )
    tool_schemas = dict(
        online_state["agent_input"]["online_inputs"]["tool_schemas"]
    )
    tool_schemas["final"] = {
        "arguments": {"answer": {"type": "string", "required": True}}
    }
    resolver = PublicFrozenAgentDojoCaseResolverV2(
        plan_path=e6_v1.PLAN_PATHS["deepseek"]
    )
    backend = resolver.build_backend(context, tool_schemas)
    try:
        observation = backend.execute("get_received_emails", {})
    finally:
        backend.close()
    rendered = json.dumps(
        _jsonable(observation), ensure_ascii=False, sort_keys=True
    )
    messages = [{"role": "user", "content": rendered}]

    with pytest.raises(ProviderPayloadError, match="credential-like"):
        validate_messages(
            messages,
            content_class="public_benchmark_case",
            policy=_policy(),
            active_api_key=ACTIVE_TEST_KEY,
        )

    assert validate_messages(
        messages,
        content_class="public_benchmark_case",
        policy=_policy(),
        allow_pinned_synthetic_credential_labels=True,
        active_api_key=ACTIVE_TEST_KEY,
    ) == messages


@pytest.mark.parametrize(
    ("allow_labels", "expected_status", "expected_transport_calls"),
    [
        (False, "provider_failure", 1),
        (True, "completed", 2),
    ],
)
def test_frozen_agentdojo_two_turn_runtime_obeys_case_scoped_boundary(
    allow_labels: bool,
    expected_status: str,
    expected_transport_calls: int,
) -> None:
    row = next(
        item
        for item in e6_v1._load_plan("deepseek")
        if item["replicate_window"] == "W2"
        and item["case_id"]
        == "agentdojo:v1:workspace:user_task_16:injection_task_1"
        and item["condition_id"] == "no_defense"
    )
    hydrated, online_state, _ = lean._hydrate_work_item(row)
    context = OnlineExecutorContext(
        execution_identity=str(hydrated["execution_identity"]),
        work_key=str(hydrated["work_key"]),
        benchmark=str(hydrated["benchmark"]),
        condition_id=str(hydrated["condition_id"]),
        max_provider_calls=int(hydrated["max_provider_calls"]),
        online_state=online_state,
    )
    policy = _policy()
    transport_calls: list[int] = []

    def transport(_endpoint, _headers, payload, _timeout):
        transport_calls.append(len(transport_calls) + 1)
        response_text = (
            '{"tool":"get_received_emails","arguments":{}}'
            if len(transport_calls) == 1
            else '{"tool":"final","arguments":{"answer":"done"}}'
        )
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-request-id": f"runtime-{len(transport_calls)}"},
            body={
                "id": f"runtime-response-{len(transport_calls)}",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": response_text,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 40,
                    "prompt_cache_hit_tokens": 32,
                    "prompt_cache_miss_tokens": 8,
                    "completion_tokens": 8,
                    "total_tokens": 48,
                },
            },
        )

    resolver = PublicFrozenAgentDojoCaseResolverV2(
        plan_path=e6_v1.PLAN_PATHS["deepseek"]
    )

    def provider_factory(_context):
        return DeepSeekJsonOfficialClient(
            provider_id="deepseek",
            api_key=ACTIVE_TEST_KEY,
            content_class="public_benchmark_case",
            budget_state=ProviderBudgetState(
                provider_id="deepseek", policy=policy
            ),
            policy=policy,
            transport=transport,
            allow_pinned_synthetic_credential_labels=allow_labels,
        )

    runtime = LiveConditionRuntime(
        provider_client_factory=provider_factory,
        effect_backend_factory=resolver.build_backend,
        recorded_at=lambda: "2026-08-29T00:00:00+08:00",
    )
    result = runtime.execute(context, CONDITION_PROFILES["no_defense"])

    assert result["operational_status"] == expected_status
    assert len(transport_calls) == expected_transport_calls
    if allow_labels:
        material = result["offline_evaluator_input"]
        assert sha256_canonical_json(
            _jsonable(material["pre_environment"])
        ) == sha256_canonical_json(_jsonable(material["post_environment"]))
        safety = result["safety_receipt"]["evidence"]
        assert safety["provider_managed_tools_enabled"] is False
        assert safety["external_connectors_enabled"] is False
    else:
        assert result["failure_stage"] == "provider_call"
        assert result["failure_class"] == "ProviderPayloadError"
        assert result["provider_call_index"] == 2
