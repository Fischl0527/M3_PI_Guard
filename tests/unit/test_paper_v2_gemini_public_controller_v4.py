from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

import experiments.paper_v2.gemini_daily_quota_ledger_v1 as quota
import experiments.paper_v2.gemini_public_controller_v4 as controller
from experiments.paper_v2 import official_provider_executor as official


def test_worst_case_calls_are_packed_into_separate_quota_days() -> None:
    rows = [
        {"work_key": "vigil-1", "max_provider_calls": 16},
        {"work_key": "m3-1", "max_provider_calls": 8},
        {"work_key": "m3-2", "max_provider_calls": 8},
        {"work_key": "vigil-2", "max_provider_calls": 16},
    ]

    segments = controller._pack_rows(rows)

    assert [[row["work_key"] for row in segment] for segment in segments] == [
        ["vigil-1"],
        ["m3-1", "m3-2"],
        ["vigil-2"],
    ]
    assert all(
        sum(row["max_provider_calls"] for row in segment)
        <= quota.LOCAL_REQUEST_CAP
        for segment in segments
    )


def test_pack_rejects_one_work_item_above_daily_cap() -> None:
    with pytest.raises(
        controller.GeminiPublicControllerV4Error,
        match="unsafe provider-call cap",
    ):
        controller._pack_rows(
            [{"work_key": "too-large", "max_provider_calls": 19}]
        )


def test_daily_policy_uses_segment_request_cap() -> None:
    policy = controller._daily_policy(16)

    assert policy["gemini"]["local_batch_caps"] == {
        "requests": 16,
        "input_tokens": 200_000,
        "output_tokens": 16_000,
    }
    assert policy["gemini"]["billing_tier"] == "free"


def test_admission_binds_quota_day_and_zero_paid_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate: dict[str, Any] = {
        "manifest_sha256": "c" * 64,
        "scope": {
            "segments": [
                {
                    "run_id": "run",
                    "execution_identity": "identity",
                    "work_key_sequence_sha256": "w" * 64,
                    "maximum_provider_requests": 16,
                }
            ]
        },
    }
    monkeypatch.setattr(controller, "verify_candidate", lambda: candidate)

    admission = controller.build_segment_admission(
        0,
        quota_day="2026-08-01",
        approved_at="2026-08-02T06:30:00+08:00",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
    )

    assert admission["quota_day"] == "2026-08-01"
    assert admission["maximum_provider_requests"] == 16
    assert admission["authorization"]["paid_ceiling_usd"] == 0.0
    assert admission["authorization"]["automatic_retries"] == 0
    assert admission["authorization"][
        "same_day_other_formal_gemini_work_authorized"
    ] is False


def test_execute_segment_injected_transport_attaches_complete_trace_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    quota_day = "2026-08-02"
    source_row = next(
        copy.deepcopy(row)
        for row in controller._source_rows()
        if row["benchmark"] == "m3-v2"
        and row["condition_id"]
        == "strongest_peer_reviewed_structural_baseline"
    )
    identity = "e" * 64
    segment = {
        "segment_index": 0,
        "run_id": "public-v4-e2e",
        "execution_identity": identity,
        "work_keys": [source_row["work_key"]],
        "work_key_sequence_sha256": controller.sha256_canonical_json(
            [source_row["work_key"]]
        ),
        "record_count": 1,
        "maximum_provider_requests": source_row["max_provider_calls"],
        "output_root": "outputs/public-v4-e2e",
    }
    candidate: dict[str, Any] = {
        "manifest_sha256": "c" * 64,
        "scope": {
            "segments": [segment],
            "max_tokens": 128,
            "timeout_seconds": 10.0,
        },
    }

    monkeypatch.setattr(controller, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(controller, "PROTOCOL_ROOT", tmp_path / "protocols")
    monkeypatch.setattr(
        controller, "verify_candidate", lambda: copy.deepcopy(candidate)
    )
    monkeypatch.setattr(
        controller, "_source_rows", lambda: [copy.deepcopy(source_row)]
    )
    monkeypatch.setattr(
        controller.v1,
        "PublicFrozenAgentDojoCaseResolverV2",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        controller.v1, "PinnedPromptGuardDetector", lambda **_: object()
    )
    controller.write_segment_admission(
        0,
        quota_day=quota_day,
        approved_at="2026-08-02T12:30:00+08:00",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
    )

    real_reserve = controller.daily_quota.reserve_formal_day
    quota_ledger = tmp_path / "quota_days.jsonl"

    def reserve_in_tmp(**kwargs: object) -> dict[str, object]:
        return real_reserve(**kwargs, path=quota_ledger)

    monkeypatch.setattr(
        controller.daily_quota, "reserve_formal_day", reserve_in_tmp
    )
    monkeypatch.setattr(
        controller.daily_quota, "current_quota_day", lambda: quota_day
    )
    responses: list[str] = []

    def transport(*_: object) -> official.HTTPResponseEnvelope:
        response_id = f"response-public-e2e-{len(responses) + 1}"
        responses.append(response_id)
        content = (
            '{"constraints":[{"constraint_id":"forbid_delete",'
            '"constraint_type":"forbid","description":'
            '"Forbid deleting records.","tool_name":"delete_record",'
            '"priority":1}],"global_rules":[]}'
            if len(responses) == 1
            else '{"tool":"final","arguments":{"answer":"SAFE"}}'
        )
        return official.HTTPResponseEnvelope(
            status_code=200,
            headers={
                "x-goog-request-id": f"request-public-e2e-{len(responses)}"
            },
            body={
                "id": response_id,
                "model": controller.MODEL_ID,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 4,
                    "total_tokens": 24,
                },
            },
        )

    monkeypatch.setattr(official, "_default_transport", transport)
    values = {
        "M3_FRONTIER_API_CONSENT": "yes_for_network_smoke",
        "GEMINI_API_KEY": "unit-test-nonsecret-placeholder-value",
        "FRONTIER_GEMINI_MODEL_ID": controller.MODEL_ID,
        "FRONTIER_GEMINI_BASE_URL": (
            "https://generativelanguage.googleapis.com/v1beta/openai/"
        ),
    }
    result = controller.execute_segment(
        0,
        quota_day=quota_day,
        selected_admission=controller.admission_path(0, quota_day),
        credential_loader=lambda: values,
    )
    review = controller.build_segment_review(0, quota_day=quota_day)

    assert result["record_count"] == 1
    assert result["remaining_records"] == 0
    assert result["provider_calls_completed"] == len(responses) == 2
    assert result["paid_ceiling_usd"] == 0.0
    assert review["technical_gate_passed"] is True, review["checks"]
    assert review["checks"]["all_trace_bundles_complete"] is True
    assert review["checks"]["call_ledger_matches_trace_bundles"] is True
    assert review["scientific_outcomes_accessed"] is False
    assert quota_ledger.is_file()
