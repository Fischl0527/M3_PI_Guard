from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.e14_performance import (
    DEFAULT_CASES,
    GPU_MEMORY_CHART_FIELDS,
    LATENCY_CHART_FIELDS,
    PERFORMANCE_FIELDS,
    THROUGHPUT_CHART_FIELDS,
    _lane_specs,
    _render_chart,
    _signed_summary,
    build_analysis,
    build_execution_plan,
    build_gpu_chart_data,
    build_performance_metrics,
    load_representative_cases,
    run_e14,
)
from experiments.manifest import validate_completed_manifest
from m3_core.tool_sandbox import SANDBOX_RUNTIME_VERSION
from m3_eval.figure_manifest import load_figure_manifest


MODEL = "qwen3:4b-instruct"


def _arg(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def _configuration_hash(configuration: dict) -> str:
    stable = {key: value for key, value in configuration.items() if key != "config_hash"}
    payload = json.dumps(
        stable,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _lane_result(spec: dict, *, failed: bool = False, timed_out: bool = False) -> dict:
    command = list(spec["command"])
    condition_spec = _arg(command, "--conditions")
    condition = "full_guard" if condition_spec.endswith(":full_guard") else "off"
    model = _arg(command, "--model")
    repeats = int(_arg(command, "--repeats"))
    num_ctx = int(_arg(command, "--num-ctx"))
    rows: list[dict] = []
    for repeat in range(repeats):
        for index, case_id in enumerate(spec["case_ids"]):
            if failed:
                rows.append(
                    {
                        "run_key": f"{case_id}-{condition}-{repeat}",
                        "case_id": case_id,
                        "model": model,
                        "replicate_id": repeat,
                        "seed": 42 + repeat,
                        "condition_id": f"e14_{condition}",
                        "step": 0,
                        "final_status": "error",
                        "guard_decision": "error",
                        "model_config": {"num_ctx": num_ctx},
                        "model_latency_ms": None,
                        "guard_latency_ms": None,
                        "total_latency_ms": None,
                        "case_latency_ms": None,
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "total_tokens": None,
                        "timed_out": timed_out,
                    }
                )
                continue
            guard_ms = 2.0 if condition == "full_guard" else 0.0
            model_ms = 100.0 + index + repeat
            total_ms = model_ms + guard_ms + 1.0
            rows.append(
                {
                    "run_key": f"{case_id}-{condition}-{repeat}",
                    "case_id": case_id,
                    "model": model,
                    "replicate_id": repeat,
                    "seed": 42 + repeat,
                    "condition_id": f"e14_{condition}",
                    "step": 1,
                    "final_status": "completed",
                    "guard_decision": "allow" if condition == "full_guard" else "not_applicable",
                    "model_config": {"num_ctx": num_ctx},
                    "model_latency_ms": model_ms,
                    "guard_latency_ms": guard_ms,
                    "total_latency_ms": total_ms,
                    "case_latency_ms": total_ms,
                    "prompt_tokens": 20,
                    "completion_tokens": 5,
                    "total_tokens": 25,
                    "timed_out": False,
                }
            )
    raw_path = Path(spec["raw_path"])
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    stderr_path = Path(spec["stderr_path"])
    stderr_path.write_text("simulated timeout\n" if failed else "", encoding="utf-8")
    Path(spec["stdout_path"]).write_text("fixture lane\n", encoding="utf-8")
    return {
        "lane_id": spec["lane_id"],
        "case_ids": list(spec["case_ids"]),
        "command": command,
        "exit_code": 1 if failed else 0,
        "timed_out": timed_out,
        "terminated": timed_out,
        "process_alive_checked": True,
        "duration_seconds": 0.01,
        "stdout_path": str(spec["stdout_path"]),
        "stderr_path": str(stderr_path),
        "stderr_tail": ["simulated timeout"] if failed else [],
        "raw_path": str(raw_path),
        "raw_exists": True,
    }


def _success_lane(spec: dict) -> dict:
    return _lane_result(spec)


def _gpu() -> dict:
    return {
        "captured_at": "test",
        "available": True,
        "name": "fixture-gpu",
        "utilization_percent": 50.0,
        "memory_used_mib": 2048.0,
        "memory_free_mib": 6144.0,
        "memory_total_mib": 8192.0,
    }


class E14PerformanceTests(unittest.TestCase):
    def _manifest_patches(self):
        return (
            patch(
                "experiments.manifest.environment_snapshot",
                return_value={"captured_at": "test", "python": "test"},
            ),
            patch(
                "experiments.manifest.git_state",
                return_value={
                    "commit": "e14-test-commit",
                    "branch": "test1",
                    "dirty": True,
                    "status_sha256": "test",
                },
            ),
        )

    def test_default_plan_has_full_grid_warmups_and_counterbalancing(self) -> None:
        cases = load_representative_cases()
        plan = build_execution_plan(cases)
        self.assertEqual(len(cases), 6)
        self.assertEqual(plan["performance_job_count"], 24)
        self.assertEqual(plan["warmup_job_count"], 8)
        self.assertEqual(plan["warmup_conditions"], ["off", "full_guard"])
        self.assertEqual(plan["warmup_case_run_count"], 48)
        self.assertEqual(len(plan["jobs"]), 32)
        warmups = [job for job in plan["jobs"] if job["job_type"] == "warmup"]
        self.assertEqual(
            {(job["num_ctx"], job["condition"]) for job in warmups},
            {
                (context, condition)
                for context in (2048, 4096, 8192, 16384)
                for condition in ("off", "full_guard")
            },
        )
        for job in warmups:
            self.assertEqual(job["case_ids"], [case["case_id"] for case in cases])
            self.assertEqual(job["expected_case_runs"], 6)
            self.assertEqual(job["repeats"], 1)
            self.assertTrue(job["excluded_from_metrics"])
            self.assertTrue(job["id"].endswith(f"__{job['condition']}"))
        performance = [job for job in plan["jobs"] if job["job_type"] == "performance"]
        self.assertEqual([job["condition"] for job in performance[:2]], ["off", "full_guard"])
        self.assertEqual([job["condition"] for job in performance[2:4]], ["full_guard", "off"])
        self.assertEqual({job["num_ctx"] for job in performance}, {2048, 4096, 8192, 16384})
        self.assertEqual({job["concurrency"] for job in performance}, {1, 2, 4})

    def test_lane_specs_split_cases_and_forward_num_ctx_resume_and_timeout(self) -> None:
        cases = load_representative_cases()
        plan = build_execution_plan(
            cases, contexts=[16384], concurrencies=[4], warmup=False
        )
        job = next(item for item in plan["jobs"] if item["condition"] == "full_guard")
        with tempfile.TemporaryDirectory() as temp:
            specs = _lane_specs(
                job,
                output_dir=Path(temp),
                cases_path=DEFAULT_CASES,
                resume=True,
                seed=7,
                temperature=0.0,
                max_tokens=128,
                max_steps=2,
                request_timeout_seconds=33.0,
                lane_timeout_seconds=99.0,
                ask_threshold=0.3,
                deny_threshold=0.7,
            )
        self.assertEqual(len(specs), 4)
        self.assertEqual(sorted(len(spec["case_ids"]) for spec in specs), [1, 1, 2, 2])
        for spec in specs:
            self.assertIn("--resume", spec["command"])
            self.assertEqual(_arg(spec["command"], "--backend"), "ollama")
            self.assertEqual(_arg(spec["command"], "--num-ctx"), "16384")
            self.assertEqual(_arg(spec["command"], "--timeout"), "33.0")
            self.assertEqual(spec["timeout_seconds"], 99.0)

    def test_warmup_lane_commands_use_each_condition_guard_mode_and_full_case_set(
        self,
    ) -> None:
        cases = load_representative_cases()
        case_ids = [case["case_id"] for case in cases]
        plan = build_execution_plan(
            cases, contexts=[2048], concurrencies=[1], warmup=True
        )
        warmups = [job for job in plan["jobs"] if job["job_type"] == "warmup"]
        self.assertEqual([job["condition"] for job in warmups], ["off", "full_guard"])
        with tempfile.TemporaryDirectory() as temp:
            for job in warmups:
                specs = _lane_specs(
                    job,
                    output_dir=Path(temp),
                    cases_path=DEFAULT_CASES,
                    resume=False,
                    seed=7,
                    temperature=0.0,
                    max_tokens=128,
                    max_steps=2,
                    request_timeout_seconds=33.0,
                    lane_timeout_seconds=99.0,
                    ask_threshold=0.3,
                    deny_threshold=0.7,
                )
                self.assertEqual(len(specs), 1)
                self.assertEqual(specs[0]["case_ids"], case_ids)
                expected_guard_mode = {
                    "off": "off",
                    "full_guard": "full_guard",
                }[job["condition"]]
                self.assertEqual(job["prompt_profile"], "normal")
                self.assertEqual(job["guard_mode"], expected_guard_mode)
                expected_condition = (
                    f"e14_warmup_{job['condition']}="
                    f"normal:{expected_guard_mode}"
                )
                self.assertEqual(
                    _arg(specs[0]["command"], "--conditions"), expected_condition
                )
                self.assertEqual(_arg(specs[0]["command"], "--repeats"), "1")
                self.assertIn("excluded from metrics", _arg(specs[0]["command"], "--notes"))

    def test_no_warmup_keeps_performance_plan_and_reports_zero_warmup_work(self) -> None:
        cases = load_representative_cases()
        plan = build_execution_plan(
            cases, contexts=[2048], concurrencies=[1], warmup=False
        )
        self.assertFalse(plan["warmup_enabled"])
        self.assertEqual(plan["warmup_conditions"], [])
        self.assertEqual(plan["warmup_job_count"], 0)
        self.assertEqual(plan["warmup_case_run_count"], 0)
        self.assertEqual(plan["performance_job_count"], 2)
        self.assertEqual(len(plan["jobs"]), 2)
        self.assertTrue(all(job["job_type"] == "performance" for job in plan["jobs"]))

    def test_plan_only_writes_recoverable_manifest_without_model_access(self) -> None:
        def forbidden(*_args, **_kwargs):
            raise AssertionError("plan-only must not inspect or run a model")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with first_patch, second_patch:
                manifest = run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    plan_only=True,
                    inventory_provider=forbidden,
                    lane_executor=forbidden,
                    model_stopper=forbidden,
                )
            self.assertEqual(manifest["status"], "planned")
            self.assertEqual(manifest["progress"]["expected_runs"], 2)
            self.assertTrue((output / "manifest.json").exists())
            self.assertTrue((output / "execution_plan.json").exists())
            self.assertFalse((output / "raw_runs.jsonl").exists())
            self.assertFalse((output / "figure_manifest.json").exists())
            self.assertTrue(all(job["status"] == "pending" for job in manifest["jobs"]))

    def test_gpu_chart_data_preserves_zero_delta_and_independent_na(self) -> None:
        common = {
            "model": MODEL,
            "num_ctx": 2048,
            "concurrency": 1,
            "condition": "off",
            "prompt_profile": "normal",
            "guard_mode": "off",
            "job_status": "completed",
            "gpu_sample_count": 3,
        }
        rows = build_gpu_chart_data(
            [
                {
                    **common,
                    "job_id": "gpu-observed-zero",
                    "gpu_peak_memory_mib": 2048.0,
                    "gpu_memory_delta_mib": 0.0,
                },
                {
                    **common,
                    "job_id": "gpu-partial-telemetry",
                    "gpu_peak_memory_mib": 2050.0,
                    "gpu_memory_delta_mib": None,
                },
            ]
        )
        self.assertEqual(rows[0]["gpu_memory_delta_mib"], 0.0)
        self.assertEqual(rows[0]["delta_status"], "observed")
        self.assertEqual(rows[1]["peak_status"], "observed")
        self.assertEqual(rows[1]["delta_status"], "NA_telemetry_unavailable")

    def test_signed_overhead_summary_preserves_negative_improvements(self) -> None:
        summary = _signed_summary([-20.0, -10.0, 5.0])
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["median"], -10.0)
        self.assertAlmostEqual(summary["p95"], 3.5)

    def test_throughput_chart_uses_numeric_context_order_and_non_color_condition_encoding(
        self,
    ) -> None:
        rows = []
        for context in (16384, 2048, 4096):
            for condition in ("full_guard", "off"):
                rows.append(
                    {
                        "model": MODEL,
                        "num_ctx": context,
                        "concurrency": 1,
                        "condition": condition,
                        "expected_case_runs": 6,
                        "observed_case_runs": 6,
                        "successful_case_runs": 6,
                        "missing_case_runs": 0,
                        "error_case_runs": 0,
                        "timeout_case_runs": 0,
                        "wall_seconds": 12.0,
                        "throughput_case_runs_per_s": 0.5,
                        "value_status": "observed",
                    }
                )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            integrity = _render_chart(
                rows,
                chart="throughput",
                png_path=root / "throughput.png",
                svg_path=root / "throughput.svg",
            )
            self.assertTrue((root / "throughput.png").exists())
            self.assertTrue((root / "throughput.svg").exists())

        self.assertEqual(integrity["color_order"], [2048, 4096, 16384])
        self.assertEqual(integrity["encoding"]["color"], "context tokens in numeric order")
        self.assertEqual(
            integrity["encoding"]["condition_styles"],
            {
                "off": {"linestyle": "--", "marker": "s"},
                "full_guard": {"linestyle": "-", "marker": "o"},
            },
        )
        self.assertEqual(
            integrity["encoding"]["legend_background"],
            "opaque_white_with_border",
        )
        self.assertIn(f"single-model ({MODEL})", integrity["title"])
        self.assertIn("n=6/6", integrity["footer"])
        self.assertIn("job wall-clock seconds", integrity["footer"])
        self.assertIn("no inferential interval", integrity["footer"])

    def test_analysis_labels_2048_c1_guard_target_failure_as_noncausal_cold_start_like(
        self,
    ) -> None:
        def comparison(context: int, guard_p95: float, target: bool) -> dict:
            return {
                "model": MODEL,
                "num_ctx": context,
                "concurrency": 1,
                "paired_case_runs": 6,
                "total_latency_overhead_percent": {"median": -0.35},
                "guard_latency_ms": {"median": 1.4, "p95": guard_p95},
                "total_latency_wilcoxon": {
                    "p_value": 0.5,
                    "holm_adjusted_p": 1.0,
                    "rank_biserial": -0.2,
                },
                "target_checks": {
                    "guard_p95_below_10ms": target,
                    "median_end_to_end_overhead_below_10pct": True,
                },
            }

        analysis = build_analysis(
            {
                "performance_job_count": 2,
                "num_ctx_values": [2048, 4096],
                "concurrency_values": [1],
            },
            [
                {"job_type": "performance", "status": "completed"},
                {"job_type": "performance", "status": "completed"},
            ],
            [],
            {
                "comparisons": [
                    comparison(2048, 40.56, False),
                    comparison(4096, 1.2, True),
                ]
            },
        )
        self.assertIn("Observed cold-start-like anomaly", analysis)
        self.assertIn("2048 tokens / c=1", analysis)
        self.assertIn("未达到 p95<10 ms 目标", analysis)
        self.assertIn("不是纯可加的 Guard overhead", analysis)
        self.assertIn("不能确认冷启动或任何具体机制", analysis)

    def test_analysis_describes_dual_condition_full_representative_warmup(self) -> None:
        cases = load_representative_cases()
        plan = build_execution_plan(
            cases, contexts=[2048], concurrencies=[1], warmup=True
        )
        analysis = build_analysis(
            plan,
            [
                {"job_type": "performance", "status": "completed"},
                {"job_type": "performance", "status": "completed"},
            ],
            [],
            {
                "comparisons": [
                    {
                        "model": MODEL,
                        "num_ctx": 2048,
                        "concurrency": 1,
                        "paired_case_runs": 6,
                        "total_latency_overhead_percent": {"median": 1.0},
                        "guard_latency_ms": {"median": 1.4, "p95": 40.56},
                        "total_latency_wilcoxon": {
                            "p_value": 0.5,
                            "holm_adjusted_p": 1.0,
                            "rank_biserial": 0.2,
                        },
                        "target_checks": {
                            "guard_p95_below_10ms": False,
                            "median_end_to_end_overhead_below_10pct": True,
                        },
                    }
                ]
            },
        )
        self.assertIn("每个 model×num_ctx 分别执行 off/full_guard 两个独立任务", analysis)
        self.assertIn("完整 6 条代表案例", analysis)
        self.assertIn("共 2 jobs / 12 case-runs", analysis)
        self.assertIn("全部标记 excluded_from_metrics", analysis)
        self.assertIn("Observed post-warmup tail anomaly", analysis)
        self.assertIn("不能仅依据执行位置把该尾部归因为冷启动", analysis)
        self.assertNotIn("Observed cold-start-like anomaly", analysis)

    def test_planned_manifest_refreshes_formal_provenance_in_place(self) -> None:
        planning_command = [
            "python",
            "-m",
            "experiments.e14_performance",
            "--plan-only",
        ]
        formal_command = ["python", "-m", "experiments.e14_performance"]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with first_patch, second_patch:
                planned = run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    plan_only=True,
                    command=planning_command,
                )

            lane_calls: list[dict] = []

            def formal_lane(spec: dict) -> dict:
                lane_calls.append(dict(spec))
                self.assertNotIn("--resume", spec["command"])
                return _lane_result(spec)

            formal_git = {
                "commit": "formal-commit",
                "branch": "formal-branch",
                "dirty": False,
                "status_sha256": "formal-status",
            }
            formal_environment = {"captured_at": "formal", "python": "formal"}
            with (
                patch(
                    "experiments.manifest.environment_snapshot",
                    return_value=formal_environment,
                ),
                patch("experiments.manifest.git_state", return_value=formal_git),
            ):
                completed = run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    command=formal_command,
                    lane_executor=formal_lane,
                    gpu_provider=_gpu,
                    inventory_provider=lambda: {MODEL: {}},
                    model_stopper=lambda _model: None,
                )

            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["created_at"], planned["created_at"])
            self.assertNotEqual(completed["updated_at"], planned["updated_at"])
            self.assertEqual(completed["configuration"], planned["configuration"])
            self.assertEqual(completed["command"], formal_command)
            self.assertEqual(completed["git"], formal_git)
            self.assertEqual(completed["environment"], formal_environment)
            self.assertIn("formal_started", [event["type"] for event in completed["events"]])
            self.assertEqual(len(lane_calls), 2)

    def test_configuration_drift_refusal_does_not_mutate_plan_or_manifest(self) -> None:
        def forbidden(*_args, **_kwargs):
            raise AssertionError("configuration drift must fail before model access")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with first_patch, second_patch:
                run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    plan_only=True,
                )
            manifest_path = output / "manifest.json"
            plan_path = output / "execution_plan.json"
            manifest_before = manifest_path.read_bytes()
            plan_before = plan_path.read_bytes()

            with self.assertRaisesRegex(
                RuntimeError, "Refusing E14 resume: configuration hash changed"
            ):
                run_e14(
                    output,
                    contexts=[4096],
                    concurrencies=[1],
                    warmup=False,
                    inventory_provider=forbidden,
                    lane_executor=forbidden,
                    model_stopper=forbidden,
                )

            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            self.assertEqual(plan_path.read_bytes(), plan_before)

    def test_sandbox_runtime_drift_refuses_v1_resume_before_model_access(self) -> None:
        def forbidden(*_args, **_kwargs):
            raise AssertionError("runtime drift must fail before model access")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with (
                first_patch,
                second_patch,
                patch(
                    "experiments.e14_performance.SANDBOX_RUNTIME_VERSION",
                    "isolated-tool-sandbox-v1",
                ),
            ):
                planned = run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    plan_only=True,
                )

            configuration = planned["configuration"]
            self.assertEqual(
                configuration["sandbox_runtime_version"],
                "isolated-tool-sandbox-v1",
            )
            self.assertEqual(planned["sandbox_runtime_version"], "isolated-tool-sandbox-v1")
            self.assertEqual(configuration["config_hash"], _configuration_hash(configuration))
            manifest_path = output / "manifest.json"
            plan_path = output / "execution_plan.json"
            manifest_before = manifest_path.read_bytes()
            plan_before = plan_path.read_bytes()

            self.assertEqual(SANDBOX_RUNTIME_VERSION, "isolated-tool-sandbox-v2")
            with self.assertRaisesRegex(
                RuntimeError,
                "Refusing E14 resume: sandbox_runtime_version changed",
            ):
                run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    inventory_provider=forbidden,
                    lane_executor=forbidden,
                    model_stopper=forbidden,
                )

            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            self.assertEqual(plan_path.read_bytes(), plan_before)

    def test_implementation_drift_refuses_resume_before_model_access(self) -> None:
        def forbidden(*_args, **_kwargs):
            raise AssertionError("implementation drift must fail before model access")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with (
                first_patch,
                second_patch,
                patch(
                    "experiments.e14_performance._e14_implementation_sha256",
                    return_value="1" * 64,
                ),
            ):
                planned = run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    plan_only=True,
                )

            configuration = planned["configuration"]
            self.assertEqual(configuration["implementation_sha256"], "1" * 64)
            self.assertEqual(planned["implementation_sha256"], "1" * 64)
            self.assertEqual(configuration["config_hash"], _configuration_hash(configuration))
            manifest_path = output / "manifest.json"
            plan_path = output / "execution_plan.json"
            manifest_before = manifest_path.read_bytes()
            plan_before = plan_path.read_bytes()

            with (
                patch(
                    "experiments.e14_performance._e14_implementation_sha256",
                    return_value="2" * 64,
                ),
                self.assertRaisesRegex(
                    RuntimeError,
                    "Refusing E14 resume: implementation_sha256 changed",
                ),
            ):
                run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    inventory_provider=forbidden,
                    lane_executor=forbidden,
                    model_stopper=forbidden,
                )

            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            self.assertEqual(plan_path.read_bytes(), plan_before)

    def test_top_level_runtime_provenance_mismatch_refuses_resume(self) -> None:
        def forbidden(*_args, **_kwargs):
            raise AssertionError("provenance mismatch must fail before model access")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with first_patch, second_patch:
                run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    plan_only=True,
                )

            manifest_path = output / "manifest.json"
            plan_path = output / "execution_plan.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["sandbox_runtime_version"] = "tampered-runtime"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            manifest_before = manifest_path.read_bytes()
            plan_before = plan_path.read_bytes()

            with self.assertRaisesRegex(
                RuntimeError,
                "top-level sandbox_runtime_version provenance mismatch",
            ):
                run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    inventory_provider=forbidden,
                    lane_executor=forbidden,
                    model_stopper=forbidden,
                )

            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            self.assertEqual(plan_path.read_bytes(), plan_before)

    def test_successful_fake_run_writes_complete_metrics_statistics_and_figures(self) -> None:
        stopped: list[str] = []
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with first_patch, second_patch:
                manifest = run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1, 2],
                    warmup=False,
                    lane_executor=_success_lane,
                    gpu_provider=_gpu,
                    inventory_provider=lambda: {MODEL: {}},
                    model_stopper=stopped.append,
                )
            self.assertEqual(validate_completed_manifest(manifest), [])
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["progress"]["completed_runs"], 4)
            self.assertEqual(stopped, [MODEL])
            expected = {
                "manifest.json",
                "execution_plan.json",
                "raw_runs.jsonl",
                "gpu_snapshots.jsonl",
                "job_records.jsonl",
                "performance.csv",
                "metrics.csv",
                "metrics.json",
                "statistics.json",
                "analysis.md",
                "latency_by_context_data.csv",
                "latency_by_context.png",
                "latency_by_context.svg",
                "throughput_by_concurrency_data.csv",
                "throughput_by_concurrency.png",
                "throughput_by_concurrency.svg",
                "gpu_memory_by_context_data.csv",
                "gpu_memory_by_context.png",
                "gpu_memory_by_context.svg",
                "figure_manifest.json",
                "work",
            }
            self.assertEqual({path.name for path in output.iterdir()}, expected)
            with (output / "performance.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                metrics = list(csv.DictReader(stream))
            self.assertEqual(len(metrics), 4)
            self.assertEqual(tuple(metrics[0]), PERFORMANCE_FIELDS)
            self.assertTrue(all(row["observed_case_runs"] == "6" for row in metrics))
            self.assertTrue(all(row["successful_case_runs"] == "6" for row in metrics))
            self.assertTrue(all(row["total_tokens_median"] == "25.0" for row in metrics))
            guarded = [row for row in metrics if row["condition"] == "full_guard"]
            self.assertTrue(all(row["guard_latency_p95_ms"] == "2.0" for row in guarded))
            self.assertTrue(all(row["throughput_case_runs_per_s"] for row in metrics))
            with (output / "latency_by_context_data.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                latency_chart_rows = list(csv.DictReader(stream))
            self.assertEqual(tuple(latency_chart_rows[0]), LATENCY_CHART_FIELDS)
            self.assertTrue(
                all(
                    row["expected_case_runs"] == "6"
                    and row["observed_case_runs"] == "6"
                    and row["successful_case_runs"] == "6"
                    and row["total_latency_count"] == "6"
                    for row in latency_chart_rows
                )
            )
            with (output / "throughput_by_concurrency_data.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                throughput_chart_rows = list(csv.DictReader(stream))
            self.assertEqual(tuple(throughput_chart_rows[0]), THROUGHPUT_CHART_FIELDS)
            self.assertTrue(
                all(
                    row["successful_case_runs"] == "6" and row["wall_seconds"]
                    for row in throughput_chart_rows
                )
            )
            statistics = json.loads((output / "statistics.json").read_text(encoding="utf-8"))
            self.assertEqual(statistics["status"], "completed")
            self.assertEqual(len(statistics["comparisons"]), 2)
            for comparison in statistics["comparisons"]:
                test = comparison["total_latency_wilcoxon"]
                self.assertEqual(test["method"], "wilcoxon_signed_rank_exact")
                self.assertIn("holm_adjusted_p", test)
                self.assertEqual(comparison["paired_case_runs"], 6)
                self.assertIsNotNone(test["rank_biserial"])
            latency_integrity = statistics["chart_integrity"]["latency"]
            self.assertEqual(
                latency_integrity["encoding"]["color"], "concurrency in numeric order"
            )
            self.assertEqual(latency_integrity["encoding"]["linestyle"], "condition")
            self.assertEqual(latency_integrity["encoding"]["marker"], "condition")
            self.assertEqual(latency_integrity["x_label"], "Context window (tokens)")
            self.assertIn(f"single-model ({MODEL})", latency_integrity["title"])
            self.assertIn("n=6/6", latency_integrity["footer"])
            self.assertIn("descriptive medians", latency_integrity["footer"])
            self.assertIn("No inferential interval", latency_integrity["footer"])
            throughput_integrity = statistics["chart_integrity"]["throughput"]
            self.assertEqual(
                throughput_integrity["denominator_audit"]["successful_over_expected"],
                ["6/6"],
            )
            self.assertIn("job wall-clock seconds", throughput_integrity["footer"])
            self.assertIn("no inferential interval", throughput_integrity["footer"])
            self.assertTrue(
                (output / "latency_by_context.png").read_bytes().startswith(
                    b"\x89PNG\r\n\x1a\n"
                )
            )
            self.assertIn(
                "<svg",
                (output / "throughput_by_concurrency.svg").read_text(encoding="utf-8"),
            )
            self.assertTrue(
                (output / "gpu_memory_by_context.png").read_bytes().startswith(
                    b"\x89PNG\r\n\x1a\n"
                )
            )
            with (output / "gpu_memory_by_context_data.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                gpu_chart_rows = list(csv.DictReader(stream))
            self.assertEqual(len(gpu_chart_rows), 4)
            self.assertEqual(tuple(gpu_chart_rows[0]), GPU_MEMORY_CHART_FIELDS)
            self.assertTrue(all(row["gpu_peak_memory_mib"] == "2048.0" for row in gpu_chart_rows))
            self.assertTrue(all(row["gpu_memory_delta_mib"] == "0.0" for row in gpu_chart_rows))
            self.assertTrue(all(row["peak_status"] == "observed" for row in gpu_chart_rows))
            self.assertTrue(all(row["delta_status"] == "observed" for row in gpu_chart_rows))
            self.assertEqual(
                statistics["chart_integrity"]["gpu_memory"]["peak_plotted_point_count"],
                4,
            )
            self.assertEqual(
                statistics["chart_integrity"]["gpu_memory"]["delta_plotted_point_count"],
                4,
            )
            gpu_integrity = statistics["chart_integrity"]["gpu_memory"]
            self.assertIsNotNone(gpu_integrity["gpu_sample_count_min"])
            self.assertLessEqual(
                gpu_integrity["gpu_sample_count_min"], gpu_integrity["gpu_sample_count_max"]
            )
            self.assertEqual(gpu_integrity["x_label"], "Context window (tokens)")
            self.assertIn("snapshot n=", gpu_integrity["footer"])
            self.assertIn("transient peaks", gpu_integrity["footer"])
            figure_manifest = load_figure_manifest(output, expected_experiment_id="E14")
            self.assertEqual(figure_manifest["evidence_tier"], "formal_dedicated")
            self.assertEqual(
                [figure["id"] for figure in figure_manifest["figures"]],
                ["latency_by_context", "throughput_by_concurrency", "gpu_vram_peak_delta"],
            )
            gpu_figure = figure_manifest["figures"][2]
            self.assertEqual(gpu_figure["role"], "secondary")
            self.assertEqual(gpu_figure["chart_type"], "two_panel_heatmap")
            self.assertEqual(
                gpu_figure["files"]["data"]["path"],
                "gpu_memory_by_context_data.csv",
            )
            self.assertIn("gpu_memory_delta_mib", gpu_figure["metrics"])
            self.assertTrue(any("device-wide" in warning for warning in gpu_figure["warnings"]))
            analysis = (output / "analysis.md").read_text(encoding="utf-8")
            self.assertIn("Material Passport", analysis)
            self.assertIn("效应量", analysis)
            self.assertIn("NA 不替换成 0", analysis)

    def test_postprocessing_failure_is_persisted_for_safe_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with (
                first_patch,
                second_patch,
                patch(
                    "experiments.e14_performance._build_outputs",
                    side_effect=ValueError("signed aggregation fixture"),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "signed aggregation fixture"):
                    run_e14(
                        output,
                        contexts=[2048],
                        concurrencies=[1],
                        warmup=False,
                        lane_executor=_success_lane,
                        gpu_provider=_gpu,
                        inventory_provider=lambda: {MODEL: {}},
                        model_stopper=lambda _model: None,
                    )

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["failure"]["category"], "postprocessing_failure")
            self.assertEqual(manifest["progress"]["completed_runs"], 2)
            self.assertEqual(manifest["progress"]["failed_jobs"], 1)
            self.assertTrue(all(job["status"] == "completed" for job in manifest["jobs"]))
            self.assertIn(
                "postprocessing_failed",
                [event["type"] for event in manifest["events"]],
            )

    def test_failed_timeout_job_retains_counts_and_na_instead_of_zero(self) -> None:
        def failing_guard_lane(spec: dict) -> dict:
            condition = _arg(spec["command"], "--conditions")
            return _lane_result(
                spec,
                failed=condition.endswith(":full_guard"),
                timed_out=condition.endswith(":full_guard"),
            )

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with first_patch, second_patch:
                manifest = run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    lane_executor=failing_guard_lane,
                    gpu_provider=_gpu,
                    inventory_provider=lambda: {MODEL: {}},
                    model_stopper=lambda _model: None,
                )
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["progress"]["completed_runs"], 1)
            with (output / "performance.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                rows = {row["condition"]: row for row in csv.DictReader(stream)}
            guarded = rows["full_guard"]
            self.assertEqual(guarded["error_case_runs"], "6")
            self.assertEqual(guarded["timeout_case_runs"], "6")
            self.assertEqual(guarded["error_rate"], "1.0")
            self.assertEqual(guarded["total_latency_median_ms"], "")
            self.assertEqual(guarded["throughput_case_runs_per_s"], "")
            statistics = json.loads((output / "statistics.json").read_text(encoding="utf-8"))
            comparison = statistics["comparisons"][0]
            self.assertEqual(comparison["paired_case_runs"], 0)
            self.assertIsNone(comparison["total_latency_wilcoxon"]["p_value"])
            with (output / "latency_by_context_data.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                chart_rows = list(csv.DictReader(stream))
            guard_chart = next(row for row in chart_rows if row["condition"] == "full_guard")
            self.assertEqual(guard_chart["median_total_latency_ms"], "")
            self.assertEqual(guard_chart["value_status"], "NA_missing_or_failed")
            records = [
                json.loads(line)
                for line in (output / "job_records.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            failed_record = next(row for row in records if row["condition"] == "full_guard")
            self.assertTrue(failed_record["timed_out"])
            self.assertEqual(failed_record["lanes"][0]["stderr_tail"], ["simulated timeout"])

    def test_resume_retries_only_failed_job_and_preserves_completed_job(self) -> None:
        first_calls: list[str] = []

        def first_executor(spec: dict) -> dict:
            condition = _arg(spec["command"], "--conditions")
            first_calls.append(condition)
            failed = condition.endswith(":full_guard")
            return _lane_result(spec, failed=failed, timed_out=failed)

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "E14"
            first_patch, second_patch = self._manifest_patches()
            with first_patch, second_patch:
                first = run_e14(
                    output,
                    contexts=[2048],
                    concurrencies=[1],
                    warmup=False,
                    lane_executor=first_executor,
                    gpu_provider=_gpu,
                    inventory_provider=lambda: {MODEL: {}},
                    model_stopper=lambda _model: None,
                )
            self.assertEqual(first["status"], "failed")
            self.assertEqual(len(first_calls), 2)

            resume_calls: list[str] = []

            def resume_executor(spec: dict) -> dict:
                resume_calls.append(_arg(spec["command"], "--conditions"))
                self.assertIn("--resume", spec["command"])
                return _lane_result(spec)

            # Existing manifest already contains the patched environment/git data;
            # resume does not construct a new manifest or touch a model in tests.
            resumed = run_e14(
                output,
                contexts=[2048],
                concurrencies=[1],
                warmup=False,
                resume=True,
                lane_executor=resume_executor,
                gpu_provider=_gpu,
                inventory_provider=lambda: {MODEL: {}},
                model_stopper=lambda _model: None,
            )
            self.assertEqual(resumed["status"], "completed")
            self.assertEqual(resume_calls, ["e14_full_guard=normal:full_guard"])
            entries = {job["condition"]: job for job in resumed["jobs"]}
            self.assertEqual(entries["off"]["attempts"], 1)
            self.assertEqual(entries["full_guard"]["attempts"], 2)

    def test_missing_job_evidence_produces_na_metrics(self) -> None:
        cases = load_representative_cases()
        plan = build_execution_plan(
            cases, contexts=[2048], concurrencies=[1], warmup=False
        )
        rows = build_performance_metrics(plan, [], [])
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["job_status"], "missing")
            self.assertEqual(row["observed_case_runs"], 0)
            self.assertEqual(row["missing_case_runs"], 6)
            self.assertIsNone(row["error_rate"])
            self.assertIsNone(row["total_latency_median_ms"])
            self.assertIsNone(row["throughput_case_runs_per_s"])
            self.assertIsNone(row["gpu_peak_memory_mib"])
        gpu_rows = build_gpu_chart_data(rows)
        self.assertTrue(all(row["peak_status"] == "NA_telemetry_unavailable" for row in gpu_rows))
        self.assertTrue(all(row["delta_status"] == "NA_telemetry_unavailable" for row in gpu_rows))


if __name__ == "__main__":
    unittest.main()
