from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import pytest

import experiments.paper_v2.gemini_public_controller_v3 as controller
from experiments.paper_v2.gemini_json_client_v1 import (
    GeminiJsonTracedProviderClient,
    GeminiUsageRegistry,
)


def test_v2_supersession_is_zero_call_and_non_destructive() -> None:
    value = controller.build_v2_supersession_review()

    assert value["status"] == "v2_superseded_before_execution"
    assert value["v2_nonempty_output_files"] == 0
    assert value["provider_calls_made"] == 0
    assert value["network_calls_made"] == 0
    assert value["deletion_performed"] is False


def test_v3_qualification_binds_cross_work_usage_fix() -> None:
    value = controller.build_offline_qualification()

    assert value["status"] == (
        "offline_gemini_json_shared_usage_canary_qualified"
    )
    assert value["plan_records"] == 1791
    assert value["canary_records"] == 12
    assert value["shared_usage_work_items"] == 2
    assert value["shared_usage_provider_calls"] == 2
    assert value["network_calls_made"] == 0


def test_v3_admission_is_free_only_and_exact_command() -> None:
    value = controller.validate_canary_admission(
        controller._read_json(controller.DEFAULT_ADMISSION)
    )

    assert value["authorization"]["canary_execution_authorized"] is True
    assert value["authorization"]["matrix_continuation_authorized"] is False
    assert value["controls"]["billing_tier"] == "free"
    assert value["controls"]["paid_ceiling_usd"] == 0.0
    assert value["controls"]["automatic_retries"] == 0
    assert "gemini_public_controller_v3" in value["exact_command"]


def test_v3_dispatcher_injects_one_shared_usage_registry(
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

    traced_factory = captured["traced_client_class"]
    assert result == "dispatcher"
    assert isinstance(traced_factory, functools.partial)
    assert traced_factory.func is GeminiJsonTracedProviderClient
    assert isinstance(
        traced_factory.keywords["usage_registry"], GeminiUsageRegistry
    )


def test_v2_supersession_rejects_nonempty_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = controller.v2.verify_canary_candidate()
    admission = controller.v2.validate_canary_admission(
        controller.v2._read_json(controller.v2.DEFAULT_ADMISSION)
    )
    (tmp_path / "evidence.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        controller.v2, "verify_canary_candidate", lambda: candidate
    )
    monkeypatch.setattr(
        controller.v2,
        "validate_canary_admission",
        lambda value: admission,
    )
    monkeypatch.setattr(controller.v2, "OUTPUT_ROOT", tmp_path)

    with pytest.raises(
        controller.GeminiPublicControllerV3Error,
        match="cannot be superseded",
    ):
        controller.build_v2_supersession_review()
