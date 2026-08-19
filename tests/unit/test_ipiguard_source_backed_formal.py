from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

from experiments.paper_v1.benchmarks.audit_ipiguard_source_backed_import import audit
from experiments.paper_v1.benchmarks.analyze_ipiguard_source_backed_formal import analyze
from experiments.paper_v1.benchmarks.build_ipiguard_source_backed_formal_freeze import (
    DEFAULT_CHECKOUT,
    DEFAULT_MODEL_REGISTRY,
    DEFAULT_PUBLIC_FREEZE,
    build_freeze,
)
from experiments.paper_v1.benchmarks.common import rows_sha256
from experiments.paper_v1.benchmarks.run_ipiguard_source_backed_formal import (
    _dag_snapshot,
    _persist_construct_capture,
    _pipeline_name,
    _validate_local_adapter_freeze,
    _validate_resume_identity,
    run,
)


ROOT = Path(__file__).resolve().parents[2]


def _built_freeze() -> dict:
    return build_freeze(
        public_freeze_path=DEFAULT_PUBLIC_FREEZE,
        model_registry_path=DEFAULT_MODEL_REGISTRY,
        checkout=DEFAULT_CHECKOUT,
        model_id="m3-paper-qwen3-8b-v1:latest",
    )


def test_ipiguard_source_freeze_covers_public_agentdojo_universe() -> None:
    freeze = _built_freeze()

    assert freeze["status"] == "completed_frozen_formal_protocol"
    assert freeze["case_counts"] == {"utility": 97, "security": 629, "total": 726}
    assert len({row["benchmark_case_id"] for row in freeze["case_rows"]}) == 726
    assert rows_sha256(freeze["case_rows"]) == freeze["case_rows_sha256"]
    assert freeze["ipiguard"]["adapter_classification"].startswith("source_backed")
    assert freeze["optional_provider_import_isolation"]["algorithm_change"] is False
    assert freeze["local_adapter"]["raw_construct_output_capture"] is True
    assert all(freeze["local_adapter"]["sha256"].values())
    assert freeze["failed_checks"] == []


def test_ipiguard_pipeline_name_is_windows_path_safe() -> None:
    value = _pipeline_name("m3-paper-qwen3-8b-v1:latest")

    assert ":" not in value
    assert "/" not in value
    assert "\\" not in value
    assert value.endswith("-ipiguard-source-backed")


def test_ipiguard_dag_snapshot_retains_nodes_edges_and_arguments() -> None:
    class Call:
        function = "search"
        args = {"query": "paper"}

    dag = nx.DiGraph()
    dag.add_node("1", function_call=Call(), depends_on=[])
    dag.add_node("2", function_call=Call(), depends_on=["1"])
    dag.add_edge("1", "2")

    snapshot = _dag_snapshot(dag)

    assert snapshot["present"] is True
    assert len(snapshot["nodes"]) == 2
    assert snapshot["edges"] == [["1", "2"]]
    assert snapshot["nodes"][0]["args"] == {"query": "paper"}


def test_ipiguard_construct_capture_retains_malformed_schema_evidence(tmp_path: Path) -> None:
    class Pipeline:
        @staticmethod
        def construct_capture() -> str:
            return '{"tool_calls":[{"id":"1","name":"search","args":{}}]}'

    evidence = _persist_construct_capture(
        pipeline=Pipeline(),
        capture_root=tmp_path / "raw",
        case_manifest_path=tmp_path / "case_0001.json",
    )

    assert evidence["construct_output_present"] is True
    assert evidence["construct_output_json_valid"] is True
    assert evidence["construct_output_tool_call_count"] == 1
    assert evidence["construct_output_tool_call_key_sets"] == [["args", "id", "name"]]
    assert Path(evidence["construct_output_path"]).read_text(encoding="utf-8").startswith("{")


def test_ipiguard_local_adapter_freeze_fails_closed_on_hash_drift(tmp_path: Path) -> None:
    adapter = tmp_path / "runner.py"
    adapter.write_text("before", encoding="utf-8")
    freeze = {
        "local_adapter": {
            "files": {"runner": str(adapter)},
            "sha256": {"runner": "0" * 64},
        }
    }

    with pytest.raises(ValueError, match="local adapter freeze hash mismatch: runner"):
        _validate_local_adapter_freeze(freeze)


def test_ipiguard_resume_rejects_old_freeze_before_model_probe(tmp_path: Path) -> None:
    freeze_path = tmp_path / "freeze.json"
    freeze = {"model_id": "model-v2"}
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
    output_dir = tmp_path / "old-run"
    output_dir.mkdir()
    (output_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "freeze_sha256": "old",
                "runner_version": "runner-v1",
                "model_id": "model-v1",
                "condition_id": "ipiguard_source_backed",
                "selected_cases": 1,
                "case_rows_sha256": rows_sha256(
                    [{"benchmark_case_id": "case-1", "case_kind": "utility"}]
                ),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="resume root identity mismatch"):
        _validate_resume_identity(
            output_dir=output_dir,
            freeze_path=freeze_path,
            freeze=freeze,
            selected=[{"benchmark_case_id": "case-1", "case_kind": "utility"}],
        )


def test_ipiguard_formal_admission_rejects_partial_before_service_probe(tmp_path: Path) -> None:
    freeze = _built_freeze()
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")

    with pytest.raises(ValueError, match="formal admission cannot be requested for a partial run"):
        run(
            freeze_path=freeze_path,
            output_dir=tmp_path / "run",
            case_limit=1,
            case_ids=None,
            admit_formal=True,
            resume=True,
            retry_failed=False,
        )


def test_ipiguard_analyzer_rejects_unadmitted_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "status": "completed_diagnostic_partial",
                "result_eligible_for_formal_tables": False,
                "summary": {"expected_cases": 1},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "outcomes.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="not formally admitted"):
        analyze(run_dir=run_dir, output_dir=tmp_path / "analysis", allow_diagnostic=False)


def test_ipiguard_import_preflight_builds_without_network_or_cases(tmp_path: Path) -> None:
    result = audit(
        freeze_path=ROOT
        / "protocols"
        / "paper_upgrade_v1"
        / "ipiguard_source_backed_formal_freeze_v1.json",
        output_dir=tmp_path,
    )

    assert result["status"] == "completed_import_preflight_only"
    assert result["passed_checks"] == result["total_checks"]
    assert result["network_calls_performed"] is False
    assert result["ollama_probe_performed"] is False
    assert result["benchmark_cases_executed"] == 0
    assert result["result_eligible_for_formal_tables"] is False
