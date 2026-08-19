from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from m3_core.project_config import (
    ProjectConfigError,
    load_project_config,
    parse_env_file,
    redacted_config,
    validate_project_config,
)
from experiments.paper_v1.benchmarks.audit_frontier_api_model_slots import (
    build_frontier_api_model_slot_audit,
)
from scripts.check_project_config import tracked_secret_hits


VALID_SHARED = {
    "M3_RUNTIME_ROOT": r"E:\M3_PI_Guard_runtime",
    "HF_HOME": r"E:\AI_Cache\huggingface",
    "HF_HUB_CACHE": r"E:\AI_Cache\huggingface\hub",
    "OLLAMA_MODELS": r"E:\Ollama\models",
    "M3_OLLAMA_BASE_URL": "http://127.0.0.1:11434/v1",
    "PROMPTGUARD_MODEL_ID": "meta-llama/Llama-Prompt-Guard-2-86M",
    "PROMPTGUARD_REVISION": "a8ded8e697ce7c355e395a0df51f94adb4a2fd27",
    "PROMPTGUARD_THRESHOLD": "0.5",
    "PROMPTGUARD_CHUNK_TOKEN_LIMIT": "512",
    "PROMPTGUARD_DOWNLOAD_SNAPSHOT": r"E:\runtime\snapshot.json",
}


class ProjectConfigTests(unittest.TestCase):
    def test_parser_preserves_hash_and_dollar_in_unquoted_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local.env"
            path.write_text("HF_TOKEN=hf_example#$value\n", encoding="utf-8")
            self.assertEqual(parse_env_file(path)["HF_TOKEN"], "hf_example#$value")

    def test_parser_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local.env"
            path.write_text("A=1\nA=2\n", encoding="utf-8")
            with self.assertRaises(ProjectConfigError):
                parse_env_file(path)

    def test_redaction_never_returns_secret_value(self) -> None:
        token = "hf_this_must_never_be_printed"
        result = redacted_config(
            {
                "HF_TOKEN": token,
                "OPENAI_API_KEY": "sk-example",
                "PROMPTGUARD_CHUNK_TOKEN_LIMIT": "512",
                "MODEL": "safe",
            }
        )
        self.assertNotIn(token, repr(result))
        self.assertNotIn("sk-example", repr(result))
        self.assertEqual(result["HF_TOKEN"], "<redacted:set>")
        self.assertEqual(result["PROMPTGUARD_CHUNK_TOKEN_LIMIT"], "512")
        self.assertEqual(result["MODEL"], "safe")

    def test_token_gate_distinguishes_placeholder_and_set_value(self) -> None:
        placeholder = {**VALID_SHARED, "HF_TOKEN": "__SET_LOCALLY__"}
        configured = {**VALID_SHARED, "HF_TOKEN": "hf_abcdefghijklmnopqrstuvwxyz"}
        self.assertIn(
            "HF_TOKEN is missing or still a placeholder",
            validate_project_config(placeholder, require_promptguard_token=True),
        )
        self.assertEqual(
            validate_project_config(configured, require_promptguard_token=True), []
        )

    def test_loader_does_not_override_process_values_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local.env"
            path.write_text("M3_TEST_CONFIG_VALUE=file\n", encoding="utf-8")
            with patch.dict(os.environ, {"M3_TEST_CONFIG_VALUE": "process"}, clear=False):
                _, values = load_project_config(path)
                self.assertEqual(values["M3_TEST_CONFIG_VALUE"], "file")
                self.assertEqual(os.environ["M3_TEST_CONFIG_VALUE"], "process")

    def test_tracked_secret_scan_reports_key_and_path_not_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            token = "hf_abcdefghijklmnopqrstuvwxyz"
            (root / "leak.txt").write_text(token, encoding="utf-8")
            subprocess.run(["git", "add", "leak.txt"], cwd=root, check=True)

            hits = tracked_secret_hits({"HF_TOKEN": token}, root=root)

            self.assertEqual(hits, [{"key": "HF_TOKEN", "path": "leak.txt"}])
            self.assertNotIn(token, repr(hits))

    def test_frontier_api_audit_blocks_placeholder_slots_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "project.local.env"
            model_registry = root / "model_registry.json"
            config_path.write_text(
                "\n".join(
                    [
                        *[f"{key}={value}" for key, value in VALID_SHARED.items()],
                        "OPENAI_API_KEY=__OPTIONAL_SET_LOCALLY__",
                        "ANTHROPIC_API_KEY=__OPTIONAL_SET_LOCALLY__",
                        "FRONTIER_OPENAI_MODEL_ID=__OPTIONAL_SET_LOCALLY__",
                        "FRONTIER_ANTHROPIC_MODEL_ID=__OPTIONAL_SET_LOCALLY__",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            model_registry.write_text('{"models": [], "summary": {}}\n', encoding="utf-8")

            audit = build_frontier_api_model_slot_audit(
                config_path=config_path,
                model_registry_path=model_registry,
                output_dir=root,
            )

        self.assertEqual(audit["status"], "blocked_missing_or_unsafe_local_config")
        self.assertFalse(audit["network_calls_performed"])
        self.assertFalse(audit["result_eligible_for_formal_tables"])
        self.assertEqual(audit["configured_vendor_count"], 0)

    def test_frontier_api_audit_redacts_configured_credentials_and_keeps_registry_gate(self) -> None:
        repo_config = Path(__file__).resolve().parents[2] / "config" / "project.local.env.frontier-test"
        openai_key = "sk-test-secret-value-never-printed"
        anthropic_key = "sk-ant-test-secret-value-never-printed"
        try:
            repo_config.write_text(
                "\n".join(
                    [
                        *[f"{key}={value}" for key, value in VALID_SHARED.items()],
                        f"OPENAI_API_KEY={openai_key}",
                        f"ANTHROPIC_API_KEY={anthropic_key}",
                        "M3_FRONTIER_API_CONSENT=yes_for_network_smoke",
                        "FRONTIER_OPENAI_MODEL_ID=openai-frontier-placeholder",
                        "FRONTIER_ANTHROPIC_MODEL_ID=anthropic-frontier-placeholder",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                model_registry = root / "model_registry.json"
                model_registry.write_text('{"models": [], "summary": {}}\n', encoding="utf-8")

                audit = build_frontier_api_model_slot_audit(
                    config_path=repo_config,
                    model_registry_path=model_registry,
                    output_dir=root,
                )

        finally:
            repo_config.unlink(missing_ok=True)

        self.assertEqual(audit["status"], "configured_pending_network_smoke")
        self.assertEqual(audit["configured_vendor_count"], 2)
        self.assertEqual(audit["frontier_api_q2_gate"], "not_satisfied_registry_slots_missing")
        self.assertFalse(audit["network_calls_performed"])
        self.assertNotIn(openai_key, repr(audit))
        self.assertNotIn(anthropic_key, repr(audit))


if __name__ == "__main__":
    unittest.main()
