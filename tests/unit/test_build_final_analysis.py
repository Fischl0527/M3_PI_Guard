from __future__ import annotations

import csv
import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest
import scripts.build_final_analysis as final_analysis_module

from m3_eval.evidence_dashboard import load_dashboard_sources
from m3_eval.figure_manifest import load_figure_manifest, write_figure_manifest
from scripts.build_final_analysis import (
    Bundle,
    E11_REQUIRED_FREEZE_ROLES,
    E11_SUPPLEMENT_DENOMINATOR_POLICY,
    E11_SUPPLEMENT_EXECUTION_REVISION,
    E11_SUPPLEMENT_ID,
    E11_SUPPLEMENT_PATTERNS,
    E11_SUPPLEMENT_VISUALIZATION_REVISION,
    FinalAnalysisError,
    _build_failure_taxonomy,
    _validate_supplement_chart_layout,
    build_acceptance_matrix,
    build_e9_data_quality,
    build_failure_summary,
    generate_final_analysis,
    validate_e11_supplement,
    validate_inputs,
)


EXPERIMENT_IDS = tuple(f"E{index}" for index in range(18))


def _install_synthetic_corrected_e17_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def load(path: str | Path) -> dict:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return {
            "source_mode": payload["source_mode"],
            "coverage": payload["coverage"],
        }

    monkeypatch.setattr(final_analysis_module.e17_review, "load_source_index", load)


@pytest.fixture(autouse=True)
def _synthetic_corrected_e17_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_synthetic_corrected_e17_loader(monkeypatch)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_failure_taxonomy_uses_interval_dots_for_dense_composition(tmp_path: Path) -> None:
    counts_path = tmp_path / "failure_class_counts.csv"
    rows = []
    counts = {
        "leak": 30,
        "false_block": 20,
        "ask": 15,
        "parse_failure": 12,
        "timeout": 8,
        "max_steps": 7,
        "other": 5,
        "none": 3,
    }
    for failure_class, count in counts.items():
        rows.append(
            {
                "failure_class": failure_class,
                "count": count,
                "total": 100,
                "percent": float(count),
                "ci_low_percent": max(0.0, float(count) - 3.0),
                "ci_high_percent": min(100.0, float(count) + 3.0),
            }
        )
    _write_csv(counts_path, rows)
    bundle = Bundle(
        experiment_id="E17",
        directory=tmp_path,
        manifest_path=tmp_path / "manifest.json",
        manifest={},
        files={"failure_class_counts.csv": counts_path},
        figure_manifest={},
    )

    chart = _build_failure_taxonomy({"E17": bundle})

    assert chart.chart_type == "authoritative_count_bar_plus_share_dot_with_wilson_95ci"
    assert "too dense for an honest donut" in chart.caption


def test_e14_failure_summary_excludes_warmup_denominator(tmp_path: Path) -> None:
    performance = tmp_path / "performance.csv"
    _write_csv(
        performance,
        [
            {
                "job_type": "warmup",
                "expected_case_runs": 48,
                "error_case_runs": 7,
                "timeout_case_runs": 3,
            },
            {
                "job_type": "formal",
                "expected_case_runs": 432,
                "error_case_runs": 2,
                "timeout_case_runs": 1,
            },
        ],
    )
    bundles = {
        "E14": Bundle(
            experiment_id="E14",
            directory=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            manifest={},
            files={"performance.csv": performance},
            figure_manifest={},
        ),
        "E16": Bundle(
            experiment_id="E16",
            directory=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            manifest={},
            files={"adaptive_rounds.csv": tmp_path / "adaptive_rounds.csv"},
            figure_manifest={},
        ),
        "E17": Bundle(
            experiment_id="E17",
            directory=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            manifest={},
            files={"failure_class_counts.csv": tmp_path / "failure_class_counts.csv"},
            figure_manifest={},
        ),
    }
    _write_csv(
        bundles["E16"].files["adaptive_rounds.csv"],
        [
            {
                "denominator": 1,
                "parse_failures": 0,
                "timeouts": 0,
                "unresolved": 0,
                "max_steps": 0,
            }
        ],
    )
    _write_csv(
        bundles["E17"].files["failure_class_counts.csv"],
        [
            {
                "failure_class": "none",
                "count": 0,
                "total": 1,
                "percent": 0,
                "ci_low_percent": 0,
                "ci_high_percent": 0,
            }
        ],
    )

    e14 = [row for row in build_failure_summary(bundles) if row["source_experiment"] == "E14"]

    assert {row["denominator"] for row in e14} == {432}
    assert {row["failure_class"]: row["count"] for row in e14} == {
        "error": 2,
        "timeout": 1,
    }


def _write_white_png(path: Path, *, width: int, height: int) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    scanline = b"\x00" + (b"\xff\xff\xff" * width)
    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(scanline * height, level=9))
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


def _proportion(metric: str, numerator: int, denominator: int) -> dict:
    value = None if denominator == 0 else numerator / denominator
    # Exact interval values are not under test here; they only need to be finite
    # and remain NA when the denominator is zero.
    return {
        metric: value,
        f"{metric}_numerator": numerator,
        f"{metric}_denominator": denominator,
        f"{metric}_ci_low": None if denominator == 0 else max(0.0, value - 0.05),
        f"{metric}_ci_high": None if denominator == 0 else min(1.0, value + 0.05),
    }


def _metric_row(experiment_id: str, **values) -> dict:
    row = {
        "experiment_id": experiment_id,
        "scope": "overall",
        "model": "qwen3:4b-instruct",
        "condition_id": "regular_full",
        "prompt_profile": "normal",
        "guard_mode": "full_guard",
        "evidence_tier": "formal_model",
    }
    row.update(values)
    return row


def _generic_metrics(experiment_id: str) -> list[dict]:
    return [
        _metric_row(
            experiment_id,
            **_proportion("ASR", 1, 10),
            **_proportion("FPR", 0, 0),
            F1=0.5,
            F1_numerator=None,
            F1_denominator=None,
            F1_ci_low=None,
            F1_ci_high=None,
        )
    ]


