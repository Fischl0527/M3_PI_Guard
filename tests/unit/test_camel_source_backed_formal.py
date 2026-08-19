from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v1.benchmarks.analyze_camel_source_backed_formal import analyze
from experiments.paper_v1.benchmarks.formal_run_identity import validate_hash_bound_files
from experiments.paper_v1.benchmarks.run_camel_source_backed_formal import (
    _failure_row,
    RUNNER_VERSION,
    run,
)


ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_formal_freeze_v2.json"
)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_camel_formal_admission_rejects_partial_before_model_probe(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="formal admission cannot be requested for a partial run"):
        run(
            freeze_path=FREEZE_PATH,
            output_dir=tmp_path / "run",
            case_limit=1,
            case_ids=None,
            admit_formal=True,
            resume=True,
            retry_failed=False,
        )


def test_camel_freeze_hash_binds_local_adapter_files() -> None:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    assert freeze["schema_version"] == "paper-camel-source-backed-formal-freeze-1.3"
    assert freeze["passed_checks"] == 17
    assert freeze["total_checks"] == 17
    adapter = freeze["local_adapter"]
    assert adapter["resume_identity_checked_before_model_probe"] is True
    assert "formal_runner" in adapter["files"]
    assert "shared_identity" in adapter["files"]
    assert "protocol" in adapter["files"]
    validate_hash_bound_files(adapter)


def test_camel_resume_identity_rejects_old_root_before_service_probe(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "freeze_sha256": "old-freeze",
            "runner_version": RUNNER_VERSION,
            "model_id": "m3-paper-qwen3-8b-v1:latest",
            "condition_id": "camel_or_fides",
            "selected_cases": 1,
            "selected_case_rows_sha256": "old-selection",
        },
    )

    with pytest.raises(ValueError, match="resume root identity mismatch"):
        run(
            freeze_path=FREEZE_PATH,
            output_dir=run_dir,
            case_limit=1,
            case_ids=None,
            admit_formal=False,
            resume=True,
            retry_failed=False,
        )


def test_camel_failure_row_is_fail_closed_for_security_case() -> None:
    row = _failure_row(
        parsed={
            "case_kind": "security",
            "suite": "workspace",
            "user_task_id": "user_task_0",
            "injection_task_id": "injection_task_0",
        },
        case_id="agentdojo:v1:workspace:user_task_0:injection_task_0",
        index=1,
        exc=RuntimeError("synthetic failure"),
    )
    assert row["status"] == "failed"
    assert row["utility_success"] is False
    assert row["security_success"] is False
    assert row["attack_success"] is True
    assert row["result_eligible_for_formal_tables"] is False


def test_camel_analyzer_keeps_diagnostic_run_out_of_formal_tables(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    trace = run_dir / "official_logs" / "trace.json"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text("{}\n", encoding="utf-8")
    binding = {
        "suite": "workspace",
        "policy_engine_class": "WorkspaceSecurityPolicyEngine",
        "privileged_transport": "agentdojo.OpenAILLM(openai-compatible-local)",
        "quarantined_transport": "pydantic_ai.Agent(openai-compatible-local)",
    }
    rows = [
        {
            "status": "completed",
            "benchmark_case_id": "agentdojo:v1:workspace:user_task_0",
            "case_kind": "utility",
            "suite": "workspace",
            "utility_success": True,
            "security_success": None,
            "attack_success": False,
            "elapsed_ms": 10.0,
            "official_trace_path": str(trace.resolve()),
            "official_trace_sha256": "diagnostic-fixture",
            "camel_transport_binding": binding,
        },
        {
            "status": "completed",
            "benchmark_case_id": "agentdojo:v1:workspace:user_task_0:injection_task_0",
            "case_kind": "security",
            "suite": "workspace",
            "utility_success": True,
            "security_success": True,
            "attack_success": False,
            "elapsed_ms": 20.0,
            "official_trace_path": str(trace.resolve()),
            "official_trace_sha256": "diagnostic-fixture",
            "camel_transport_binding": binding,
        },
    ]
    _write_jsonl(run_dir / "outcomes.jsonl", rows)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "status": "completed_diagnostic_partial",
            "result_eligible_for_formal_tables": False,
            "model_id": "m3-paper-qwen3-8b-v1:latest",
            "summary": {"expected_cases": 2},
            "runtime_binding": {"transport_bindings": {"workspace": binding}},
        },
    )

    manifest = analyze(
        run_dir=run_dir,
        output_dir=run_dir / "analysis",
        allow_diagnostic=True,
    )

    assert manifest["status"] == "completed_diagnostic_analysis"
    assert manifest["result_eligible_for_formal_tables"] is False
    assert manifest["case_count"] == 2
    assert Path(manifest["metrics_path"]).is_file()
    assert Path(manifest["report_path"]).is_file()
