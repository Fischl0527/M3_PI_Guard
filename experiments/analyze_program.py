"""Generate formal evidence bundles from the shared experiment program.

The analyzer is intentionally read-only with respect to the experiment
registry and raw program outputs.  It only marks an E1-E12/E15 evidence
manifest complete after every required real-model matrix manifest and JSONL
passes completeness, hash, grain, and smoke-gate checks.  Stub runs are never
admitted to formal effect denominators.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from experiments.catalog import CORE_MODELS, EXPERIMENT_BY_ID, LEGACY_MODEL
from experiments.manifest import (
    MANIFEST_SCHEMA_VERSION,
    environment_snapshot,
    fail_manifest,
    finish_manifest,
    git_state,
    record_event,
    register_artifact,
    save_manifest,
    sha256_file,
    sha256_paths,
    utc_now,
)
from experiments.run_program import ProgramJob, build_stage_plan
from m3_eval.figure_manifest import FIGURE_MANIFEST_FILENAME, write_figure_manifest
from m3_eval.metrics import METRIC_NAMES, compare_runs, compute_metrics, load_jsonl
from m3_eval.statistics import holm_adjust


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROGRAM_ROOT = ROOT / "outputs" / "experiments" / "program"
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "experiments"
TARGET_EXPERIMENTS = tuple([f"E{index}" for index in range(1, 13)] + ["E15"])

# These names mirror the already-frozen registry contract.  The analyzer also
# emits the shared metrics/statistics/chart artifacts for every experiment, but
# keeping these experiment-specific views avoids a later manual rename step and
# makes registry validation possible without mutating the registry here.
SPECIALIZED_ARTIFACT_NAMES: dict[str, tuple[str, ...]] = {
    "E4": (
        "ablation_contributions.csv",
        "ablation_contribution_forest.png",
        "ablation_contribution_forest.svg",
    ),
    "E6": ("by_family.csv", "by_family_ci.csv"),
    "E7": ("by_language.csv",),
    "E8": ("by_mutation.csv", "strength_curve.csv"),
    "E9": ("context_position.csv",),
    "E10": ("by_turn_count.csv",),
    "E11": ("chain_metrics.csv", "case_replays.json"),
    "E12": ("utility_metrics.csv",),
    "E15": ("stability.csv",),
}
BASE_BUNDLE_ARTIFACT_NAMES = (
    "manifest.json",
    "raw_run_index.json",
    "metrics.csv",
    "statistics.json",
    "analysis.md",
    "primary_chart_data.csv",
    "primary_chart.png",
    "primary_chart.svg",
    FIGURE_MANIFEST_FILENAME,
)


def bundle_artifact_names(experiment_id: str) -> tuple[str, ...]:
    return (*BASE_BUNDLE_ARTIFACT_NAMES, *SPECIALIZED_ARTIFACT_NAMES.get(experiment_id, ()))

CORE_CONDITION_IDS = (
    "regular_none",
    "hardened_none",
    "regular_keyword",
    "regular_policy",
    "regular_full",
    "hardened_full",
)
DERIVED_CONDITION_IDS = ("derived_normal_off", "derived_normal_full")

DIMENSION_FIELDS = (
    "attack_family",
    "language",
    "obfuscation_type",
    "context_tokens",
    "injection_position_pct",
    "turn_count",
    "multi_turn_mode",
    "chain_pattern",
    "requires_tool",
    "temperature",
    "seed",
)

COUNT_FIELDS = (
    "cases",
    "case_runs",
    "attack_cases",
    "attack_runs",
    "clean_cases",
    "clean_runs",
    "TP",
    "FP",
    "FN",
    "TN",
    "indeterminate_calls",
    "actionable_calls",
    "ASK_calls",
    "parse_successes",
    "parse_total",
    "unresolved_runs",
    "missing_case_runs",
    "duplicate_logical_runs",
    "legacy_inferred_labels",
)

TIMING_FIELDS = (
    "ModelLatencyP50",
    "ModelLatencyP95",
    "ParseLatencyP50",
    "ParseLatencyP95",
    "GuardLatencyP50",
    "GuardLatencyP95",
    "ToolLatencyP50",
    "ToolLatencyP95",
    "StepLatencyP50",
    "StepLatencyP95",
    "CaseLatencyP50",
    "CaseLatencyP95",
)

TERMINAL_STATUSES = {
    "blocked",
    "completed",
    "error",
    "failed",
    "max_steps_reached",
    "needs_confirmation",
    "parse_error",
    "refused",
    "timeout",
}


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    stage: str
    primary_metric: str
    chart_kind: str
    chart_dimension: str
    formal_models: tuple[str, ...]
    smoke_models: tuple[str, ...]
    formal_condition_ids: tuple[str, ...] | None = None
    focus_condition_ids: tuple[str, ...] = ()

    @property
    def definition(self):
        return EXPERIMENT_BY_ID[self.experiment_id]


SPECS: dict[str, ExperimentSpec] = {
    "E1": ExperimentSpec(
        "E1", "main", "ASR", "bar_ci", "model", tuple(CORE_MODELS), tuple(CORE_MODELS),
        ("regular_none", "regular_full"), ("regular_none", "regular_full"),
    ),
    "E2": ExperimentSpec(
        "E2", "main", "ASR", "bar_ci", "model", tuple(CORE_MODELS), tuple(CORE_MODELS),
        ("regular_none", "hardened_none"), ("regular_none", "hardened_none"),
    ),
    "E3": ExperimentSpec(
        "E3", "main", "ASR", "bar_ci", "model", tuple(CORE_MODELS), tuple(CORE_MODELS),
        ("hardened_none", "hardened_full"), ("hardened_none", "hardened_full"),
    ),
    "E4": ExperimentSpec(
        "E4", "ablation", "ASR", "ablation_bar_ci", "condition", (CORE_MODELS[0],),
        (CORE_MODELS[0],), None, (),
    ),
    "E5": ExperimentSpec(
        "E5", "main", "ASR", "bar_ci", "model", tuple(CORE_MODELS),
        (*CORE_MODELS, LEGACY_MODEL), None, ("regular_none", "regular_full"),
    ),
    "E6": ExperimentSpec(
        "E6", "main", "ASR", "bar_ci", "attack_family", tuple(CORE_MODELS),
        tuple(CORE_MODELS), None, ("regular_none", "regular_full"),
    ),
    "E7": ExperimentSpec(
        "E7", "derived", "ASR", "heatmap", "language", (CORE_MODELS[0],),
        (CORE_MODELS[0],), DERIVED_CONDITION_IDS, DERIVED_CONDITION_IDS,
    ),
    "E8": ExperimentSpec(
        "E8", "derived", "ASR", "heatmap", "obfuscation_type", (CORE_MODELS[0],),
        (CORE_MODELS[0],), DERIVED_CONDITION_IDS, DERIVED_CONDITION_IDS,
    ),
    "E9": ExperimentSpec(
        "E9", "derived", "ASR", "line", "context_position", (CORE_MODELS[0],),
        (CORE_MODELS[0],), DERIVED_CONDITION_IDS, DERIVED_CONDITION_IDS,
    ),
    "E10": ExperimentSpec(
        "E10", "derived", "ASR", "line", "turn_count", (CORE_MODELS[0],),
        (CORE_MODELS[0],), DERIVED_CONDITION_IDS, DERIVED_CONDITION_IDS,
    ),
    "E11": ExperimentSpec(
        "E11", "derived", "ASR", "heatmap", "chain_pattern", (CORE_MODELS[0],),
        (CORE_MODELS[0],), DERIVED_CONDITION_IDS, DERIVED_CONDITION_IDS,
    ),
    "E12": ExperimentSpec(
        "E12", "main", "TCR", "bar_ci", "model", tuple(CORE_MODELS),
        tuple(CORE_MODELS), None, CORE_CONDITION_IDS,
    ),
    "E15": ExperimentSpec(
        "E15", "stability", "ASR", "box", "model_temperature", tuple(CORE_MODELS),
        tuple(CORE_MODELS), None, ("stability_normal_full",),
    ),
}


@dataclass
class ConditionInput:
    stage: str
    job_id: str
    model: str
    backend: str
    condition_id: str
    prompt_profile: str
    guard_mode: str
    guard_modules: tuple[str, ...]
    temperature: float | None
    seed: int | None
    expected_runs: int
    manifest_path: Path
    log_path: Path
    case_path: Path
    cases: list[dict[str, Any]]
    logs: list[dict[str, Any]]


@dataclass
class Inspection:
    experiment_id: str
    status: str
    expected_runs: int
    completed_runs: int
    inputs: list[ConditionInput] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    raw_records: list[dict[str, Any]] = field(default_factory=list)
    case_paths: list[Path] = field(default_factory=list)
    formal_models: list[str] = field(default_factory=list)
    smoke_models: list[str] = field(default_factory=list)


@dataclass
class MetricGroup:
    dimensions: dict[str, Any]
    prompt_profile: str
    guard_mode: str
    guard_modules: tuple[str, ...]
    cases: dict[str, dict[str, Any]] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    job_ids: set[str] = field(default_factory=set)
    log_paths: set[str] = field(default_factory=set)


def _display(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _csv_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _condition_specs(job: ProgramJob) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for value in _csv_values(job.matrix_config.get("conditions")):
        condition_id, separator, configuration = value.partition("=")
        prompt_profile, second, guard_mode = configuration.partition(":")
        if not separator or not second:
            raise ValueError(f"invalid condition specification in {job.job_id}: {value!r}")
        result[condition_id] = (prompt_profile, guard_mode)
    return result


def _formal_requirements(
    spec: ExperimentSpec, program_root: Path
) -> list[tuple[ProgramJob, tuple[str, ...]]]:
    plan = build_stage_plan(
        spec.stage,
        output_root=program_root,
        include_derived_coverage=True,
    )
    jobs = list(plan.jobs)
    if spec.stage == "derived":
        marker = f"__{spec.experiment_id.lower()}__"
        jobs = [job for job in jobs if marker in job.job_id]
    if not jobs:
        raise RuntimeError(f"no shared-program jobs map to {spec.experiment_id}")
    requirements: list[tuple[ProgramJob, tuple[str, ...]]] = []
    for job in jobs:
        all_ids = tuple(_condition_specs(job))
        selected = (
            tuple(condition for condition in all_ids if condition in set(spec.formal_condition_ids))
            if spec.formal_condition_ids is not None
            else all_ids
        )
        if not selected:
            raise RuntimeError(f"{spec.experiment_id} selects no conditions from {job.job_id}")
        requirements.append((job, selected))
    return requirements


def _smoke_requirements(spec: ExperimentSpec, program_root: Path) -> list[ProgramJob]:
    plan = build_stage_plan("smoke", output_root=program_root)
    required = set(spec.smoke_models)
    jobs = [job for job in plan.jobs if job.model in required]
    if {job.model for job in jobs} != required:
        raise RuntimeError(f"smoke plan does not cover models for {spec.experiment_id}")
    return jobs


def chart_contract(spec: ExperimentSpec) -> dict[str, Any]:
    family = {
        "bar_ci": "comparison_and_uncertainty",
        "ablation_bar_ci": "comparison_and_uncertainty",
        "heatmap": "matrix_and_cohort",
        "line": "trend_ordered_axis",
        "box": "distribution",
    }[spec.chart_kind]
    variant = {
        "bar_ci": "grouped_bar_with_wilson_95ci",
        "ablation_bar_ci": "horizontal_bar_with_wilson_95ci",
        "heatmap": "annotated_heatmap",
        "line": "multi_series_line_with_wilson_95ci",
        "box": "grouped_boxplot_across_seeds",
    }[spec.chart_kind]
    if spec.experiment_id == "E4":
        family = "paired_effect_and_uncertainty"
        variant = "paired_ASR_TCR_contribution_forest_with_bootstrap_95ci"
    elif spec.experiment_id == "E15":
        variant = "grouped_boxplot_with_deterministic_seed_points"
    return {
        "analytical_question": spec.definition.question,
        "family": family,
        "variant": variant,
        "metric": spec.primary_metric,
        "dimension": spec.chart_dimension,
        "renderer": "matplotlib_static_png_svg",
        "palette_policy": (
            "single_root" if spec.chart_kind in {"ablation_bar_ci", "heatmap", "box"}
            else "hard_two_root_plus_non_color_styles"
        ),
        "na_policy": "undefined values are labelled NA and never rendered as zero",
        "uncertainty": (
            "case-clustered paired bootstrap 95% confidence intervals"
            if spec.experiment_id == "E4"
            else "raw seed-level points plus distribution summary; box whiskers are not confidence intervals"
            if spec.experiment_id == "E15"
            else "Wilson 95% confidence intervals"
            if spec.chart_kind in {"bar_ci", "ablation_bar_ci", "line"}
            else "numerators, denominators and Wilson intervals remain in chart CSV"
        ),
    }


def build_plan(program_root: str | Path = DEFAULT_PROGRAM_ROOT) -> dict[str, Any]:
    root = Path(program_root).resolve()
    experiments: list[dict[str, Any]] = []
    for experiment_id in TARGET_EXPERIMENTS:
        spec = SPECS[experiment_id]
        formal = _formal_requirements(spec, root)
        smoke = _smoke_requirements(spec, root)
        formal_jobs = []
        expected_runs = 0
        for job, condition_ids in formal:
            per_condition = job.expected_run_count // job.condition_count
            selected_runs = per_condition * len(condition_ids)
            expected_runs += selected_runs
            formal_jobs.append(
                {
                    "stage": job.stage,
                    "job_id": job.job_id,
                    "model": job.model,
                    "condition_ids": list(condition_ids),
                    "expected_runs": selected_runs,
                }
            )
        experiments.append(
            {
                "experiment_id": experiment_id,
                "name": spec.definition.name,
                "formal_stage": spec.stage,
                "formal_jobs": formal_jobs,
                "smoke_jobs": [
                    {
                        "job_id": job.job_id,
                        "model": job.model,
                        "expected_runs": job.expected_run_count,
                    }
                    for job in smoke
                ],
                "expected_formal_runs": expected_runs,
                "formal_models": list(spec.formal_models),
                "compatibility_only_models": sorted(set(spec.smoke_models) - set(spec.formal_models)),
                "chart_contract": chart_contract(spec),
                "required_bundle_artifacts": list(bundle_artifact_names(experiment_id)),
            }
        )
    return {
        "schema_version": "1.0",
        "program_root": _display(root),
        "experiments": experiments,
        "registry_mutation": False,
        "stub_policy": "regression_only_excluded_from_formal_effects",
    }


def _resolve_source_path(value: Any, manifest_path: Path) -> Path:
    candidate = Path(str(value))
    if candidate.is_absolute():
        return candidate.resolve()
    repo_candidate = (ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate
    local_candidate = (manifest_path.parent / candidate).resolve()
    if local_candidate.exists():
        return local_candidate
    return repo_candidate


def _locate_manifest(program_root: Path, stage: str, job_id: str) -> Path:
    direct = program_root / stage / job_id / "manifest.json"
    if direct.exists():
        return direct
    matches = [
        path
        for path in program_root.rglob("manifest.json")
        if path.parent.name == job_id and stage in path.parts
    ]
    return matches[0] if len(matches) == 1 else direct


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    stage: str,
    job_id: str,
    condition_id: str = "",
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "stage": stage,
        "job_id": job_id,
        "condition_id": condition_id,
    }


def _source_record(path: Path, kind: str, **details: Any) -> dict[str, Any]:
    record = {
        "kind": kind,
        "path": _display(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else None,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }
    record.update(details)
    return record


def _select_cases(cases: list[dict[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    selected = list(cases)
    for config_key, case_key in (
        ("families", "attack_family"),
        ("splits", "split"),
        ("sample_types", "sample_type"),
        ("task_types", "task_type"),
        ("case_ids", "case_id"),
    ):
        accepted = set(_csv_values(config.get(config_key)))
        if accepted:
            selected = [
                case for case in selected if str(case.get(case_key, "")).strip() in accepted
            ]
    if bool(config.get("shuffle", False)):
        seed = int(config.get("selection_seed", config.get("generation_seed", 42)))
        random.Random(seed).shuffle(selected)
    limit = config.get("limit")
    if limit not in {None, ""}:
        selected = selected[: int(limit)]
    return selected


def _run_key(row: Mapping[str, Any]) -> str:
    value = str(row.get("run_key", "")).strip()
    if value:
        return value
    return "|".join(
        str(row.get(field, ""))
        for field in ("experiment_id", "model", "condition_id", "case_id", "replicate_id", "seed")
    )


def _log_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    duplicate_steps = 0
    seen_steps: set[tuple[str, int]] = set()
    for row in rows:
        key = _run_key(row)
        by_run[key].append(row)
        identity = (key, int(row.get("step", 0) or 0))
        if identity in seen_steps:
            duplicate_steps += 1
        seen_steps.add(identity)
    unresolved = 0
    nonterminal = 0
    for run_rows in by_run.values():
        ordered = sorted(run_rows, key=lambda item: int(item.get("step", 0) or 0))
        final_status = str(ordered[-1].get("final_status", "")).strip().lower()
        if final_status not in TERMINAL_STATUSES:
            nonterminal += 1
        if (
            any(item.get("parse_ok") is False for item in ordered)
            or any(item.get("timed_out") is True or item.get("refused") is True for item in ordered)
            or final_status in {"", "error", "failed", "max_steps_reached", "parse_error", "refused", "timeout"}
        ):
            unresolved += 1
    return {
        "row_count": len(rows),
        "logical_run_count": len(by_run),
        "distinct_case_count": len({str(row.get("case_id", "")) for row in rows}),
        "parse_failure_rows": sum(row.get("parse_ok") is False for row in rows),
        "unresolved_run_count": unresolved,
        "nonterminal_run_count": nonterminal,
        "duplicate_run_step_rows": duplicate_steps,
    }


def _inspect_job(
    job: ProgramJob,
    selected_condition_ids: Sequence[str],
    *,
    program_root: Path,
    role: str,
) -> tuple[list[ConditionInput], list[dict[str, Any]], list[dict[str, Any]], int, list[Path]]:
    inputs: list[ConditionInput] = []
    issues: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    completed_runs = 0
    case_paths: list[Path] = []
    manifest_path = _locate_manifest(program_root, job.stage, job.job_id)
    if not manifest_path.exists():
        issues.append(
            _issue(
                "pending",
                "missing_matrix_manifest",
                f"matrix manifest not found: {_display(manifest_path)}",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
        records.append(_source_record(manifest_path, f"{role}_matrix_manifest"))
        return inputs, issues, records, completed_runs, case_paths
    records.append(_source_record(manifest_path, f"{role}_matrix_manifest"))
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(
            _issue(
                "failed",
                "invalid_matrix_manifest",
                f"{type(exc).__name__}: {exc}",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
        return inputs, issues, records, completed_runs, case_paths

    manifest_status = str(manifest.get("status", "")).lower()
    if manifest_status != "completed":
        severity = "failed" if manifest_status in {"failed", "blocked"} else "pending"
        issues.append(
            _issue(
                severity,
                "matrix_not_completed",
                f"matrix status is {manifest_status!r}",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
        return inputs, issues, records, completed_runs, case_paths

    expected_backend = str(job.matrix_config.get("backend", ""))
    if manifest.get("model") != job.model or manifest.get("backend") != expected_backend:
        issues.append(
            _issue(
                "failed",
                "matrix_identity_mismatch",
                f"expected model/backend={job.model}/{expected_backend}, got {manifest.get('model')}/{manifest.get('backend')}",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
    if expected_backend == "stub" or manifest.get("oracle_stub") is True:
        issues.append(
            _issue(
                "failed",
                "stub_in_formal_input",
                "Stub is regression-only and cannot enter a formal evidence bundle",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
    if manifest.get("evidence_tier") != "formal_model":
        issues.append(
            _issue(
                "failed",
                "nonformal_evidence_tier",
                f"evidence_tier={manifest.get('evidence_tier')!r}",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
    identity = manifest.get("model_identity", {})
    if not isinstance(identity, dict) or identity.get("tag") != job.model or identity.get("digest") in {None, "", "unknown"}:
        issues.append(
            _issue(
                "failed",
                "missing_model_identity",
                "formal manifest must record the exact model tag and non-unknown digest",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
    if manifest.get("git_commit") in {None, "", "unknown"}:
        issues.append(
            _issue(
                "failed",
                "missing_git_commit",
                "formal matrix manifest has no Git commit",
                stage=job.stage,
                job_id=job.job_id,
            )
        )

    dataset_info = manifest.get("dataset", {})
    dataset_path = _resolve_source_path(
        dataset_info.get("path") or manifest.get("config", {}).get("cases", ""),
        manifest_path,
    )
    records.append(_source_record(dataset_path, f"{role}_case_dataset"))
    if not dataset_path.exists():
        issues.append(
            _issue(
                "failed",
                "missing_case_dataset",
                f"case dataset not found: {_display(dataset_path)}",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
        return inputs, issues, records, completed_runs, case_paths
    case_paths.append(dataset_path)
    if dataset_info.get("sha256") != sha256_file(dataset_path):
        issues.append(
            _issue(
                "failed",
                "dataset_hash_mismatch",
                "case dataset hash does not match matrix manifest",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
    try:
        all_cases = load_jsonl(dataset_path)
    except Exception as exc:
        issues.append(
            _issue(
                "failed",
                "invalid_case_dataset",
                f"{type(exc).__name__}: {exc}",
                stage=job.stage,
                job_id=job.job_id,
            )
        )
        return inputs, issues, records, completed_runs, case_paths
    selected_cases = _select_cases(all_cases, manifest.get("config", {}))
    expected_per_condition = job.expected_run_count // job.condition_count
    repeats = int(manifest.get("config", {}).get("repeats", 1) or 1)
    expected_case_count = expected_per_condition // repeats
    if len(selected_cases) != expected_case_count:
        issues.append(
            _issue(
                "failed",
                "selected_case_count_mismatch",
                f"selected cases={len(selected_cases)}, expected={expected_case_count}",
                stage=job.stage,
                job_id=job.job_id,
            )
        )

    result_rows = manifest.get("results")
    if not isinstance(result_rows, list):
        result_rows = manifest.get("conditions", [])
    result_by_condition = {
        str(item.get("condition_id")): item
        for item in result_rows
        if isinstance(item, dict) and item.get("condition_id")
    }
    condition_meta = {
        str(item.get("condition_id")): item
        for item in manifest.get("conditions", [])
        if isinstance(item, dict) and item.get("condition_id")
    }
    expected_specs = _condition_specs(job)
    for condition_id in selected_condition_ids:
        result = result_by_condition.get(condition_id)
        if result is None:
            issues.append(
                _issue(
                    "failed",
                    "missing_condition_result",
                    "condition result absent from completed matrix manifest",
                    stage=job.stage,
                    job_id=job.job_id,
                    condition_id=condition_id,
                )
            )
            continue
        counters = {
            "selected_run_count": int(result.get("selected_run_count", -1)),
            "completed_run_count": int(result.get("completed_run_count", -1)),
            "error_count": int(result.get("error_count", -1)),
        }
        if (
            result.get("status") != "completed"
            or counters["selected_run_count"] != expected_per_condition
            or counters["completed_run_count"] != expected_per_condition
            or counters["error_count"] != 0
        ):
            issues.append(
                _issue(
                    "failed",
                    "condition_counter_mismatch",
                    f"status/counters={result.get('status')}/{counters}, expected={expected_per_condition}",
                    stage=job.stage,
                    job_id=job.job_id,
                    condition_id=condition_id,
                )
            )
            continue
        log_path = _resolve_source_path(result.get("jsonl", ""), manifest_path)
        if not log_path.exists():
            issues.append(
                _issue(
                    "failed",
                    "missing_run_log",
                    f"JSONL not found: {_display(log_path)}",
                    stage=job.stage,
                    job_id=job.job_id,
                    condition_id=condition_id,
                )
            )
            records.append(_source_record(log_path, f"{role}_raw_log", condition_id=condition_id))
            continue
        actual_hash = sha256_file(log_path)
        if result.get("jsonl_sha256") != actual_hash:
            issues.append(
                _issue(
                    "failed",
                    "run_log_hash_mismatch",
                    "JSONL hash does not match matrix manifest",
                    stage=job.stage,
                    job_id=job.job_id,
                    condition_id=condition_id,
                )
            )
            continue
        try:
            logs = load_jsonl(log_path)
        except Exception as exc:
            issues.append(
                _issue(
                    "failed",
                    "invalid_run_log",
                    f"{type(exc).__name__}: {exc}",
                    stage=job.stage,
                    job_id=job.job_id,
                    condition_id=condition_id,
                )
            )
            continue
        profile = _log_profile(logs)
        records.append(
            _source_record(
                log_path,
                f"{role}_raw_log",
                stage=job.stage,
                job_id=job.job_id,
                condition_id=condition_id,
                model=manifest.get("model"),
                backend=manifest.get("backend"),
                oracle_stub=manifest.get("oracle_stub"),
                evidence_tier=manifest.get("evidence_tier"),
                expected_logical_runs=expected_per_condition,
                **profile,
            )
        )
        selected_ids = {str(case.get("case_id")) for case in selected_cases}
        logged_ids = {str(row.get("case_id")) for row in logs}
        validation_errors: list[str] = []
        if profile["logical_run_count"] != expected_per_condition:
            validation_errors.append(
                f"logical_runs={profile['logical_run_count']} expected={expected_per_condition}"
            )
        if logged_ids != selected_ids:
            validation_errors.append(
                f"case_coverage missing={len(selected_ids - logged_ids)} extra={len(logged_ids - selected_ids)}"
            )
        if profile["duplicate_run_step_rows"]:
            validation_errors.append(f"duplicate_run_steps={profile['duplicate_run_step_rows']}")
        if profile["nonterminal_run_count"]:
            validation_errors.append(f"nonterminal_runs={profile['nonterminal_run_count']}")
        invalid_rows = [
            row
            for row in logs
            if row.get("model") != job.model
            or row.get("backend") != expected_backend
            or row.get("oracle_stub") is True
            or row.get("evidence_tier") != "formal_model"
            or row.get("condition_id") != condition_id
        ]
        if invalid_rows:
            validation_errors.append(f"identity_invalid_rows={len(invalid_rows)}")
        case_type = {str(case.get("case_id")): case.get("sample_type") for case in selected_cases}
        label_mismatches = sum(
            str(row.get("sample_type", "")) != str(case_type.get(str(row.get("case_id")), ""))
            for row in logs
        )
        if label_mismatches:
            validation_errors.append(f"sample_type_mismatch_rows={label_mismatches}")
        run_counts = Counter(_run_key(row) for row in logs if int(row.get("step", 0) or 0) == 1)
        per_case_runs = Counter()
        seen_run_case: set[tuple[str, str]] = set()
        for row in logs:
            identity_pair = (_run_key(row), str(row.get("case_id", "")))
            if identity_pair not in seen_run_case:
                per_case_runs[identity_pair[1]] += 1
                seen_run_case.add(identity_pair)
        if any(per_case_runs[case_id] != repeats for case_id in selected_ids):
            validation_errors.append("per_case_repeat_coverage_mismatch")
        if validation_errors:
            issues.append(
                _issue(
                    "failed",
                    "run_log_integrity_failure",
                    "; ".join(validation_errors),
                    stage=job.stage,
                    job_id=job.job_id,
                    condition_id=condition_id,
                )
            )
            continue
        prompt_profile, guard_mode = expected_specs[condition_id]
        metadata = condition_meta.get(condition_id, {})
        inputs.append(
            ConditionInput(
                stage=job.stage,
                job_id=job.job_id,
                model=job.model,
                backend=expected_backend,
                condition_id=condition_id,
                prompt_profile=prompt_profile,
                guard_mode=guard_mode,
                guard_modules=tuple(sorted(str(item) for item in metadata.get("guard_modules", []))),
                temperature=(
                    float(manifest.get("config", {}).get("temperature"))
                    if manifest.get("config", {}).get("temperature") is not None
                    else None
                ),
                seed=(
                    int(manifest.get("config", {}).get("generation_seed"))
                    if manifest.get("config", {}).get("generation_seed") is not None
                    else None
                ),
                expected_runs=expected_per_condition,
                manifest_path=manifest_path,
                log_path=log_path,
                case_path=dataset_path,
                cases=copy.deepcopy(selected_cases),
                logs=logs,
            )
        )
        completed_runs += expected_per_condition
    return inputs, issues, records, completed_runs, case_paths


def inspect_experiment(
    experiment_id: str,
    *,
    program_root: str | Path = DEFAULT_PROGRAM_ROOT,
) -> Inspection:
    if experiment_id not in SPECS:
        raise ValueError(f"unsupported shared-program analysis experiment: {experiment_id}")
    spec = SPECS[experiment_id]
    root = Path(program_root).resolve()
    formal_requirements = _formal_requirements(spec, root)
    smoke_requirements = _smoke_requirements(spec, root)
    expected_runs = sum(
        (job.expected_run_count // job.condition_count) * len(condition_ids)
        for job, condition_ids in formal_requirements
    )
    inspection = Inspection(
        experiment_id=experiment_id,
        status="pending",
        expected_runs=expected_runs,
        completed_runs=0,
        formal_models=list(spec.formal_models),
        smoke_models=list(spec.smoke_models),
    )
    for job in smoke_requirements:
        condition_ids = tuple(_condition_specs(job))
        _, issues, records, _, case_paths = _inspect_job(
            job,
            condition_ids,
            program_root=root,
            role="smoke_gate",
        )
        inspection.issues.extend(issues)
        inspection.raw_records.extend(records)
        # Smoke cases are prerequisites, not part of formal effect dataset hashes.
        _ = case_paths
    for job, condition_ids in formal_requirements:
        inputs, issues, records, completed, case_paths = _inspect_job(
            job,
            condition_ids,
            program_root=root,
            role="formal",
        )
        inspection.inputs.extend(inputs)
        inspection.issues.extend(issues)
        inspection.raw_records.extend(records)
        inspection.completed_runs += completed
        inspection.case_paths.extend(case_paths)
    inspection.raw_records = _deduplicate_records(inspection.raw_records)
    inspection.case_paths = sorted(set(path.resolve() for path in inspection.case_paths))
    if any(issue["severity"] == "failed" for issue in inspection.issues):
        inspection.status = "failed"
    elif inspection.issues or inspection.completed_runs != inspection.expected_runs:
        inspection.status = "pending"
    else:
        inspection.status = "completed"
    return inspection


def _deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        key = (
            str(record.get("kind")),
            str(record.get("path")),
            str(record.get("condition_id", "")),
        )
        if key not in seen:
            result.append(record)
            seen.add(key)
    return result


def _dimension_value(case: Mapping[str, Any], name: str) -> Any:
    dimensions = case.get("attack_dimensions", {})
    if not isinstance(dimensions, dict):
        dimensions = {}
    if name == "obfuscation_type":
        return dimensions.get("obfuscation_type") or "none"
    if name == "context_tokens":
        return dimensions.get("context_tokens")
    if name == "injection_position_pct":
        return dimensions.get("injection_position_pct")
    if name == "turn_count":
        return dimensions.get("turn_count")
    if name == "multi_turn_mode":
        return dimensions.get("multi_turn_mode") or "none"
    if name == "chain_pattern":
        return dimensions.get("chain_pattern") or "unspecified"
    return case.get(name)


def _group_descriptors(
    experiment_id: str,
    item: ConditionInput,
    case: Mapping[str, Any],
) -> list[dict[str, Any]]:
    base: dict[str, Any] = {
        "model": item.model,
        "condition_id": item.condition_id,
        "scope": "model_condition",
    }
    if experiment_id in {"E1", "E2", "E3", "E5"}:
        return [base]
    if experiment_id == "E4":
        return [{**base, "scope": "ablation_condition", "model": item.model}]
    if experiment_id == "E6":
        family = str(case.get("attack_family", ""))
        if case.get("sample_type") != "attack":
            return []
        return [
            {**base, "scope": "family_by_model", "attack_family": family},
            {
                **base,
                "scope": "family_all_models",
                "model": "all_core",
                "attack_family": family,
            },
        ]
    if experiment_id == "E7":
        return [
            {
                **base,
                "scope": "language",
                "language": _dimension_value(case, "language"),
            }
        ]
    if experiment_id == "E8":
        return [
            {
                **base,
                "scope": "obfuscation",
                "obfuscation_type": _dimension_value(case, "obfuscation_type"),
            }
        ]
    if experiment_id == "E9":
        return [
            {
                **base,
                "scope": "context_position",
                "context_tokens": _dimension_value(case, "context_tokens"),
                "injection_position_pct": _dimension_value(case, "injection_position_pct"),
            }
        ]
    if experiment_id == "E10":
        return [
            {
                **base,
                "scope": "turn_mode",
                "turn_count": _dimension_value(case, "turn_count"),
                "multi_turn_mode": _dimension_value(case, "multi_turn_mode"),
            }
        ]
    if experiment_id == "E11":
        return [
            {
                **base,
                "scope": "chain_pattern",
                "chain_pattern": _dimension_value(case, "chain_pattern"),
            }
        ]
    if experiment_id == "E12":
        if case.get("sample_type") != "benign":
            return []
        return [
            {
                **base,
                "scope": "utility_by_tool_requirement",
                "requires_tool": str(bool(case.get("requires_tool"))).lower(),
            },
            {**base, "scope": "utility_overall", "requires_tool": "all"},
        ]
    if experiment_id == "E15":
        return [
            {
                **base,
                "scope": "stability_seed",
                "temperature": item.temperature,
                "seed": item.seed,
            },
            {
                **base,
                "scope": "stability_temperature",
                "temperature": item.temperature,
                "seed": "all",
            },
        ]
    raise ValueError(experiment_id)


def build_metric_rows(
    experiment_id: str,
    inputs: Sequence[ConditionInput],
) -> list[dict[str, Any]]:
    groups: dict[str, MetricGroup] = {}
    for item in inputs:
        logs_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in item.logs:
            logs_by_case[str(row.get("case_id", ""))].append(row)
        for case in item.cases:
            case_id = str(case.get("case_id", ""))
            for dimensions in _group_descriptors(experiment_id, item, case):
                encoded = json.dumps(dimensions, ensure_ascii=False, sort_keys=True, default=str)
                group = groups.get(encoded)
                if group is None:
                    group = MetricGroup(
                        dimensions=dict(dimensions),
                        prompt_profile=item.prompt_profile,
                        guard_mode=item.guard_mode,
                        guard_modules=item.guard_modules,
                    )
                    groups[encoded] = group
                elif (
                    group.prompt_profile != item.prompt_profile
                    or group.guard_mode != item.guard_mode
                    or group.guard_modules != item.guard_modules
                ):
                    raise ValueError(f"configuration drift within metric group {encoded}")
                group.cases[case_id] = copy.deepcopy(case)
                group.logs.extend(logs_by_case.get(case_id, []))
                group.job_ids.add(item.job_id)
                group.log_paths.add(_display(item.log_path))

    rows: list[dict[str, Any]] = []
    for encoded in sorted(groups):
        group = groups[encoded]
        formal = compute_metrics(
            group.logs,
            list(group.cases.values()),
            label=encoded,
            strict_labels=True,
            include_missing=True,
        )
        row: dict[str, Any] = {
            "experiment_id": experiment_id,
            "scope": group.dimensions.get("scope", ""),
            "model": group.dimensions.get("model", ""),
            "condition_id": group.dimensions.get("condition_id", ""),
            "prompt_profile": group.prompt_profile,
            "guard_mode": group.guard_mode,
            "guard_modules": json.dumps(group.guard_modules, ensure_ascii=False),
            "evidence_tier": "formal_model",
            "source_job_count": len(group.job_ids),
            "source_job_ids": json.dumps(sorted(group.job_ids), ensure_ascii=False),
            "source_log_count": len(group.log_paths),
            "source_log_paths": json.dumps(sorted(group.log_paths), ensure_ascii=False),
        }
        for field_name in DIMENSION_FIELDS:
            row[field_name] = group.dimensions.get(field_name)
        for field_name in COUNT_FIELDS:
            row[field_name] = formal.get(field_name)
        for metric_name in METRIC_NAMES:
            row[metric_name] = formal.get(metric_name)
            row[f"{metric_name}_numerator"] = formal.get(f"{metric_name}_numerator")
            row[f"{metric_name}_denominator"] = formal.get(f"{metric_name}_denominator")
            row[f"{metric_name}_ci_low"] = formal.get(f"{metric_name}_ci_low")
            row[f"{metric_name}_ci_high"] = formal.get(f"{metric_name}_ci_high")
        for field_name in TIMING_FIELDS:
            row[field_name] = formal.get(field_name)
        row["AvgRisk"] = formal.get("AvgRisk")
        row["WRS"] = formal.get("WRS")
        row["data_quality_warnings"] = json.dumps(
            formal.get("data_quality_warnings", []), ensure_ascii=False
        )
        rows.append(row)
    return rows


def metric_fieldnames() -> list[str]:
    fields = [
        "experiment_id",
        "scope",
        "model",
        "condition_id",
        "prompt_profile",
        "guard_mode",
        "guard_modules",
        *DIMENSION_FIELDS,
        "evidence_tier",
        "source_job_count",
        "source_job_ids",
        "source_log_count",
        "source_log_paths",
        *COUNT_FIELDS,
    ]
    for metric_name in METRIC_NAMES:
        fields.extend(
            [
                metric_name,
                f"{metric_name}_numerator",
                f"{metric_name}_denominator",
                f"{metric_name}_ci_low",
                f"{metric_name}_ci_high",
            ]
        )
    fields.extend((*TIMING_FIELDS, "AvgRisk", "WRS", "data_quality_warnings"))
    return list(dict.fromkeys(fields))


def _case_predicate(**expected: Any) -> Callable[[Mapping[str, Any]], bool]:
    def predicate(case: Mapping[str, Any]) -> bool:
        for name, value in expected.items():
            actual = _dimension_value(case, name)
            if actual != value:
                return False
        return True

    return predicate


def _filtered_input_payload(
    inputs: Sequence[ConditionInput],
    predicate: Callable[[Mapping[str, Any]], bool],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: dict[str, dict[str, Any]] = {}
    accepted_ids: set[str] = set()
    for item in inputs:
        for case in item.cases:
            if predicate(case):
                case_id = str(case.get("case_id", ""))
                cases[case_id] = copy.deepcopy(case)
                accepted_ids.add(case_id)
    logs = [
        row
        for item in inputs
        for row in item.logs
        if str(row.get("case_id", "")) in accepted_ids
    ]
    return list(cases.values()), logs


def _compare_subset(
    *,
    comparison_id: str,
    baseline_inputs: Sequence[ConditionInput],
    treatment_inputs: Sequence[ConditionInput],
    predicate: Callable[[Mapping[str, Any]], bool] = lambda case: True,
    dimensions: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    baseline_cases, baseline_logs = _filtered_input_payload(baseline_inputs, predicate)
    treatment_cases, treatment_logs = _filtered_input_payload(treatment_inputs, predicate)
    baseline_ids = {str(case.get("case_id")) for case in baseline_cases}
    treatment_ids = {str(case.get("case_id")) for case in treatment_cases}
    if not baseline_ids and not treatment_ids:
        return None
    if baseline_ids != treatment_ids:
        raise ValueError(
            f"unpaired case coverage for {comparison_id}: "
            f"baseline_only={len(baseline_ids-treatment_ids)}, treatment_only={len(treatment_ids-baseline_ids)}"
        )
    compared = compare_runs(
        baseline_logs,
        treatment_logs,
        baseline_cases,
        strict_labels=True,
        bootstrap_iterations=10_000,
        bootstrap_seed=42,
    )
    return {
        "comparison_id": comparison_id,
        "dimensions": dict(dimensions or {}),
        "baseline": {
            "condition_id": baseline_inputs[0].condition_id,
            "prompt_profile": baseline_inputs[0].prompt_profile,
            "guard_mode": baseline_inputs[0].guard_mode,
        },
        "treatment": {
            "condition_id": treatment_inputs[0].condition_id,
            "prompt_profile": treatment_inputs[0].prompt_profile,
            "guard_mode": treatment_inputs[0].guard_mode,
        },
        "delta": compared["delta"],
        "paired_statistics": compared["paired_statistics"],
    }


def _condition_inputs(
    inputs: Sequence[ConditionInput],
    condition_id: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> list[ConditionInput]:
    return [
        item
        for item in inputs
        if item.condition_id == condition_id
        and (model is None or item.model == model)
        and (temperature is None or item.temperature == temperature)
    ]


def _unique_case_values(
    inputs: Sequence[ConditionInput],
    *dimension_names: str,
    predicate: Callable[[Mapping[str, Any]], bool] = lambda case: True,
) -> list[tuple[Any, ...]]:
    values = {
        tuple(_dimension_value(case, name) for name in dimension_names)
        for item in inputs
        for case in item.cases
        if predicate(case)
    }
    return sorted(values, key=lambda item: tuple(_sort_token(value) for value in item))


def _sort_token(value: Any) -> tuple[int, Any]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    return (1, str(value))


def _paired_comparisons(
    experiment_id: str,
    inputs: Sequence[ConditionInput],
) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []

    def add(
        comparison_id: str,
        baseline: Sequence[ConditionInput],
        treatment: Sequence[ConditionInput],
        predicate: Callable[[Mapping[str, Any]], bool] = lambda case: True,
        dimensions: Mapping[str, Any] | None = None,
    ) -> None:
        if not baseline or not treatment:
            raise ValueError(f"missing paired condition input for {comparison_id}")
        result = _compare_subset(
            comparison_id=comparison_id,
            baseline_inputs=baseline,
            treatment_inputs=treatment,
            predicate=predicate,
            dimensions=dimensions,
        )
        if result is not None:
            comparisons.append(result)

    if experiment_id in {"E1", "E2", "E3", "E5"}:
        pair = {
            "E1": ("regular_none", "regular_full"),
            "E2": ("regular_none", "hardened_none"),
            "E3": ("hardened_none", "hardened_full"),
            "E5": ("regular_none", "regular_full"),
        }[experiment_id]
        for model in CORE_MODELS:
            add(
                f"{experiment_id.lower()}__{model}__{pair[0]}__vs__{pair[1]}",
                _condition_inputs(inputs, pair[0], model=model),
                _condition_inputs(inputs, pair[1], model=model),
                dimensions={"model": model},
            )
    elif experiment_id == "E4":
        baseline_id = "ablation_named_full_guard"
        baseline = _condition_inputs(inputs, baseline_id, model=CORE_MODELS[0])
        for condition_id in sorted({item.condition_id for item in inputs} - {baseline_id}):
            add(
                f"e4__full_vs__{condition_id}",
                baseline,
                _condition_inputs(inputs, condition_id, model=CORE_MODELS[0]),
                dimensions={"condition_id": condition_id},
            )
    elif experiment_id == "E6":
        families = _unique_case_values(
            inputs,
            "attack_family",
            predicate=lambda case: case.get("sample_type") == "attack",
        )
        for model in CORE_MODELS:
            for (family,) in families:
                predicate = _case_predicate(attack_family=family)
                add(
                    f"e6__{model}__{family}",
                    _condition_inputs(inputs, "regular_none", model=model),
                    _condition_inputs(inputs, "regular_full", model=model),
                    predicate,
                    {"model": model, "attack_family": family},
                )
    elif experiment_id in {"E7", "E8", "E9", "E10", "E11"}:
        dimension_names = {
            "E7": ("language",),
            "E8": ("obfuscation_type",),
            "E9": ("context_tokens", "injection_position_pct"),
            "E10": ("turn_count", "multi_turn_mode"),
            "E11": ("chain_pattern",),
        }[experiment_id]
        for values in _unique_case_values(inputs, *dimension_names):
            dimensions = dict(zip(dimension_names, values))
            add(
                f"{experiment_id.lower()}__" + "__".join(str(value) for value in values),
                _condition_inputs(inputs, "derived_normal_off", model=CORE_MODELS[0]),
                _condition_inputs(inputs, "derived_normal_full", model=CORE_MODELS[0]),
                _case_predicate(**dimensions),
                dimensions,
            )
    elif experiment_id == "E12":
        predicate = lambda case: case.get("sample_type") == "benign"
        for model in CORE_MODELS:
            for baseline_id, treatment_id in (
                ("regular_none", "regular_full"),
                ("hardened_none", "hardened_full"),
            ):
                add(
                    f"e12__{model}__{baseline_id}__vs__{treatment_id}",
                    _condition_inputs(inputs, baseline_id, model=model),
                    _condition_inputs(inputs, treatment_id, model=model),
                    predicate,
                    {"model": model, "sample_type": "benign"},
                )
    elif experiment_id == "E15":
        condition_id = "stability_normal_full"
        for model in CORE_MODELS:
            for baseline_temperature, treatment_temperature in ((0.0, 0.2), (0.0, 0.7)):
                add(
                    f"e15__{model}__temp_{baseline_temperature:g}__vs__{treatment_temperature:g}",
                    _condition_inputs(
                        inputs, condition_id, model=model, temperature=baseline_temperature
                    ),
                    _condition_inputs(
                        inputs, condition_id, model=model, temperature=treatment_temperature
                    ),
                    dimensions={
                        "model": model,
                        "baseline_temperature": baseline_temperature,
                        "treatment_temperature": treatment_temperature,
                    },
                )
    else:
        raise ValueError(experiment_id)
    return comparisons


def build_statistics(
    experiment_id: str,
    inputs: Sequence[ConditionInput],
) -> dict[str, Any]:
    comparisons = _paired_comparisons(experiment_id, inputs)
    hypotheses: list[tuple[dict[str, Any], str, float]] = []
    for comparison in comparisons:
        paired = comparison.get("paired_statistics", {})
        for metric_name in ("ASR", "DSR", "TCR"):
            name = f"{metric_name}_mcnemar"
            test = paired.get(name, {})
            if int(test.get("pairs", 0) or 0) > 0 and test.get("p_value") is not None:
                hypotheses.append((comparison, name, float(test["p_value"])))
        latency = paired.get("latency_wilcoxon", {})
        if int(latency.get("pairs", 0) or 0) > 0 and latency.get("p_value") is not None:
            hypotheses.append((comparison, "latency_wilcoxon", float(latency["p_value"])))
    adjusted_values = holm_adjust([item[2] for item in hypotheses]) if hypotheses else []
    correction_rows: list[dict[str, Any]] = []
    for (comparison, test_name, raw_p), adjusted_p in zip(hypotheses, adjusted_values):
        comparison["paired_statistics"][test_name]["holm_adjusted_p"] = adjusted_p
        correction_rows.append(
            {
                "comparison_id": comparison["comparison_id"],
                "test": test_name,
                "raw_p": raw_p,
                "holm_adjusted_p": adjusted_p,
            }
        )
    return {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "status": "completed",
        "evidence_tier": "formal_model_only",
        "methods": {
            "proportions": "raw numerator/denominator plus Wilson 95% confidence interval",
            "paired_binary": "two-sided exact McNemar",
            "paired_effect_ci": "case-clustered paired bootstrap, 10,000 iterations, seed 42",
            "latency": "paired Wilcoxon signed-rank plus rank-biserial effect size",
            "multiplicity": "Holm correction within this experiment evidence family",
            "undefined_values": "null/NA, never numeric zero",
        },
        "comparison_count": len(comparisons),
        "comparisons": comparisons,
        "holm_correction": correction_rows,
    }


def build_chart_rows(
    experiment_id: str,
    metric_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    spec = SPECS[experiment_id]
    focus = set(spec.focus_condition_ids)
    rows: list[dict[str, Any]] = []
    for metric_row in metric_rows:
        condition_id = str(metric_row.get("condition_id", ""))
        if focus and condition_id not in focus:
            continue
        scope = str(metric_row.get("scope", ""))
        chart_x: Any
        chart_series: str
        if experiment_id in {"E1", "E2", "E3", "E5"}:
            if scope != "model_condition":
                continue
            chart_x = metric_row["model"]
            chart_series = condition_id
        elif experiment_id == "E4":
            if scope != "ablation_condition":
                continue
            chart_x = condition_id
            chart_series = spec.primary_metric
        elif experiment_id == "E6":
            if scope != "family_all_models":
                continue
            chart_x = metric_row["attack_family"]
            chart_series = condition_id
        elif experiment_id == "E7":
            if scope != "language":
                continue
            chart_x = metric_row["language"]
            chart_series = condition_id
        elif experiment_id == "E8":
            if scope != "obfuscation":
                continue
            chart_x = metric_row["obfuscation_type"]
            chart_series = condition_id
        elif experiment_id == "E9":
            if scope != "context_position":
                continue
            chart_x = metric_row["injection_position_pct"]
            chart_series = f"{condition_id}|ctx={metric_row['context_tokens']}"
        elif experiment_id == "E10":
            if scope != "turn_mode":
                continue
            chart_x = metric_row["turn_count"]
            chart_series = f"{condition_id}|{metric_row['multi_turn_mode']}"
        elif experiment_id == "E11":
            if scope != "chain_pattern":
                continue
            chart_x = metric_row["chain_pattern"]
            chart_series = condition_id
        elif experiment_id == "E12":
            if scope != "utility_overall":
                continue
            chart_x = metric_row["model"]
            chart_series = condition_id
        elif experiment_id == "E15":
            if scope != "stability_seed":
                continue
            chart_x = f"{metric_row['model']}|T={metric_row['temperature']}"
            chart_series = str(metric_row["model"])
        else:
            raise ValueError(experiment_id)
        metric = spec.primary_metric
        rows.append(
            {
                "experiment_id": experiment_id,
                "chart_kind": spec.chart_kind,
                "chart_metric": metric,
                "chart_x": chart_x,
                "chart_series": chart_series,
                "value": metric_row.get(metric),
                "numerator": metric_row.get(f"{metric}_numerator"),
                "denominator": metric_row.get(f"{metric}_denominator"),
                "ci_low": metric_row.get(f"{metric}_ci_low"),
                "ci_high": metric_row.get(f"{metric}_ci_high"),
                "value_status": (
                    "observed" if metric_row.get(metric) is not None else "NA_zero_denominator"
                ),
                "scope": scope,
                "model": metric_row.get("model"),
                "condition_id": condition_id,
                "prompt_profile": metric_row.get("prompt_profile"),
                "guard_mode": metric_row.get("guard_mode"),
                **{name: metric_row.get(name) for name in DIMENSION_FIELDS},
            }
        )
    condition_order = {
        condition_id: index for index, condition_id in enumerate(spec.focus_condition_ids)
    }
    return sorted(
        rows,
        key=lambda row: (
            _sort_token(row.get("chart_x")),
            condition_order.get(str(row.get("condition_id", "")), len(condition_order)),
            str(row.get("chart_series", "")),
            _sort_token(row.get("seed")),
        ),
    )


def chart_fieldnames() -> list[str]:
    return list(
        dict.fromkeys(
            [
                "experiment_id",
                "chart_kind",
                "chart_metric",
                "chart_x",
                "chart_series",
                "value",
                "numerator",
                "denominator",
                "ci_low",
                "ci_high",
                "value_status",
                "scope",
                "model",
                "condition_id",
                "prompt_profile",
                "guard_mode",
                *DIMENSION_FIELDS,
            ]
        )
    )


def _chart_imports():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


BLUE = "#2F6B9A"
BLUE_LIGHT = "#91B4CE"
ORANGE = "#D97732"
ORANGE_LIGHT = "#E8B089"
GOLD = "#C99A2E"
OLIVE = "#7E8B52"
PINK = "#B66B88"
INK = "#263238"
GRID = "#D9E0E5"
NA_GREY = "#D5D8DA"


def _ci_error(row: Mapping[str, Any]) -> tuple[float, float] | None:
    value = row.get("value")
    low = row.get("ci_low")
    high = row.get("ci_high")
    if value is None or low is None or high is None:
        return None
    return max(0.0, float(value) - float(low)), max(0.0, float(high) - float(value))


def _style_axis(axis: Any, *, y_grid: bool = True) -> None:
    axis.set_facecolor("white")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color("#87939A")
    axis.spines["bottom"].set_color("#87939A")
    axis.tick_params(colors=INK)
    if y_grid:
        axis.grid(axis="y", color=GRID, linestyle="--", linewidth=0.7, alpha=0.8)
        axis.set_axisbelow(True)


def _series_style(series: str, index: int) -> tuple[str, str]:
    lowered = series.lower()
    if "hardened" in lowered:
        color = ORANGE
    elif "full" in lowered or "policy" in lowered or "keyword" in lowered:
        color = BLUE
    else:
        color = ORANGE_LIGHT
    hatches = ("", "//", "xx", "..", "--", "oo", "\\\\")
    return color, hatches[index % len(hatches)]


def _render_bar_ci(
    experiment_id: str,
    rows: Sequence[dict[str, Any]],
    png_path: Path,
    svg_path: Path,
    *,
    horizontal: bool = False,
) -> None:
    plt = _chart_imports()
    categories = list(dict.fromkeys(str(row["chart_x"]) for row in rows))
    series_values = list(dict.fromkeys(str(row["chart_series"]) for row in rows))
    by_key = {(str(row["chart_x"]), str(row["chart_series"])): row for row in rows}
    metric = SPECS[experiment_id].primary_metric
    if horizontal:
        fig_height = max(7.0, 0.42 * len(categories) + 2.4)
        fig, axis = plt.subplots(figsize=(13.5, fig_height))
        positions = list(range(len(categories)))
        for index, category in enumerate(categories):
            row = by_key.get((category, series_values[0]))
            if row is None or row["value"] is None:
                axis.text(0.01, index, "NA", va="center", color="#666666")
                continue
            value = float(row["value"])
            error = _ci_error(row)
            axis.barh(
                index,
                value,
                color=BLUE,
                edgecolor=INK,
                linewidth=0.5,
                xerr=[[error[0]], [error[1]]] if error else None,
                capsize=3,
            )
        axis.set_yticks(positions, categories)
        axis.invert_yaxis()
        axis.set_xlim(0.0, 1.03)
        axis.set_xlabel(metric)
        _style_axis(axis, y_grid=False)
        axis.grid(axis="x", color=GRID, linestyle="--", linewidth=0.7, alpha=0.8)
    else:
        fig_width = max(10.5, 1.2 * len(categories) + 4.0)
        fig, axis = plt.subplots(figsize=(fig_width, 7.0))
        width = min(0.22, 0.78 / max(1, len(series_values)))
        base = list(range(len(categories)))
        for series_index, series in enumerate(series_values):
            color, hatch = _series_style(series, series_index)
            offset = (series_index - (len(series_values) - 1) / 2.0) * width
            label_used = False
            for category_index, category in enumerate(categories):
                row = by_key.get((category, series))
                position = base[category_index] + offset
                if row is None or row["value"] is None:
                    axis.text(
                        position,
                        0.015,
                        "NA",
                        rotation=90,
                        ha="center",
                        va="bottom",
                        fontsize=6.5,
                        color="#666666",
                    )
                    continue
                value = float(row["value"])
                error = _ci_error(row)
                axis.bar(
                    position,
                    value,
                    width=width,
                    color=color,
                    edgecolor=INK,
                    linewidth=0.5,
                    hatch=hatch,
                    label=series if not label_used else None,
                    yerr=[[error[0]], [error[1]]] if error else None,
                    capsize=2.5,
                )
                label_used = True
        axis.set_xticks(base, categories, rotation=18 if len(categories) <= 9 else 35, ha="right")
        axis.set_ylim(0.0, 1.06)
        axis.set_ylabel(metric)
        _style_axis(axis)
        if series_values:
            axis.legend(
                title="Condition",
                frameon=False,
                ncol=min(3, len(series_values)),
                loc="upper center",
            )
    axis.set_title(
        f"{experiment_id}: {metric} by {SPECS[experiment_id].chart_dimension}\n"
        "Proportion with Wilson 95% confidence interval; NA is not zero",
        color=INK,
        pad=14,
    )
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(png_path, dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _render_heatmap(
    experiment_id: str,
    rows: Sequence[dict[str, Any]],
    png_path: Path,
    svg_path: Path,
) -> None:
    plt = _chart_imports()
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    categories = list(dict.fromkeys(str(row["chart_x"]) for row in rows))
    series_values = list(dict.fromkeys(str(row["chart_series"]) for row in rows))
    by_key = {(str(row["chart_x"]), str(row["chart_series"])): row for row in rows}
    matrix = np.full((len(categories), len(series_values)), np.nan, dtype=float)
    for row_index, category in enumerate(categories):
        for column_index, series in enumerate(series_values):
            row = by_key.get((category, series))
            if row is not None and row["value"] is not None:
                matrix[row_index, column_index] = float(row["value"])
    masked = np.ma.masked_invalid(matrix)
    palette = LinearSegmentedColormap.from_list("m3_blue", ["#F4F7FA", BLUE_LIGHT, BLUE])
    palette.set_bad(NA_GREY)
    fig_height = max(5.5, 0.5 * len(categories) + 2.5)
    fig, axis = plt.subplots(figsize=(9.5, fig_height))
    image = axis.imshow(masked, vmin=0.0, vmax=1.0, cmap=palette, aspect="auto")
    axis.set_xticks(range(len(series_values)), series_values, rotation=20, ha="right")
    axis.set_yticks(range(len(categories)), categories)
    for row_index in range(len(categories)):
        for column_index in range(len(series_values)):
            value = matrix[row_index, column_index]
            label = "NA" if math.isnan(value) else f"{value:.2f}"
            color = "#666666" if math.isnan(value) or value < 0.58 else "white"
            axis.text(column_index, row_index, label, ha="center", va="center", color=color, fontsize=8)
    colorbar = fig.colorbar(image, ax=axis, fraction=0.035, pad=0.035)
    colorbar.set_label(SPECS[experiment_id].primary_metric)
    axis.set_xlabel("Condition")
    axis.set_ylabel(SPECS[experiment_id].chart_dimension)
    axis.set_title(
        f"{experiment_id}: {SPECS[experiment_id].primary_metric} heatmap\n"
        "Cell values are proportions; exact counts and Wilson intervals are in chart CSV",
        color=INK,
        pad=14,
    )
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(png_path, dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _line_style(series: str, index: int) -> tuple[str, str, str]:
    color = BLUE if "full" in series else ORANGE
    line_styles = ("-", "--", "-.", ":")
    markers = ("o", "s", "^", "D", "P", "X")
    return color, line_styles[(index // 2) % len(line_styles)], markers[index % len(markers)]


def _render_line(
    experiment_id: str,
    rows: Sequence[dict[str, Any]],
    png_path: Path,
    svg_path: Path,
) -> None:
    plt = _chart_imports()
    series_values = list(dict.fromkeys(str(row["chart_series"]) for row in rows))
    fig, axis = plt.subplots(figsize=(12.5, 7.2))
    for index, series in enumerate(series_values):
        series_rows = sorted(
            [row for row in rows if str(row["chart_series"]) == series],
            key=lambda row: _sort_token(row["chart_x"]),
        )
        observed = [row for row in series_rows if row["value"] is not None]
        if not observed:
            continue
        x_values = [float(row["chart_x"]) for row in observed]
        y_values = [float(row["value"]) for row in observed]
        lower = [
            float(row["value"]) - float(row["ci_low"])
            if row.get("ci_low") is not None
            else 0.0
            for row in observed
        ]
        upper = [
            float(row["ci_high"]) - float(row["value"])
            if row.get("ci_high") is not None
            else 0.0
            for row in observed
        ]
        color, linestyle, marker = _line_style(series, index)
        axis.errorbar(
            x_values,
            y_values,
            yerr=[lower, upper],
            label=series,
            color=color,
            linestyle=linestyle,
            marker=marker,
            markersize=5,
            linewidth=1.5,
            capsize=2.5,
            markerfacecolor="white" if index % 2 else color,
            markeredgecolor=color,
        )
    all_x = sorted({float(row["chart_x"]) for row in rows}, key=float)
    axis.set_xticks(all_x, [f"{value:g}" for value in all_x])
    axis.set_ylim(0.0, 1.06)
    axis.set_xlabel(SPECS[experiment_id].chart_dimension)
    axis.set_ylabel(SPECS[experiment_id].primary_metric)
    axis.set_title(
        f"{experiment_id}: {SPECS[experiment_id].primary_metric} by ordered experiment axis\n"
        "Points show proportions with Wilson 95% confidence intervals",
        color=INK,
        pad=14,
    )
    _style_axis(axis)
    axis.legend(frameon=False, ncol=2, fontsize=8, loc="upper center")
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(png_path, dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _seed_point_layout(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return deterministic E15 seed-point positions without random jitter."""

    categories = sorted({str(row["chart_x"]) for row in rows}, key=_sort_token)
    seeds = sorted(
        {row.get("seed") for row in rows if row.get("value") is not None},
        key=_sort_token,
    )
    if any(seed is None for seed in seeds):
        raise ValueError("E15 seed points require an explicit seed for every observed value")
    if not seeds:
        return []
    if len(seeds) == 1:
        offsets = {seeds[0]: 0.0}
    else:
        offsets = {
            seed: -0.14 + 0.28 * index / (len(seeds) - 1)
            for index, seed in enumerate(seeds)
        }
    category_positions = {category: index for index, category in enumerate(categories, start=1)}
    seen: set[tuple[str, Any]] = set()
    points: list[dict[str, Any]] = []
    for row in rows:
        if row.get("value") is None:
            continue
        category = str(row["chart_x"])
        seed = row.get("seed")
        key = (category, seed)
        if key in seen:
            raise ValueError(f"E15 has duplicate seed point for {category}: seed={seed}")
        seen.add(key)
        points.append(
            {
                "category": category,
                "seed": seed,
                "seed_index": seeds.index(seed),
                "x": category_positions[category] + offsets[seed],
                "value": float(row["value"]),
            }
        )
    return points


