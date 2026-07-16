from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.e0_audit import CANONICAL_CASES, run_e0
from experiments.manifest import sha256_file, validate_completed_manifest
from m3_eval.figure_manifest import load_figure_manifest


class E0AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.output = Path(cls._temp_dir.name) / "E0"
        with (
            patch(
                "experiments.manifest.environment_snapshot",
                return_value={"captured_at": "test", "python": "test"},
            ),
            patch(
                "experiments.manifest.git_state",
                return_value={
                    "commit": "e0-test-commit",
                    "branch": "test1",
                    "dirty": True,
                    "status_sha256": "test",
                },
            ),
        ):
            cls.manifest = run_e0(cls.output)
        cls.audit = json.loads(
            (cls.output / "measurement_audit.json").read_text(encoding="utf-8")
        )
        cls.raw_index = json.loads(
            (cls.output / "raw_run_index.json").read_text(encoding="utf-8")
        )
        cls.statistics = json.loads(
            (cls.output / "statistics.json").read_text(encoding="utf-8")
        )
        with (cls.output / "historical_metrics.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            cls.metrics = list(csv.DictReader(stream))
        with (cls.output / "historical_diagnostic_metrics_data.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            cls.chart_data = list(csv.DictReader(stream))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp_dir.cleanup()

    def test_complete_manifest_registers_full_evidence_package(self) -> None:
        self.assertEqual(validate_completed_manifest(self.manifest), [])
        self.assertEqual(self.manifest["status"], "completed")
        self.assertEqual(
            self.manifest["progress"],
            {
                "expected_runs": 6,
                "completed_runs": 6,
                "failed_jobs": 0,
                "unresolved_cases": 5,
            },
        )
        kinds = {artifact["kind"] for artifact in self.manifest["artifacts"]}
        self.assertTrue(
            {"raw_log", "metrics", "statistics", "analysis", "figure", "figure_manifest"}.issubset(kinds)
        )
        expected_files = {
            "manifest.json",
            "raw_run_index.json",
            "measurement_audit.json",
            "historical_metrics.csv",
            "statistics.json",
            "analysis.md",
            "historical_diagnostic_metrics_data.csv",
            "historical_diagnostic_metrics.png",
            "historical_diagnostic_metrics.svg",
            "figure_manifest.json",
        }
        self.assertEqual({path.name for path in self.output.iterdir()}, expected_files)

    def test_raw_index_has_hashes_and_exact_row_case_counts(self) -> None:
        self.assertEqual(self.raw_index["historical_run_count"], 6)
        self.assertEqual(len(self.raw_index["records"]), 9)
        records = {record["path"]: record for record in self.raw_index["records"]}
        canonical = records["m3_attacks/cases/all_cases.jsonl"]
        self.assertEqual(canonical["row_count"], 300)
        self.assertEqual(canonical["distinct_case_count"], 300)
        self.assertEqual(canonical["sha256"], sha256_file(CANONICAL_CASES))
        expected = {
            "outputs/runs/day5_stub_matrix/day5_stub_all_baseline.jsonl": (163, 69),
            "outputs/runs/day5_stub_matrix/day5_stub_all_keyword_only.jsonl": (91, 69),
            "outputs/runs/day5_stub_matrix/day5_stub_all_policy_only.jsonl": (69, 69),
            "outputs/runs/day5_stub_matrix/day5_stub_all_full_guard.jsonl": (69, 69),
            "outputs/runs/day5_qwen25_matrix/day5_qwen25_rep_baseline.jsonl": (38, 24),
            "outputs/runs/day5_qwen25_matrix/day5_qwen25_rep_full_guard.jsonl": (24, 24),
        }
        for path, (rows, cases) in expected.items():
            self.assertEqual(records[path]["row_count"], rows)
            self.assertEqual(records[path]["distinct_case_count"], cases)
            self.assertEqual(len(records[path]["sha256"]), 64)

    def test_canonical_dataset_and_runtime_prompt_checks_pass(self) -> None:
        self.assertEqual(self.audit["status"], "pass_with_historical_findings")
        self.assertTrue(all(self.audit["current_measurement_checks"].values()))
        canonical = self.audit["canonical_dataset"]
        self.assertEqual(canonical["total_cases"], 300)
        self.assertEqual(canonical["sample_type_count"], {"attack": 210, "benign": 90})
        self.assertEqual(canonical["split_count"], {"blind": 90, "dev": 150, "validation": 60})
        self.assertEqual(canonical["benign_tool_requirement_count"], {"no_tool": 45, "tool": 45})
        self.assertEqual(len(canonical["attack_family_count"]), 9)
        self.assertEqual(sum(canonical["attack_family_count"].values()), 210)
        self.assertEqual(canonical["legacy_case_count"], 69)
        self.assertEqual(canonical["legacy_case_split_count"], {"dev": 69})
        self.assertEqual(canonical["cross_split_templates"], [])
        runtime = self.audit["runtime_prompt_audit"]
        self.assertEqual(runtime["status"], "pass")
        self.assertEqual(runtime["cases_checked"], 300)
        self.assertEqual(runtime["messages_compared"], 600)
        self.assertEqual(runtime["projection_failures"], [])
        self.assertEqual(runtime["metamorphic_invariance_failures"], [])
        self.assertEqual(runtime["sentinel_leakage_failures"], [])

    def test_historical_denominators_and_metrics_are_corrected(self) -> None:
        self.assertEqual(len(self.metrics), 6)
        rows = {row["run_name"]: row for row in self.metrics}
        for name in (
            "stub_baseline",
            "stub_keyword_only",
            "stub_policy_only",
            "stub_full_guard",
        ):
            self.assertEqual(rows[name]["ASR_denominator"], "61")
            self.assertEqual(rows[name]["TCR_denominator"], "8")
            self.assertEqual(rows[name]["legacy_inferred_labels"], "0")
        for name in ("qwen25_baseline", "qwen25_full_guard"):
            self.assertEqual(rows[name]["ASR_denominator"], "19")
            self.assertEqual(rows[name]["TCR_denominator"], "5")
            self.assertEqual(rows[name]["legacy_inferred_labels"], "0")
        self.assertEqual(rows["stub_baseline"]["ASR_numerator"], "35")
        self.assertEqual(rows["stub_baseline"]["ASR"], "0.57377")
        self.assertEqual(rows["stub_keyword_only"]["ASR_numerator"], "8")
        self.assertEqual(rows["stub_policy_only"]["ASR"], "0.0")
        self.assertEqual(rows["stub_full_guard"]["ASR"], "0.0")
        self.assertEqual(rows["qwen25_baseline"]["ParseSuccessRate_numerator"], "36")
        self.assertEqual(rows["qwen25_baseline"]["ParseSuccessRate_denominator"], "38")
        self.assertEqual(rows["qwen25_baseline"]["unresolved_runs"], "3")
        self.assertEqual(rows["qwen25_full_guard"]["ParseSuccessRate_numerator"], "22")
        self.assertEqual(rows["qwen25_full_guard"]["ParseSuccessRate_denominator"], "24")
        self.assertEqual(rows["qwen25_full_guard"]["unresolved_runs"], "2")

    def test_undefined_metrics_remain_na_in_csv_and_chart(self) -> None:
        rows = {row["run_name"]: row for row in self.metrics}
        # The archived Qwen full-Guard log contains two legal file calls using
        # the historical ``file_path`` alias.  Both were blocked, so they are
        # observable false positives rather than an undefined zero denominator.
        self.assertEqual(rows["qwen25_full_guard"]["FPR"], "1.0")
        self.assertEqual(rows["qwen25_full_guard"]["FPR_numerator"], "2")
        self.assertEqual(rows["qwen25_full_guard"]["FPR_denominator"], "2")
        self.assertEqual(rows["qwen25_baseline"]["FPR"], "0.0")
        self.assertEqual(rows["qwen25_baseline"]["FPR_denominator"], "3")

        for name in (
            "stub_baseline",
            "stub_keyword_only",
            "stub_policy_only",
            "stub_full_guard",
        ):
            self.assertEqual(rows[name]["FPR"], "")
            self.assertEqual(rows[name]["FPR_denominator"], "0")

        na_rows = [row for row in self.chart_data if row["value_status"] == "NA_zero_denominator"]
        self.assertEqual(len(na_rows), 4)
        self.assertTrue(all(row["value"] == "" for row in na_rows))
        self.assertEqual(
            {(row["run_name"], row["metric"]) for row in na_rows},
            {
                ("stub_baseline", "FPR"),
                ("stub_keyword_only", "FPR"),
                ("stub_policy_only", "FPR"),
                ("stub_full_guard", "FPR"),
            },
        )
        qwen_baseline_fpr = next(
            row
            for row in self.chart_data
            if row["run_name"] == "qwen25_baseline" and row["metric"] == "FPR"
        )
        self.assertEqual(qwen_baseline_fpr["value"], "0.0")
        self.assertEqual(qwen_baseline_fpr["value_status"], "observed")

        qwen_full_fpr = next(
            row
            for row in self.chart_data
            if row["run_name"] == "qwen25_full_guard" and row["metric"] == "FPR"
        )
        self.assertEqual(qwen_full_fpr["value"], "1.0")
        self.assertEqual(qwen_full_fpr["value_status"], "observed")

    def test_statistics_use_formal_paired_methods(self) -> None:
        self.assertEqual(self.statistics["status"], "completed")
        self.assertEqual(self.statistics["scope"], "historical_diagnostic_only")
        self.assertEqual(len(self.statistics["comparisons"]), 4)
        self.assertEqual(len(self.statistics["holm_correction"]), 12)
        for comparison in self.statistics["comparisons"]:
            paired = comparison["paired_statistics"]
            for metric in ("ASR", "DSR", "TCR"):
                self.assertEqual(paired[f"{metric}_mcnemar"]["method"], "mcnemar_exact")
                self.assertIn("holm_adjusted_p", paired[f"{metric}_mcnemar"])
                bootstrap = paired[f"{metric}_bootstrap_guard_minus_baseline"]
                self.assertEqual(bootstrap["iterations"], 10_000)
                self.assertEqual(bootstrap["seed"], 42)

    def test_historical_causal_limitations_are_explicit(self) -> None:
        findings = self.audit["historical_source_findings"]
        self.assertTrue(findings["prompt_guard_coupling"]["detected"])
        self.assertTrue(findings["model_input_label_leakage"]["detected"])
        self.assertEqual(
            set(findings["model_input_label_leakage"]["leaked_fields"]),
            {"case_id", "attack_family", "expected_safe_behavior"},
        )
        self.assertTrue(findings["stub_oracle_label_dependency"]["detected"])
        self.assertEqual(findings["causal_interpretation"], "diagnostic_only")
        analysis = (self.output / "analysis.md").read_text(encoding="utf-8")
        for phrase in (
            "diagnostic only",
            "Prompt/Guard coupling",
            "Label leakage",
            "Stub oracle dependency",
            "不能支持 Guard 的正式因果结论",
        ):
            self.assertIn(phrase, analysis)

    def test_png_svg_and_adjacent_chart_data_are_valid(self) -> None:
        png = (self.output / "historical_diagnostic_metrics.png").read_bytes()
        svg = (self.output / "historical_diagnostic_metrics.svg").read_text(encoding="utf-8")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("<svg", svg)
        self.assertEqual(len(self.chart_data), 6 * 5)
        figure_manifest = load_figure_manifest(self.output, expected_experiment_id="E0")
        self.assertEqual(figure_manifest["evidence_tier"], "historical_diagnostic_only")
        self.assertEqual(len(figure_manifest["figures"]), 1)
        self.assertEqual(figure_manifest["figures"][0]["role"], "diagnostic")
        self.assertTrue(figure_manifest["figures"][0]["warnings"])


if __name__ == "__main__":
    unittest.main()
