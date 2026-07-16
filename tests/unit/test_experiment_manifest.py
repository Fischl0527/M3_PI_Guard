from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.catalog import CORE_CONDITIONS, CORE_MODELS, MAIN_SEEDS
from experiments.manifest import (
    finish_manifest,
    new_manifest,
    register_artifact,
    save_manifest,
    sha256_paths,
    validate_completed_manifest,
)


class ExperimentManifestTests(unittest.TestCase):
    def test_frozen_main_grid_shape(self) -> None:
        self.assertEqual(len(CORE_MODELS) * 90 * len(CORE_CONDITIONS) * len(MAIN_SEEDS), 6480)

    def test_hash_is_deterministic_and_path_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            a = root / "a.jsonl"
            b = root / "b.jsonl"
            a.write_text("one\n", encoding="utf-8")
            b.write_text("two\n", encoding="utf-8")
            self.assertEqual(sha256_paths([a, b]), sha256_paths([b, a]))
            original = sha256_paths([a, b])
            b.write_text("changed\n", encoding="utf-8")
            self.assertNotEqual(original, sha256_paths([a, b]))

    @patch("experiments.manifest.environment_snapshot", return_value={"test": True})
    @patch("experiments.manifest.git_state", return_value={"commit": "abc", "branch": "test1", "dirty": True})
    def test_manifest_requires_exact_run_count(self, _git: object, _env: object) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset = root / "cases.jsonl"
            dataset.write_text("{}\n", encoding="utf-8")
            manifest = new_manifest(
                "E1",
                dataset_paths=[dataset],
                configuration={"condition": "regular_full"},
                expected_runs=3,
                models=["stub"],
            )
            with self.assertRaises(ValueError):
                finish_manifest(manifest, completed_runs=2)
            finish_manifest(manifest, completed_runs=3)
            self.assertEqual(validate_completed_manifest(manifest), [])
            path = root / "manifest.json"
            save_manifest(manifest, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "completed")

    @patch("experiments.manifest.environment_snapshot", return_value={"test": True})
    @patch("experiments.manifest.git_state", return_value={"commit": "abc", "branch": "test1", "dirty": True})
    def test_registered_artifact_records_bytes_and_hash(self, _git: object, _env: object) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset = root / "cases.jsonl"
            dataset.write_text("{}\n", encoding="utf-8")
            artifact = root / "metrics.csv"
            artifact.write_text("metric,value\nASR,0.1\n", encoding="utf-8")
            manifest = new_manifest(
                "E1", dataset_paths=[dataset], configuration={}, expected_runs=0
            )
            register_artifact(manifest, artifact, kind="metrics")
            self.assertGreater(manifest["artifacts"][0]["bytes"], 0)
            self.assertEqual(len(manifest["artifacts"][0]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
