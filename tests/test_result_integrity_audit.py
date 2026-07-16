from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from agent.result_integrity_audit import audit_program, render_markdown


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ResultIntegrityAuditTests(unittest.TestCase):
    def _fixture(self, root: Path, *, stage_status: str = "completed") -> tuple[Path, Path, Path]:
        dataset = root / "fixtures" / "cases.jsonl"
        dataset.parent.mkdir(parents=True)
        dataset.write_text(
            json.dumps({"case_id": "CASE-001", "split": "blind"}) + "\n",
            encoding="utf-8",
        )
        thresholds = root / "outputs" / "experiments" / "E13" / "frozen_thresholds.json"
        _write_json(
            thresholds,
            {"experiment_id": "E13", "ask_threshold": 1.0, "deny_threshold": 1.0},
        )
        protected = root / "m3_core" / "frozen.py"
        protected.parent.mkdir(parents=True)
        protected.write_text("VALUE = 1\n", encoding="utf-8")
        freeze = root / "outputs" / "experiments" / "blind_freeze.json"
        _write_json(
            freeze,
            {
                "file_count": 2,
                "files": {
                    "m3_core/frozen.py": _sha(protected),
                    "outputs/experiments/E13/frozen_thresholds.json": _sha(thresholds),
                },
            },
        )
        freeze_sha = _sha(freeze)
        threshold_sha = _sha(thresholds)

        stages: dict[str, object] = {}
        lifecycle: list[dict[str, object]] = []
        for stage_name in ("main", "derived", "stability"):
            job_id = f"{stage_name}__qwen"
            out_dir = root / "outputs" / "experiments" / "program" / stage_name / job_id
            out_dir.mkdir(parents=True)
            jsonl_path = out_dir / f"{job_id}_full.jsonl"
            csv_path = out_dir / f"{job_id}_full.csv"
            run_row = {
                "run_id": f"run-{stage_name}",
                "run_key": f"full:CASE-001:r0:s7:{stage_name}",
                "case_id": "CASE-001",
                "condition_id": "full",
                "replicate_id": 0,
                "seed": 7,
                "step": 1,
                "final_status": "max_steps_reached" if stage_name == "stability" else "completed",
                "parse_ok": stage_name != "derived",
                "timed_out": False,
                "model": "qwen3:4b-instruct",
                "sandbox_instance_id": f"sandbox-{stage_name}",
                "sandbox_reset_status": "fresh_cleaned",
                "sandbox_fixture_sha256": "fixture-sha",
                "sandbox_seed_sha256": "seed-sha",
                "raw_model_output": "DO-NOT-LEAK-THIS-MODEL-TEXT",
            }
            jsonl_path.write_text(json.dumps(run_row) + "\n", encoding="utf-8")
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(run_row))
                writer.writeheader()
                writer.writerow(run_row)
            config = {
                "cases": "fixtures/cases.jsonl",
                "dataset_sha256": _sha(dataset),
                "model": "qwen3:4b-instruct",
                "conditions": [{"condition_id": "full", "prompt_profile": "normal", "guard_mode": "full_guard"}],
                "ask_threshold": 1.0,
                "deny_threshold": 1.0,
                "families": [],
                "splits": ["blind"],
                "sample_types": [],
                "task_types": [],
                "case_ids": [],
                "limit": None,
                "shuffle": False,
                "selection_seed": 7,
                "generation_seed": 7,
                "repeats": 1,
                "max_steps": 1,
            }
            condition = {
                "condition_id": "full",
                "status": "completed",
                "jsonl": jsonl_path.relative_to(root).as_posix(),
                "csv": csv_path.relative_to(root).as_posix(),
                "jsonl_sha256": _sha(jsonl_path),
                "csv_sha256": _sha(csv_path),
                "selected_run_count": 1,
                "completed_run_count": 1,
                "log_count": 1,
                "sandbox_fixture_sha256": "fixture-sha",
                "sandbox_seed_sha256": {"7": "seed-sha"},
            }
            matrix_manifest = out_dir / "manifest.json"
            _write_json(
                matrix_manifest,
                {
                    "status": "completed",
                    "config": config,
                    "config_hash": _json_hash(config),
                    "model_identity": {
                        "tag": "qwen3:4b-instruct",
                        "digest": "digest-1",
                        "ollama_version": "ollama 1.0",
                    },
                    "dataset": {
                        "path": "fixtures/cases.jsonl",
                        "sha256": _sha(dataset),
                        "row_count": 1,
                    },
                    "conditions": [condition],
                    "results": [dict(condition)],
                },
            )
            job = {
                "job_id": job_id,
                "model": "qwen3:4b-instruct",
                "status": "completed" if stage_status == "completed" else "running",
                "expected_run_count": 1,
                "selected_run_count": 1,
                "completed_run_count": 1,
                "result_manifest": matrix_manifest.relative_to(root).as_posix(),
                "completed_at": "2026-01-01T00:00:00+00:00",
                "matrix_config": {"ask_threshold": 1.0, "deny_threshold": 1.0},
            }
            stages[stage_name] = {
                "stage": stage_name,
                "status": stage_status,
                "job_count": 1,
                "condition_count": 1,
                "expected_run_count": 1,
                "required_models": ["qwen3:4b-instruct"],
                "jobs": [job],
                "progress": {"expected_runs": 1, "completed_runs": 1, "error_count": 0},
                "frozen_inputs": {
                    "blind_freeze": {
                        "path": freeze.relative_to(root).as_posix(),
                        "sha256": freeze_sha,
                    },
                    "thresholds": {
                        "path": thresholds.relative_to(root).as_posix(),
                        "sha256": threshold_sha,
                    },
                },
                "freeze_verification": {
                    "status": "pass",
                    "problems": [],
                    "sha256": freeze_sha,
                },
                "threshold_freeze": {
                    "ask_threshold": 1.0,
                    "deny_threshold": 1.0,
                    "sha256": threshold_sha,
                },
            }
            lifecycle.append(
                {
                    "stage": stage_name,
                    "model": "qwen3:4b-instruct",
                    "at": "2026-01-01T00:01:00+00:00",
                    "action": "ollama_stop_then_gpu_snapshot",
                    "stop_status": "completed",
                    "error": None,
                    "gpu_snapshot": {"available": True},
                }
            )
        program = root / "outputs" / "experiments" / "program_manifest.json"
        _write_json(program, {"status": stage_status, "stages": stages, "model_lifecycle": lifecycle})
        return program, freeze, thresholds

    def test_complete_fixture_passes_without_leaking_model_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program, freeze, thresholds = self._fixture(root)
            report = audit_program(
                repo_root=root,
                program_manifest=program,
                freeze_path=freeze,
                threshold_path=thresholds,
            )
            self.assertEqual("pass", report["status"])
            self.assertEqual(3, report["totals"]["logical_runs"])
            self.assertEqual(1, report["totals"]["parse_failure_rows"])
            self.assertEqual(1, report["totals"]["max_step_runs"])
            serialized = json.dumps(report, ensure_ascii=False) + render_markdown(report)
            self.assertNotIn("DO-NOT-LEAK-THIS-MODEL-TEXT", serialized)

    def test_running_stage_is_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program, freeze, thresholds = self._fixture(root, stage_status="running")
            # If a job were scanned this corruption would produce a decode error;
            # the concurrency gate must stop before opening it.
            active_jsonl = next((root / "outputs" / "experiments" / "program").rglob("*.jsonl"))
            active_jsonl.write_text("this file is still being written", encoding="utf-8")
            report = audit_program(
                repo_root=root,
                program_manifest=program,
                freeze_path=freeze,
                threshold_path=thresholds,
            )
            self.assertEqual("fail", report["status"])
            self.assertTrue(all(not stage["scanned"] for stage in report["stages"]))
            codes = [finding["code"] for finding in report["findings"]]
            self.assertEqual(3, codes.count("stage_not_completed"))
            self.assertNotIn("jsonl_decode_error", codes)

    def test_hash_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program, freeze, thresholds = self._fixture(root)
            target = next((root / "outputs" / "experiments" / "program" / "main").rglob("*.csv"))
            target.write_text(target.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            report = audit_program(
                repo_root=root,
                program_manifest=program,
                freeze_path=freeze,
                threshold_path=thresholds,
                stages=["main"],
            )
            self.assertEqual("fail", report["status"])
            codes = {finding["code"] for finding in report["findings"]}
            self.assertIn("csv_sha_mismatch", codes)


if __name__ == "__main__":
    unittest.main()
