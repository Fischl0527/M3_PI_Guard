from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.m3_offline_evaluator import (
    M3OfflineEvaluatorError,
    M3OfflineOutcomeEvaluator,
    _load_jsonl,
)
from experiments.paper_v2.public_m3_live_dependency_v3 import (
    DEFAULT_PLAN,
    PublicFrozenM3CaseResolverV3,
)
from experiments.paper_v2.public_m3_live_dependency_v4 import (
    PublicFrozenM3CaseResolverV4,
    build_public_m3_resolver_qualification,
)


def _first_m3_item() -> dict[str, object]:
    return copy.deepcopy(
        next(
            row
            for row in _load_jsonl(DEFAULT_PLAN)
            if row.get("benchmark") == "m3-v2"
        )
    )


def _raw_trace(item: dict[str, object], identity: str) -> dict[str, object]:
    return {
        "offline_evaluator_input": {
            "backend_id": "m3_sandbox_fixture",
            "work_key_sha256": sha256_canonical_json(
                {
                    "execution_identity": identity,
                    "work_key": item["work_key"],
                }
            ),
            "tool_events": [],
        }
    }


def test_v3_reproduces_public_execution_identity_mismatch() -> None:
    item = _first_m3_item()
    identity = "a" * 64
    item["execution_identity"] = identity

    with pytest.raises(
        M3OfflineEvaluatorError,
        match="not bound to this frozen work item",
    ):
        M3OfflineOutcomeEvaluator(
            PublicFrozenM3CaseResolverV3()
        ).evaluate(item, _raw_trace(item, identity))


def test_v4_evaluator_binds_active_execution_identity() -> None:
    item = _first_m3_item()
    identity = "b" * 64
    item["execution_identity"] = identity
    resolver = PublicFrozenM3CaseResolverV4(
        execution_identity=identity
    )

    outcome = M3OfflineOutcomeEvaluator(resolver).evaluate(
        item,
        _raw_trace(item, identity),
    )

    assert resolver.resolve(str(item["work_key"])).execution_identity == (
        identity
    )
    assert outcome["unsafe_effect"] is False


def test_v4_rejects_malformed_execution_identity() -> None:
    with pytest.raises(
        M3OfflineEvaluatorError,
        match="lowercase SHA-256",
    ):
        PublicFrozenM3CaseResolverV4(execution_identity="not-a-digest")


def test_v4_qualification_executes_four_real_evaluator_probes() -> None:
    value = build_public_m3_resolver_qualification()

    assert value["qualification_probe_count"] == 4
    assert value["public_m3_work_items"] == 3600
    assert value["private_selection_bindings"] == 750
    assert all(
        probe["binding_digest_matches_material"]
        and probe["evaluator_completed"]
        for probe in value["qualification_probes"]
    )
    assert value["network_calls_made"] == 0
