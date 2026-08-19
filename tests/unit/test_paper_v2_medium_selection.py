from __future__ import annotations

import json
from collections import Counter

from experiments.paper_v2.medium_case_selection import (
    PROJECT_ROOT,
    DEFAULT_INDEX,
    DEFAULT_MANIFEST,
    DEFAULT_SPEC,
    build_selection,
    verify_selection,
)


def _read_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_INDEX.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_medium_selection_is_72_unique_paired_cases() -> None:
    rows, manifest = build_selection(DEFAULT_SPEC)

    assert len(rows) == 72
    assert len({row["case_id"] for row in rows}) == 72
    assert manifest["case_counts"] == {
        "attack": 36,
        "benign_no_tool": 12,
        "benign_tool": 24,
    }
    assert manifest["context_dependent_cases"] >= 24
    assert manifest["sealed_holdout_used"] is False
    assert manifest["outcomes_accessed_for_selection"] is False
    assert manifest["results_status"] == "not_run"


def test_primary_regime_is_non_oracle_and_probe_is_segregated() -> None:
    rows = _read_rows()
    probes = [row["regime_probe"] for row in rows if row["regime_probe"]]

    assert all(row["primary_authorization_regime"] == "auto_compiled" for row in rows)
    assert len(probes) == 24
    assert Counter(probe["authorization_regime"] for probe in probes) == {
        "exact_gold": 6,
        "broad": 6,
        "underspecified": 6,
        "conflicting": 6,
    }
    exact = [probe for probe in probes if probe["authorization_regime"] == "exact_gold"]
    assert all(probe["oracle_ablation"] is True for probe in exact)
    assert all(probe["primary_endpoint_excluded"] is True for probe in probes)


def test_online_projection_digests_exclude_forbidden_fields() -> None:
    rows = _read_rows()

    assert all(
        row["online_visible_field_digest"]["forbidden_fields_present"] is False
        for row in rows
    )
    assert all(
        not row["online_visible_field_digest"]["forbidden_field_paths"]
        for row in rows
    )


def test_frozen_index_and_manifest_reproduce_byte_for_byte() -> None:
    manifest = verify_selection(
        spec_path=DEFAULT_SPEC,
        index_path=DEFAULT_INDEX,
        manifest_path=DEFAULT_MANIFEST,
    )

    assert manifest["case_count"] == 72
    assert len(manifest["index_sha256"]) == 64


def test_live_medium_gate_has_costed_ledger_and_requires_provider_approval() -> None:
    gate = json.loads(
        (
            PROJECT_ROOT
            / "protocols/paper_upgrade_v2/medium_falsification_gate_v2.json"
        ).read_text(encoding="utf-8")
    )

    assert gate["required_inputs"]["case_selection"]["status"] == "pass"
    assert (
        gate["required_inputs"]["structural_baseline"]["status"]
        == "pass_zero_call_adapter_qualification"
    )
    assert (
        gate["required_inputs"]["primary_model"]["status"]
        == "candidate_frozen_runtime_attestation_pending"
    )
    assert (
        gate["required_inputs"]["cost_ceiling"]["status"]
        == "estimated_user_approval_pending"
    )
    assert (
        gate["required_inputs"]["cost_ceiling"]["total_cost_upper_bound_usd"]
        == 119.93484
    )
    assert gate["required_inputs"]["execution_ledger"]["work_items"] == 480
    assert (
        gate["required_inputs"]["execution_ledger"]["execution_authorized"]
        is False
    )
    assert gate["start_authorized"] is False
    assert gate["expected_records"]["total"] == 480
