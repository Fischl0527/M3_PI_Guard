from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.public_live_controller_v2 import (
    _canary_rows,
    PublicLiveControllerError,
    build_canary_admission,
    canonical_canary_command,
    validate_canary_admission,
)


def test_public_canary_admission_binds_primary_exact_command() -> None:
    value = build_canary_admission(
        "primary",
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-28T00:40:00+08:00",
    )

    assert value["scope"]["model_role"] == "primary"
    assert value["scope"]["model_id"] == "deepseek-v4-pro"
    assert value["scope"]["canary_records"] == 24
    assert value["scope"]["exact_command"] == canonical_canary_command(
        "primary"
    )
    assert "public_live_controller_v2" in value["scope"]["exact_command"]
    assert value["scope"]["execution_identity"] == _canary_rows("primary")[
        0
    ]["execution_identity"]
    assert value["authorization"]["canary_execution_authorized"] is True
    assert value["authorization"]["matrix_continuation_authorized"] is False
    assert value["authorization"]["result_admission_authorized"] is False


def test_public_canary_admission_binds_flash_as_cross_model() -> None:
    value = build_canary_admission(
        "second",
        owner_statement_sha256="b" * 64,
        approved_at="2026-07-28T00:40:00+08:00",
    )

    assert value["scope"]["model_id"] == "deepseek-v4-flash"
    assert value["scope"]["canary_records"] == 12


def test_public_canary_admission_rejects_command_drift() -> None:
    value = build_canary_admission(
        "primary",
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-28T00:40:00+08:00",
    )
    drifted = copy.deepcopy(value)
    drifted["scope"]["exact_command"] += " --unsafe"

    with pytest.raises(
        PublicLiveControllerError,
        match="digest/scope drift",
    ):
        validate_canary_admission(drifted, model_role="primary")
