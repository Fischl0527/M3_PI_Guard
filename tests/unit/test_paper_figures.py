from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.paper_v1.build_figures import CONTRACT_PATH, build_figures


class PaperFigureTests(unittest.TestCase):
    def test_contract_has_ten_fixed_figures_and_only_one_pie(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(contract["figures"]), 10)
        self.assertEqual(
            [row["id"] for row in contract["figures"]],
            [f"F{index:02d}" for index in range(1, 11)],
        )
        pies = [row for row in contract["figures"] if "pie" in row["variant"]]
        self.assertEqual([row["id"] for row in pies], ["F10"])
        self.assertIn("DEMO", contract["formal_input_policy"])

    def test_demo_builder_is_visibly_separate_and_hashes_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "figures_demo"
            manifest = build_figures(Path(directory) / "unused", output, demo=True)
            self.assertEqual(manifest["status"], "demo_not_formal_evidence")
            self.assertEqual(manifest["figure_count"], 10)
            self.assertEqual(manifest["artifact_count"], 20)
            self.assertEqual(len({row["figure_id"] for row in manifest["artifacts"]}), 10)
            for artifact in manifest["artifacts"]:
                path = Path(artifact["path"])
                if not path.is_absolute():
                    path = Path(__file__).resolve().parents[2] / path
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 500)

    def test_formal_builder_refuses_missing_frozen_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "missing frozen figure inputs"):
                build_figures(
                    Path(directory) / "missing",
                    Path(directory) / "formal",
                    demo=False,
                )


if __name__ == "__main__":
    unittest.main()
