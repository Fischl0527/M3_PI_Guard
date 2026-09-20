"""No-network fixtures for the corrected development provider boundary."""

from __future__ import annotations

import copy
import io
import json
import threading
from urllib import error as urllib_error

import pytest

from experiments.paper_v2 import correctness_provider_v1 as subject


MESSAGES = [
    {"role": "system", "content": "Return one JSON object."},
    {"role": "user", "content": "Return the fixed safe marker."},
]
OFFLINE_KEY = "offline-provider-fixture-credential"
DEFAULT_TRANSPORT = object()


def envelope(model="deepseek-v4-pro", *, status=200, body_changes=None):
    body = {
        "id": "fixture-response-001",
        "model": model,
        "choices": [
            {
                "message": {
                    "content": '{"tool":"final","arguments":{"answer":"SAFE"}}'
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "total_tokens": 110,
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
        },
    }
    body.update(body_changes or {})
    return subject.official.HTTPResponseEnvelope(
        status, {"x-request-id": "fixture-request-001"}, body
    )


def make_client(
    tmp_path, *, model_group="deepseek_pro", transport=DEFAULT_TRANSPORT, **changes
):
    options = dict(
        model_group=model_group,
        model=subject.APPROVED_MODEL_GROUPS.get(model_group, "unknown"),
        api_key=OFFLINE_KEY,
        benchmark="m3-v2",
        work_key="fixture-work",
        attempt=1,
        trace_path=tmp_path / "requests.jsonl",
        pacer=subject.RequestPacer(0, threading.Event()),
        transport=(lambda *args: envelope())
        if transport is DEFAULT_TRANSPORT
        else transport,
    )
    options.update(changes)
    return subject.DevelopmentRequestClient(**options)


def log_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize(
    "model_group", ["deepseek_pro", "deepseek_flash", "gemini_flash"]
)
def test_exact_model_receipt_and_pretransport_identity(tmp_path, model_group):
    observed = []
    model = subject.APPROVED_MODEL_GROUPS[model_group]

    def transport(endpoint, headers, payload, timeout):
        started = log_rows(tmp_path / "requests.jsonl")
        assert len(started) == 1 and started[0]["event"] == "started"
        assert started[0]["local_request_id"].startswith("m3req-")
        assert started[0]["payload_sha256"] == subject.sha256_canonical_json(payload)
        assert payload["model"] == model
        assert payload["max_tokens"] == 512 and payload["temperature"] == 0
        assert timeout == 180
        assert "tools" not in payload and "tool_choice" not in payload
        observed.append(copy.deepcopy(payload))
        return envelope(model)

    client = make_client(tmp_path, model_group=model_group, transport=transport)
    result = client.complete(MESSAGES)
    assert len(observed) == 1
    assert result.provider_attempts == 1
    assert result.receipt["evidence"]["transport_kind"] == "injected_test_double"
    assert result.receipt["evidence"]["configured_model"] == model
    assert client.last_receipt == result.receipt
    assert (
        result.receipt["evidence"]["payload_sha256"]
        == client.requests[0]["payload_sha256"]
    )
    assert client.requests[0]["response_received"] is True
    assert client.requests[0]["status"] == "completed"
    trace = (tmp_path / "requests.jsonl").read_text(encoding="utf-8")
    assert OFFLINE_KEY not in trace
    assert MESSAGES[0]["content"] not in trace
    assert "SAFE" not in trace


@pytest.mark.parametrize("identity", [None, "", "   ", 123, {"unexpected": "data"}])
def test_missing_or_malformed_response_id_remains_response_bearing(tmp_path, identity):
    client = make_client(
        tmp_path, transport=lambda *args: envelope(body_changes={"id": identity})
    )
    with pytest.raises(subject.official.ProviderIdentityError):
        client.complete(MESSAGES)
    assert client.requests[0]["response_received"] is True
    assert client.requests[0]["status"] == "failed"
    assert len(log_rows(tmp_path / "requests.jsonl")) == 2


@pytest.mark.parametrize(
    "changed",
    [
        {"model": "deepseek-v4-flash"},
        {"model": "deepseek-flash"},
        {"choices": []},
        {"usage": {}},
    ],
)
def test_invalid_response_is_not_marked_no_response(tmp_path, changed):
    calls = []

    def transport(*args):
        calls.append(1)
        return envelope(body_changes=changed)

    client = make_client(tmp_path, transport=transport)
    with pytest.raises(subject.official.OfficialProviderError):
        client.complete(MESSAGES)
    assert calls == [1]
    assert client.requests[0]["response_received"] is True


def test_transport_failure_single_attempt_and_no_response(tmp_path):
    calls = []

    def transport(*args):
        calls.append(1)
        raise subject.official.ProviderTransportError("fixture transport failure")

    client = make_client(tmp_path, transport=transport)
    with pytest.raises(subject.official.ProviderTransportError):
        client.complete(MESSAGES)
    assert calls == [1]
    assert client.requests[0]["response_received"] is False
    assert client.requests[0]["transport_started"] is True


def test_task_call_cap_is_eight_without_automatic_retry(tmp_path):
    calls = []
    client = make_client(
        tmp_path, transport=lambda *args: calls.append(1) or envelope()
    )
    for step in range(1, 9):
        client.complete(MESSAGES, step=step)
    with pytest.raises(subject.official.ProviderPayloadError, match="cap reached"):
        client.complete(MESSAGES, step=9)
    assert len(calls) == len(client.requests) == 8
    assert len({r["local_request_id"] for r in client.requests}) == 8


@pytest.mark.parametrize("raised", [False, True])
def test_429_stops_subsequent_dispatch_even_when_transport_raises(tmp_path, raised):
    calls = []

    def transport(*args):
        calls.append(1)
        if raised:
            raise subject.official.ProviderPausedError("fixture quota")
        return envelope(status=429)

    client = make_client(tmp_path, transport=transport)
    with pytest.raises(subject.official.ProviderPausedError):
        client.complete(MESSAGES)
    assert client._pacer.stopped.is_set()
    assert client.requests[0]["http_status"] == 429
    assert client.requests[0]["http_response_received"] is True
    assert client.requests[0]["response_received"] is False
    with pytest.raises(subject.DispatchStopped):
        client.complete(MESSAGES)
    assert calls == [1]


def test_payload_changed_after_commitment_never_reaches_transport(
    tmp_path, monkeypatch
):
    original = subject.ds._payload
    built = []
    calls = []

    def unstable_payload(client, messages):
        value = original(client, messages)
        built.append(1)
        if len(built) == 2:
            value["max_tokens"] = 513
        return value

    monkeypatch.setattr(subject.ds, "_payload", unstable_payload)
    client = make_client(
        tmp_path, transport=lambda *args: calls.append(1) or envelope()
    )
    with pytest.raises(subject.official.ProviderPayloadError, match="payload changed"):
        client.complete(MESSAGES)
    assert calls == []
    assert client.requests[0]["transport_started"] is False


def test_provider_tools_cannot_be_injected(tmp_path, monkeypatch):
    original = subject.ds._payload

    def tool_payload(client, messages):
        return {**original(client, messages), "tools": []}

    monkeypatch.setattr(subject.ds, "_payload", tool_payload)
    calls = []
    client = make_client(
        tmp_path, transport=lambda *args: calls.append(1) or envelope()
    )
    with pytest.raises(subject.official.ProviderPayloadError, match="tools"):
        client.complete(MESSAGES)
    assert calls == []


@pytest.mark.parametrize(
    "group,model",
    [
        ("typo", "deepseek-v4-pro"),
        ("deepseek_flash", "deepseek-v4-flash"),
        ("deepseek_flash", "deepseek-v4-pro"),
        ("gemini_flash", "gemini-replacement"),
    ],
)
def test_group_identity_and_retired_service_do_not_fallback(tmp_path, group, model):
    with pytest.raises(subject.official.ProviderIdentityError):
        make_client(tmp_path, model_group=group, model=model)


@pytest.mark.parametrize(
    "field,value",
    [
        ("allow_paid_tier", True),
        ("billing_tier", "paid"),
        ("monetary_hard_limit_usd", 1),
    ],
)
def test_paid_gemini_policy_rejected(tmp_path, monkeypatch, field, value):
    policy = subject._gemini_policy()
    policy["gemini"][field] = value
    monkeypatch.setattr(subject, "_gemini_policy", lambda: policy)
    with pytest.raises(subject.official.ProviderPayloadError, match="free-only"):
        make_client(tmp_path, model_group="gemini_flash")


def test_development_budget_and_current_tariff_not_historical_ceiling():
    for model, (_, miss, output) in subject.PEAK_TARIFF.items():
        policy = subject.deepseek_policy(model)
        budget = subject.DevelopmentBudgetState("deepseek", policy)
        assert (
            policy["deepseek"]["hard_spend_limit_cny"]
            == 8 * (miss + 512 * output / 1_000_000) + 1
        )
        assert policy["deepseek"]["hard_spend_limit_cny"] > 8
        for _ in range(8):
            budget.assert_before_request()
            budget.record_usage(
                {
                    "prompt_tokens": 1_000_000,
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 1_000_000,
                    "completion_tokens": 512,
                }
            )


def test_cost_is_peak_estimate_not_invoice_and_marks_missing_usage():
    requests = [
        {
            "response_received": True,
            "usage": {
                "prompt_cache_hit_tokens": 1_000_000,
                "prompt_cache_miss_tokens": 1_000_000,
                "completion_tokens": 1_000_000,
            },
        }
    ]
    assert subject.request_cost(requests, "deepseek-v4-pro")["amount"] == 36.3
    flash = subject.request_cost(requests, "deepseek-flash")
    assert flash["amount"] == 10.04 and flash["off_peak_lower_estimate"] == 5.02
    assert "not_invoice" in flash["basis"]
    missing = subject.request_cost([{"response_received": True}], "deepseek-flash")
    assert (
        missing["usage_complete"] is False and missing["unpriced_response_count"] == 1
    )
    assert missing["basis"] == "known_usage_subtotal_not_total_cost_upper_bound"
    assert missing["off_peak_lower_estimate"] is None
    gemini = subject.request_cost(requests, "gemini-3.6-flash")
    assert gemini["amount"] == 0 and gemini["paid_fallback"] is False
    assert "not_billing_api_verified" in gemini["basis"]


class FakeHTTPResponse(io.BytesIO):
    def __init__(self, raw, status=200):
        super().__init__(raw)
        self.status = status
        self.headers = {"x-request-id": "http-fixture-request"}


@pytest.mark.parametrize("raw", [b"not-json-private-response-body", b"[]", b"\xff"])
def test_http_200_invalid_json_still_response_bearing(tmp_path, monkeypatch, raw):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(1)
        return FakeHTTPResponse(raw)

    monkeypatch.setattr(subject.urllib_request, "urlopen", fake_urlopen)
    client = make_client(tmp_path, transport=None)
    with pytest.raises(subject.official.ProviderTransportError):
        client.complete(MESSAGES)
    assert calls == [1]
    assert client.requests[0]["response_received"] is True
    assert client.requests[0]["http_response_received"] is True
    assert "not-json-private" not in (tmp_path / "requests.jsonl").read_text(
        encoding="utf-8"
    )


def test_real_path_httperror_429_stops_without_retry(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(1)
        raise urllib_error.HTTPError(
            request.full_url,
            429,
            "quota",
            {"x-request-id": "quota-id"},
            io.BytesIO(b"private quota error body"),
        )

    monkeypatch.setattr(subject.urllib_request, "urlopen", fake_urlopen)
    client = make_client(tmp_path, transport=None)
    with pytest.raises(subject.official.ProviderPausedError):
        client.complete(MESSAGES)
    assert client._pacer.stopped.is_set() and calls == [1]
    assert client.requests[0]["provider_request_id"] == "quota-id"
    assert "private quota" not in (tmp_path / "requests.jsonl").read_text(
        encoding="utf-8"
    )


def test_real_transport_path_receipt_is_not_misclassified_as_injected(
    tmp_path, monkeypatch
):
    raw = json.dumps(envelope().body).encode()
    monkeypatch.setattr(
        subject.urllib_request, "urlopen", lambda *args, **kwargs: FakeHTTPResponse(raw)
    )
    client = make_client(tmp_path, transport=None)
    result = client.complete(MESSAGES)
    assert result.receipt["evidence"]["transport_kind"] == "official_network"
    assert client.last_receipt["evidence"]["transport_kind"] == "official_network"
    assert client.last_request_metadata["transport_kind"] == "official_network"


@pytest.mark.parametrize("field", ["id", "model", "header"])
def test_echoed_active_credential_never_enters_request_log(tmp_path, field):
    reply = envelope(body_changes={field: OFFLINE_KEY} if field != "header" else {})
    if field == "header":
        reply = subject.official.HTTPResponseEnvelope(
            200, {"x-request-id": OFFLINE_KEY}, reply.body
        )
    client = make_client(tmp_path, transport=lambda *args: reply)
    with pytest.raises(subject.official.ProviderPayloadError, match="echoed"):
        client.complete(MESSAGES)
    assert OFFLINE_KEY not in (tmp_path / "requests.jsonl").read_text(encoding="utf-8")
    assert client.requests[0]["response_received"] is True


def test_unapproved_cost_identity_is_not_silently_zero_billed():
    with pytest.raises(ValueError, match="exact approved"):
        subject.request_cost([], "gemini-substitute")


def test_gemini_recovery_settings_reach_transport_and_all_receipts(tmp_path):
    observed = []

    def transport(endpoint, headers, payload, timeout):
        del endpoint, headers
        assert payload["max_tokens"] == 2048
        assert payload["reasoning_effort"] == "low"
        assert payload["temperature"] == 0 and timeout == 180
        assert "tools" not in payload and "tool_choice" not in payload
        started = log_rows(tmp_path / "requests.jsonl")[0]
        assert started["max_tokens"] == 2048
        assert started["reasoning_effort"] == "low"
        assert started["generation_profile"] == "gemini_recovery_v1"
        assert started["payload_sha256"] == subject.sha256_canonical_json(payload)
        observed.append(copy.deepcopy(payload))
        return envelope("gemini-3.6-flash")

    client = make_client(
        tmp_path,
        model_group="gemini_flash",
        transport=transport,
        generation_profile="gemini_recovery_v1",
    )
    result = client.complete(MESSAGES)
    assert len(observed) == 1 and result.provider_attempts == 1
    assert client.max_tokens == 2048 and client.reasoning_effort == "low"
    assert result.receipt["evidence"]["max_tokens"] == 2048
    assert result.receipt["evidence"]["reasoning_effort"] == "low"
    assert client.requests[0]["reasoning_effort"] == "low"
    assert client.requests[0]["payload_sha256"] == result.receipt["evidence"]["payload_sha256"]
    assert subject._gemini_policy()["deepseek"]["dynamic_fuse"]["next_request_output_tokens_upper_bound"] == 512


def test_remaining_call_budget_is_enforced_before_new_transport(tmp_path):
    calls = []
    client = make_client(
        tmp_path,
        model_group="gemini_flash",
        generation_profile="gemini_recovery_v1",
        max_provider_calls=3,
        transport=lambda *args: calls.append(1) or envelope("gemini-3.6-flash"),
    )
    assert client.max_provider_calls == 3
    for step in range(1, 4):
        client.complete(MESSAGES, step=step)
    with pytest.raises(subject.official.ProviderPayloadError, match="cap reached"):
        client.complete(MESSAGES, step=4)
    assert len(calls) == len(client.requests) == 3


def test_default_gemini_payload_is_unchanged_without_recovery_profile(tmp_path):
    observed = []

    def transport(endpoint, headers, payload, timeout):
        del endpoint, headers, timeout
        observed.append(payload)
        return envelope("gemini-3.6-flash")

    client = make_client(tmp_path, model_group="gemini_flash", transport=transport)
    result = client.complete(MESSAGES)
    assert observed == [{
        "model": "gemini-3.6-flash",
        "messages": MESSAGES,
        "temperature": 0.0,
        "max_tokens": 512,
        "stream": False,
        "response_format": {"type": "json_object"},
    }]
    assert "reasoning_effort" not in result.receipt["evidence"]
    assert "generation_profile" not in result.receipt["evidence"]
    assert client.requests[0]["max_tokens"] == 512
    assert client.requests[0]["reasoning_effort"] is None
    assert client.max_provider_calls == 8


@pytest.mark.parametrize(
    "model_group,profile",
    [
        ("deepseek_pro", "gemini_recovery_v1"),
        ("deepseek_flash", "gemini_recovery_v1"),
        ("gemini_flash", "unapproved_profile"),
        ("gemini_flash", ""),
        ("gemini_flash", True),
    ],
)
def test_generation_profile_cannot_change_other_models_or_unknown_settings(
    tmp_path, model_group, profile
):
    with pytest.raises(subject.official.ProviderPayloadError, match="generation profile"):
        make_client(tmp_path, model_group=model_group, generation_profile=profile)
    assert not (tmp_path / "requests.jsonl").exists()


@pytest.mark.parametrize("limit", [0, -1, 9, True, 1.0, None])
def test_remaining_call_budget_rejects_invalid_bounds(tmp_path, limit):
    with pytest.raises(subject.official.ProviderPayloadError, match="1..8"):
        make_client(tmp_path, max_provider_calls=limit)
    assert not (tmp_path / "requests.jsonl").exists()


def test_recovery_503_uses_budget_without_implicit_retry(tmp_path):
    calls = []
    client = make_client(
        tmp_path,
        model_group="gemini_flash",
        generation_profile="gemini_recovery_v1",
        max_provider_calls=1,
        transport=lambda *args: calls.append(1) or envelope("gemini-3.6-flash", status=503),
    )
    with pytest.raises(subject.official.ProviderTransportError):
        client.complete(MESSAGES)
    with pytest.raises(subject.official.ProviderPayloadError, match="cap reached"):
        client.complete(MESSAGES)
    assert len(calls) == 1
    assert client.requests[0]["http_status"] == 503
    assert client.requests[0]["response_received"] is False
    assert client.requests[0]["max_tokens"] == 2048


@pytest.mark.parametrize("effort", ["high", "none", "", False])
def test_gemini_client_rejects_unapproved_reasoning_effort(effort):
    policy = subject._gemini_policy()
    with pytest.raises(subject.official.ProviderPayloadError, match="reasoning effort"):
        subject.gm.GeminiJsonOfficialClient(
            provider_id="gemini",
            api_key=OFFLINE_KEY,
            content_class="synthetic_m3_case",
            budget_state=subject.official.ProviderBudgetState("gemini", policy),
            policy=policy,
            reasoning_effort=effort,
            transport=lambda *args: pytest.fail("invalid config must not make a request"),
        )
