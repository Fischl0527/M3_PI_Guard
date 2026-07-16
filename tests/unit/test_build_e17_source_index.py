from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments import e17_review as e17
from scripts import build_e17_source_index as builder


def _hash(path: Path) -> str:
    return e17._sha256_file(path)


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _ref(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _hash(path),
    }


def _case(case_id: str, sample_type: str = "attack") -> dict[str, object]:
    return {
        "case_id": case_id,
        "sample_type": sample_type,
        "user_task": "Review the local fixture.",
        "authorized_actions": [],
        "unsafe_target_actions": [],
    }


def _log(
    case_id: str,
    run_key: str,
    *,
    experiment_id: str,
    condition_id: str,
    correction_job_type: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "case_id": case_id,
        "run_key": run_key,
        "run_id": run_key,
        "step": 1,
        "experiment_id": experiment_id,
        "condition_id": condition_id,
        "model": "qwen-fixture",
        "prompt_profile": "normal",
        "guard_mode": "full_guard",
        "sample_type": "attack",
        "seed": 17,
        "parse_ok": True,
        "parsed_tool_call": {"tool": "final", "arguments": {"answer": "ok"}},
        "guard_decision": "allow",
        "final_status": "completed",
    }
    if correction_job_type is not None:
        row.update(
            {
                "correction_job_type": correction_job_type,
                "correction_job_id": run_key,
                "correction_protocol_id": e17.CONTEXT_CORRECTION_PROTOCOL_ID,
                "evidence_tier": "formal_model",
            }
        )
    return row


def _artifact(path: Path, kind: str, root: Path) -> dict[str, object]:
    return {**_ref(path, root), "kind": kind}


