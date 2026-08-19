from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from experiments.paper_v1.benchmarks import run_progent_source_backed_formal_v14 as runner
from experiments.paper_v1.benchmarks.audit_progent_v14_correctness import audit
from experiments.paper_v1.benchmarks.build_progent_source_backed_formal_freeze import (
    DEFAULT_AGENTDOJO,
    DEFAULT_MODEL_REGISTRY,
    DEFAULT_PROGENT,
    DEFAULT_PUBLIC_FREEZE,
)
from experiments.paper_v1.benchmarks.build_progent_source_backed_formal_freeze_v14 import (
    build_freeze,
)
from experiments.paper_v1.benchmarks.common import rows_sha256
from experiments.paper_v1.benchmarks.progent_policy_contract import (
    PolicySchemaValidationError,
    validate_generated_policy_shape,
)
from experiments.paper_v1.benchmarks.progent_source_backed_runtime_v14 import (
    ProgentV14Trace,
    build_progent_pipeline_v14,
    runtime_contract,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def progent_v14_freeze() -> dict:
    return build_freeze(
        public_freeze_path=DEFAULT_PUBLIC_FREEZE,
        model_registry_path=DEFAULT_MODEL_REGISTRY,
        agentdojo_checkout=DEFAULT_AGENTDOJO,
        progent_checkout=DEFAULT_PROGENT,
        model_id="m3-paper-qwen3-8b-v1:latest",
    )


def test_v14_freeze_hash_binds_staged_selections_and_blocks_p6(
    progent_v14_freeze: dict,
) -> None:
    freeze = progent_v14_freeze

    assert freeze["status"] == "completed_frozen_formal_protocol"
    assert freeze["schema_version"] == "paper-progent-source-backed-freeze-1.4"
    assert freeze["formal_execution_authorized"] is False
    assert freeze["runtime_contract"] == runtime_contract()
    assert freeze["runtime_contract"]["policy_contract_validator_enabled"] is True
    assert "policy_contract" in freeze["local_adapter"]["files"]
    assert freeze["source_freezes"]["v13_failed_p3_review"].endswith(
        "progent_v13_p3_failure_review_v1.md"
    )
    assert freeze["selections"]["p3"]["case_counts"] == {
        "utility": 4,
        "security": 4,
        "total": 8,
    }
    assert freeze["selections"]["p4"]["case_counts"] == {
        "utility": 8,
        "security": 8,
        "total": 16,
    }
    assert freeze["selections"]["p5"]["case_counts"] == {
        "utility": 16,
        "security": 16,
        "total": 32,
    }
    assert freeze["selections"]["formal"]["case_counts"] == {
        "utility": 97,
        "security": 629,
        "total": 726,
    }
    assert rows_sha256(freeze["case_rows"]) == freeze["case_rows_sha256"]
    assert all(not Path(path).is_absolute() for path in freeze["local_adapter"]["files"].values())
    assert freeze["failure_policy"]["security_operational_failure_scored_as_unresolved"] is True
    assert freeze["failure_policy"]["retry_failed_interface"] is False


def test_v14_policy_contract_rejects_missing_tool_name() -> None:
    validated = validate_generated_policy_shape(
        [{"name": "send_email", "args": {"recipient": "alice@example.test"}}],
        available_tool_names={"send_email"},
    )

    assert validated == [{"name": "send_email", "args": {"recipient": "alice@example.test"}}]
    with pytest.raises(PolicySchemaValidationError, match=r"policy\[0\]\.name is missing"):
        validate_generated_policy_shape([{"args": {}}], available_tool_names={"send_email"})


def test_v14_freeze_identity_rejects_formal_without_authorization(
    tmp_path: Path, progent_v14_freeze: dict
) -> None:
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(progent_v14_freeze), encoding="utf-8")

    with pytest.raises(ValueError, match="P6 formal execution requires"):
        runner.validate_freeze_identity(
            freeze=progent_v14_freeze,
            freeze_path=freeze_path,
            selection_name="formal",
        )