def _data_files(experiment_id: str) -> dict[str, object]:
    files: dict[str, object] = {"metrics.csv": _generic_metrics(experiment_id)}
    if experiment_id == "E0":
        return {
            "measurement_audit.json": {"status": "completed", "scope": "diagnostic_only"},
            "historical_metrics.csv": [{"metric": "FPR", "value": 0, "denominator": 0}],
            "statistics.json": {"status": "completed", "scope": "historical_diagnostic_only"},
        }
    if experiment_id == "E1":
        rows = []
        for condition, asr, dsr, tcr, precision, recall, parse in (
            ("regular_none", (8, 10), (2, 10), (10, 10), (8, 10), (8, 10), (10, 10)),
            ("regular_full", (1, 10), (0, 10), (10, 10), (9, 10), (9, 10), (10, 10)),
        ):
            rows.append(
                _metric_row(
                    "E1",
                    scope="model_condition",
                    condition_id=condition,
                    guard_mode="off" if condition == "regular_none" else "full_guard",
                    **_proportion("ASR", *asr),
                    **_proportion("DSR", *dsr),
                    **_proportion("TCR", *tcr),
                    **_proportion("Precision", *precision),
                    **_proportion("Recall", *recall),
                    **_proportion("ParseSuccessRate", *parse),
                )
            )
        return {"metrics.csv": rows, "statistics.json": {"status": "completed", "comparisons": []}}
    if experiment_id in {"E2", "E3"}:
        baseline = "regular_none" if experiment_id == "E2" else "hardened_none"
        treatment = "hardened_none" if experiment_id == "E2" else "hardened_full"
        statistics = {
            "status": "completed",
            "comparisons": [
                {
                    "comparison_id": f"{experiment_id.lower()}-fixture",
                    "dimensions": {"model": "qwen3:4b-instruct"},
                    "baseline": {"condition_id": baseline, "prompt_profile": "normal", "guard_mode": "off"},
                    "treatment": {"condition_id": treatment, "prompt_profile": "hardened", "guard_mode": "full_guard" if experiment_id == "E3" else "off"},
                    "delta": {"ASR_reduction": 0.2},
                    "paired_statistics": {
                        "ASR_bootstrap_guard_minus_baseline": {
                            "estimate": -0.2,
                            "ci_low": -0.3,
                            "ci_high": -0.1,
                        }
                    },
                }
            ],
        }
        return {"metrics.csv": _generic_metrics(experiment_id), "statistics.json": statistics}
    if experiment_id == "E4":
        return {
            "metrics.csv": _generic_metrics("E4"),
            "statistics.json": {"status": "completed", "comparisons": []},
            "ablation_contributions.csv": [
                {
                    "variant_condition_id": "without_policy",
                    "ASR_increase_when_variant_replaces_full": 0.2,
                    "ASR_variant_minus_full_ci_low": 0.1,
                    "ASR_variant_minus_full_ci_high": 0.3,
                }
            ],
        }
    if experiment_id == "E5":
        rows = [
            _metric_row("E5", scope="model_condition", condition_id=condition, **_proportion("ASR", numerator, 10))
            for condition, numerator in (("regular_none", 8), ("regular_full", 1))
        ]
        return {"metrics.csv": rows, "statistics.json": {"status": "completed", "comparisons": []}}
    if experiment_id == "E6":
        row = _metric_row(
            "E6",
            scope="family_by_model",
            condition_id="regular_full",
            attack_family="indirect_injection",
            **_proportion("ASR", 1, 10),
            **_proportion("Recall", 9, 10),
            **_proportion("DSR", 0, 10),
        )
        return {"metrics.csv": [row], "by_family.csv": [row], "by_family_ci.csv": [row], "statistics.json": {"status": "completed"}}
    if experiment_id == "E7":
        row = _metric_row(
            "E7", scope="language", condition_id="derived_normal_full", language="zh", **_proportion("ASR", 1, 10), **_proportion("Recall", 9, 10)
        )
        return {"metrics.csv": [row], "by_language.csv": [row], "statistics.json": {"status": "completed"}}
    if experiment_id == "E8":
        row = _metric_row(
            "E8", scope="obfuscation", condition_id="derived_normal_full", obfuscation_type="base64", **_proportion("ASR", 2, 10), **_proportion("Recall", 8, 10)
        )
        return {"metrics.csv": [row], "by_mutation.csv": [row], "strength_curve.csv": [row], "statistics.json": {"status": "completed"}}
    if experiment_id == "E9":
        rows = [
            _metric_row(
                "E9",
                scope="context_position",
                condition_id="derived_normal_full",
                backend="ollama",
                evidence_tier="formal_context_correction_v2",
                protocol_id="CONTEXT_CORRECTION_V2",
                context_tokens=2048,
                target_prompt_tokens=2048,
                injection_position_pct=position,
                case_runs=10,
                unresolved_runs=unresolved,
                CaseLatencyP95=120 + position,
                **_proportion("ASR", numerator, 10),
                **_proportion("UnresolvedRate", unresolved, 10),
            )
            for position, numerator, unresolved in ((0, 1, 2), (100, 2, 3))
        ]
        return {
            "metrics.csv": rows,
            "context_position.csv": rows,
            "statistics.json": {
                "status": "completed",
                "protocol_id": "CONTEXT_CORRECTION_V2",
                "evidence_tier": "formal_context_correction_v2",
                "formal_model_only": True,
            },
        }
    if experiment_id == "E10":
        rows = [
            _metric_row(
                "E10",
                scope="turn_mode",
                condition_id="derived_normal_full",
                turn_count=turns,
                multi_turn_mode="delayed",
                **_proportion("ASR", numerator, 10),
            )
            for turns, numerator in ((1, 1), (3, 2))
        ]
        return {"metrics.csv": rows, "by_turn_count.csv": rows, "statistics.json": {"status": "completed"}}
    if experiment_id == "E11":
        rows = []
        for pattern, denominator, off_successes in (
            ("read_file_to_call_api", 6, 4),
            ("read_file_to_send_email", 6, 3),
            ("run_code_to_write_file", 6, 2),
            ("write_file_to_call_api", 4, 1),
        ):
            for condition, successes in (
                ("derived_normal_off", off_successes),
                ("derived_normal_full", 0),
            ):
                rows.append(
                    _metric_row(
                        "E11",
                        scope="chain_pattern",
                        condition_id=condition,
                        guard_mode="off" if condition.endswith("_off") else "full_guard",
                        chain_pattern=pattern,
                        **_proportion("ASR", successes, denominator),
                    )
                )
        return {
            "metrics.csv": _generic_metrics("E11"),
            "chain_metrics.csv": rows,
            "case_replays.json": {"replays": []},
            "statistics.json": {"status": "completed"},
        }
    if experiment_id == "E12":
        rows = [
            _metric_row(
                "E12",
                scope="utility_overall",
                condition_id="regular_none",
                guard_mode="off",
                **_proportion("TCR", 10, 10),
                **_proportion("FPR", 0, 10),
                **_proportion("BenignASKRate", 0, 10),
            ),
            _metric_row(
                "E12",
                scope="utility_overall",
                condition_id="regular_full",
                **_proportion("TCR", 10, 10),
                **_proportion("FPR", 0, 10),
                **_proportion("BenignASKRate", 1, 10),
            ),
            _metric_row(
                "E12",
                scope="utility_by_tool_requirement",
                condition_id="regular_full",
                requires_tool="true",
                **_proportion("TCR", 9, 10),
            ),
        ]
        return {"metrics.csv": rows, "utility_metrics.csv": rows, "statistics.json": {"status": "completed", "comparisons": []}}
    if experiment_id == "E13":
        scans = []
        for selected, ask, deny, tp, fp in ((True, 0.5, 0.8, 9, 0), (False, 0.6, 0.9, 8, 0)):
            scans.append(
                {
                    "ask_threshold": ask,
                    "deny_threshold": deny,
                    "selected": selected,
                    **_proportion("recall", tp, 10),
                    **_proportion("precision", tp, tp + fp),
                    **_proportion("fpr", fp, 10),
                    **_proportion("benign_ask_rate", 1, 10),
                }
            )
        return {
            "threshold_scan.csv": scans,
            "frozen_thresholds.json": {
                "scope": "validation_only",
                "status": "targets_met",
                "ask_threshold": 0.5,
                "deny_threshold": 0.8,
                "targets": {
                    "precision_min": 0.9,
                    "recall_min": 0.9,
                    "fpr_max": 0.05,
                    "benign_ask_rate_max": 0.1,
                },
                "target_checks": {
                    "precision": {"operator": ">=", "target": 0.9, "value": 1.0, "passed": True},
                    "recall": {"operator": ">=", "target": 0.9, "value": 0.9, "passed": True},
                    "fpr": {"operator": "<=", "target": 0.05, "value": 0.0, "passed": True},
                    "benign_ask_rate": {"operator": "<=", "target": 0.1, "value": 0.1, "passed": True},
                },
            },
            "statistics.json": {"status": "completed", "target_status": "targets_met"},
        }
    if experiment_id == "E14":
        performance = []
        for cohort in ("matched_benign_latency", "mixed_throughput"):
            for condition_id, guard_mode in (
                ("e14_v2_off", "off"),
                ("e14_v2_full_guard", "full_guard"),
            ):
                performance.append(
                    {
                        "job_type": "formal",
                        "model": "qwen3:4b-instruct",
                        "target_prompt_tokens": 2048,
                        "concurrency": 1,
                        "condition_id": condition_id,
                        "workload_cohort": cohort,
                        "prompt_profile": "normal",
                        "guard_mode": guard_mode,
                        "expected_case_runs": 10,
                        "observed_case_runs": 10,
                        "successful_case_runs": 10,
                        "missing_case_runs": 0,
                        "error_case_runs": 0,
                        "timeout_case_runs": 0,
                    }
                )
        latency = [
            {
                "target_prompt_tokens": 2048,
                "concurrency": 1,
                "condition_id": condition_id,
                "total_latency_p95_ms": total,
                "guard_latency_p95_ms": guard,
            }
            for condition_id, total, guard in (
                ("e14_v2_off", 100.0, 0.0),
                ("e14_v2_full_guard", 105.0, 5.0),
            )
        ]
        throughput = [
            {
                "target_prompt_tokens": 2048,
                "concurrency": 1,
                "condition_id": condition_id,
                "successful_case_runs_per_s": rate,
            }
            for condition_id, rate in (
                ("e14_v2_off", 2.0),
                ("e14_v2_full_guard", 1.9),
            )
        ]
        statistics = {
            "status": "completed",
            "protocol_id": "CONTEXT_CORRECTION_V2",
            "workload_revision": "r2",
            "evidence_tier": "formal_context_correction_v2",
            "formal_model_only": True,
            "comparisons": [
                {
                    "paired_overhead_percent": {"median": 5.0},
                    "target_checks": {"median_end_to_end_overhead_below_10pct": True},
                }
            ],
        }
        return {
            "performance.csv": performance,
            "latency_by_context_data.csv": latency,
            "throughput_by_concurrency_data.csv": throughput,
            "statistics.json": statistics,
        }
    if experiment_id == "E15":
        rows = [
            _metric_row(
                "E15",
                scope="stability_seed",
                condition_id="stability_normal_full",
                temperature=0.2,
                seed=seed,
                **_proportion("ASR", numerator, 10),
            )
            for seed, numerator in ((1, 1), (2, 2), (3, 1))
        ]
        return {"metrics.csv": rows, "stability.csv": rows, "statistics.json": {"status": "completed"}}
    if experiment_id == "E16":
        rounds = [
            {
                "round": index,
                "successes": successes,
                "denominator": 10,
                "asr": successes / 10,
                "ci_low": max(0, successes / 10 - 0.05),
                "ci_high": min(1, successes / 10 + 0.05),
                "parse_failures": 0,
                "timeouts": 0,
                "unresolved": 0,
                "max_steps": 0,
            }
            for index, successes in ((1, 1), (2, 2), (3, 3))
        ]
        raw_attempts = [
            {
                "attempt_key": f"fixture:{index}",
                "logs": [
                    {
                        "sandbox_runtime_version": "isolated-tool-sandbox-fixture-v1",
                        "model_config": {
                            "sandbox_runtime_version": "isolated-tool-sandbox-fixture-v1"
                        },
                    }
                ],
            }
            for index in range(2)
        ]
        return {
            "adaptive_rounds.csv": rounds,
            "statistics.json": {"status": "completed", "excluded_from_main_matrix": True},
            "raw_attempts.jsonl": raw_attempts,
        }
    if experiment_id == "E17":
        counts = []
        values = {"leak": 1, "false_block": 1, "ask": 0, "parse_failure": 0, "timeout": 0, "max_steps": 0, "other": 0, "none": 8}
        for name, count in values.items():
            counts.append(
                {
                    "failure_class": name,
                    "count": count,
                    "total": 10,
                    "percent": count * 10.0,
                    "ci_low_percent": max(0.0, count * 10.0 - 5.0),
                    "ci_high_percent": min(100.0, count * 10.0 + 5.0),
                }
            )
        return {
            "failure_class_counts.csv": counts,
            "failure_taxonomy.csv": [{"case_id": "fixture", "final_primary_code": "leak"}],
            "reviewer_agreement.json": {"percent_agreement": 1.0},
            "statistics.json": {"status": "completed", "excluded_from_main_matrix": True},
        }
    raise AssertionError(experiment_id)


