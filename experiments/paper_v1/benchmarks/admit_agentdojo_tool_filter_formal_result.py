"""Admit a completed AgentDojo tool_filter formal run into the baseline registry.

This is an evidence bridge, not a runner. It never starts Ollama, never retries
cases, and never turns a partial/running root into a formal result.  Its only
state-changing action is updating ``baseline_registry.json`` after three pieces
of evidence already agree:

* the run manifest is ``completed_formal`` with exact 726-case coverage;
* the read-only monitor says the same root is formally admitted;
* the analyzer produced ``completed_formal_analysis`` for that exact manifest.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .analyze_agentdojo_official_tool_filter_formal import analyze
from .common import portable_path, portable_value, sha256_file
from .monitor_agentdojo_official_formal_run import build_monitor_snapshot


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "baseline_registry.json"
DEFAULT_RUN_DIR = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_tool_filter_official_formal_v1"
)
DEFAULT_MONITOR_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1" / "monitors" / "tool_filter_formal_v1"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
ADMISSION_STEM = "agentdojo_tool_filter_formal_admission_v1"
ADMISSION_VERSION = "m3-paper-v1-agentdojo-tool-filter-formal-admission-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _relative(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _condition_index(registry: Mapping[str, Any]) -> dict[str, int]:
    rows = registry.get("conditions", [])
    if not isinstance(rows, list):
        raise ValueError("baseline registry missing conditions list")
    result: dict[str, int] = {}
    for index, row in enumerate(rows):
        if isinstance(row, Mapping):
            result[str(row.get("id", ""))] = index
    return result


def _validate_evidence(
    *,
    run_dir: Path,
    monitor: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    run_manifest_path = run_dir / "run_manifest.json"
    outcomes_path = run_dir / "outcomes.jsonl"
    progress_path = run_dir / "progress.jsonl"
    if not run_manifest_path.exists():
        return ["run_manifest_missing"]
    if not outcomes_path.exists():
        blockers.append("outcomes_jsonl_missing")
    if not progress_path.exists():
        blockers.append("progress_jsonl_missing")
    run = _read_json(run_manifest_path)
    summary = run.get("summary", {})
    if run.get("status") != "completed_formal":
        blockers.append("run_not_completed_formal")
    if run.get("result_eligible_for_formal_tables") is not True:
        blockers.append("run_not_result_eligible")
    if summary.get("expected_cases") != 726:
        blockers.append("run_expected_cases_not_726")
    if summary.get("completed_cases") != 726:
        blockers.append("run_completed_cases_not_726")
    if summary.get("failed_cases") != 0:
        blockers.append("run_failed_cases_present")
    if run.get("exact_frozen_coverage") is not True:
        blockers.append("run_exact_frozen_coverage_false")
    if monitor.get("health_status") != "completed_formal_admitted":
        blockers.append("monitor_not_completed_formal_admitted")
    if monitor.get("formal_result_admitted_now") is not True:
        blockers.append("monitor_not_formal_result_admitted")
    if str(Path(str(monitor.get("run_manifest_path", ""))).resolve()) != str(
        run_manifest_path.resolve()
    ):
        blockers.append("monitor_points_to_different_run_manifest")
    counts = monitor.get("counts", {})
    if counts.get("completed_cases") != 726 or counts.get("failed_cases") != 0:
        blockers.append("monitor_counts_not_exact_726_zero_failed")
    if analysis.get("status") != "completed_formal_analysis":
        blockers.append("analysis_not_completed_formal")
    if analysis.get("result_eligible_for_formal_tables") is not True:
        blockers.append("analysis_not_result_eligible")
    if analysis.get("run_manifest_sha256") != sha256_file(run_manifest_path):
        blockers.append("analysis_run_manifest_hash_mismatch")
    if outcomes_path.exists() and analysis.get("outcomes_sha256") != sha256_file(outcomes_path):
        blockers.append("analysis_outcomes_hash_mismatch")
    return blockers


def _admitted_registry(
    *,
    registry: Mapping[str, Any],
    run_dir: Path,
    analysis_manifest: Mapping[str, Any],
    monitor_snapshot_path: Path,
) -> dict[str, Any]:
    updated = deepcopy(dict(registry))
    rows = updated.get("conditions", [])
    if not isinstance(rows, list):
        raise ValueError("baseline registry missing conditions list")
    index = _condition_index(updated)
    if "agentdojo_tool_filter" not in index:
        raise ValueError("agentdojo_tool_filter missing from baseline registry")
    row = dict(rows[index["agentdojo_tool_filter"]])
    run_manifest_path = run_dir / "run_manifest.json"
    outcomes_path = run_dir / "outcomes.jsonl"
    progress_path = run_dir / "progress.jsonl"
    analysis_manifest_path = Path(str(analysis_manifest["manifest_path"]))
    row.update(
        {
            "implementation_status": "ready",
            "result_eligible": True,
            "current_blockers": [],
            "current_runner_status": "completed_formal_analyzed",
            "formal_manifest": _relative(analysis_manifest_path),
            "formal_analysis_manifest": _relative(analysis_manifest_path),
            "complete_logs": [
                _relative(run_manifest_path),
                _relative(outcomes_path),
                _relative(progress_path),
                _relative(monitor_snapshot_path),
            ],
            "formal_admission_evidence": {
                "admission_version": ADMISSION_VERSION,
                "run_manifest_sha256": sha256_file(run_manifest_path),
                "outcomes_sha256": sha256_file(outcomes_path),
                "progress_sha256": sha256_file(progress_path),
                "analysis_manifest_sha256": sha256_file(analysis_manifest_path),
                "monitor_snapshot_sha256": sha256_file(monitor_snapshot_path),
            },
            "formal_exclusion_rule": (
                "Admitted only for the exact declared formal_manifest and complete_logs; "
                "any rerun, configuration drift, failed case, missing case or non-identical "
                "adapter must be admitted under a new manifest."
            ),
        }
    )
    rows[index["agentdojo_tool_filter"]] = row
    summary = updated.setdefault("q2_gate_minimum_strong_baselines", {})
    if isinstance(summary, dict):
        ready = set(summary.get("formal_ready_strong_baselines", []))
        ready.add("agentdojo_tool_filter")
        summary["formal_ready_strong_baselines"] = sorted(ready)
        summary["formal_ready_count"] = len(ready)
        minimum = int(summary.get("minimum_exact_or_disclosed_exclusion_count", 5))
        summary["current_gate_status"] = "satisfied" if len(ready) >= minimum else "not_satisfied"
    return updated


def admit(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    run_dir: Path = DEFAULT_RUN_DIR,
    monitor_output_dir: Path = DEFAULT_MONITOR_OUTPUT,
    output_dir: Path = DEFAULT_OUTPUT,
    write_registry: bool = False,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    registry_path = registry_path.resolve()
    monitor_output_dir = monitor_output_dir.resolve()
    output_dir = output_dir.resolve()
    monitor = build_monitor_snapshot(run_dir=run_dir, output_dir=monitor_output_dir)
    analysis_manifest: dict[str, Any] = {}
    actions = ["monitor_refreshed"]
    if monitor.get("health_status") == "completed_formal_admitted":
        analysis_manifest = analyze(
            run_dir=run_dir,
            output_dir=(run_dir / "analysis").resolve(),
            allow_diagnostic=False,
        )
        actions.append("formal_analysis_refreshed")
    blockers = _validate_evidence(
        run_dir=run_dir,
        monitor=monitor,
        analysis=analysis_manifest,
    )
    registry_written = False
    registry_output_path = registry_path
    if not blockers:
        registry = _read_json(registry_path)
        admitted = _admitted_registry(
            registry=registry,
            run_dir=run_dir,
            analysis_manifest=analysis_manifest,
            monitor_snapshot_path=Path(str(monitor["json_path"])),
        )
        registry_output_path = registry_path if write_registry else output_dir / "baseline_registry_tool_filter_admitted_candidate.json"
        _write_json(registry_output_path, admitted)
        registry_written = bool(write_registry)
        actions.append("registry_updated" if write_registry else "registry_candidate_written")
    status = "admitted_registry_updated" if registry_written else "admission_pending"
    if blockers:
        status = "blocked_not_formally_admitted"
    result = {
        "schema_version": "paper-agentdojo-tool-filter-formal-admission-1.0",
        "admission_version": ADMISSION_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "result_eligible_for_formal_tables": registry_written,
        "write_registry": write_registry,
        "registry_path": _relative(registry_path),
        "registry_output_path": _relative(registry_output_path),
        "run_dir": _relative(run_dir),
        "monitor_path": portable_value(monitor.get("json_path", ""), root=ROOT),
        "monitor_health_status": monitor.get("health_status", ""),
        "monitor_counts": monitor.get("counts", {}),
        "analysis_manifest_path": portable_value(
            analysis_manifest.get("manifest_path", ""), root=ROOT
        ),
        "actions": actions,
        "blockers": blockers,
        "boundary": (
            "Admission bridge only. Running or partial roots remain blocked. "
            "Registry updates require completed_formal run evidence, monitor agreement, "
            "formal analysis and explicit --write-registry."
        ),
    }
    _write_json(output_dir / f"{ADMISSION_STEM}.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--monitor-output-dir", type=Path, default=DEFAULT_MONITOR_OUTPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-registry", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = admit(
        registry_path=args.registry,
        run_dir=args.run_dir,
        monitor_output_dir=args.monitor_output_dir,
        output_dir=args.output_dir,
        write_registry=args.write_registry,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"admitted_registry_updated", "admission_pending"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