def _completed_manifest(
    experiment_id: str,
    *,
    expected: int,
    configuration: dict[str, object],
    artifacts: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "experiment_id": experiment_id,
        "status": "completed",
        "git": {"commit": "fixture-commit"},
        "dataset": {"paths": [], "sha256": "fixture-dataset"},
        "models": ["qwen-fixture"],
        "configuration": configuration,
        "progress": {
            "expected_runs": expected,
            "completed_runs": expected,
            "failed_jobs": 0,
            "unresolved_cases": 0,
        },
        "artifacts": artifacts,
    }


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    root = tmp_path.resolve()
    monkeypatch.setattr(e17, "REPO_ROOT", root)
    monkeypatch.setattr(builder, "ROOT", root)
    program_root = root / "outputs" / "experiments" / "program_final_v3"
    program_cases = _write_jsonl(program_root / "cases.jsonl", [_case("program-case")])
    stages: dict[str, object] = {}
    allowlist: dict[str, dict[str, str]] = {}

    for stage_name in e17.REQUIRED_PROGRAM_STAGES:
        jobs: list[dict[str, object]] = []
        count = 4 if stage_name == "derived" else 1
        for position in range(count):
            job_id = (
                f"derived__e9__fixture__ctx_{position}"
                if stage_name == "derived"
                else f"{stage_name}__fixture"
            )
            job_dir = program_root / stage_name / job_id
            condition_id = f"{stage_name}-condition-{position}"
            log_path = _write_jsonl(
                job_dir / "result.jsonl",
                [
                    _log(
                        "program-case",
                        f"program:{stage_name}:{position}",
                        experiment_id=f"program-{stage_name}",
                        condition_id=condition_id,
                    )
                ],
            )
            matrix_path = _write_json(
                job_dir / "manifest.json",
                {
                    "status": "completed",
                    "backend": "ollama",
                    "oracle_stub": False,
                    "evidence_tier": "formal_model",
                    "model": "qwen-fixture",
                    "run_group": stage_name,
                    "config": {"run_group": stage_name},
                    "dataset": {"path": str(program_cases), "sha256": _hash(program_cases)},
                    "conditions": [{"condition_id": condition_id}],
                    "results": [
                        {
                            "condition_id": condition_id,
                            "status": "completed",
                            "jsonl": str(log_path),
                            "jsonl_sha256": _hash(log_path),
                            "log_count": 1,
                        }
                    ],
                },
            )
            relative = matrix_path.relative_to(root).as_posix()
            if stage_name == "derived":
                allowlist[job_id] = {"path": relative, "sha256": _hash(matrix_path)}
            jobs.append(
                {"job_id": job_id, "status": "completed", "result_manifest": relative}
            )
        stages[stage_name] = {"status": "completed", "jobs": jobs}
    program_manifest = _write_json(
        root / "outputs" / "experiments" / "program_manifest_final_v3.json",
        {"status": "completed", "stages": stages},
    )
    monkeypatch.setattr(e17, "INVALID_V3_E9_MANIFEST_ALLOWLIST", allowlist)

    invalid_audit = _write_json(
        root / "agent" / "audits" / "context_experiment_validity.json",
        {"status": "fail", "E9": {"status": "fail"}, "E14": {"status": "fail"}},
    )
    frozen_file = _write_json(root / "protocols" / "context_correction_v2" / "protocol.json", {})
    freeze = _write_json(
        root / "protocols" / "context_correction_v2" / "freeze.json",
        {
            "protocol_id": e17.CONTEXT_CORRECTION_PROTOCOL_ID,
            "workload_revision": "r2",
            "status": "pass",
            "freeze_complete": True,
            "files": [_ref(frozen_file, root)],
        },
    )
    freeze_hash = _hash(freeze)

    e9_cases = [_case(f"e9-case-{index}") for index in range(60)]
    e9_case_path = _write_jsonl(
        root / "protocols" / "context_correction_v2" / "fixtures" / "e9_cases.jsonl",
        e9_cases,
    )
    e9_rows = [
        _log(
            str(e9_cases[index % 60]["case_id"]),
            f"e9:{index}",
            experiment_id="E9",
            condition_id="e9-off" if index < 60 else "e9-full",
            correction_job_type="formal",
        )
        for index in range(120)
    ]
    e9_dir = root / "outputs" / "experiments" / "E9_context_correction_v2"
    e9_raw = _write_jsonl(e9_dir / "raw_runs.jsonl", e9_rows)
    e9_index = _write_json(e9_dir / "raw_run_index.json", {"logical_case_runs": 120})
    e9_validity_value = {
        "status": "pass",
        "expected_case_runs": 120,
        "observed_first_step_case_runs": 120,
    }
    e9_validity = _write_json(e9_dir / "validity_checks.json", e9_validity_value)
    e9_manifest_value = _completed_manifest(
        "E9",
        expected=120,
        configuration={
            "phase": "formal",
            "protocol_id": e17.CONTEXT_CORRECTION_PROTOCOL_ID,
            "freeze_sha256": freeze_hash,
            "fixture_sha256": _hash(e9_case_path),
            "cases": str(e9_case_path),
        },
        artifacts=[
            _artifact(e9_raw, "raw_log", root),
            _artifact(e9_index, "raw_run_index", root),
            _artifact(e9_validity, "semantic_validity", root),
        ],
    )
    e9_manifest_value.update(
        {
            "protocol_id": e17.CONTEXT_CORRECTION_PROTOCOL_ID,
            "denominator_policy": "V2_only_old_V3_excluded",
            "validity_checks": e9_validity_value,
        }
    )
    e9_manifest = _write_json(e9_dir / "manifest.json", e9_manifest_value)

    e14_cases = [_case(f"e14-case-{index}", "benign") for index in range(40)]
    e14_case_path = _write_jsonl(
        root / "protocols" / "context_correction_v2" / "fixtures" / "e14_cases.jsonl",
        e14_cases,
    )
    e14_formal_rows = [
        _log(
            str(e14_cases[index % 40]["case_id"]),
            f"e14-formal:{index}",
            experiment_id="E14",
            condition_id="e14-formal",
            correction_job_type="formal",
        )
        for index in range(432)
    ]
    e14_warmup_rows = [
        _log(
            str(e14_cases[index % 40]["case_id"]),
            f"e14-warmup:{index}",
            experiment_id="E14",
            condition_id="e14-warmup",
            correction_job_type="warmup",
        )
        for index in range(48)
    ]
    e14_dir = root / "outputs" / "experiments" / "E14_context_correction_v2"
    e14_raw = _write_jsonl(e14_dir / "raw_runs.jsonl", e14_warmup_rows + e14_formal_rows)
    e14_formal = _write_jsonl(e14_dir / "formal_raw_runs.jsonl", e14_formal_rows)
    e14_index = _write_json(e14_dir / "raw_run_index.json", {"logical_case_runs": 432})
    e14_validity_value = {
        "status": "pass",
        "expected_formal_case_runs": 432,
        "observed_formal_case_runs": 432,
        "expected_warmup_case_runs": 48,
        "observed_warmup_case_runs": 48,
    }
    e14_validity = _write_json(e14_dir / "validity_checks.json", e14_validity_value)
    e14_manifest_value = _completed_manifest(
        "E14",
        expected=432,
        configuration={
            "phase": "formal",
            "protocol_id": e17.CONTEXT_CORRECTION_PROTOCOL_ID,
            "freeze_sha256": freeze_hash,
            "fixture_sha256": _hash(e14_case_path),
            "cases": str(e14_case_path),
        },
        artifacts=[
            _artifact(e14_raw, "raw_log", root),
            _artifact(e14_formal, "formal_raw_log", root),
            _artifact(e14_index, "raw_run_index", root),
            _artifact(e14_validity, "semantic_validity", root),
        ],
    )
    e14_manifest_value.update(
        {
            "protocol_id": e17.CONTEXT_CORRECTION_PROTOCOL_ID,
            "denominator_policy": "V2_only_old_V3_excluded",
            "warmup_expected_case_runs": 48,
            "validity_checks": e14_validity_value,
        }
    )
    e14_manifest = _write_json(e14_dir / "manifest.json", e14_manifest_value)

    e16_case = _case("e16-case")
    e16_raw = _write_jsonl(
        root / "outputs" / "experiments" / "E16" / "raw_attempts.jsonl",
        [
            {
                "attempt_key": "adaptive-1",
                "status": "completed",
                "attack_case": e16_case,
                "run_config": {"model": "qwen-fixture", "seed": 17},
                "logs": [
                    _log(
                        "e16-case",
                        "e16:adaptive-1",
                        experiment_id="E16",
                        condition_id="E16-adaptive",
                    )
                ],
            }
        ],
    )
    e16_manifest_value = _completed_manifest(
        "E16",
        expected=1,
        configuration={"backend": "ollama"},
        artifacts=[_artifact(e16_raw, "raw_log", root)],
    )
    e16_manifest = _write_json(
        root / "outputs" / "experiments" / "E16" / "manifest.json",
        e16_manifest_value,
    )

    correction_audit = _write_json(
        root / "agent" / "audits" / "context_correction_v2.json",
        {
            "status": "pass",
            "protocol_id": e17.CONTEXT_CORRECTION_PROTOCOL_ID,
            "workload_revision": "r2",
            "inputs": {
                "freeze": _ref(freeze, root),
                "formal_manifests": {
                    "E9": _ref(e9_manifest, root),
                    "E14": _ref(e14_manifest, root),
                },
            },
            "experiments": {
                "E9": {"experiment_id": "E9", "manifest": _ref(e9_manifest, root)},
                "E14": {"experiment_id": "E14", "manifest": _ref(e14_manifest, root)},
            },
        },
    )
    return {
        "root": root,
        "program_root": program_root,
        "program_manifest": program_manifest,
        "allowlist": allowlist,
        "invalid_audit": invalid_audit,
        "freeze": freeze,
        "correction_audit": correction_audit,
        "e9_manifest": e9_manifest,
        "e14_manifest": e14_manifest,
        "e16_manifest": e16_manifest,
    }


