from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import experiments.paper_v2.gemini_fallback_controller_v2 as fallback
import experiments.paper_v2.gemini_json_client_v1 as gemini_json
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    ProviderBudgetState,
    ProviderPausedError,
)


MESSAGES = [
    {"role": "system", "content": "Return JSON only."},
    {"role": "user", "content": "Synthetic Gemini JSON qualification."},
]


def _official_adapter(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value["evidence"]["transport_kind"] = "official_network"
    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def _traced_client(
    trace_path: Path,
    *,
    status_code: int = 200,
    work_key: str = "work-test",
    budget_state: ProviderBudgetState | None = None,
    usage_registry: gemini_json.GeminiUsageRegistry | None = None,
) -> gemini_json.GeminiJsonTracedProviderClient:
    policy = fallback._effective_policy()

    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> HTTPResponseEnvelope:
        del endpoint, headers, timeout
        rows = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
        ]
        commitment = rows[-1]["event"]["commitment"]
        assert rows[-1]["event"]["event_type"] == "started"
        assert payload["response_format"] == {"type": "json_object"}
        assert commitment["payload_sha256"] == sha256_canonical_json(payload)
        return HTTPResponseEnvelope(
            status_code=status_code,
            headers={"x-goog-request-id": "gemini-json-request-test"},
            body=(
                {}
                if status_code != 200
                else {
                    "id": f"gemini-json-response-{work_key}",
                    "model": payload["model"],
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "{\"tool\":\"final\",\"arguments\":{\"answer\":\"SAFE\"}}",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 4,
                        "total_tokens": 24,
                    },
                }
            ),
        )

    official = gemini_json.GeminiJsonOfficialClient(
        provider_id="gemini",
        api_key="unit-test-key",
        content_class="synthetic_m3_case",
        budget_state=(
            budget_state
            or ProviderBudgetState(provider_id="gemini", policy=policy)
        ),
        policy=policy,
        temperature=0.0,
        max_tokens=64,
        timeout=30.0,
        transport=transport,
    )
    return gemini_json.GeminiJsonTracedProviderClient(
        official,
        execution_identity="execution-test",
        work_key=work_key,
        trace_path=trace_path,
        admission_manifest_sha256="a" * 64,
        recorded_at=lambda: "2026-08-02T00:30:00+08:00",
        receipt_adapter=_official_adapter,
        usage_registry=usage_registry,
    )


def test_json_payload_is_precommitted_before_transport(tmp_path: Path) -> None:
    client = _traced_client(tmp_path / "trace.jsonl")

    completion = client.complete(MESSAGES, step=1)
    bundle = client.build_bundle()

    assert completion.text
    assert bundle["bundle_status"] == "completed"
    assert bundle["result_tier_ceiling"] == "formal_candidate"
    assert bundle["open_request_count"] == 0
    assert bundle["usage_summary"]["charged_usd"] == 0.0
    serialized = json.dumps(bundle)
    assert "unit-test-key" not in serialized
    assert "Synthetic Gemini JSON qualification" not in serialized


def test_first_429_stays_diagnostic_without_retry(tmp_path: Path) -> None:
    client = _traced_client(tmp_path / "trace.jsonl", status_code=429)

    with pytest.raises(ProviderPausedError):
        client.complete(MESSAGES, step=1)

    bundle = client.build_bundle()
    assert bundle["bundle_status"] == "incomplete_paused"
    assert bundle["result_tier_ceiling"] == "diagnostic"
    assert bundle["request_count"] == 1
    assert bundle["open_request_count"] == 1


def test_offline_qualification_covers_vigil_json_path() -> None:
    qualification = gemini_json.build_qualification()

    assert qualification["status"] == "offline_json_payload_and_vigil_qualified"
    assert qualification["response_format"] == {"type": "json_object"}
    assert qualification["vigil_decisions"] == {
        "read_report": "ALLOW",
        "send_report": "ASK",
        "delete_record": "DENY",
    }
    assert qualification["provider_calls"] == 1
    assert qualification["network_calls"] == 0


def test_persisted_qualification_rebuilds_exactly() -> None:
    observed = gemini_json.verify_qualification()
    assert observed == gemini_json.build_qualification()


def test_shared_registry_cross_binds_two_work_items(tmp_path: Path) -> None:
    policy = fallback._effective_policy()
    budget = ProviderBudgetState(provider_id="gemini", policy=policy)
    registry = gemini_json.GeminiUsageRegistry()
    first = _traced_client(
        tmp_path / "first.jsonl",
        work_key="work-first",
        budget_state=budget,
        usage_registry=registry,
    )
    second = _traced_client(
        tmp_path / "second.jsonl",
        work_key="work-second",
        budget_state=budget,
        usage_registry=registry,
    )

    first.complete(MESSAGES, step=1)
    second.complete(MESSAGES, step=1)

    assert first.build_bundle()["usage_evidence"][0]["cumulative_usage"][
        "requests"
    ] == 1
    assert second.build_bundle()["usage_evidence"][0]["cumulative_usage"][
        "requests"
    ] == 2
    assert len(registry.prior_items()) == 2


def test_shared_usage_qualification_rebuilds_exactly() -> None:
    observed = gemini_json.verify_shared_usage_qualification()

    assert observed["status"] == (
        "two_work_item_cumulative_usage_qualified_offline"
    )
    assert [item["cumulative_requests"] for item in observed["summaries"]] == [
        1,
        2,
    ]
    assert observed["provider_calls"] == 2
    assert observed["network_calls"] == 0
