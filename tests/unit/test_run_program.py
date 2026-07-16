from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from experiments.catalog import (
    ALL_MODELS,
    CORE_MODELS,
    MAIN_SEEDS,
    STABILITY_SEEDS,
    STABILITY_TEMPERATURES,
)
from experiments.run_program import (
    ProgramError,
    ProgramGateError,
    QWEN_MODEL,
    STAGES,
    build_stage_plan,
    core_condition_specs,
    matrix_command,
    run_stage,
)
from experiments.manifest import sha256_file
from m3_guard.config import ALL_MODULES, MODE_MODULES


def _condition_ids(config: dict[str, Any]) -> list[str]:
    return [
        item.partition("=")[0]
        for item in str(config["conditions"]).split(",")
        if item
    ]


def _write_freeze(path: Path, marker: str = "v1") -> bytes:
    payload = f'{{"schema_version":"2.0","marker":"{marker}"}}\n'.encode()
    path.write_bytes(payload)
    return payload


def _write_thresholds(path: Path) -> bytes:
    payload = (
        b'{"experiment_id":"E13","scope":"validation_only",'
        b'"status":"targets_met","ask_threshold":1.0,"deny_threshold":1.0}\n'
    )
    path.write_bytes(payload)
    return payload


def _success_runner(plans: Iterable[Any], calls: list[dict[str, Any]]):
    jobs = {
        job.job_id: job
        for plan in plans
        for job in plan.jobs
    }

    def run(config: dict[str, Any]) -> dict[str, Any]:
        calls.append(dict(config))
        job = jobs[config["run_prefix"]]
        condition_ids = _condition_ids(config)
        per_condition = job.expected_run_count // len(condition_ids)
        return {
            "manifest_path": f"mock/{job.job_id}/manifest.json",
            "manifest": {"status": "completed"},
            "results": [
                {
                    "condition_id": condition_id,
                    "status": "completed",
                    "selected_run_count": per_condition,
                    "completed_run_count": per_condition,
                    "error_count": 0,
                }
                for condition_id in condition_ids
            ],
        }

    return run


