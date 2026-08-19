from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.audit_strong_baseline_formal_readiness import (
    _external_requirements,
)


def _by_name(rows: list[dict]) -> dict[str, dict]:
    return {str(row["name"]): row for row in rows}


def test_ifc_gate_requires_only_the_frozen_selected_method(tmp_path: Path) -> None:
    adapter = tmp_path / "camel_formal_manifest.json"
    adapter.write_text(
        json.dumps(
            {
                "status": "completed_formal_analysis",
                "config": {"selected_candidate": "camel"},
                "method_selected": True,
                "source_checkout_ready": True,
            }
        ),
        encoding="utf-8",
    )
    entries = [
        {
            "id": "camel_google_research",
            "registry_key": "camel_or_fides",
            "result_eligible_for_formal_tables": True,
        },
        {
            "id": "fides_microsoft",
            "registry_key": "camel_or_fides",
            "result_eligible_for_formal_tables": False,
        },
    ]
    requirements = _external_requirements(
        "camel_or_fides",
        {
            "formal_manifest": str(adapter),
            "complete_logs": ["run_manifest.json", "outcomes.jsonl"],
        },
        {"camel_or_fides": entries},
        {
            "status": "completed",
            "readiness_by_key": {
                "camel_or_fides": {"snapshot_ready": True, "blockers": []}
            },
            "adapter_preflight_snapshots": {
                "camel_or_fides": {
                    "source_smoke_status": "completed_source_smoke_only",
                    "source_smoke_network_calls": False,
                    "source_smoke_formal_result_eligible": False,
                    "source_smoke_passed_checks": 8,
                    "source_smoke_total_checks": 8,
                }
            },
        },
    )
    indexed = _by_name(requirements)

    assert indexed["external_entries_result_eligible_true"]["passed"] is True
    assert indexed["adapter_is_source_backed_not_stub_only"]["passed"] is True
    assert indexed["exactly_one_ifc_capability_method_selected"]["passed"] is True
    assert indexed["unselected_ifc_methods_not_result_eligible"]["passed"] is True


def test_ifc_gate_rejects_result_eligible_unselected_method(tmp_path: Path) -> None:
    adapter = tmp_path / "camel_formal_manifest.json"
    adapter.write_text(
        json.dumps(
            {
                "status": "completed_formal_analysis",
                "config": {"selected_candidate": "camel"},
                "method_selected": True,
                "source_checkout_ready": True,
            }
        ),
        encoding="utf-8",
    )
    entries = [
        {
            "id": "camel_google_research",
            "registry_key": "camel_or_fides",
            "result_eligible_for_formal_tables": True,
        },
        {
            "id": "fides_microsoft",
            "registry_key": "camel_or_fides",
            "result_eligible_for_formal_tables": True,
        },
    ]
    requirements = _external_requirements(
        "camel_or_fides",
        {
            "formal_manifest": str(adapter),
            "complete_logs": ["run_manifest.json", "outcomes.jsonl"],
        },
        {"camel_or_fides": entries},
        {
            "status": "completed",
            "readiness_by_key": {"camel_or_fides": {"snapshot_ready": True}},
            "adapter_preflight_snapshots": {
                "camel_or_fides": {
                    "source_smoke_status": "completed_source_smoke_only",
                    "source_smoke_network_calls": False,
                    "source_smoke_formal_result_eligible": False,
                }
            },
        },
    )
    indexed = _by_name(requirements)

    assert indexed["exactly_one_ifc_capability_method_selected"]["passed"] is False
    assert indexed["unselected_ifc_methods_not_result_eligible"]["passed"] is False


def test_ifc_selection_remains_bound_to_freeze_after_analysis_admission(tmp_path: Path) -> None:
    analysis = tmp_path / "analysis_manifest.json"
    freeze = tmp_path / "freeze.json"
    analysis.write_text(
        json.dumps({"status": "completed_formal_analysis"}), encoding="utf-8"
    )
    freeze.write_text(
        json.dumps(
            {
                "status": "completed_frozen_formal_protocol",
                "config": {"selected_candidate": "camel"},
                "method_selected": True,
                "source_checkout_ready": True,
            }
        ),
        encoding="utf-8",
    )
    entries = [
        {
            "id": "camel_google_research",
            "registry_key": "camel_or_fides",
            "result_eligible_for_formal_tables": True,
        },
        {
            "id": "fides_microsoft",
            "registry_key": "camel_or_fides",
            "result_eligible_for_formal_tables": False,
        },
    ]
    requirements = _external_requirements(
        "camel_or_fides",
        {
            "formal_manifest": str(analysis),
            "formal_freeze": str(freeze),
            "complete_logs": ["run_manifest.json", "outcomes.jsonl"],
        },
        {"camel_or_fides": entries},
        {
            "status": "completed",
            "readiness_by_key": {"camel_or_fides": {"snapshot_ready": True}},
            "adapter_preflight_snapshots": {
                "camel_or_fides": {
                    "source_smoke_status": "completed_source_smoke_only",
                    "source_smoke_network_calls": False,
                    "source_smoke_formal_result_eligible": False,
                }
            },
        },
    )
    indexed = _by_name(requirements)

    assert indexed["external_entries_result_eligible_true"]["passed"] is True
    assert indexed["adapter_is_source_backed_not_stub_only"]["passed"] is True
    assert indexed["exactly_one_ifc_capability_method_selected"]["passed"] is True
    assert indexed["selected_method_source_checkout_ready"]["passed"] is True
