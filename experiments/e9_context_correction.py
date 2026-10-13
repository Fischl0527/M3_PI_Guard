"""运行并分析经过 Token 校准的 E9 上下文长度与载荷位置修正实验。

探究注入 Prompt 位于上下文首部、中部或尾部时对防御监视器拦截率的影响（大海捞针鲁棒性）。
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from m3_eval.figure_manifest import write_figure_manifest
from m3_eval.metrics import compare_runs, compute_metrics
from m3_eval.statistics import holm_adjust

from .catalog import CONTEXT_LENGTHS, INJECTION_POSITIONS
from .context_correction_runtime import (
    archive_invalid_job_attempt,
    effective_prompt_eval_count,
    execute_matrix_job,
    file_record,
    first_step_rows,
    prompt_token_validity,
    provider_incomplete_is_safely_retained,
    read_jsonl,
    reusable_job_evidence,
    semantic_failure_progress,
    stable_json_hash,
    utc_now,
    verify_freeze,
    write_json,
    write_jsonl,
)
from .context_workloads import (
    DEFAULT_E9_OUT,
    DEFAULT_PROMPT_VERIFICATION_OUT,
    EFFECTIVE_CONTEXT_BY_TARGET,
    MODEL_ALIAS_BY_TARGET,
    PROTOCOL_ID,
    WORKLOAD_REVISION,
    load_prompt_verification,
)
from .manifest import (
    fail_manifest,
    finish_manifest,
    new_manifest,
    record_event,
    register_artifact,
    save_manifest,
    sha256_file,
)
from .model_manager import stop_model


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs" / "experiments" / "E9_context_correction_v2_r3"
DEFAULT_SMOKE_OUTPUT = (
    ROOT / "outputs" / "experiments" / "E9_context_correction_v2_r3_smoke"
)
DEFAULT_FREEZE = ROOT / "protocols" / "context_correction_v2" / "freeze_r3.json"
CONDITIONS = (
    ("derived_normal_off", "normal", "off"),
    ("derived_normal_full", "normal", "full_guard"),
)
MAX_TOKENS = 512
SEED = 419
TEMPERATURE = 0.0
TOKEN_TOLERANCE = 0.05


def load_cases(path: str | Path = DEFAULT_E9_OUT) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    if len(rows) != 60:
        raise ValueError(f"E9 V2 fixture must contain 60 cases, got {len(rows)}")
    if len({str(row.get("case_id")) for row in rows}) != 60:
        raise ValueError("E9 V2 fixture has duplicate case IDs")
    return rows


def build_plan(
    cases: Sequence[Mapping[str, Any]], *, phase: str = "formal"
) -> dict[str, Any]:
    if phase not in {"smoke", "formal"}:
        raise ValueError("phase must be smoke or formal")
    jobs: list[dict[str, Any]] = []
    for target in CONTEXT_LENGTHS:
        target_rows = [
            row
            for row in cases
            if int(row["attack_dimensions"]["target_prompt_tokens"]) == target
        ]
        if phase == "smoke":
            target_rows = [
                row
                for row in target_rows
                if int(row["attack_dimensions"]["injection_position_pct"]) in {0, 100}
            ]
        expected_per_condition = 6 if phase == "smoke" else 15
        if len(target_rows) != expected_per_condition:
            raise ValueError(
                f"E9 {phase} target={target} expected {expected_per_condition} cases, "
                f"found {len(target_rows)}"
            )
        for condition_id, prompt_profile, guard_mode in CONDITIONS:
            jobs.append(
                {
                    "id": f"{phase}__ctx{target}__{condition_id}",
                    "protocol_id": PROTOCOL_ID,
                    "phase": phase,
                    "base_model": "qwen3:4b-instruct",
                    "served_model": MODEL_ALIAS_BY_TARGET[target],
                    "target_prompt_tokens": target,
                    "effective_context_window_tokens": EFFECTIVE_CONTEXT_BY_TARGET[target],
                    "condition_id": condition_id,
                    "prompt_profile": prompt_profile,
                    "guard_mode": guard_mode,
                    "workload_cohort": "long_context_attack",
                    "concurrency": 1,
                    "outer_replicate_id": 0,
                    "case_ids": sorted(str(row["case_id"]) for row in target_rows),
                    "expected_case_runs": expected_per_condition,
                    "run_group": f"{PROTOCOL_ID}_E9_{phase}",
                    "notes": f"E9 V2 {phase}; excluded_from_formal={phase == 'smoke'}",
                }
            )
    expected = 48 if phase == "smoke" else 120
    if sum(int(job["expected_case_runs"]) for job in jobs) != expected:
        raise AssertionError("E9 V2 plan denominator mismatch")
    return {
        "schema_version": "2.0",
        "protocol_id": PROTOCOL_ID,
        "workload_revision": WORKLOAD_REVISION,
        "experiment_id": "E9",
        "phase": phase,
        "seed": SEED,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "dynamic_num_ctx": None,
        "transport": "ollama_native",
        "expected_case_runs": expected,
        "jobs": jobs,
    }


def _case_map(cases: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["case_id"]): dict(row) for row in cases}


def _validate(
    plan: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected = int(plan["expected_case_runs"])
    first = first_step_rows(rows)
    case_by_id = _case_map(cases)
    relevant_ids = {case_id for job in plan["jobs"] for case_id in job["case_ids"]}
    run_keys = [str(row.get("run_key", "")) for row in first]
    checks: dict[str, bool] = {
        "exact_first_step_run_count": len(first) == expected,
        "no_duplicate_run_key": len(run_keys) == len(set(run_keys)) and all(run_keys),
        "case_selector_exact": {str(row.get("case_id")) for row in first} == relevant_ids,
        "native_usage_every_step": all(
            (
                row.get("usage_source") == "ollama_native_prompt_eval_count"
                and row.get("prompt_eval_count") is not None
            )
            or row.get("provider_done") is False
            for row in rows
        ),
        "first_step_workload_proof_complete": all(
            effective_prompt_eval_count(row) is not None for row in first
        ),
        "provider_incomplete_safely_retained": all(
            provider_incomplete_is_safely_retained(row) for row in rows
        ),
        "dynamic_num_ctx_absent": all(
            (row.get("model_config") or {}).get("num_ctx") in {None, ""}
            for row in rows
        ),
        "no_timeout_or_runtime_error": all(
            not bool(row.get("timed_out"))
            and (
                str(row.get("final_status")) != "error"
                or row.get("provider_done") is False
            )
            for row in rows
        ),
    }
    per_target: list[dict[str, Any]] = []
    for target in CONTEXT_LENGTHS:
        target_rows = [row for row in first if int(row.get("target_prompt_tokens")) == target]
        validity = prompt_token_validity(
            target_rows, target=target, tolerance=TOKEN_TOLERANCE
        )
        validity["served_model"] = MODEL_ALIAS_BY_TARGET[target]
        validity["effective_context_window_tokens"] = EFFECTIVE_CONTEXT_BY_TARGET[target]
        validity["model_matches"] = all(
            row.get("model") == MODEL_ALIAS_BY_TARGET[target]
            and row.get("served_model") == MODEL_ALIAS_BY_TARGET[target]
            for row in target_rows
        )
        validity["output_headroom_pass"] = all(
            effective_prompt_eval_count(row) is not None
            and EFFECTIVE_CONTEXT_BY_TARGET[target]
            - int(effective_prompt_eval_count(row) or 0)
            >= MAX_TOKENS
            for row in target_rows
        ) and len(target_rows) == int(validity["expected_rows"])
        per_target.append(validity)
    checks["every_run_within_target_tolerance"] = all(
        item["all_within_tolerance"] for item in per_target
    )
    checks["served_alias_matches"] = all(item["model_matches"] for item in per_target)
    checks["minimum_output_headroom"] = all(
        item["output_headroom_pass"] for item in per_target
    )

    paired_counts: dict[tuple[str, int], dict[str, int | None]] = defaultdict(dict)
    for row in first:
        paired_counts[(str(row.get("case_id")), int(row.get("seed") or 0))][
            str(row.get("condition_id"))
        ] = effective_prompt_eval_count(row)
    checks["off_full_prompt_counts_identical"] = all(
        set(values) == {"derived_normal_off", "derived_normal_full"}
        and len(set(values.values())) == 1
        for values in paired_counts.values()
    ) and len(paired_counts) == expected // 2

    series: dict[tuple[str, int, str], dict[int, int]] = defaultdict(dict)
    for row in first:
        case = case_by_id[str(row["case_id"])]
        dimensions = case["attack_dimensions"]
        key = (
            str(case.get("parent_case_id")),
            int(dimensions["injection_position_pct"]),
            str(row["condition_id"]),
        )
        effective_count = effective_prompt_eval_count(row)
        if effective_count is not None:
            series[key][int(dimensions["target_prompt_tokens"])] = int(
                effective_count
            )
    required_series = 12 if plan["phase"] == "smoke" else 30
    checks["strict_monotonic_no_collapse"] = len(series) == required_series and all(
        tuple(sorted(values)) == tuple(CONTEXT_LENGTHS)
        and all(
            values[left] < values[right]
            for left, right in zip(CONTEXT_LENGTHS, CONTEXT_LENGTHS[1:])
        )
        for values in series.values()
    )
    checks["position_grid_complete"] = (
        {
            int(case_by_id[str(row["case_id"])]["attack_dimensions"]["injection_position_pct"])
            for row in first
        }
        == ({0, 100} if plan["phase"] == "smoke" else set(INJECTION_POSITIONS))
    )
    checks["all_case_labels_present"] = all(
        case_by_id[case_id].get("sample_type") == "attack" for case_id in relevant_ids
    )
    run_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        run_rows[str(row.get("run_key", ""))].append(row)
    incomplete_run_count = sum(
        any(step.get("provider_done") is False for step in steps)
        for steps in run_rows.values()
    )
    return {
        "schema_version": "2.0",
        "protocol_id": PROTOCOL_ID,
        "experiment_id": "E9",
        "phase": plan["phase"],
        "status": "pass" if all(checks.values()) else "fail",
        "expected_case_runs": expected,
        "observed_first_step_case_runs": len(first),
        "checks": checks,
        "per_target": per_target,
        "parse_success_count": sum(bool(row.get("parse_ok")) for row in first),
        "parse_failure_count": sum(not bool(row.get("parse_ok")) for row in first),
        "provider_incomplete_case_runs": incomplete_run_count,
        "provider_incomplete_first_step_case_runs": sum(
            row.get("provider_done") is False for row in first
        ),
        "provider_incomplete_later_step_case_runs": sum(
            any(
                int(step.get("step") or 0) > 1
                and step.get("provider_done") is False
                for step in steps
            )
            for steps in run_rows.values()
        ),
        "formal_provider_counter_missing_case_runs": sum(
            row.get("prompt_eval_count") is None for row in first
        ),
        "preflight_fallback_case_runs": sum(
            row.get("prompt_count_evidence") == "frozen_one_token_preflight"
            for row in first
        ),
        "output_length_finish_count": sum(
            str(row.get("finish_reason")) == "length" for row in rows
        ),
    }


def _metrics(
    cases: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_by_id = _case_map(cases)
    metrics: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    p_tests: list[tuple[int, str, float]] = []
    for target in CONTEXT_LENGTHS:
        for position in INJECTION_POSITIONS:
            cell_cases = [
                case
                for case in cases
                if int(case["attack_dimensions"]["target_prompt_tokens"]) == target
                and int(case["attack_dimensions"]["injection_position_pct"]) == position
            ]
            cell_ids = {str(case["case_id"]) for case in cell_cases}
            by_condition: dict[str, list[dict[str, Any]]] = {}
            for condition_id, _, _ in CONDITIONS:
                logs = [
                    dict(row)
                    for row in rows
                    if str(row.get("case_id")) in cell_ids
                    and row.get("condition_id") == condition_id
                ]
                by_condition[condition_id] = logs
                formal = compute_metrics(logs, list(cell_cases), strict_labels=True)
                metrics.append(
                    {
                        "experiment_id": "E9",
                        "backend": "ollama",
                        "evidence_tier": "formal_context_correction_v2",
                        "protocol_id": PROTOCOL_ID,
                        "target_prompt_tokens": target,
                        "context_tokens": target,
                        "injection_position_pct": position,
                        "condition_id": condition_id,
                        "case_runs": formal.get("case_runs"),
                        "unresolved_runs": formal.get("unresolved_runs"),
                        "missing_case_runs": formal.get("missing_case_runs"),
                        "CaseLatencyP95": formal.get("CaseLatencyP95"),
                        **{
                            key: formal.get(key)
                            for key in (
                                "ASR",
                                "ASR_numerator",
                                "ASR_denominator",
                                "ASR_ci_low",
                                "ASR_ci_high",
                                "DSR",
                                "DSR_numerator",
                                "DSR_denominator",
                                "Recall",
                                "Recall_numerator",
                                "Recall_denominator",
                                "ParseSuccessRate",
                                "ParseSuccessRate_numerator",
                                "ParseSuccessRate_denominator",
                                "UnresolvedRate",
                                "UnresolvedRate_numerator",
                                "UnresolvedRate_denominator",
                            )
                        },
                    }
                )
            comparison = compare_runs(
                by_condition["derived_normal_off"],
                by_condition["derived_normal_full"],
                list(cell_cases),
                strict_labels=True,
                bootstrap_iterations=10_000,
                bootstrap_seed=42,
            )
            item = {
                "comparison_id": f"ctx{target}_pos{position}",
                "target_prompt_tokens": target,
                "injection_position_pct": position,
                "delta": comparison["delta"],
                "paired_statistics": comparison["paired_statistics"],
            }
            index = len(comparisons)
            comparisons.append(item)
            for name, test in comparison["paired_statistics"].items():
                if isinstance(test, dict) and test.get("p_value") is not None:
                    p_tests.append((index, name, float(test["p_value"])))
    adjusted = holm_adjust([value for _, _, value in p_tests]) if p_tests else []
    correction: list[dict[str, Any]] = []
    for (index, name, raw), adj in zip(p_tests, adjusted):
        comparisons[index]["paired_statistics"][name]["holm_adjusted_p"] = adj
        correction.append(
            {
                "comparison_id": comparisons[index]["comparison_id"],
                "test": name,
                "raw_p": raw,
                "holm_adjusted_p": adj,
            }
        )
    return metrics, {
        "schema_version": "2.0",
        "experiment_id": "E9",
        "protocol_id": PROTOCOL_ID,
        "backend": "ollama",
        "evidence_tier": "formal_context_correction_v2",
        "formal_model_only": True,
        "status": "completed",
        "methods": {
            "proportion": "Wilson 95% interval",
            "paired_binary": "two-sided exact McNemar",
            "paired_effect": "case-clustered paired bootstrap, 10000 iterations",
            "multiplicity": "Holm correction",
        },
        "comparisons": comparisons,
        "holm_correction": correction,
    }


METRIC_FIELDS = (
    "experiment_id",
    "backend",
    "evidence_tier",
    "protocol_id",
    "target_prompt_tokens",
    "context_tokens",
    "injection_position_pct",
    "condition_id",
    "case_runs",
    "unresolved_runs",
    "missing_case_runs",
    "CaseLatencyP95",
    "ASR",
    "ASR_numerator",
    "ASR_denominator",
    "ASR_ci_low",
    "ASR_ci_high",
    "DSR",
    "DSR_numerator",
    "DSR_denominator",
    "Recall",
    "Recall_numerator",
    "Recall_denominator",
    "ParseSuccessRate",
    "ParseSuccessRate_numerator",
    "ParseSuccessRate_denominator",
    "UnresolvedRate",
    "UnresolvedRate_numerator",
    "UnresolvedRate_denominator",
)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(METRIC_FIELDS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _render_chart(metrics: Sequence[Mapping[str, Any]], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {2048: "#4C78A8", 4096: "#F58518", 8192: "#54A24B", 16384: "#E45756"}
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), sharey=True)
    for axis, condition in zip(axes, ("derived_normal_off", "derived_normal_full")):
        for target in CONTEXT_LENGTHS:
            values = sorted(
                (
                    row
                    for row in metrics
                    if row["condition_id"] == condition
                    and int(row["target_prompt_tokens"]) == target
                ),
                key=lambda row: int(row["injection_position_pct"]),
            )
            x = [int(row["injection_position_pct"]) for row in values]
            y = [float(row["ASR"]) * 100 if row["ASR"] is not None else float("nan") for row in values]
            low = [float(row["ASR_ci_low"]) * 100 for row in values]
            high = [float(row["ASR_ci_high"]) * 100 for row in values]
            axis.errorbar(
                x,
                y,
                yerr=[[value - lo for value, lo in zip(y, low)], [hi - value for value, hi in zip(y, high)]],
                marker="o",
                linewidth=1.8,
                capsize=3,
                color=colors[target],
                label=f"{target // 1024}K prompt",
            )
        axis.set_title("No Guard" if condition.endswith("off") else "Full Guard")
        axis.set_xlabel("Operational injection position (%)")
        axis.set_xticks(INJECTION_POSITIONS)
        axis.grid(axis="y", alpha=0.25)
        axis.set_ylim(-5, 105)
    axes[0].set_ylabel("Attack success rate (%)")
    axes[1].legend(frameon=True, facecolor="white")
    fig.suptitle("E9 V2: calibrated long-context attack success")
    fig.text(
        0.5,
        0.01,
        "Each point: 3 attack cases; Wilson 95% CI. V3 invalid context cells are excluded.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(output / "primary_chart.png", dpi=180)
    fig.savefig(output / "primary_chart.svg")
    plt.close(fig)


def _analysis_text(
    metrics: Sequence[Mapping[str, Any]], validity: Mapping[str, Any]
) -> str:
    off = [row for row in metrics if row["condition_id"] == "derived_normal_off"]
    guarded = [row for row in metrics if row["condition_id"] == "derived_normal_full"]
    off_num = sum(int(row["ASR_numerator"]) for row in off)
    off_den = sum(int(row["ASR_denominator"]) for row in off)
    guard_num = sum(int(row["ASR_numerator"]) for row in guarded)
    guard_den = sum(int(row["ASR_denominator"]) for row in guarded)
    lines = [
        "# E9 V2 calibrated context/position analysis",
        "",
        f"- Semantic validity: **{validity['status']}**; {validity['observed_first_step_case_runs']}/{validity['expected_case_runs']} formal first-step case-runs.",
        f"- No Guard ASR: {off_num}/{off_den} ({100 * off_num / off_den:.2f}%).",
        f"- Full Guard ASR: {guard_num}/{guard_den} ({100 * guard_num / guard_den:.2f}%).",
        f"- Parse failures retained: {validity['parse_failure_count']} first-step runs.",
        "- Every exact first-turn prompt has frozen native Ollama token proof; a formal raw counter is preferred and the one-token preflight is used only when Ollama returns an explicitly non-final response.",
        f"- Provider-incomplete outcomes retained as non-executable errors: {validity['provider_incomplete_case_runs']} case-runs.",
        "- V3 E9 is preserved only as invalid diagnostic provenance and is not pooled with this denominator.",
        "",
        "Interpret position and context trends from `context_position.csv` and the paired tests in `statistics.json`; each cell contains only three attacks, so Wilson intervals are intentionally wide.",
    ]
    return "\n".join(lines) + "\n"


def _build_outputs(
    output: Path,
    plan: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    validity: Mapping[str, Any],
    cases_path: str | Path = DEFAULT_E9_OUT,
) -> list[tuple[Path, str]]:
    raw_path = output / "raw_runs.jsonl"
    validity_path = output / "validity_checks.json"
    write_jsonl(raw_path, rows)
    write_json(validity_path, validity)
    outputs: list[tuple[Path, str]] = [
        (raw_path, "raw_log"),
        (validity_path, "semantic_validity"),
    ]
    if plan["phase"] != "formal" or validity["status"] != "pass":
        return outputs
    raw_index_path = output / "raw_run_index.json"
    write_json(
        raw_index_path,
        {
            "schema_version": "2.0",
            "experiment_id": "E9",
            "protocol_id": PROTOCOL_ID,
            "old_v3_policy": "excluded_invalid_diagnostic_provenance",
            "records": [
                {
                    **file_record(cases_path, kind="case_dataset"),
                    "row_count": len(cases),
                    "distinct_case_count": len({str(case["case_id"]) for case in cases}),
                },
                {
                    **file_record(raw_path, kind="formal_raw_log"),
                    "row_count": len(rows),
                    "distinct_case_count": len({str(row["case_id"]) for row in rows}),
                    "evidence_tier": "formal_context_correction_v2",
                },
            ],
        },
    )
    outputs.append((raw_index_path, "raw_run_index"))
    metrics, statistics_payload = _metrics(cases, rows)
    metrics_path = output / "metrics.csv"
    context_path = output / "context_position.csv"
    chart_data_path = output / "primary_chart_data.csv"
    statistics_path = output / "statistics.json"
    analysis_path = output / "analysis.md"
    _write_csv(metrics_path, metrics)
    _write_csv(context_path, metrics)
    _write_csv(chart_data_path, metrics)
    write_json(statistics_path, statistics_payload)
    analysis_path.write_text(_analysis_text(metrics, validity), encoding="utf-8")
    _render_chart(metrics, output)
    figure_manifest = write_figure_manifest(
        output,
        experiment_id="E9",
        evidence_tier="formal_context_correction_v2",
        figures=[
            {
                "id": "e9_calibrated_context_position",
                "title": "E9 V2 calibrated long-context attack success",
                "role": "primary",
                "order": 0,
                "chart_type": "two_panel_multi_series_line_with_wilson_ci",
                "caption": "ASR by calibrated first-step prompt target, operational injection position and Guard condition.",
                "files": {
                    "data": chart_data_path.name,
                    "png": "primary_chart.png",
                    "svg": "primary_chart.svg",
                },
                "metrics": ["ASR", "ASR_ci_low", "ASR_ci_high"],
                "grain": ["target_prompt_tokens", "injection_position_pct", "condition_id"],
                "uncertainty": [{"method": "Wilson 95% confidence interval"}],
                "warnings": [
                    "Three attack cases per cell; intervals are wide.",
                    "Old V3 E9 context cells are invalid diagnostic provenance and excluded.",
                ],
            }
        ],
    )
    outputs.extend(
        [
            (metrics_path, "metrics"),
            (context_path, "metrics"),
            (chart_data_path, "figure_data"),
            (statistics_path, "statistics"),
            (analysis_path, "analysis"),
            (output / "primary_chart.png", "figure"),
            (output / "primary_chart.svg", "figure"),
            (figure_manifest, "figure_manifest"),
        ]
    )
    return outputs


def run(
    *,
    phase: str,
    cases_path: str | Path = DEFAULT_E9_OUT,
    output_dir: str | Path | None = None,
    freeze_path: str | Path = DEFAULT_FREEZE,
    prompt_verification_path: str | Path = DEFAULT_PROMPT_VERIFICATION_OUT,
    resume: bool = False,
) -> dict[str, Any]:
    cases_file = Path(cases_path)
    cases = load_cases(cases_file)
    prompt_verification_file = Path(prompt_verification_path)
    _, prompt_verification = load_prompt_verification(
        prompt_verification_file,
        required_cases=cases,
        experiment_id="E9",
        fixture_path=cases_file,
    )
    plan = build_plan(cases, phase=phase)
    output = Path(output_dir or (DEFAULT_SMOKE_OUTPUT if phase == "smoke" else DEFAULT_OUTPUT))
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "execution_plan.json"
    write_json(plan_path, plan)
    freeze = None
    if phase == "formal":
        freeze = verify_freeze(freeze_path)
    configuration = {
        "protocol_id": PROTOCOL_ID,
        "workload_revision": WORKLOAD_REVISION,
        "phase": phase,
        "plan_sha256": sha256_file(plan_path),
        "fixture_sha256": sha256_file(cases_file),
        "freeze_sha256": sha256_file(freeze_path) if freeze else None,
        "freeze_path": Path(freeze_path).resolve().relative_to(ROOT).as_posix(),
        "prompt_verification_sha256": sha256_file(prompt_verification_file),
        "transport": "ollama_native",
        "dynamic_num_ctx": None,
        "seed": SEED,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "token_tolerance": TOKEN_TOLERANCE,
    }
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("configuration_hash") != stable_json_hash(configuration):
            raise RuntimeError("refusing E9 V2 resume: configuration changed")
        if not resume:
            raise FileExistsError("E9 V2 manifest exists; pass --resume")
        manifest["status"] = "running"
        record_event(manifest, "resumed", "explicit E9 V2 resume requested")
    else:
        manifest = new_manifest(
            "E9",
            dataset_paths=[cases_file, prompt_verification_file, plan_path],
            configuration=configuration,
            expected_runs=int(plan["expected_case_runs"]),
            models=[MODEL_ALIAS_BY_TARGET[target] for target in CONTEXT_LENGTHS],
            command=list(sys.argv),
        )
        manifest["protocol_id"] = PROTOCOL_ID
        manifest["workload_revision"] = WORKLOAD_REVISION
        manifest["configuration_hash"] = stable_json_hash(configuration)
        manifest["correction_of"] = "invalid V3 E9 context evidence"
        manifest["denominator_policy"] = "V2_only_old_V3_excluded"
        manifest["jobs"] = [
            {**job, "status": "pending", "attempts": 0, "last_error": None}
            for job in plan["jobs"]
        ]
    register_artifact(manifest, plan_path, kind="execution_plan")
    register_artifact(
        manifest, prompt_verification_file, kind="prompt_workload_verification"
    )
    save_manifest(manifest, manifest_path)
    all_rows: list[dict[str, Any]] = []
    try:
        for target in CONTEXT_LENGTHS:
            for job in (item for item in plan["jobs"] if item["target_prompt_tokens"] == target):
                entry = next(item for item in manifest["jobs"] if item["id"] == job["id"])
                job_dir = output / "work" / job["id"]
                record_path = output / "work" / job["id"] / "job_record.json"
                record = None
                if record_path.exists():
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                    if reusable_job_evidence(
                        record, job, tolerance=TOKEN_TOLERANCE
                    ):
                        if entry.get("status") != "completed":
                            entry["status"] = "completed"
                            entry["last_error"] = None
                            entry["completed_at"] = record.get("completed_at") or utc_now()
                            record_event(
                                manifest,
                                "durable_job_recovered",
                                f"recovered complete evidence for {job['id']}",
                            )
                            save_manifest(manifest, manifest_path)
                    else:
                        archived = archive_invalid_job_attempt(
                            output,
                            job["id"],
                            attempt=max(1, int(entry.get("attempts", 0))),
                        )
                        record_event(
                            manifest,
                            "invalid_job_archived",
                            f"rerunning complete affected condition {job['id']}",
                            archive=str(archived) if archived else None,
                        )
                        entry["status"] = "pending"
                        entry["last_error"] = "semantic resume audit failed"
                        record = None
                elif job_dir.exists():
                    archived = archive_invalid_job_attempt(
                        output,
                        job["id"],
                        attempt=max(1, int(entry.get("attempts", 0))),
                    )
                    record_event(
                        manifest,
                        "partial_job_archived",
                        f"preserved incomplete condition before rerun {job['id']}",
                        archive=str(archived) if archived else None,
                    )
                    entry["status"] = "pending"
                    entry["last_error"] = "partial job evidence archived"
                if record is None:
                    entry["status"] = "running"
                    entry["attempts"] = int(entry.get("attempts", 0)) + 1
                    save_manifest(manifest, manifest_path)
                    record = execute_matrix_job(
                        job,
                        cases_path=cases_file,
                        output_dir=output,
                        resume=False,
                        max_steps=5,
                        max_tokens=MAX_TOKENS,
                        timeout_seconds=600.0,
                        lane_timeout_seconds=7200.0,
                        temperature=TEMPERATURE,
                        seed=SEED,
                        prompt_verification=prompt_verification,
                    )
                    entry["status"] = record["status"]
                    entry["last_error"] = None if record["status"] == "completed" else "job completeness failure"
                    entry["completed_at"] = utc_now()
                    save_manifest(manifest, manifest_path)
                all_rows.extend(read_jsonl(record["raw_path"]))
            stop_model(MODEL_ALIAS_BY_TARGET[target])
            record_event(manifest, "model_stopped", MODEL_ALIAS_BY_TARGET[target])
            save_manifest(manifest, manifest_path)
        validity = _validate(plan, cases, all_rows)
        outputs = _build_outputs(
            output, plan, cases, all_rows, validity, cases_path=cases_file
        )
        for path, kind in outputs:
            register_artifact(manifest, path, kind=kind)
        failed_jobs = sum(job.get("status") != "completed" for job in manifest["jobs"])
        manifest["validity_checks"] = validity
        unresolved_cases = int(validity["provider_incomplete_case_runs"])
        if validity["status"] != "pass" or failed_jobs:
            message = f"semantic validity={validity['status']}, failed_jobs={failed_jobs}"
            manifest["progress"] = semantic_failure_progress(
                expected_runs=int(plan["expected_case_runs"]),
                completed_runs=len(first_step_rows(all_rows)),
                failed_jobs=failed_jobs,
                unresolved_cases=unresolved_cases,
            )
            fail_manifest(manifest, category="semantic_validity", message=message)
        else:
            finish_manifest(
                manifest,
                completed_runs=int(plan["expected_case_runs"]),
                failed_jobs=0,
                unresolved_cases=unresolved_cases,
            )
        save_manifest(manifest, manifest_path)
        return manifest
    except Exception as exc:
        fail_manifest(manifest, category=type(exc).__name__, message=str(exc))
        save_manifest(manifest, manifest_path)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["plan", "smoke", "formal", "audit"], required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_E9_OUT)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument(
        "--prompt-verification",
        type=Path,
        default=DEFAULT_PROMPT_VERIFICATION_OUT,
    )
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_cases(args.cases)
    if args.phase == "plan":
        print(json.dumps(build_plan(cases, phase="formal"), ensure_ascii=False, indent=2))
        return 0
    if args.phase == "audit":
        output = args.out_dir or DEFAULT_OUTPUT
        plan = json.loads((output / "execution_plan.json").read_text(encoding="utf-8"))
        rows = read_jsonl(output / "raw_runs.jsonl")
        validity = _validate(plan, cases, rows)
        write_json(output / "validity_checks.json", validity)
        print(json.dumps(validity, ensure_ascii=False, indent=2))
        return 0 if validity["status"] == "pass" else 1
    manifest = run(
        phase=args.phase,
        cases_path=args.cases,
        output_dir=args.out_dir,
        freeze_path=args.freeze,
        prompt_verification_path=args.prompt_verification,
        resume=args.resume,
    )
    print(json.dumps({"status": manifest["status"], "manifest": str((args.out_dir or (DEFAULT_SMOKE_OUTPUT if args.phase == 'smoke' else DEFAULT_OUTPUT)) / 'manifest.json')}, ensure_ascii=False))
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