class RunProgramPlanTests(unittest.TestCase):
    def test_exact_stage_scales(self) -> None:
        plans = {stage: build_stage_plan(stage) for stage in STAGES}
        expected = {
            "stub": (1, 11, 3300),
            "smoke": (5, 10, 60),
            "validation-baseline": (1, 1, 60),
            "ablation": (25, 25, 1500),
            "main": (12, 72, 6480),
            "derived": (6, 12, 282),
            "stability": (120, 120, 3600),
        }
        self.assertEqual(
            {
                stage: (len(plan.jobs), plan.condition_count, plan.expected_run_count)
                for stage, plan in plans.items()
            },
            expected,
        )
        self.assertEqual(sum(plan.expected_run_count for plan in plans.values()), 15282)

        self.assertEqual(plans["stub"].jobs[0].evidence_tier, "regression_only")
        self.assertTrue(plans["main"].freeze_required)
        self.assertTrue(plans["derived"].freeze_required)
        self.assertTrue(plans["stability"].freeze_required)
        self.assertEqual(
            Counter(job.model for job in plans["main"].jobs),
            {model: len(MAIN_SEEDS) for model in CORE_MODELS},
        )
        self.assertTrue(all(job.expected_run_count == 540 for job in plans["main"].jobs))
        self.assertEqual(
            {
                (job.model, int(job.matrix_config["generation_seed"]))
                for job in plans["main"].jobs
            },
            {(model, seed) for model in CORE_MODELS for seed in MAIN_SEEDS},
        )
        self.assertTrue(
            all(tuple(job.matrix_config["conditions"].split(",")) == core_condition_specs()
                for job in plans["main"].jobs)
        )
        self.assertTrue(all(job.matrix_config["splits"] == "blind" for job in plans["main"].jobs))

        stability = plans["stability"]
        self.assertEqual(
            {
                (
                    job.model,
                    int(job.matrix_config["generation_seed"]),
                    float(job.matrix_config["temperature"]),
                )
                for job in stability.jobs
            },
            {
                (model, seed, temperature)
                for model in CORE_MODELS
                for temperature in STABILITY_TEMPERATURES
                for seed in STABILITY_SEEDS
            },
        )

    def test_all_conditions_are_explicit_and_outputs_are_unique(self) -> None:
        output_dirs: list[str] = []
        run_prefixes: list[str] = []
        for stage in STAGES:
            plan = build_stage_plan(stage)
            for job in plan.jobs:
                output_dirs.append(str(job.matrix_config["out_dir"]))
                run_prefixes.append(str(job.matrix_config["run_prefix"]))
                for condition in str(job.matrix_config["conditions"]).split(","):
                    condition_id, separator, specification = condition.partition("=")
                    self.assertTrue(condition_id)
                    self.assertEqual(separator, "=")
                    self.assertIn(":", specification)
        self.assertEqual(len(output_dirs), len(set(output_dirs)))
        self.assertEqual(len(run_prefixes), len(set(run_prefixes)))

    def test_ablation_covers_all_solo_remove_and_named_profiles(self) -> None:
        plan = build_stage_plan("ablation")
        condition_ids = [_condition_ids(job.matrix_config)[0] for job in plan.jobs]
        self.assertEqual(len(condition_ids), len(set(condition_ids)))
        self.assertEqual(len(condition_ids), 2 * len(ALL_MODULES) + len(MODE_MODULES))
        for module in ALL_MODULES:
            solo = next(job for job in plan.jobs if job.job_id.endswith(f"solo_{module}"))
            self.assertEqual(solo.matrix_config["guard_modules"], module)
            removed = next(job for job in plan.jobs if job.job_id.endswith(f"remove_{module}"))
            self.assertEqual(
                set(str(removed.matrix_config["guard_modules"]).split(",")),
                set(ALL_MODULES) - {module},
            )
        for mode in MODE_MODULES:
            named = next(job for job in plan.jobs if job.job_id.endswith(f"named_{mode}"))
            self.assertEqual(named.matrix_config["guard_modules"], "")
            self.assertTrue(str(named.matrix_config["conditions"]).endswith(f"normal:{mode}"))
        self.assertEqual(
            {int(job.matrix_config["generation_seed"]) for job in plan.jobs},
            {307},
        )

    def test_derived_context_batches_and_optional_coverage(self) -> None:
        plan = build_stage_plan("derived")
        e9 = [job for job in plan.jobs if "__e9__" in job.job_id]
        self.assertEqual(len(e9), 4)
        self.assertEqual({job.matrix_config["num_ctx"] for job in e9}, {2048, 4096, 8192, 16384})
        self.assertTrue(all(len(str(job.matrix_config["case_ids"]).split(",")) == 15 for job in e9))
        self.assertTrue(all(job.expected_run_count == 30 for job in e9))

        expanded = build_stage_plan("derived", include_derived_coverage=True)
        self.assertEqual(len(expanded.jobs), 8)
        self.assertEqual(expanded.expected_run_count, 446)
        self.assertTrue(any("__e7__" in job.job_id for job in expanded.jobs))
        self.assertTrue(any("__e11__" in job.job_id for job in expanded.jobs))

    def test_matrix_command_is_config_equivalent(self) -> None:
        regular = build_stage_plan("validation-baseline").jobs[0]
        command = matrix_command(regular.matrix_config)
        self.assertIn("--conditions", command)
        self.assertIn(regular.matrix_config["conditions"], command)
        self.assertIn("--out-dir", command)
        self.assertNotIn("--resume", command)

        e9 = next(job for job in build_stage_plan("derived").jobs if "__e9__" in job.job_id)
        command = matrix_command({**e9.matrix_config, "resume": True})
        self.assertIn("--num-ctx", command)
        self.assertIn(str(e9.matrix_config["num_ctx"]), command)
        self.assertIn("--case-ids", command)
        self.assertIn("--resume", command)


