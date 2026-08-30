from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderPausedError,
    ProviderBudgetState,
    ProviderTransportError,
)
from experiments.paper_v2.vigil_live_dependency import (
    DEFAULT_BUDGET_POLICY,
    DEFAULT_OUTPUT,
    VigilLiveDependencyError,
    VigilOfficialConstraintFactory,
    build_qualification,
)


def _client(text: str) -> OfficialProviderClient:
    policy = json.loads(DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8"))

    def transport(endpoint, headers, payload, timeout):
        del endpoint, headers, timeout
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-request-id": "vigil-test-request"},
            body={
                "id": "vigil-test-response",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 10,
                    "total_tokens": 110,
                    "prompt_cache_hit_tokens": 90,
                    "prompt_cache_miss_tokens": 10,
                },
            },
        )

    return OfficialProviderClient(
        provider_id="deepseek",
        api_key="fixture-key-for-vigil-tests",
        content_class="public_benchmark_case",
        budget_state=ProviderBudgetState(
            provider_id="deepseek", policy=policy
        ),
        policy=policy,
        transport=transport,
    )


def test_frozen_vigil_provider_bridge_reproduces_without_network() -> None:
    current = build_qualification()
    frozen = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert current == frozen
    assert current["provider_bridge"]["official_provider_client"] is True
    assert current["provider_bridge"]["provider_calls_consumed"] == 1
    assert current["provider_bridge"]["automatic_retries"] == 0
    assert (
        current["provider_bridge"]["silent_default_fallback_accepted"]
        is False
    )
    assert current["runtime_decisions"] == {
        "delete_record": "DENY",
        "read_report": "ALLOW",
        "send_report": "ASK",
    }
    assert current["network_calls_made"] == 0
    assert current["formal_results_created"] == 0


def test_vigil_bridge_rejects_official_default_fallback() -> None:
    client = _client("not valid JSON")

    with pytest.raises(
        VigilLiveDependencyError,
        match="silently fell back",
    ):
        VigilOfficialConstraintFactory()(
            None,
            "Read a public report.",
            client,
        )


@pytest.mark.parametrize(
    ("exception_type", "message"),
    [
        (ProviderPausedError, "synthetic provider pause"),
        (ProviderTransportError, "synthetic provider transport failure"),
    ],
)
def test_vigil_bridge_rethrows_provider_failure_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[ProviderTransportError],
    message: str,
) -> None:
    client = _client("unused")
    calls = 0
    root_cause = OSError("synthetic socket failure")

    def fail_once(messages, *, step):
        nonlocal calls
        del messages
        calls += 1
        assert step == 1
        try:
            raise root_cause
        except OSError as exc:
            raise exception_type(message) from exc

    monkeypatch.setattr(client, "complete", fail_once)

    with pytest.raises(exception_type) as caught:
        VigilOfficialConstraintFactory()(
            None,
            "Read a public report.",
            client,
        )

    assert calls == 1
    assert caught.value.args == (message,)
    assert caught.value.__cause__ is root_cause


def test_vigil_bridge_keeps_parse_fallback_classification() -> None:
    client = _client("not valid JSON")

    with pytest.raises(VigilLiveDependencyError, match="silently fell back") as caught:
        VigilOfficialConstraintFactory()(
            None,
            "Read a public report.",
            client,
        )

    assert not isinstance(caught.value, ProviderTransportError)


def test_vigil_qualification_does_not_persist_query_or_raw_response() -> None:
    rendered = Path(DEFAULT_OUTPUT).read_text(encoding="utf-8")

    assert "Send the report only after confirmation" not in rendered
    assert "Confirm sending the report" not in rendered
    assert '"raw_response"' not in rendered
