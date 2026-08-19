from __future__ import annotations

import unittest

from experiments.paper_v2.provider_safety import (
    ProviderSafetyError,
    build_safety_receipt,
    load_safety_policy,
    validate_provider_endpoint,
    validate_safety_receipt,
    validate_tool_effect,
)


class PaperV2ProviderSafetyTests(unittest.TestCase):
    def test_policy_is_fail_closed(self) -> None:
        policy = load_safety_policy()
        self.assertFalse(policy["enforcement"]["external_connectors_enabled"])
        self.assertFalse(
            policy["enforcement"]["provider_managed_tools_enabled"]
        )
        self.assertEqual(
            policy["enforcement"]["unsafe_or_unknown_effect"], "DENY"
        )

    def test_official_deepseek_and_gemini_inference_paths_pass(self) -> None:
        validate_provider_endpoint(
            "deepseek", "https://api.deepseek.com/chat/completions"
        )
        validate_provider_endpoint(
            "gemini",
            "https://generativelanguage.googleapis.com/"
            "v1beta/openai/chat/completions",
        )

    def test_relay_and_provider_managed_paths_fail(self) -> None:
        with self.assertRaises(ProviderSafetyError):
            validate_provider_endpoint(
                "deepseek", "https://relay.example.test/chat/completions"
            )
        with self.assertRaises(ProviderSafetyError):
            validate_provider_endpoint(
                "gemini",
                "https://generativelanguage.googleapis.com/v1beta/models",
            )

    def test_m3_effects_are_limited_to_synthetic_targets(self) -> None:
        validate_tool_effect(
            effect_backend="m3_sandbox_fixture",
            tool="write_file",
            arguments={"path": "sandbox/public/result.txt", "content": "fixture"},
        )
        validate_tool_effect(
            effect_backend="m3_sandbox_fixture",
            tool="send_email",
            arguments={"to": "recipient@example.test"},
        )
        validate_tool_effect(
            effect_backend="m3_sandbox_fixture",
            tool="call_api",
            arguments={"endpoint": "/mock/calendar"},
        )
        for tool, arguments in (
            ("write_file", {"path": "C:/Users/user/private.txt"}),
            ("send_email", {"to": "real-user@example.com"}),
            ("call_api", {"endpoint": "https://bank.example/pay"}),
            ("run_code", {"code": "echo unsafe"}),
        ):
            with self.subTest(tool=tool), self.assertRaises(
                ProviderSafetyError
            ):
                validate_tool_effect(
                    effect_backend="m3_sandbox_fixture",
                    tool=tool,
                    arguments=arguments,
                )

    def test_agentdojo_is_allowed_only_as_connector_free_memory_copy(self) -> None:
        validate_tool_effect(
            effect_backend="agentdojo_in_memory_copy",
            tool="send_money",
            arguments={"recipient": "fixture", "amount": 1},
        )
        with self.assertRaises(ProviderSafetyError):
            validate_tool_effect(
                effect_backend="agentdojo_in_memory_copy",
                tool="send_money",
                arguments={"recipient": "fixture", "amount": 1},
                external_connectors_enabled=True,
            )

    def test_receipt_contains_hashes_not_argument_values(self) -> None:
        receipt = build_safety_receipt(
            provider_id="deepseek",
            endpoint_url="https://api.deepseek.com/chat/completions",
            effect_backend="m3_sandbox_fixture",
            tool="write_file",
            arguments={
                "path": "sandbox/public/result.txt",
                "content": "sensitive fixture content",
            },
        )
        validate_safety_receipt(receipt)
        self.assertNotIn("sensitive fixture content", repr(receipt))
        self.assertFalse(receipt["credentials_stored"])


if __name__ == "__main__":
    unittest.main()
