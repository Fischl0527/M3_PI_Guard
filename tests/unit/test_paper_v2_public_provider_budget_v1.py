from __future__ import annotations

import copy
from typing import Any, Mapping

import pytest

from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    ProviderIdentityError,
    provider_receipt_to_attestation,
)
from experiments.paper_v2.public_deepseek_client_v1 import (
    PublicDeepSeekJsonOfficialClient,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicBudgetPolicyError,
    PublicProviderBudgetState,
    build_role_policy,
    load_public_policy,
    validate_public_policy,
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
        headers={"x-request-id": f"offline-{payload['model']}-request"},
        body={
            "id": f"offline-{payload['model']}-response",
            "model": payload["model"],
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            '{"tool":"final","arguments":'
                            '{"answer":"QUALIFIED"}}'
                        ),
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


@pytest.mark.parametrize(
    ("role", "model_id"),
    (
        ("primary", "deepseek-v4-pro"),
        ("second", "deepseek-v4-flash"),
    ),
)
def test_public_client_binds_exact_official_role_offline(
    role: str,
    model_id: str,
) -> None:
    role_policy = build_role_policy(load_public_policy(), role)
    budget = PublicProviderBudgetState("deepseek", role_policy)
    client = PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-public-qualification-key",
        content_class="public_benchmark_case",
        budget_state=budget,
        policy=role_policy,
        model_role=role,
        transport=_transport,
    )

    completion = client.complete(
        [{"role": "user", "content": "offline public qualification"}]
    )
    attestation = provider_receipt_to_attestation(completion.receipt)

    assert client.model == model_id
    assert client.endpoint == "https://api.deepseek.com/chat/completions"
    assert client.last_request_metadata["thinking_mode"] == "disabled"
    assert client.last_request_metadata["response_format"] == "json_object"
    assert client.last_request_metadata["provider_tools_declared"] is False
    assert attestation["model_id"] == model_id
    assert attestation["endpoint_type"] == "stub"
    assert completion.receipt["credentials_stored"] is False


def test_public_policy_rejects_expanded_budget() -> None:
    policy = load_public_policy()
    policy["deepseek"]["incremental_hard_limit_cny"] = 30.0

    with pytest.raises(PublicBudgetPolicyError, match="aggregate budget"):
        validate_public_policy(policy)


def test_public_client_rejects_returned_model_drift() -> None:
    role_policy = build_role_policy(load_public_policy(), "primary")
    budget = PublicProviderBudgetState("deepseek", role_policy)

    def drift_transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> HTTPResponseEnvelope:
        envelope = _transport(endpoint, headers, payload, timeout)
        body = copy.deepcopy(dict(envelope.body))
        body["model"] = "deepseek-v4-flash"
        return HTTPResponseEnvelope(
            status_code=envelope.status_code,
            headers=envelope.headers,
            body=body,
        )

    client = PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-public-qualification-key",
        content_class="public_benchmark_case",
        budget_state=budget,
        policy=role_policy,
        model_role="primary",
        transport=drift_transport,
    )

    with pytest.raises(ProviderIdentityError, match="returned model"):
        client.complete(
            [{"role": "user", "content": "offline public qualification"}]
        )
