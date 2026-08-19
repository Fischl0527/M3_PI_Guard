from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from experiments.paper_v1.benchmarks.monitor_adaptive_mcts_budget_formal import (
    build_monitor_snapshot,
)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_monitor_reports_missing_manifest(tmp_path: Path) -> None:
    snapshot = build_monitor_snapshot(
        run_dir=tmp_path / "missing",
        output_dir=tmp_path / "monitor",
    )

    assert snapshot["health_status"] == "missing_manifest"
    assert snapshot["pid_alive"] is False
    assert snapshot["result_eligible_for_formal_tables"] is False


def test_monitor_reports_live_progress_and_query_consistency(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    now = datetime.now(timezone.utc)
    _write_json(
        run_dir / "manifest.json",
        {
            "status": "running",
            "pid": os.getpid(),
            "frozen_task_count": 80,
            "selected_task_count": 2,
            "completed_task_count": 1,
            "unresolved_failure_count": 0,
            "queries_executed": 2,
            "updated_at": now.isoformat(),
        },
    )
    _write_json(
        run_dir / "execution_config.json",
        {"selected_case_ids": ["task-a", "task-b"]},
    )
    _write_jsonl(
        run_dir / "task_results.jsonl",
        [{"task_id": "task-a", "queries_executed": 2}],
    )
    _write_json(run_dir / "tasks" / "task-a" / "queries" / "00001.json", {})
    _write_json(run_dir / "tasks" / "task-a" / "queries" / "00002.json", {})

    snapshot = build_monitor_snapshot(
        run_dir=run_dir,
        output_dir=tmp_path / "monitor",
        now=now,
    )

    assert snapshot["health_status"] == "running_progressing"
    assert snapshot["pid_alive"] is True
    assert snapshot["counts"]["completed_tasks"] == 1
    assert snapshot["counts"]["missing_tasks"] == 1
    assert snapshot["counts"]["query_count_matches_manifest"] is True


def test_monitor_keeps_completed_formal_status_read_only(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "manifest.json",
        {
            "status": "completed_formal",
            "pid": 99999999,
            "result_eligible_for_formal_tables": True,
            "frozen_task_count": 80,
            "selected_task_count": 80,
            "queries_executed": 0,
        },
    )

    snapshot = build_monitor_snapshot(
        run_dir=run_dir,
        output_dir=tmp_path / "monitor",
    )

    assert snapshot["health_status"] == "completed_formal_admitted"
    assert snapshot["result_eligible_for_formal_tables"] is True
    assert snapshot["pid_alive"] is False