def test_v14_failed_root_rejected_before_service_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, progent_v14_freeze: dict
) -> None:
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(progent_v14_freeze), encoding="utf-8")
    run_dir = tmp_path / "failed-root"
    case_dir = run_dir / "case_manifests"
    case_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "freeze_sha256": runner.sha256_file(freeze_path),
                "runner_version": runner.RUNNER_VERSION,
                "model_id": progent_v14_freeze["model_id"],
                "condition_id": runner.CONDITION_ID,
                "selection_name": "p3",
                "selected_cases": 8,
                "selected_case_rows_sha256": progent_v14_freeze["selections"]["p3"][
                    "case_rows_sha256"
                ],
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "0001_failed.json").write_text(
        json.dumps(
            {
                "benchmark_case_id": "agentdojo:v1:banking:user_task_0",
                "status": "failed",
                "operational_status": "timeout",
            }
        ),
        encoding="utf-8",
    )

    def fail_probe(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("service probe must not run for failed roots")

    monkeypatch.setattr(runner, "_ollama_probe", fail_probe)

    with pytest.raises(ValueError, match="failed Progent v1.4 root cannot resume"):
        runner.run(
            freeze_path=freeze_path,
            output_dir=run_dir,
            selection_name="p3",
            resume=True,
        )


def test_v14_parent_watchdog_writes_unresolved_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TimeoutProcess:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            self.killed = False

        def wait(self, timeout=None):  # type: ignore[no-untyped-def]
            if self.killed:
                return -9
            raise subprocess.TimeoutExpired(cmd=["worker"], timeout=timeout)

        def kill(self) -> None:
            self.killed = True

    monkeypatch.setattr(runner.subprocess, "Popen", TimeoutProcess)

    row = runner.run_case_subprocess(
        freeze_path=tmp_path / "freeze.json",
        worker_dir=tmp_path / "worker",
        case_id="agentdojo:v1:banking:user_task_0:injection_task_0",
        watchdog_seconds=0.01,
    )

    assert row["status"] == "failed"
    assert row["operational_status"] == "timeout"
    assert row["attack_outcome"] == "unresolved"
    assert row["trace_sealed"] is True
    assert (ROOT / row["trace_event_path"]).is_file()
    assert (ROOT / row["trace_snapshot_path"]).is_file()


def test_v14_pipeline_deduplicates_reused_agentdojo_llm_object(
    tmp_path: Path, progent_v14_freeze: dict
) -> None:
    trace = ProgentV14Trace(tmp_path / "trace_events.jsonl")

    pipeline = build_progent_pipeline_v14(
        progent_v14_freeze,
        trace_event_path=tmp_path / "trace_events.jsonl",
        case_id="agentdojo:v1:banking:user_task_0",
        suite="banking",
        trace=trace,
    )

    binding = pipeline.m3_progent_agent_client_binding
    assert binding["pipeline_position_count"] == 2
    assert binding["unique_client_object_count"] == 1
    assert binding["duplicate_position_count"] == 1
    assert binding["deduplicated_by_object_identity"] is True
    assert any(row["event"] == "agent_client_binding" for row in trace.events)


def test_v14_g1_correctness_audit_preserves_historical_hash_drift_failure(
    tmp_path: Path, progent_v14_freeze: dict
) -> None:
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(progent_v14_freeze), encoding="utf-8")

    result = audit(freeze_path=freeze_path, g0_path=runner.ROOT / "protocols" / "paper_upgrade_v1" / "execution" / "progent_v12_p0_metric_semantics_v1" / "gate_g0.json", output_dir=tmp_path / "g1")

    assert result["status"] == "completed_fail"
    assert result["failed_checks"] == [
        "protected_historical_hashes_unchanged"
    ]
    assert result["passed_checks"] == result["total_checks"] - 1
    assert result["model_calls"] == 0
    assert result["benchmark_cases_executed"] == 0
    assert result["next_action"] == "fix_progent_v14_correctness"
