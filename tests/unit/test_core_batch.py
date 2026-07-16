from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from m3_core.run_batch import _filter_cases, read_jsonl, run_batch, write_jsonl
from m3_core.run_matrix import _conditions, run_matrix
from m3_core.tool_sandbox import (
    FIXTURE_SHA256,
    ISOLATION_POLICY,
    SANDBOX_RUNTIME_VERSION,
    sandbox_seed_sha256,
)


def _write_cases(path: Path) -> None:
    rows = [
        {
            "case_id": "A",
            "sample_type": "attack",
            "split": "blind",
            "task_type": "summary",
            "attack_family": "rag_indirect",
            "user_task": "summarize",
            "document_content": "x",
        },
        {
            "case_id": "B",
            "sample_type": "benign",
            "split": "validation",
            "task_type": "tool_use",
            "attack_family": "benign_clean",
            "user_task": "read",
            "document_content": "y",
        },
    ]
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fake_success(case, **kwargs):
    return [
        {
            "run_id": "fake",
            "run_key": kwargs["run_key"],
            "case_id": case["case_id"],
            "seed": kwargs["generation_seed"],
            "replicate_id": kwargs["replicate_id"],
            "step": 1,
            "final_status": "completed",
        }
    ]


class BatchRecoveryTests(unittest.TestCase):
    def test_filters_support_split_sample_and_task_type(self) -> None:
        rows = [
            {"case_id": "A", "split": "blind", "sample_type": "attack", "task_type": "summary"},
            {"case_id": "B", "split": "dev", "sample_type": "benign", "task_type": "tool_use"},
        ]
        selected = _filter_cases(
            rows,
            {"splits": "blind", "sample_types": "attack", "task_types": "summary"},
        )
        self.assertEqual([row["case_id"] for row in selected], ["A"])

    def test_repeats_have_unique_keys_and_resume_skips_completed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases.jsonl"
            out = root / "runs.jsonl"
            _write_cases(cases)
            config = {
                "cases": str(cases),
                "out": str(out),
                "backend": "stub",
                "model": "stub",
                "defense": "baseline",
                "prompt_profile": "normal",
                "guard_mode": "off",
                "condition_id": "normal__off",
                "repeats": 2,
                "generation_seed": 50,
            }
            with patch("m3_core.run_batch.run_case", side_effect=_fake_success) as runner:
                first = run_batch(config)
                self.assertEqual(runner.call_count, 4)
            rows = list(read_jsonl(out))
            self.assertEqual(len({row["run_key"] for row in rows}), 4)
            self.assertEqual({row["seed"] for row in rows}, {50, 51})

            with patch("m3_core.run_batch.run_case", side_effect=_fake_success) as runner:
                second = run_batch({**config, "resume": True})
                self.assertEqual(runner.call_count, 0)
            self.assertEqual(second["skipped_run_count"], 4)
            self.assertEqual(first["completed_run_count"], 4)
            self.assertEqual(first["sandbox_runtime_version"], SANDBOX_RUNTIME_VERSION)
            self.assertEqual(first["sandbox_fixture_sha256"], FIXTURE_SHA256)
            self.assertEqual(first["sandbox_isolation_policy"], ISOLATION_POLICY)
            self.assertEqual(
                first["sandbox_seed_sha256"],
                {"50": sandbox_seed_sha256(50), "51": sandbox_seed_sha256(51)},
            )

    def test_error_is_retried_and_replaced_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases.jsonl"
            out = root / "runs.jsonl"
            _write_cases(cases)
            config = {
                "cases": str(cases),
                "case_ids": "A",
                "out": str(out),
                "backend": "stub",
                "model": "stub",
                "defense": "baseline",
                "condition_id": "normal__off",
            }
            with patch("m3_core.run_batch.run_case", side_effect=RuntimeError("boom")):
                result = run_batch(config)
            self.assertEqual(result["error_count"], 1)

            with patch("m3_core.run_batch.run_case", side_effect=_fake_success) as runner:
                run_batch({**config, "resume": True})
                self.assertEqual(runner.call_count, 1)
            rows = list(read_jsonl(out))
            self.assertEqual([row["final_status"] for row in rows], ["completed"])

    def test_atomic_checkpoint_supersedes_partially_appended_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases.jsonl"
            out = root / "runs.jsonl"
            _write_cases(cases)
            config = {
                "cases": str(cases),
                "case_ids": "A",
                "out": str(out),
                "backend": "stub",
                "model": "stub",
                "defense": "baseline",
                "condition_id": "normal__off",
            }
            with patch("m3_core.run_batch.run_case", side_effect=RuntimeError("boom")):
                run_batch(config)
            error_row = list(read_jsonl(out))[0]
            checkpoint = next((root / ".runs.parts").glob("*.jsonl"))
            success = {
                "run_id": "recovered",
                "run_key": error_row["run_key"],
                "case_id": "A",
                "seed": 42,
                "replicate_id": 0,
                "step": 1,
                "final_status": "completed",
            }
            write_jsonl(checkpoint, [success])

            with patch("m3_core.run_batch.run_case", side_effect=_fake_success) as runner:
                run_batch({**config, "resume": True})
                self.assertEqual(runner.call_count, 0)
            self.assertEqual(list(read_jsonl(out)), [success])


