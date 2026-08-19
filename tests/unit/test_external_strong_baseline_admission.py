from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.admit_external_strong_baseline_formal_result import (
    admit,
)
from experiments.paper_v1.benchmarks.common import sha256_file


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _registries(tmp_path: Path, condition_id: str, freeze: Path) -> tuple[Path, Path]:
    baseline_path = tmp_path / "baseline_registry.json"
    external_path = tmp_path / "external_registry.json"
    _write_json(
        baseline_path,
        {
            "conditions": [
                {
                    "id": condition_id,
                    "implementation_status": "qualification_pending",
                    "result_eligible": False,
                    "current_blockers": ["formal run pending"],
                    "formal_freeze": str(freeze),
                }
            ],
            "q2_gate_minimum_strong_baselines": {
                "formal_ready_strong_baselines": ["promptguard"],
                "formal_ready_count": 1,
                "minimum_exact_or_disclosed_exclusion_count": 5,
            },
        },
    )
    entries = [
        {
            "id": "camel_google_research",
            "registry_key": "camel_or_fides",
            "result_eligible_for_formal_tables": False,
            "current_blockers": ["pending"],
        },
        {
            "id": "fides_microsoft",
            "registry_key": "camel_or_fides",
            "result_eligible_for_formal_tables": False,
            "current_blockers": ["not selected"],
        },
    ]
    if condition_id != "camel_or_fides":
        selected = {
            "task_shield": "task_shield_acl2025",
            "ipiguard": "ipiguard_github_emnlp2025",
            "progent": "progent_arxiv2025",
        }[condition_id]
        entries = [
            {
                "id": selected,
                "registry_key": condition_id,
                "result_eligible_for_formal_tables": False,
                "current_blockers": ["pending"],
            }
        ]
    _write_json(external_path, {"entries": entries})
    return baseline_path, external_path


def _formal_evidence(tmp_path: Path) -> tuple[Path, Path]:
    freeze = tmp_path / "freeze.json"
    _write_json(freeze, {"status": "completed_frozen_formal_protocol"})
    run_dir = tmp_path / "run"
    outcomes = run_dir / "outcomes.jsonl"
    progress = run_dir / "progress.jsonl"
    rows = [
        {
            "status": "completed",
            "benchmark_case_id": f"case-{index:04d}",
            "result_eligible_for_formal_tables": True,
        }
        for index in range(726)
    ]
    _write_jsonl(outcomes, rows)
    _write_jsonl(progress, [{"status": "completed", "index": index} for index in range(726)])
    run_manifest = run_dir / "run_manifest.json"
    _write_json(
        run_manifest,
        {
            "status": "completed_formal",
            "result_eligible_for_formal_tables": True,
            "exact_frozen_coverage": True,
            "freeze_sha256": sha256_file(freeze),
            "summary": {
                "expected_cases": 726,
                "completed_cases": 726,
                "failed_cases": 0,
            },
        },
    )
    analysis_dir = run_dir / "analysis"
    metrics = analysis_dir / "metrics.csv"
    summary = analysis_dir / "summary.json"
    report = analysis_dir / "analysis.md"
    metrics.parent.mkdir(parents=True, exist_ok=True)
    metrics.write_text("metric,value\nasr,0\n", encoding="utf-8")
    _write_json(summary, {"case_count": 726})
    report.write_text("# Formal analysis\n", encoding="utf-8")
    analysis_manifest = analysis_dir / "analysis_manifest.json"
    _write_json(
        analysis_manifest,
        {
            "status": "completed_formal_analysis",
            "result_eligible_for_formal_tables": True,
            "run_manifest_sha256": sha256_file(run_manifest),
            "outcomes_sha256": sha256_file(outcomes),
            "case_count": 726,
            "metrics_path": str(metrics),
            "metrics_sha256": sha256_file(metrics),
            "summary_path": str(summary),
            "summary_sha256": sha256_file(summary),
            "report_path": str(report),
            "report_sha256": sha256_file(report),
            "figures": {"overall": {"path": "figure.png"}},
        },
    )
    return freeze, run_dir


def test_admission_refuses_missing_formal_evidence_without_registry_changes(tmp_path: Path) -> None:
    freeze = tmp_path / "freeze.json"
    _write_json(freeze, {"status": "completed_frozen_formal_protocol"})
    baseline, external = _registries(tmp_path, "progent", freeze)
    before_baseline = baseline.read_bytes()
    before_external = external.read_bytes()

    result = admit(
        condition_id="progent",
        run_dir=tmp_path / "missing_run",
        baseline_registry_path=baseline,
        external_registry_path=external,
        output_dir=tmp_path / "admission",
        write_registries=True,
    )

    assert result["status"] == "blocked_not_formally_admitted"
    assert result["registries_written"] is False
    assert baseline.read_bytes() == before_baseline
    assert external.read_bytes() == before_external


def test_camel_admission_updates_only_selected_external_method(tmp_path: Path) -> None:
    freeze, run_dir = _formal_evidence(tmp_path)
    baseline, external = _registries(tmp_path, "camel_or_fides", freeze)

    result = admit(
        condition_id="camel_or_fides",
        run_dir=run_dir,
        baseline_registry_path=baseline,
        external_registry_path=external,
        output_dir=tmp_path / "admission",
        write_registries=True,
    )

    assert result["status"] == "admitted_formal_result"
    assert result["registries_written"] is True
    baseline_data = json.loads(baseline.read_text(encoding="utf-8"))
    condition = baseline_data["conditions"][0]
    assert condition["implementation_status"] == "ready"
    assert condition["result_eligible"] is True
    external_data = json.loads(external.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in external_data["entries"]}
    assert by_id["camel_google_research"]["result_eligible_for_formal_tables"] is True
    assert by_id["fides_microsoft"]["result_eligible_for_formal_tables"] is False