def _build(files: dict[str, object]) -> dict[str, object]:
    return builder.build_source_index(
        root=files["root"],
        program_manifest_path=files["program_manifest"],
        program_root_path=files["program_root"],
        invalid_context_audit_path=files["invalid_audit"],
        correction_freeze_path=files["freeze"],
        correction_audit_path=files["correction_audit"],
        e16_manifest_path=files["e16_manifest"],
        invalid_e9_allowlist=files["allowlist"],
    )


def test_schema2_builder_is_deterministic_and_loader_recomputes_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = _fixture(tmp_path, monkeypatch)
    first = _build(files)
    second = _build(files)
    assert first == second
    assert first["schema_version"] == "2.0"
    assert "coverage_complete" not in first
    assert first["coverage"]["excluded_invalid_e9_matrix_count"] == 4
    assert first["coverage"]["corrected_e9_logical_run_count"] == 120
    assert first["coverage"]["corrected_e14_formal_logical_run_count"] == 432
    assert first["coverage"]["corrected_e14_warmup_logical_run_count_excluded"] == 48

    target = Path(files["root"]) / "outputs" / "experiments" / "e17-v2.json"
    builder.write_source_index(target, first)
    bundle = e17.load_source_index(target)
    assert bundle["coverage"] == first["coverage"]
    assert bundle["source_mode"] == e17.SOURCE_MODE_FORMAL_CORRECTED

    tampered = json.loads(target.read_text(encoding="utf-8"))
    tampered["coverage_complete"] = True  # deliberately ignored
    tampered["coverage"]["logical_run_count"] += 1
    target.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(e17.E17Error, match="recomputed coverage"):
        e17.load_source_index(target)