class MatrixManifestTests(unittest.TestCase):
    def test_ablation_override_has_unique_condition_identity(self) -> None:
        labeled = _conditions(
            {
                "conditions": "normal:full_guard",
                "condition_label": "ablate_dataflow",
                "guard_modules": "policy,instruction_detector",
            }
        )
        self.assertEqual(labeled[0]["condition_id"], "ablate_dataflow")
        automatic = _conditions(
            {
                "conditions": "normal:full_guard",
                "guard_modules": "policy,instruction_detector",
            }
        )
        self.assertIn("modules_", automatic[0]["condition_id"])
        explicit = _conditions(
            {
                "conditions": "my_ablation=normal:full_guard",
                "guard_modules": "policy,instruction_detector",
            }
        )
        self.assertEqual(explicit[0]["condition_id"], "my_ablation")

    def test_legacy_defense_cli_keeps_historical_output_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases.jsonl"
            out_dir = root / "matrix"
            _write_cases(cases)

            def fake_batch(config):
                Path(config["out"]).write_text("{}\n", encoding="utf-8")
                Path(config["csv_out"]).write_text("header\n", encoding="utf-8")
                return {"error_count": 0, "log_count": 1}

            with patch("m3_core.run_matrix.run_batch", side_effect=fake_batch):
                result = run_matrix(
                    {
                        "cases": str(cases),
                        "out_dir": str(out_dir),
                        "backend": "stub",
                        "defense_modes": "baseline,full_guard",
                        "run_prefix": "legacy",
                    }
                )
            names = {Path(item["jsonl"]).name for item in result["results"]}
            self.assertEqual(names, {"legacy_baseline.jsonl", "legacy_full_guard.jsonl"})

    def test_manifest_is_completed_and_resume_rejects_config_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases.jsonl"
            out_dir = root / "matrix"
            _write_cases(cases)

            def fake_batch(config):
                Path(config["out"]).write_text("{}\n", encoding="utf-8")
                Path(config["csv_out"]).write_text("header\n", encoding="utf-8")
                return {
                    "case_count": 2,
                    "selected_case_count": 2,
                    "selected_run_count": 2,
                    "skipped_case_count": 0,
                    "completed_run_count": 2,
                    "error_count": 0,
                    "log_count": 2,
                }

            config = {
                "cases": str(cases),
                "out_dir": str(out_dir),
                "backend": "stub",
                "model": "stub",
                "conditions": "normal:off,hardened:full_guard",
                "run_prefix": "test",
            }
            with patch("m3_core.run_matrix.run_batch", side_effect=fake_batch):
                result = run_matrix(config)
            self.assertEqual(result["manifest"]["status"], "completed")
            self.assertEqual(len(result["manifest"]["conditions"]), 2)
            self.assertEqual(
                result["manifest"]["sandbox_runtime_version"],
                SANDBOX_RUNTIME_VERSION,
            )
            self.assertEqual(
                result["manifest"]["sandbox_fixture_sha256"],
                FIXTURE_SHA256,
            )
            self.assertEqual(
                result["manifest"]["sandbox_seed_sha256"],
                {"42": sandbox_seed_sha256(42)},
            )
            self.assertEqual(
                result["manifest"]["config"]["sandbox_isolation_policy"],
                ISOLATION_POLICY,
            )
            self.assertTrue(
                all(
                    item["sandbox_fixture_sha256"] == FIXTURE_SHA256
                    for item in result["manifest"]["results"]
                )
            )

            with patch("m3_core.run_matrix.run_batch", side_effect=fake_batch):
                with self.assertRaisesRegex(RuntimeError, "config_hash"):
                    run_matrix({**config, "resume": True, "temperature": 0.9})

            manifest_path = out_dir / "manifest.json"
            tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered["sandbox_fixture_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(tampered), encoding="utf-8")
            with patch("m3_core.run_matrix.run_batch", side_effect=fake_batch):
                with self.assertRaisesRegex(RuntimeError, "sandbox identity"):
                    run_matrix({**config, "resume": True})


if __name__ == "__main__":
    unittest.main()
