from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from m3_core.agent_runner import run_case
from m3_core.llm_client import CompletionResult
from m3_core.run_batch import _make_run_key
from m3_core.tool_sandbox import SANDBOX_ROOT, sandbox_seed_sha256


class _SequenceClient:
    def __init__(self, **_kwargs):
        pass

    def complete(self, _messages, *, case, step, observations):
        mode = case["test_mode"]
        if mode == "write-read":
            if step == 1:
                text = (
                    '{"tool":"write_file","arguments":'
                    '{"path":"sandbox/public/notes.txt","content":"run-one"}}'
                )
            elif step == 2:
                text = (
                    '{"tool":"read_file","arguments":'
                    '{"path":"sandbox/public/notes.txt"}}'
                )
            else:
                text = '{"tool":"final","arguments":{"answer":"done"}}'
        elif step == 1:
            text = (
                '{"tool":"read_file","arguments":'
                '{"path":"sandbox/public/notes.txt"}}'
            )
        else:
            text = '{"tool":"final","arguments":{"answer":"done"}}'
        return CompletionResult(text=text, model_latency_ms=1.0)


def _public_snapshot() -> dict[str, bytes]:
    root = SANDBOX_ROOT / "public"
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class RunSandboxIsolationTests(unittest.TestCase):
    def test_run_case_shares_one_sandbox_across_steps_and_resets_next_run(self) -> None:
        before = _public_snapshot()
        with patch("m3_core.agent_runner.LLMClient", _SequenceClient):
            first = run_case(
                {
                    "case_id": "CASE-1",
                    "sample_type": "benign",
                    "user_task": "local test",
                    "document_content": "",
                    "test_mode": "write-read",
                },
                backend="stub",
                prompt_profile="normal",
                guard_mode="off",
                generation_seed=42,
                condition_id="condition-a",
                run_key="condition-a:CASE-1:r0:s42:test",
                max_steps=3,
            )
            second = run_case(
                {
                    "case_id": "CASE-1",
                    "sample_type": "benign",
                    "user_task": "local test",
                    "document_content": "",
                    "test_mode": "read-only",
                },
                backend="stub",
                prompt_profile="normal",
                guard_mode="off",
                generation_seed=42,
                condition_id="condition-b",
                run_key="condition-b:CASE-1:r0:s42:test",
                max_steps=2,
            )

        self.assertEqual(first[1]["observation"], "run-one")
        self.assertIn("file not found", second[0]["observation"])
        self.assertEqual(
            {row["sandbox_instance_id"] for row in first},
            {first[0]["sandbox_instance_id"]},
        )
        self.assertNotEqual(
            first[0]["sandbox_instance_id"],
            second[0]["sandbox_instance_id"],
        )
        self.assertEqual(
            first[0]["sandbox_fixture_sha256"],
            second[0]["sandbox_fixture_sha256"],
        )
        self.assertEqual(
            first[0]["sandbox_seed_sha256"],
            second[0]["sandbox_seed_sha256"],
        )
        self.assertTrue(
            all(row["sandbox_reset_status"] == "fresh_cleaned" for row in first + second)
        )
        self.assertEqual(
            [row["sandbox_event"]["event_seq"] for row in first],
            [1, 2, 3],
        )
        self.assertEqual(_public_snapshot(), before)

    def test_run_key_includes_stable_sandbox_seed_identity(self) -> None:
        first = _make_run_key(
            case_id="CASE",
            condition_id="condition",
            model="model",
            replicate_id=0,
            generation_seed=42,
        )
        repeated = _make_run_key(
            case_id="CASE",
            condition_id="condition",
            model="model",
            replicate_id=0,
            generation_seed=42,
        )
        changed = _make_run_key(
            case_id="CASE",
            condition_id="condition",
            model="model",
            replicate_id=0,
            generation_seed=43,
        )
        other_experiment = _make_run_key(
            case_id="CASE",
            condition_id="condition",
            model="model",
            replicate_id=0,
            generation_seed=42,
            experiment_id="independent-job-b",
        )
        named_experiment = _make_run_key(
            case_id="CASE",
            condition_id="condition",
            model="model",
            replicate_id=0,
            generation_seed=42,
            experiment_id="independent-job-a",
        )
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, changed)
        self.assertNotEqual(named_experiment, other_experiment)
        self.assertIn(f"sb{sandbox_seed_sha256(42)[:12]}", first)


if __name__ == "__main__":
    unittest.main()
