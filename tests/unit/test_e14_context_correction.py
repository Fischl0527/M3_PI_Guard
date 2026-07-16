from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.context_correction_runtime import max_interval_overlap
from experiments.e14_context_correction import (
    DEFAULT_FREEZE,
    DEFAULT_SMOKE_OUTPUT,
    _matched_path_check,
    _statistics_payload,
    _validate,
    build_plan,
    load_cases,
)


class E14ContextCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()

    def test_plan_preserves_exact_corrected_denominators(self) -> None:
        plan = build_plan(self.cases, phase="formal")
        self.assertEqual(plan["warmup_job_count"], 8)
        self.assertEqual(plan["formal_job_count"], 96)
        self.assertEqual(plan["expected_warmup_case_runs"], 48)
        self.assertEqual(plan["expected_matched_benign_case_runs"], 288)
        self.assertEqual(plan["expected_mixed_throughput_case_runs"], 144)
        self.assertEqual(plan["expected_formal_case_runs"], 432)
        self.assertEqual(
            {job["concurrency"] for job in plan["jobs"] if job["job_type"] == "formal"},
            {1, 2, 4},
        )
        self.assertTrue(all("num_ctx" not in job for job in plan["jobs"]))
        self.assertEqual(plan["workload_revision"], "r2")
        self.assertTrue(all(job["workload_revision"] == "r2" for job in plan["jobs"]))
        self.assertIn("r3", DEFAULT_SMOKE_OUTPUT.name)
        self.assertEqual(DEFAULT_FREEZE.name, "freeze_r3.json")

    def test_smoke_is_four_matched_plus_two_mixed_per_alias_and_condition(self) -> None:
        plan = build_plan(self.cases, phase="smoke")
        self.assertEqual(len(plan["jobs"]), 8)
        self.assertEqual(plan["expected_formal_case_runs"], 48)
        self.assertTrue(all(job["expected_case_runs"] == 6 for job in plan["jobs"]))

    def test_statistics_payload_carries_formal_correction_identity(self) -> None:
        payload = _statistics_payload(self.cases, [], [])
        self.assertEqual(payload["protocol_id"], "CONTEXT_CORRECTION_V2")
        self.assertEqual(payload["workload_revision"], "r2")
        self.assertEqual(payload["evidence_tier"], "formal_context_correction_v2")
        self.assertIs(payload["formal_model_only"], True)

    def test_smoke_matched_path_gate_requires_exactly_sixteen_complete_pairs(self) -> None:
        plan = build_plan(self.cases, phase="smoke")
        eligible = {
            str(case["case_id"])
            for case in self.cases
            if bool(case.get("latency_overhead_eligible"))
        }
        rows = []
        for job in plan["jobs"]:
            for case_id in job["case_ids"]:
                if case_id not in eligible:
                    continue
                raw = json.dumps(
                    {"tool": "final", "arguments": {"answer": f"ok:{case_id}"}},
                    sort_keys=True,
                )
                rows.append(
                    {
                        "run_key": f"{job['id']}|{case_id}",
                        "case_id": case_id,
                        "step": 1,
                        "condition_id": job["condition_id"],
                        "target_prompt_tokens": job["target_prompt_tokens"],
                        "offered_concurrency": job["concurrency"],
                        "outer_replicate_id": job["outer_replicate_id"],
                        "correction_job_id": job["id"],
                        "parse_ok": True,
                        "parsed_tool_call": {
                            "tool": "final",
                            "arguments": {"answer": f"ok:{case_id}"},
                        },
                        "raw_model_output": raw,
                        "guard_decision": (
                            "allow"
                            if job["condition_id"] == "e14_v2_full_guard"
                            else "not_applicable"
                        ),
                        "final_status": "completed",
                    }
                )

        matched = _matched_path_check(rows, plan, self.cases)
        self.assertEqual(matched["status"], "pass")
        self.assertEqual(matched["expected_pairs"], 16)
        self.assertEqual(matched["observed_pairs"], 16)
        self.assertEqual(matched["valid_pairs"], 16)

        missing_one_condition = rows[:-1]
        failed = _matched_path_check(missing_one_condition, plan, self.cases)
        self.assertEqual(failed["status"], "fail")
        self.assertEqual(failed["expected_pairs"], 16)

    def test_interval_overlap_reports_client_offered_concurrency(self) -> None:
        self.assertEqual(max_interval_overlap([(0.0, 3.0), (1.0, 2.0), (1.5, 4.0)]), 3)
        self.assertEqual(max_interval_overlap([(0.0, 1.0), (1.1, 2.0)]), 1)

    def _synthetic(self, root: Path):
        plan = build_plan(self.cases, phase="formal")
        rows = []
        records = []
        for job in plan["jobs"]:
            telemetry_path = root / f"{job['id']}.jsonl"
            telemetry_path.write_text(
                json.dumps(
                    {
                        "gpu": {"available": True, "memory_used_mib": 2048},
                        "ollama_ps": {
                            "models": [
                                {
                                    "name": job["served_model"],
                                    "context_length": job["effective_context_window_tokens"],
                                }
                            ]
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            records.append(
                {
                    **job,
                    "status": "completed",
                    "telemetry_path": str(telemetry_path),
                    "observed_max_inflight": job["concurrency"],
                }
            )
            for case_id in job["case_ids"]:
                raw = json.dumps(
                    {"tool": "final", "arguments": {"answer": f"ok:{case_id}"}},
                    sort_keys=True,
                )
                rows.append(
                    {
                        "run_key": f"{job['id']}|{case_id}",
                        "case_id": case_id,
                        "step": 1,
                        "seed": 419 + int(job["outer_replicate_id"]),
                        "condition_id": job["condition_id"],
                        "model": job["served_model"],
                        "served_model": job["served_model"],
                        "target_prompt_tokens": job["target_prompt_tokens"],
                        "prompt_eval_count": job["target_prompt_tokens"],
                        "usage_source": "ollama_native_prompt_eval_count",
                        "model_config": {"num_ctx": None},
                        "timed_out": False,
                        "final_status": "completed",
                        "parse_ok": True,
                        "parsed_tool_call": {
                            "tool": "final",
                            "arguments": {"answer": f"ok:{case_id}"},
                        },
                        "raw_model_output": raw,
                        "guard_decision": (
                            "allow" if job["guard_mode"] == "full_guard" else "not_applicable"
                        ),
                        "correction_job_id": job["id"],
                        "correction_job_type": job["job_type"],
                        "workload_cohort": job["workload_cohort"],
                        "effective_context_window_tokens": job[
                            "effective_context_window_tokens"
                        ],
                        "offered_concurrency": job["concurrency"],
                        "outer_replicate_id": job["outer_replicate_id"],
                        "finish_reason": "stop",
                    }
                )
        return plan, rows, records

    def test_semantic_gate_passes_exact_synthetic_matrix_and_matched_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan, rows, records = self._synthetic(Path(temp))
            matched = _matched_path_check(rows, plan)
            self.assertEqual(matched["status"], "pass")
            self.assertEqual(matched["valid_pairs"], 144)
            validity = _validate(plan, self.cases, rows, records)
            self.assertEqual(validity["status"], "pass")
            self.assertTrue(all(validity["checks"].values()))

    def test_flat_or_outlier_prompt_workload_fails_semantic_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan, rows, records = self._synthetic(Path(temp))
            rows[0]["prompt_eval_count"] = 20
            validity = _validate(plan, self.cases, rows, records)
            self.assertEqual(validity["status"], "fail")
            self.assertFalse(validity["checks"]["every_run_within_target_tolerance"])


if __name__ == "__main__":
    unittest.main()
