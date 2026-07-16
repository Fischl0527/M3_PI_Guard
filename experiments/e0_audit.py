"""Build the complete E0 measurement-integrity evidence package.

E0 deliberately reuses the frozen Day-5 logs.  Those logs are useful for
checking corrected denominators and metric implementations, but the archived
runner coupled its prompt profile to Guard mode and exposed evaluator labels
to the model.  Every generated artifact therefore marks the historical
comparisons as diagnostic-only.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from experiments.manifest import (
    fail_manifest,
    finish_manifest,
    new_manifest,
    record_event,
    register_artifact,
    save_manifest,
    sha256_file,
    utc_now,
)
from m3_attacks.attackgen import ATTACK_FAMILIES, audit_cases, dataset_sha256
from m3_core.agent_runner import _build_initial_messages
from m3_core.case_views import RUNTIME_CASE_FIELDS, runtime_case_view
from m3_eval.metrics import compare_runs, compute_metrics, load_jsonl
from m3_eval.figure_manifest import write_figure_manifest
from m3_eval.statistics import holm_adjust


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "outputs" / "experiments" / "E0"

CANONICAL_CASES = ROOT / "m3_attacks" / "cases" / "all_cases.jsonl"
ARCHIVED_CASES = (
    ROOT
    / "release"
    / "Redteam_LLM_Security_v1.0"
    / "m3_attacks"
    / "cases"
    / "all_cases.jsonl"
)
REPRESENTATIVE_CASES = ROOT / "fixtures" / "day5_representative_cases.jsonl"
ARCHIVED_RUNNER = (
    ROOT
    / "release"
    / "Redteam_LLM_Security_v1.0"
    / "m3_core"
    / "agent_runner.py"
)
ARCHIVED_STUB_CLIENT = (
    ROOT
    / "release"
    / "Redteam_LLM_Security_v1.0"
    / "m3_core"
    / "llm_client.py"
)


HISTORICAL_RUNS = (
    {
        "run_name": "stub_baseline",
        "display_label": "Stub baseline",
        "cohort": "day5_stub_69",
        "backend": "stub",
        "model": "stub",
        "case_path": ARCHIVED_CASES,
        "log_path": ROOT / "outputs" / "runs" / "day5_stub_matrix" / "day5_stub_all_baseline.jsonl",
        "legacy_defense_mode": "baseline",
        "historical_prompt_profile": "normal",
        "historical_guard_mode": "none",
    },
    {
        "run_name": "stub_keyword_only",
        "display_label": "Stub keyword",
        "cohort": "day5_stub_69",
        "backend": "stub",
        "model": "stub",
        "case_path": ARCHIVED_CASES,
        "log_path": ROOT / "outputs" / "runs" / "day5_stub_matrix" / "day5_stub_all_keyword_only.jsonl",
        "legacy_defense_mode": "keyword_only",
        "historical_prompt_profile": "hardened_coupled",
        "historical_guard_mode": "keyword_only",
    },
    {
        "run_name": "stub_policy_only",
        "display_label": "Stub policy",
        "cohort": "day5_stub_69",
        "backend": "stub",
        "model": "stub",
        "case_path": ARCHIVED_CASES,
        "log_path": ROOT / "outputs" / "runs" / "day5_stub_matrix" / "day5_stub_all_policy_only.jsonl",
        "legacy_defense_mode": "policy_only",
        "historical_prompt_profile": "hardened_coupled",
        "historical_guard_mode": "policy_only",
    },
    {
        "run_name": "stub_full_guard",
        "display_label": "Stub full Guard",
        "cohort": "day5_stub_69",
        "backend": "stub",
        "model": "stub",
        "case_path": ARCHIVED_CASES,
        "log_path": ROOT / "outputs" / "runs" / "day5_stub_matrix" / "day5_stub_all_full_guard.jsonl",
        "legacy_defense_mode": "full_guard",
        "historical_prompt_profile": "hardened_coupled",
        "historical_guard_mode": "full_guard",
    },
    {
        "run_name": "qwen25_baseline",
        "display_label": "Qwen2.5 baseline",
        "cohort": "day5_qwen25_24",
        "backend": "ollama",
        "model": "m3-target-qwen25-7b",
        "case_path": REPRESENTATIVE_CASES,
        "log_path": ROOT / "outputs" / "runs" / "day5_qwen25_matrix" / "day5_qwen25_rep_baseline.jsonl",
        "legacy_defense_mode": "baseline",
        "historical_prompt_profile": "normal",
        "historical_guard_mode": "none",
    },
    {
        "run_name": "qwen25_full_guard",
        "display_label": "Qwen2.5 full Guard",
        "cohort": "day5_qwen25_24",
        "backend": "ollama",
        "model": "m3-target-qwen25-7b",
        "case_path": REPRESENTATIVE_CASES,
        "log_path": ROOT / "outputs" / "runs" / "day5_qwen25_matrix" / "day5_qwen25_rep_full_guard.jsonl",
        "legacy_defense_mode": "full_guard",
        "historical_prompt_profile": "hardened_coupled",
        "historical_guard_mode": "full_guard",
    },
)

PROPORTION_METRICS = (
    "ASR",
    "UTR",
    "DSR",
    "DSRAllAttack",
    "BSR",
    "TCR",
    "Precision",
    "Recall",
    "F1",
    "FPR",
    "CaseFPR",
    "BenignInterventionRate",
    "ASK",
    "BenignASKRate",
    "ParseSuccessRate",
    "UnresolvedRate",
)
CHART_METRICS = (
    "ASR",
    "TCR",
    "BenignInterventionRate",
    "ParseSuccessRate",
    "FPR",
)


def _relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})


def _explicit_legacy_labels(cases: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize frozen pre-schema cases to explicit labels for strict scoring."""

    normalized: list[dict[str, Any]] = []
    for original in cases:
        case = copy.deepcopy(original)
        family = str(case.get("attack_family", "")).strip().lower()
        inferred = "benign" if family in {"benign", "benign_clean", "benign_summary"} else "attack"
        existing = case.get("sample_type")
        if existing is not None and existing != inferred:
            raise ValueError(
                f"legacy case {case.get('case_id')!r} has inconsistent sample_type={existing!r}"
            )
        case["sample_type"] = inferred
        normalized.append(case)
    return normalized


