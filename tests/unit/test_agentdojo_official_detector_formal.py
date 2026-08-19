from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from experiments.paper_v1.benchmarks.common import rows_sha256
from experiments.paper_v1.benchmarks.analyze_agentdojo_official_detector_formal import (
    DEFAULT_RUN_DIR,
    build_metrics,
    wilson_interval,
)
from experiments.paper_v1.benchmarks.run_agentdojo_official_detector_formal import (
    DEFAULT_FREEZE as DETECTOR_DEFAULT_FREEZE,
    DEFAULT_OUTPUT as DETECTOR_DEFAULT_OUTPUT,
    _apply_detector_device_policy,
    _install_resource_policy,
    _summary,
    _trace_path,
    parse_agentdojo_case_id,
)
from experiments.paper_v1.benchmarks.run_agentdojo_official_tool_filter_formal import (
    DEFAULT_OUTPUT as TOOL_FILTER_DEFAULT_OUTPUT,
    DEFAULT_FREEZE as TOOL_FILTER_DEFAULT_FREEZE,
    RUNNER_VERSION as TOOL_FILTER_RUNNER_VERSION,
    _bind_openai_compatible_tool_filter_model,
)
from experiments.paper_v1.benchmarks.analyze_agentdojo_official_tool_filter_formal import (
    DEFAULT_RUN_DIR as TOOL_FILTER_ANALYSIS_DEFAULT_RUN_DIR,
    ANALYZER_VERSION as TOOL_FILTER_ANALYZER_VERSION,
)
from experiments.paper_v1.benchmarks.monitor_agentdojo_official_formal_run import (
    _pid_alive,
    build_monitor_snapshot,
)
from experiments.paper_v1.benchmarks.smoke_agentdojo_transformers_pi_detector_long_output_direct import (
    extract_longest_tool_output,
)


ROOT = Path(__file__).resolve().parents[2]
FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_transformers_pi_detector_formal_freeze_v1.json"
)
RESOURCE_FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_transformers_pi_detector_resource_isolated_freeze_v1.json"
)
TOOL_FILTER_FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_tool_filter_formal_freeze_v1.json"
)


