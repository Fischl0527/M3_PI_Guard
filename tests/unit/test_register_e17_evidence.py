from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import register_e17_evidence as registration


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, dict[str, object]]:
    root = tmp_path / "repo"
    e17_dir = root / "outputs" / "experiments" / "E17"
    source_index = root / "outputs" / "experiments" / "e17_source_index_corrected_v2.json"
    _write_json(
        source_index,
        {
            "schema_version": "2.0",
            "experiment_id": "E17",
            "source_mode": "formal_program_corrected_context",
            "status": "frozen",
        },
    )
    coverage = {
        "status": "pass",
        "duplicate_logical_run_count": 0,
        "duplicate_logical_step_count": 0,
        "logical_run_count": 1,
    }
    taxonomy = e17_dir / "failure_taxonomy.csv"
    agreement = e17_dir / "reviewer_agreement.json"
    taxonomy.parent.mkdir(parents=True, exist_ok=True)
    taxonomy.write_text("blind_id,primary_code\nB-1,none\n", encoding="utf-8")
    _write_json(agreement, {"reviewers": 2, "disagreements": 0})
    manifest_path = e17_dir / "manifest.json"
    manifest: dict[str, object] = {
        "schema_version": "2.0",
        "experiment_id": "E17",
        "status": "completed",
        "phase": "completed",
        "completed_at": "2026-07-14T00:00:00+00:00",
        "git": {"commit": "2c53f52"},
        "dataset": {"sha256": "a" * 64},
        "configuration": {
            "source_mode": "formal_program_corrected_context",
            "source_index": {
                "path": source_index.relative_to(root).as_posix(),
                "sha256": _hash(source_index),
            },
            "coverage": coverage,
            "registry_eligible": True,
        },
        "plan": {
            "source_mode": "formal_program_corrected_context",
            "source_index": {
                "path": source_index.relative_to(root).as_posix(),
                "sha256": _hash(source_index),
            },
            "coverage": coverage,
        },
        "progress": {
            "expected_runs": 1,
            "completed_runs": 1,
            "failed_jobs": 0,
            "unresolved_cases": 0,
        },
        "artifacts": [
            {
                "path": taxonomy.relative_to(root).as_posix(),
                "kind": "failure_taxonomy",
                "bytes": taxonomy.stat().st_size,
                "sha256": _hash(taxonomy),
            },
            {
                "path": agreement.relative_to(root).as_posix(),
                "kind": "reviewer_agreement",
                "bytes": agreement.stat().st_size,
                "sha256": _hash(agreement),
            },
        ],
    }
    _write_json(manifest_path, manifest)

    experiments: list[dict[str, object]] = []
    for index in range(18):
        experiment_id = f"E{index}"
        placeholder = root / "required" / experiment_id / "artifact.txt"
        placeholder.parent.mkdir(parents=True, exist_ok=True)
        placeholder.write_text("ok\n", encoding="utf-8")
        required = [str(placeholder)]
        if experiment_id == "E17":
            required = [str(manifest_path), str(taxonomy), str(agreement)]
        experiments.append(
            {
                "id": experiment_id,
                "name": f"fixture-{experiment_id}",
                "status": "running" if experiment_id == "E17" else "completed",
                "required_artifacts": required,
                "evidence": [],
                "error": "",
            }
        )
    registry_path = root / "experiments" / "registry.json"
    _write_json(registry_path, {"schema_version": "1.0", "experiments": experiments})
    return root, registry_path, source_index, manifest_path, manifest


def _completed_fast_path(monkeypatch: pytest.MonkeyPatch, manifest_path: Path) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_execute(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "manifest_path": str(manifest_path),
            "manifest": json.loads(manifest_path.read_text(encoding="utf-8")),
        }

    monkeypatch.setattr(registration.e17_review, "execute", fake_execute)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        registration.e17_review,
        "load_source_index",
        lambda _path: {
            "source_mode": "formal_program_corrected_context",
            "coverage": manifest["configuration"]["coverage"],
        },
    )
    return calls


