"""Analyze the admitted 5,082-record public primary-model matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import experiments.paper_v2.public_primary_merge_review_v2 as merge_v2
import experiments.paper_v2.public_primary_result_admission_v1 as admission_v1
from experiments.paper_v2.contracts import (  # noqa: E402
    canonical_json_bytes,
    sha256_canonical_json,
    validate_experiment_record,
)
from experiments.paper_v2.medium_analysis import (  # noqa: E402
    analyze_medium_records,
)
from m3_eval.statistics import proportion_result  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/public_execution_plan_v1.jsonl"
)
GATE_SPEC_PATH = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_gate_spec_v1.json"
)
DEFAULT_OUTPUT = admission_v1.ANALYSIS_OUTPUT_ROOT
SUMMARY_NAME = "public_primary_analysis_summary_v1.json"
CONDITION_CSV_NAME = "public_primary_condition_summary_v1.csv"
MANIFEST_NAME = "analysis_manifest.json"
SCHEMA_VERSION = "m3-paper-v2-public-primary-analysis-1.0"
CONDITIONS = (
    "no_defense",
    "safe_prompt_or_spotlighting",
    "promptguard_detector_only",
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_full",
)
CONDITION_LABELS = {
    "no_defense": "No defense",
    "safe_prompt_or_spotlighting": "Safe prompt",
    "promptguard_detector_only": "PromptGuard",
    "strongest_peer_reviewed_structural_baseline": "Structural",
    "m3_policy_only": "M3 policy",
    "m3_full": "M3 full",
}
BENCHMARKS = ("agentdojo-v1", "m3-v2")
FIGURE_FILES = (
    "public_primary_security_v1.png",
    "public_primary_security_v1.svg",
    "public_primary_utility_v1.png",
    "public_primary_utility_v1.svg",
    "public_primary_diagnostics_v1.png",
    "public_primary_diagnostics_v1.svg",
)


class PublicPrimaryAnalysisError(ValueError):
    """Raised when admitted public primary evidence is incomplete or drifts."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicPrimaryAnalysisError(f"{path}: expected an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise PublicPrimaryAnalysisError(f"missing JSONL input: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise PublicPrimaryAnalysisError(
                    f"{path}:{number}: expected an object"
                )
            rows.append(value)
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _primary_plan() -> list[dict[str, Any]]:
    rows = [
        row
        for row in _read_jsonl(PLAN_PATH)
        if row.get("model_role") == "primary"
    ]
    if len(rows) != 5082:
        raise PublicPrimaryAnalysisError(
            f"expected 5082 primary plan rows, observed {len(rows)}"
        )
    keys = [(row["case_id"], row["condition_id"]) for row in rows]
    if (
        len(set(keys)) != 5082
        or set(row["condition_id"] for row in rows) != set(CONDITIONS)
        or set(row["benchmark"] for row in rows) != set(BENCHMARKS)
    ):
        raise PublicPrimaryAnalysisError("public primary plan matrix drift")
    return rows


def _records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in admission_v1._record_paths():
        for envelope in _read_jsonl(path):
            record = envelope.get("record")
            if not isinstance(record, dict):
                raise PublicPrimaryAnalysisError(
                    f"{path}: missing record envelope"
                )
            validate_experiment_record(record)
            if record["included_in_intention_to_treat"] is not True:
                raise PublicPrimaryAnalysisError(
                    "all public records must remain in ITT"
                )
            records.append(record)
    if len(records) != 5082:
        raise PublicPrimaryAnalysisError(
            f"expected 5082 public primary records, observed {len(records)}"
        )
    return records


def _validate_matrix(
    records: list[dict[str, Any]],
    plan: list[dict[str, Any]],
) -> None:
    expected = {
        (row["case_id"], row["condition_id"]): row for row in plan
    }
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (record["case_id"], record["condition_id"])
        if key in observed:
            raise PublicPrimaryAnalysisError(
                f"duplicate public record: {key}"
            )
        observed[key] = record
    if set(observed) != set(expected):
        raise PublicPrimaryAnalysisError(
            "public record case-condition coverage drift"
        )
    for key, record in observed.items():
        plan_row = expected[key]
        if (
            record["benchmark_id"] != plan_row["benchmark"]
            or record["evaluation_case_type"]
            != plan_row["evaluation_case_type"]
            or record["authorization_regime"] != "auto_compiled"
        ):
            raise PublicPrimaryAnalysisError(
                f"public record plan projection drift: {key}"
            )