def _render_box(
    experiment_id: str,
    rows: Sequence[dict[str, Any]],
    png_path: Path,
    svg_path: Path,
) -> None:
    plt = _chart_imports()
    categories = sorted({str(row["chart_x"]) for row in rows}, key=_sort_token)
    samples = [
        [float(row["value"]) for row in rows if str(row["chart_x"]) == category and row["value"] is not None]
        for category in categories
    ]
    if any(not sample for sample in samples):
        missing = [category for category, sample in zip(categories, samples) if not sample]
        raise ValueError(f"E15 boxplot has no observed value for: {missing}")
    fig, axis = plt.subplots(figsize=(15.5, 7.2))
    boxes = axis.boxplot(
        samples,
        tick_labels=categories,
        patch_artist=True,
        showmeans=True,
        showfliers=False,
        medianprops={"color": INK, "linewidth": 1.4},
        meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": INK, "markersize": 4},
        whiskerprops={"color": INK},
        capprops={"color": INK},
        flierprops={"marker": "o", "markerfacecolor": "white", "markeredgecolor": BLUE, "markersize": 3},
    )
    shades = ("#DCE9F2", BLUE_LIGHT, BLUE)
    for index, box in enumerate(boxes["boxes"]):
        box.set_facecolor(shades[index % len(shades)])
        box.set_edgecolor(INK)
        box.set_linewidth(0.6)
    points = _seed_point_layout(rows)
    seeds = sorted({point["seed"] for point in points}, key=_sort_token)
    color_map = plt.get_cmap("tab10")
    for point in points:
        axis.scatter(
            point["x"],
            point["value"],
            s=28,
            color=color_map(point["seed_index"] % 10),
            edgecolor="white",
            linewidth=0.55,
            alpha=0.92,
            zorder=4,
        )
    for seed_index, seed in enumerate(seeds):
        axis.scatter(
            [],
            [],
            s=28,
            color=color_map(seed_index % 10),
            edgecolor="white",
            linewidth=0.55,
            label=f"seed={seed}",
        )
    axis.set_ylim(0.0, 1.06)
    axis.set_ylabel(SPECS[experiment_id].primary_metric)
    axis.set_xticklabels(categories, rotation=35, ha="right")
    axis.set_title(
        "E15: ASR distribution across ten seeds by model and temperature\n"
        "Boxes summarize distributions; deterministic points show every seed-level proportion",
        color=INK,
        pad=14,
    )
    _style_axis(axis)
    if seeds:
        axis.legend(
            title="Raw seed points",
            frameon=False,
            ncol=min(5, len(seeds)),
            fontsize=7,
            loc="upper center",
        )
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(png_path, dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _render_ablation_contribution_forest(
    rows: Sequence[dict[str, Any]],
    png_path: Path,
    svg_path: Path,
) -> dict[str, Any]:
    """Render paired E4 ASR/TCR effects using the same variant-minus-full direction."""

    if not rows:
        raise ValueError("E4 contribution forest requires at least one comparison")
    plt = _chart_imports()
    labels = [str(row.get("variant_condition_id") or row.get("comparison_id")) for row in rows]
    panels = (
        (
            "ASR",
            "ASR_variant_minus_full_bootstrap",
            "ASR_variant_minus_full_ci_low",
            "ASR_variant_minus_full_ci_high",
            "#B24A3A",
            "ASR change (variant − full)",
            "Positive means the variant has higher attack success than full Guard",
        ),
        (
            "TCR",
            "TCR_variant_minus_full_bootstrap",
            "TCR_variant_minus_full_ci_low",
            "TCR_variant_minus_full_ci_high",
            BLUE,
            "TCR change (variant − full)",
            "Positive means the variant has higher task completion than full Guard",
        ),
    )
    fig_height = max(6.8, 0.48 * len(labels) + 2.8)
    fig, axes = plt.subplots(1, 2, figsize=(16.2, fig_height), sharey=True)
    integrity: dict[str, Any] = {
        "row_count": len(rows),
        "direction": "variant_minus_full",
        "interval_method": "case_clustered_paired_bootstrap_95ci",
    }
    for panel_index, (metric, estimate_field, low_field, high_field, color, xlabel, subtitle) in enumerate(panels):
        axis = axes[panel_index]
        finite_values = [0.0]
        interval_count = 0
        point_count = 0
        for row_index, row in enumerate(rows):
            estimate = row.get(estimate_field)
            low = row.get(low_field)
            high = row.get(high_field)
            observed = all(
                value is not None and math.isfinite(float(value))
                for value in (estimate, low, high)
            )
            if observed:
                estimate_value = float(estimate)
                low_value = float(low)
                high_value = float(high)
                axis.errorbar(
                    estimate_value,
                    row_index,
                    xerr=[
                        [max(0.0, estimate_value - low_value)],
                        [max(0.0, high_value - estimate_value)],
                    ],
                    fmt="o",
                    color=color,
                    markeredgecolor="white",
                    markeredgewidth=0.65,
                    markersize=7,
                    capsize=3,
                    linewidth=1.25,
                    zorder=3,
                )
                finite_values.extend((estimate_value, low_value, high_value))
                interval_count += 1
                point_count += 1
            elif estimate is not None and math.isfinite(float(estimate)):
                estimate_value = float(estimate)
                axis.scatter(estimate_value, row_index, color=color, marker="x", zorder=3)
                finite_values.append(estimate_value)
                point_count += 1
            else:
                axis.text(0.0, row_index, "NA", ha="center", va="center", color="#666666")
        extent = max(0.05, max(abs(value) for value in finite_values) * 1.18)
        axis.set_xlim(-extent, extent)
        axis.axvline(0.0, color=INK, linewidth=0.9, linestyle="--", zorder=1)
        axis.set_xlabel(xlabel)
        axis.set_title(f"{metric}\n{subtitle}", fontsize=11, color=INK, pad=10)
        axis.grid(axis="x", color=GRID, linestyle="--", linewidth=0.7, alpha=0.8)
        axis.set_axisbelow(True)
        for spine in ("top", "right", "left"):
            axis.spines[spine].set_visible(False)
        axis.spines["bottom"].set_color(GRID)
        integrity[f"{metric}_point_count"] = point_count
        integrity[f"{metric}_interval_count"] = interval_count
    axes[0].set_yticks(range(len(labels)), labels)
    axes[0].invert_yaxis()
    axes[1].tick_params(axis="y", left=False, labelleft=False)
    fig.suptitle(
        "E4 paired ablation contribution forest",
        fontsize=15,
        color=INK,
        y=0.995,
    )
    fig.text(
        0.5,
        0.012,
        "Points and intervals are variant − named full Guard; bars are case-clustered paired bootstrap 95% CIs. "
        "Exact paired n and McNemar/Holm results are in ablation_contributions.csv.",
        ha="center",
        fontsize=8.5,
        color="#536372",
    )
    fig.patch.set_facecolor("white")
    fig.tight_layout(rect=(0, 0.045, 1, 0.965))
    fig.savefig(png_path, dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return integrity


def render_primary_chart(
    experiment_id: str,
    rows: Sequence[dict[str, Any]],
    png_path: Path,
    svg_path: Path,
) -> None:
    if not rows:
        raise ValueError(f"no chart rows for {experiment_id}")
    kind = SPECS[experiment_id].chart_kind
    if kind == "bar_ci":
        _render_bar_ci(experiment_id, rows, png_path, svg_path)
    elif kind == "ablation_bar_ci":
        _render_bar_ci(experiment_id, rows, png_path, svg_path, horizontal=True)
    elif kind == "heatmap":
        _render_heatmap(experiment_id, rows, png_path, svg_path)
    elif kind == "line":
        _render_line(experiment_id, rows, png_path, svg_path)
    elif kind == "box":
        _render_box(experiment_id, rows, png_path, svg_path)
    else:
        raise ValueError(f"unsupported chart kind: {kind}")
    if png_path.stat().st_size <= 100 or svg_path.stat().st_size <= 100:
        raise RuntimeError(f"chart export is empty for {experiment_id}")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field_name: "" if row.get(field_name) is None else row.get(field_name) for field_name in fieldnames}
            )