def _materialize_file(path: Path, value: object) -> None:
    if path.suffix == ".csv":
        assert isinstance(value, list)
        _write_csv(path, value)
    elif path.suffix == ".json":
        assert isinstance(value, dict)
        _write_json(path, value)
    elif path.suffix == ".jsonl":
        assert isinstance(value, list)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in value),
            encoding="utf-8",
        )
    else:
        path.write_text(str(value), encoding="utf-8")


def _wilson_fixture(numerator: int, denominator: int) -> tuple[float, float]:
    z = 1.959963984540054
    estimate = numerator / denominator
    scale = 1.0 + z * z / denominator
    center = (estimate + z * z / (2.0 * denominator)) / scale
    radius = z * (
        (estimate * (1.0 - estimate) / denominator + z * z / (4.0 * denominator * denominator))
        ** 0.5
    ) / scale
    return max(0.0, center - radius), min(1.0, center + radius)


def _make_e11_supplement(root: Path) -> Path:
    output = root / "outputs" / "experiments" / "E11_posthoc_amendment_v1"
    run_root = root / "outputs" / "experiments" / "E11_posthoc_amendment_v1_runs" / "formal"
    protocol_dir = root / "protocols" / "e11_amendment_v1"
    output.mkdir(parents=True)
    run_root.mkdir(parents=True)
    protocol_dir.mkdir(parents=True)

    bound_root = root / "fixture_bound" / "e11_amendment"
    bound_root.mkdir(parents=True)
    freeze_artifacts: list[dict] = []
    v3_freeze = root / "outputs" / "experiments" / "blind_freeze_v3.json"
    thresholds = root / "outputs" / "experiments" / "E13" / "frozen_thresholds.json"
    special_roles = {
        "v3_blind_freeze": v3_freeze,
        "e13_thresholds": thresholds,
    }
    for role in sorted(E11_REQUIRED_FREEZE_ROLES):
        path = special_roles.get(role)
        if path is None:
            path = bound_root / f"{role.replace('.', '_')}.txt"
            path.write_text(f"frozen fixture for {role}\n", encoding="utf-8")
        freeze_artifacts.append(
            {
                "role": role,
                "path": path.relative_to(root).as_posix(),
                "sha256": _hash(path),
            }
        )
    freeze = {
        "schema_version": "1.0",
        "protocol_id": E11_SUPPLEMENT_ID,
        "amendment_type": "posthoc_protocol_amendment",
        "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
        "execution_revision": E11_SUPPLEMENT_EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": E11_SUPPLEMENT_DENOMINATOR_POLICY,
        "formal_model": "qwen3:4b-instruct",
        "formal_case_count": 24,
        "formal_logical_runs": 48,
        "supersedes_freeze_sha256": next(
            item["sha256"] for item in freeze_artifacts if item["role"] == "legacy_freeze"
        ),
        "historical_v3_freeze_integrity_mode": "hash_bound_reference_only",
        "v3_blind_freeze_sha256": _hash(v3_freeze),
        "e13_thresholds_sha256": _hash(thresholds),
        "artifacts": freeze_artifacts,
    }
    freeze_path = protocol_dir / "freeze_r2.json"
    _write_json(freeze_path, freeze)

    case_ids: dict[str, list[str]] = {
        pattern: [f"{pattern}-{index:02d}" for index in range(1, 7)]
        for pattern in E11_SUPPLEMENT_PATTERNS
    }
    materialized = run_root / "materialized_cases.jsonl"
    materialized.write_text(
        "".join(
            json.dumps({"case_id": case_id, "pattern": pattern}) + "\n"
            for pattern, values in case_ids.items()
            for case_id in values
        ),
        encoding="utf-8",
    )
    matrix_path = run_root / "matrix_manifest.json"
    _write_json(
        matrix_path,
        {
            "status": "completed",
            "results": [
                {
                    "condition_id": condition,
                    "status": "completed",
                    "case_count": 24,
                    "selected_case_count": 24,
                    "error_count": 0,
                }
                for condition in ("posthoc_off", "posthoc_full")
            ],
        },
    )
    selected_case_ids = [case_id for values in case_ids.values() for case_id in values]
    execution = {
        "schema_version": "1.0",
        "protocol_id": E11_SUPPLEMENT_ID,
        "amendment_type": "posthoc_protocol_amendment",
        "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
        "execution_revision": E11_SUPPLEMENT_EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": E11_SUPPLEMENT_DENOMINATOR_POLICY,
        "status": "completed",
        "phase": "formal",
        "backend": "ollama",
        "model": "qwen3:4b-instruct",
        "evidence_tier": "formal_model_posthoc",
        "conditions": ["posthoc_off", "posthoc_full"],
        "selected_case_ids": selected_case_ids,
        "expected_case_count_per_condition": 24,
        "expected_logical_runs": 48,
        "actual_logical_runs": 48,
        "materialized_cases_path": materialized.relative_to(root).as_posix(),
        "materialized_cases_sha256": _hash(materialized),
        "matrix_manifest_path": matrix_path.relative_to(root).as_posix(),
        "matrix_manifest_sha256": _hash(matrix_path),
        "amendment_freeze_path": freeze_path.relative_to(root).as_posix(),
        "amendment_freeze_sha256": _hash(freeze_path),
        "v3_blind_freeze_path": v3_freeze.relative_to(root).as_posix(),
        "v3_blind_freeze_sha256": _hash(v3_freeze),
        "e13_thresholds_path": thresholds.relative_to(root).as_posix(),
        "e13_thresholds_sha256": _hash(thresholds),
    }
    execution_path = run_root / "execution_manifest.json"
    _write_json(execution_path, execution)

    successes = {
        "read_to_send": (4, 0),
        "search_to_api": (3, 1),
        "memory_to_file": (2, 0),
        "tool_output_to_next_action": (5, 1),
    }
    metrics: list[dict] = []
    raw_runs: list[dict] = []
    replays: list[dict] = []
    comparisons: list[dict] = []
    for pattern in E11_SUPPLEMENT_PATTERNS:
        off_successes, full_successes = successes[pattern]
        for condition, numerator in (
            ("posthoc_off", off_successes),
            ("posthoc_full", full_successes),
        ):
            low, high = _wilson_fixture(numerator, 6)
            metrics.append(
                {
                    "pattern": pattern,
                    "condition_id": condition,
                    "prompt_profile": "normal",
                    "guard_mode": "off" if condition == "posthoc_off" else "full_guard",
                    "attack_runs": 6,
                    "missing_case_runs": 0,
                    "ASR": numerator / 6,
                    "ASR_numerator": numerator,
                    "ASR_denominator": 6,
                    "ASR_ci_low": low,
                    "ASR_ci_high": high,
                }
            )
            for index, case_id in enumerate(case_ids[pattern]):
                raw_runs.append(
                    {
                        "run_key": f"{condition}:{case_id}",
                        "case_id": case_id,
                        "pattern": pattern,
                        "condition_id": condition,
                        "attack_success": index < numerator,
                    }
                )
        for case_id in case_ids[pattern]:
            replays.append(
                {
                    "case_id": case_id,
                    "pattern": pattern,
                    "conditions": [
                        {"condition_id": "posthoc_off"},
                        {"condition_id": "posthoc_full"},
                    ],
                }
            )
        comparisons.append(
            {
                "pattern": pattern,
                "mcnemar": {
                    "pairs": 6,
                    "p_value": 0.125,
                    "p_value_holm": 0.5,
                    "holm_family": list(E11_SUPPLEMENT_PATTERNS),
                },
                "case_paired_bootstrap": {
                    "iterations": 10_000,
                    "pairs": 6,
                    "clusters": 6,
                    "estimate": (full_successes - off_successes) / 6,
                    "ci_low": -1.0,
                    "ci_high": 0.0,
                },
            }
        )
    _write_csv(output / "metrics.csv", metrics)
    _write_csv(
        output / "primary_chart_data.csv",
        [
            {
                key: row[key]
                for key in (
                    "pattern",
                    "condition_id",
                    "attack_runs",
                    "ASR",
                    "ASR_numerator",
                    "ASR_denominator",
                    "ASR_ci_low",
                    "ASR_ci_high",
                )
            }
            for row in metrics
        ],
    )
    _write_json(
        output / "statistics.json",
        {
            "schema_version": "1.0",
            "protocol_id": E11_SUPPLEMENT_ID,
            "amendment_type": "posthoc_protocol_amendment",
            "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
            "execution_revision": E11_SUPPLEMENT_EXECUTION_REVISION,
            "pre_registered": False,
            "denominator_policy": E11_SUPPLEMENT_DENOMINATOR_POLICY,
            "bootstrap_iterations": 10_000,
            "comparisons": comparisons,
        },
    )
    _write_json(
        output / "raw_run_index.json",
        {
            "schema_version": "1.0",
            "protocol_id": E11_SUPPLEMENT_ID,
            "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
            "execution_revision": E11_SUPPLEMENT_EXECUTION_REVISION,
            "denominator_policy": E11_SUPPLEMENT_DENOMINATOR_POLICY,
            "logical_run_count": 48,
            "runs": raw_runs,
        },
    )
    _write_json(
        output / "case_replays.json",
        {
            "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
            "replays": replays,
        },
    )
    (output / "analysis.md").write_text(
        "# Post-hoc E11 supplement\n\npre_registered=false; denominators are not pooled.\n",
        encoding="utf-8",
    )
    _write_white_png(output / "primary_chart.png", width=2070, height=1188)
    (output / "primary_chart.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8"
    )
    _write_json(
        output / "primary_chart_layout.json",
        {
            "schema_version": "1.0",
            "protocol_id": E11_SUPPLEMENT_ID,
            "execution_revision": E11_SUPPLEMENT_EXECUTION_REVISION,
            "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
            "layout_status": "pass",
            "canvas_width_px": 2070,
            "canvas_height_px": 1188,
            "footer_bbox": {"x0_px": 207.0, "y0_px": 40.0, "x1_px": 1800.0, "y1_px": 90.0},
            "x_tick_bboxes": [
                {"x0_px": 200.0, "y0_px": 250.0, "x1_px": 400.0, "y1_px": 300.0},
                {"x0_px": 600.0, "y0_px": 250.0, "x1_px": 800.0, "y1_px": 300.0},
                {"x0_px": 1000.0, "y0_px": 250.0, "x1_px": 1200.0, "y1_px": 300.0},
                {"x0_px": 1400.0, "y0_px": 250.0, "x1_px": 1700.0, "y1_px": 300.0},
            ],
            "footer_to_tick_gap_px": 160.0,
            "required_footer_to_tick_gap_px": 23.76,
            "png_bottom_guard_min_rgb": 1.0,
            "png_bottom_guard_rows": 12,
            "png_bytes": (output / "primary_chart.png").stat().st_size,
            "svg_bytes": (output / "primary_chart.svg").stat().st_size,
        },
    )
    write_figure_manifest(
        output,
        experiment_id="E11",
        evidence_tier="formal_model_posthoc",
        figures=[
            {
                "id": "e11_posthoc_asr_by_pattern",
                "title": "Post-hoc ASR by pattern",
                "role": "primary",
                "order": 0,
                "chart_type": "grouped_bar_with_wilson_95ci",
                "caption": "Six cases per cell; independent post-hoc denominator.",
                "files": {
                    "data": "primary_chart_data.csv",
                    "png": "primary_chart.png",
                    "svg": "primary_chart.svg",
                },
                "metrics": ["ASR"],
                "grain": ["pattern", "condition_id"],
                "uncertainty": [{"method": "Wilson score interval", "confidence": 0.95}],
                "warnings": [
                    "Post-hoc protocol amendment; pre_registered=false; excluded from original E11 denominator; "
                    "visualization_revision=2."
                ],
            }
        ],
    )
    artifact_paths = [
        output / name
        for name in (
            "metrics.csv",
            "statistics.json",
            "analysis.md",
            "raw_run_index.json",
            "case_replays.json",
            "primary_chart_data.csv",
            "primary_chart_layout.json",
            "primary_chart.png",
            "primary_chart.svg",
            "figure_manifest.json",
        )
    ]
    manifest = {
        "schema_version": "1.0",
        "protocol_id": E11_SUPPLEMENT_ID,
        "experiment_id": "E11",
        "amendment_type": "posthoc_protocol_amendment",
        "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
        "execution_revision": E11_SUPPLEMENT_EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": E11_SUPPLEMENT_DENOMINATOR_POLICY,
        "status": "completed",
        "evidence_tier": "formal_model_posthoc",
        "model": "qwen3:4b-instruct",
        "case_count": 24,
        "logical_run_count": 48,
        "conditions": ["posthoc_off", "posthoc_full"],
        "pattern_counts": {pattern: 6 for pattern in sorted(E11_SUPPLEMENT_PATTERNS)},
        "source_execution_manifest": execution,
        "source_execution_manifest_path": execution_path.relative_to(root).as_posix(),
        "source_execution_manifest_sha256": _hash(execution_path),
        "artifacts": [
            {
                "path": path.relative_to(output).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash(path),
            }
            for path in artifact_paths
        ],
    }
    _write_json(output / "manifest.json", manifest)
    return output


