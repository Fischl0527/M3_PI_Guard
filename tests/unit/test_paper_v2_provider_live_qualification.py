from __future__ import annotations

import copy
import json
from dataclasses import replace

import pytest

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
)
from experiments.paper_v2.provider_live_qualification import (
    CONSENT_VALUE,
    ProviderLiveQualificationError,
    execute_live_qualification,
    validate_artifact,
)


def _values() -> dict[str, str]:
    return {
        "M3_FRONTIER_API_CONSENT": CONSENT_VALUE,
        "DEEPSEEK_API_KEY": "test-deepseek-credential",
        "FRONTIER_DEEPSEEK_MODEL_ID": "deepseek-v4-pro",
        "FRONTIER_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "GEMINI_API_KEY": "test-gemini-credential",
        "FRONTIER_GEMINI_MODEL_ID": "gemini-3.6-flash",
        "FRONTIER_GEMINI_BASE_URL": (
            "https://generativelanguage.googleapis.com/v1beta/openai/"
        ),
    }


def _response(provider_id: str) -> HTTPResponseEnvelope:
    if provider_id == "deepseek":
        model = "deepseek-v4-pro"
        usage = {
            "prompt_tokens": 10,
            "prompt_cache_hit_tokens": 8,
            "prompt_cache_miss_tokens": 2,
            "completion_tokens": 2,
            "total_tokens": 12,
        }
        header = {"x-request-id": "deepseek-request"}
    else:
        model = "gemini-3.6-flash"
        usage = {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
        }
        header = {"x-goog-request-id": "gemini-request"}
    return HTTPResponseEnvelope(
        status_code=200,
        headers=header,
        body={
            "id": f"{provider_id}-response",
            "model": model,
            "choices": [
                {
                    "message": {"role": "assistant", "content": "SAFE"},
                    "finish_reason": "stop",
                }
            ],
            "usage": usage,
        },
    )


class _OfficialReceiptFixtureClient:
    def __init__(self, client: OfficialProviderClient) -> None:
        self.client = client
        self.calls = 0

    def complete(self, messages, *, step):
        self.calls += 1
        completion = self.client.complete(messages, step=step)
        receipt = copy.deepcopy(dict(completion.receipt))
        receipt["evidence"]["transport_kind"] = "official_network"
        receipt["evidence_sha256"] = sha256_canonical_json(
            receipt["evidence"]
        )
        return replace(completion, receipt=receipt)


def _factory(calls: dict[str, _OfficialReceiptFixtureClient]):
    def build(provider_id, api_key, policy):
        client = OfficialProviderClient(
            provider_id=provider_id,
            api_key=api_key,
            content_class=(
                "synthetic_m3_case"
                if provider_id == "deepseek"
                else "public_benchmark_case"
            ),
            budget_state=ProviderBudgetState(
                provider_id=provider_id,
                policy=policy,
            ),
            policy=policy,
            transport=lambda *_: _response(provider_id),
            temperature=0.0,
            max_tokens=16,
        )
        fixture = _OfficialReceiptFixtureClient(client)
        calls[provider_id] = fixture
        return fixture

    return build


def test_two_provider_identity_qualification_is_content_free() -> None:
    calls: dict[str, _OfficialReceiptFixtureClient] = {}
    artifact = execute_live_qualification(
        _values(),
        client_factory=_factory(calls),
    )
    validate_artifact(artifact)

    assert artifact["status"] == "two_provider_live_identity_qualified"
    assert artifact["qualified_provider_count"] == 2
    assert artifact["network_call_attempts"] == 2
    assert all(client.calls == 1 for client in calls.values())
    assert all(
        result["response_exact_safe"] is True
        for result in artifact["providers"].values()
    )
    serialized = json.dumps(artifact, sort_keys=True)
    assert "test-deepseek-credential" not in serialized
    assert "test-gemini-credential" not in serialized
    assert '"response_text"' not in serialized
    assert '"messages"' not in serialized
    assert artifact["result_eligible_for_effect_tables"] is False


def test_failed_provider_attempt_is_retained_without_error_text() -> None:
    calls: dict[str, _OfficialReceiptFixtureClient] = {}
    good_factory = _factory(calls)

    class FailedClient:
        def complete(self, messages, *, step):
            del messages, step
            raise RuntimeError("sensitive upstream text must not persist")

    def factory(provider_id, api_key, policy):
        if provider_id == "gemini":
            return FailedClient()
        return good_factory(provider_id, api_key, policy)

    artifact = execute_live_qualification(
        _values(),
        client_factory=factory,
    )
    validate_artifact(artifact)

    failed = artifact["providers"]["gemini"]
    assert artifact["status"] == "live_identity_qualification_incomplete"
    assert artifact["qualified_provider_count"] == 1
    assert failed == {
        "status": "failed_single_attempt_preserved",
        "error_type": "RuntimeError",
        "provider_attempts": 1,
        "response_text_persisted": False,
    }
    assert "sensitive upstream text" not in json.dumps(artifact)


def test_configuration_requires_exact_consent_and_frozen_model() -> None:
    values = _values()
    values["M3_FRONTIER_API_CONSENT"] = "no"
    with pytest.raises(
        ProviderLiveQualificationError,
        match="explicit local consent",
    ):
        execute_live_qualification(values, client_factory=lambda *_: None)

    values = _values()
    values["FRONTIER_GEMINI_MODEL_ID"] = "different-model"
    with pytest.raises(
        ProviderLiveQualificationError,
        match="frozen policy",
    ):
        execute_live_qualification(values, client_factory=lambda *_: None)
