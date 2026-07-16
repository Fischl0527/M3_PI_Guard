from __future__ import annotations

import unittest

from experiments.e9_context_correction import (
    DEFAULT_FREEZE,
    DEFAULT_SMOKE_OUTPUT,
    _validate,
    build_plan,
    load_cases,
)


class E9ContextCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()

    def _rows(self):
        plan = build_plan(self.cases, phase="formal")
        rows = []
        for job in plan["jobs"]:
            for case_id in job["case_ids"]:
                target = int(job["target_prompt_tokens"])
                rows.append(
                    {
                        "run_key": f"{case_id}|{job['condition_id']}",
                        "case_id": case_id,
                        "step": 1,
                        "seed": 419,
                        "condition_id": job["condition_id"],
                        "model": job["served_model"],
                        "served_model": job["served_model"],
                        "target_prompt_tokens": target,
                        "prompt_eval_count": target,
                        "usage_source": "ollama_native_prompt_eval_count",
                        "model_config": {"num_ctx": None},
                        "timed_out": False,
                        "final_status": "completed",
                        "parse_ok": True,
                        "finish_reason": "stop",
                    }
                )
        return plan, rows

    def test_plan_has_exact_smoke_and_formal_denominators(self) -> None:
        formal = build_plan(self.cases, phase="formal")
        smoke = build_plan(self.cases, phase="smoke")
        self.assertEqual(formal["expected_case_runs"], 120)
        self.assertEqual(smoke["expected_case_runs"], 48)
        self.assertEqual(len(formal["jobs"]), 8)
        self.assertTrue(all(job["concurrency"] == 1 for job in formal["jobs"]))
        self.assertTrue(all(job["served_model"].startswith("m3-qwen3") for job in formal["jobs"]))
        self.assertEqual(formal["workload_revision"], "r2")
        self.assertIn("r3", DEFAULT_SMOKE_OUTPUT.name)
        self.assertEqual(DEFAULT_FREEZE.name, "freeze_r3.json")

    def test_every_run_semantic_gate_passes_exact_fixture(self) -> None:
        plan, rows = self._rows()
        validity = _validate(plan, self.cases, rows)
        self.assertEqual(validity["status"], "pass")
        self.assertTrue(all(validity["checks"].values()))

    def test_one_out_of_tolerance_run_fails_even_when_cell_median_can_pass(self) -> None:
        plan, rows = self._rows()
        rows[0]["prompt_eval_count"] = 100
        validity = _validate(plan, self.cases, rows)
        self.assertEqual(validity["status"], "fail")
        self.assertFalse(validity["checks"]["every_run_within_target_tolerance"])

    def test_dynamic_num_ctx_or_non_native_usage_fails(self) -> None:
        plan, rows = self._rows()
        rows[0]["model_config"]["num_ctx"] = 2048
        rows[1]["usage_source"] = "openai_compat_usage"
        validity = _validate(plan, self.cases, rows)
        self.assertFalse(validity["checks"]["dynamic_num_ctx_absent"])
        self.assertFalse(validity["checks"]["native_usage_every_step"])


if __name__ == "__main__":
    unittest.main()
