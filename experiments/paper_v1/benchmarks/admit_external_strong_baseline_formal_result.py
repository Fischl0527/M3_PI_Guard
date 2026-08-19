"""Admit a completed external strong-baseline run into both registries.

This is a fail-closed evidence bridge.  It never starts a model, runs an
analyzer, retries a case, or edits evidence.  Registry writes require an exact
726-case, zero-failure formal run and a hash-linked formal analysis.
"""

from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASELINE_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "baseline_registry.json"
DEFAULT_EXTERNAL_REGISTRY = (
    ROOT / "protocols" / "paper_upgrade_v1" / "external_strong_baselines_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1" / "admissions"
ADMISSION_VERSION = "m3-paper-v1-external-strong-baseline-admission-1.0"
EXPECTED_CASES = 726

CONDITIONS = {
    "task_shield": {
        "run_dir": ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v14",
        "selected_external_entry": "task_shield_acl2025",
    },
    "ipiguard": {
        "run_dir": ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "ipiguard_source_backed_formal_v1",
        "selected_external_entry": "ipiguard_github_emnlp2025",
    },
    "progent": {
        "run_dir": ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "progent_source_backed_formal_v1",
        "selected_external_entry": "progent_arxiv2025",
    },
    "camel_or_fides": {
        "run_dir": ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "camel_source_backed_formal_v3",
        "selected_external_entry": "camel_google_research",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _relative(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _resolve_repo_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return (path if path.is_absolute() else ROOT / path).resolve()


def _find_condition(registry: Mapping[str, Any], condition_id: str) -> tuple[int, dict[str, Any]]:
    rows = registry.get("conditions", [])
    if not isinstance(rows, list):
        raise ValueError("baseline registry missing conditions list")
    for index, row in enumerate(rows):
        if isinstance(row, Mapping) and row.get("id") == condition_id:
            return index, dict(row)
    raise ValueError(f"condition missing from baseline registry: {condition_id}")


def _artifact_hash_matches(manifest: Mapping[str, Any], path_key: str, hash_key: str) -> bool:
    path = _resolve_repo_path(manifest.get(path_key))
    expected = str(manifest.get(hash_key, ""))
    return bool(path and path.is_file() and expected and sha256_file(path) == expected)


def _validate_evidence(
    *,
    condition: Mapping[str, Any],
    run_dir: Path,
    analysis_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    run_manifest_path = run_dir / "run_manifest.json"
    outcomes_path = run_dir / "outcomes.jsonl"
    progress_path = run_dir / "progress.jsonl"
    required_paths = {
        "run_manifest_missing": run_manifest_path,
        "outcomes_missing": outcomes_path,
        "progress_missing": progress_path,
        "analysis_manifest_missing": analysis_path,
    }
    for blocker, path in required_paths.items():
        if not path.is_file():
            blockers.append(blocker)
    if blockers:
        return blockers, {
            "required_paths": {
                key: _relative(path) for key, path in required_paths.items()
            }
        }

    run = _read_json(run_manifest_path)
    analysis = _read_json(analysis_path)
    rows = _read_jsonl(outcomes_path)
    summary = run.get("summary", {})
    if run.get("status") != "completed_formal":
        blockers.append("run_not_completed_formal")
    if run.get("result_eligible_for_formal_tables") is not True:
        blockers.append("run_not_result_eligible")
    if run.get("exact_frozen_coverage") is not True:
        blockers.append("run_exact_frozen_coverage_false")
    if summary.get("expected_cases") != EXPECTED_CASES:
        blockers.append("run_expected_cases_not_726")
    if summary.get("completed_cases") != EXPECTED_CASES:
        blockers.append("run_completed_cases_not_726")
    if summary.get("failed_cases") != 0:
        blockers.append("run_failed_cases_present")
    if len(rows) != EXPECTED_CASES:
        blockers.append("outcome_rows_not_726")
    case_ids = [str(row.get("benchmark_case_id", "")) for row in rows]
    if not all(case_ids) or len(set(case_ids)) != len(case_ids):
        blockers.append("outcome_case_ids_missing_or_duplicate")
    if any(row.get("status") != "completed" for row in rows):
        blockers.append("non_completed_outcomes_present")
    if any(row.get("result_eligible_for_formal_tables") is not True for row in rows):
        blockers.append("non_formal_outcomes_present")

    freeze_path = _resolve_repo_path(condition.get("formal_freeze"))
    if freeze_path is None or not freeze_path.is_file():
        blockers.append("condition_formal_freeze_missing")
    elif run.get("freeze_sha256") != sha256_file(freeze_path):
        blockers.append("run_freeze_hash_mismatch")

    if analysis.get("status") != "completed_formal_analysis":
        blockers.append("analysis_not_completed_formal")
    if analysis.get("result_eligible_for_formal_tables") is not True:
        blockers.append("analysis_not_result_eligible")
    if analysis.get("run_manifest_sha256") != sha256_file(run_manifest_path):
        blockers.append("analysis_run_manifest_hash_mismatch")
    if analysis.get("outcomes_sha256") != sha256_file(outcomes_path):
        blockers.append("analysis_outcomes_hash_mismatch")
    analysis_case_count = analysis.get("case_count", analysis.get("summary", {}).get("case_count"))
    if analysis_case_count != EXPECTED_CASES:
        blockers.append("analysis_case_count_not_726")
    for path_key, hash_key in (
        ("metrics_path", "metrics_sha256"),
        ("summary_path", "summary_sha256"),
        ("report_path", "report_sha256"),
    ):
        if not _artifact_hash_matches(analysis, path_key, hash_key):
            blockers.append(f"analysis_{path_key}_hash_mismatch")
    if not analysis.get("figures"):
        blockers.append("analysis_figures_missing")

    evidence = {
        "run_manifest_path": _relative(run_manifest_path),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "outcomes_path": _relative(outcomes_path),
        "outcomes_sha256": sha256_file(outcomes_path),
        "progress_path": _relative(progress_path),
        "progress_sha256": sha256_file(progress_path),
        "analysis_manifest_path": _relative(analysis_path),
        "analysis_manifest_sha256": sha256_file(analysis_path),
        "formal_freeze_path": _relative(freeze_path) if freeze_path else "",
        "formal_freeze_sha256": sha256_file(freeze_path) if freeze_path and freeze_path.is_file() else "",
        "case_count": len(rows),
    }
    return blockers, evidence


def _admitted_registries(
    *,
    baseline_registry: Mapping[str, Any],
    external_registry: Mapping[str, Any],
    condition_id: str,
    selected_external_entry: str,
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline = deepcopy(dict(baseline_registry))
    external = deepcopy(dict(external_registry))
    index, condition = _find_condition(baseline, condition_id)
    analysis_path = Path(str(evidence["analysis_manifest_path"]))
    logs = [
        _relative(Path(str(evidence["run_manifest_path"]))),
        _relative(Path(str(evidence["outcomes_path"]))),
        _relative(Path(str(evidence["progress_path"]))),
    ]
    condition.update(
        {
            "implementation_status": "ready",
            "result_eligible": True,
            "current_blockers": [],
            "current_runner_status": "completed_formal_analyzed",
            "formal_manifest": _relative(analysis_path),
            "formal_analysis_manifest": _relative(analysis_path),
            "complete_logs": logs,
            "formal_admission_evidence": {
                "admission_version": ADMISSION_VERSION,
                **dict(evidence),
            },
            "formal_exclusion_rule": (
                "Admitted only for the hash-pinned formal run and analysis listed in "
                "formal_admission_evidence; configuration drift requires a new admission."
            ),
        }
    )
    baseline["conditions"][index] = condition
    gate = baseline.setdefault("q2_gate_minimum_strong_baselines", {})
    if isinstance(gate, dict):
        ready = set(gate.get("formal_ready_strong_baselines", []))
        ready.add(condition_id)
        gate["formal_ready_strong_baselines"] = sorted(ready)
        gate["formal_ready_count"] = len(ready)
        minimum = int(gate.get("minimum_exact_or_disclosed_exclusion_count", 5))
        gate["current_gate_status"] = "satisfied" if len(ready) >= minimum else "not_satisfied"

    rows = external.get("entries", [])
    if not isinstance(rows, list):
        raise ValueError("external registry missing entries list")
    matched = False
    for row_index, raw in enumerate(rows):
        if not isinstance(raw, Mapping) or raw.get("registry_key") != condition_id:
            continue
        row = dict(raw)
        is_selected = row.get("id") == selected_external_entry
        if is_selected:
            matched = True
            row.update(
                {
                    "current_status": "ready",
                    "current_blockers": [],
                    "result_eligible_for_formal_tables": True,
                    "formal_manifest": _relative(analysis_path),
                    "complete_logs": logs,
                    "formal_admission_evidence": {
                        "admission_version": ADMISSION_VERSION,
                        **dict(evidence),
                    },
                }
            )
        elif condition_id == "camel_or_fides":
            row["result_eligible_for_formal_tables"] = False
        rows[row_index] = row
    if not matched:
        raise ValueError(f"selected external entry missing: {selected_external_entry}")
    return baseline, external


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def admit(
    *,
    condition_id: str,
    run_dir: Path | None = None,
    analysis_path: Path | None = None,
    baseline_registry_path: Path = DEFAULT_BASELINE_REGISTRY,
    external_registry_path: Path = DEFAULT_EXTERNAL_REGISTRY,
    output_dir: Path = DEFAULT_OUTPUT,
    write_registries: bool = False,
) -> dict[str, Any]:
    if condition_id not in CONDITIONS:
        raise ValueError("unsupported external strong baseline: " + condition_id)
    config = CONDITIONS[condition_id]
    run_dir = (run_dir or Path(config["run_dir"])).resolve()
    analysis_path = (analysis_path or run_dir / "analysis" / "analysis_manifest.json").resolve()
    baseline_registry_path = baseline_registry_path.resolve()
    external_registry_path = external_registry_path.resolve()
    baseline = _read_json(baseline_registry_path)
    external = _read_json(external_registry_path)
    _, condition = _find_condition(baseline, condition_id)
    blockers, evidence = _validate_evidence(
        condition=condition,
        run_dir=run_dir,
        analysis_path=analysis_path,
    )
    registries_written = False
    if not blockers and write_registries:
        updated_baseline, updated_external = _admitted_registries(
            baseline_registry=baseline,
            external_registry=external,
            condition_id=condition_id,
            selected_external_entry=str(config["selected_external_entry"]),
            evidence=evidence,
        )
        _atomic_write_json(baseline_registry_path, updated_baseline)
        _atomic_write_json(external_registry_path, updated_external)
        registries_written = True
    status = (
        "admitted_formal_result"
        if registries_written
        else "ready_for_registry_admission"
        if not blockers
        else "blocked_not_formally_admitted"
    )
    result = {
        "schema_version": "paper-external-strong-baseline-admission-1.0",
        "admission_version": ADMISSION_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "condition_id": condition_id,
        "selected_external_entry": config["selected_external_entry"],
        "write_registries_requested": write_registries,
        "registries_written": registries_written,
        "result_eligible_for_formal_tables": registries_written,
        "blockers": blockers,
        "evidence": evidence,
        "baseline_registry_path": _relative(baseline_registry_path),
        "external_registry_path": _relative(external_registry_path),
        "boundary": (
            "Evidence admission only. Missing, partial, failed, diagnostic, stale, or "
            "hash-mismatched runs remain ineligible and never modify either registry."
        ),
    }
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(output_dir / f"{condition_id}_formal_admission_v1.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition-id", required=True, choices=sorted(CONDITIONS))
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--analysis-manifest", type=Path)
    parser.add_argument("--baseline-registry", type=Path, default=DEFAULT_BASELINE_REGISTRY)
    parser.add_argument("--external-registry", type=Path, default=DEFAULT_EXTERNAL_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-registries", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = admit(
        condition_id=args.condition_id,
        run_dir=args.run_dir,
        analysis_path=args.analysis_manifest,
        baseline_registry_path=args.baseline_registry,
        external_registry_path=args.external_registry,
        output_dir=args.output_dir,
        write_registries=args.write_registries,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"admitted_formal_result", "ready_for_registry_admission"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
