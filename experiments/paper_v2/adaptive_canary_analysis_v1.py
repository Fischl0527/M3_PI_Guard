"""八任务自适应 DeepSeek 金丝雀实验的准入分析模块。

计算并汇总自适应金丝雀测试的防御拦截率、查询预算消耗、有效攻击载荷比率，
生成格式规范的准入分析统计字典与报告。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import experiments.paper_v2.adaptive_cost_canary_controller_v1 as canary_v1
import experiments.paper_v2.adaptive_cost_canary_controller_v2 as canary_v2
import experiments.paper_v2.adaptive_cost_canary_plan_v1 as plan_v1
import experiments.paper_v2.adaptive_recovery_technical_review_v1 as typed_review
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    cross_bind_query_and_call_ledgers,
    validate_query_events,
)
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.public_execution_store_v1 import (
    validate_public_budget_events,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1"
)
SCHEMA_VERSION = "m3-paper-v2-adaptive-canary-analysis-1.0"
ANALYZED_AT = "2026-07-30T03:05:00+08:00"


class AdaptiveCanaryAnalysisError(ValueError):
    """当准入的自适应分析输入发生漂移时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdaptiveCanaryAnalysisError(f"{path}: expected an object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            raise AdaptiveCanaryAnalysisError(
                f"{path}:{number}: blank row"
            )
        value = json.loads(line)
        if not isinstance(value, dict):
            raise AdaptiveCanaryAnalysisError(
                f"{path}:{number}: expected an object"
            )
        rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _wilson(successes: int, total: int) -> dict[str, float]:
    if total <= 0 or successes < 0 or successes > total:
        raise AdaptiveCanaryAnalysisError("invalid Wilson inputs")
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            p * (1 - p) / total + z * z / (4 * total * total)
        )
        / denominator
    )
    return {
        "value": round(p, 10),
        "ci_low": round(max(0.0, center - radius), 10),
        "ci_high": round(min(1.0, center + radius), 10),
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise AdaptiveCanaryAnalysisError("analysis CSV cannot be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _build_figure(
    *,
    output_root: Path,
    estimate: Mapping[str, float],
) -> list[dict[str, Any]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(7.2, 4.6))
    value = 100.0 * float(estimate["value"])
    lower = 100.0 * float(estimate["ci_low"])
    upper = 100.0 * float(estimate["ci_high"])
    axis.errorbar(
        [50],
        [value],
        yerr=[[value - lower], [upper - value]],
        fmt="o-",
        linewidth=2.2,
        markersize=7,
        capsize=5,
        color="#b42318",
    )
    axis.set_xlim(40, 60)
    axis.set_ylim(0, 100)
    axis.set_xticks([50])
    axis.set_xlabel("Adaptive query budget per task")
    axis.set_ylabel("Unsafe-effect success rate (%)")
    axis.set_title("Adaptive canary success at 50 queries")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    artifacts: list[dict[str, Any]] = []
    for suffix in ("png", "svg"):
        path = output_root / f"adaptive_canary_asr.{suffix}"
        figure.savefig(path, dpi=180 if suffix == "png" else None)
        artifacts.append(
            {
                "path": _display_path(path),
                "sha256": _sha256_file(path),
            }
        )
    plt.close(figure)
    return artifacts


def analyze(
    *,
    admission_path: Path,
    output_root: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    from experiments.paper_v2 import adaptive_canary_result_admission_v1

    admission = adaptive_canary_result_admission_v1.validate_admission(
        _load_json(admission_path)
    )
    technical = typed_review.verify_review()
    permit = canary_v2.authorize_canary(
        admission_path=canary_v2.ADMISSION_PATH
    )
    role_policy = canary_v1.adaptive_role_policy()
    query_events = _load_jsonl(permit.query_ledger_path)
    budget_events = _load_jsonl(permit.budget_ledger_path)
    query_status = validate_query_events(
        query_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    budget_status = validate_public_budget_events(
        budget_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    cross_bind_query_and_call_ledgers(
        query_events=query_events,
        budget_events=budget_events,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    if (
        query_status["tail_sha256"]
        != technical["query_ledger_tail_sha256"]
        or budget_status["tail_sha256"]
        != technical["budget_ledger_tail_sha256"]
        or query_status["terminal_query_count"]
        != technical["terminal_query_count"]
        or query_status["open_query_work_keys"]
    ):
        raise AdaptiveCanaryAnalysisError(
            "adaptive admitted ledgers differ from technical review"
        )
    terminal_by_case: dict[str, list[Mapping[str, Any]]] = {}
    for event in query_events:
        if event["event_type"] == "terminal":
            terminal_by_case.setdefault(
                str(event["case_id"]),
                [],
            ).append(event)
    task_metadata = {
        str(task["case_id"]): task
        for task in permit.candidate["scope"]["tasks"]
    }
    task_rows: list[dict[str, Any]] = []
    first_successes: list[int] = []
    decision_counts: Counter[str] = Counter()
    for task in permit.tasks:
        case_id = str(task["case_id"])
        checkpoint_path = permit.checkpoint_root / f"{case_id}.json"
        checkpoint = _load_json(checkpoint_path)
        queries = checkpoint.get("queries")
        if not isinstance(queries, list) or not queries:
            raise AdaptiveCanaryAnalysisError(
                "adaptive admitted checkpoint lacks queries"
            )
        first = checkpoint.get("first_success_query")
        if first is not None:
            if (
                isinstance(first, bool)
                or not isinstance(first, int)
                or not 1 <= first <= len(queries)
            ):
                raise AdaptiveCanaryAnalysisError(
                    "adaptive first-success query is invalid"
                )
            first_successes.append(first)
        events = terminal_by_case.get(case_id, [])
        diagnostics = sum(
            event["result_tier"] == "diagnostic" for event in events
        )
        for event in events:
            record = event["record"]
            decision_counts[str(record["initial_guard_decision"])] += 1
        metadata = task_metadata[case_id]
        task_rows.append(
            {
                "case_id": case_id,
                "attack_family": metadata["attack_family"],
                "language": metadata["language"],
                "queries_executed": len(queries),
                "first_unsafe_effect_query": (
                    "" if first is None else first
                ),
                "unsafe_effect_within_50": first is not None,
                "diagnostic_queries": diagnostics,
            }
        )
    estimate = _wilson(len(first_successes), len(task_rows))
    output_root.mkdir(parents=True, exist_ok=True)
    task_path = output_root / "task_results.csv"
    summary_path = output_root / "summary.json"
    _write_csv(task_path, task_rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "analyzed_at": ANALYZED_AT,
        "model_id": plan_v1.MODEL_ID,
        "condition_id": plan_v1.CONDITION_ID,
        "authorization_regime": plan_v1.AUTHORIZATION_REGIME,
        "task_count": len(task_rows),
        "query_budget_per_task": plan_v1.QUERY_BUDGET,
        "terminal_query_count": query_status["terminal_query_count"],
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "diagnostic_query_count": query_status[
            "diagnostic_query_count"
        ],
        "cumulative_cost_cny": budget_status[
            "role_cumulative_cost_cny"
        ],
        "unsafe_effect_successes": len(first_successes),
        "unsafe_effect_rate_at_50": estimate,
        "first_unsafe_effect_queries": first_successes,
        "decision_distribution": dict(sorted(decision_counts.items())),
        "interpretation_boundary": {
            "exploratory_cost_canary": True,
            "full_40_task_adaptive_panel_completed": False,
            "second_model_adaptive_panel_completed": False,
            "diagnostic_queries_retained_in_itt": True,
            "sota_claim_authorized": False,
        },
    }
    _write_json(summary_path, summary)
    figures = _build_figure(output_root=output_root, estimate=estimate)
    core = {
        "schema_version": "m3-paper-v2-adaptive-analysis-manifest-1.0",
        "artifact_role": "admitted_adaptive_canary_analysis",
        "analyzed_at": ANALYZED_AT,
        "status": "completed_exploratory_adaptive_canary_analysis",
        "admission_manifest_sha256": admission["manifest_sha256"],
        "technical_review_manifest_sha256": technical[
            "manifest_sha256"
        ],
        "summary": {
            "path": _display_path(summary_path),
            "sha256": _sha256_file(summary_path),
        },
        "task_results": {
            "path": _display_path(task_path),
            "sha256": _sha256_file(task_path),
        },
        "figures": figures,
        "source_tails": {
            "query_ledger_tail_sha256": query_status["tail_sha256"],
            "budget_ledger_tail_sha256": budget_status["tail_sha256"],
        },
        "scientific_claim_boundary": summary["interpretation_boundary"],
    }
    manifest = {**core, "manifest_sha256": sha256_canonical_json(core)}
    _write_json(output_root / "analysis_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyze", action="store_true", required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    value = analyze(
        admission_path=args.admission,
        output_root=args.output,
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
