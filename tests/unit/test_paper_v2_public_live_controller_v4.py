from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any

import pytest

import experiments.paper_v2.public_live_controller_v4 as live
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import (
    PublicFrozenAgentDojoCaseResolverV2,
)
from experiments.paper_v2.public_m3_live_dependency_v4 import (
    PublicFrozenM3CaseResolverV4,
)
from experiments.paper_v2.public_matrix_controller_v4 import (
    DEFAULT_CANDIDATE,
)


def _candidate() -> dict[str, Any]:
    value = json.loads(DEFAULT_CANDIDATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_public_v4_canary_admission_binds_exact_primary_command(
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
        approved_at="2026-07-29T02:10:00+08:00",
    )

    assert value["scope"]["model_role"] == "primary"
    assert value["scope"]["model_id"] == "deepseek-v4-pro"
    assert value["scope"]["canary_records"] == 24
    assert value["scope"]["exact_command"] == (
        live.canonical_canary_command("primary")
    )
    assert "public_live_controller_v4" in value["scope"]["exact_command"]
    assert "deepseek_public_primary_canary_admission_v4.json" in value[
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


def test_public_v4_canary_admission_rejects_command_drift(
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
        approved_at="2026-07-29T02:10:00+08:00",
    )
    drifted = copy.deepcopy(value)
    drifted["scope"]["exact_command"] += " --unsafe"

    with pytest.raises(
        live.PublicLiveControllerV4Error,
        match="digest/scope drift",
    ):
        live.validate_canary_admission(drifted, model_role="primary")


def test_public_v4_offline_evaluator_uses_identity_aware_resolver() -> None:
    agentdojo = PublicFrozenAgentDojoCaseResolverV2()
    identity = "b" * 64
    m3 = PublicFrozenM3CaseResolverV4(execution_identity=identity)

    wrapped = live._build_public_offline_evaluator(
        agentdojo=agentdojo,
        m3=m3,
    )

    assert wrapped.delegate.agentdojo.resolver is agentdojo
    assert wrapped.delegate.m3._delegate.resolver is m3
    first_key = next(
        key
        for key, item in m3._items.items()
        if item.get("benchmark") == "m3-v2"
    )
    assert m3.resolve(first_key).execution_identity == identity


def test_public_v4_dispatcher_injects_permit_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class Resolver:
        def __init__(self, *, execution_identity: str) -> None:
            captured["identity"] = execution_identity

    monkeypatch.setattr(live, "PublicFrozenM3CaseResolverV4", Resolver)
    monkeypatch.setattr(
        live,
        "_build_public_offline_evaluator",
        lambda **kwargs: captured.setdefault("evaluator_args", kwargs),
    )
    monkeypatch.setattr(
        live,
        "PinnedPromptGuardDetector",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        live,
        "LiveConditionRuntime",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        live,
        "TrustedContextBoundaryRuntimeV3",
        lambda runtime, **kwargs: runtime,
    )
    monkeypatch.setattr(
        live.medium_v2,
        "FailureTierNormalizingRuntime",
        lambda runtime: runtime,
    )
    monkeypatch.setattr(
        live,
        "build_condition_dispatcher",
        lambda **kwargs: kwargs,
    )
    identity = "c" * 64
    permit = SimpleNamespace(
        execution_identity=identity,
        model_role="primary",
        max_tokens=1,
        timeout_seconds=1.0,
        trace_root=SimpleNamespace(),
    )

    result = live._build_dispatcher(
        permit,
        object(),
        api_key="not-used",
        role_policy={},
    )

    assert captured["identity"] == identity
    assert captured["evaluator_args"]["m3"].__class__ is Resolver
    assert "evaluator" in result
