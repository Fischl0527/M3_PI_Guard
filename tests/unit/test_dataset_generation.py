from __future__ import annotations

import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from m3_attacks.attackgen import (
    ATTACK_FAMILIES,
    EVALUATOR_ONLY_FIELDS,
    LANGUAGE_CYCLE,
    MODEL_VISIBLE_FIELDS,
    TARGET_ATTACK_COUNTS,
    TARGET_BENIGN_COUNTS,
    TARGET_BENIGN_TOOL_COUNTS,
    audit_cases,
    build_canonical_cases,
    build_stats,
    dataset_sha256,
    iter_case_files,
    load_cases,
    model_visible_payload,
)


ROOT = Path(__file__).resolve().parents[2]


class DatasetGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cases_dir = ROOT / "m3_attacks" / "cases"
        legacy = load_cases(iter_case_files(cases_dir, cases_dir / "all_cases.jsonl"))
        cls.cases = build_canonical_cases(legacy)

    def test_exact_dataset_totals_and_split_quotas(self) -> None:
        self.assertEqual(len(self.cases), 300)
        self.assertEqual(Counter(case["sample_type"] for case in self.cases), {"attack": 210, "benign": 90})
        self.assertEqual(Counter(case["split"] for case in self.cases), {"dev": 150, "validation": 60, "blind": 90})

        family_split = Counter(
            (case["split"], case["attack_family"])
            for case in self.cases
            if case["sample_type"] == "attack"
        )
        for split, targets in TARGET_ATTACK_COUNTS.items():
            for family, expected in targets.items():
                self.assertEqual(family_split[(split, family)], expected)

        benign_split = Counter(
            (case["split"], "tool" if case["requires_tool"] else "no_tool")
            for case in self.cases
            if case["sample_type"] == "benign"
        )
        for split, targets in TARGET_BENIGN_COUNTS.items():
            for kind, expected in targets.items():
                self.assertEqual(benign_split[(split, kind)], expected)

    def test_benign_authorized_tool_distribution(self) -> None:
        actual = Counter(
            (case["split"], action.partition(":")[0])
            for case in self.cases
            if case["sample_type"] == "benign"
            for action in case["authorized_actions"]
        )
        for split, targets in TARGET_BENIGN_TOOL_COUNTS.items():
            for tool, expected in targets.items():
                self.assertEqual(actual[(split, tool)], expected)

    def test_schema_accepts_every_canonical_case(self) -> None:
        schema = json.loads((ROOT / "schemas" / "attack_case.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        errors = [
            (case["case_id"], error.message)
            for case in self.cases
            for error in validator.iter_errors(case)
        ]
        self.assertEqual(errors, [])

    def test_full_audit_passes(self) -> None:
        audit = audit_cases(self.cases)
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(audit["hard_fail_count"], 0)
        self.assertEqual(audit["warnings"]["cross_split_near_duplicate"], 0)

    def test_generation_is_reproducible(self) -> None:
        cases_dir = ROOT / "m3_attacks" / "cases"
        legacy = load_cases(iter_case_files(cases_dir, cases_dir / "all_cases.jsonl"))
        rebuilt = build_canonical_cases(legacy)
        self.assertEqual(dataset_sha256(rebuilt), dataset_sha256(self.cases))
        self.assertEqual(build_stats(rebuilt)["dataset_sha256"], build_stats(self.cases)["dataset_sha256"])

    def test_template_and_mutation_ids_do_not_cross_splits(self) -> None:
        splits_by_template: dict[str, set[str]] = {}
        seen_mutations: set[tuple[str, str]] = set()
        for case in self.cases:
            splits_by_template.setdefault(case["template_id"], set()).add(case["split"])
            key = (case["template_id"], case["mutation_id"])
            self.assertNotIn(key, seen_mutations)
            seen_mutations.add(key)
        self.assertTrue(all(len(splits) == 1 for splits in splits_by_template.values()))

    def test_model_visible_payload_excludes_all_evaluator_labels(self) -> None:
        for case in self.cases:
            payload = model_visible_payload(case)
            self.assertEqual(set(payload), set(MODEL_VISIBLE_FIELDS))
            self.assertTrue(set(payload).isdisjoint(EVALUATOR_ONLY_FIELDS))

    def test_audit_detects_template_leakage_and_label_name_leakage(self) -> None:
        corrupted = copy.deepcopy(self.cases)
        source = next(case for case in corrupted if case["split"] == "validation")
        source["template_id"] = next(case["template_id"] for case in corrupted if case["split"] == "dev")
        source["user_task"] += " expected_safe_behavior"
        audit = audit_cases(corrupted)
        self.assertGreater(audit["issue_counts"]["template_cross_split"], 0)
        self.assertGreater(audit["issue_counts"]["label_field_name_leakage"], 0)

    def test_all_nine_attack_families_are_in_blind_split(self) -> None:
        blind = Counter(
            case["attack_family"]
            for case in self.cases
            if case["sample_type"] == "attack" and case["split"] == "blind"
        )
        self.assertEqual(set(blind), set(ATTACK_FAMILIES))
        self.assertTrue(all(count == 7 for count in blind.values()))

    def test_e7_and_e8_base_dimensions_are_represented(self) -> None:
        attack_languages = {
            case["language"] for case in self.cases if case["sample_type"] == "attack"
        }
        self.assertTrue(set(LANGUAGE_CYCLE).issubset(attack_languages))

        obfuscation_modes = {
            case["attack_dimensions"].get("obfuscation_type")
            for case in self.cases
            if case["attack_family"] == "obfuscation_evasion"
        }
        self.assertTrue(
            {"base64", "zero_width", "unicode_escape", "character_split", "homoglyph"}.issubset(
                obfuscation_modes
            )
        )
        structured_carriers = {
            case["carrier"]
            for case in self.cases
            if case["attack_family"] == "json_rpc"
        }
        self.assertTrue(
            {"json_data_field", "yaml_structured_input", "xml_structured_input"}.issubset(
                structured_carriers
            )
        )


if __name__ == "__main__":
    unittest.main()
