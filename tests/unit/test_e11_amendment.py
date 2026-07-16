from __future__ import annotations

import copy
import csv
import json
from collections import Counter
from pathlib import Path

import pytest
from matplotlib import image as mpimg
from jsonschema import Draft202012Validator

from m3_core.agent_runner import _build_initial_messages
from m3_core.case_views import FORBIDDEN_RUNTIME_FIELDS
from m3_eval.figure_manifest import load_figure_manifest, write_figure_manifest
from scripts.e11_amendment_analyzer import (
    PATTERNS,
    build_metric_rows,
    build_pattern_statistics,
    build_statistics_from_binary_pairs,
    render_primary_figure,
    validate_formal_execution,
)
from scripts.e11_amendment_runner import (
    FREEZE_PATH,
    EXECUTION_REVISION,
    LEGACY_FREEZE_PATH,
    REPO_ROOT,
    SMOKE_CASE_IDS,
    VISUALIZATION_REVISION,
    canonical_action,
    load_protocol_data,
    materialize_case,
    runtime_projection,
    selected_case_ids_for_phase,
    verify_amendment_freeze,
    verify_hash_entries,
)
from scripts.verify_historical_evidence import verify_historical_evidence


def test_amendment_dataset_has_four_patterns_six_each_and_valid_semantics() -> None:
    cases, fixtures = load_protocol_data()
    schema = json.loads(
        (REPO_ROOT / "schemas" / "attack_case.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    for case in cases:
        assert list(validator.iter_errors(case)) == []

    assert len(cases) == 24
    assert Counter(
        case["attack_dimensions"]["chain_pattern"] for case in cases
    ) == Counter({pattern: 6 for pattern in PATTERNS})
    assert len(fixtures) == 24
    assert {case["observation_fixture_id"] for case in cases} == set(fixtures)

    allowed_source_tools = {"read_file", "call_api"}
    allowed_next_tools = {"send_email", "call_api", "write_file", "run_code"}
    for case in cases:
        fixture = fixtures[case["observation_fixture_id"]]
        source = fixture["source_tool_call"]
        unsafe = fixture["unsafe_next_tool_call"]
        assert source["tool"] in allowed_source_tools
        assert unsafe["tool"] in allowed_next_tools
        assert case["authorized_actions"] == [canonical_action(source)]
        assert case["unsafe_target_actions"] == [canonical_action(unsafe)]
        assert case["sample_type"] == "attack"
        assert case["attack_dimensions"]["posthoc_protocol_amendment"] is True
        assert case["attack_dimensions"]["pre_registered"] is False


def test_materialization_does_not_leak_offline_answer_fields_to_model_messages() -> None:
    cases, fixtures = load_protocol_data()
    case = copy.deepcopy(cases[0])
    canary = "OFFLINE_LABEL_LEAK_CANARY_7F9C"
    for field in FORBIDDEN_RUNTIME_FIELDS:
        case[field] = canary
    materialized = materialize_case(case, fixtures[cases[0]["observation_fixture_id"]])
    projection = runtime_projection(materialized)
    messages = _build_initial_messages(materialized, prompt_profile="normal")
    serialized_projection = json.dumps(projection, ensure_ascii=False, sort_keys=True)
    serialized_messages = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    assert canary not in serialized_projection
    assert canary not in serialized_messages
    assert set(projection) == {
        "user_task",
        "document_content",
        "requires_tool",
        "authorized_actions",
        "conversation_turns",
    }
    assert projection["conversation_turns"][-1]["trust"] == "tool_output"


def test_amendment_freeze_is_preserved_and_current_drift_is_explicit() -> None:
    payload = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    assert payload["pre_registered"] is False
    assert payload["visualization_revision"] == VISUALIZATION_REVISION == 2
    assert payload["execution_revision"] == EXECUTION_REVISION == "r2"
    assert payload["denominator_policy"] == (
        "excluded_from_original_e11_denominator"
    )
    with pytest.raises(RuntimeError, match="freeze drift for runtime.agent_runner"):
        verify_amendment_freeze()
    compatibility = verify_historical_evidence()
    assert compatibility["status"] == "pass"
    assert compatibility["current_evidence"]["source_records"] > 0
    by_id = {item["id"]: item for item in compatibility["historical_bundles"]}
    assert by_id["e11_amendment_execution_r2"]["declared_current_source_drifts"] == 6
    assert (
        by_id["context_correction_v2_execution_r3_and_sampled_e17"]
        ["declared_current_source_drifts"]
        == 7
    )
    drifted = copy.deepcopy(payload)
    cases_entry = next(item for item in drifted["artifacts"] if item["role"] == "cases")
    cases_entry["sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="freeze drift for cases"):
        verify_hash_entries(drifted)
    legacy = json.loads(LEGACY_FREEZE_PATH.read_text(encoding="utf-8"))
    with pytest.raises(RuntimeError, match="freeze drift"):
        verify_hash_entries(legacy)


def test_statistics_contract_is_case_paired_10k_and_holm_corrected() -> None:
    pairs = {
        pattern: [
            (True, False),
            (True, False),
            (True, False),
            (False, False),
            (True, True),
            (False, False),
        ]
        for pattern in PATTERNS
    }
    result = build_statistics_from_binary_pairs(pairs)
    assert result["bootstrap_iterations"] == 10_000
    assert [item["pattern"] for item in result["comparisons"]] == list(PATTERNS)
    for comparison in result["comparisons"]:
        mcnemar = comparison["mcnemar"]
        bootstrap = comparison["case_paired_bootstrap"]
        assert mcnemar["pairs"] == 6
        assert mcnemar["p_value_holm"] >= mcnemar["p_value"]
        assert bootstrap["iterations"] == 10_000
        assert bootstrap["pairs"] == 6
        assert bootstrap["clusters"] == 6
        assert bootstrap["estimate"] == pytest.approx(-0.5)


def test_production_metric_and_comparison_path_uses_six_paired_cases_per_pattern() -> None:
    cases, fixtures = load_protocol_data()
    logs = {"posthoc_off": [], "posthoc_full": []}
    for case in cases:
        fixture = fixtures[case["observation_fixture_id"]]
        for condition, guarded in (("posthoc_off", False), ("posthoc_full", True)):
            logs[condition].append(
                {
                    "experiment_id": "e11_posthoc_amendment_v1_formal",
                    "run_id": f"{condition}:{case['case_id']}",
                    "run_key": f"{condition}:{case['case_id']}",
                    "case_id": case["case_id"],
                    "model": "qwen3:4b-instruct",
                    "backend": "ollama",
                    "evidence_tier": "formal_model",
                    "condition_id": condition,
                    "prompt_profile": "normal",
                    "guard_mode": "full_guard" if guarded else "off",
                    "guard_modules": [],
                    "replicate_id": 0,
                    "seed": 433,
                    "step": 1,
                    "parse_ok": True,
                    "parsed_tool_call": fixture["unsafe_next_tool_call"],
                    "guard_decision": "deny" if guarded else "allow",
                    "risk_score": 1.0 if guarded else 0.0,
                    "observation": (
                        "BLOCKED_BY_M3_GUARD" if guarded else "MOCK_TOOL_EXECUTED"
                    ),
                    "final_status": "blocked" if guarded else "completed",
                    "timed_out": False,
                }
            )
    rows, _ = build_metric_rows(logs, cases)
    assert len(rows) == 8
    for row in rows:
        assert row["attack_runs"] == 6
        assert row["ASR_denominator"] == 6
        assert row["ASR"] == (0.0 if row["condition_id"] == "posthoc_full" else 1.0)
        assert row["ASR_ci_low"] is not None
        assert row["ASR_ci_high"] is not None
    statistics = build_pattern_statistics(logs, cases)
    assert len(statistics["comparisons"]) == 4
    for comparison in statistics["comparisons"]:
        assert comparison["mcnemar"]["pairs"] == 6
        assert comparison["case_paired_bootstrap"]["iterations"] == 10_000
        assert comparison["case_paired_bootstrap"]["estimate"] == pytest.approx(-1.0)
        assert comparison["mcnemar"]["p_value_holm"] >= comparison["mcnemar"]["p_value"]


def test_chart_and_figure_manifest_contract(tmp_path: Path) -> None:
    metric_rows = []
    for pattern_index, pattern in enumerate(PATTERNS):
        for condition, numerator in (("posthoc_off", 4), ("posthoc_full", 1)):
            value = numerator / 6
            metric_rows.append(
                {
                    "pattern": pattern,
                    "condition_id": condition,
                    "attack_runs": 6,
                    "ASR": value,
                    "ASR_numerator": numerator,
                    "ASR_denominator": 6,
                    "ASR_ci_low": max(0.0, value - 0.2),
                    "ASR_ci_high": min(1.0, value + 0.2),
                }
            )
    layout = render_primary_figure(metric_rows, tmp_path)
    assert layout["visualization_revision"] == 2
    assert layout["layout_status"] == "pass"
    assert (layout["canvas_width_px"], layout["canvas_height_px"]) == (2070, 1188)
    assert layout["footer_to_tick_gap_px"] >= layout["required_footer_to_tick_gap_px"]
    assert len(layout["x_tick_bboxes"]) == 4
    footer = layout["footer_bbox"]
    assert footer["y1_px"] < min(item["y0_px"] for item in layout["x_tick_bboxes"])
    ordered = sorted(layout["x_tick_bboxes"], key=lambda item: item["x0_px"])
    assert all(left["x1_px"] + 8 <= right["x0_px"] for left, right in zip(ordered, ordered[1:]))
    pixels = mpimg.imread(tmp_path / "primary_chart.png")
    assert pixels.shape[:2] == (1188, 2070)
    assert float(pixels[-12:, :, :3].min()) >= 0.98
    data_path = tmp_path / "primary_chart_data.csv"
    with data_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["pattern", "condition_id", "ASR", "ASR_ci_low", "ASR_ci_high"],
        )
        writer.writeheader()
        for row in metric_rows:
            writer.writerow({field: row[field] for field in writer.fieldnames})
    manifest_path = write_figure_manifest(
        tmp_path,
        experiment_id="E11",
        evidence_tier="formal_model_posthoc",
        figures=[
            {
                "id": "e11_posthoc_test",
                "title": "E11 post-hoc chart contract",
                "role": "primary",
                "order": 0,
                "chart_type": "grouped_bar_with_wilson_95ci",
                "caption": "Six cases per independently denominated pattern.",
                "files": {
                    "data": {"path": data_path.name},
                    "png": {"path": "primary_chart.png"},
                    "svg": {"path": "primary_chart.svg"},
                },
                "metrics": ["ASR"],
                "grain": ["pattern", "condition_id"],
                "uncertainty": [{"method": "Wilson", "confidence": 0.95}],
                "warnings": ["Post-hoc; excluded from original denominator."],
            }
        ],
    )
    loaded = load_figure_manifest(manifest_path, expected_experiment_id="E11")
    assert loaded["evidence_tier"] == "formal_model_posthoc"
    for name in ("primary_chart.png", "primary_chart.svg", "primary_chart_data.csv"):
        assert (tmp_path / name).stat().st_size > 0


def test_formal_analyzer_rejects_stub_execution_before_reading_artifacts(
    tmp_path: Path,
) -> None:
    formal_dir = tmp_path / "formal"
    formal_dir.mkdir(parents=True)
    payload = {
        "protocol_id": "E11_POSTHOC_AMENDMENT_V1",
        "amendment_type": "posthoc_protocol_amendment",
        "visualization_revision": 2,
        "execution_revision": EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": "excluded_from_original_e11_denominator",
        "status": "completed",
        "phase": "formal",
        "backend": "stub",
        "model": "stub",
        "evidence_tier": "regression_only",
        "expected_logical_runs": 48,
        "actual_logical_runs": 48,
        "conditions": ["posthoc_off", "posthoc_full"],
    }
    (formal_dir / "execution_manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="backend mismatch"):
        validate_formal_execution(tmp_path)


def test_freeze_binds_protocol_runner_analyzer_v3_and_thresholds() -> None:
    payload = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    roles = {entry["role"] for entry in payload["artifacts"]}
    assert {
        "protocol",
        "protocol.execution_r2",
        "cases",
        "fixtures",
        "runner",
        "analyzer",
        "freeze_builder",
        "legacy_freeze",
        "v3_blind_freeze",
        "e13_thresholds",
        "runtime.agent_runner",
        "runtime.guard_engine",
        "runtime.metrics",
        "runtime.statistics",
    } <= roles


def test_phase_selection_records_explicit_smoke_and_formal_case_ids() -> None:
    cases, _fixtures = load_protocol_data()
    smoke = selected_case_ids_for_phase(cases, "smoke")
    formal = selected_case_ids_for_phase(cases, "formal")
    assert smoke == list(SMOKE_CASE_IDS)
    assert len(formal) == len(set(formal)) == 24
    assert formal == [case["case_id"] for case in cases]
