from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import experiments.paper_v2.gemini_public_controller_v2 as controller
from experiments.paper_v2.gemini_json_client_v1 import (
    GeminiJsonOfficialClient,
    GeminiJsonTracedProviderClient,
)


def test_v1_is_superseded_only_when_no_execution_evidence_exists() -> None:
    value = controller.build_v1_supersession_review()

    assert value["status"] == "v1_superseded_before_execution"
    assert value["v1_nonempty_output_files"] == 0
    assert value["provider_calls_made"] == 0
    assert value["network_calls_made"] == 0
    assert value["deletion_performed"] is False


def test_v2_qualification_binds_json_vigil_and_public_plan() -> None:
    value = controller.build_offline_qualification()

    assert value["status"] == "offline_gemini_json_public_canary_qualified"
    assert value["plan_records"] == 1791
    assert value["canary_records"] == 12
    assert value["network_calls_made"] == 0
    assert value["credentials_read"] is False
    assert len(value["json_client_qualification_sha256"]) == 64
    assert len(value["vigil_constraint_set_sha256"]) == 64


def test_v2_admission_is_exact_command_and_free_only() -> None:
    value = controller.validate_canary_admission(
        controller._read_json(controller.DEFAULT_ADMISSION)
    )

    assert value["authorization"] == {
        "canary_execution_authorized": True,
        "matrix_continuation_authorized": False,
        "result_admission_authorized": False,
    }
    assert value["controls"]["billing_tier"] == "free"
    assert value["controls"]["paid_ceiling_usd"] == 0.0
    assert value["controls"]["automatic_retries"] == 0
    assert "gemini_public_controller_v2" in value["exact_command"]


def test_v2_dispatcher_injects_json_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_builder(*args: Any, **kwargs: Any) -> str:
        captured.update(kwargs)
        return "dispatcher"

    monkeypatch.setattr(controller.v1, "_build_dispatcher", fake_builder)
    result = controller._build_dispatcher(
        object(),
        api_key="not-persisted",
        policy={},
        call_sink=object(),
        budget_state=object(),
    )

    assert result == "dispatcher"
    assert captured["official_client_class"] is GeminiJsonOfficialClient
    assert captured["traced_client_class"] is GeminiJsonTracedProviderClient


def test_v1_supersession_rejects_nonempty_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = controller.v1.verify_canary_candidate()
    admission = controller.v1.validate_canary_admission(
        controller.v1._read_json(controller.v1.DEFAULT_ADMISSION)
    )
    (tmp_path / "evidence.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        controller.v1, "verify_canary_candidate", lambda: candidate
    )
    monkeypatch.setattr(
        controller.v1,
        "validate_canary_admission",
        lambda value: admission,
    )
    monkeypatch.setattr(controller.v1, "OUTPUT_ROOT", tmp_path)

    with pytest.raises(
        controller.GeminiPublicControllerV2Error,
        match="cannot be superseded",
    ):
        controller.build_v1_supersession_review()


def test_superseded_v2_cannot_execute() -> None:
    with pytest.raises(
        controller.GeminiPublicControllerV2Error,
        match="superseded",
    ):
        controller.execute_canary(admission_path=controller.DEFAULT_ADMISSION)
