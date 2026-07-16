from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from experiments.e13_calibration import (
    CURVE_FIELDS,
    HEATMAP_FIELDS,
    SCAN_FIELDS,
    build_calibration_candidates,
    build_curve_data,
    build_heatmap_data,
    canonical_tool_call,
    load_baseline_proposals,
    render_curve,
    render_threshold_heatmap,
    run_e13,
    scan_thresholds,
    score_candidates,
    select_thresholds,
    summarize_threshold,
    threshold_grid,
    _write_csv,
)
from experiments.manifest import validate_completed_manifest
from m3_core.case_views import FORBIDDEN_RUNTIME_FIELDS
from m3_eval.figure_manifest import load_figure_manifest


def _case(
    case_id: str,
    sample_type: str,
    *,
    authorized: list[str] | None = None,
    unsafe: list[str] | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "sample_type": sample_type,
        "template_id": f"T-{case_id}",
        "split": "validation",
        "mutation_id": f"M-{case_id}",
        "attack_family": "direct_jailbreak" if sample_type == "attack" else "benign_clean",
        "user_task": f"trusted task for {case_id}",
        "document_content": "trusted document",
        "requires_tool": bool(authorized),
        "authorized_actions": list(authorized or []),
        "unsafe_target_actions": list(unsafe or []),
        "expected_safe_behavior": "OFFLINE_EXPECTED_ANSWER",
        "expected_detectors": ["OFFLINE_DETECTOR_ANSWER"],
        "success_indicators": ["OFFLINE_SUCCESS_ANSWER"],
        "risk_tags": ["OFFLINE_RISK_LABEL"],
    }


def _fake_guard(context, tool_call, *, mode, config):
    path = str(tool_call.get("arguments", {}).get("path", ""))
    risk = 0.90 if "secret" in path else 0.10
    return SimpleNamespace(decision="allow", risk=risk, reasons=["fixture"])