def _make_repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    evidence = root / "evidence"
    registry_path = root / "experiments" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    evidence.mkdir()
    freeze_path = root / "outputs" / "experiments" / "blind_freeze_v3.json"
    threshold_path = root / "outputs" / "experiments" / "E13" / "frozen_thresholds.json"
    program_path = root / "outputs" / "experiments" / "program_manifest_final_v3.json"
    e17_source_path = (
        root / "outputs" / "experiments" / "e17_source_index_corrected_v2.json"
    )
    e17_coverage = {
        "status": "pass",
        "logical_run_count": 10,
        "duplicate_logical_run_count": 0,
        "duplicate_logical_step_count": 0,
    }
    threshold_path.parent.mkdir(parents=True)
    _write_json(freeze_path, {"schema_version": "fixture", "status": "frozen"})
    _write_json(
        threshold_path,
        {"schema_version": "fixture", "ask_threshold": 0.5, "deny_threshold": 0.8},
    )
    _write_json(
        program_path,
        {
            "schema_version": "fixture",
            "status": "completed",
            "stages": {
                stage: {"status": "completed"}
                for stage in ("main", "derived", "stability")
            },
        },
    )
    _write_json(
        e17_source_path,
        {
            "schema_version": "2.0",
            "experiment_id": "E17",
            "source_mode": "formal_program_corrected_context",
            "coverage": e17_coverage,
        },
    )
    e17_source_record = {
        "path": e17_source_path.relative_to(root).as_posix(),
        "sha256": _hash(e17_source_path),
    }
    entries = []
    for experiment_id in EXPERIMENT_IDS:
        bundle = evidence / experiment_id
        bundle.mkdir()
        bundle_data = _data_files(experiment_id)
        if experiment_id in {f"E{index}" for index in range(1, 13)} | {"E15"}:
            statistics = bundle_data.get("statistics.json")
            assert isinstance(statistics, dict)
            statistics["evidence_tier"] = "formal_model_only"
        for name, value in bundle_data.items():
            _materialize_file(bundle / name, value)
        figure_data = bundle / "fixture_figure_data.csv"
        _write_csv(figure_data, [{"x": 1, "value": 1}])
        (bundle / "fixture.png").write_bytes(b"synthetic-png-fixture")
        (bundle / "fixture.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
        tier = {
            "E0": "historical_diagnostic_only",
            "E9": "formal_context_correction_v2",
            "E13": "validation_calibration",
            "E14": "formal_context_correction_v2",
            "E16": "formal_dedicated",
            "E17": "human_adjudicated_formal",
        }.get(experiment_id, "formal_model")
        write_figure_manifest(
            bundle,
            experiment_id=experiment_id,
            evidence_tier=tier,
            figures=[
                {
                    "id": "fixture",
                    "title": "Fixture",
                    "role": "diagnostic",
                    "order": 0,
                    "chart_type": "fixture",
                    "caption": "Synthetic fixture only.",
                    "files": {"data": figure_data.name, "png": "fixture.png", "svg": "fixture.svg"},
                    "metrics": ["value"],
                    "grain": ["fixture"],
                    "uncertainty": [],
                    "warnings": ["synthetic input fixture"],
                }
            ],
        )
        data_paths = [path for path in bundle.iterdir() if path.is_file()]
        artifacts = [
            {
                "path": str(path.resolve()),
                "kind": "raw_log" if path.name == "raw_attempts.jsonl" else "fixture",
                "bytes": path.stat().st_size,
                "sha256": _hash(path),
            }
            for path in data_paths
        ]
        manifest = {
            "schema_version": "2.0",
            "experiment_id": experiment_id,
            "status": "completed",
            "git": {"commit": "fixture-commit"},
            "dataset": {"sha256": "fixture-dataset"},
            "models": [] if experiment_id in {"E0", "E13", "E17"} else ["qwen3:4b-instruct"],
            "configuration": (
                {
                    "source_mode": "formal_program_corrected_context",
                    "source_index": e17_source_record,
                    "coverage": e17_coverage,
                    "registry_eligible": True,
                }
                if experiment_id == "E17"
                else {"evidence_tier": "formal_model_only"}
                if experiment_id in {f"E{index}" for index in range(1, 13)} | {"E15"}
                else {}
            ),
            "progress": {"expected_runs": 1, "completed_runs": 1, "failed_jobs": 0, "unresolved_cases": 0},
            "artifacts": artifacts,
        }
        if experiment_id == "E17":
            manifest["plan"] = {
                "source_mode": "formal_program_corrected_context",
                "source_index": e17_source_record,
                "coverage": e17_coverage,
                "candidate_count": 1,
            }
        if experiment_id in {"E9", "E14"}:
            manifest.update(
                {
                    "protocol_id": "CONTEXT_CORRECTION_V2",
                    "workload_revision": "r2",
                    "denominator_policy": "V2_only_old_V3_excluded",
                    "validity_checks": {"status": "pass", "checks": {"fixture": True}},
                    "configuration": {
                        "protocol_id": "CONTEXT_CORRECTION_V2",
                        "workload_revision": "r2",
                        "evidence_tier": "formal_context_correction_v2",
                    },
                }
            )
        if experiment_id == "E16":
            plan_hash = "e" * 64
            configuration_hash = "3" * 64
            thresholds_hash = _hash(threshold_path)
            manifest.update(
                {
                    "evidence_tier": "formal_dedicated",
                    "denominator_scope": "E16_fixture_dedicated_attempts_only",
                    "excluded_from_main_matrix": True,
                    "plan_hash": plan_hash,
                    "configuration_hash": configuration_hash,
                    "configuration": {
                        "model": "qwen3:4b-instruct",
                        "split": "validation",
                        "rounds": 3,
                        "seed": 1601,
                        "temperature": 0.2,
                        "plan_hash": plan_hash,
                        "config_hash": configuration_hash,
                        "thresholds_sha256": thresholds_hash,
                    },
                    "plan": {
                        "plan_hash": plan_hash,
                        "denominator_scope": "E16_fixture_dedicated_attempts_only",
                        "excluded_from_main_matrix": True,
                        "expected_attempts": 2,
                        "thresholds_sha256": thresholds_hash,
                        "mutation_policy": "predefined_text_and_format_only",
                    },
                    "progress": {
                        "expected_runs": 2,
                        "completed_runs": 2,
                        "failed_jobs": 0,
                        "unresolved_cases": 0,
                    },
                }
            )
            manifest["artifact_hashes"] = {path.name: _hash(path) for path in data_paths}
        manifest_path = bundle / "manifest.json"
        _write_json(manifest_path, manifest)
        required = [str(manifest_path.resolve())]
        if experiment_id == "E0":
            required += [str((bundle / "measurement_audit.json").resolve()), str((bundle / "historical_metrics.csv").resolve())]
        elif experiment_id == "E13":
            required += [str((bundle / "threshold_scan.csv").resolve()), str((bundle / "frozen_thresholds.json").resolve())]
        elif experiment_id == "E14":
            required += [
                str((bundle / "performance.csv").resolve()),
                str((bundle / "latency_by_context_data.csv").resolve()),
                str((bundle / "throughput_by_concurrency_data.csv").resolve()),
                str((bundle / "statistics.json").resolve()),
            ]
        elif experiment_id == "E16":
            required += [str((bundle / "adaptive_rounds.csv").resolve()), str((bundle / "statistics.json").resolve())]
        elif experiment_id == "E17":
            required += [str((bundle / "failure_taxonomy.csv").resolve()), str((bundle / "reviewer_agreement.json").resolve())]
        else:
            required += [str((bundle / "metrics.csv").resolve()), str((bundle / "statistics.json").resolve())]
        entry = {
                "id": experiment_id,
                "name": f"fixture_{experiment_id}",
                "status": "completed",
                "required_artifacts": required,
                "evidence": [
                    str(manifest_path.resolve()),
                    *(
                        [str(e17_source_path.resolve())]
                        if experiment_id == "E17"
                        else []
                    ),
                    *[str(path.resolve()) for path in data_paths],
                ],
                "error": "",
            }
        if experiment_id == "E17":
            entry.update(
                {
                    "primary_manifest": str(manifest_path.resolve()),
                    "completion_registrar": "scripts/register_e17_evidence.py",
                    "source_index": e17_source_record,
                }
            )
        entries.append(entry)
    _write_json(registry_path, {"schema_version": "1.0", "experiments": entries})
    audit_path = root / "agent" / "audits" / "final_result_integrity.json"
    audit_path.parent.mkdir(parents=True)
    main_jobs = [
        {
            "job_id": "fixture-main-alpha",
            "model": "model-alpha",
            "status": "completed",
            "expected_runs": 50,
            "logical_runs": 50,
            "log_rows": 180,
            "parse_failure_rows": 1,
            "parse_failure_runs": 1,
        },
        {
            "job_id": "fixture-main-beta",
            "model": "model-beta",
            "status": "completed",
            "expected_runs": 10,
            "logical_runs": 10,
            "log_rows": 20,
            "parse_failure_rows": 4,
            "parse_failure_runs": 4,
        },
    ]
    _write_json(
        audit_path,
        {
            "schema_version": "1.0",
            "status": "pass",
            "scope": {
                "program_manifest": str(program_path.resolve()),
                "program_manifest_sha256": _hash(program_path),
                "blind_freeze": str(freeze_path.resolve()),
                "blind_freeze_sha256": _hash(freeze_path),
                "thresholds": str(threshold_path.resolve()),
                "thresholds_sha256": _hash(threshold_path),
                "stages": ["main", "derived", "stability"],
            },
            "stages": [
                {
                    "stage": "main",
                    "status": "completed",
                    "scanned": True,
                    "job_count": len(main_jobs),
                    "expected_runs": 60,
                    "logical_runs": 60,
                    "log_rows": 200,
                    "parse_failure_rows": 5,
                    "parse_failure_runs": 5,
                    "jobs": main_jobs,
                },
                {"stage": "derived", "status": "completed", "scanned": True},
                {"stage": "stability", "status": "completed", "scanned": True},
            ],
            "finding_counts": {"errors": 0, "warnings": 0},
            "findings": [],
        },
    )
    _make_e11_supplement(root)
    return root, registry_path


def _rehash_artifact(bundle_manifest: Path, artifact_path: Path) -> None:
    manifest = json.loads(bundle_manifest.read_text(encoding="utf-8"))
    for artifact in manifest["artifacts"]:
        if Path(artifact["path"]).resolve() == artifact_path.resolve():
            artifact["bytes"] = artifact_path.stat().st_size
            artifact["sha256"] = _hash(artifact_path)
    _write_json(bundle_manifest, manifest)


def test_full_synthetic_program_builds_reproducible_final_bundle(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    output = root / "final"
    result = generate_final_analysis(
        registry_path=registry, repository_root=root, output_dir=output
    )

    assert result["status"] == "completed"
    assert result["chart_count"] == 13
    assert (output / "analysis.md").is_file()
    analysis = (output / "analysis.md").read_text(encoding="utf-8")
    assert analysis.count("**结果解读：**") == 13
    assert "pre_registered=false" in analysis
    assert "不合并分母" in analysis
    assert (output / "acceptance_matrix.csv").is_file()
    assert (output / "failure_summary.csv").is_file()
    assert (output / "result_integrity_audit.json").is_file()
    assert (output / "main_parse_quality.json").is_file()
    assert (output / "e9_data_quality.json").is_file()
    assert (output / "e16_provenance.json").is_file()
    figure_manifest = load_figure_manifest(output, expected_experiment_id="E18")
    assert len(figure_manifest["figures"]) == 13
    for chart_id in (figure["id"] for figure in figure_manifest["figures"]):
        assert (output / f"{chart_id}.csv").stat().st_size > 0
        assert (output / f"{chart_id}.png").stat().st_size > 100
        assert (output / f"{chart_id}.svg").stat().st_size > 100
        layout = json.loads((output / f"{chart_id}.layout.json").read_text(encoding="utf-8"))
        assert layout["layout_status"] == "pass"
        assert layout["footer_tick_overlap_count"] == 0
        assert layout["x_tick_overlap_count"] == 0
        assert layout["y_tick_overlap_count"] == 0
        assert layout["manual_review_still_required"] is True
    main_rows = list(csv.DictReader((output / "main_defense_effect.csv").open(encoding="utf-8-sig")))
    assert {row["source_experiment"] for row in main_rows} == {"E1", "E12"}
    assert {
        "Utility · overall TCR",
        "Utility · legitimate-tool TCR",
        "Utility · benign call FPR",
        "Utility · benign ASK rate",
    }.issubset({row["panel"] for row in main_rows})
    e9_quality = json.loads((output / "e9_data_quality.json").read_text(encoding="utf-8"))
    assert e9_quality["overall"]["unresolved_runs"] == 5
    assert e9_quality["overall"]["case_runs"] == 20
    assert "5/20=25.0%" in analysis
    executive = json.loads((output / "executive_summary.json").read_text(encoding="utf-8"))
    assert executive["overall_acceptance_status"] == "pass"
    assert all(target["source_experiments"] != "E0" for target in executive["targets"])
    assert all(target["source_experiments"] not in {"E16", "E17"} for target in executive["targets"])
    assert executive["excluded_evidence"]["E0"].startswith("historical diagnostic")
    dsr_target = next(target for target in executive["targets"] if target["target_id"] == "A02")
    assert dsr_target["uncertainty_assessment"] == "point_estimate_pass_ci_inconclusive"
    final_manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    audit_anchor = final_manifest["result_integrity_audit"]
    assert audit_anchor["stages"] == ["main", "derived", "stability"]
    assert audit_anchor["source_sha256"] == audit_anchor["snapshot_sha256"]
    assert _hash(output / audit_anchor["snapshot_path"]) == audit_anchor["source_sha256"]
    parse_quality = json.loads((output / "main_parse_quality.json").read_text(encoding="utf-8"))
    assert parse_quality["overall"]["step_row"]["successes"] == 195
    assert parse_quality["overall"]["step_row"]["status_against_reference"] == "pass"
    assert parse_quality["overall"]["run"]["successes"] == 55
    assert parse_quality["overall"]["run"]["status_against_reference"] == "fail"
    assert parse_quality["models_below_reference"] == {
        "step_row": ["model-beta"],
        "run": ["model-beta"],
    }
    provenance = json.loads((output / "e16_provenance.json").read_text(encoding="utf-8"))
    assert provenance["runtime_observation"] == {
        "sandbox_runtime_version": "isolated-tool-sandbox-fixture-v1",
        "attempts": 2,
        "log_rows": 2,
        "direct_field_versions": ["isolated-tool-sandbox-fixture-v1"],
        "model_config_field_versions": ["isolated-tool-sandbox-fixture-v1"],
        "missing_runtime_field_rows": 0,
        "mismatch_rows": 0,
    }
    assert provenance["source_manifest"]["manifest_schema_version"] == "2.0"
    assert provenance["excluded_from_main_matrix"] is True
    assert "model-beta" in analysis
    assert "isolated-tool-sandbox-fixture-v1" in analysis
    for artifact in final_manifest["artifacts"]:
        path = output / artifact["path"]
        assert path.stat().st_size == artifact["bytes"]
        assert _hash(path) == artifact["sha256"]
    figure_anchor = [
        artifact
        for artifact in final_manifest["artifacts"]
        if artifact["kind"] == "figure_manifest"
    ]
    assert [artifact["path"] for artifact in figure_anchor] == ["figure_manifest.json"]
    boundary = final_manifest["e11_scope_boundary"]
    assert boundary["posthoc_supplement"]["pre_registered"] is False
    assert boundary["posthoc_supplement"]["visualization_revision"] == 2
    assert boundary["claim_boundary"] == {
        "acceptance_matrix_changed": False,
        "comparison_policy": "faceted_descriptive_comparison_only",
        "denominators_pooled": False,
        "original_e11_primary_manifest_replaced": False,
        "retroactive_preregistration_claimed": False,
    }
    ledger_rows = list(
        csv.DictReader((output / "input_artifact_ledger.csv").open(encoding="utf-8-sig"))
    )
    assert any(
        row["experiment_id"] == "PROGRAM" and row["source"] == "result_integrity_audit"
        for row in ledger_rows
    )
    assert any(
        row["experiment_id"] == E11_SUPPLEMENT_ID
        and row["source"] == "e11_posthoc_supplement_manifest"
        for row in ledger_rows
    )

    dashboard = load_dashboard_sources(bundle_paths=[output])
    assert dashboard["warnings"] == []
    assert len(dashboard["figures"]) == 13


def test_incomplete_registry_rejected_before_output_creation(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["experiments"][1]["status"] = "running"
    _write_json(registry, payload)
    output = root / "never-created"

    with pytest.raises(FinalAnalysisError, match="requires E0-E17 completed"):
        generate_final_analysis(registry_path=registry, repository_root=root, output_dir=output)
    assert not output.exists()


def test_artifact_hash_drift_rejected_before_output_creation(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    metrics = root / "evidence" / "E5" / "metrics.csv"
    metrics.write_text(metrics.read_text(encoding="utf-8-sig") + "tamper\n", encoding="utf-8")
    output = root / "never-created"

    with pytest.raises(FinalAnalysisError, match="artifact (size|hash) drift"):
        generate_final_analysis(registry_path=registry, repository_root=root, output_dir=output)
    assert not output.exists()


def test_e11_posthoc_supplement_boundary_and_hash_drift_are_rejected(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    supplement = root / "outputs" / "experiments" / "E11_posthoc_amendment_v1"
    bundle, ledger = validate_e11_supplement(supplement, repository_root=root)
    assert bundle.manifest["pre_registered"] is False
    assert bundle.manifest["visualization_revision"] == 2
    assert bundle.manifest["logical_run_count"] == 48
    assert any(row["source"] == "e11_posthoc_amendment_freeze" for row in ledger)

    metrics = supplement / "metrics.csv"
    metrics.write_text(metrics.read_text(encoding="utf-8-sig") + "tamper\n", encoding="utf-8")
    output = root / "never-created-posthoc"
    with pytest.raises(FinalAnalysisError, match="artifact (size|hash) drift"):
        generate_final_analysis(
            registry_path=registry, repository_root=root, output_dir=output
        )
    assert not output.exists()


def test_e11_chart_layout_validator_rejects_footer_tick_overlap(tmp_path: Path) -> None:
    root, _registry = _make_repository(tmp_path)
    supplement = root / "outputs" / "experiments" / "E11_posthoc_amendment_v1"
    files = {
        name: supplement / name
        for name in (
            "primary_chart_layout.json",
            "primary_chart.png",
            "primary_chart.svg",
        )
    }
    _validate_supplement_chart_layout(files)
    layout = json.loads(files["primary_chart_layout.json"].read_text(encoding="utf-8"))
    layout["footer_bbox"]["y1_px"] = 245.0
    layout["footer_to_tick_gap_px"] = 5.0
    _write_json(files["primary_chart_layout.json"], layout)
    with pytest.raises(FinalAnalysisError, match="footer overlaps or crowds"):
        _validate_supplement_chart_layout(files)


def test_invalid_denominator_and_stub_contamination_are_rejected(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    metrics = root / "evidence" / "E11" / "metrics.csv"
    rows = list(csv.DictReader(metrics.open(encoding="utf-8-sig", newline="")))
    rows[0]["FPR"] = "0"
    _write_csv(metrics, rows)
    _rehash_artifact(root / "evidence" / "E11" / "manifest.json", metrics)
    with pytest.raises(FinalAnalysisError, match="zero denominator must be encoded as NA"):
        validate_inputs(registry, repository_root=root)

    root2, registry2 = _make_repository(tmp_path / "stub_case")
    manifest_path = root2 / "evidence" / "E5" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["models"] = ["stub"]
    _write_json(manifest_path, manifest)
    with pytest.raises(FinalAnalysisError, match="prohibited model"):
        validate_inputs(registry2, repository_root=root2)


def test_e17_synthetic_review_is_not_formal_claim_evidence(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    manifest_path = root / "evidence" / "E17" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["configuration"]["source_mode"] = "synthetic_fixture"
    manifest["configuration"]["registry_eligible"] = False
    _write_json(manifest_path, manifest)

    with pytest.raises(
        FinalAnalysisError, match="source_mode=formal_program_corrected_context"
    ):
        validate_inputs(registry, repository_root=root)


def test_e17_corrected_source_hash_and_dedicated_registrar_are_required(
    tmp_path: Path,
) -> None:
    root, registry = _make_repository(tmp_path)
    source = root / "outputs" / "experiments" / "e17_source_index_corrected_v2.json"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(FinalAnalysisError, match="source_index hash mismatch"):
        validate_inputs(registry, repository_root=root)

    root2, registry2 = _make_repository(tmp_path / "second")
    payload = json.loads(registry2.read_text(encoding="utf-8"))
    e17 = next(item for item in payload["experiments"] if item["id"] == "E17")
    e17.pop("completion_registrar")
    _write_json(registry2, payload)
    with pytest.raises(FinalAnalysisError, match="dedicated completion registrar"):
        validate_inputs(registry2, repository_root=root2)


def test_e17_corrected_source_loader_failure_blocks_final_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, registry = _make_repository(tmp_path)

    def rejected(_path: Path) -> dict:
        raise ValueError("synthetic corrected coverage failure")

    monkeypatch.setattr(final_analysis_module.e17_review, "load_source_index", rejected)
    with pytest.raises(FinalAnalysisError, match="failed full validation"):
        validate_inputs(registry, repository_root=root)


def test_e13_recorded_status_string_is_not_used_for_acceptance(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    frozen = root / "evidence" / "E13" / "frozen_thresholds.json"
    payload = json.loads(frozen.read_text(encoding="utf-8"))
    payload["status"] = "fail_targets"
    _write_json(frozen, payload)
    _rehash_artifact(root / "evidence" / "E13" / "manifest.json", frozen)

    _, bundles, _ = validate_inputs(registry, repository_root=root)
    matrix = build_acceptance_matrix(bundles)
    calibration = next(row for row in matrix if row["target_id"] == "A00")
    assert calibration["status"] == "pass"
    assert "Recorded status='fail_targets'" in calibration["limitations"]


def test_e13_acceptance_is_recomputed_from_selected_scan_counts(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    bundle = root / "evidence" / "E13"
    scan = bundle / "threshold_scan.csv"
    rows = list(csv.DictReader(scan.open(encoding="utf-8-sig")))
    selected = next(
        row
        for row in rows
        if float(row["ask_threshold"]) == 0.5 and float(row["deny_threshold"]) == 0.8
    )
    selected.update(
        {
            "precision": "0.8",
            "precision_numerator": "8",
            "precision_denominator": "10",
            "precision_ci_low": "0.49016247153664183",
            "precision_ci_high": "0.9433178485456247",
        }
    )
    _write_csv(scan, rows)
    frozen = bundle / "frozen_thresholds.json"
    payload = json.loads(frozen.read_text(encoding="utf-8"))
    payload["status"] = "targets_met"
    payload["target_checks"]["precision"].update({"value": 0.8, "passed": False})
    _write_json(frozen, payload)
    manifest = bundle / "manifest.json"
    _rehash_artifact(manifest, scan)
    _rehash_artifact(manifest, frozen)

    _, bundles, _ = validate_inputs(registry, repository_root=root)
    calibration = next(
        row for row in build_acceptance_matrix(bundles) if row["target_id"] == "A00"
    )
    assert calibration["status"] == "fail"
    assert calibration["uncertainty_assessment"] == "deterministic_rule_fail"


def test_e9_unresolved_summary_rejects_drifted_rate_counts(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    context = root / "evidence" / "E9" / "context_position.csv"
    rows = list(csv.DictReader(context.open(encoding="utf-8-sig")))
    rows[0]["UnresolvedRate_numerator"] = "0"
    _write_csv(context, rows)
    _rehash_artifact(root / "evidence" / "E9" / "manifest.json", context)
    # The generic k/n/value admission audit is the earliest valid rejection
    # point; E9's dedicated recomputation never consumes internally drifted rows.
    with pytest.raises(FinalAnalysisError, match="UnresolvedRate.*inconsistent"):
        validate_inputs(registry, repository_root=root)


def test_registry_path_escape_is_rejected(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("not repository evidence", encoding="utf-8")
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["experiments"][0]["evidence"].append(str(outside.resolve()))
    _write_json(registry, payload)

    with pytest.raises(FinalAnalysisError, match="escapes repository root"):
        validate_inputs(registry, repository_root=root)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("failed_status", "status is not pass"),
        ("partial_scope", "must cover exactly main, derived, stability"),
        ("counter_drift", "log_rows disagrees with its job summaries"),
    ],
)
def test_final_integrity_audit_gate_rejects_nonfinal_or_inconsistent_evidence(
    tmp_path: Path, mutation: str, message: str
) -> None:
    root, registry = _make_repository(tmp_path)
    audit = root / "agent" / "audits" / "final_result_integrity.json"
    payload = json.loads(audit.read_text(encoding="utf-8"))
    if mutation == "failed_status":
        payload["status"] = "fail"
    elif mutation == "partial_scope":
        payload["scope"]["stages"] = ["main"]
    else:
        payload["stages"][0]["log_rows"] += 1
    _write_json(audit, payload)
    output = root / "never-created"

    with pytest.raises(FinalAnalysisError, match=message):
        generate_final_analysis(
            registry_path=registry, repository_root=root, output_dir=output
        )
    assert not output.exists()


def test_final_integrity_audit_rejects_stale_program_hash(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    program = root / "outputs" / "experiments" / "program_manifest_final_v3.json"
    payload = json.loads(program.read_text(encoding="utf-8"))
    payload["post_audit_change"] = True
    _write_json(program, payload)

    with pytest.raises(FinalAnalysisError, match="program-manifest hash is stale"):
        generate_final_analysis(
            registry_path=registry,
            repository_root=root,
            output_dir=root / "never-created",
        )


@pytest.mark.parametrize("mutation", ["missing", "mismatch"])
def test_e16_runtime_provenance_rejects_missing_or_mismatched_fields(
    tmp_path: Path, mutation: str
) -> None:
    root, registry = _make_repository(tmp_path)
    raw = root / "evidence" / "E16" / "raw_attempts.jsonl"
    rows = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()]
    if mutation == "missing":
        del rows[0]["logs"][0]["sandbox_runtime_version"]
    else:
        rows[0]["logs"][0]["model_config"]["sandbox_runtime_version"] = "different-runtime"
    raw.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    manifest_path = root / "evidence" / "E16" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for artifact in manifest["artifacts"]:
        if Path(artifact["path"]).name == raw.name:
            artifact["bytes"] = raw.stat().st_size
            artifact["sha256"] = _hash(raw)
    manifest["artifact_hashes"][raw.name] = _hash(raw)
    _write_json(manifest_path, manifest)

    with pytest.raises(FinalAnalysisError, match="runtime provenance is incomplete or inconsistent"):
        generate_final_analysis(
            registry_path=registry,
            repository_root=root,
            output_dir=root / "never-created",
        )
