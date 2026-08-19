from __future__ import annotations

import unittest
import warnings

from m3_core.agent_runner import extract_tool_call


class ToolArgumentNormalizationTests(unittest.TestCase):
    def test_invalid_escape_does_not_emit_syntax_warning(self) -> None:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = extract_tool_call(r"{'tool':'final','arguments':{'answer':'bad\_escape'}}")
        self.assertTrue(result["parse_ok"])
        self.assertFalse(any(item.category is SyntaxWarning for item in captured))

    def test_markdown_escaped_tool_and_sandbox_path_are_repaired(self) -> None:
        result = extract_tool_call(
            r'{"tool":"read\_file","arguments":{"path":"/sandbox/public/clean\_report.md"}}'
        )
        self.assertTrue(result["parse_ok"])
        self.assertEqual(
            result["tool_call"],
            {"tool": "read_file", "arguments": {"path": "sandbox/public/clean_report.md"}},
        )

    def test_local_secret_alias_is_kept_inside_mock_sandbox(self) -> None:
        result = extract_tool_call(
            r'{"tool":"read_file","arguments":{"path":"/secrets/api_key.txt"}}'
        )
        self.assertTrue(result["parse_ok"])
        self.assertEqual(result["tool_call"]["arguments"]["path"], "sandbox/secrets/api_key.txt")

    def test_unescaped_nested_json_is_recovered_only_as_final_text(self) -> None:
        result = extract_tool_call(
            '{"tool":"final","arguments":{"answer":"'
            '{"review_state":"pending"}'
            '"}}'
        )
        self.assertTrue(result["parse_ok"])
        self.assertEqual(
            result["tool_call"],
            {"tool": "final", "arguments": {"answer": '{"review_state":"pending"}'}},
        )

    def test_read_file_alias_is_canonicalized(self) -> None:
        result = extract_tool_call(
            '{"tool":"read_file","arguments":{"file":"sandbox/public/report.md"}}'
        )
        self.assertTrue(result["parse_ok"])
        self.assertEqual(
            result["tool_call"],
            {"tool": "read_file", "arguments": {"path": "sandbox/public/report.md"}},
        )

    def test_email_aliases_are_canonicalized_and_unknown_context_is_kept(self) -> None:
        result = extract_tool_call(
            '{"tool":"send_email","arguments":'
            '{"recipient":"user@example.test","title":"Hi","content":"Body","trace":"x"}}'
        )
        self.assertEqual(
            result["tool_call"]["arguments"],
            {
                "to": "user@example.test",
                "subject": "Hi",
                "body": "Body",
                "trace": "x",
            },
        )

    def test_canonical_value_wins_over_alias(self) -> None:
        result = extract_tool_call(
            '{"tool":"write_file","arguments":'
            '{"path":"sandbox/public/a.txt","file":"sandbox/public/b.txt",'
            '"content":"safe","text":"ignored"}}'
        )
        self.assertEqual(
            result["tool_call"]["arguments"],
            {"path": "sandbox/public/a.txt", "content": "safe"},
        )

if __name__ == "__main__":
    unittest.main()
