from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

import experiments.paper_v2.gemini_daily_quota_ledger_v1 as quota
import experiments.paper_v2.gemini_public_controller_v5 as controller
from experiments.paper_v2 import official_provider_executor as official
from experiments.paper_v2.gemini_public_execution_store_v1 import (
    load_record_entries,
)


@pytest.fixture(scope="module")
def real_candidate() -> dict[str, Any]:
    return controller.build_candidate()


def test_real_candidate_selects_only_ten_untouched_canary_rows(
    real_candidate: dict[str, Any],
) -> None:
    value = controller.validate_candidate(real_candidate)
    scope = value["scope"]
    boundary = scope["historical_boundary"]
    keys = [
        key for segment in scope["segments"] for key in segment["work_keys"]
    ]

    assert scope["combined_canary_slots"] == 12
    assert scope["pending_records"] == len(keys) == 10
    assert boundary["historical_slots"] == 2
    assert boundary["historical_records"] == 1
    assert boundary["historical_aborts_retained_in_itt"] == 1
    assert boundary["historical_terminal_record_work_key"] not in keys
    assert boundary["historical_aborted_work_key"] not in keys
    assert all(
        segment["maximum_provider_requests"] <= quota.LOCAL_REQUEST_CAP
        for segment in scope["segments"]
    )
    assert value["authorization"]["segment_execution_authorized"] is False
    assert value["authorization"]["historical_retry_authorized"] is False
    assert value["evidence_boundary"]["network_calls_made"] == 0


def test_admission_is_exact_free_only_and_non_result_authorizing(
    real_candidate: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        controller,
        "verify_candidate",
        lambda: copy.deepcopy(real_candidate),
    )

    admission = controller.build_segment_admission(
        0,
        quota_day="2026-08-04",
        approved_at="2026-08-04T15:01:00+08:00",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
    )

    assert admission["quota_day"] == "2026-08-04"
    assert admission["authorization"]["paid_ceiling_usd"] == 0.0
    assert admission["authorization"]["automatic_retries"] == 0
    assert admission["authorization"]["provider_tools_enabled"] is False
    assert admission["authorization"]["external_effects_enabled"] is False
    assert admission["authorization"]["result_admission_authorized"] is False
    assert "gemini_public_controller_v5" in admission["exact_command"]


def test_admission_rejects_unapproved_owner_digest(
    real_candidate: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        controller,
        "verify_candidate",
        lambda: copy.deepcopy(real_candidate),
    )

    with pytest.raises(
        controller.GeminiPublicControllerV5Error,
        match="owner authorization digest drift",
    ):
        controller.build_segment_admission(
            0,
            quota_day="2026-08-04",
            approved_at="2026-08-04T15:01:00+08:00",
            owner_statement_sha256="0" * 64,
        )


def test_injected_missing_request_id_completes_v2_contract_record(
    real_candidate: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    boundary = real_candidate["scope"]["historical_boundary"]
    source_row = next(
        copy.deepcopy(row)
        for row in controller._pending_source_rows(boundary)
        if row["benchmark"] == "m3-v2"
        and row["condition_id"]
        == "strongest_peer_reviewed_structural_baseline"
    )
    identity = "e" * 64
    segment = {
        "segment_index": 0,
        "run_id": "public-v5-contract-e2e",
        "execution_identity": identity,
        "work_keys": [source_row["work_key"]],
        "work_key_sequence_sha256": controller.sha256_canonical_json(
            [source_row["work_key"]]
        ),
        "record_count": 1,
        "maximum_provider_requests": source_row["max_provider_calls"],
        "output_root": "outputs/public-v5-contract-e2e",
    }
    candidate: dict[str, Any] = {
        "manifest_sha256": "c" * 64,
        "scope": {
            "historical_boundary": boundary,
            "segments": [segment],
            "max_tokens": 128,
            "timeout_seconds": 10.0,
        },
    }
    monkeypatch.setattr(controller, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(controller, "PROTOCOL_ROOT", tmp_path / "protocols")
    monkeypatch.setattr(
        controller,
        "verify_candidate",
        lambda: copy.deepcopy(candidate),
    )
    monkeypatch.setattr(
        controller,
        "_pending_source_rows",
        lambda boundary=None: [copy.deepcopy(source_row)],
    )
    monkeypatch.setattr(
        controller.public_v1,
        "PublicFrozenAgentDojoCaseResolverV2",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        controller.public_v1,
        "PinnedPromptGuardDetector",
        lambda **_: object(),
    )
    quota_day = controller.daily_quota.current_quota_day()
    controller.write_segment_admission(
        0,
        quota_day=quota_day,
        approved_at="2026-08-04T15:01:00+08:00",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
    )
    real_reserve = controller.daily_quota.reserve_formal_day
    quota_ledger = tmp_path / "quota_days.jsonl"

    def reserve_in_tmp(**kwargs: object) -> dict[str, object]:
        return real_reserve(**kwargs, path=quota_ledger)

    monkeypatch.setattr(
        controller.daily_quota,
        "reserve_formal_day",
        reserve_in_tmp,
    )
    responses: list[str] = []

    def transport(*_: object) -> official.HTTPResponseEnvelope:
        response_id = f"response-public-v5-e2e-{len(responses) + 1}"
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
            # Deliberately omit Google's provider request ID.  The official
            # response ID and pretransport local commitment must be sufficient.
            headers={},
            body={
                "id": response_id,
                "model": controller.MODEL_ID,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
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
    records = load_record_entries(
        tmp_path
        / "outputs/public-v5-contract-e2e/experiment_records_v2_contract.jsonl"
    )

    assert result["record_count"] == 1
    assert result["remaining_records"] == 0
    assert result["paid_ceiling_usd"] == 0.0
    assert len(responses) == 2
    assert review["technical_gate_passed"] is True, review["checks"]
    assert review["checks"]["all_v2_contract_attestations"] is True
    attestation = records[0]["record"]["provider_attestation"]
    assert attestation["request_id"] is None
    assert attestation["provider_request_id_available"] is False
    assert attestation["formal_evidence_contract"] == (
        controller.trace_runtime_v2.CONTRACT_ID
    )
    assert quota_ledger.is_file()
