from __future__ import annotations

import unittest

from experiments.acceptance_remediation_analysis_patch import (
    adapt_legal_result,
    normalize_figure_manifest_anchor,
)


class AcceptanceRemediationAnalysisPatchTests(unittest.TestCase):
    def test_value_alias_preserves_all_formal_fields(self) -> None:
        source = {
            "numerator": 166,
            "denominator": 168,
            "value": 166 / 168,
            "ci_low": 0.95,
            "ci_high": 0.99,
            "confidence": 0.95,
        }
        result = adapt_legal_result(source)
        self.assertEqual(result["estimate"], source["value"])
        for key, value in source.items():
            self.assertEqual(result[key], value)
        self.assertNotIn("estimate", source)

    def test_figure_manifest_anchor_adds_only_required_kind(self) -> None:
        source = {
            "status": "completed",
            "artifacts": [
                {"path": "metrics.csv", "bytes": 10, "sha256": "a"},
                {"path": "figure_manifest.json", "bytes": 20, "sha256": "b"},
            ],
        }
        result = normalize_figure_manifest_anchor(source)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["artifacts"][0], source["artifacts"][0])
        self.assertEqual(result["artifacts"][1]["kind"], "figure_manifest")
        for key, value in source["artifacts"][1].items():
            self.assertEqual(result["artifacts"][1][key], value)
        self.assertNotIn("kind", source["artifacts"][1])


if __name__ == "__main__":
    unittest.main()
