from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v2.source_audit import (
    PROJECT_ROOT,
    run,
    verify_evidence_manifest,
)


SPEC_PATH = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/online_state_audit_specs_v1.json"
)
EVIDENCE_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2/audits"
REGISTRY_V2 = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/online_state_audit_registry_v2.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_audit_spec_covers_all_registered_units_and_multiple_artifacts() -> None:
    spec = _load_json(SPEC_PATH)
    units = spec["audit_units"]

    assert len(units) == 22
    assert len({unit["audit_id"] for unit in units}) == 22
    assert len({unit["artifact"] for unit in units}) >= 10
    assert all(len(unit["expected_commit"]) == 40 for unit in units)
    assert all(
        unit["projection"]["online_fields"]
        or unit.get("missing_component_check")
        or (
            not unit["online_boundaries"]
            and unit["conclusion"] == "not_a_runtime_guard"
        )
        for unit in units
    )
    assert all(unit["projection"]["offline_fields"] for unit in units)


def test_audit_conclusions_preserve_scope_and_uncertainty() -> None:
    spec = _load_json(SPEC_PATH)
    by_id = {unit["audit_id"]: unit for unit in spec["audit_units"]}

    assert by_id["A02-siren-loader"]["conclusion"] == "inconclusive"
    assert by_id["A09-camel-runtime"]["conclusion"] == "mixed_or_path_dependent"
    assert by_id["A21-promptguard-detector"]["conclusion"] == "not_a_runtime_guard"
    assert by_id["A19-wasp-benchmark"]["conclusion"] == "not_a_runtime_guard"
    assert by_id["A22-task-shield-runtime"]["conclusion"] == "inconclusive"
    assert by_id["A22-task-shield-runtime"]["official_source_available"] is False
    assert (
        by_id["A22-task-shield-runtime"]["source_provenance"]
        == "disclosed_local_reproduction"
    )
    assert (
        by_id["A01-vigil-runtime"]["authorization_source"]
        == "auto_compiled_non_gold"
    )
    assert spec["review_policy"]["independent_second_reviewer"] is None
    assert spec["review_policy"]["domain_claim_allowed"] is False


def test_generated_evidence_is_hash_complete_and_not_claim_ready() -> None:
    summary = _load_json(EVIDENCE_ROOT / "summary.json")
    assert summary["status"] == "pass"
    assert summary["audit_units"] == 22
    assert summary["distinct_artifacts"] == 16
    assert summary["official_source_code_units"] == 20
    assert summary["disclosed_reproduction_units"] == 1
    assert summary["official_source_unavailable_units"] == 2
    assert summary["claim_ready"] == 0
    assert summary["domain_oracle_problem_claim_allowed"] is False

    manifests = sorted(EVIDENCE_ROOT.glob("*/evidence_manifest.json"))
    assert len(manifests) == 22
    for path in manifests:
        verify_evidence_manifest(path)
        manifest = _load_json(path)
        assert manifest["review_status"] == "single_reviewer_complete"
        assert manifest["claim_ready"] is False
        assert len(manifest["files"]) == 8


def test_verify_only_rechecks_all_frozen_sources_and_evidence() -> None:
    summary = run(
        spec_path=SPEC_PATH,
        output_root=EVIDENCE_ROOT,
        verify_only=True,
    )

    assert summary["status"] == "pass"
    assert summary["audit_units"] == 22
    assert summary["claim_ready"] == 0


def test_registry_v2_reports_completion_without_unlocking_domain_claim() -> None:
    registry = _load_json(REGISTRY_V2)
    completed = [
        target
        for target in registry["targets"]
        if target["audit_status"] == "completed"
    ]

    assert registry["summary"]["audit_units_registered"] == 22
    assert registry["summary"]["completed"] == 22
    assert registry["summary"]["distinct_artifacts_completed"] == 16
    assert registry["summary"]["official_source_code_units"] == 20
    assert registry["summary"]["disclosed_reproduction_units"] == 1
    assert registry["summary"]["official_source_unavailable_units"] == 2
    assert registry["summary"]["independent_second_reviews"] == 0
    assert len(completed) == 22
    assert all(target["claim_ready"] is False for target in completed)
    assert registry["claim_policy"]["minimum_coverage_reached"] is True
    assert (
        registry["claim_policy"]["domain_oracle_problem_claim_allowed"] is False
    )
