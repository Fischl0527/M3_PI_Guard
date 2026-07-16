from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.registry import (
    EXPERIMENT_IDS,
    complete_experiment,
    load_registry,
    set_status,
)


class ExperimentRegistryTests(unittest.TestCase):
    def test_registry_has_all_ordered_experiments(self) -> None:
        payload = load_registry()
        self.assertEqual(
            [item["id"] for item in payload["experiments"]], list(EXPERIMENT_IDS)
        )

    def test_atomic_status_transition(self) -> None:
        payload = load_registry()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            updated = set_status("E0", "running", path=path)
            self.assertEqual(updated["status"], "running")
            loaded = load_registry(path)
            self.assertEqual(loaded["experiments"][0]["status"], "running")

    def test_invalidated_completion_drops_stale_completed_timestamp(self) -> None:
        payload = load_registry()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            entry = next(item for item in payload["experiments"] if item["id"] == "E1")
            entry["status"] = "completed"
            entry["completed_at"] = "2026-01-01T00:00:00+00:00"
            path.write_text(json.dumps(payload), encoding="utf-8")

            failed = set_status(
                "E1",
                "failed",
                error="provenance audit invalidated this result",
                path=path,
            )
            self.assertEqual(failed["status"], "failed")
            self.assertNotIn("completed_at", failed)

    def test_set_status_cannot_bypass_completion_gate(self) -> None:
        payload = load_registry()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            before = path.read_bytes()

            with self.assertRaisesRegex(ValueError, "cannot be set directly"):
                set_status("E1", "completed", path=path)

            self.assertEqual(path.read_bytes(), before)

    def test_dedicated_experiments_reject_generic_completion_without_mutation(self) -> None:
        payload = load_registry()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(payload), encoding="utf-8")
            before = registry_path.read_bytes()

            for experiment_id in ("E9", "E14", "E17"):
                manifest_path = root / f"{experiment_id}.manifest.json"
                manifest_path.write_text(
                    json.dumps(_completed_manifest(experiment_id)), encoding="utf-8"
                )
                with self.subTest(experiment_id=experiment_id):
                    with self.assertRaisesRegex(
                        ValueError,
                        rf"{experiment_id} requires a dedicated completion registrar",
                    ):
                        complete_experiment(
                            experiment_id,
                            manifest_path=manifest_path,
                            evidence=[str(manifest_path)],
                            path=registry_path,
                        )
                    self.assertEqual(registry_path.read_bytes(), before)

    def test_manifest_experiment_id_must_match_target_without_mutation(self) -> None:
        payload = load_registry()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(_completed_manifest("E2")), encoding="utf-8"
            )
            registry_path = root / "registry.json"
            entry = next(item for item in payload["experiments"] if item["id"] == "E1")
            entry["required_artifacts"] = [str(manifest_path)]
            registry_path.write_text(json.dumps(payload), encoding="utf-8")
            before = registry_path.read_bytes()

            with self.assertRaisesRegex(ValueError, "experiment_id mismatch"):
                complete_experiment(
                    "E1",
                    manifest_path=manifest_path,
                    evidence=[str(manifest_path)],
                    path=registry_path,
                )

            self.assertEqual(registry_path.read_bytes(), before)


def _completed_manifest(experiment_id: str) -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "status": "completed",
        "progress": {
            "expected_runs": 1,
            "completed_runs": 1,
            "failed_jobs": 0,
        },
        "git": {"commit": "test-commit"},
        "dataset": {"sha256": "test-dataset-sha256"},
    }


if __name__ == "__main__":
    unittest.main()
