from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from experiments.paper_v1.run_matrix import DEFAULT_DATASET, ROOT, main


class PaperMatrixTests(unittest.TestCase):
    def test_stub_diagnostic_matrix_is_resume_safe_and_manifested(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "matrix"
            arguments = [
                "--dataset",
                str(DEFAULT_DATASET),
                "--output-dir",
                str(output),
                "--experiment-id",
                "unit-paper-matrix",
                "--backend",
                "stub",
                "--oracle-stub",
                "--models",
                "stub-regression",
                "--conditions",
                "no_defense",
                "m3_full",
                "--no-think",
                "--case-limit",
                "2",
            ]
            self.assertEqual(main(arguments), 0)
            result_lines = (output / "case_results.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(result_lines), 4)
            self.assertEqual(main(arguments), 0)
            self.assertEqual(
                len(
                    (output / "case_results.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ),
                4,
            )
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            schema = json.loads(
                (ROOT / "schemas" / "paper_v1" / "experiment_manifest.schema.json")
                .read_text(encoding="utf-8")
            )
            Draft202012Validator(schema).validate(manifest)
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["completed_case_runs"], 4)
            self.assertFalse(manifest["effectiveness_eligible"])
            self.assertFalse((output / "failures.jsonl").exists())
            config = json.loads((output / "execution_config.json").read_text(encoding="utf-8"))
            self.assertIs(config["think"], False)
            self.assertEqual(config["dataset"], "m3_attacks/cases/paper_v1/m3_v2_validation.jsonl")
            self.assertEqual(config["baseline_registry"], "protocols/paper_upgrade_v1/baseline_registry.json")


if __name__ == "__main__":
    unittest.main()
