from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.diagnose_agentdojo_formal_run_failures import (
    _classify_failure,
    build_failure_diagnostic,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_agentdojo_failure_classifier_detects_cpu_oom() -> None:
    row = {
        "error_type": "RuntimeError",
        "error": (
            "[enforce fail at alloc_cpu.cpp:121] data. "
            "DefaultCPUAllocator: not enough memory"
        ),
        "traceback": "transformers.pipeline(tool_output)",
    }

    assert _classify_failure(row) == "resource_cpu_memory"


def test_runtime_filename_does_not_turn_invalid_json_into_timeout() -> None:
    row = {
        "error_type": "TaskShieldVerifierError",
        "error": "verifier returned invalid JSON",
        "traceback": (
            "File 'experiments/paper_v1/benchmarks/taskshield_paper_runtime_v14.py'"
        ),
    }

    assert _classify_failure(row) == "model_output_or_parse"


def test_agentdojo_failure_diagnostic_writes_non_formal_cpu_oom_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    output_dir = tmp_path / "diagnostic"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "status": "running",
            "condition_id": "agentdojo_transformers_pi_detector_official",
            "model_id": "m3-paper-qwen3-8b-v1:latest",
        },
    )
    _write_jsonl(
        run_dir / "outcomes.jsonl",
        [
            {
                "status": "failed",
                "benchmark_case_id": "agentdojo:v1:workspace:user_task_25",
                "case_index": 76,
                "case_kind": "utility",
                "suite": "workspace",
                "error_type": "RuntimeError",
                "error": "DefaultCPUAllocator: not enough memory",
            }
        ],
    )
    (run_dir / "progress.jsonl").write_text("", encoding="utf-8")
    (run_dir / "runner_stderr.log").write_text("Device set to use cpu\n", encoding="utf-8")

    diagnostic = build_failure_diagnostic(run_dir=run_dir, output_dir=output_dir)

    assert diagnostic["status"] == "completed_failure_diagnostic"
    assert diagnostic["result_eligible_for_formal_tables"] is False
    assert diagnostic["counts"]["classification_counts"] == {"resource_cpu_memory": 1}
    assert diagnostic["failures"][0]["classification"] == "resource_cpu_memory"
    assert (output_dir / "failure_diagnostic.json").is_file()
    assert (output_dir / "failure_diagnostic.md").is_file()


def test_agentdojo_failure_diagnostic_blocks_missing_outcomes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    output_dir = tmp_path / "diagnostic"
    _write_json(run_dir / "run_manifest.json", {"status": "running"})

    diagnostic = build_failure_diagnostic(run_dir=run_dir, output_dir=output_dir)

    assert diagnostic["status"] == "blocked_missing_outcomes"
    assert diagnostic["counts"]["failed_rows"] == 0
    assert diagnostic["result_eligible_for_formal_tables"] is False
