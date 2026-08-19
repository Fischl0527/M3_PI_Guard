from __future__ import annotations

import json
import tempfile
from pathlib import Path

from experiments.paper_v1.benchmarks.admit_agentdojo_tool_filter_formal_result import (
    _admitted_registry,
    _validate_evidence,
)
from experiments.paper_v1.benchmarks.common import sha256_file
from experiments.paper_v1.benchmarks.run_agentdojo_official_tool_filter_formal import (
    DEFAULT_FREEZE,
    DEFAULT_OUTPUT,
    _running_manifest,
)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def test_tool_filter_admission_updates_registry_only_after_exact_formal_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        run_dir.mkdir()
        run_manifest = {
            "status": "completed_formal",
            "result_eligible_for_formal_tables": True,
            "exact_frozen_coverage": True,
            "summary": {"expected_cases": 726, "completed_cases": 726, "failed_cases": 0},
        }
        _write_json(run_dir / "run_manifest.json", run_manifest)
        (run_dir / "outcomes.jsonl").write_text('{"status":"completed"}\n', encoding="utf-8")
        (run_dir / "progress.jsonl").write_text('{"status":"completed"}\n', encoding="utf-8")
        analysis_path = run_dir / "analysis" / "analysis_manifest.json"
        analysis = {
            "status": "completed_formal_analysis",
            "result_eligible_for_formal_tables": True,
            "manifest_path": str(analysis_path),
            "run_manifest_sha256": sha256_file(run_dir / "run_manifest.json"),
            "outcomes_sha256": sha256_file(run_dir / "outcomes.jsonl"),
        }
        _write_json(analysis_path, analysis)
        monitor_path = root / "monitor.json"
        _write_json(monitor_path, {"status": "completed"})
        monitor = {
            "health_status": "completed_formal_admitted",
            "formal_result_admitted_now": True,
            "run_manifest_path": str(run_dir / "run_manifest.json"),
            "json_path": str(monitor_path),
            "counts": {"completed_cases": 726, "failed_cases": 0, "missing_cases": 0},
        }

        blockers = _validate_evidence(run_dir=run_dir, monitor=monitor, analysis=analysis)
        admitted = _admitted_registry(
            registry={
                "q2_gate_minimum_strong_baselines": {
                    "formal_ready_strong_baselines": ["promptguard"],
                    "minimum_exact_or_disclosed_exclusion_count": 5,
                },
                "conditions": [
                    {
                        "id": "agentdojo_tool_filter",
                        "implementation_status": "ready_official_tool_filter_qualification_completed_formal_run_pending",
                        "result_eligible": False,
                        "current_blockers": ["pending formal run"],
                    }
                ],
            },
            run_dir=run_dir,
            analysis_manifest=analysis,
            monitor_snapshot_path=monitor_path,
        )

    row = admitted["conditions"][0]
    assert blockers == []
    assert row["implementation_status"] == "ready"
    assert row["result_eligible"] is True
    assert row["current_blockers"] == []
    assert row["formal_manifest"]
    assert len(row["complete_logs"]) == 4
    assert admitted["q2_gate_minimum_strong_baselines"]["formal_ready_count"] == 2
    assert admitted["q2_gate_minimum_strong_baselines"]["current_gate_status"] == "not_satisfied"


def test_tool_filter_admission_blocks_running_or_mismatched_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        run_dir.mkdir()
        _write_json(
            run_dir / "run_manifest.json",
            {
                "status": "running",
                "result_eligible_for_formal_tables": False,
                "summary": {"expected_cases": 726, "completed_cases": 100, "failed_cases": 0},
            },
        )
        (run_dir / "outcomes.jsonl").write_text("", encoding="utf-8")
        (run_dir / "progress.jsonl").write_text("", encoding="utf-8")

        blockers = _validate_evidence(
            run_dir=run_dir,
            monitor={
                "health_status": "running_progressing",
                "formal_result_admitted_now": False,
                "run_manifest_path": str(root / "other" / "run_manifest.json"),
                "counts": {"completed_cases": 100, "failed_cases": 0, "missing_cases": 626},
            },
            analysis={},
        )

    assert "run_not_completed_formal" in blockers
    assert "monitor_not_completed_formal_admitted" in blockers
    assert "monitor_points_to_different_run_manifest" in blockers
    assert "analysis_not_completed_formal" in blockers


def test_tool_filter_runner_manifest_uses_relative_repo_paths() -> None:
    manifest = _running_manifest(
        freeze_path=DEFAULT_FREEZE,
        output_dir=DEFAULT_OUTPUT,
        service={"base_url": "http://127.0.0.1:11434/v1", "model_present": True},
        freeze={"model_id": "m3-paper-qwen3-8b-v1:latest", "condition_id": "agentdojo_tool_filter_official"},
        selected_count=726,
        case_limit=None,
        case_ids=[],
        admit_formal=True,
        resume=True,
        retry_failed=False,
        started_at="2026-07-22T00:00:00+00:00",
        rows=[],
    )

    assert manifest["freeze_path"] == "protocols/paper_upgrade_v1/agentdojo_tool_filter_formal_freeze_v1.json"
    assert manifest["output_dir"] == "outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1"
    assert ":\\" not in manifest["freeze_path"]
    assert ":\\" not in manifest["output_dir"]
