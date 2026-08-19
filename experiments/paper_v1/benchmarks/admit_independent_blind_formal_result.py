"""Fail-closed admission for a completed independent-blind formal result.

The preregistration-bound v1 candidate audit and historical final-analysis
manifest are immutable.  This bridge consumes the post-preregistration v2
candidate audit, verifies a separate formal result manifest and updates the
mutable paper-v1 evidence index only when explicitly requested.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .common import (
    portable_path,
    portable_value,
    resolve_artifact_path,
    rows_sha256,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_ROOT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_CANDIDATE_AUDIT = (
    PROTOCOL_ROOT / "m3_v2_independent_blind_admission_audit_v2.json"
)
DEFAULT_RUN_MANIFEST = (
    ROOT / "outputs" / "paper_upgrade_v1" / "m3_v2_independent_blind_v1" / "manifest.json"
)
DEFAULT_EVIDENCE_INDEX = PROTOCOL_ROOT / "paper_v1_evidence_index_v1.json"
DEFAULT_OUTPUT = PROTOCOL_ROOT
AUDIT_STEM = "m3_v2_independent_blind_formal_admission_v1"
REQUIRED_ARTIFACTS = ("runs", "metrics", "statistics", "figures_manifest")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _nested(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    child = value.get(key, {})
    return child if isinstance(child, Mapping) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _candidate_sha(manifest: Mapping[str, Any]) -> str:
    sources = _nested(manifest, "sources")
    candidate = _nested(sources, "independent_blind_candidate")
    dataset = _nested(manifest, "dataset")
    return _first_text(
        manifest.get("independent_blind_candidate_sha256"),
        manifest.get("candidate_sha256"),
        candidate.get("sha256"),
        dataset.get("sha256"),
    )


def _case_count(manifest: Mapping[str, Any]) -> int:
    summary = _nested(manifest, "summary")
    dataset = _nested(manifest, "dataset")
    for value in (
        manifest.get("selected_cases"),
        manifest.get("case_count"),
        summary.get("total_cases"),
        dataset.get("case_count"),
    ):
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _resolve_artifact(manifest_path: Path, raw_path: Any) -> Path:
    path = Path(str(raw_path or ""))
    repository_candidate = resolve_artifact_path(path, root=ROOT)
    if repository_candidate.exists():
        return repository_candidate
    return (manifest_path.parent / path).resolve()


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def build_admission(
    *,
    candidate_audit_path: Path = DEFAULT_CANDIDATE_AUDIT,
    run_manifest_path: Path = DEFAULT_RUN_MANIFEST,
    evidence_index_path: Path = DEFAULT_EVIDENCE_INDEX,
    output_dir: Path = DEFAULT_OUTPUT,
    write_evidence_index: bool = False,
) -> dict[str, Any]:
    candidate_audit_path = candidate_audit_path.resolve()
    run_manifest_path = run_manifest_path.resolve()
    evidence_index_path = evidence_index_path.resolve()
    output_dir = output_dir.resolve()
    candidate_audit = _read_json(candidate_audit_path)
    run_manifest = _read_json(run_manifest_path)
    evidence_index = _read_json(evidence_index_path)
    expected_candidate_sha = str(candidate_audit.get("candidate_sha256", ""))
    observed_candidate_sha = _candidate_sha(run_manifest)
    selected_cases = _case_count(run_manifest)
    expected_runs = int(run_manifest.get("expected_case_runs", 0) or 0)
    completed_runs = int(run_manifest.get("completed_case_runs", 0) or 0)
    failed_runs = int(run_manifest.get("failed_case_runs", 0) or 0)
    split = str(run_manifest.get("split", _nested(run_manifest, "dataset").get("split", "")))
    evidence_level = str(
        run_manifest.get(
            "evidence_level",
            _nested(run_manifest, "dataset").get("evidence_level", ""),
        )
    )

    artifacts = _nested(run_manifest, "artifacts")
    artifact_checks: list[dict[str, Any]] = []
    for name in REQUIRED_ARTIFACTS:
        record = artifacts.get(name, {})
        record = record if isinstance(record, Mapping) else {}
        artifact_path = _resolve_artifact(run_manifest_path, record.get("path"))
        declared_sha = str(record.get("sha256", ""))
        exists = bool(str(artifact_path)) and artifact_path.is_file()
        actual_sha = sha256_file(artifact_path) if exists else ""
        artifact_checks.append(
            {
                "name": name,
                "path": portable_path(artifact_path, root=ROOT) if exists else "",
                "exists": exists,
                "declared_sha256": declared_sha,
                "actual_sha256": actual_sha,
                "passed": exists and bool(declared_sha) and actual_sha == declared_sha,
            }
        )

    checks = [
        _check("candidate_audit_exists", candidate_audit_path.is_file(), portable_path(candidate_audit_path, root=ROOT)),
        _check("candidate_audit_admitted", candidate_audit.get("status") == "admitted_independent_blind", candidate_audit.get("status", "")),
        _check("candidate_audit_result_eligible", candidate_audit.get("result_eligible_for_confirmatory_q2_tables") is True, candidate_audit.get("result_eligible_for_confirmatory_q2_tables")),
        _check("candidate_sha_declared", bool(expected_candidate_sha), expected_candidate_sha),
        _check("run_manifest_exists", run_manifest_path.is_file(), portable_path(run_manifest_path, root=ROOT)),
        _check("run_status_completed_formal", run_manifest.get("status") in {"completed_formal", "completed_formal_analysis"}, run_manifest.get("status", "")),
        _check("run_result_eligible", run_manifest.get("result_eligible_for_confirmatory_q2_tables") is True, run_manifest.get("result_eligible_for_confirmatory_q2_tables")),
        _check("exact_600_cases", selected_cases == 600, selected_cases),
        _check("independent_blind_scope", split == "independent_blind" or evidence_level == "independent_blind", {"split": split, "evidence_level": evidence_level}),
        _check("candidate_sha_matches", bool(expected_candidate_sha) and observed_candidate_sha == expected_candidate_sha, {"expected": expected_candidate_sha, "observed": observed_candidate_sha}),
        _check("case_runs_complete", expected_runs > 0 and completed_runs == expected_runs, {"expected": expected_runs, "completed": completed_runs}),
        _check("zero_failed_case_runs", failed_runs == 0, failed_runs),
        _check("required_artifacts_complete", all(row["passed"] for row in artifact_checks), artifact_checks),
        _check("evidence_index_exists", evidence_index_path.is_file(), portable_path(evidence_index_path, root=ROOT)),
        _check("evidence_index_schema", evidence_index.get("schema_version") == "paper-v1-evidence-index-1.0", evidence_index.get("schema_version", "")),
    ]
    blockers = [row["name"] for row in checks if not row["passed"]]
    admitted = not blockers
    index_written = False
    if admitted and write_evidence_index:
        updated = dict(evidence_index)
        updated["revision"] = int(updated.get("revision", 0) or 0) + 1
        updated["m3_v2_independent_blind_manifest"] = portable_path(
            run_manifest_path,
            root=ROOT,
        )
        updated["m3_v2_independent_blind_manifest_sha256"] = sha256_file(run_manifest_path)
        updated["m3_v2_independent_blind_candidate_sha256"] = expected_candidate_sha
        updated["m3_v2_independent_blind_admission_audit"] = portable_path(
            candidate_audit_path,
            root=ROOT,
        )
        updated["result_eligible_for_confirmatory_q2_tables"] = True
        temporary = evidence_index_path.with_suffix(evidence_index_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(evidence_index_path)
        index_written = True

    admission = portable_value(
        {
            "schema_version": "paper-independent-blind-formal-admission-1.0",
            "status": "admitted_formal_independent_blind" if admitted else "blocked_not_admitted",
            "result_eligible_for_confirmatory_q2_tables": admitted,
            "candidate_audit_path": str(candidate_audit_path),
            "candidate_audit_sha256": sha256_file(candidate_audit_path) if candidate_audit_path.is_file() else "",
            "run_manifest_path": str(run_manifest_path),
            "run_manifest_sha256": sha256_file(run_manifest_path) if run_manifest_path.is_file() else "",
            "evidence_index_path": str(evidence_index_path),
            "evidence_index_written": index_written,
            "write_evidence_index_requested": bool(write_evidence_index),
            "checks": checks,
            "checks_sha256": rows_sha256(checks),
            "blockers": blockers,
            "artifact_checks": artifact_checks,
            "boundary": (
                "Admission only. A missing, partial, failed, hash-mismatched or non-independent "
                "result cannot update the paper-v1 evidence index. The preregistration-bound v1 "
                "audit and historical final_analysis manifest are never rewritten."
            ),
        },
        root=ROOT,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{AUDIT_STEM}.json"
    output_path.write_text(
        json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return admission


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-audit", type=Path, default=DEFAULT_CANDIDATE_AUDIT)
    parser.add_argument("--run-manifest", type=Path, default=DEFAULT_RUN_MANIFEST)
    parser.add_argument("--evidence-index", type=Path, default=DEFAULT_EVIDENCE_INDEX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-evidence-index", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    admission = build_admission(
        candidate_audit_path=args.candidate_audit,
        run_manifest_path=args.run_manifest,
        evidence_index_path=args.evidence_index,
        output_dir=args.output_dir,
        write_evidence_index=args.write_evidence_index,
    )
    print(json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if admission["result_eligible_for_confirmatory_q2_tables"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
