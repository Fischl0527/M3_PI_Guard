from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v2.formal_condition_executors import OnlineExecutorContext
from experiments.paper_v2.live_condition_runtime import M3SandboxEffectBackend
from experiments.paper_v2.m3_offline_evaluator import (
    DEFAULT_OUTPUT,
    FrozenM3CaseResolver,
    M3OfflineEvaluatorError,
    M3OfflineOutcomeEvaluator,
    build_qualification,
)
from experiments.paper_v2.medium_runtime import (
    DEFAULT_V2_PLAN,
    reconstruct_initial_online_state,
)


def _items() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_V2_PLAN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _m3_items() -> list[dict]:
    return [
        item
        for item in _items()
        if item["benchmark"] == "m3-v2"
        and item["condition_id"] == "no_defense"
        and item["analysis_tier"] == "primary"
    ]


def _context(item: dict) -> OnlineExecutorContext:
    return OnlineExecutorContext(
        execution_identity=item["execution_identity"],
        work_key=item["work_key"],
        benchmark=item["benchmark"],
        condition_id=item["condition_id"],
        max_provider_calls=item["max_provider_calls"],
        online_state=reconstruct_initial_online_state(item),
    )


def test_frozen_m3_offline_evaluator_qualification_reproduces() -> None:
    current = build_qualification()
    frozen = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert current == frozen
    assert current["qualification_probes"][0]["task_completion"] is True
    assert current["qualification_probes"][1]["task_completion"] is False
    assert current["qualification_probes"][2]["unsafe_effect"] is True
    assert current["composite_evaluator"]["benchmarks"] == [
        "agentdojo-v1",
        "m3-v2",
    ]
    assert current["network_calls_made"] == 0
    assert current["formal_results_created"] == 0
    assert current["evaluator_labels_visible_online"] is False


def test_m3_expected_effect_labels_are_absent_from_online_state() -> None:
    item = _m3_items()[0]
    state = reconstruct_initial_online_state(item)
    rendered = json.dumps(state, ensure_ascii=False, sort_keys=True)

    assert "offline_evaluation" not in rendered
    assert "expected_allowed_effects" not in rendered
    assert "expected_unsafe_effects" not in rendered


def test_m3_evaluator_rejects_material_from_another_work_key() -> None:
    first, second = _m3_items()[:2]
    backend = M3SandboxEffectBackend(_context(first))
    try:
        backend.execute("final", {"answer": "qualification"})
        material = backend.evaluator_material()
        with pytest.raises(
            M3OfflineEvaluatorError,
            match="not bound to this frozen work item",
        ):
            M3OfflineOutcomeEvaluator(FrozenM3CaseResolver()).evaluate(
                second, {"offline_evaluator_input": material}
            )
    finally:
        backend.close()


def test_m3_qualification_artifact_contains_no_effect_arguments() -> None:
    rendered = Path(DEFAULT_OUTPUT).read_text(encoding="utf-8")

    assert "redteam-" not in rendered
    assert "/mock/internal/export" not in rendered
    assert "sandbox/public/m3v2_" not in rendered
