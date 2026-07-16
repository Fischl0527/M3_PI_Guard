from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.context_correction_runtime import (
    EXPECTED_FREEZE_PATHS,
    execute_matrix_job,
    read_jsonl,
    reusable_job_evidence,
    semantic_failure_progress,
    write_jsonl,
)
from experiments.manifest import sha256_file


class ContextCorrectionRuntimeTests(unittest.TestCase):
    def test_freeze_allowlist_uses_only_r2_workload_artifacts(self) -> None:
        paths = set(EXPECTED_FREEZE_PATHS)
        self.assertIn(
            "protocols/context_correction_v2/calibration_r2.json", paths
        )
        self.assertIn(
            "protocols/context_correction_v2/prompt_verification_r2.json", paths
        )
        self.assertIn(
            "protocols/context_correction_v2/fixtures/e14_cases_r2.jsonl", paths
        )
        self.assertNotIn("protocols/context_correction_v2/calibration.json", paths)
        self.assertNotIn(
            "protocols/context_correction_v2/prompt_verification.json", paths
        )
        self.assertNotIn(
            "protocols/context_correction_v2/fixtures/e14_cases.jsonl", paths
        )

    def test_semantic_failure_does_not_invent_a_failed_job(self) -> None:
        progress = semantic_failure_progress(
            expected_runs=48,
            completed_runs=48,
            failed_jobs=0,
            unresolved_cases=0,
        )
        self.assertEqual(progress["failed_jobs"], 0)
        self.assertEqual(progress["semantic_status"], "fail")

    def test_preflight_fallback_is_first_step_only_and_later_missing_usage_is_rejected(self) -> None:
        job = {
            "id": "test-context-job",
            "protocol_id": "context_correction_v2",
            "job_type": "formal",
            "workload_cohort": "mixed_throughput",
            "case_ids": ["CTX-CASE-1"],
            "concurrency": 1,
            "expected_case_runs": 1,
            "target_prompt_tokens": 4096,
            "served_model": "m3-qwen3-ctx4k:latest",
            "base_model": "qwen3:4b-instruct",
            "effective_context_window_tokens": 8192,
            "outer_replicate_id": 0,
            "condition_id": "e14_v2_off",
            "prompt_profile": "normal",
            "guard_mode": "off",
        }
        common = {
            "run_key": "run-1",
            "case_id": "CTX-CASE-1",
            "model": job["served_model"],
            "model_config": {"num_ctx": None, "ollama_transport": "native"},
            "timed_out": False,
            "usage_source": "",
            "prompt_eval_count": None,
            "provider_done": True,
            "provider_attempts": 1,
        }
        lane = {
            "lane_id": 0,
            "status": "completed",
            "started_perf": 1.0,
            "completed_perf": 2.0,
            "raw_rows": [
                {
                    **common,
                    "step": 1,
                    "final_status": "running",
                    "parse_ok": True,
                },
                {
                    **common,
                    "step": 2,
                    "final_status": "completed",
                    "parse_ok": True,
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "experiments.context_correction_runtime._run_lane",
                return_value=copy.deepcopy(lane),
            ):
                record = execute_matrix_job(
                    job,
                    cases_path=Path(temp) / "unused.jsonl",
                    output_dir=temp,
                    prompt_verification={"CTX-CASE-1": 4096},
                )

            rows = read_jsonl(record["raw_path"])
            self.assertEqual(rows[0]["calibrated_prompt_eval_count"], 4096)
            self.assertEqual(
                rows[0]["prompt_count_evidence"], "frozen_one_token_preflight"
            )
            self.assertIsNone(rows[1]["calibrated_prompt_eval_count"])
            self.assertEqual(rows[1]["prompt_count_evidence"], "missing")
            self.assertFalse(reusable_job_evidence(record, job))

            rows[1].update(
                {
                    "provider_done": False,
                    "parse_ok": False,
                    "parse_error": "provider_incomplete_response",
                    "final_status": "error",
                    "guard_decision": "error",
                    "tool_execution_attempted": False,
                    "guard_latency_ms": 0.0,
                    "parsed_tool_call": {
                        "tool": "final",
                        "arguments": {
                            "answer": "PROVIDER_INCOMPLETE_RESPONSE_NOT_EXECUTED"
                        },
                    },
                    "observation": "PROVIDER_INCOMPLETE_RESPONSE_NOT_EXECUTED",
                }
            )
            write_jsonl(record["raw_path"], rows)
            record["raw_sha256"] = sha256_file(record["raw_path"])
            self.assertTrue(reusable_job_evidence(record, job))


if __name__ == "__main__":
    unittest.main()
