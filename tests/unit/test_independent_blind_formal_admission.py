from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.paper_v1.benchmarks.admit_independent_blind_formal_result import (
    build_admission,
)
from experiments.paper_v1.benchmarks.audit_q2_readiness import _confirmatory_blind


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, *, candidate_sha: str = "a" * 64) -> tuple[Path, Path, Path]:
    candidate_audit = tmp_path / "candidate_audit.json"
    _write_json(
        candidate_audit,
        {
            "status": "admitted_independent_blind",
            "result_eligible_for_confirmatory_q2_tables": True,
            "candidate_sha256": candidate_sha,
        },
    )
    run_root = tmp_path / "run"
    artifacts: dict[str, dict[str, str]] = {}
    for name in ("runs", "metrics", "statistics", "figures_manifest"):
        path = run_root / f"{name}.json"
        _write_json(path, {"name": name})
        artifacts[name] = {"path": path.name, "sha256": _sha(path)}
    run_manifest = run_root / "manifest.json"
    _write_json(
        run_manifest,
        {
            "status": "completed_formal",
            "result_eligible_for_confirmatory_q2_tables": True,
            "selected_cases": 600,
            "split": "independent_blind",
            "candidate_sha256": candidate_sha,
            "expected_case_runs": 1200,
            "completed_case_runs": 1200,
            "failed_case_runs": 0,
            "artifacts": artifacts,
        },
    )
    evidence_index = tmp_path / "paper_v1_evidence_index_v1.json"
    _write_json(
        evidence_index,
        {
            "schema_version": "paper-v1-evidence-index-1.0",
            "status": "active_evidence_index",
            "revision": 1,
            "m3_v2_independent_blind_manifest": "",
        },
    )
    return candidate_audit, run_manifest, evidence_index


def test_missing_formal_result_is_blocked_without_index_write(tmp_path: Path) -> None:
    candidate_audit, _run_manifest, evidence_index = _fixture(tmp_path)
    before = evidence_index.read_bytes()
    admission = build_admission(
        candidate_audit_path=candidate_audit,
        run_manifest_path=tmp_path / "missing.json",
        evidence_index_path=evidence_index,
        output_dir=tmp_path / "audit",
        write_evidence_index=True,
    )

    assert admission["status"] == "blocked_not_admitted"
    assert admission["result_eligible_for_confirmatory_q2_tables"] is False
    assert "run_manifest_exists" in admission["blockers"]
    assert evidence_index.read_bytes() == before


def test_valid_result_requires_explicit_write_then_updates_separate_index(tmp_path: Path) -> None:
    candidate_audit, run_manifest, evidence_index = _fixture(tmp_path)
    before = evidence_index.read_bytes()
    plan = build_admission(
        candidate_audit_path=candidate_audit,
        run_manifest_path=run_manifest,
        evidence_index_path=evidence_index,
        output_dir=tmp_path / "plan",
    )
    assert plan["status"] == "admitted_formal_independent_blind"
    assert plan["evidence_index_written"] is False
    assert evidence_index.read_bytes() == before

    admitted = build_admission(
        candidate_audit_path=candidate_audit,
        run_manifest_path=run_manifest,
        evidence_index_path=evidence_index,
        output_dir=tmp_path / "admit",
        write_evidence_index=True,
    )
    updated = json.loads(evidence_index.read_text(encoding="utf-8"))
    assert admitted["evidence_index_written"] is True
    assert updated["revision"] == 2
    assert updated["m3_v2_independent_blind_manifest"] == str(run_manifest)
    assert updated["m3_v2_independent_blind_manifest_sha256"] == _sha(run_manifest)

    criterion = _confirmatory_blind(
        {"formal_evidence_policy": {"E17": "historical_sample_only"}},
        json.loads(candidate_audit.read_text(encoding="utf-8")),
        updated,
    )
    assert criterion["status"] == "complete"
    assert criterion["earned"] == 15.0


def test_candidate_hash_or_artifact_mismatch_blocks_update(tmp_path: Path) -> None:
    candidate_audit, run_manifest, evidence_index = _fixture(tmp_path)
    manifest = json.loads(run_manifest.read_text(encoding="utf-8"))
    manifest["candidate_sha256"] = "b" * 64
    manifest["artifacts"]["metrics"]["sha256"] = "0" * 64
    _write_json(run_manifest, manifest)
    before = evidence_index.read_bytes()

    admission = build_admission(
        candidate_audit_path=candidate_audit,
        run_manifest_path=run_manifest,
        evidence_index_path=evidence_index,
        output_dir=tmp_path / "audit",
        write_evidence_index=True,
    )

    assert "candidate_sha_matches" in admission["blockers"]
    assert "required_artifacts_complete" in admission["blockers"]
    assert evidence_index.read_bytes() == before