class AgentDojoOfficialDetectorFormalTests(unittest.TestCase):
    def test_parse_utility_and_security_case_ids(self) -> None:
        utility = parse_agentdojo_case_id("agentdojo:v1:banking:user_task_0")
        security = parse_agentdojo_case_id(
            "agentdojo:v1:banking:user_task_0:injection_task_0"
        )
        self.assertEqual(utility["case_kind"], "utility")
        self.assertIsNone(utility["injection_task_id"])
        self.assertEqual(security["case_kind"], "security")
        self.assertEqual(security["injection_task_id"], "injection_task_0")

    def test_invalid_case_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_agentdojo_case_id("not-agentdojo:v1:banking:user_task_0")

    def test_detector_cpu_policy_hides_cuda_before_transformers_import(self) -> None:
        old_value = os.environ.get("CUDA_VISIBLE_DEVICES")
        try:
            os.environ["CUDA_VISIBLE_DEVICES"] = "0"
            policy = _apply_detector_device_policy("cpu")
            self.assertEqual(policy["detector_device_policy"], "cpu")
            self.assertEqual(policy["cuda_visible_devices_before"], "0")
            self.assertEqual(policy["cuda_visible_devices_after"], "-1")
            self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], "-1")
        finally:
            if old_value is None:
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)
            else:
                os.environ["CUDA_VISIBLE_DEVICES"] = old_value

    def test_unknown_detector_device_policy_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _apply_detector_device_policy("quantum")

    def test_resource_policy_unloads_before_exact_detector_without_changing_input(self) -> None:
        events = []

        class TransformersBasedPIDetector:
            def detect(self, text):
                events.append(("detect", text))
                return True, 0.1

        class Loop:
            def __init__(self):
                self.elements = [TransformersBasedPIDetector()]

        class Pipeline:
            def __init__(self):
                self.elements = [Loop()]

        def unload(base_url, model_id):
            events.append(("unload", base_url, model_id))
            return {"status": "unloaded_before_detector", "done": True}

        pipeline = Pipeline()
        info = _install_resource_policy(
            pipeline,
            policy="unload_ollama_before_detector",
            base_url="http://127.0.0.1:11434/v1",
            model_id="paper-model",
            unload_fn=unload,
        )
        result = pipeline.elements[0].elements[0].detect("complete unmodified input")
        self.assertEqual(result, (True, 0.1))
        self.assertEqual(events[0][0], "unload")
        self.assertEqual(events[1], ("detect", "complete unmodified input"))
        self.assertEqual(info["ollama_unload_count"], 1)
        self.assertFalse(info["detector_input_changed"])

    def test_unknown_resource_policy_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _install_resource_policy(
                object(),
                policy="truncate_silently",
                base_url="http://127.0.0.1:11434/v1",
                model_id="paper-model",
            )

    def test_analyzer_default_points_to_resource_isolated_detector_root(self) -> None:
        self.assertIn(
            "agentdojo_transformers_pi_detector_official_resource_isolated_formal_v1",
            str(DEFAULT_RUN_DIR),
        )
        self.assertEqual(DEFAULT_RUN_DIR, DETECTOR_DEFAULT_OUTPUT)

    def test_runner_default_uses_resource_isolated_freeze(self) -> None:
        self.assertEqual(DETECTOR_DEFAULT_FREEZE, RESOURCE_FREEZE)
        self.assertIn(
            "agentdojo_transformers_pi_detector_official_resource_isolated_formal_v1",
            str(DETECTOR_DEFAULT_OUTPUT),
        )

    def test_frozen_universe_is_complete_and_hash_stable(self) -> None:
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        rows = freeze["case_rows"]
        self.assertEqual(freeze["status"], "completed_frozen_formal_protocol")
        self.assertEqual(freeze["case_counts"], {"security": 629, "total": 726, "utility": 97})
        self.assertEqual(len(rows), 726)
        self.assertEqual(len({row["benchmark_case_id"] for row in rows}), 726)
        self.assertEqual(rows_sha256(rows), freeze["case_rows_sha256"])

    def test_resource_isolated_freeze_preserves_case_universe_and_detector_semantics(self) -> None:
        freeze = json.loads(RESOURCE_FREEZE.read_text(encoding="utf-8"))
        rows = freeze["case_rows"]
        self.assertEqual(freeze["status"], "completed_frozen_formal_protocol")
        self.assertEqual(
            freeze["condition_id"],
            "agentdojo_transformers_pi_detector_official_resource_isolated",
        )
        self.assertEqual(freeze["case_counts"], {"security": 629, "total": 726, "utility": 97})
        self.assertEqual(len(rows), 726)
        self.assertEqual(len({row["benchmark_case_id"] for row in rows}), 726)
        self.assertEqual(rows_sha256(rows), freeze["case_rows_sha256"])
        self.assertEqual(
            freeze["runtime"]["resource_policy"],
            "unload_ollama_before_detector",
        )
        self.assertFalse(freeze["runtime"]["resource_policy_changes_detector_input"])
        self.assertFalse(
            freeze["runtime"]["resource_policy_changes_detector_model_or_threshold"]
        )
        check_names = {row["name"] for row in freeze["checks"]}
        self.assertIn("resource_policy_preserves_detector_semantics", check_names)

    def test_long_output_direct_smoke_extracts_longest_tool_text_without_copying_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "suite_name": "workspace",
                        "pipeline_name": "openai-compatible-transformers_pi_detector",
                        "user_task_id": "user_task_25",
                        "messages": [
                            {"role": "tool", "content": [{"type": "text", "content": "short"}]},
                            {
                                "role": "tool",
                                "tool_call": {"function": "list_files"},
                                "content": [{"type": "text", "content": "x" * 25}],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            extracted = extract_longest_tool_output(trace_path, minimum_chars=20)

        self.assertEqual(extracted["tool_block_count"], 2)
        self.assertEqual(extracted["selected"]["function"], "list_files")
        self.assertEqual(extracted["selected"]["char_count"], 25)
        self.assertEqual(extracted["selected"]["text"], "x" * 25)

    def test_tool_filter_freeze_records_official_transport_without_formal_results(self) -> None:
        freeze = json.loads(TOOL_FILTER_FREEZE.read_text(encoding="utf-8"))
        rows = freeze["case_rows"]
        self.assertEqual(freeze["status"], "completed_frozen_formal_protocol")
        self.assertFalse(freeze["result_eligible_for_formal_tables"])
        self.assertEqual(freeze["case_counts"], {"security": 629, "total": 726, "utility": 97})
        self.assertEqual(len(rows), 726)
        self.assertEqual(rows_sha256(rows), freeze["case_rows_sha256"])
        self.assertEqual(
            freeze["agentdojo"]["official_pipeline_config"]["llm"],
            "OPENAI_COMPATIBLE",
        )
        self.assertEqual(freeze["transport"]["provider"], "openai-compatible")
        self.assertTrue(freeze["agentdojo"]["official_markers"]["official_filter_component"])
        self.assertTrue(freeze["agentdojo"]["official_markers"]["openai_compatible_provider"])
        self.assertTrue(freeze["tool_filter"]["prompt_sha256"])

    def test_tool_filter_runner_defaults_use_frozen_official_condition(self) -> None:
        self.assertEqual(TOOL_FILTER_DEFAULT_FREEZE, TOOL_FILTER_FREEZE)
        self.assertIn("agentdojo_tool_filter_official_formal_v1", str(TOOL_FILTER_DEFAULT_OUTPUT))
        self.assertIn("tool-filter-runner", TOOL_FILTER_RUNNER_VERSION)

    def test_tool_filter_local_provider_binding_rewrites_only_filter_model(self) -> None:
        class OpenAILLMToolFilter:
            def __init__(self):
                self.model = "openai-compatible"
                self.prompt = "official prompt"

        class OpenAILLM:
            def __init__(self):
                self.model = "m3-paper-qwen3-8b-v1:latest"

        class Pipeline:
            def __init__(self):
                self.elements = [OpenAILLMToolFilter(), OpenAILLM()]

        pipeline = Pipeline()
        binding = _bind_openai_compatible_tool_filter_model(
            pipeline,
            "m3-paper-qwen3-8b-v1:latest",
        )

        self.assertEqual(pipeline.elements[0].model, "m3-paper-qwen3-8b-v1:latest")
        self.assertEqual(pipeline.elements[1].model, "m3-paper-qwen3-8b-v1:latest")
        self.assertEqual(binding["rebound_elements"][0]["model_before"], "openai-compatible")
        self.assertFalse(binding["algorithm_changed"])
        self.assertFalse(binding["prompt_changed"])
        self.assertFalse(binding["selection_rule_changed"])

    def test_tool_filter_analyzer_defaults_use_tool_filter_formal_dir(self) -> None:
        self.assertEqual(TOOL_FILTER_ANALYSIS_DEFAULT_RUN_DIR, TOOL_FILTER_DEFAULT_OUTPUT)
        self.assertIn("tool-filter-analysis", TOOL_FILTER_ANALYZER_VERSION)

    def test_trace_path_matches_official_logger_layout(self) -> None:
        parsed = parse_agentdojo_case_id(
            "agentdojo:v1:banking:user_task_0:injection_task_0"
        )
        path = _trace_path(
            Path("logs"),
            "openai-compatible-transformers_pi_detector",
            parsed,
        )
        self.assertEqual(
            path.as_posix(),
            "logs/openai-compatible-transformers_pi_detector/banking/"
            "user_task_0/direct/injection_task_0.json",
        )

    def test_failed_security_case_remains_in_denominator(self) -> None:
        rows = [
            {
                "status": "failed",
                "case_kind": "security",
                "utility_success": False,
                "attack_success": True,
            },
            {
                "status": "completed",
                "case_kind": "utility",
                "utility_success": True,
                "attack_success": False,
            },
        ]
        summary = _summary(rows, 2)
        self.assertEqual(summary["failed_cases"], 1)
        self.assertEqual(summary["attack_successes"], 1)
        self.assertEqual(summary["utility_successes"], 1)
        self.assertEqual(summary["missing_cases"], 0)

    def test_analysis_metrics_preserve_failures_and_wilson_counts(self) -> None:
        rows = [
            {
                "status": "completed",
                "case_kind": "utility",
                "suite": "banking",
                "utility_success": True,
                "attack_success": False,
                "detector_redaction_marker_count": 0,
                "elapsed_ms": 10.0,
            },
            {
                "status": "failed",
                "case_kind": "security",
                "suite": "banking",
                "utility_success": False,
                "attack_success": True,
            },
        ]
        metrics, summary = build_metrics(rows)
        overall_asr = next(
            row
            for row in metrics
            if row["suite"] == "overall" and row["metric"] == "ASR"
        )
        self.assertEqual(overall_asr["successes"], 1)
        self.assertEqual(overall_asr["total"], 1)
        self.assertEqual(overall_asr["rate"], 1.0)
        self.assertEqual(summary["failure_count"], 1)
        self.assertEqual(summary["latency_ms"]["n"], 1)

    def test_wilson_interval_is_bounded(self) -> None:
        low, high = wilson_interval(5, 10)
        self.assertGreater(low, 0.0)
        self.assertLess(high, 1.0)
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)

    def test_formal_run_monitor_counts_outcomes_not_results_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "status": "running",
                        "started_at": "2026-07-21T00:00:00+00:00",
                        "updated_at": "2026-07-21T00:10:00+00:00",
                        "condition_id": "agentdojo_transformers_pi_detector",
                        "model_id": "m3-paper-qwen3-8b-v1:latest",
                        "pid": -1,
                        "summary": {"expected_cases": 3},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "progress.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "index": 1,
                                "selected_cases": 3,
                                "status": "running",
                                "created_at": "2026-07-21T00:01:00+00:00",
                            }
                        ),
                        json.dumps(
                            {
                                "index": 1,
                                "selected_cases": 3,
                                "status": "completed",
                                "created_at": "2026-07-21T00:02:00+00:00",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "outcomes.jsonl").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "case_kind": "utility",
                        "created_at": "2026-07-21T00:02:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            snapshot = build_monitor_snapshot(
                run_dir=run_dir,
                output_dir=root / "protocols",
                stall_minutes=45,
                write_files=False,
                now=datetime(2026, 7, 21, 0, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(snapshot["health_status"], "running_progressing")
        self.assertEqual(snapshot["counts"]["expected_cases"], 3)
        self.assertEqual(snapshot["counts"]["observed_outcomes"], 1)
        self.assertEqual(snapshot["counts"]["completed_cases"], 1)
        self.assertEqual(snapshot["counts"]["missing_cases"], 2)
        self.assertEqual(
            snapshot["counts"]["progress_status_counts"],
            {"completed": 1, "running": 1},
        )

    def test_formal_run_monitor_distinguishes_live_and_exited_processes(self) -> None:
        self.assertTrue(_pid_alive(os.getpid()))
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=10)
        self.assertFalse(_pid_alive(child.pid))

    def test_formal_run_monitor_creates_nested_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "status": "running",
                        "started_at": "2026-07-21T00:00:00+00:00",
                        "updated_at": "2026-07-21T00:01:00+00:00",
                        "condition_id": "agentdojo_tool_filter",
                        "model_id": "m3-paper-qwen3-8b-v1:latest",
                        "pid": -1,
                        "summary": {"expected_cases": 1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "progress.jsonl").write_text(
                json.dumps(
                    {
                        "index": 1,
                        "selected_cases": 1,
                        "status": "running",
                        "created_at": "2026-07-21T00:01:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            output_dir = root / "nested" / "monitor"

            snapshot = build_monitor_snapshot(
                run_dir=run_dir,
                output_dir=output_dir,
                write_files=True,
                now=datetime(2026, 7, 21, 0, 2, tzinfo=timezone.utc),
            )

            self.assertTrue((output_dir / "agentdojo_official_formal_run_monitor_v1.json").exists())
            self.assertTrue((output_dir / "agentdojo_official_formal_run_monitor_v1.md").exists())
            self.assertEqual(snapshot["status"], "completed")

    def test_formal_run_monitor_admits_only_exact_failure_free_completed_formal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "status": "completed_formal",
                        "started_at": "2026-07-21T00:00:00+00:00",
                        "completed_at": "2026-07-21T00:10:00+00:00",
                        "result_eligible_for_formal_tables": True,
                        "condition_id": "agentdojo_tool_filter",
                        "model_id": "m3-paper-qwen3-8b-v1:latest",
                        "summary": {"expected_cases": 2},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "outcomes.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"status": "completed", "case_kind": "utility"}),
                        json.dumps({"status": "completed", "case_kind": "security"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            snapshot = build_monitor_snapshot(
                run_dir=run_dir,
                output_dir=root / "protocols",
                write_files=False,
                now=datetime(2026, 7, 21, 0, 12, tzinfo=timezone.utc),
            )

        self.assertEqual(snapshot["health_status"], "completed_formal_admitted")
        self.assertTrue(snapshot["formal_result_admitted_now"])
        self.assertEqual(snapshot["counts"]["missing_cases"], 0)

    def test_formal_run_monitor_failure_blocks_formal_table_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "status": "running",
                        "started_at": "2026-07-21T00:00:00+00:00",
                        "updated_at": "2026-07-21T00:02:00+00:00",
                        "summary": {"expected_cases": 2},
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "outcomes.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"status": "completed", "case_kind": "utility"}),
                        json.dumps({"status": "failed", "case_kind": "security"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            snapshot = build_monitor_snapshot(
                run_dir=run_dir,
                output_dir=root / "protocols",
                write_files=False,
                now=datetime(2026, 7, 21, 0, 3, tzinfo=timezone.utc),
            )

        self.assertEqual(snapshot["health_status"], "running_with_failures_requires_attention")
        self.assertFalse(snapshot["formal_result_admitted_now"])
        self.assertIn("failed_cases_present", snapshot["health_blockers"])

    def test_formal_run_monitor_displays_repo_paths_relatively(self) -> None:
        from experiments.paper_v1.benchmarks.common import portable_path

        root = Path("E:/portable") / ("M3_PI_" + "Guard_test")
        self.assertEqual(
            portable_path(root / "outputs" / "run", root=root),
            "outputs/run",
        )


if __name__ == "__main__":
    unittest.main()
