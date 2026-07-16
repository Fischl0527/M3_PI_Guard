from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.run_program import (
    ProgramGateError,
    _apply_frozen_thresholds,
    _load_frozen_thresholds,
    build_stage_plan,
)


class ProgramThresholdFreezeTests(unittest.TestCase):
    def test_e13_thresholds_are_applied_to_every_post_calibration_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "frozen_thresholds.json"
            path.write_text(
                json.dumps(
                    {
                        "experiment_id": "E13",
                        "scope": "validation_only",
                        "status": "targets_met",
                        "ask_threshold": 0.41,
                        "deny_threshold": 0.73,
                    }
                ),
                encoding="utf-8",
            )
            frozen = _load_frozen_thresholds(path)
            plan = _apply_frozen_thresholds(build_stage_plan("main"), frozen)
            self.assertTrue(
                all(job.matrix_config["ask_threshold"] == 0.41 for job in plan.jobs)
            )
            self.assertTrue(
                all(job.matrix_config["deny_threshold"] == 0.73 for job in plan.jobs)
            )

            ablation = _apply_frozen_thresholds(
                build_stage_plan("ablation"), frozen
            )
            self.assertTrue(
                all(job.matrix_config["ask_threshold"] == 0.41 for job in ablation.jobs)
            )
            self.assertTrue(
                all(job.matrix_config["deny_threshold"] == 0.73 for job in ablation.jobs)
            )

    def test_non_validation_threshold_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "wrong.json"
            path.write_text(
                json.dumps(
                    {
                        "experiment_id": "E13",
                        "scope": "blind",
                        "ask_threshold": 0.3,
                        "deny_threshold": 0.7,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ProgramGateError):
                _load_frozen_thresholds(path)


if __name__ == "__main__":
    unittest.main()
