from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.analyze_camel_source_backed_formal_v3 import (
    analyze,
    build_metrics,
)
from experiments.paper_v1.benchmarks.formal_run_identity import validate_hash_bound_files
from experiments.paper_v1.benchmarks.run_camel_source_backed_formal_v3 import (
    STDIO_BINDING,
    _canonicalize_outcome,
    _failure_row,
)


ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_formal_freeze_v3.json"
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


def test_camel_v3_stdio_declares_utf8_guard() -> None:
    assert STDIO_BINDING["PYTHONIOENCODING"] == "utf-8"
    assert "stdout" in STDIO_BINDING["streams_reconfigured"]


def test_camel_v3_freeze_hash_binds_v3_adapter_files() -> None:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))

    assert freeze["schema_version"] == "paper-camel-source-backed-formal-freeze-1.4"
    assert freeze["metric_semantics_version"] == "agentdojo_official_v2"
    assert freeze["v3_corrections"]["utf8_stdio_reconfigure_before_upstream_camel_prints"] is True
    adapter = freeze["local_adapter"]
    assert adapter["files"]["formal_runner"].endswith("run_camel_source_backed_formal_v3.py")
    assert adapter["files"]["formal_analyzer"].endswith("analyze_camel_source_backed_formal_v3.py")
    validate_hash_bound_files(adapter)


def test_camel_v3_failure_row_is_unresolved_not_attack_success() -> None:
    row = _failure_row(
        parsed={
            "case_kind": "security",
            "suite": "banking",
            "user_task_id": "user_task_0",
            "injection_task_id": "injection_task_0",
        },
        case_id="agentdojo:v1:banking:user_task_0:injection_task_0",
        index=1,
        exc=UnicodeEncodeError("gbk", "✅", 0, 1, "synthetic"),
    )

    assert row["status"] == "failed"
    assert row["operational_status"] == "runtime_failure"
    assert row["attack_outcome"] == "unresolved"
    assert row["attack_success"] is None
    assert row["official_injection_goal_achieved"] is None


def test_camel_v3_completed_security_uses_agentdojo_official_semantics() -> None:
    parsed = {
        "case_kind": "security",
        "suite": "banking",
        "user_task_id": "user_task_0",
        "injection_task_id": "injection_task_0",
    }
    outcome = _canonicalize_outcome(
        parsed=parsed,
        outcome={
            "utility_success": True,
            "security_success": True,
            "attack_success": False,
            "elapsed_ms": 12.0,
            "official_trace_path": str(ROOT / "trace.json"),
        },
    )

    assert outcome["metric_semantics_version"] == "agentdojo_official_v2"
    assert outcome["official_injection_goal_achieved"] is True
    assert outcome["attack_outcome"] == "success"
    assert outcome["attack_success"] is True
    assert outcome["legacy_attack_success"] is False


def test_camel_v3_metrics_keep_unresolved_attack_separate() -> None:
    rows = [
        {"case_kind": "security", "suite": "banking", "attack_outcome": "success"},
        {"case_kind": "security", "suite": "banking", "attack_outcome": "failure"},
        {"case_kind": "security", "suite": "banking", "attack_outcome": "unresolved"},
    ]

    metrics, summary = build_metrics(rows)
    asr = next(row for row in metrics if row["suite"] == "overall" and row["metric"] == "ASR")
    unresolved = next(
        row for row in metrics if row["suite"] == "overall" and row["metric"] == "unresolved_attack_rate"
    )

    assert asr["successes"] == 1
    assert asr["total"] == 2
    assert unresolved["successes"] == 1
    assert unresolved["total"] == 3
    assert summary["unresolved_security_case_count"] == 1


def test_camel_v3_analyzer_accepts_relative_project_trace_paths(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    trace = run_dir / "official_logs" / "trace.json"
    relative_trace = trace.resolve().relative_to(ROOT).as_posix() if trace.resolve().is_relative_to(ROOT) else str(trace)
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text("{}\n", encoding="utf-8")
    binding = {
        "suite": "banking",
        "policy_engine_class": "BankingSecurityPolicyEngine",
        "privileged_transport": "agentdojo.OpenAILLM(openai-compatible-local)",
        "quarantined_transport": "pydantic_ai.Agent(openai-compatible-local)",
    }
    rows = [
        {
            "status": "completed",
            "benchmark_case_id": "agentdojo:v1:banking:user_task_0",
            "case_kind": "utility",
            "suite": "banking",
            "utility_success": True,
            "attack_outcome": None,
            "elapsed_ms": 10.0,
            "official_trace_path": relative_trace,
            "official_trace_sha256": "fixture",
            "camel_transport_binding": binding,
        }
    ]
    _write_jsonl(run_dir / "outcomes.jsonl", rows)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "status": "completed_diagnostic_partial",
            "result_eligible_for_formal_tables": False,
            "model_id": "m3-paper-qwen3-8b-v1:latest",
            "summary": {"expected_cases": 1},
            "runtime_binding": {"transport_bindings": {"banking": binding}},
        },
    )

    manifest = analyze(run_dir=run_dir, output_dir=run_dir / "analysis", allow_diagnostic=True)

    assert manifest["status"] == "completed_diagnostic_analysis"
    assert manifest["result_eligible_for_formal_tables"] is False
    assert (run_dir / "analysis" / "metrics.csv").is_file()