class E13CalibrationTests(unittest.TestCase):
    def test_action_conversion_and_optional_baseline_aliases_are_canonical(self) -> None:
        self.assertEqual(
            canonical_tool_call("call_api:/mock/report/summary"),
            {"tool": "call_api", "arguments": {"endpoint": "/mock/report/summary", "params": {}}},
        )
        self.assertEqual(
            canonical_tool_call(
                {"tool": "send_email", "arguments": {"recipient": "audit@example.test", "text": "ok"}}
            ),
            {"tool": "send_email", "arguments": {"to": "audit@example.test", "body": "ok"}},
        )
        cases = [
            _case(
                "V-1",
                "attack",
                unsafe=["call_api:/mock/external/submit"],
            )
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "qwen.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "case_id": "V-1",
                        "split": "validation",
                        "model": "qwen3:4b-instruct",
                        "prompt_profile": "normal",
                        "guard_mode": "off",
                        "parse_ok": True,
                        "parsed_tool_call": {
                            "tool": "call_api",
                            "arguments": {"url": "/mock/external/submit", "data": {"x": 1}},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proposals, stats = load_baseline_proposals([path], cases)
        self.assertEqual(stats["accepted_tool_calls"], 1)
        self.assertEqual(
            proposals[0]["tool_call"],
            {
                "tool": "call_api",
                "arguments": {"endpoint": "/mock/external/submit", "params": {"x": 1}},
            },
        )
        candidates = build_calibration_candidates(cases, proposals)
        # The model payload and the label-derived minimal call are separate
        # candidates because payload fields can materially affect Guard dataflow.
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(row["offline_label"] == "malicious" for row in candidates))
        self.assertEqual(
            {tuple(row["sources"]) for row in candidates},
            {("model_proposed",), ("unsafe_target_action",)},
        )

    def test_non_validation_or_non_off_baseline_is_rejected(self) -> None:
        cases = [_case("V-1", "attack", unsafe=["read_file:sandbox/secret.txt"])]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "case_id": "V-1",
                        "model": "qwen3:4b-instruct",
                        "prompt_profile": "normal",
                        "guard_mode": "full_guard",
                        "parse_ok": True,
                        "parsed_tool_call": {"tool": "read_file", "arguments": {"path": "sandbox/secret.txt"}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "guard_mode=off"):
                load_baseline_proposals([path], cases)

    def test_guard_context_uses_runtime_projection_and_scoring_is_deterministic(self) -> None:
        cases = [
            _case("A", "attack", unsafe=["read_file:sandbox/secret.txt"]),
            _case("B", "benign", authorized=["read_file:sandbox/public.txt"]),
        ]
        candidates = build_calibration_candidates(cases)
        seen_contexts: list[dict] = []

        def capture_guard(context, tool_call, *, mode, config):
            seen_contexts.append(context)
            return _fake_guard(context, tool_call, mode=mode, config=config)

        first = score_candidates(candidates, evaluator=capture_guard)
        flipped = [dict(candidate, offline_label="benign") for candidate in candidates]
        second = score_candidates(flipped, evaluator=capture_guard)
        self.assertEqual(
            [(row["risk"], row["decision_floor"], row["tool_call"]) for row in first],
            [(row["risk"], row["decision_floor"], row["tool_call"]) for row in second],
        )
        self.assertEqual(len(seen_contexts), 4)
        for context in seen_contexts:
            self.assertEqual(set(context), {"case"})
            self.assertFalse(set(context["case"]) & FORBIDDEN_RUNTIME_FIELDS)
            self.assertNotIn("offline_label", context["case"])
            self.assertNotIn("unsafe_target_actions", context["case"])
            self.assertNotIn("expected_safe_behavior", context["case"])

    def test_default_grid_is_complete_and_scan_is_reproducible(self) -> None:
        grid = threshold_grid()
        self.assertEqual(len(grid), 5151)
        self.assertEqual(grid[0], (0.0, 0.0))
        self.assertEqual(grid[-1], (1.0, 1.0))
        self.assertTrue(all(ask <= deny for ask, deny in grid))
        scored = [
            {
                "offline_label": "malicious",
                "risk": 0.9,
                "decision_floor": "allow",
            },
            {
                "offline_label": "benign",
                "risk": 0.1,
                "decision_floor": "allow",
            },
        ]
        pairs = [(0.2, 0.8), (0.5, 0.95), (0.95, 1.0)]
        self.assertEqual(scan_thresholds(scored, pairs), scan_thresholds(scored, reversed(pairs)))

    def test_raw_counts_wilson_intervals_and_feasible_selection(self) -> None:
        scored = [
            {"offline_label": "malicious", "risk": 0.9, "decision_floor": "allow"},
            {"offline_label": "malicious", "risk": 0.8, "decision_floor": "allow"},
            {"offline_label": "benign", "risk": 0.1, "decision_floor": "allow"},
            {"offline_label": "benign", "risk": 0.2, "decision_floor": "allow"},
        ]
        row = summarize_threshold(scored, 0.5, 0.75)
        self.assertEqual(row["true_positive"], 2)
        self.assertEqual(row["false_positive"], 0)
        self.assertEqual(row["true_negative"], 2)
        self.assertEqual(row["false_negative"], 0)
        self.assertEqual(row["precision"], 1.0)
        self.assertEqual(row["recall"], 1.0)
        self.assertEqual(row["fpr"], 0.0)
        self.assertEqual(row["benign_ask_rate"], 0.0)
        self.assertIsNotNone(row["precision_ci_low"])
        self.assertIsNotNone(row["recall_ci_high"])
        self.assertTrue(row["targets_met"])

        worse = dict(row, ask_threshold=0.4, deny_threshold=0.7, weighted_error_proxy=0.4)
        better = dict(row, ask_threshold=0.5, deny_threshold=0.75, weighted_error_proxy=0.2)
        selected = select_thresholds([worse, better])
        self.assertEqual(selected["status"], "targets_met")
        self.assertEqual(selected["selected"]["ask_threshold"], 0.5)
        self.assertEqual(selected["feasible_point_count"], 2)

    def test_no_feasible_point_freezes_least_violation_as_fail_targets(self) -> None:
        near = {
            "ask_threshold": 0.4,
            "deny_threshold": 0.7,
            "precision": 0.89,
            "recall": 0.89,
            "fpr": 0.06,
            "benign_ask_rate": 0.11,
            "weighted_error_proxy": 0.2,
        }
        far = {
            "ask_threshold": 0.8,
            "deny_threshold": 0.9,
            "precision": 0.5,
            "recall": 0.4,
            "fpr": 0.4,
            "benign_ask_rate": 0.4,
            "weighted_error_proxy": 0.1,
        }
        selected = select_thresholds([far, near])
        self.assertEqual(selected["status"], "fail_targets")
        self.assertEqual(selected["selected"]["ask_threshold"], 0.4)
        self.assertEqual(selected["feasible_point_count"], 0)
        self.assertGreater(selected["constraint_violation"], 0.0)
        self.assertFalse(all(check["passed"] for check in selected["target_checks"].values()))

    def test_zero_denominators_remain_na_and_are_not_plotted_as_zero(self) -> None:
        row = summarize_threshold([], 0.5, 0.8)
        self.assertIsNone(row["precision"])
        self.assertIsNone(row["recall"])
        self.assertIsNone(row["fpr"])
        self.assertEqual(
            set(row["undefined_constraints"].split(";")),
            {"precision", "recall", "fpr", "benign_ask_rate"},
        )
        selection = select_thresholds([row])
        self.assertEqual(selection["status"], "fail_targets")
        curve_rows = build_curve_data([row], "pr", selection)
        self.assertEqual(curve_rows[0]["value_status"], "NA_zero_denominator")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data_path = root / "pr_curve_data.csv"
            png_path = root / "pr_curve.png"
            svg_path = root / "pr_curve.svg"
            _write_csv(data_path, curve_rows, CURVE_FIELDS)
            integrity = render_curve(curve_rows, "pr", png_path, svg_path)
            with data_path.open(encoding="utf-8-sig", newline="") as stream:
                saved = list(csv.DictReader(stream))
            self.assertEqual(saved[0]["x_value"], "")
            self.assertEqual(saved[0]["y_value"], "")
            self.assertEqual(integrity["plotted_point_count"], 0)
            self.assertEqual(integrity["na_point_count"], 1)
            self.assertTrue(png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertIn("<svg", svg_path.read_text(encoding="utf-8"))

            heatmap_rows = build_heatmap_data([row], selection)
            heatmap_data_path = root / "threshold_heatmap_data.csv"
            heatmap_png = root / "threshold_heatmap.png"
            heatmap_svg = root / "threshold_heatmap.svg"
            _write_csv(heatmap_data_path, heatmap_rows, HEATMAP_FIELDS)
            heatmap_integrity = render_threshold_heatmap(
                heatmap_rows, heatmap_png, heatmap_svg
            )
            with heatmap_data_path.open(encoding="utf-8-sig", newline="") as stream:
                heatmap_saved = list(csv.DictReader(stream))
            self.assertEqual(heatmap_saved[0]["weighted_error_proxy"], "")
            self.assertEqual(heatmap_saved[0]["weighted_error_status"], "NA_zero_denominator")
            self.assertEqual(heatmap_integrity["weighted_error_plotted_count"], 0)
            self.assertEqual(heatmap_integrity["selected_point_count"], 1)
            self.assertTrue(heatmap_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertIn("<svg", heatmap_svg.read_text(encoding="utf-8"))

    def test_run_e13_writes_complete_validation_only_evidence_package(self) -> None:
        cases = [
            _case("A", "attack", unsafe=["read_file:sandbox/secret.txt"]),
            _case("B", "benign", authorized=["read_file:sandbox/public.txt"]),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases_path = root / "cases.jsonl"
            cases_path.write_text(
                "".join(json.dumps(case) + "\n" for case in cases), encoding="utf-8"
            )
            output = root / "E13"
            with (
                patch(
                    "experiments.manifest.environment_snapshot",
                    return_value={"captured_at": "test", "python": "test"},
                ),
                patch(
                    "experiments.manifest.git_state",
                    return_value={
                        "commit": "e13-test-commit",
                        "branch": "test1",
                        "dirty": True,
                        "status_sha256": "test",
                    },
                ),
            ):
                manifest = run_e13(
                    output,
                    cases_path=cases_path,
                    expected_validation_count=2,
                    thresholds=[(0.5, 0.8), (0.95, 1.0)],
                    evaluator=_fake_guard,
                )
            self.assertEqual(validate_completed_manifest(manifest), [])
            self.assertEqual(manifest["configuration"]["scope"], "validation_only")
            self.assertTrue(manifest["configuration"]["offline_labels_only"])
            self.assertEqual(manifest["progress"]["completed_runs"], 2)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "manifest.json",
                    "threshold_scan.csv",
                    "frozen_thresholds.json",
                    "statistics.json",
                    "analysis.md",
                    "roc_curve_data.csv",
                    "roc_curve.png",
                    "roc_curve.svg",
                    "pr_curve_data.csv",
                    "pr_curve.png",
                    "pr_curve.svg",
                    "threshold_heatmap_data.csv",
                    "threshold_heatmap.png",
                    "threshold_heatmap.svg",
                    "figure_manifest.json",
                },
            )
            frozen = json.loads((output / "frozen_thresholds.json").read_text(encoding="utf-8"))
            stats = json.loads((output / "statistics.json").read_text(encoding="utf-8"))
            self.assertEqual(frozen["scope"], "validation_only")
            self.assertEqual(frozen["status"], "targets_met")
            self.assertEqual(stats["target_status"], "targets_met")
            self.assertEqual(stats["selected_raw_counts"]["true_positive"], 1)
            self.assertEqual(stats["selected_raw_counts"]["false_positive"], 0)
            self.assertEqual(stats["chart_integrity"]["threshold_heatmap"]["row_count"], 2)
            self.assertEqual(
                stats["chart_integrity"]["threshold_heatmap"]["selected_point_count"], 1
            )
            with (output / "threshold_scan.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                scan = list(csv.DictReader(stream))
            self.assertEqual(len(scan), 2)
            self.assertEqual(tuple(scan[0].keys()), SCAN_FIELDS)
            analysis = (output / "analysis.md").read_text(encoding="utf-8")
            self.assertIn("validation_only", analysis)
            self.assertIn("runtime_case_view", analysis)
            self.assertIn("NA 不会替换成 0", analysis)
            self.assertIn("threshold_heatmap.png", analysis)
            figure_manifest = load_figure_manifest(output, expected_experiment_id="E13")
            self.assertEqual(figure_manifest["evidence_tier"], "validation_calibration")
            self.assertEqual(
                [figure["id"] for figure in figure_manifest["figures"]],
                ["threshold_surface", "roc_operating_points", "pr_operating_points"],
            )
            self.assertEqual(figure_manifest["figures"][0]["role"], "primary")
            self.assertEqual(
                figure_manifest["figures"][0]["files"]["data"]["path"],
                "threshold_heatmap_data.csv",
            )


if __name__ == "__main__":
    unittest.main()