def _source_record(path: Path, *, kind: str) -> dict[str, Any]:
    rows = load_jsonl(path)
    case_ids = [str(row.get("case_id", "")) for row in rows if str(row.get("case_id", ""))]
    return {
        "kind": kind,
        "path": _relative(path),
        "sha256": sha256_file(path),
        "row_count": len(rows),
        "distinct_case_count": len(set(case_ids)),
        "duplicate_case_id_rows": len(case_ids) - len(set(case_ids)) if kind == "case_dataset" else None,
    }


def build_raw_run_index() -> dict[str, Any]:
    ordered_sources: list[tuple[Path, str]] = [
        (CANONICAL_CASES, "case_dataset"),
        (ARCHIVED_CASES, "case_dataset"),
        (REPRESENTATIVE_CASES, "case_dataset"),
    ]
    ordered_sources.extend((definition["log_path"], "run_log") for definition in HISTORICAL_RUNS)
    records = [_source_record(path, kind=kind) for path, kind in ordered_sources]
    return {
        "schema_version": "1.0",
        "experiment_id": "E0",
        "purpose": "Immutable source index for six historical diagnostic runs",
        "historical_run_count": len(HISTORICAL_RUNS),
        "records": records,
    }


def _runtime_prompt_audit(cases: list[dict[str, Any]]) -> dict[str, Any]:
    allowed_fields = set(RUNTIME_CASE_FIELDS)
    projection_failures: list[dict[str, Any]] = []
    invariance_failures: list[dict[str, Any]] = []
    sentinel_failures: list[dict[str, Any]] = []

    for index, case in enumerate(cases):
        view = runtime_case_view(case)
        extra_fields = sorted(set(view) - allowed_fields)
        if extra_fields:
            projection_failures.append({"case_id": case.get("case_id"), "fields": extra_fields})

        mutated = copy.deepcopy(case)
        sentinels: list[str] = []
        for field in sorted(set(case) - allowed_fields):
            sentinel = f"__E0_EVALUATOR_ONLY_{index}_{field.upper()}__"
            mutated[field] = sentinel
            sentinels.append(sentinel)
        for profile in ("normal", "hardened"):
            original_messages = _build_initial_messages(case, prompt_profile=profile)
            mutated_messages = _build_initial_messages(mutated, prompt_profile=profile)
            if original_messages != mutated_messages:
                invariance_failures.append(
                    {"case_id": case.get("case_id"), "prompt_profile": profile}
                )
            serialized = json.dumps(mutated_messages, ensure_ascii=False, sort_keys=True)
            leaked = [sentinel for sentinel in sentinels if sentinel in serialized]
            if leaked:
                sentinel_failures.append(
                    {
                        "case_id": case.get("case_id"),
                        "prompt_profile": profile,
                        "sentinels": leaked,
                    }
                )

    return {
        "runtime_allowlist": list(RUNTIME_CASE_FIELDS),
        "cases_checked": len(cases),
        "prompt_profiles_checked": ["normal", "hardened"],
        "messages_compared": len(cases) * 2,
        "projection_failures": projection_failures,
        "metamorphic_invariance_failures": invariance_failures,
        "sentinel_leakage_failures": sentinel_failures,
        "status": (
            "pass"
            if not projection_failures and not invariance_failures and not sentinel_failures
            else "fail"
        ),
        "method": (
            "For every canonical case, mutate every non-runtime field to a unique sentinel and "
            "require byte-equivalent normal/hardened message objects."
        ),
    }


