from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from experiments.paper_v1.benchmarks.promptguard_adapter import (
    PromptGuardConfig,
    build_promptguard_preflight,
    normalize_promptguard_label,
)
from experiments.paper_v1.benchmarks.promptguard_real_smoke import (
    binary_label_mapping,
    smoke_cases,
    summarize_predictions,
)


class PromptGuardRealSmokeTests(unittest.TestCase):
    def test_generic_binary_labels_are_not_inverted(self) -> None:
        malicious_score, label = normalize_promptguard_label(
            {"label": "LABEL_0", "score": 0.97}
        )
        self.assertEqual(label, "label_0")
        self.assertAlmostEqual(malicious_score, 0.03)

        malicious_score, label = normalize_promptguard_label(
            {"label": "LABEL_1", "score": 0.91}
        )
        self.assertEqual(label, "label_1")
        self.assertAlmostEqual(malicious_score, 0.91)

    def test_unknown_binary_label_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_promptguard_label({"label": "mystery", "score": 0.9})

    def test_binary_mapping_accepts_model_card_and_generic_labels(self) -> None:
        self.assertEqual(
            binary_label_mapping({0: "BENIGN", 1: "MALICIOUS"}),
            {0: "BENIGN", 1: "MALICIOUS"},
        )
        self.assertEqual(
            binary_label_mapping({0: "LABEL_0", 1: "LABEL_1"}),
            {0: "BENIGN", 1: "MALICIOUS"},
        )

    def test_smoke_case_set_covers_required_dimensions(self) -> None:
        cases = smoke_cases()
        self.assertEqual(len(cases), 12)
        self.assertEqual(len({row["case_id"] for row in cases}), len(cases))
        self.assertEqual({row["sample_type"] for row in cases}, {"benign", "malicious"})
        self.assertTrue({"en", "zh", "mixed"}.issubset({row["language"] for row in cases}))
        self.assertTrue(
            {
                "direct_injection",
                "indirect_injection",
                "base64_evasion",
                "character_split_evasion",
                "zero_width_evasion",
                "structured_hiding",
            }.issubset({row["category"] for row in cases})
        )

    def test_summary_keeps_diagnostic_misses_visible(self) -> None:
        rows = []
        for index, case in enumerate(smoke_cases()):
            expected = case["sample_type"]
            decision = "benign" if index == 3 else expected
            probability = 0.9 if decision == "malicious" else 0.1
            rows.append(
                {
                    **case,
                    "benign_probability": 1.0 - probability,
                    "malicious_probability": probability,
                    "threshold_decision": decision,
                    "latency_ms": 1.0 + index,
                }
            )

        summary = summarize_predictions(rows, threshold=0.5)

        self.assertTrue(summary["runtime_checks_passed"])
        self.assertEqual(summary["malicious_miss_count"], 1)
        self.assertEqual(summary["missed_malicious_case_ids"], [rows[3]["case_id"]])
        self.assertEqual(summary["exact_match_count"], len(rows) - 1)

    def test_preflight_admits_matching_real_smoke_as_qualification_only(self) -> None:
        registry = (
            Path(__file__).resolve().parents[2]
            / "protocols"
            / "paper_upgrade_v1"
            / "external_strong_baselines_v1.json"
        )
        config = PromptGuardConfig()
        with tempfile.TemporaryDirectory() as tmp:
            smoke_path = Path(tmp) / "smoke.json"
            smoke_path.write_text(
                json.dumps(
                    {
                        "status": "completed_real_model_smoke",
                        "real_model_loaded": True,
                        "stub_used": False,
                        "result_eligible_for_formal_tables": False,
                        "model": {
                            "model_id": config.model_id,
                            "revision": config.revision,
                        },
                        "summary": {
                            "case_count": 12,
                            "diagnostic_exact_match_rate": 0.75,
                            "runtime_checks_passed": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "experiments.paper_v1.benchmarks.promptguard_adapter.dependency_probe",
                return_value={
                    "transformers_installed": True,
                    "torch_installed": True,
                    "model_cache_complete": True,
                    "expected_revision_complete": True,
                },
            ):
                manifest = build_promptguard_preflight(
                    registry_path=registry,
                    output_dir=Path(tmp) / "preflight",
                    config=config,
                    real_smoke_manifest_path=smoke_path,
                )

        self.assertEqual(
            manifest["status"],
            "real_detector_smoke_completed_formal_run_pending",
        )
        self.assertTrue(manifest["real_detector_smoke"]["completed"])
        self.assertFalse(manifest["result_eligible_for_formal_tables"])


if __name__ == "__main__":
    unittest.main()
