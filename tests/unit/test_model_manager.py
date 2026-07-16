from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from experiments.model_manager import installed_models, missing_models, pull_model


class ModelManagerTests(unittest.TestCase):
    @patch("experiments.model_manager.run_ollama")
    def test_parses_installed_models(self, mocked_run: object) -> None:
        mocked_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="NAME ID SIZE MODIFIED\nqwen3:4b-instruct abc 2.5 GB now\nvicuna:7b def 3.8 GB old\n",
            stderr="",
        )
        rows = installed_models()
        self.assertEqual(set(rows), {"qwen3:4b-instruct", "vicuna:7b"})
        self.assertEqual(missing_models(["qwen3:4b-instruct", "gemma3:4b"]), ["gemma3:4b"])

    def test_rejects_unapproved_pull(self) -> None:
        with self.assertRaises(ValueError):
            pull_model("unknown:model")


if __name__ == "__main__":
    unittest.main()
