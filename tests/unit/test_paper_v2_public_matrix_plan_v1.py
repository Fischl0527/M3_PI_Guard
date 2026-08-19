from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_FREEZE,
    EXPECTED_RECORDS,
    PublicMatrixPlanError,
    build_public_execution_plan,
    hydrate_public_work_item,
    reconstruct_public_initial_online_state,
    verify_public_execution_plan,
    write_public_execution_plan,
)


def test_public_plan_has_exact_two_model_coverage() -> None:
    rows, manifest = build_public_execution_plan()

    assert len(rows) == EXPECTED_RECORDS == 6873
    assert manifest["plan"]["records"] == 6873
    assert manifest["counts"]["by_model_role"] == {
        "primary": 5082,
        "second": 1791,
    }
    assert manifest["canary"]["primary_records"] == 24
    assert manifest["canary"]["second_records"] == 12
    assert manifest["execution_authorized"] is False
    assert manifest["result_admission_authorized"] is False
    assert manifest["network_calls_made"] == 0
    assert manifest["formal_results_created"] == 0
    assert len({row["work_key"] for row in rows}) == 6873
    assert {row["model_id"] for row in rows} == {
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    }


def test_public_plan_reconstructs_initial_states_without_evaluator_fields() -> None:
    rows, _ = build_public_execution_plan()
    sample_indices = (0, 1, 2381, 2382, 5081, 5082, 5972, 6872)

    for index in sample_indices:
        row = rows[index]
        state = reconstruct_public_initial_online_state(row)
        assert state
        assert row["source_projection_forbidden_fields_present"] is False
        assert row["initial_online_forbidden_fields_present"] is False
        hydrated, hydrated_state = hydrate_public_work_item(row)
        assert hydrated_state == state
        assert hydrated["initial_online_visible_field_digest"][
            "forbidden_fields_present"
        ] is False


def test_public_plan_writes_and_verifies_deterministically(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.jsonl"
    manifest = tmp_path / "manifest.json"

    written = write_public_execution_plan(
        plan_path=plan,
        manifest_path=manifest,
    )
    verified = verify_public_execution_plan(
        plan_path=plan,
        manifest_path=manifest,
    )

    assert written == verified
    assert len(plan.read_text(encoding="utf-8").splitlines()) == 6873
    assert json.loads(manifest.read_text(encoding="utf-8")) == verified


def test_public_plan_rejects_freeze_record_count_drift(
    tmp_path: Path,
) -> None:
    freeze = json.loads(DEFAULT_FREEZE.read_text(encoding="utf-8"))
    freeze["expected_case_condition_records"] = 6872
    path = tmp_path / "drift.json"
    path.write_text(json.dumps(freeze), encoding="utf-8")

    with pytest.raises(
        PublicMatrixPlanError,
        match="freeze identity drift",
    ):
        build_public_execution_plan(freeze_path=path)
