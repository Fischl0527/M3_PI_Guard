from __future__ import annotations

import unittest

from m3_eval.metrics import build_summary_rows, compute_metrics


class MetricConditionIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = {
            "case_id": "A-1",
            "template_id": "T-1",
            "sample_type": "attack",
            "attack_family": "direct_jailbreak",
            "unsafe_target_actions": ["run_code:mock_only"],
            "authorized_actions": [],
            "requires_tool": False,
            "risk_tags": ["code_execution"],
        }

    @staticmethod
    def _row(condition_id: str, modules: list[str]) -> dict:
        return {
            "experiment_id": "E4",
            "condition_id": condition_id,
            "guard_modules": modules,
            "model": "stub",
            "prompt_profile": "normal",
            "guard_mode": "full_guard",
            "defense_mode": "full_guard",
            "case_id": "A-1",
            "replicate_id": 0,
            "seed": 42,
            "run_id": "shared-run-id",
            "step": 1,
            "parsed_tool_call": {"tool": "run_code", "arguments": {"code": "mock_only"}},
            "guard_decision": "deny",
            "final_status": "blocked",
            "parse_ok": True,
        }

    def test_module_overrides_are_distinct_case_runs(self) -> None:
        logs = [
            self._row("solo_policy", ["policy"]),
            self._row("solo_dataflow", ["dataflow"]),
        ]
        metrics = compute_metrics(logs, [self.case], strict_labels=True, include_missing=False)
        self.assertEqual(metrics["case_runs"], 2)
        self.assertEqual(metrics["duplicate_logical_runs"], 0)

        rows = build_summary_rows({"combined.jsonl": logs}, [self.case], strict_labels=True)
        condition_groups = {
            row["group"] for row in rows if row["scope"] == "condition_id"
        }
        self.assertEqual(condition_groups, {"solo_policy", "solo_dataflow"})


if __name__ == "__main__":
    unittest.main()
