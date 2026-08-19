from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.seal_taskshield_v14_failed_root import (
    RECOVERY_PATH,
    build_failed_root_seal,
)


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_v14_failed_root_seal_hashes_without_editing_source(tmp_path: Path) -> None:
    run_dir = tmp_path / "outputs" / "taskshield_paper_formal_v14"
    manifest = _write(
        run_dir / "run_manifest.json",
        {
            "runner_version": "runner-1.4",
            "model_id": "model-a",
            "freeze_sha256": "freeze-sha",
            "selected_case_rows_sha256": "rows-sha",
        },
    )
    outcomes = run_dir / "outcomes.jsonl"
    outcomes.write_text('{"status":"failed"}\n', encoding="utf-8")
    before = {path: path.read_bytes() for path in (manifest, outcomes)}
    monitor = _write(
        tmp_path / "monitor.json",
        {
            "pid": 9804,
            "pid_alive": False,
            "run_dir": str(run_dir.resolve()),
            "formal_result_admitted_now": False,
            "counts": {
                "completed_cases": 24,
                "failed_cases": 2,
                "missing_cases": 700,
                "expected_cases": 726,
            },
        },
    )
    diagnostic = _write(tmp_path / "diagnostic.json", {"counts": {"failed_rows": 2}})
    decision = _write(
        tmp_path / "decision.json",
        {
            "decision_status": "approved",
            "chosen_recovery_path": RECOVERY_PATH,
            "acknowledgements": {"preserve": True, "fresh_root": True},
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
    assert seal["counts"]["failed_cases"] == 2
    assert seal["failed_checks"] == []
    assert all(path.read_bytes() == content for path, content in before.items())
    assert (tmp_path / "seal" / "taskshield_v14_failed_root_seal_v1.json").is_file()


def test_v14_failed_root_seal_blocks_live_pid(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write(run_dir / "run_manifest.json", {})
    monitor = _write(
        tmp_path / "monitor.json",
        {
            "pid": 9804,
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
            "chosen_recovery_path": RECOVERY_PATH,
            "acknowledgements": {"preserve": True},
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
