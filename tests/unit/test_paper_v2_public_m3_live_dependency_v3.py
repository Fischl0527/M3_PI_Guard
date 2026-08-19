from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v2.m3_offline_evaluator import (
    FrozenM3CaseResolver,
    M3OfflineEvaluatorError,
)
from experiments.paper_v2.public_m3_live_dependency_v3 import (
    PublicFrozenM3CaseResolverV3,
    build_public_m3_resolver_qualification,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_PLAN,
    reconstruct_public_initial_online_state,
)


def _rows() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_PLAN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _public_m3_item(
    *,
    role: str = "primary",
    category: str = "attack",
) -> dict:
    return next(
        row
        for row in _rows()
        if row["model_role"] == role
        and row["benchmark"] == "m3-v2"
        and (
            row["evaluation_case_type"] == "attack"
        )
        is (category == "attack")
    )


def test_public_m3_qualification_is_offline_and_complete() -> None:
    value = build_public_m3_resolver_qualification()

    assert value["status"] == "public_plan_m3_bindings_qualified_offline"
    assert value["plan_records"] == 6873
    assert value["qualification_probe_count"] == 4
    assert {
        (probe["model_role"], probe["category"])
        for probe in value["qualification_probes"]
    } == {
        ("primary", "attack"),
        ("primary", "benign"),
        ("second", "attack"),
        ("second", "benign"),
    }
    assert value["network_calls_made"] == 0
    assert value["provider_calls_made"] == 0
    assert value["formal_results_created"] == 0
    assert value["online_state_mutated"] is False


def test_public_m3_key_resolves_but_medium_resolver_rejects_it() -> None:
    item = _public_m3_item()
    binding = PublicFrozenM3CaseResolverV3().resolve(
        item["work_key"]
    )

    assert binding.case_id == item["case_id"]
    assert binding.source_record_sha256 == item["source_record_sha256"]
    with pytest.raises(
        M3OfflineEvaluatorError,
        match="unknown paper-v2 work key",
    ):
        FrozenM3CaseResolver().resolve(item["work_key"])


def test_public_m3_private_labels_are_absent_from_online_state() -> None:
    item = _public_m3_item()
    state = reconstruct_public_initial_online_state(item)
    binding = PublicFrozenM3CaseResolverV3().resolve(
        item["work_key"]
    )
    rendered = json.dumps(state, ensure_ascii=False, sort_keys=True)

    assert binding.offline_evaluation["offline_only"] is True
    assert "offline_evaluation" not in rendered
    assert "expected_unsafe_effects" not in rendered
    assert "expected_allowed_effects" not in rendered


def test_public_m3_source_reference_drift_fails_closed(
    tmp_path: Path,
) -> None:
    rows = _rows()
    target = next(
        row for row in rows if row["benchmark"] == "m3-v2"
    )
    target["source_reference"]["sha256"] = "0" * 64
    path = tmp_path / "drifted-plan.jsonl"
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        M3OfflineEvaluatorError,
        match="source reference drift",
    ):
        PublicFrozenM3CaseResolverV3(plan_path=path)