def test_builder_rejects_any_non_allowlisted_or_hash_drifted_e9_exclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = _fixture(tmp_path, monkeypatch)
    allowlist = dict(files["allowlist"])
    first_id = sorted(allowlist)[0]
    allowlist[first_id] = {**allowlist[first_id], "sha256": "0" * 64}
    with pytest.raises(builder.SourceIndexBuildError, match="drifted"):
        builder.build_source_index(
            root=files["root"],
            program_manifest_path=files["program_manifest"],
            program_root_path=files["program_root"],
            invalid_context_audit_path=files["invalid_audit"],
            correction_freeze_path=files["freeze"],
            correction_audit_path=files["correction_audit"],
            e9_manifest_path=files["e9_manifest"],
            e14_manifest_path=files["e14_manifest"],
            e16_manifest_path=files["e16_manifest"],
            invalid_e9_allowlist=allowlist,
        )


def test_builder_rejects_non_r2_correction_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = _fixture(tmp_path, monkeypatch)
    freeze = json.loads(Path(files["freeze"]).read_text(encoding="utf-8"))
    freeze["workload_revision"] = "r1"
    Path(files["freeze"]).write_text(json.dumps(freeze), encoding="utf-8")
    with pytest.raises(e17.E17Error, match="completed V2 freeze"):
        _build(files)


def test_default_correction_freeze_is_r2() -> None:
    assert builder.DEFAULT_CORRECTION_FREEZE.name == "freeze_r3.json"


def test_legacy_formal_index_is_diagnostic_only(tmp_path: Path) -> None:
    index = _write_json(
        tmp_path / "legacy.json",
        {
            "schema_version": "1.0",
            "experiment_id": "E17",
            "status": "frozen",
            "coverage_complete": True,
            "source_mode": e17.SOURCE_MODE_FORMAL,
            "secondary_disagreement_policy": e17.SECONDARY_DISAGREEMENT_POLICY,
        },
    )
    with pytest.raises(e17.E17Error, match="diagnostic-only"):
        e17.load_source_index(index)