def _metric_rows_for_scope(
    metric_rows: Sequence[dict[str, Any]], *scopes: str
) -> list[dict[str, Any]]:
    accepted = set(scopes)
    return [row for row in metric_rows if str(row.get("scope", "")) in accepted]


def _long_metric_view(
    metric_rows: Sequence[dict[str, Any]], metric_names: Sequence[str]
) -> list[dict[str, Any]]:
    """Return an auditable long-form view without coercing undefined values."""

    rows: list[dict[str, Any]] = []
    for source in metric_rows:
        for metric_name in metric_names:
            value = source.get(metric_name)
            rows.append(
                {
                    "experiment_id": source.get("experiment_id"),
                    "scope": source.get("scope"),
                    "model": source.get("model"),
                    "condition_id": source.get("condition_id"),
                    "prompt_profile": source.get("prompt_profile"),
                    "guard_mode": source.get("guard_mode"),
                    **{name: source.get(name) for name in DIMENSION_FIELDS},
                    "metric": metric_name,
                    "value": value,
                    "numerator": source.get(f"{metric_name}_numerator"),
                    "denominator": source.get(f"{metric_name}_denominator"),
                    "ci_low": source.get(f"{metric_name}_ci_low"),
                    "ci_high": source.get(f"{metric_name}_ci_high"),
                    "value_status": "observed" if value is not None else "NA_zero_denominator",
                    "evidence_tier": source.get("evidence_tier"),
                }
            )
    return rows


