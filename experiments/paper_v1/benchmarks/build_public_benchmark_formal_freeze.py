"""Build the public-benchmark formal-freeze manifest for paper-v1.

This artifact defines the full AgentDojo and InjecAgent case universe, the
currently runnable formal candidate conditions, the model slots, and the gates
that must pass before results may enter a Q2-oriented paper table.

It is deliberately non-executing: no model service is started, no benchmark
case is run, no repository is cloned, and no dependency is installed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .agentdojo_adapter import build_agentdojo_index
from .common import rows_sha256, sha256_file
from .injecagent_stage_runner import build_stage_rows


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AGENTDOJO = ROOT / "external" / "benchmarks" / "agentdojo"
DEFAULT_INJECAGENT = ROOT / "external" / "benchmarks" / "injecagent"
DEFAULT_LOCK = ROOT / "external" / "benchmarks" / "benchmark_lock.json"
DEFAULT_BASELINE_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "baseline_registry.json"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
FREEZE_VERSION = "m3-paper-v1-public-benchmark-formal-freeze-1.0"
FREEZE_STEM = "public_benchmark_formal_freeze_v1"

FORMAL_MAIN_CONDITION_IDS = (
    "no_defense",
    "safe_prompt",
    "spotlighting",
    "prompt_sandwich",
    "promptguard",
    "task_shield",
    "ipiguard",
    "progent",
    "camel_or_fides",
    "m3_policy_only",
    "m3_full",
)
AGENTDOJO_OFFICIAL_STRONG_CONDITION_IDS = (
    "agentdojo_tool_filter",
    "agentdojo_transformers_pi_detector",
)
DIAGNOSTIC_ONLY_CONDITION_STATUSES = {"ready_diagnostic_adapter"}
DEFAULT_MODEL_SLOTS = (
    {
        "id": "qwen3:4b-instruct",
        "family": "local_small_open",
        "role": "core_local_small",
        "formal_slot_status": "declared_local",
    },
    {
        "id": "phi4-mini:3.8b",
        "family": "local_small_open",
        "role": "core_local_small",
        "formal_slot_status": "declared_local",
    },
    {
        "id": "llama3.2:3b",
        "family": "local_small_open",
        "role": "core_local_small",
        "formal_slot_status": "declared_local",
    },
    {
        "id": "gemma3:4b",
        "family": "local_small_open",
        "role": "core_local_small",
        "formal_slot_status": "declared_local",
    },
    {
        "id": "vicuna:7b",
        "family": "local_legacy_weak",
        "role": "legacy_weak_baseline",
        "formal_slot_status": "declared_local_legacy",
    },
)
Q2_REQUIRED_MODEL_SLOT_SUMMARY = {
    "local_small_open_minimum": 2,
    "open_source_7b_14b_minimum": 2,
    "frontier_api_vendor_minimum": 2,
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _condition_index(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = registry.get("conditions")
    if not isinstance(rows, list):
        raise ValueError("baseline registry missing conditions list")
    return {str(row.get("id", "")): dict(row) for row in rows if isinstance(row, Mapping)}


def _result_eligible(row: Mapping[str, Any]) -> bool:
    return bool(row.get("result_eligible", row.get("implementation_status") == "ready"))


def _case_id_rows(kind: str, case_ids: list[str]) -> list[dict[str, Any]]:
    return [{"kind": kind, "case_id": case_id} for case_id in case_ids]


def _agentdojo_case_universe(agentdojo_index: Mapping[str, Any]) -> dict[str, Any]:
    utility_ids = sorted(str(row["benchmark_case_id"]) for row in agentdojo_index["utility_rows"])
    security_ids = sorted(str(row["benchmark_case_id"]) for row in agentdojo_index["security_rows"])
    all_ids = [*_case_id_rows("utility", utility_ids), *_case_id_rows("security", security_ids)]
    return {
        "benchmark": "agentdojo",
        "version": agentdojo_index["version"],
        "utility_case_count": len(utility_ids),
        "security_case_count": len(security_ids),
        "total_case_count": len(utility_ids) + len(security_ids),
        "suite_counts": agentdojo_index["suite_counts"],
        "utility_case_ids": utility_ids,
        "security_case_ids": security_ids,
        "case_universe_sha256": rows_sha256(all_ids),
        "utility_sha256": agentdojo_index["utility_sha256"],
        "security_sha256": agentdojo_index["security_sha256"],
        "formal_execution_boundary": (
            "Native AgentDojo full run must preserve official utility and "
            "security checkers while keeping attack goals and checker labels "
            "offline."
        ),
    }


def _injecagent_case_universe(stage_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    case_ids = sorted(str(row["benchmark_case_id"]) for row in stage_rows)
    attack_types: dict[str, int] = {}
    suites: dict[str, int] = {}
    for row in stage_rows:
        suite = str(row.get("suite", ""))
        suites[suite] = suites.get(suite, 0) + 1
        offline = row.get("offline_evaluation", {})
        attack_type = str(offline.get("attack_type", "")) if isinstance(offline, Mapping) else ""
        attack_types[attack_type] = attack_types.get(attack_type, 0) + 1
    return {
        "benchmark": "injecagent",
        "version": "official-release-2024-official-stage-compatible",
        "security_case_count": len(case_ids),
        "utility_case_count": 0,
        "total_case_count": len(case_ids),
        "suite_counts": dict(sorted(suites.items())),
        "attack_type_counts": dict(sorted(attack_types.items())),
        "security_case_ids": case_ids,
        "case_universe_sha256": rows_sha256(_case_id_rows("security", case_ids)),
        "stage_rows_sha256": rows_sha256([dict(row) for row in stage_rows]),
        "formal_execution_boundary": (
            "The current stage runner is official-stage compatible but not "
            "byte-identical InjecAgent prompted/function-calling execution. "
            "Formal use requires either byte-identical execution or a frozen "
            "disclosed-compatibility protocol."
        ),
    }


def _condition_plan(registry: Mapping[str, Any]) -> dict[str, Any]:
    index = _condition_index(registry)
    missing = [condition_id for condition_id in FORMAL_MAIN_CONDITION_IDS if condition_id not in index]
    ready_main = [
        condition_id
        for condition_id in FORMAL_MAIN_CONDITION_IDS
        if condition_id in index
        and index[condition_id].get("implementation_status") == "ready"
        and _result_eligible(index[condition_id])
    ]
    blocked_main = [
        condition_id
        for condition_id in FORMAL_MAIN_CONDITION_IDS
        if condition_id in index and condition_id not in ready_main
    ]
    diagnostic_excluded = [
        condition_id
        for condition_id, row in sorted(index.items())
        if row.get("implementation_status") in DIAGNOSTIC_ONLY_CONDITION_STATUSES
    ]
    agentdojo_official_strong_blocked = [
        condition_id
        for condition_id in AGENTDOJO_OFFICIAL_STRONG_CONDITION_IDS
        if condition_id not in index
        or index[condition_id].get("implementation_status") != "ready"
        or not _result_eligible(index[condition_id])
    ]
    return {
        "formal_main_condition_ids": list(FORMAL_MAIN_CONDITION_IDS),
        "ready_formal_main_condition_ids": ready_main,
        "blocked_or_pending_formal_main_condition_ids": blocked_main,
        "missing_formal_main_condition_ids": missing,
        "diagnostic_condition_ids_excluded_from_formal_matrix": diagnostic_excluded,
        "agentdojo_official_strong_condition_ids": list(AGENTDOJO_OFFICIAL_STRONG_CONDITION_IDS),
        "agentdojo_official_strong_blocked_or_pending_ids": agentdojo_official_strong_blocked,
        "registry_q2_gate": registry.get("q2_gate_minimum_strong_baselines", {}),
    }


def _model_plan(model_slots: tuple[Mapping[str, Any], ...] = DEFAULT_MODEL_SLOTS) -> dict[str, Any]:
    local_small = [row["id"] for row in model_slots if row.get("role") == "core_local_small"]
    modern_7b_14b = [
        row["id"]
        for row in model_slots
        if row.get("role") == "modern_open_7b_14b"
    ]
    api_vendors = [
        row["id"]
        for row in model_slots
        if row.get("role") == "frontier_api_vendor"
    ]
    missing = {
        "open_source_7b_14b": max(
            0,
            Q2_REQUIRED_MODEL_SLOT_SUMMARY["open_source_7b_14b_minimum"]
            - len(modern_7b_14b),
        ),
        "frontier_api_vendor": max(
            0,
            Q2_REQUIRED_MODEL_SLOT_SUMMARY["frontier_api_vendor_minimum"]
            - len(api_vendors),
        ),
    }
    return {
        "declared_model_slots": [dict(row) for row in model_slots],
        "ready_local_execution_model_ids": [str(row["id"]) for row in model_slots],
        "q2_required_model_slot_summary": Q2_REQUIRED_MODEL_SLOT_SUMMARY,
        "core_local_small_model_ids": local_small,
        "modern_open_7b_14b_model_ids": modern_7b_14b,
        "frontier_api_vendor_model_ids": api_vendors,
        "missing_q2_model_slots": missing,
        "q2_model_gate": "not_satisfied" if any(missing.values()) else "satisfied",
        "boundary": (
            "Local 3B/4B and legacy Vicuna slots are declared for reproducible "
            "local execution. Two modern 7B-14B open models and two frontier "
            "API vendor models are still required for Q2-grade evidence."
        ),
    }


def _job_matrix_summary(
    *,
    benchmarks: Mapping[str, Mapping[str, Any]],
    ready_conditions: list[str],
    model_ids: list[str],
    repeats: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for benchmark_id, benchmark in benchmarks.items():
        for model_id in model_ids:
            for condition_id in ready_conditions:
                rows.append(
                    {
                        "benchmark": benchmark_id,
                        "model": model_id,
                        "condition_id": condition_id,
                        "repeats": repeats,
                        "case_count": benchmark["total_case_count"],
                        "case_runs": benchmark["total_case_count"] * repeats,
                    }
                )
    return rows


def _lock_artifacts_match(lock: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = lock.get("artifacts", {})
    result: dict[str, Any] = {}
    if not isinstance(artifacts, Mapping):
        return result
    for name, artifact in artifacts.items():
        if not isinstance(artifact, Mapping):
            continue
        path = ROOT / str(artifact.get("path", ""))
        expected = str(artifact.get("sha256", ""))
        actual = sha256_file(path) if path.exists() else ""
        result[str(name)] = {
            "path": str(path),
            "exists": path.exists(),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "matches": bool(expected) and expected == actual,
        }
    return result


def _check(name: str, passed: bool, *, severity: str = "error", detail: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _audit_freeze(
    *,
    lock: Mapping[str, Any],
    benchmarks: Mapping[str, Mapping[str, Any]],
    condition_plan: Mapping[str, Any],
    model_plan: Mapping[str, Any],
    job_matrix: list[dict[str, Any]],
    lock_artifacts: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ready_conditions = set(condition_plan["ready_formal_main_condition_ids"])
    blocked = set(condition_plan["blocked_or_pending_formal_main_condition_ids"])
    diagnostic = set(condition_plan["diagnostic_condition_ids_excluded_from_formal_matrix"])
    matrix_conditions = {str(row["condition_id"]) for row in job_matrix}
    q2_gate = condition_plan.get("registry_q2_gate", {})
    protocol = lock.get("protocol", {}) if isinstance(lock.get("protocol"), Mapping) else {}
    return [
        _check(
            "benchmark_lock_artifacts_match",
            bool(lock_artifacts) and all(item.get("matches") for item in lock_artifacts.values()),
            detail=lock_artifacts,
        ),
        _check(
            "agentdojo_full_case_universe_declared",
            benchmarks["agentdojo"]["utility_case_count"] == 97
            and benchmarks["agentdojo"]["security_case_count"] == 629
            and benchmarks["agentdojo"]["total_case_count"] == 726,
            detail={
                "utility": benchmarks["agentdojo"]["utility_case_count"],
                "security": benchmarks["agentdojo"]["security_case_count"],
                "total": benchmarks["agentdojo"]["total_case_count"],
            },
        ),
        _check(
            "injecagent_full_case_universe_declared",
            benchmarks["injecagent"]["security_case_count"] == 1054
            and benchmarks["injecagent"]["total_case_count"] == 1054,
            detail={
                "security": benchmarks["injecagent"]["security_case_count"],
                "total": benchmarks["injecagent"]["total_case_count"],
            },
        ),
        _check(
            "no_favorable_case_filtering_declared",
            bool(protocol.get("no_favorable_case_filtering")),
            detail=protocol,
        ),
        _check(
            "ready_job_matrix_uses_only_ready_formal_conditions",
            matrix_conditions <= ready_conditions and bool(matrix_conditions),
            detail={"matrix_conditions": sorted(matrix_conditions), "ready": sorted(ready_conditions)},
        ),
        _check(
            "blocked_strong_baselines_excluded_from_ready_job_matrix",
            not (blocked & matrix_conditions),
            detail={"blocked": sorted(blocked), "matrix_conditions": sorted(matrix_conditions)},
        ),
        _check(
            "diagnostic_conditions_excluded_from_ready_job_matrix",
            not (diagnostic & matrix_conditions),
            detail={
                "diagnostic": sorted(diagnostic),
                "matrix_conditions": sorted(matrix_conditions),
            },
        ),
        _check(
            "q2_gate_not_satisfied_until_strong_baselines_ready",
            q2_gate.get("current_gate_status") == "not_satisfied"
            and bool(condition_plan["blocked_or_pending_formal_main_condition_ids"])
            and bool(condition_plan["agentdojo_official_strong_blocked_or_pending_ids"]),
            severity="warning",
            detail={
                "q2_gate": q2_gate.get("current_gate_status"),
                "blocked_main": condition_plan["blocked_or_pending_formal_main_condition_ids"],
                "blocked_agentdojo_official": condition_plan[
                    "agentdojo_official_strong_blocked_or_pending_ids"
                ],
            },
        ),
        _check(
            "q2_model_gate_not_satisfied_until_7b14b_and_api_slots_ready",
            model_plan["q2_model_gate"] == "not_satisfied",
            severity="warning",
            detail=model_plan["missing_q2_model_slots"],
        ),
    ]


def _write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    lines = [
        f"# Public benchmark formal freeze ({manifest['freeze_version']})",
        "",
        f"Generated: {manifest['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Formal freeze gate: `{manifest['formal_freeze_gate']}`",
        f"- Q2 public-benchmark gate: `{manifest['q2_public_benchmark_gate']}`",
        f"- Ready local matrix case-runs: {manifest['ready_local_job_matrix_case_runs']}",
        f"- Result eligible for formal tables: `{manifest['result_eligible_for_formal_tables']}`",
        "",
        "## Benchmark universe",
        "",
        "| Benchmark | Utility | Security | Total | Case universe hash |",
        "|---|---:|---:|---:|---|",
    ]
    for benchmark in manifest["benchmarks"].values():
        lines.append(
            f"| `{benchmark['benchmark']}` | {benchmark.get('utility_case_count', 0)} | "
            f"{benchmark.get('security_case_count', 0)} | {benchmark['total_case_count']} | "
            f"`{benchmark['case_universe_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Conditions",
            "",
            "- Ready formal main conditions: "
            + ", ".join(f"`{item}`" for item in manifest["condition_plan"]["ready_formal_main_condition_ids"]),
            "- Blocked/pending formal main conditions: "
            + ", ".join(
                f"`{item}`"
                for item in manifest["condition_plan"][
                    "blocked_or_pending_formal_main_condition_ids"
                ]
            ),
            "- Diagnostic conditions excluded: "
            + ", ".join(
                f"`{item}`"
                for item in manifest["condition_plan"][
                    "diagnostic_condition_ids_excluded_from_formal_matrix"
                ]
            ),
            "",
            "## Model gate",
            "",
            f"- Q2 model gate: `{manifest['model_plan']['q2_model_gate']}`",
            f"- Missing Q2 model slots: `{json.dumps(manifest['model_plan']['missing_q2_model_slots'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Severity | Detail |",
            "|---|---|---|---|",
        ]
    )
    for check in manifest["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | {detail.replace('|', '\\|')} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            manifest["boundary"],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_public_benchmark_formal_freeze(
    *,
    agentdojo_checkout: Path = DEFAULT_AGENTDOJO,
    injecagent_checkout: Path = DEFAULT_INJECAGENT,
    benchmark_lock_path: Path = DEFAULT_LOCK,
    baseline_registry_path: Path = DEFAULT_BASELINE_REGISTRY,
    output_dir: Path = DEFAULT_OUTPUT,
    repeats: int = 1,
    model_registry_path: Path | None = None,
    freeze_version: str = FREEZE_VERSION,
    freeze_stem: str = FREEZE_STEM,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    agentdojo_checkout = agentdojo_checkout.resolve()
    injecagent_checkout = injecagent_checkout.resolve()
    benchmark_lock_path = benchmark_lock_path.resolve()
    baseline_registry_path = baseline_registry_path.resolve()
    output_dir = output_dir.resolve()
    lock = _read_json(benchmark_lock_path)
    baseline_registry = _read_json(baseline_registry_path)
    agentdojo_index = build_agentdojo_index(agentdojo_checkout)
    injecagent_stage_rows = build_stage_rows(injecagent_checkout)
    benchmarks = {
        "agentdojo": _agentdojo_case_universe(agentdojo_index),
        "injecagent": _injecagent_case_universe(injecagent_stage_rows),
    }
    condition_plan = _condition_plan(baseline_registry)
    model_registry: dict[str, Any] = {}
    model_slots: tuple[Mapping[str, Any], ...] = DEFAULT_MODEL_SLOTS
    if model_registry_path is not None:
        model_registry_path = model_registry_path.resolve()
        model_registry = _read_json(model_registry_path)
        raw_slots = model_registry.get("models")
        if not isinstance(raw_slots, list) or not raw_slots:
            raise ValueError("model registry missing non-empty models list")
        model_slots = tuple(
            dict(row) for row in raw_slots if isinstance(row, Mapping)
        )
    model_plan = _model_plan(model_slots)
    job_matrix = _job_matrix_summary(
        benchmarks=benchmarks,
        ready_conditions=condition_plan["ready_formal_main_condition_ids"],
        model_ids=model_plan["ready_local_execution_model_ids"],
        repeats=repeats,
    )
    lock_artifacts = _lock_artifacts_match(lock)
    checks = _audit_freeze(
        lock=lock,
        benchmarks=benchmarks,
        condition_plan=condition_plan,
        model_plan=model_plan,
        job_matrix=job_matrix,
        lock_artifacts=lock_artifacts,
    )
    error_failures = [
        check
        for check in checks
        if check["status"] != "pass" and check.get("severity") == "error"
    ]
    case_runs = sum(int(row["case_runs"]) for row in job_matrix)
    manifest = {
        "schema_version": "paper-public-benchmark-formal-freeze-1.0",
        "freeze_version": freeze_version,
        "status": "completed" if not error_failures else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_lock_path": str(benchmark_lock_path),
        "benchmark_lock_sha256": sha256_file(benchmark_lock_path),
        "baseline_registry_path": str(baseline_registry_path),
        "baseline_registry_sha256": sha256_file(baseline_registry_path),
        "model_registry_path": str(model_registry_path) if model_registry_path else "",
        "model_registry_sha256": sha256_file(model_registry_path)
        if model_registry_path
        else "",
        "agentdojo_checkout": str(agentdojo_checkout),
        "injecagent_checkout": str(injecagent_checkout),
        "benchmarks": benchmarks,
        "condition_plan": condition_plan,
        "model_plan": model_plan,
        "repeats": repeats,
        "ready_local_job_matrix_summary": job_matrix,
        "ready_local_job_matrix_sha256": rows_sha256(job_matrix),
        "ready_local_job_matrix_case_runs": case_runs,
        "lock_artifact_probe": lock_artifacts,
        "formal_freeze_gate": (
            "local_ready_matrix_declared_q2_gate_not_satisfied"
            if not error_failures
            else "failed"
        ),
        "q2_public_benchmark_gate": "not_satisfied",
        "result_eligible_for_formal_tables": False,
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "total_checks": len(checks),
        "passed_checks": sum(1 for check in checks if check["status"] == "pass"),
        "error_failures": error_failures,
        "boundary": (
            "This file freezes the public-benchmark case universe and ready "
            "local execution matrix. It is not a result manifest. Q2-grade "
            "paper claims still require the declared formal jobs to be run, "
            "strong baselines to become source-backed/formal-ready, modern "
            "7B-14B and API model slots to be configured, and complete logs "
            "plus statistical outputs to be generated from frozen manifests."
        ),
    }
    json_path = output_dir / f"{freeze_stem}.json"
    md_path = output_dir / f"{freeze_stem}.md"
    _write_json(json_path, manifest)
    _write_markdown(md_path, manifest)
    manifest["json_path"] = str(json_path)
    manifest["markdown_path"] = str(md_path)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agentdojo-checkout", type=Path, default=DEFAULT_AGENTDOJO)
    parser.add_argument("--injecagent-checkout", type=Path, default=DEFAULT_INJECAGENT)
    parser.add_argument("--benchmark-lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--baseline-registry", type=Path, default=DEFAULT_BASELINE_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--model-registry", type=Path)
    parser.add_argument("--freeze-version", default=FREEZE_VERSION)
    parser.add_argument("--freeze-stem", default=FREEZE_STEM)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_public_benchmark_formal_freeze(
        agentdojo_checkout=args.agentdojo_checkout,
        injecagent_checkout=args.injecagent_checkout,
        benchmark_lock_path=args.benchmark_lock,
        baseline_registry_path=args.baseline_registry,
        output_dir=args.output_dir,
        repeats=args.repeats,
        model_registry_path=args.model_registry,
        freeze_version=args.freeze_version,
        freeze_stem=args.freeze_stem,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