def test_pending_manifest_is_rejected_without_invoking_or_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, registry, source_index, manifest_path, _ = _fixture(tmp_path)
    pending = json.loads(manifest_path.read_text(encoding="utf-8"))
    pending.update({"status": "running", "phase": "awaiting_independent_reviewers"})
    _write_json(manifest_path, pending)
    before = _hash(registry)

    def forbidden(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("pending E17 must not invoke execute")

    monkeypatch.setattr(registration.e17_review, "execute", forbidden)
    with pytest.raises(registration.E17RegistrationError, match="must already be"):
        registration.register(
            registry_path=registry,
            repository_root=root,
            source_index_path=source_index,
            manifest_path=manifest_path,
        )
    assert _hash(registry) == before


def test_cli_pending_manifest_has_clean_rejection_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, registry, source_index, manifest_path, _ = _fixture(tmp_path)
    pending = json.loads(manifest_path.read_text(encoding="utf-8"))
    pending.update({"status": "running", "phase": "awaiting_independent_reviewers"})
    _write_json(manifest_path, pending)
    monkeypatch.setattr(registration, "ROOT", root)

    with pytest.raises(SystemExit) as raised:
        registration.main(
            [
                "--registry",
                str(registry),
                "--source-index",
                str(source_index),
                "--manifest",
                str(manifest_path),
            ]
        )

    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert "E17 registration rejected:" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_dry_run_revalidates_completed_fast_path_and_apply_registers_all_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, registry, source_index, manifest_path, _ = _fixture(tmp_path)
    calls = _completed_fast_path(monkeypatch, manifest_path)
    before = _hash(registry)
    dry_run = registration.register(
        registry_path=registry,
        repository_root=root,
        source_index_path=source_index,
        manifest_path=manifest_path,
    )
    assert dry_run["mode"] == "dry_run"
    assert dry_run["registry_written"] is False
    assert dry_run["fast_path_revalidated"] is True
    assert dry_run["evidence_count"] == 4
    assert _hash(registry) == before
    assert len(calls) == 1

    applied = registration.register(
        registry_path=registry,
        repository_root=root,
        source_index_path=source_index,
        manifest_path=manifest_path,
        apply=True,
    )
    assert applied["registry_written"] is True
    assert applied["no_op"] is False
    stored = json.loads(registry.read_text(encoding="utf-8"))
    e17 = next(item for item in stored["experiments"] if item["id"] == "E17")
    assert e17["status"] == "completed"
    assert e17["evidence"] == applied["evidence"]
    assert e17["evidence"][0].endswith("E17/manifest.json")
    assert set(e17["evidence"][1:]) == {
        "outputs/experiments/e17_source_index_corrected_v2.json",
        "outputs/experiments/E17/failure_taxonomy.csv",
        "outputs/experiments/E17/reviewer_agreement.json",
    }
    assert e17["completion_registrar"] == "scripts/register_e17_evidence.py"
    assert e17["source_index"]["source_mode"] == "formal_program_corrected_context"
    assert len(calls) == 2

    no_op = registration.register(
        registry_path=registry,
        repository_root=root,
        source_index_path=source_index,
        manifest_path=manifest_path,
        apply=True,
    )
    assert no_op["already_registered"] is True
    assert no_op["registry_written"] is False
    assert no_op["no_op"] is True


def test_existing_final_analysis_is_rejected_before_fast_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, registry, source_index, manifest_path, _ = _fixture(tmp_path)
    (root / "outputs" / "experiments" / "final_analysis").mkdir(parents=True)

    def forbidden(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("stale synthesis gate must run before execute")

    monkeypatch.setattr(registration.e17_review, "execute", forbidden)
    with pytest.raises(registration.E17RegistrationError, match="after final_analysis exists"):
        registration.register(
            registry_path=registry,
            repository_root=root,
            source_index_path=source_index,
            manifest_path=manifest_path,
            apply=True,
        )


def test_manifest_artifact_escape_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, registry, source_index, manifest_path, manifest = _fixture(tmp_path)
    outside = tmp_path / "outside.csv"
    outside.write_text("x\n", encoding="utf-8")
    manifest["artifacts"] = [
        {
            "path": str(outside),
            "kind": "escape",
            "bytes": outside.stat().st_size,
            "sha256": _hash(outside),
        }
    ]
    _write_json(manifest_path, manifest)
    _completed_fast_path(monkeypatch, manifest_path)
    with pytest.raises(registration.E17RegistrationError, match="escapes repository root"):
        registration.register(
            registry_path=registry,
            repository_root=root,
            source_index_path=source_index,
            manifest_path=manifest_path,
        )


def test_hash_drift_and_source_binding_fail_without_registry_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, registry, source_index, manifest_path, manifest = _fixture(tmp_path)
    _completed_fast_path(monkeypatch, manifest_path)
    before = _hash(registry)
    taxonomy = root / "outputs" / "experiments" / "E17" / "failure_taxonomy.csv"
    taxonomy.write_text(taxonomy.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    with pytest.raises(registration.E17RegistrationError, match="(size|hash) mismatch"):
        registration.register(
            registry_path=registry,
            repository_root=root,
            source_index_path=source_index,
            manifest_path=manifest_path,
            apply=True,
        )
    assert _hash(registry) == before

    root2, registry2, source2, manifest2, payload2 = _fixture(tmp_path / "second")
    payload2["configuration"]["source_index"]["sha256"] = "0" * 64
    _write_json(manifest2, payload2)
    _completed_fast_path(monkeypatch, manifest2)
    before2 = _hash(registry2)
    with pytest.raises(registration.E17RegistrationError, match="hash/path mismatch"):
        registration.register(
            registry_path=registry2,
            repository_root=root2,
            source_index_path=source2,
            manifest_path=manifest2,
            apply=True,
        )
    assert _hash(registry2) == before2