def _historical_source_audit() -> dict[str, Any]:
    runner_text = ARCHIVED_RUNNER.read_text(encoding="utf-8")
    stub_text = ARCHIVED_STUB_CLIENT.read_text(encoding="utf-8")
    leaked_markers = {
        "case_id": '"case_id": case.get("case_id", "")' in runner_text,
        "attack_family": '"attack_family": case.get("attack_family", "")' in runner_text,
        "expected_safe_behavior": "<ExpectedSafeBehavior>" in runner_text
        and 'case.get("expected_safe_behavior", "")' in runner_text,
    }
    coupled_markers = {
        "guard_modes_declared": (
            'GUARD_DEFENSE_MODES = {"guarded", "keyword_only", "policy_only", "full_guard"}'
            in runner_text
        ),
        "prompt_selected_from_defense_mode": "if defense_mode in GUARD_DEFENSE_MODES:" in runner_text,
    }
    stub_markers = {
        "uses_case_id": 'case.get("case_id", "")' in stub_text,
        "uses_attack_family": 'case.get("attack_family", "")' in stub_text,
    }
    return {
        "runner_source": _relative(ARCHIVED_RUNNER),
        "runner_sha256": sha256_file(ARCHIVED_RUNNER),
        "stub_source": _relative(ARCHIVED_STUB_CLIENT),
        "stub_sha256": sha256_file(ARCHIVED_STUB_CLIENT),
        "prompt_guard_coupling": {
            "detected": all(coupled_markers.values()),
            "markers": coupled_markers,
            "impact": "Guard mode and prompt hardening cannot be isolated in historical guarded runs.",
        },
        "model_input_label_leakage": {
            "detected": all(leaked_markers.values()),
            "leaked_fields": [key for key, value in leaked_markers.items() if value],
            "markers": leaked_markers,
            "impact": "Historical model outputs were generated with evaluator-only answer metadata.",
        },
        "stub_oracle_label_dependency": {
            "detected": all(stub_markers.values()),
            "markers": stub_markers,
            "impact": "Stub results are deterministic regression evidence only, never formal model-effect evidence.",
        },
        "causal_interpretation": "diagnostic_only",
    }