def _long_metric_fieldnames() -> list[str]:
    return list(
        dict.fromkeys(
            [
                "experiment_id",
                "scope",
                "model",
                "condition_id",
                "prompt_profile",
                "guard_mode",
                *DIMENSION_FIELDS,
                "metric",
                "value",
                "numerator",
                "denominator",
                "ci_low",
                "ci_high",
                "value_status",
                "evidence_tier",
            ]
        )
    )


def _negate_or_none(value: Any) -> float | None:
    return None if value is None else -float(value)


def _ablation_contribution_rows(statistics: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten full-vs-variant paired effects with direction made explicit."""

    rows: list[dict[str, Any]] = []
    for comparison in statistics.get("comparisons", []):
        delta = comparison.get("delta", {})
        paired = comparison.get("paired_statistics", {})
        mcnemar = paired.get("ASR_mcnemar", {})
        bootstrap = paired.get("ASR_bootstrap_guard_minus_baseline", {})
        tcr_mcnemar = paired.get("TCR_mcnemar", {})
        tcr_bootstrap = paired.get("TCR_bootstrap_guard_minus_baseline", {})
        rows.append(
            {
                "experiment_id": "E4",
                "comparison_id": comparison.get("comparison_id"),
                "full_condition_id": comparison.get("baseline", {}).get("condition_id"),
                "variant_condition_id": comparison.get("treatment", {}).get("condition_id"),
                # compare_runs defines ASR_reduction as baseline - treatment.
                # Here baseline is full Guard and treatment is the ablation, so
                # the intuitive degradation from ablation is the sign inverse.
                "ASR_full_minus_variant": delta.get("ASR_reduction"),
                "ASR_increase_when_variant_replaces_full": _negate_or_none(
                    delta.get("ASR_reduction")
                ),
                "DSR_full_minus_variant": delta.get("DSR_reduction"),
                "DSR_increase_when_variant_replaces_full": _negate_or_none(
                    delta.get("DSR_reduction")
                ),
                "BSR_variant_minus_full": delta.get("BSR_gain"),
                "TCR_variant_minus_full": delta.get("TCR_change"),
                "ASR_paired_pairs": mcnemar.get("pairs"),
                "ASR_mcnemar_p": mcnemar.get("p_value"),
                "ASR_mcnemar_holm_p": mcnemar.get("holm_adjusted_p"),
                "ASR_variant_minus_full_bootstrap": bootstrap.get("estimate"),
                "ASR_variant_minus_full_ci_low": bootstrap.get("ci_low"),
                "ASR_variant_minus_full_ci_high": bootstrap.get("ci_high"),
                "TCR_paired_pairs": tcr_mcnemar.get("pairs"),
                "TCR_mcnemar_p": tcr_mcnemar.get("p_value"),
                "TCR_mcnemar_holm_p": tcr_mcnemar.get("holm_adjusted_p"),
                "TCR_variant_minus_full_bootstrap": tcr_bootstrap.get("estimate"),
                "TCR_variant_minus_full_ci_low": tcr_bootstrap.get("ci_low"),
                "TCR_variant_minus_full_ci_high": tcr_bootstrap.get("ci_high"),
                "bootstrap_iterations": bootstrap.get("iterations"),
                "bootstrap_seed": bootstrap.get("seed"),
            }
        )
    return rows


def _ablation_contribution_fieldnames() -> list[str]:
    return [
        "experiment_id",
        "comparison_id",
        "full_condition_id",
        "variant_condition_id",
        "ASR_full_minus_variant",
        "ASR_increase_when_variant_replaces_full",
        "DSR_full_minus_variant",
        "DSR_increase_when_variant_replaces_full",
        "BSR_variant_minus_full",
        "TCR_variant_minus_full",
        "ASR_paired_pairs",
        "ASR_mcnemar_p",
        "ASR_mcnemar_holm_p",
        "ASR_variant_minus_full_bootstrap",
        "ASR_variant_minus_full_ci_low",
        "ASR_variant_minus_full_ci_high",
        "TCR_paired_pairs",
        "TCR_mcnemar_p",
        "TCR_mcnemar_holm_p",
        "TCR_variant_minus_full_bootstrap",
        "TCR_variant_minus_full_ci_low",
        "TCR_variant_minus_full_ci_high",
        "bootstrap_iterations",
        "bootstrap_seed",
    ]


def _case_replay_payload(inputs: Sequence[ConditionInput]) -> dict[str, Any]:
    """Build deterministic E11 chain replays from the validated raw logs."""

    replays: list[dict[str, Any]] = []
    for item in sorted(inputs, key=lambda value: (value.model, value.condition_id, value.job_id)):
        cases = {str(case.get("case_id", "")): case for case in item.cases}
        by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in item.logs:
            by_run[_run_key(row)].append(row)
        for run_key, run_rows in sorted(by_run.items()):
            ordered = sorted(run_rows, key=lambda row: int(row.get("step", 0) or 0))
            first = ordered[0]
            final = ordered[-1]
            case_id = str(first.get("case_id", ""))
            case = cases.get(case_id, {})
            replays.append(
                {
                    "run_key": run_key,
                    "job_id": item.job_id,
                    "model": item.model,
                    "condition_id": item.condition_id,
                    "prompt_profile": item.prompt_profile,
                    "guard_mode": item.guard_mode,
                    "case_id": case_id,
                    "template_id": case.get("template_id"),
                    "sample_type": case.get("sample_type"),
                    "chain_pattern": _dimension_value(case, "chain_pattern"),
                    "authorized_actions": case.get("authorized_actions", []),
                    "unsafe_target_actions": case.get("unsafe_target_actions", []),
                    "replicate_id": first.get("replicate_id"),
                    "seed": first.get("seed"),
                    "step_count": len(ordered),
                    "final_status": final.get("final_status"),
                    "attack_success": any(bool(row.get("attack_success")) for row in ordered),
                    "data_spill": any(bool(row.get("data_spill")) for row in ordered),
                    "task_completed": any(bool(row.get("task_completed")) for row in ordered),
                    "steps": [
                        {
                            "step": row.get("step"),
                            "raw_model_output": row.get("raw_model_output"),
                            "parsed_tool_call": row.get("parsed_tool_call"),
                            "parse_ok": row.get("parse_ok"),
                            "parse_error": row.get("parse_error"),
                            "guard_decision": row.get("guard_decision"),
                            "risk_score": row.get("risk_score"),
                            "reasons": row.get("reasons", []),
                            "observation": row.get("observation"),
                            "final_status": row.get("final_status"),
                            "timed_out": row.get("timed_out"),
                            "model_latency_ms": row.get("model_latency_ms"),
                            "guard_latency_ms": row.get("guard_latency_ms"),
                            "total_latency_ms": row.get("total_latency_ms"),
                        }
                        for row in ordered
                    ],
                }
            )
    return {
        "schema_version": "1.0",
        "experiment_id": "E11",
        "status": "completed",
        "evidence_tier": "formal_model_only",
        "replay_count": len(replays),
        "replays": replays,
    }


def _write_specialized_artifacts(
    experiment_id: str,
    out_dir: Path,
    metric_rows: Sequence[dict[str, Any]],
    statistics: Mapping[str, Any],
    inputs: Sequence[ConditionInput],
) -> list[tuple[Path, str]]:
    """Write registry-compatible experiment views from the same formal rows."""

    artifacts: list[tuple[Path, str]] = []

    def write_metrics(name: str, rows: Sequence[dict[str, Any]]) -> None:
        path = out_dir / name
        _write_csv(path, rows, metric_fieldnames())
        artifacts.append((path, "specialized_metrics"))

    if experiment_id == "E4":
        path = out_dir / "ablation_contributions.csv"
        rows = _ablation_contribution_rows(statistics)
        _write_csv(path, rows, _ablation_contribution_fieldnames())
        artifacts.append((path, "ablation_contributions"))
        forest_png = out_dir / "ablation_contribution_forest.png"
        forest_svg = out_dir / "ablation_contribution_forest.svg"
        _render_ablation_contribution_forest(rows, forest_png, forest_svg)
        artifacts.extend(((forest_png, "figure"), (forest_svg, "figure")))
    elif experiment_id == "E6":
        family_rows = _metric_rows_for_scope(
            metric_rows, "family_by_model", "family_all_models"
        )
        write_metrics("by_family.csv", family_rows)
        ci_path = out_dir / "by_family_ci.csv"
        ci_rows = _long_metric_view(family_rows, ("ASR", "Recall", "DSR"))
        _write_csv(ci_path, ci_rows, _long_metric_fieldnames())
        artifacts.append((ci_path, "confidence_intervals"))
    elif experiment_id == "E7":
        write_metrics("by_language.csv", _metric_rows_for_scope(metric_rows, "language"))
    elif experiment_id == "E8":
        mutation_rows = _metric_rows_for_scope(metric_rows, "obfuscation")
        write_metrics("by_mutation.csv", mutation_rows)
        strength_path = out_dir / "strength_curve.csv"
        strength_rows = _long_metric_view(mutation_rows, ("ASR", "Recall", "DSR"))
        for row in strength_rows:
            # E8 has categorical mutation types but no validated ordinal
            # strength variable. Keep that limitation machine-readable instead
            # of inventing a numeric axis.
            row["strength_axis_status"] = "NA_no_ordinal_strength_in_dataset"
            row["strength_level"] = None
        _write_csv(
            strength_path,
            strength_rows,
            [*_long_metric_fieldnames(), "strength_axis_status", "strength_level"],
        )
        artifacts.append((strength_path, "evasion_strength_view"))
    elif experiment_id == "E9":
        write_metrics(
            "context_position.csv", _metric_rows_for_scope(metric_rows, "context_position")
        )
    elif experiment_id == "E10":
        write_metrics("by_turn_count.csv", _metric_rows_for_scope(metric_rows, "turn_mode"))
    elif experiment_id == "E11":
        write_metrics(
            "chain_metrics.csv", _metric_rows_for_scope(metric_rows, "chain_pattern")
        )
        replay_path = out_dir / "case_replays.json"
        _write_json(replay_path, _case_replay_payload(inputs))
        artifacts.append((replay_path, "case_replay"))
    elif experiment_id == "E12":
        write_metrics(
            "utility_metrics.csv",
            _metric_rows_for_scope(
                metric_rows, "utility_by_tool_requirement", "utility_overall"
            ),
        )
    elif experiment_id == "E15":
        write_metrics(
            "stability.csv",
            _metric_rows_for_scope(metric_rows, "stability_seed", "stability_temperature"),
        )
    return artifacts


def _figure_manifest_specs(
    experiment_id: str,
    *,
    source_quality: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    spec = SPECS[experiment_id]
    quality = dict(source_quality or {})
    primary_role = "secondary" if experiment_id == "E4" else "primary"
    primary_order = 20 if experiment_id == "E4" else 10
    chart_type = {
        "bar_ci": "grouped_bar_with_wilson_95ci",
        "ablation_bar_ci": "absolute_proportion_bar_with_wilson_95ci",
        "heatmap": "annotated_proportion_heatmap",
        "line": "ordered_line_with_wilson_95ci",
        "box": "boxplot_with_deterministic_seed_points",
    }[spec.chart_kind]
    uncertainty = (
        [
            {
                "metric": spec.primary_metric,
                "method": "wilson",
                "level": 0.95,
                "estimate_field": "value",
                "low_field": "ci_low",
                "high_field": "ci_high",
                "n_field": "denominator",
            }
        ]
        if spec.chart_kind in {"bar_ci", "ablation_bar_ci", "line"}
        else []
    )
    warnings: list[str] = []
    if experiment_id == "E4":
        warnings.append("absolute ASR proportions are secondary; use the paired contribution forest for effects")
        warnings.append(
            "parse-warning rows remain in the registered case-run denominators and are not dropped "
            f"(parse_failure_rows={int(quality.get('parse_failure_rows', 0) or 0)}, "
            f"logical_case_runs={int(quality.get('logical_case_runs', 0) or 0)})"
        )
    if experiment_id == "E15":
        warnings.append("box whiskers summarize seed distributions and are not confidence intervals")
    figures: list[dict[str, Any]] = [
        {
            "id": f"{experiment_id.lower()}_primary_chart",
            "title": f"{experiment_id} {spec.primary_metric} by {spec.chart_dimension}",
            "role": primary_role,
            "order": primary_order,
            "chart_type": chart_type,
            "caption": (
                "Static chart generated from the adjacent audited chart CSV; undefined values remain NA."
            ),
            "files": {
                "data": "primary_chart_data.csv",
                "png": "primary_chart.png",
                "svg": "primary_chart.svg",
            },
            "metrics": [spec.primary_metric],
            "grain": [spec.chart_dimension, "seed"] if experiment_id == "E15" else [spec.chart_dimension],
            "uncertainty": uncertainty,
            "warnings": warnings,
        }
    ]
    if experiment_id == "E4":
        figures.insert(
            0,
            {
                "id": "e4_ablation_contribution",
                "title": "E4 paired ablation contribution: ASR and TCR",
                "role": "primary",
                "order": 10,
                "chart_type": "paired_effect_forest",
                "caption": (
                    "Both panels use variant minus named full Guard; positive ASR is worse safety, "
                    "while positive TCR is improved task completion."
                ),
                "files": {
                    "data": "ablation_contributions.csv",
                    "png": "ablation_contribution_forest.png",
                    "svg": "ablation_contribution_forest.svg",
                },
                "metrics": ["ASR", "TCR"],
                "grain": ["variant_condition_id"],
                "uncertainty": [
                    {
                        "metric": metric,
                        "method": "case_clustered_paired_bootstrap",
                        "level": 0.95,
                        "estimate_field": f"{metric}_variant_minus_full_bootstrap",
                        "low_field": f"{metric}_variant_minus_full_ci_low",
                        "high_field": f"{metric}_variant_minus_full_ci_high",
                        "n_field": f"{metric}_paired_pairs",
                    }
                    for metric in ("ASR", "TCR")
                ],
                "warnings": [
                    "single-model ablation; do not generalize across models",
                    "parse-warning and unresolved case-runs remain in denominators; warnings are not discarded",
                ],
            },
        )
    return figures


def _raw_index(
    inspection: Inspection,
    *,
    program_root: Path,
) -> dict[str, Any]:
    formal_logs = [record for record in inspection.raw_records if record["kind"] == "formal_raw_log"]
    smoke_logs = [
        record for record in inspection.raw_records if record["kind"] == "smoke_gate_raw_log"
    ]
    return {
        "schema_version": "1.0",
        "experiment_id": inspection.experiment_id,
        "generated_at": utc_now(),
        "program_root": _display(program_root),
        "status": inspection.status,
        "formal_run_expectation": inspection.expected_runs,
        "formal_runs_validated": inspection.completed_runs,
        "formal_raw_log_count": len(formal_logs),
        "smoke_gate_raw_log_count": len(smoke_logs),
        "smoke_gate_models": sorted(
            {str(record.get("model")) for record in smoke_logs if record.get("model")}
        ),
        "records": inspection.raw_records,
        "issues": inspection.issues,
        "stub_records_admitted": sum(
            record.get("backend") == "stub" for record in inspection.raw_records
        ),
    }


def _source_quality(inspection: Inspection) -> dict[str, Any]:
    formal = [record for record in inspection.raw_records if record["kind"] == "formal_raw_log"]
    return {
        "formal_raw_log_count": len(formal),
        "raw_step_rows": sum(int(record.get("row_count", 0) or 0) for record in formal),
        "logical_case_runs": sum(int(record.get("logical_run_count", 0) or 0) for record in formal),
        "parse_failure_rows": sum(int(record.get("parse_failure_rows", 0) or 0) for record in formal),
        "unresolved_case_runs": sum(int(record.get("unresolved_run_count", 0) or 0) for record in formal),
        "nonterminal_case_runs": sum(int(record.get("nonterminal_run_count", 0) or 0) for record in formal),
        "duplicate_run_step_rows": sum(
            int(record.get("duplicate_run_step_rows", 0) or 0) for record in formal
        ),
    }


def _format_percent(value: Any) -> str:
    return "NA" if value is None else f"{100.0 * float(value):.1f}%"


def build_analysis_markdown(
    inspection: Inspection,
    *,
    program_root: str | Path = DEFAULT_PROGRAM_ROOT,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    metric_rows: Sequence[dict[str, Any]] = (),
    chart_rows: Sequence[dict[str, Any]] = (),
    statistics: Mapping[str, Any] | None = None,
    generation_error: str = "",
) -> str:
    experiment_id = inspection.experiment_id
    spec = SPECS[experiment_id]
    quality = _source_quality(inspection)
    lines = [
        f"# {experiment_id} {spec.definition.name} 证据分析",
        "",
        f"- 状态：`{inspection.status}`。",
        f"- 分析问题：{spec.definition.question}",
        f"- 正式运行完整度：{inspection.completed_runs}/{inspection.expected_runs}。",
        "- 证据边界：正式指标仅使用真实 Ollama 模型；Stub 仅允许作为回归证据，未进入本实验任何正式分母。",
        "- 缺失、解析失败、拒答、超时与最大步数不会被补零或静默删除。",
        "",
        "## 数据与粒度",
        "",
        "案例级指标按 case-run 计算；调用级 Precision/Recall/FPR 按可判定工具调用计算；"
        "延迟按配对 case-run 计算。相同实验的模型、条件与维度切片保持独立分母。",
        "",
        f"- 正式模型：{', '.join(spec.formal_models)}。",
        f"- Smoke 门禁模型：{', '.join(spec.smoke_models)}。",
        f"- 正式 JSONL：{quality['formal_raw_log_count']} 个；原始步骤行：{quality['raw_step_rows']}。",
        f"- 逻辑案例运行：{quality['logical_case_runs']}；未解决案例运行：{quality['unresolved_case_runs']}。",
        f"- 解析失败行：{quality['parse_failure_rows']}；非终态运行：{quality['nonterminal_case_runs']}；重复 run-step：{quality['duplicate_run_step_rows']}。",
        "- 分母政策：解析失败、未解决及其他 warning 案例运行仍保留在预注册分母中；warning 不是丢弃条件。",
    ]
    compatibility = sorted(set(spec.smoke_models) - set(spec.formal_models))
    if compatibility:
        lines.append(
            "- 兼容性基线："
            + ", ".join(compatibility)
            + " 仅记录 6-case Smoke 兼容性，不与四个核心模型的盲测分母合并。"
        )

    if inspection.issues:
        lines.extend(
            [
                "",
                "## 输入完整性问题",
                "",
                "| 严重度 | 代码 | Stage / Job / Condition | 说明 |",
                "|---|---|---|---|",
            ]
        )
        for issue in inspection.issues:
            identity = " / ".join(
                value
                for value in (issue["stage"], issue["job_id"], issue.get("condition_id", ""))
                if value
            )
            lines.append(
                f"| {issue['severity']} | `{issue['code']}` | `{identity}` | {issue['message']} |"
            )
        lines.extend(
            [
                "",
                "输入未完整冻结，因此不生成正式指标、统计检验或效果图，也不会把本实验标记为 completed。",
            ]
        )
    elif generation_error:
        lines.extend(
            [
                "",
                "## 证据生成失败",
                "",
                f"`{generation_error}`",
                "",
                "原始输入虽通过完整性检查，但派生产物失败；manifest 保持 failed，不能据此引用效果结论。",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## 指标结果",
                "",
                f"主图指标为 {spec.primary_metric}。所有比例均同时保留原始计数、分母与 Wilson 95% 置信区间；"
                "CSV 中空单元格表示 NA，不表示 0。",
                "",
                "| Scope | Model | Condition | Dimension | Value | Count | Wilson 95% CI |",
                "|---|---|---|---|---:|---:|---:|",
            ]
        )
        display_rows = list(chart_rows)[:30]
        for row in display_rows:
            dimensions = []
            for name in DIMENSION_FIELDS:
                value = row.get(name)
                if value not in {None, "", "all"} and name not in {"temperature", "seed"}:
                    dimensions.append(f"{name}={value}")
            if row.get("temperature") not in {None, ""}:
                dimensions.append(f"temperature={row.get('temperature')}")
            ci = (
                "NA"
                if row.get("ci_low") is None or row.get("ci_high") is None
                else f"[{_format_percent(row['ci_low'])}, {_format_percent(row['ci_high'])}]"
            )
            count = f"{row.get('numerator')}/{row.get('denominator')}"
            lines.append(
                f"| {row.get('scope')} | {row.get('model')} | `{row.get('condition_id')}` | "
                f"{'; '.join(dimensions) or row.get('chart_x')} | {_format_percent(row.get('value'))} | {count} | {ci} |"
            )
        if len(chart_rows) > len(display_rows):
            lines.append(f"\n表中展示前 {len(display_rows)} 行；完整 {len(chart_rows)} 行见主图相邻 CSV。")
        primary_values = [float(row["value"]) for row in chart_rows if row.get("value") is not None]
        lines.extend(
            [
                "",
                "## 统计方法与解释边界",
                "",
                f"- 配对比较：{statistics.get('comparison_count', 0) if statistics else 0} 组。",
                "- 二元结果使用双侧精确 McNemar；ASR/DSR/TCR 差值使用按案例聚类的 10,000 次配对 bootstrap。",
                "- 延迟使用配对 Wilcoxon 与 rank-biserial 效应量；同一实验内的可用假设统一做 Holm 校正。",
                "- 不以单一 p 值判断效果；必须同时引用效应量、置信区间和原始分母。",
                "- 不同实验矩阵（主矩阵、长上下文、多轮、稳定性）不互相混入分母。",
            ]
        )
        if primary_values:
            lines.append(
                f"- 主图可定义值范围：{min(primary_values):.4f}–{max(primary_values):.4f}；"
                "该范围只是证据概览，不替代逐条件统计。"
            )
        na_count = sum(row.get("value") is None for row in chart_rows)
        lines.append(f"- 主图 NA 单元：{na_count}；均未绘制为 0。")
        lines.extend(
            [
                "",
                "## 图表契约",
                "",
                "```json",
                json.dumps(chart_contract(spec), ensure_ascii=False, indent=2, sort_keys=True),
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "## 可复现命令",
            "",
            "```powershell",
            f"python -m experiments.analyze_program --experiments {experiment_id} "
            f"--program-root '{_display(Path(program_root))}' "
            f"--out-root '{_display(Path(output_root))}'",
            "```",
            "",
            "本生成器不修改 `experiments/registry.json`；只有外部验收流程可以依据完整证据更新注册表状态。",
        ]
    )
    return "\n".join(lines) + "\n"


def _required_artifact_paths(experiment_id: str, out_dir: Path) -> list[str]:
    return [_display(out_dir / name) for name in bundle_artifact_names(experiment_id)]


def _new_evidence_manifest(
    inspection: Inspection,
    *,
    program_root: Path,
    out_dir: Path,
    runtime_context: Mapping[str, Any],
) -> dict[str, Any]:
    spec = SPECS[inspection.experiment_id]
    now = utc_now()
    case_paths = inspection.case_paths
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "experiment_id": inspection.experiment_id,
        "experiment_name": spec.definition.name,
        "question": spec.definition.question,
        "status": "running",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "git": dict(runtime_context["git"]),
        "dataset": {
            "paths": [_display(path) for path in case_paths],
            "sha256": sha256_paths(case_paths) if case_paths else None,
        },
        "models": list(spec.formal_models),
        "compatibility_only_models": sorted(set(spec.smoke_models) - set(spec.formal_models)),
        "configuration": {
            "source_program_root": _display(program_root),
            "source_status": inspection.status,
            "evidence_tier": "formal_model_only",
            "stub_policy": "regression_only_excluded_from_formal_denominators",
            "strict_sample_type": True,
            "undefined_metric_policy": "null_not_zero",
            "bootstrap_iterations": 10_000,
            "bootstrap_seed": 42,
            "chart_contract": chart_contract(spec),
            "registry_mutation": False,
        },
        "command": [
            "python",
            "-m",
            "experiments.analyze_program",
            "--experiments",
            inspection.experiment_id,
            "--program-root",
            _display(program_root),
            "--out-root",
            _display(out_dir.parent),
        ],
        "environment": copy.deepcopy(runtime_context["environment"]),
        "progress": {
            "expected_runs": inspection.expected_runs,
            "completed_runs": inspection.completed_runs,
            "failed_jobs": sum(issue["severity"] == "failed" for issue in inspection.issues),
            "unresolved_cases": _source_quality(inspection)["unresolved_case_runs"],
        },
        "required_artifacts": _required_artifact_paths(inspection.experiment_id, out_dir),
        "artifacts": [],
        "events": [
            {
                "at": now,
                "type": "analysis_started",
                "message": "shared program evidence analysis started",
            }
        ],
        "failure": None,
        "input_quality": {
            "status": inspection.status,
            "issue_count": len(inspection.issues),
            "issues": inspection.issues,
            **_source_quality(inspection),
        },
    }


def _record_to_path(record: Mapping[str, Any]) -> Path:
    value = Path(str(record.get("path", "")))
    return value if value.is_absolute() else (ROOT / value).resolve()


def _register_source_artifacts(manifest: dict[str, Any], inspection: Inspection) -> None:
    for record in inspection.raw_records:
        if not record.get("exists"):
            continue
        path = _record_to_path(record)
        kind = str(record.get("kind", ""))
        if kind == "formal_raw_log":
            register_artifact(manifest, path, kind="raw_log")
        elif kind == "smoke_gate_raw_log":
            register_artifact(manifest, path, kind="smoke_gate_log")
        elif kind.endswith("matrix_manifest"):
            register_artifact(manifest, path, kind="source_manifest")


DERIVED_ARTIFACT_NAMES = (
    "metrics.csv",
    "statistics.json",
    FIGURE_MANIFEST_FILENAME,
    "primary_chart_data.csv",
    "primary_chart.png",
    "primary_chart.svg",
    *tuple(
        name
        for experiment_names in SPECIALIZED_ARTIFACT_NAMES.values()
        for name in experiment_names
    ),
)


def _remove_stale_derived_artifacts(out_dir: Path) -> None:
    for name in DERIVED_ARTIFACT_NAMES:
        path = out_dir / name
        if path.exists() and path.is_file():
            path.unlink()


def generate_bundle(
    inspection: Inspection,
    *,
    program_root: str | Path,
    output_root: str | Path,
    runtime_context: Mapping[str, Any],
) -> dict[str, Any]:
    program = Path(program_root).resolve()
    out_dir = Path(output_root).resolve() / inspection.experiment_id
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    raw_index_path = out_dir / "raw_run_index.json"
    analysis_path = out_dir / "analysis.md"
    manifest = _new_evidence_manifest(
        inspection,
        program_root=program,
        out_dir=out_dir,
        runtime_context=runtime_context,
    )
    save_manifest(manifest, manifest_path)
    raw_index = _raw_index(inspection, program_root=program)
    _write_json(raw_index_path, raw_index)

    if inspection.status != "completed":
        _remove_stale_derived_artifacts(out_dir)
        analysis_path.write_text(
            build_analysis_markdown(
                inspection,
                program_root=program,
                output_root=out_dir.parent,
            ),
            encoding="utf-8",
        )
        register_artifact(manifest, raw_index_path, kind="raw_log_index")
        register_artifact(manifest, analysis_path, kind="analysis")
        _register_source_artifacts(manifest, inspection)
        if inspection.status == "failed":
            fail_manifest(
                manifest,
                category="InputIntegrityFailure",
                message=f"{len(inspection.issues)} input completeness/integrity issue(s)",
            )
        else:
            manifest["status"] = "pending"
            record_event(
                manifest,
                "pending",
                "required shared-program inputs are not complete",
                issue_count=len(inspection.issues),
            )
        save_manifest(manifest, manifest_path)
        return manifest

    metrics_path = out_dir / "metrics.csv"
    statistics_path = out_dir / "statistics.json"
    chart_data_path = out_dir / "primary_chart_data.csv"
    png_path = out_dir / "primary_chart.png"
    svg_path = out_dir / "primary_chart.svg"
    try:
        metric_rows = build_metric_rows(inspection.experiment_id, inspection.inputs)
        statistics = build_statistics(inspection.experiment_id, inspection.inputs)
        chart_rows = build_chart_rows(inspection.experiment_id, metric_rows)
        _write_csv(metrics_path, metric_rows, metric_fieldnames())
        _write_json(statistics_path, statistics)
        _write_csv(chart_data_path, chart_rows, chart_fieldnames())
        render_primary_chart(inspection.experiment_id, chart_rows, png_path, svg_path)
        specialized_artifacts = _write_specialized_artifacts(
            inspection.experiment_id,
            out_dir,
            metric_rows,
            statistics,
            inspection.inputs,
        )
        analysis_path.write_text(
            build_analysis_markdown(
                inspection,
                program_root=program,
                output_root=out_dir.parent,
                metric_rows=metric_rows,
                chart_rows=chart_rows,
                statistics=statistics,
            ),
            encoding="utf-8",
        )
        figure_manifest_path = write_figure_manifest(
            out_dir,
            experiment_id=inspection.experiment_id,
            evidence_tier="formal_model",
            figures=_figure_manifest_specs(
                inspection.experiment_id,
                source_quality=_source_quality(inspection),
            ),
        )

        _register_source_artifacts(manifest, inspection)
        register_artifact(manifest, raw_index_path, kind="raw_log_index")
        register_artifact(manifest, metrics_path, kind="metrics")
        register_artifact(manifest, statistics_path, kind="statistics")
        register_artifact(manifest, analysis_path, kind="analysis")
        register_artifact(manifest, chart_data_path, kind="figure_data")
        register_artifact(manifest, png_path, kind="figure")
        register_artifact(manifest, svg_path, kind="figure")
        for artifact_path, artifact_kind in specialized_artifacts:
            register_artifact(manifest, artifact_path, kind=artifact_kind)
        register_artifact(manifest, figure_manifest_path, kind="figure_manifest")
        record_event(
            manifest,
            "input_validated",
            "all required real-model logs and smoke gates validated",
            formal_runs=inspection.expected_runs,
        )
        finish_manifest(
            manifest,
            completed_runs=inspection.expected_runs,
            failed_jobs=0,
            unresolved_cases=_source_quality(inspection)["unresolved_case_runs"],
        )
        save_manifest(manifest, manifest_path)
        return manifest
    except Exception as exc:
        _remove_stale_derived_artifacts(out_dir)
        message = f"{type(exc).__name__}: {exc}"
        inspection.status = "failed"
        analysis_path.write_text(
            build_analysis_markdown(
                inspection,
                program_root=program,
                output_root=out_dir.parent,
                generation_error=message,
            ),
            encoding="utf-8",
        )
        manifest["progress"]["failed_jobs"] = max(
            1, int(manifest["progress"].get("failed_jobs", 0) or 0)
        )
        fail_manifest(manifest, category="EvidenceGenerationFailure", message=message)
        register_artifact(manifest, raw_index_path, kind="raw_log_index")
        register_artifact(manifest, analysis_path, kind="analysis")
        _register_source_artifacts(manifest, inspection)
        save_manifest(manifest, manifest_path)
        return manifest


def _normalize_experiment_ids(values: str | Iterable[str] | None) -> list[str]:
    if values is None:
        return list(TARGET_EXPERIMENTS)
    raw = _csv_values(values)
    selected: list[str] = []
    for value in raw:
        experiment_id = value.upper()
        if experiment_id not in SPECS:
            raise ValueError(
                f"unsupported experiment {value!r}; expected one of {', '.join(TARGET_EXPERIMENTS)}"
            )
        if experiment_id not in selected:
            selected.append(experiment_id)
    return selected


def analyze_program(
    *,
    program_root: str | Path = DEFAULT_PROGRAM_ROOT,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    experiments: str | Iterable[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    program = Path(program_root).resolve()
    output = Path(output_root).resolve()
    selected = _normalize_experiment_ids(experiments)
    inspections = [inspect_experiment(experiment_id, program_root=program) for experiment_id in selected]
    if dry_run:
        return {
            "mode": "dry_run",
            "program_root": _display(program),
            "output_root": _display(output),
            "registry_mutated": False,
            "experiments": [
                {
                    "experiment_id": inspection.experiment_id,
                    "status": inspection.status,
                    "expected_runs": inspection.expected_runs,
                    "completed_runs": inspection.completed_runs,
                    "issue_count": len(inspection.issues),
                    "issues": inspection.issues,
                }
                for inspection in inspections
            ],
        }
    runtime_context = {
        "git": git_state(),
        "environment": environment_snapshot(),
    }
    manifests = [
        generate_bundle(
            inspection,
            program_root=program,
            output_root=output,
            runtime_context=runtime_context,
        )
        for inspection in inspections
    ]
    return {
        "mode": "generate",
        "program_root": _display(program),
        "output_root": _display(output),
        "registry_mutated": False,
        "experiments": [
            {
                "experiment_id": manifest["experiment_id"],
                "status": manifest["status"],
                "completed_runs": manifest["progress"]["completed_runs"],
                "expected_runs": manifest["progress"]["expected_runs"],
                "manifest": _display(output / manifest["experiment_id"] / "manifest.json"),
            }
            for manifest in manifests
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--program-root",
        default=str(DEFAULT_PROGRAM_ROOT),
        help="Shared run_program output root containing stage/job manifests",
    )
    parser.add_argument(
        "--out-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Parent directory for E1-E12/E15 evidence bundles",
    )
    parser.add_argument(
        "--experiments",
        default=",".join(TARGET_EXPERIMENTS),
        help="Comma-separated subset of E1-E12,E15",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print exact expected jobs, runs, smoke gates and chart contracts; read/write no results",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate available inputs and print statuses without writing evidence bundles",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.plan_only:
        payload = build_plan(args.program_root)
        selected = set(_normalize_experiment_ids(args.experiments))
        payload["experiments"] = [
            item for item in payload["experiments"] if item["experiment_id"] in selected
        ]
    else:
        payload = analyze_program(
            program_root=args.program_root,
            output_root=args.out_root,
            experiments=args.experiments,
            dry_run=args.dry_run,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    statuses = [item.get("status") for item in payload.get("experiments", [])]
    if any(status == "failed" for status in statuses):
        return 2
    if any(status == "pending" for status in statuses):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
