from __future__ import annotations

import unittest
from copy import deepcopy

from experiments.paper_v2.metrics import (
    PaperV2MetricError,
    summarize_experiment_records,
)
from tests.unit.test_paper_v2_contracts import valid_record


def record(
    suffix: str,
    *,
    benchmark: str,
    case_type: str,
    unsafe: bool | None,
    unsafe_itt: bool,
    completed: bool,
    status: str = "completed",
) -> dict:
    row = deepcopy(valid_record())
    row["record_id"] = f"record-{suffix}"
    row["case_id"] = f"case-{suffix}"
    row["benchmark_id"] = benchmark
    row["evaluation_case_type"] = case_type
    row["unsafe_effect"] = unsafe
    row["unsafe_effect_itt"] = unsafe_itt
    row["task_completion"] = completed
    row["operational_status"] = status
    return row


class PaperV2MetricGoldenTests(unittest.TestCase):
    def test_failures_remain_in_attack_itt_denominator(self) -> None:
        rows = [
            record(
                "attack-unsafe",
                benchmark="agentdojo",
                case_type="attack",
                unsafe=True,
                unsafe_itt=True,
                completed=False,
            ),
            record(
                "attack-safe",
                benchmark="agentdojo",
                case_type="attack",
                unsafe=False,
                unsafe_itt=False,
                completed=True,
            ),
            record(
                "attack-timeout",
                benchmark="agentdojo",
                case_type="attack",
                unsafe=None,
                unsafe_itt=True,
                completed=False,
                status="timeout",
            ),
        ]

        summary = summarize_experiment_records(rows)

        self.assertEqual(
            summary["unsafe_effect_itt"],
            {"numerator": 2, "denominator": 3, "rate": 2 / 3},
        )
        self.assertEqual(
            summary["unsafe_effect_observed_only"],
            {"numerator": 1, "denominator": 2, "rate": 0.5},
        )
        self.assertEqual(
            summary["operational_failure_rate"],
            {"numerator": 1, "denominator": 3, "rate": 1 / 3},
        )

    def test_refusal_is_safe_but_not_benign_task_completion(self) -> None:
        completed = record(
            "benign-completed",
            benchmark="m3-v2",
            case_type="benign_tool",
            unsafe=False,
            unsafe_itt=False,
            completed=True,
        )
        refused = record(
            "benign-refusal",
            benchmark="m3-v2",
            case_type="benign_no_tool",
            unsafe=False,
            unsafe_itt=False,
            completed=False,
            status="refusal",
        )

        summary = summarize_experiment_records([completed, refused])

        self.assertEqual(
            summary["benign_task_completion"],
            {"numerator": 1, "denominator": 2, "rate": 0.5},
        )
        self.assertEqual(summary["operational_failure_rate"]["numerator"], 0)

    def test_agentdojo_and_m3_v2_use_identical_metric_semantics(self) -> None:
        def benchmark_summary(benchmark: str) -> dict:
            return summarize_experiment_records(
                [
                    record(
                        f"{benchmark}-unsafe",
                        benchmark=benchmark,
                        case_type="attack",
                        unsafe=True,
                        unsafe_itt=True,
                        completed=False,
                    ),
                    record(
                        f"{benchmark}-safe",
                        benchmark=benchmark,
                        case_type="attack",
                        unsafe=False,
                        unsafe_itt=False,
                        completed=True,
                    ),
                ]
            )

        agentdojo = benchmark_summary("agentdojo")
        m3_v2 = benchmark_summary("m3-v2")

        self.assertEqual(
            agentdojo["unsafe_effect_itt"],
            m3_v2["unsafe_effect_itt"],
        )
        self.assertEqual(
            agentdojo["attack_condition_utility"],
            m3_v2["attack_condition_utility"],
        )

    def test_mixed_conditions_are_rejected(self) -> None:
        first = record(
            "one",
            benchmark="m3-v2",
            case_type="attack",
            unsafe=False,
            unsafe_itt=False,
            completed=True,
        )
        second = record(
            "two",
            benchmark="m3-v2",
            case_type="attack",
            unsafe=False,
            unsafe_itt=False,
            completed=True,
        )
        second["condition_id"] = "policy-only"

        with self.assertRaisesRegex(PaperV2MetricError, "multiple condition"):
            summarize_experiment_records([first, second])

    def test_duplicate_records_are_rejected(self) -> None:
        row = record(
            "duplicate",
            benchmark="m3-v2",
            case_type="attack",
            unsafe=False,
            unsafe_itt=False,
            completed=True,
        )
        with self.assertRaisesRegex(PaperV2MetricError, "duplicate record_id"):
            summarize_experiment_records([row, deepcopy(row)])


if __name__ == "__main__":
    unittest.main()

