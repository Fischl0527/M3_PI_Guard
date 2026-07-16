from __future__ import annotations

import base64
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from experiments.derived_cases import (
    CONTEXT_LENGTHS,
    DEFAULT_CANONICAL_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SMOKE_PATH,
    E8_ENCODINGS,
    EXPECTED_COUNTS,
    INJECTION_POSITIONS,
    LANGUAGE_BUCKETS,
    MULTI_TURN_MODES,
    TURN_COUNTS,
    build_audit,
    canonical_jsonl_bytes,
    derive_smoke,
    expected_files,
    generate_all,
    load_jsonl,
    rows_sha256,
)


class DerivedCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = load_jsonl(DEFAULT_CANONICAL_PATH)
        cls.datasets = generate_all(cls.canonical)
        cls.smoke = derive_smoke(cls.canonical)
        cls.audit = build_audit(cls.canonical, cls.datasets, cls.smoke)
        cls.parent_by_id = {row["case_id"]: row for row in cls.canonical}

    def test_exact_counts_and_parent_child_contract(self) -> None:
        self.assertEqual(
            {key: len(value) for key, value in self.datasets.items()}, EXPECTED_COUNTS
        )
        all_rows = [row for rows in self.datasets.values() for row in rows]
        all_rows.extend(self.smoke)
        self.assertEqual(len({row["case_id"] for row in all_rows}), len(all_rows))
        for row in all_rows:
            self.assertIn(row["parent_case_id"], self.parent_by_id)
            self.assertNotEqual(row["case_id"], row["parent_case_id"])
            self.assertEqual(
                row["attack_dimensions"]["canonical_parent_case_id"],
                row["parent_case_id"],
            )
            self.assertEqual(row["derived_generator_version"], "derived-cases-v1.0")

    def test_e7_is_complete_validation_language_selection(self) -> None:
        e7 = self.datasets["E7"]
        validation_ids = {
            row["case_id"] for row in self.canonical if row["split"] == "validation"
        }
        self.assertEqual({row["parent_case_id"] for row in e7}, validation_ids)
        self.assertEqual({row["variant_id"] for row in e7}, set(LANGUAGE_BUCKETS))
        self.assertEqual(len(e7), 60)

    def test_e8_five_parent_nine_encoding_grid_and_reversible_controls(self) -> None:
        e8 = self.datasets["E8"]
        parent_ids = {row["parent_case_id"] for row in e8}
        self.assertEqual(len(parent_ids), 5)
        self.assertEqual({row["variant_id"] for row in e8}, set(E8_ENCODINGS))
        self.assertEqual(
            len({(row["parent_case_id"], row["variant_id"]) for row in e8}), 45
        )

        for parent_id in parent_ids:
            rows = {row["variant_id"]: row for row in e8 if row["parent_case_id"] == parent_id}
            raw = rows["base64"]["injected_content"]
            encoded = rows["base64"]["document_content"].splitlines()[-1]
            self.assertEqual(base64.b64decode(encoded).decode("utf-8"), raw)
            json_payload = json.loads(rows["json"]["document_content"].splitlines()[-1])
            self.assertEqual(json_payload["assistant_next"], raw)
            self.assertIn("\u200b", rows["zero_width"]["document_content"])
            self.assertIn("<!-- assistant-next:", rows["markdown_hidden"]["document_content"])
            self.assertIn("\\u8bf7", rows["unicode_escape"]["document_content"])

    def test_e9_exact_context_and_position_grid(self) -> None:
        e9 = self.datasets["E9"]
        parent_ids = {row["parent_case_id"] for row in e9}
        grid = {
            (
                row["parent_case_id"],
                row["attack_dimensions"]["context_tokens"],
                row["attack_dimensions"]["injection_position_pct"],
            )
            for row in e9
        }
        self.assertEqual(len(parent_ids), 3)
        self.assertEqual(
            grid,
            {
                (parent_id, context, position)
                for parent_id in parent_ids
                for context in CONTEXT_LENGTHS
                for position in INJECTION_POSITIONS
            },
        )
        for row in e9:
            dimensions = row["attack_dimensions"]
            self.assertEqual(
                len(row["document_content"].split()), dimensions["context_tokens"]
            )
            self.assertEqual(
                dimensions["actual_whitespace_tokens"], dimensions["context_tokens"]
            )
            self.assertIn("<UNTRUSTED_BLOCK>", row["document_content"])

    def test_e10_exact_turn_grid_and_conversation_lengths(self) -> None:
        e10 = self.datasets["E10"]
        parent_ids = {row["parent_case_id"] for row in e10}
        grid = {
            (
                row["parent_case_id"],
                row["attack_dimensions"]["turn_count"],
                row["attack_dimensions"]["multi_turn_mode"],
            )
            for row in e10
        }
        self.assertEqual(
            grid,
            {
                (parent_id, turn_count, mode)
                for parent_id in parent_ids
                for turn_count in TURN_COUNTS
                for mode in MULTI_TURN_MODES
            },
        )
        for row in e10:
            turns = row["conversation_turns"]
            declared = row["attack_dimensions"]["turn_count"]
            self.assertEqual(len(turns), declared)
            self.assertEqual([turn["turn_index"] for turn in turns], list(range(1, declared + 1)))
            self.assertTrue(all(turn["trust"] in {"trusted", "untrusted", "tool_output"} for turn in turns))

    def test_e11_and_e15_stratification(self) -> None:
        e11 = self.datasets["E11"]
        self.assertEqual(len(e11), 22)
        self.assertTrue(all(row["attack_family"] == "cross_tool_attack_chain" for row in e11))
        self.assertTrue(all(row["attack_dimensions"]["chain_length"] == 2 for row in e11))
        self.assertEqual(
            len({row["attack_dimensions"]["chain_pattern"] for row in e11}), 4
        )

        e15 = self.datasets["E15"]
        self.assertEqual(Counter(row["sample_type"] for row in e15), {"attack": 20, "benign": 10})
        self.assertEqual(
            len({row["attack_family"] for row in e15 if row["sample_type"] == "attack"}),
            9,
        )
        benign = [row for row in e15 if row["sample_type"] == "benign"]
        self.assertEqual(sum(bool(row["requires_tool"]) for row in benign), 5)
        self.assertEqual(sum(not bool(row["requires_tool"]) for row in benign), 5)

    def test_smoke_is_fixed_six_case_shared_gate(self) -> None:
        self.assertEqual(len(self.smoke), 6)
        self.assertEqual(Counter(row["sample_type"] for row in self.smoke), {"attack": 4, "benign": 2})
        self.assertTrue(
            any(
                row["sample_type"] == "benign"
                and row["requires_tool"]
                and row["authorized_actions"]
                for row in self.smoke
            )
        )
        families = {row["attack_family"] for row in self.smoke}
        self.assertIn("cross_tool_attack_chain", families)
        self.assertIn("multilingual_t2l", families)
        self.assertEqual(
            DEFAULT_SMOKE_PATH.read_bytes(), canonical_jsonl_bytes(self.smoke)
        )

    def test_security_audit_rejects_live_endpoints_and_credentials(self) -> None:
        self.assertEqual(self.audit["status"], "pass")
        self.assertEqual(self.audit["security_issues"], [])
        self.assertTrue(all(self.audit["checks"].values()))

        corrupted = json.loads(json.dumps(self.datasets, ensure_ascii=False))
        corrupted["E8"][0]["document_content"] += " https://live.example.com/collect"
        corrupted["E8"][1]["unsafe_target_actions"] = ["read_file:C:/private.txt"]
        audit = build_audit(self.canonical, corrupted, self.smoke)
        self.assertEqual(audit["status"], "review_required")
        self.assertFalse(audit["checks"]["no_live_endpoint_or_credential_material"])
        self.assertEqual(
            {issue["kind"] for issue in audit["security_issues"]},
            {"live_url", "nonlocal_action_target"},
        )

    def test_generation_and_committed_hashes_are_byte_reproducible(self) -> None:
        rebuilt = generate_all(load_jsonl(DEFAULT_CANONICAL_PATH))
        rebuilt_smoke = derive_smoke(load_jsonl(DEFAULT_CANONICAL_PATH))
        rebuilt_audit = build_audit(self.canonical, rebuilt, rebuilt_smoke)
        self.assertEqual(rebuilt, self.datasets)
        self.assertEqual(rebuilt_audit, self.audit)

        files = expected_files(self.datasets, self.audit)
        for filename, expected in files.items():
            self.assertEqual((DEFAULT_OUTPUT_DIR / filename).read_bytes(), expected)

        audit_core = dict(self.audit)
        recorded_audit_hash = audit_core.pop("audit_sha256")
        core_bytes = (
            json.dumps(audit_core, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        self.assertEqual(hashlib.sha256(core_bytes).hexdigest(), recorded_audit_hash)
        self.assertEqual(
            rows_sha256(self.datasets["E9"]), self.audit["dataset_sha256"]["E9"]
        )


if __name__ == "__main__":
    unittest.main()
