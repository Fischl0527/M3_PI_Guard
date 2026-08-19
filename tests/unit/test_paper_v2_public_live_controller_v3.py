from __future__ import annotations

import copy
import json
from typing import Any

import pytest

import experiments.paper_v2.public_live_controller_v3 as live
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import (
    PublicFrozenAgentDojoCaseResolverV2,
)
from experiments.paper_v2.public_m3_live_dependency_v3 import (
    PublicFrozenM3CaseResolverV3,
)
from experiments.paper_v2.public_matrix_controller_v3 import (
    DEFAULT_CANDIDATE,
)


def _candidate() -> dict[str, Any]:
    value = json.loads(DEFAULT_CANDIDATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_public_v3_canary_admission_binds_exact_primary_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(
        live,
        "verify_candidate",
        lambda: copy.deepcopy(candidate),
    )

    value = live.build_canary_admission(
        "primary",
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-28T13:20:00+08:00",
    )

    assert value["scope"]["model_role"] == "primary"
    assert value["scope"]["model_id"] == "deepseek-v4-pro"
    assert value["scope"]["canary_records"] == 24
    assert value["scope"]["exact_command"] == (
        live.canonical_canary_command("primary")
    )
    assert "public_live_controller_v3" in value["scope"]["exact_command"]
    assert "deepseek_public_primary_canary_admission_v3.json" in value[
        "scope"
    ]["exact_command"]
    assert value["scope"]["execution_identity"] == candidate["scope"][
        "model_roles"
    ]["primary"]["execution_identity"]
    assert value["authorization"]["canary_execution_authorized"] is True
    assert value["authorization"][
        "matrix_continuation_authorized"
    ] is False
    assert value["authorization"]["result_admission_authorized"] is False
    assert value["authorization"]["candidate_manifest_sha256"] == candidate[
        "manifest_sha256"
    ]
    assert value["authorization"]["candidate_scope_sha256"] == candidate[
        "scope_sha256"
    ]
    assert value["authorization"]["owner_statement_sha256"] == "a" * 64


def test_public_v3_canary_admission_rejects_command_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(
        live,
        "verify_candidate",
        lambda: copy.deepcopy(candidate),
    )
    value = live.build_canary_admission(
        "primary",
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-28T13:20:00+08:00",
    )
    drifted = copy.deepcopy(value)
    drifted["scope"]["exact_command"] += " --unsafe"

    with pytest.raises(
        live.PublicLiveControllerV3Error,
        match="digest/scope drift",
    ):
        live.validate_canary_admission(drifted, model_role="primary")


def test_public_v3_offline_evaluator_uses_both_public_resolvers() -> None:
    agentdojo = PublicFrozenAgentDojoCaseResolverV2()
    m3 = PublicFrozenM3CaseResolverV3()

    wrapped = live._build_public_offline_evaluator(
        agentdojo=agentdojo,
        m3=m3,
    )

    assert wrapped.delegate.agentdojo.resolver is agentdojo
    assert wrapped.delegate.m3._delegate.resolver is m3
