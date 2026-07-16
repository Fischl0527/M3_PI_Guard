from __future__ import annotations

import unittest

from m3_eval.statistics import (
    clustered_paired_bootstrap,
    holm_adjust,
    latency_summary,
    mcnemar_exact,
    percentile,
    wilcoxon_signed_rank,
    wilson_interval,
)


class StatisticsTests(unittest.TestCase):
    def test_wilson_zero_of_eight_is_not_zero_width(self) -> None:
        low, high = wilson_interval(0, 8)
        self.assertAlmostEqual(low or 0.0, 0.0, places=7)
        self.assertAlmostEqual(high or 0.0, 0.3244076, places=6)

    def test_wilson_zero_denominator_is_undefined(self) -> None:
        self.assertEqual(wilson_interval(0, 0), (None, None))

    def test_mcnemar_exact_known_discordance(self) -> None:
        result = mcnemar_exact(baseline_only_success=4, treatment_only_success=0)
        self.assertEqual(result["discordant_pairs"], 4)
        self.assertAlmostEqual(result["p_value"], 0.125)

    def test_mcnemar_requires_paired_lengths(self) -> None:
        with self.assertRaises(ValueError):
            mcnemar_exact([True], [False, True])

    def test_clustered_bootstrap_is_deterministic_and_paired(self) -> None:
        pairs = [
            ("template-a", 1.0, 0.0),
            ("template-a", 1.0, 0.0),
            ("template-b", 0.0, 0.0),
        ]
        first = clustered_paired_bootstrap(pairs, iterations=10_000, seed=17)
        second = clustered_paired_bootstrap(pairs, iterations=10_000, seed=17)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["estimate"], -2.0 / 3.0)
        self.assertLessEqual(first["ci_low"], first["estimate"])
        self.assertGreaterEqual(first["ci_high"], first["estimate"])

    def test_wilcoxon_exact_and_effect_direction(self) -> None:
        result = wilcoxon_signed_rank([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
        self.assertEqual(result["method"], "wilcoxon_signed_rank_exact")
        self.assertAlmostEqual(result["p_value"], 0.25)
        self.assertAlmostEqual(result["rank_biserial"], 1.0)
        self.assertAlmostEqual(result["median_difference"], 1.0)

        tied_large = wilcoxon_signed_rank(
            [0.0] * 21,
            [1.0] * 11 + [-1.0] * 10,
        )
        self.assertEqual(tied_large["method"], "wilcoxon_signed_rank_normal")
        self.assertGreaterEqual(tied_large["p_value"], 0.0)
        self.assertLessEqual(tied_large["p_value"], 1.0)

    def test_holm_adjust_preserves_original_order(self) -> None:
        adjusted = holm_adjust([0.01, 0.04, 0.03])
        self.assertEqual([round(value, 6) for value in adjusted], [0.03, 0.06, 0.06])

    def test_latency_summary_and_percentile(self) -> None:
        result = latency_summary([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(result["p50"], 2.5)
        self.assertAlmostEqual(result["p95"], 3.85)
        self.assertAlmostEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.95) or 0.0, 3.85)
        with self.assertRaises(ValueError):
            latency_summary([1.0, -0.1])


if __name__ == "__main__":
    unittest.main()