class RunProgramExecutionTests(unittest.TestCase):
    def test_blind_freeze_gate_blocks_every_main_job_before_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "program.json"
            output_root = root / "outputs"
            freeze_path = root / "blind_freeze.json"
            _write_freeze(freeze_path)
            smoke = build_stage_plan("smoke", output_root=output_root)
            smoke_calls: list[dict[str, Any]] = []
            run_stage(
                "smoke",
                manifest_path=manifest_path,
                output_root=output_root,
                matrix_runner=_success_runner((smoke,), smoke_calls),
            )
            self.assertEqual(len(smoke_calls), len(ALL_MODELS))

            main = build_stage_plan("main", output_root=output_root)
            main_calls: list[dict[str, Any]] = []
            result = run_stage(
                "main",
                manifest_path=manifest_path,
                output_root=output_root,
                freeze_path=freeze_path,
                matrix_runner=_success_runner((main,), main_calls),
                freeze_verifier=lambda path: ["changed: m3_guard/config.py"],
                require_frozen_thresholds=False,
            )
            self.assertEqual(main_calls, [])
            self.assertEqual(result["stage"]["status"], "blocked")
            self.assertEqual(result["stage"]["freeze_verification"]["status"], "failed")
            self.assertTrue(all(job["status"] == "blocked" for job in result["stage"]["jobs"]))

    def test_failed_smoke_model_is_not_scheduled_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "program.json"
            output_root = root / "outputs"
            freeze_path = root / "blind_freeze.json"
            _write_freeze(freeze_path)
            smoke = build_stage_plan("smoke", output_root=output_root)
            smoke_calls: list[dict[str, Any]] = []
            successful_smoke = _success_runner((smoke,), smoke_calls)

            def smoke_runner(config: dict[str, Any]) -> dict[str, Any]:
                if config["model"] == QWEN_MODEL:
                    smoke_calls.append(dict(config))
                    ids = _condition_ids(config)
                    return {
                        "manifest_path": "mock/failed.json",
                        "manifest": {"status": "failed"},
                        "results": [
                            {
                                "condition_id": ids[0],
                                "status": "completed",
                                "selected_run_count": 6,
                                "completed_run_count": 6,
                                "error_count": 0,
                            },
                            {
                                "condition_id": ids[1],
                                "status": "failed",
                                "selected_run_count": 6,
                                "completed_run_count": 5,
                                "error_count": 1,
                            },
                        ],
                    }
                return successful_smoke(config)

            smoke_result = run_stage(
                "smoke",
                manifest_path=manifest_path,
                output_root=output_root,
                matrix_runner=smoke_runner,
            )
            self.assertEqual(smoke_result["stage"]["status"], "failed")
            self.assertIn(QWEN_MODEL, smoke_result["manifest"]["blocked_models"])

            main = build_stage_plan("main", output_root=output_root)
            main_calls: list[dict[str, Any]] = []
            result = run_stage(
                "main",
                manifest_path=manifest_path,
                output_root=output_root,
                freeze_path=freeze_path,
                matrix_runner=_success_runner((main,), main_calls),
                freeze_verifier=lambda path: [],
                continue_on_error=True,
                require_frozen_thresholds=False,
            )
            self.assertEqual(len(main_calls), 3 * len(MAIN_SEEDS))
            self.assertNotIn(QWEN_MODEL, {call["model"] for call in main_calls})
            qwen_jobs = [job for job in result["stage"]["jobs"] if job["model"] == QWEN_MODEL]
            self.assertTrue(all(job["status"] == "blocked" for job in qwen_jobs))
            self.assertEqual(result["stage"]["status"], "failed")

    def test_resume_retries_failed_job_and_does_not_silently_skip_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "program.json"
            output_root = root / "outputs"
            plan = build_stage_plan("stub", output_root=output_root)
            calls: list[dict[str, Any]] = []
            success = _success_runner((plan,), calls)
            fail_once = {"value": True}

            def runner(config: dict[str, Any]) -> dict[str, Any]:
                if fail_once["value"]:
                    fail_once["value"] = False
                    calls.append(dict(config))
                    raise RuntimeError("synthetic first-attempt failure")
                return success(config)

            first = run_stage(
                "stub",
                manifest_path=manifest_path,
                output_root=output_root,
                matrix_runner=runner,
            )
            self.assertEqual(first["stage"]["status"], "failed")
            second = run_stage(
                "stub",
                manifest_path=manifest_path,
                output_root=output_root,
                resume=True,
                matrix_runner=runner,
            )
            job = second["stage"]["jobs"][0]
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["attempts"], 2)
            self.assertEqual([item["status"] for item in job["attempt_history"]], ["failed", "completed"])
            self.assertEqual(job["completed_run_count"], 3300)
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[-1]["resume"])
            self.assertIn("--resume", job["command"])

    def test_counter_mismatch_fails_job_with_actual_counts_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "program.json"
            output_root = root / "outputs"
            plan = build_stage_plan("stub", output_root=output_root)

            def bad_runner(config: dict[str, Any]) -> dict[str, Any]:
                ids = _condition_ids(config)
                per = 300
                rows = [
                    {
                        "condition_id": condition_id,
                        "status": "completed",
                        "selected_run_count": per,
                        "completed_run_count": per,
                        "error_count": 0,
                    }
                    for condition_id in ids
                ]
                rows[-1]["selected_run_count"] -= 1
                rows[-1]["completed_run_count"] -= 1
                return {
                    "manifest_path": "mock/bad.json",
                    "manifest": {"status": "completed"},
                    "results": rows,
                }

            result = run_stage(
                "stub",
                manifest_path=manifest_path,
                output_root=output_root,
                matrix_runner=bad_runner,
            )
            job = result["stage"]["jobs"][0]
            self.assertEqual(job["status"], "failed")
            self.assertEqual(job["selected_run_count"], 3299)
            self.assertEqual(job["completed_run_count"], 3299)
            self.assertEqual(job["error_count"], 1)
            self.assertEqual(job["error"]["type"], "ResultValidationError")

    def test_frozen_inputs_are_pinned_and_resume_drift_is_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "program.json"
            output_root = root / "outputs"
            freeze_path = root / "blind_freeze.json"
            thresholds_path = root / "frozen_thresholds.json"
            freeze_bytes = _write_freeze(freeze_path)
            threshold_bytes = _write_thresholds(thresholds_path)

            smoke = build_stage_plan("smoke", output_root=output_root)
            run_stage(
                "smoke",
                manifest_path=manifest_path,
                output_root=output_root,
                matrix_runner=_success_runner((smoke,), []),
            )
            main = build_stage_plan("main", output_root=output_root)
            main_calls: list[dict[str, Any]] = []
            first = run_stage(
                "main",
                manifest_path=manifest_path,
                output_root=output_root,
                freeze_path=freeze_path,
                thresholds_path=thresholds_path,
                matrix_runner=_success_runner((main,), main_calls),
                freeze_verifier=lambda _path: [],
            )
            stage = first["stage"]
            self.assertEqual(stage["status"], "completed")
            self.assertEqual(stage["plan_hash_version"], 2)
            self.assertEqual(
                stage["frozen_inputs"]["blind_freeze"]["sha256"],
                sha256_file(freeze_path),
            )
            self.assertEqual(
                stage["frozen_inputs"]["thresholds"]["sha256"],
                sha256_file(thresholds_path),
            )
            self.assertEqual(
                stage["freeze_verification"]["sha256"], sha256_file(freeze_path)
            )

            call_count = len(main_calls)
            resumed = run_stage(
                "main",
                manifest_path=manifest_path,
                output_root=output_root,
                freeze_path=freeze_path,
                thresholds_path=thresholds_path,
                resume=True,
                matrix_runner=_success_runner((main,), main_calls),
                freeze_verifier=lambda _path: [],
            )
            self.assertEqual(resumed["stage"]["status"], "completed")
            self.assertEqual(len(main_calls), call_count)

            manifest_before_drift = manifest_path.read_bytes()
            _write_freeze(freeze_path, marker="v2")
            with self.assertRaisesRegex(ProgramError, "plan hash changed"):
                run_stage(
                    "main",
                    manifest_path=manifest_path,
                    output_root=output_root,
                    freeze_path=freeze_path,
                    thresholds_path=thresholds_path,
                    resume=True,
                    matrix_runner=_success_runner((main,), main_calls),
                    freeze_verifier=lambda _path: [],
                )
            self.assertEqual(manifest_path.read_bytes(), manifest_before_drift)

            freeze_path.write_bytes(freeze_bytes)
            thresholds_path.write_bytes(threshold_bytes + b"\n")
            with self.assertRaisesRegex(ProgramError, "plan hash changed"):
                run_stage(
                    "main",
                    manifest_path=manifest_path,
                    output_root=output_root,
                    freeze_path=freeze_path,
                    thresholds_path=thresholds_path,
                    resume=True,
                    matrix_runner=_success_runner((main,), main_calls),
                    freeze_verifier=lambda _path: [],
                )
            self.assertEqual(manifest_path.read_bytes(), manifest_before_drift)

    def test_freeze_change_during_verification_is_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "program.json"
            output_root = root / "outputs"
            freeze_path = root / "blind_freeze.json"
            _write_freeze(freeze_path)
            smoke = build_stage_plan("smoke", output_root=output_root)
            run_stage(
                "smoke",
                manifest_path=manifest_path,
                output_root=output_root,
                matrix_runner=_success_runner((smoke,), []),
            )
            manifest_before = manifest_path.read_bytes()

            def mutating_verifier(path: Path) -> list[str]:
                _write_freeze(Path(path), marker="changed-during-verify")
                return []

            main = build_stage_plan("main", output_root=output_root)
            with self.assertRaisesRegex(
                ProgramGateError, "changed during verification"
            ):
                run_stage(
                    "main",
                    manifest_path=manifest_path,
                    output_root=output_root,
                    freeze_path=freeze_path,
                    matrix_runner=_success_runner((main,), []),
                    freeze_verifier=mutating_verifier,
                    require_frozen_thresholds=False,
                )
            self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_stability_stops_each_model_and_records_gpu_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "program.json"
            output_root = root / "outputs"
            freeze_path = root / "blind_freeze.json"
            _write_freeze(freeze_path)
            smoke = build_stage_plan("smoke", output_root=output_root)
            smoke_calls: list[dict[str, Any]] = []
            run_stage(
                "smoke",
                manifest_path=manifest_path,
                output_root=output_root,
                matrix_runner=_success_runner((smoke,), smoke_calls),
            )

            stability = build_stage_plan("stability", output_root=output_root)
            stability_calls: list[dict[str, Any]] = []
            stopped: list[str] = []
            snapshots: list[int] = []

            def snapshot() -> dict[str, Any]:
                snapshots.append(len(snapshots) + 1)
                return {"available": True, "sequence": snapshots[-1]}

            result = run_stage(
                "stability",
                manifest_path=manifest_path,
                output_root=output_root,
                freeze_path=freeze_path,
                matrix_runner=_success_runner((stability,), stability_calls),
                model_stopper=stopped.append,
                gpu_snapshotter=snapshot,
                freeze_verifier=lambda path: [],
                require_frozen_thresholds=False,
                manage_model_lifecycle=True,
            )
            self.assertEqual(result["stage"]["status"], "completed")
            self.assertEqual(len(stability_calls), 120)
            self.assertEqual(stopped, list(CORE_MODELS))
            self.assertEqual(len(snapshots), len(CORE_MODELS))
            lifecycle = [
                item
                for item in result["manifest"]["model_lifecycle"]
                if item["stage"] == "stability"
            ]
            self.assertEqual(len(lifecycle), 4)
            self.assertTrue(all(item["stop_status"] == "completed" for item in lifecycle))
            self.assertEqual(result["stage"]["progress"]["completed_runs"], 3600)


if __name__ == "__main__":
    unittest.main()
