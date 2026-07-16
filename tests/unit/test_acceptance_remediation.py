from __future__ import annotations

import unittest

from experiments.acceptance_remediation import (
    FROZEN_SOURCES,
    _acceptance_row,
    _new_execution_manifest,
    _performance_source_rows,
    protocol,
)


class AcceptanceRemediationProtocolTests(unittest.TestCase):
    def test_main_scale_and_job_plan_are_exact(self) -> None:
        spec = protocol()
        expected = (
            spec["expected_case_count"]
            * len(spec["models"])
            * len(spec["conditions"])
            * len(spec["seeds"])
        )
        self.assertEqual(expected, 2160)
        self.assertEqual(spec["expected_logical_case_runs"], expected)
        manifest = _new_execution_manifest(spec)
        self.assertEqual(len(manifest["jobs"]), 12)
        self.assertEqual(
            sum(job["expected_case_runs"] for job in manifest["jobs"]),
            expected,
        )

    def test_performance_replay_source_has_all_frozen_cells(self) -> None:
        spec = protocol()
        rows, cases = _performance_source_rows(spec)
        self.assertEqual(len(rows), 144)
        self.assertEqual(len(cases), 40)
        self.assertEqual(
            len(
                {
                    (row["target_prompt_tokens"], row["offered_concurrency"])
                    for row in rows
                }
            ),
            12,
        )
        self.assertTrue(all(row["condition_id"] == "e14_v2_off" for row in rows))
        self.assertTrue(all(row["step"] == 1 for row in rows))

    def test_diagnostic_smokes_cannot_be_frozen_formal_sources(self) -> None:
        self.assertFalse(
            any("diagnostic" in path.casefold() for path in FROZEN_SOURCES)
        )

    def test_acceptance_row_does_not_hide_failed_gate(self) -> None:
        row = _acceptance_row(
            "A04",
            "Recall",
            ">= 90%",
            False,
            0.89,
            "proportion",
            0.9,
            method="test",
        )
        self.assertEqual(row["status"], "fail")


if __name__ == "__main__":
    unittest.main()