def _case_index(plan: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {"case_id": case_id}
        for case_id in sorted({str(row["case_id"]) for row in plan})
    ]


def _case_manifest(
    plan: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    case_ids = {str(row["case_id"]) for row in plan}
    return {
        "case_count": len(case_ids),
        "core_conditions": list(CONDITIONS),
        "regime_probe_cases": 0,
    }


def _condition_rows(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for benchmark in (*BENCHMARKS, "all"):
        benchmark_rows = (
            records
            if benchmark == "all"
            else [
                row for row in records if row["benchmark_id"] == benchmark
            ]
        )
        for case_type in ("attack", "benign_tool", "benign_no_tool"):
            for condition in CONDITIONS:
                selected = [
                    row
                    for row in benchmark_rows
                    if row["evaluation_case_type"] == case_type
                    and row["condition_id"] == condition
                ]
                if not selected:
                    continue
                if case_type == "attack":
                    events = sum(bool(row["unsafe_effect_itt"]) for row in selected)
                    endpoint = "unsafe_effect_itt"
                else:
                    events = sum(bool(row["task_completion"]) for row in selected)
                    endpoint = "task_completion"
                proportion = proportion_result(events, len(selected))
                latencies = [
                    float(row["latency_ms"]["total"]) for row in selected
                ]
                result.append(
                    {
                        "benchmark": benchmark,
                        "evaluation_case_type": case_type,
                        "condition_id": condition,
                        "endpoint": endpoint,
                        "events": events,
                        "total": len(selected),
                        "rate": proportion["value"],
                        "wilson_low": proportion["ci_low"],
                        "wilson_high": proportion["ci_high"],
                        "diagnostic_records": sum(
                            row["result_tier"] == "diagnostic"
                            for row in selected
                        ),
                        "operational_failure_records": sum(
                            row["operational_status"] != "completed"
                            for row in selected
                        ),
                        "initial_allow": sum(
                            row["initial_guard_decision"] == "ALLOW"
                            for row in selected
                        ),
                        "initial_ask": sum(
                            row["initial_guard_decision"] == "ASK"
                            for row in selected
                        ),
                        "initial_deny": sum(
                            row["initial_guard_decision"] == "DENY"
                            for row in selected
                        ),
                        "latency_median_ms": median(latencies),
                        "latency_p95_ms": _percentile(latencies, 0.95),
                        "prompt_tokens": sum(
                            int(row["token_usage"]["input"])
                            for row in selected
                        ),
                        "completion_tokens": sum(
                            int(row["token_usage"]["output"])
                            for row in selected
                        ),
                        "total_tokens": sum(
                            int(row["token_usage"]["total"])
                            for row in selected
                        ),
                    }
                )
    return result


def _operational_summary(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    diagnostics = [
        row for row in records if row["result_tier"] == "diagnostic"
    ]
    return {
        "record_count": len(records),
        "formal_candidate_count": len(records) - len(diagnostics),
        "diagnostic_count": len(diagnostics),
        "diagnostic_fraction": len(diagnostics) / len(records),
        "diagnostics_by_benchmark": dict(
            sorted(Counter(row["benchmark_id"] for row in diagnostics).items())
        ),
        "diagnostics_by_condition": dict(
            sorted(Counter(row["condition_id"] for row in diagnostics).items())
        ),
        "operational_status_counts": dict(
            sorted(Counter(row["operational_status"] for row in records).items())
        ),
        "result_tier_counts": dict(
            sorted(Counter(row["result_tier"] for row in records).items())
        ),
        "all_records_in_itt": all(
            row["included_in_intention_to_treat"] is True for row in records
        ),
        "diagnostic_records_excluded": 0,
    }


def _analysis_report(
    records: list[dict[str, Any]],
    plan: list[dict[str, Any]],
    *,
    admission: Mapping[str, Any],
    candidate: Mapping[str, Any],
    merge: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    gate_spec = _load_json(GATE_SPEC_PATH)
    overall = analyze_medium_records(
        records,
        case_manifest=_case_manifest(plan),
        case_index=_case_index(plan),
        gate_spec=gate_spec,
    )
    by_benchmark: dict[str, Any] = {}
    for benchmark in BENCHMARKS:
        benchmark_records = [
            row for row in records if row["benchmark_id"] == benchmark
        ]
        benchmark_plan = [
            row for row in plan if row["benchmark"] == benchmark
        ]
        by_benchmark[benchmark] = analyze_medium_records(
            benchmark_records,
            case_manifest=_case_manifest(benchmark_plan),
            case_index=_case_index(benchmark_plan),
            gate_spec=gate_spec,
        )
    condition_rows = _condition_rows(records)
    core = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_primary_model_empirical_fallback",
        "model_role": "primary",
        "model_id": "deepseek-v4-pro",
        "result_admission_manifest_sha256": admission["manifest_sha256"],
        "result_candidate_manifest_sha256": candidate["manifest_sha256"],
        "primary_merge_manifest_sha256": merge["manifest_sha256"],
        "coverage": {
            "records": len(records),
            "cases": len({row["case_id"] for row in records}),
            "attack_cases": len(
                {
                    row["case_id"]
                    for row in records
                    if row["evaluation_case_type"] == "attack"
                }
            ),
            "benign_cases": len(
                {
                    row["case_id"]
                    for row in records
                    if row["evaluation_case_type"] != "attack"
                }
            ),
            "benchmarks": list(BENCHMARKS),
            "conditions": list(CONDITIONS),
        },
        "operational": _operational_summary(records),
        "overall": overall,
        "by_benchmark": by_benchmark,
        "claim_decision": {
            "route": "empirical_security_utility_fallback",
            "clean_mechanism_quality_claim_eligible": False,
            "reason": (
                "The frozen one-percent diagnostic quality gate failed; "
                "all terminal diagnostics remain in the ITT denominator."
            ),
            "primary_model_only": True,
            "cross_model_claim_authorized": False,
            "cross_provider_claim_authorized": False,
            "sota_claim_authorized": False,
        },
        "analysis_boundary": {
            "new_provider_calls": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "diagnostic_records_excluded": 0,
            "results_accessed_only_after_admission": True,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}, condition_rows


def _write_condition_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        raise PublicPrimaryAnalysisError("condition summary is empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _metric_lookup(
    rows: list[dict[str, Any]],
    *,
    benchmark: str,
    case_type: str,
) -> dict[str, dict[str, Any]]:
    return {
        row["condition_id"]: row
        for row in rows
        if row["benchmark"] == benchmark
        and row["evaluation_case_type"] == case_type
    }


def _save_figure(fig: plt.Figure, output_root: Path, stem: str) -> None:
    fig.savefig(
        output_root / f"{stem}.png",
        dpi=180,
        bbox_inches="tight",
        metadata={"Software": "M3-PI Guard"},
    )
    fig.savefig(
        output_root / f"{stem}.svg",
        bbox_inches="tight",
        metadata={"Date": None},
    )
    plt.close(fig)


def _write_figures(
    output_root: Path,
    rows: list[dict[str, Any]],
) -> None:
    colors = {"agentdojo-v1": "#2878B5", "m3-v2": "#D95F02"}
    x = list(range(len(CONDITIONS)))
    width = 0.36
    for case_type, stem, ylabel, title in (
        (
            "attack",
            "public_primary_security_v1",
            "Unsafe-effect rate (ITT)",
            "Public primary attack outcomes",
        ),
        (
            "benign_tool",
            "public_primary_utility_v1",
            "Task-completion rate",
            "Public primary benign-tool utility",
        ),
    ):
        fig, ax = plt.subplots(figsize=(10.5, 5.8))
        for offset, benchmark in zip((-width / 2, width / 2), BENCHMARKS):
            lookup = _metric_lookup(
                rows,
                benchmark=benchmark,
                case_type=case_type,
            )
            values = [lookup[condition]["rate"] for condition in CONDITIONS]
            ax.bar(
                [position + offset for position in x],
                values,
                width,
                label=benchmark,
                color=colors[benchmark],
            )
        ax.set_ylim(0, 1)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(
            [CONDITION_LABELS[item] for item in CONDITIONS],
            rotation=20,
            ha="right",
        )
        ax.grid(axis="y", alpha=0.25)
        ax.legend(frameon=False)
        fig.tight_layout()
        _save_figure(fig, output_root, stem)

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    for offset, benchmark in zip((-width / 2, width / 2), BENCHMARKS):
        lookup = _metric_lookup(
            rows,
            benchmark=benchmark,
            case_type="attack",
        )
        values = [
            lookup[condition]["diagnostic_records"]
            / lookup[condition]["total"]
            for condition in CONDITIONS
        ]
        ax.bar(
            [position + offset for position in x],
            values,
            width,
            label=benchmark,
            color=colors[benchmark],
        )
    ax.axhline(
        0.01,
        color="#C44E52",
        linestyle="--",
        linewidth=1.4,
        label="Frozen 1% quality gate",
    )
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Diagnostic-record fraction")
    ax.set_title("Public primary diagnostic burden")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [CONDITION_LABELS[item] for item in CONDITIONS],
        rotation=20,
        ha="right",
    )
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    _save_figure(fig, output_root, "public_primary_diagnostics_v1")


def _file_lock(path: Path) -> dict[str, Any]:
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def analyze(
    *,
    admission_path: Path = admission_v1.ADMISSION_PATH,
    output_root: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    admission = admission_v1.validate_admission(_load_json(admission_path))
    if (
        admission["authorization"][
            "scientific_outcome_access_authorized"
        ]
        is not True
    ):
        raise PublicPrimaryAnalysisError(
            "public primary result access is not authorized"
        )
    candidate = admission_v1.verify_candidate()
    merge = merge_v2.verify_primary_merge_review()
    if output_root.exists():
        raise PublicPrimaryAnalysisError(
            "public primary analysis output root already exists"
        )
    plan = _primary_plan()
    records = _records()
    _validate_matrix(records, plan)
    summary, condition_rows = _analysis_report(
        records,
        plan,
        admission=admission,
        candidate=candidate,
        merge=merge,
    )
    output_root.mkdir(parents=True, exist_ok=False)
    summary_path = output_root / SUMMARY_NAME
    csv_path = output_root / CONDITION_CSV_NAME
    _write_json(summary_path, summary)
    _write_condition_csv(csv_path, condition_rows)
    _write_figures(output_root, condition_rows)
    output_files = [
        summary_path,
        csv_path,
        *[output_root / name for name in FIGURE_FILES],
    ]
    manifest_core = {
        "schema_version": "m3-paper-v2-public-primary-analysis-manifest-1.0",
        "status": "complete",
        "analysis_manifest_sha256": summary["manifest_sha256"],
        "result_admission_manifest_sha256": admission["manifest_sha256"],
        "files": [_file_lock(path) for path in output_files],
        "boundary": {
            "provider_calls_made": 0,
            "ledger_rows_mutated": 0,
            "diagnostic_rows_excluded": 0,
            "new_external_effects": 0,
        },
    }
    manifest = {
        **manifest_core,
        "manifest_sha256": sha256_canonical_json(manifest_core),
    }
    _write_json(output_root / MANIFEST_NAME, manifest)
    return manifest


def verify_analysis(
    *,
    admission_path: Path = admission_v1.ADMISSION_PATH,
    output_root: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    admission_v1.validate_admission(_load_json(admission_path))
    manifest = _load_json(output_root / MANIFEST_NAME)
    expected_manifest = sha256_canonical_json(
        {
            key: child
            for key, child in manifest.items()
            if key != "manifest_sha256"
        }
    )
    if manifest.get("manifest_sha256") != expected_manifest:
        raise PublicPrimaryAnalysisError(
            "public primary analysis manifest drift"
        )
    for lock in manifest.get("files", []):
        path = PROJECT_ROOT / str(lock["path"])
        if (
            not path.is_file()
            or path.stat().st_size != lock["bytes"]
            or _sha256_file(path) != lock["sha256"]
        ):
            raise PublicPrimaryAnalysisError(
                f"public primary analysis output drift: {lock['path']}"
            )
    plan = _primary_plan()
    records = _records()
    _validate_matrix(records, plan)
    candidate = admission_v1.verify_candidate()
    merge = merge_v2.verify_primary_merge_review()
    admission = admission_v1.validate_admission(_load_json(admission_path))
    expected_summary, expected_rows = _analysis_report(
        records,
        plan,
        admission=admission,
        candidate=candidate,
        merge=merge,
    )
    if _load_json(output_root / SUMMARY_NAME) != expected_summary:
        raise PublicPrimaryAnalysisError(
            "public primary summary does not reproduce"
        )
    with (output_root / CONDITION_CSV_NAME).open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        observed_rows = list(csv.DictReader(stream))
    expected_csv = [
        {
            key: "" if value is None else str(value)
            for key, value in row.items()
        }
        for row in expected_rows
    ]
    if observed_rows != expected_csv:
        raise PublicPrimaryAnalysisError(
            "public primary condition CSV does not reproduce"
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--analyze", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    admission_path = (
        args.admission
        if args.admission.is_absolute()
        else PROJECT_ROOT / args.admission
    )
    output_root = (
        args.output_root
        if args.output_root.is_absolute()
        else PROJECT_ROOT / args.output_root
    )
    value = (
        analyze(admission_path=admission_path, output_root=output_root)
        if args.analyze
        else verify_analysis(
            admission_path=admission_path,
            output_root=output_root,
        )
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
