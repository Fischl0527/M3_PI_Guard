from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

import experiments.paper_v2.gemini_public_controller_v1 as controller


def test_offline_qualification_covers_exact_public_mirror() -> None:
    value = controller.build_offline_qualification()

    assert value["status"] == "offline_interfaces_qualified_live_canary_pending"
    assert value["plan_records"] == 1791
    assert value["canary_records"] == 12
    assert value["resolver_probe_count"] == 4
    assert value["controls"] == {
        "billing_tier": "free",
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_managed_tools_enabled": False,
        "external_effects_enabled": False,
        "first_http_429": "seal_current_run",
    }
    assert value["network_calls_made"] == 0
    assert value["scientific_outcomes_read"] == 0


def test_candidate_is_result_blind_and_command_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    qualification = controller.build_offline_qualification()
    monkeypatch.setattr(
        controller,
        "verify_offline_qualification",
        lambda: qualification,
    )
    monkeypatch.setattr(
        controller,
        "_sha256_file",
        lambda path: (
            "f" * 64
            if path == controller.DEFAULT_QUALIFICATION
            else hashlib.sha256(path.read_bytes()).hexdigest()
        ),
    )

    candidate = controller.build_canary_candidate()

    assert candidate["status"] == "candidate_pending_exact_command_admission"
    assert candidate["canary_records"] == 12
    assert candidate["result_admission_authorized"] is False
    assert candidate["scientific_outcomes_read"] == 0
    assert "--execute-canary" in candidate["exact_command"]


def test_admission_requires_exact_owner_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = {
        "manifest_sha256": "c" * 64,
        "exact_command": controller.canonical_canary_command(),
        "run_id": controller.RUN_ID,
        "execution_identity": "e" * 64,
        "canary_records": 12,
        "canary_work_key_sequence_sha256": "w" * 64,
        "controls": controller.build_offline_qualification()["controls"],
    }
    monkeypatch.setattr(controller, "verify_canary_candidate", lambda: candidate)

    with pytest.raises(
        controller.GeminiPublicControllerV1Error,
        match="authorization digest drift",
    ):
        controller.build_canary_admission(
            owner_statement_sha256="0" * 64,
            approved_at="2026-08-02T00:00:00+08:00",
        )

    value = controller.build_canary_admission(
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
        approved_at="2026-08-02T00:00:00+08:00",
    )
    assert value["authorization"]["canary_execution_authorized"] is True
    assert value["authorization"]["matrix_continuation_authorized"] is False
    assert value["controls"]["paid_ceiling_usd"] == 0.0


def test_superseded_v1_cannot_execute() -> None:
    with pytest.raises(
        controller.GeminiPublicControllerV1Error,
        match="superseded",
    ):
        controller.execute_canary(
            admission_path=controller.DEFAULT_ADMISSION,
            permit_loader=lambda path: SimpleNamespace(run_id=controller.RUN_ID),
        )