def build_measurement_audit(
    canonical_cases: list[dict[str, Any]],
    historical_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical_file_hash = sha256_file(CANONICAL_CASES)
    sample_counts = Counter(str(case.get("sample_type")) for case in canonical_cases)
    split_counts = Counter(str(case.get("split")) for case in canonical_cases)
    attack_family_counts = Counter(
        str(case.get("attack_family"))
        for case in canonical_cases
        if case.get("sample_type") == "attack"
    )
    benign_tool_counts = Counter(
        "tool" if case.get("requires_tool") else "no_tool"
        for case in canonical_cases
        if case.get("sample_type") == "benign"
    )
    legacy_cases = [case for case in canonical_cases if case.get("mutation_id") == "legacy"]
    templates_by_split: dict[str, set[str]] = defaultdict(set)
    for case in canonical_cases:
        templates_by_split[str(case.get("template_id"))].add(str(case.get("split")))
    cross_split_templates = sorted(
        template for template, splits in templates_by_split.items() if len(splits) > 1
    )

    dataset_audit = audit_cases(canonical_cases)
    runtime_audit = _runtime_prompt_audit(canonical_cases)
    historical_source_audit = _historical_source_audit()
    historical_denominators = {
        row["run_name"]: {
            "attack": row["ASR_denominator"],
            "benign": row["TCR_denominator"],
            "total_case_runs": row["case_runs"],
        }
        for row in historical_metrics
    }
    expected_denominators = {
        "stub": {"attack": 61, "benign": 8, "total_case_runs": 69},
        "qwen25": {"attack": 19, "benign": 5, "total_case_runs": 24},
    }
    denominator_pass = all(
        values
        == expected_denominators["stub" if name.startswith("stub_") else "qwen25"]
        for name, values in historical_denominators.items()
    )
    current_checks = {
        "canonical_total_300": len(canonical_cases) == 300,
        "canonical_explicit_sample_type": sample_counts == {"attack": 210, "benign": 90},
        "canonical_split_quota": split_counts == {"dev": 150, "validation": 60, "blind": 90},
        "canonical_nine_attack_families": (
            set(attack_family_counts) == set(ATTACK_FAMILIES)
            and sum(attack_family_counts.values()) == 210
        ),
        "canonical_benign_tool_balance": benign_tool_counts == {"no_tool": 45, "tool": 45},
        "legacy_69_development_only": (
            len(legacy_cases) == 69 and {case.get("split") for case in legacy_cases} == {"dev"}
        ),
        "unique_case_ids": len({case.get("case_id") for case in canonical_cases}) == 300,
        "no_template_cross_split": not cross_split_templates,
        "canonical_dataset_audit": dataset_audit.get("status") == "pass"
        and dataset_audit.get("hard_fail_count") == 0,
        "runtime_prompt_no_evaluator_leakage": runtime_audit.get("status") == "pass",
        "historical_denominators_corrected": denominator_pass,
    }
    return {
        "schema_version": "1.0",
        "experiment_id": "E0",
        "generated_at": utc_now(),
        "status": "pass_with_historical_findings" if all(current_checks.values()) else "fail",
        "current_measurement_checks": current_checks,
        "canonical_dataset": {
            "path": _relative(CANONICAL_CASES),
            "file_sha256": canonical_file_hash,
            "semantic_sha256": dataset_sha256(canonical_cases),
            "total_cases": len(canonical_cases),
            "sample_type_count": dict(sorted(sample_counts.items())),
            "split_count": dict(sorted(split_counts.items())),
            "attack_family_count": dict(sorted(attack_family_counts.items())),
            "benign_tool_requirement_count": dict(sorted(benign_tool_counts.items())),
            "legacy_case_count": len(legacy_cases),
            "legacy_case_split_count": dict(
                sorted(Counter(str(case.get("split")) for case in legacy_cases).items())
            ),
            "template_count": len(templates_by_split),
            "cross_split_templates": cross_split_templates,
            "dataset_audit_status": dataset_audit.get("status"),
            "dataset_audit_hard_fail_count": dataset_audit.get("hard_fail_count"),
            "dataset_audit_warning_count": dataset_audit.get("warnings", {}),
        },
        "runtime_prompt_audit": runtime_audit,
        "historical_denominator_audit": {
            "status": "pass" if denominator_pass else "fail",
            "label_policy": (
                "Frozen pre-schema cases were copied in memory and assigned explicit sample_type: "
                "benign only for benign/benign_clean/benign_summary; all others attack."
            ),
            "expected": expected_denominators,
            "observed": historical_denominators,
            "benign_clean_excluded_from_attack_denominator": denominator_pass,
        },
        "historical_source_findings": historical_source_audit,
        "historical_evidence_interpretation": "diagnostic_only",
    }


def build_historical_metrics() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    metric_rows: list[dict[str, Any]] = []
    loaded_logs: dict[str, list[dict[str, Any]]] = {}
    case_cache: dict[Path, list[dict[str, Any]]] = {}
    for definition in HISTORICAL_RUNS:
        case_path = definition["case_path"]
        if case_path not in case_cache:
            case_cache[case_path] = _explicit_legacy_labels(load_jsonl(case_path))
        cases = case_cache[case_path]
        logs = load_jsonl(definition["log_path"])
        loaded_logs[definition["run_name"]] = logs
        metrics = compute_metrics(
            logs,
            cases,
            label=definition["run_name"],
            strict_labels=True,
            include_missing=True,
        )
        row: dict[str, Any] = {
            key: value
            for key, value in definition.items()
            if key not in {"case_path", "log_path"}
        }
        row.update(
            {
                "source_case_path": _relative(case_path),
                "source_log_path": _relative(definition["log_path"]),
                "source_log_sha256": sha256_file(definition["log_path"]),
                "log_rows": len(logs),
                "distinct_logged_cases": len(
                    {str(log.get("case_id")) for log in logs if log.get("case_id")}
                ),
                "case_runs": metrics["case_runs"],
                "attack_cases": metrics["attack_cases"],
                "attack_runs": metrics["attack_runs"],
                "benign_cases": metrics["clean_cases"],
                "benign_runs": metrics["clean_runs"],
                "missing_case_runs": metrics["missing_case_runs"],
                "unresolved_runs": metrics["unresolved_runs"],
                "parse_successes": metrics["parse_successes"],
                "parse_total": metrics["parse_total"],
                "TP": metrics["TP"],
                "FP": metrics["FP"],
                "FN": metrics["FN"],
                "TN": metrics["TN"],
                "legacy_inferred_labels": metrics["legacy_inferred_labels"],
                "label_policy": "explicit_in_memory_legacy_normalization",
                "causal_interpretation": "diagnostic_only",
                "data_warnings": " | ".join(metrics["data_quality_warnings"]),
            }
        )
        for metric in PROPORTION_METRICS:
            row[metric] = metrics.get(metric)
            row[f"{metric}_numerator"] = metrics.get(f"{metric}_numerator")
            row[f"{metric}_denominator"] = metrics.get(f"{metric}_denominator")
            row[f"{metric}_ci_low"] = metrics.get(f"{metric}_ci_low")
            row[f"{metric}_ci_high"] = metrics.get(f"{metric}_ci_high")
        metric_rows.append(row)
    return metric_rows, loaded_logs


def _historical_fieldnames() -> list[str]:
    fields = [
        "run_name",
        "display_label",
        "cohort",
        "backend",
        "model",
        "legacy_defense_mode",
        "historical_prompt_profile",
        "historical_guard_mode",
        "source_case_path",
        "source_log_path",
        "source_log_sha256",
        "log_rows",
        "distinct_logged_cases",
        "case_runs",
        "attack_cases",
        "attack_runs",
        "benign_cases",
        "benign_runs",
        "missing_case_runs",
        "unresolved_runs",
        "parse_successes",
        "parse_total",
        "TP",
        "FP",
        "FN",
        "TN",
        "legacy_inferred_labels",
        "label_policy",
        "causal_interpretation",
    ]
    for metric in PROPORTION_METRICS:
        fields.extend(
            [
                metric,
                f"{metric}_numerator",
                f"{metric}_denominator",
                f"{metric}_ci_low",
                f"{metric}_ci_high",
            ]
        )
    fields.append("data_warnings")
    return fields


def build_statistics(loaded_logs: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    comparisons = (
        ("stub_baseline_vs_keyword", "stub_baseline", "stub_keyword_only", ARCHIVED_CASES),
        ("stub_baseline_vs_policy", "stub_baseline", "stub_policy_only", ARCHIVED_CASES),
        ("stub_baseline_vs_full", "stub_baseline", "stub_full_guard", ARCHIVED_CASES),
        ("qwen25_baseline_vs_full", "qwen25_baseline", "qwen25_full_guard", REPRESENTATIVE_CASES),
    )
    results: list[dict[str, Any]] = []
    hypotheses: list[tuple[dict[str, Any], str, float]] = []
    for comparison_id, baseline_name, treatment_name, case_path in comparisons:
        cases = _explicit_legacy_labels(load_jsonl(case_path))
        compared = compare_runs(
            loaded_logs[baseline_name],
            loaded_logs[treatment_name],
            cases,
            strict_labels=True,
            bootstrap_iterations=10_000,
            bootstrap_seed=42,
        )
        result = {
            "comparison_id": comparison_id,
            "baseline": baseline_name,
            "treatment": treatment_name,
            "case_source": _relative(case_path),
            "causal_interpretation": "diagnostic_only",
            "delta": compared["delta"],
            "paired_statistics": compared["paired_statistics"],
        }
        results.append(result)
        for metric in ("ASR", "DSR", "TCR"):
            test = result["paired_statistics"].get(f"{metric}_mcnemar", {})
            p_value = test.get("p_value")
            if p_value is not None:
                hypotheses.append((result, metric, float(p_value)))

    adjusted = holm_adjust([item[2] for item in hypotheses])
    correction_rows: list[dict[str, Any]] = []
    for (result, metric, raw_p), adjusted_p in zip(hypotheses, adjusted):
        test = result["paired_statistics"][f"{metric}_mcnemar"]
        test["holm_adjusted_p"] = adjusted_p
        correction_rows.append(
            {
                "comparison_id": result["comparison_id"],
                "metric": metric,
                "raw_p": raw_p,
                "holm_adjusted_p": adjusted_p,
            }
        )
    return {
        "schema_version": "1.0",
        "experiment_id": "E0",
        "status": "completed",
        "scope": "historical_diagnostic_only",
        "methods": {
            "binary_paired": "two-sided exact McNemar",
            "paired_difference_ci": "case-clustered paired bootstrap, 10,000 iterations, seed 42",
            "multiple_comparisons": "Holm family-wise correction across historical McNemar tests",
            "undefined_metric_policy": "zero denominators remain null/NA",
        },
        "comparisons": results,
        "holm_correction": correction_rows,
        "warning": (
            "Prompt/Guard coupling and evaluator-label leakage in the archived runner make all "
            "effect comparisons diagnostic only, irrespective of p-values."
        ),
    }


def build_chart_data(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in metric_rows:
        for metric in CHART_METRICS:
            value = run.get(metric)
            rows.append(
                {
                    "run_name": run["run_name"],
                    "display_label": run["display_label"],
                    "metric": metric,
                    "value": value,
                    "numerator": run.get(f"{metric}_numerator"),
                    "denominator": run.get(f"{metric}_denominator"),
                    "value_status": "observed" if value is not None else "NA_zero_denominator",
                    "causal_interpretation": "diagnostic_only",
                }
            )
    return rows


def render_chart(chart_rows: list[dict[str, Any]], png_path: Path, svg_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(dict.fromkeys(row["display_label"] for row in chart_rows))
    metrics = list(CHART_METRICS)
    colors = ["#D55E00", "#0072B2", "#009E73", "#CC79A7", "#E69F00"]
    width = 0.15
    base_positions = list(range(len(labels)))
    fig, axis = plt.subplots(figsize=(13.5, 6.8))
    by_key = {(row["display_label"], row["metric"]): row for row in chart_rows}

    for metric_index, (metric, color) in enumerate(zip(metrics, colors)):
        offsets = [
            position + (metric_index - (len(metrics) - 1) / 2) * width
            for position in base_positions
        ]
        observed_positions: list[float] = []
        observed_values: list[float] = []
        for position, label in zip(offsets, labels):
            value = by_key[(label, metric)]["value"]
            if value is None:
                axis.text(
                    position,
                    0.018,
                    "NA",
                    ha="center",
                    va="bottom",
                    rotation=90,
                    fontsize=6.5,
                    color="#666666",
                )
            else:
                observed_positions.append(position)
                observed_values.append(float(value))
        axis.bar(
            observed_positions,
            observed_values,
            width=width,
            label=metric,
            color=color,
            edgecolor="white",
            linewidth=0.4,
        )

    axis.set_ylim(0.0, 1.06)
    axis.set_ylabel("Proportion")
    axis.set_title("Historical diagnostic metrics (not causal evidence)")
    axis.set_xticks(base_positions, labels, rotation=18, ha="right")
    axis.grid(axis="y", linestyle="--", alpha=0.3)
    axis.legend(ncol=3, frameon=False, loc="upper center")
    fig.text(
        0.5,
        0.01,
        "NA denotes an undefined zero-denominator metric; no zero-height bar is drawn.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def _percent(value: Any) -> str:
    return "NA" if value is None else f"{100.0 * float(value):.1f}%"


def build_analysis(
    raw_index: dict[str, Any],
    audit: dict[str, Any],
    metric_rows: list[dict[str, Any]],
    statistics: dict[str, Any],
) -> str:
    canonical = audit["canonical_dataset"]
    lines = [
        "# E0 指标、标签与历史结果审计",
        "",
        "> 结论限定：**diagnostic only（仅诊断）**。历史运行存在 prompt/Guard coupling "
        "（提示词与 Guard 耦合）和 evaluator-label leakage（评估答案字段泄漏），不得用于正式因果效果声明。",
        "",
        "## 验收结论",
        "",
        f"- 当前测量链路：`{audit['status']}`。显式 `sample_type`、数据集配额、模板隔离和运行时输入投影检查均通过。",
        "- 历史结果：六组日志已原样索引并重新计算；解析失败、拒答、超时或未完成状态仍保留在原分母。",
        "- Stub：只作为确定性回归证据。旧 Stub 直接读取 `case_id` 和 `attack_family`，不能代表真实模型安全效果。",
        "- 空分母：统一写作 `NA`，图中不绘制为 0。",
        "",
        "## 数据与粒度",
        "",
        "| 数据 | 行/案例 | SHA-256 |",
        "|---|---:|---|",
    ]
    for record in raw_index["records"]:
        lines.append(
            f"| `{record['path']}` | {record['row_count']} / {record['distinct_case_count']} | `{record['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "主比例指标按案例运行（case-run）计算；Precision/Recall/FPR 按可判定工具调用计算；ParseSuccessRate 按解析尝试计算。",
            "历史 pre-schema 数据仅在内存副本中按 `benign_clean → benign，其余 → attack` 写入显式 `sample_type`，原文件未修改。",
            "",
            "## 300 条规范数据集审计",
            "",
            f"- 文件哈希：`{canonical['file_sha256']}`；语义哈希：`{canonical['semantic_sha256']}`。",
            f"- 共 {canonical['total_cases']} 条：attack={canonical['sample_type_count'].get('attack')}，benign={canonical['sample_type_count'].get('benign')}。",
            f"- 切分：dev={canonical['split_count'].get('dev')}，validation={canonical['split_count'].get('validation')}，blind={canonical['split_count'].get('blind')}。",
            f"- 正常任务：无工具={canonical['benign_tool_requirement_count'].get('no_tool')}，合法工具={canonical['benign_tool_requirement_count'].get('tool')}。",
            f"- 九类攻击共 {sum(canonical['attack_family_count'].values())} 条；69 条遗留样本全部位于 dev。",
            f"- 数据审计：`{canonical['dataset_audit_status']}`，hard_fail={canonical['dataset_audit_hard_fail_count']}，跨集合模板={len(canonical['cross_split_templates'])}。",
            f"- 运行时泄漏变形测试：{audit['runtime_prompt_audit']['messages_compared']} 组消息对，状态 `{audit['runtime_prompt_audit']['status']}`。",
            "",
            "## 历史指标重算",
            "",
            "| 运行 | attack/benign | ASR | UTR | DSR | BSR | TCR | 正常干预 | 解析成功 | 未解决案例 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in metric_rows:
        lines.append(
            "| {label} | {attack}/{benign} | {asr} | {utr} | {dsr} | {bsr} | {tcr} | {bir} | {parse} | {unresolved} |".format(
                label=row["display_label"],
                attack=row["ASR_denominator"],
                benign=row["TCR_denominator"],
                asr=_percent(row["ASR"]),
                utr=_percent(row["UTR"]),
                dsr=_percent(row["DSR"]),
                bsr=_percent(row["BSR"]),
                tcr=_percent(row["TCR"]),
                bir=_percent(row["BenignInterventionRate"]),
                parse=_percent(row["ParseSuccessRate"]),
                unresolved=row["unresolved_runs"],
            )
        )
    lines.extend(
        [
            "",
            "关键分母修正：69 条 Stub 快照统一使用 attack=61、benign=8；24 条 Qwen 快照使用 attack=19、benign=5。"
            "8 条 `benign_clean` 不再进入 Stub ASR/UTR/DSR 的攻击分母。",
            "Qwen baseline/full 的解析成功率分别为 36/38 与 22/24；未解决案例分别为 3 与 2，均未被静默删除。",
            "FPR 只有存在可判定的合法工具调用分母时才定义；Qwen full 的两条合法文件调用虽使用历史 `file_path` 别名，"
            "仍应计入分母，且两条均被拒绝，因此 FPR=2/2=100%、正常案例干预率=2/5。"
            "四组 Stub 快照没有可判定的合法工具调用，FPR 才是 NA。",
            "",
            "## 历史缺陷与解释边界",
            "",
            "1. **Prompt/Guard coupling**：旧 `_build_initial_messages` 直接从 `defense_mode` 选择普通或强化提示。keyword、policy、full Guard 与 baseline 的差异同时包含提示词变化。",
            "2. **Label leakage**：旧模型输入包含 `case_id`、`attack_family` 和 `<ExpectedSafeBehavior>`。这相当于向模型暴露样本标签和期望答案。",
            "3. **Stub oracle dependency**：旧 Stub 根据 `case_id`/`attack_family` 直接选择工具调用路径，只适合回归测试。",
            "4. 因此，`statistics.json` 的 McNemar、10,000 次配对 bootstrap 和 Holm 校正仅验证重算链路；即使 p 值很小，也不能支持 Guard 的正式因果结论。",
            "",
            "## 可复现入口",
            "",
            "```powershell",
            "python -m experiments.e0_audit --out-dir outputs/experiments/E0",
            "```",
            "",
            f"统计比较数：{len(statistics['comparisons'])}；历史运行数：{len(metric_rows)}。",
        ]
    )
    return "\n".join(lines) + "\n"


def run_e0(out_dir: str | Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    output = Path(out_dir)
    if not output.is_absolute():
        output = ROOT / output
    output.mkdir(parents=True, exist_ok=True)
    source_paths = [CANONICAL_CASES, ARCHIVED_CASES, REPRESENTATIVE_CASES]
    source_paths.extend(definition["log_path"] for definition in HISTORICAL_RUNS)
    manifest = new_manifest(
        "E0",
        dataset_paths=source_paths,
        configuration={
            "historical_run_count": 6,
            "historical_interpretation": "diagnostic_only",
            "strict_sample_type_after_legacy_normalization": True,
            "bootstrap_iterations": 10_000,
            "bootstrap_seed": 42,
            "undefined_metric_policy": "null_not_zero",
        },
        expected_runs=6,
        models=["stub", "m3-target-qwen25-7b"],
        command=["python", "-m", "experiments.e0_audit", "--out-dir", _relative(output)],
    )
    manifest_path = output / "manifest.json"
    save_manifest(manifest, manifest_path)

    try:
        raw_index = build_raw_run_index()
        metric_rows, loaded_logs = build_historical_metrics()
        canonical_cases = load_jsonl(CANONICAL_CASES)
        audit = build_measurement_audit(canonical_cases, metric_rows)
        if audit["status"] == "fail":
            failed = [key for key, value in audit["current_measurement_checks"].items() if not value]
            raise RuntimeError(f"E0 current measurement check(s) failed: {failed}")
        statistics = build_statistics(loaded_logs)
        chart_rows = build_chart_data(metric_rows)

        raw_index_path = output / "raw_run_index.json"
        audit_path = output / "measurement_audit.json"
        metrics_path = output / "historical_metrics.csv"
        statistics_path = output / "statistics.json"
        chart_data_path = output / "historical_diagnostic_metrics_data.csv"
        png_path = output / "historical_diagnostic_metrics.png"
        svg_path = output / "historical_diagnostic_metrics.svg"
        analysis_path = output / "analysis.md"

        _write_json(raw_index_path, raw_index)
        _write_json(audit_path, audit)
        _write_csv(metrics_path, metric_rows, _historical_fieldnames())
        _write_json(statistics_path, statistics)
        _write_csv(
            chart_data_path,
            chart_rows,
            [
                "run_name",
                "display_label",
                "metric",
                "value",
                "numerator",
                "denominator",
                "value_status",
                "causal_interpretation",
            ],
        )
        render_chart(chart_rows, png_path, svg_path)
        figure_manifest_path = write_figure_manifest(
            output,
            experiment_id="E0",
            evidence_tier="historical_diagnostic_only",
            figures=[
                {
                    "id": "historical_diagnostic_metrics",
                    "title": "Historical diagnostic metrics",
                    "role": "diagnostic",
                    "order": 0,
                    "chart_type": "grouped_bar",
                    "caption": (
                        "Corrected historical metric estimates by archived run; undefined "
                        "zero-denominator values are labeled NA rather than plotted as zero."
                    ),
                    "files": {
                        "data": chart_data_path.name,
                        "png": png_path.name,
                        "svg": svg_path.name,
                    },
                    "metrics": list(CHART_METRICS),
                    "grain": ["historical_run", "metric"],
                    "uncertainty": [
                        {
                            "method": "none_in_figure",
                            "reason": "diagnostic chart shows corrected point estimates and raw denominators",
                        }
                    ],
                    "warnings": [
                        "Historical diagnostic evidence only; archived prompt/Guard coupling prevents causal interpretation.",
                        "Archived evaluator-label leakage prevents formal defense-effect claims.",
                    ],
                }
            ],
        )
        analysis_path.write_text(
            build_analysis(raw_index, audit, metric_rows, statistics), encoding="utf-8"
        )

        for definition in HISTORICAL_RUNS:
            register_artifact(manifest, definition["log_path"], kind="raw_log")
        register_artifact(manifest, raw_index_path, kind="raw_log_index")
        register_artifact(manifest, audit_path, kind="metrics")
        register_artifact(manifest, metrics_path, kind="metrics")
        register_artifact(manifest, chart_data_path, kind="metrics")
        register_artifact(manifest, statistics_path, kind="statistics")
        register_artifact(manifest, analysis_path, kind="analysis")
        register_artifact(manifest, png_path, kind="figure")
        register_artifact(manifest, svg_path, kind="figure")
        register_artifact(manifest, figure_manifest_path, kind="figure_manifest")
        record_event(
            manifest,
            "audit_findings",
            "historical evidence restricted to diagnostic use",
            prompt_guard_coupling=True,
            evaluator_label_leakage=True,
        )
        finish_manifest(
            manifest,
            completed_runs=6,
            failed_jobs=0,
            unresolved_cases=sum(int(row["unresolved_runs"]) for row in metric_rows),
        )
        save_manifest(manifest, manifest_path)
        return manifest
    except Exception as exc:
        fail_manifest(manifest, category=type(exc).__name__, message=str(exc))
        save_manifest(manifest, manifest_path)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="E0 artifact directory (default: outputs/experiments/E0)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = run_e0(args.out_dir)
    print(
        json.dumps(
            {
                "experiment_id": manifest["experiment_id"],
                "status": manifest["status"],
                "completed_runs": manifest["progress"]["completed_runs"],
                "output_dir": _relative(Path(args.out_dir) if Path(args.out_dir).is_absolute() else ROOT / args.out_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
