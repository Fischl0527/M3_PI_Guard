from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.seal_taskshield_v13_failed_root import (
    build_failed_root_seal,
)


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_failed_root_seal_hashes_root_without_editing_it(tmp_path: Path) -> None:
    run_dir = tmp_path / "outputs" / "taskshield_paper_formal_v13"
    run_manifest = _write(
        run_dir / "run_manifest.json",
        {
            "runner_version": "runner-1.3",
            "model_id": "model-a",
            "freeze_sha256": "freeze-sha",
            "selected_case_rows_sha256": "rows-sha",
        },
    )
    outcome = run_dir / "outcomes.jsonl"
    outcome.write_text('{"status":"failed"}\n', encoding="utf-8")
    before = {path: path.read_bytes() for path in (run_manifest, outcome)}
    monitor = _write(
        tmp_path / "monitor.json",
        {
            "pid": 123,
            "pid_alive": False,
            "run_dir": str(run_dir.resolve()),
            "formal_result_admitted_now": False,
            "counts": {
                "completed_cases": 2,
                "failed_cases": 1,
                "missing_cases": 3,
                "expected_cases": 6,
            },
        },
    )
    diagnostic = _write(tmp_path / "diagnostic.json", {"counts": {"failed_rows": 1}})
    decision = _write(
        tmp_path / "decision.json",
        {
            "decision_status": "approved",
            "chosen_recovery_path": "preserve_v1_3_failed_root_start_fresh_v14",
        },
    )

    seal = build_failed_root_seal(
        run_dir=run_dir,
        monitor_path=monitor,
        diagnostic_path=diagnostic,
        decision_path=decision,
        output_dir=tmp_path / "seal",
    )

    assert seal["status"] == "sealed_failed_formal_root"
    assert seal["result_eligible_for_formal_tables"] is False
    assert seal["file_count"] == 2
    assert seal["failed_checks"] == []
    assert all(path.read_bytes() == content for path, content in before.items())
    assert (tmp_path / "seal" / "taskshield_v13_failed_root_seal_v1.json").is_file()


def test_failed_root_seal_blocks_a_live_pid(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write(run_dir / "run_manifest.json", {})
    monitor = _write(
        tmp_path / "monitor.json",
        {
            "pid": 123,
            "pid_alive": True,
            "run_dir": str(run_dir.resolve()),
            "formal_result_admitted_now": False,
            "counts": {"failed_cases": 1},
        },
    )
    diagnostic = _write(tmp_path / "diagnostic.json", {"counts": {"failed_rows": 1}})
    decision = _write(
        tmp_path / "decision.json",
        {
            "decision_status": "approved",
            "chosen_recovery_path": "preserve_v1_3_failed_root_start_fresh_v14",
        },
    )

    seal = build_failed_root_seal(
        run_dir=run_dir,
        monitor_path=monitor,
        diagnostic_path=diagnostic,
        decision_path=decision,
        output_dir=tmp_path / "seal",
    )

    assert seal["status"] == "blocked_not_sealed"
    assert "monitor_pid_is_not_alive" in seal["failed_checks"]
