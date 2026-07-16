from __future__ import annotations

import unittest

from m3_guard.config import ALL_MODULES, TEXT_DETECTOR_MODULES, GuardConfig


class GuardConfigTests(unittest.TestCase):
    def test_canonical_ablation_profiles_remove_exactly_one_module(self) -> None:
        full = GuardConfig.resolve("full_guard")
        self.assertEqual(full.modules, ALL_MODULES)
        self.assertEqual(
            GuardConfig.resolve("no_dataflow").modules,
            ALL_MODULES - {"dataflow"},
        )
        self.assertEqual(
            GuardConfig.resolve("no_structured_detector").modules,
            ALL_MODULES - {"structured_detector"},
        )
        self.assertEqual(
            GuardConfig.resolve("detector_only").modules,
            TEXT_DETECTOR_MODULES,
        )
        self.assertNotIn("intent_action", GuardConfig.resolve("detector_only").modules)

    def test_thresholds_and_module_names_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            GuardConfig.resolve("full_guard", ask_threshold=0.8, deny_threshold=0.4)
        with self.assertRaises(ValueError):
            GuardConfig.resolve("full_guard", modules="policy,not_a_module")


if __name__ == "__main__":
    unittest.main()
