from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import register_context_correction as registration_module
from scripts.audit_context_correction_v2 import (
    PROTOCOL_ID,
    audit_context_correction_v2,
)
from scripts.register_context_correction import (
    ContextCorrectionRegistrationError,
    register_context_correction,
)


TARGETS = (2048, 4096, 8192, 16384)
MODELS = {
    2048: "m3-qwen3-4b-ctx4k:latest",
    4096: "m3-qwen3-4b-ctx8k:latest",
    8192: "m3-qwen3-4b-ctx16k:latest",
    16384: "m3-qwen3-4b-ctx32k:latest",
}
ALIASES = {
    2048: "0ce262040abb",
    4096: "81f2e7df722a",
    8192: "b7c705adc68a",
    16384: "ef6929a22b37",
}
CONTEXTS = {2048: 4096, 4096: 8192, 8192: 16384, 16384: 32768}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _file_record(path: Path, root: Path, *, kind: str) -> dict[str, object]:
    return {
        "path": _relative(path, root),
        "kind": kind,
        "bytes": path.stat().st_size,
        "sha256": _hash(path),
    }


def _dataset_hash(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item.resolve() for item in paths), key=lambda item: str(item)):
        digest.update(_relative(path, root).encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(_hash(path)))
    return digest.hexdigest()


def _fixtures(root: Path) -> tuple[Path, Path, list[dict[str, object]], list[dict[str, object]]]:
    fixture_root = root / "protocols" / "context_correction_v2" / "fixtures_r2"
    e9: list[dict[str, object]] = []
    for target in TARGETS:
        for index in range(15):
            e9.append(
                {
                    "case_id": f"E9-R2-{target}-{index:02d}",
                    "sample_type": "attack",
                    "attack_dimensions": {
                        "target_prompt_tokens": target,
                        "injection_position_pct": (index % 5) * 25,
                    },
                }
            )
    e14: list[dict[str, object]] = []
    for target in TARGETS:
        for index in range(4):
            e14.append(
                {
                    "case_id": f"E14-R2-MATCH-{target}-{index}",
                    "sample_type": "benign",
                    "attack_dimensions": {
                        "target_prompt_tokens": target,
                        "workload_cohort": "matched_benign_latency",
                    },
                }
            )
        for index in range(6):
            e14.append(
                {
                    "case_id": f"E14-R2-MIX-{target}-{index}",
                    "sample_type": "attack" if index % 2 else "benign",
                    "attack_dimensions": {
                        "target_prompt_tokens": target,
                        "workload_cohort": "mixed_throughput",
                    },
                }
            )
    e9_path = fixture_root / "e9_cases_r2.jsonl"
    e14_path = fixture_root / "e14_cases_r2.jsonl"
    _write_jsonl(e9_path, e9)
    _write_jsonl(e14_path, e14)
    return e9_path, e14_path, e9, e14


def _prompt_proof(
    root: Path,
    e9_path: Path,
    e14_path: Path,
    e9: list[dict[str, object]],
    e14: list[dict[str, object]],
) -> Path:
    observations: list[dict[str, object]] = []
    for experiment_id, rows in (("E9", e9), ("E14", e14)):
        for row in rows:
            target = int(row["attack_dimensions"]["target_prompt_tokens"])  # type: ignore[index]
            observations.append(
                {
                    "case_id": row["case_id"],
                    "experiment_id": experiment_id,
                    "target_prompt_tokens": target,
                    "observed_prompt_eval_count": target + 2,
                    "usage_source": "ollama_native_prompt_eval_count",
                    "provider_done": True,
                    "within_tolerance": True,
                    "served_model": MODELS[target],
                    "effective_context_window_tokens": CONTEXTS[target],
                    "provider_attempts": 1,
                    "verification_request_attempts": 1,
                    "fixture_row_sha256": "a" * 64,
                    "rendered_messages_sha256": "b" * 64,
                }
            )
    prompt = root / "protocols" / "context_correction_v2" / "prompt_verification_r2.json"
    _write_json(
        prompt,
        {
            "schema_version": "2.0",
            "protocol_id": PROTOCOL_ID,
            "workload_revision": "r2",
            "status": "pass",
            "measurement_role": "frozen_first_turn_workload_proof_not_model_outcome",
            "num_predict": 1,
            "temperature": 0.0,
            "seed": 419,
            "ollama_version": "ollama version is 0.24.0",
            "checks": {"all": True},
            "target_medians": {str(target): target + 2 for target in TARGETS},
            "fixture_files": {
                "E9": {"path": _relative(e9_path, root), "sha256": _hash(e9_path)},
                "E14": {"path": _relative(e14_path, root), "sha256": _hash(e14_path)},
            },
            "model_evidence": {
                str(target): {
                    "served_model": MODELS[target],
                    "installed_alias_id": ALIASES[target],
                    "expected_effective_context_window_tokens": CONTEXTS[target],
                    "resident_snapshot": {
                        "models": [
                            {
                                "name": MODELS[target],
                                "context_length": CONTEXTS[target],
                            }
                        ]
                    },
                }
                for target in TARGETS
            },
            "observations": observations,
        },
    )
    return prompt


def _smoke(
    root: Path, experiment_id: str, prompt: Path, fixture: Path
) -> Path:
    path = (
        root
        / "outputs"
        / "experiments"
        / f"{experiment_id}_context_correction_v2_smoke_r2"
        / "manifest.json"
    )
    plan = path.parent / "execution_plan.json"
    raw = path.parent / "raw_runs.jsonl"
    validity_path = path.parent / "validity_checks.json"
    _write_json(plan, {"experiment_id": experiment_id, "phase": "smoke"})
    _write_jsonl(raw, [{"experiment_id": experiment_id, "step": 1}])
    validity = {"status": "pass", "checks": {"synthetic": True}}
    _write_json(validity_path, validity)
    dataset_paths = [fixture, prompt, plan]
    _write_json(
        path,
        {
            "experiment_id": experiment_id,
            "protocol_id": PROTOCOL_ID,
            "workload_revision": "r2",
            "status": "completed",
            "configuration": {
                "phase": "smoke",
                "prompt_verification_sha256": _hash(prompt),
            },
            "validity_checks": validity,
            "progress": {"expected_runs": 48, "completed_runs": 48, "failed_jobs": 0},
            "dataset": {
                "paths": [_relative(item, root) for item in dataset_paths],
                "sha256": _dataset_hash(dataset_paths, root),
            },
            "jobs": [
                {"id": f"smoke-{index}", "status": "completed"}
                for index in range(8)
            ],
            "artifacts": [
                _file_record(plan, root, kind="execution_plan"),
                _file_record(prompt, root, kind="prompt_workload_verification"),
                _file_record(raw, root, kind="raw_log"),
                _file_record(validity_path, root, kind="semantic_validity"),
            ],
        },
    )
    return path


def _freeze(root: Path, prompt: Path, smoke_e9: Path, smoke_e14: Path) -> tuple[Path, tuple[str, ...]]:
    protocol_root = root / "protocols" / "context_correction_v2"
    frozen_paths = [
        protocol_root / "protocol_r2.md",
        protocol_root / "protocol_r2.json",
        prompt,
        protocol_root / "fixtures_r2" / "e9_cases_r2.jsonl",
        protocol_root / "fixtures_r2" / "e14_cases_r2.jsonl",
        root / "experiments" / "frozen_runtime_r2.py",
    ]
    for path in frozen_paths:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"frozen: {path.name}\n", encoding="utf-8")
    relative_paths = tuple(_relative(path, root) for path in frozen_paths)
    freeze = protocol_root / "freeze.json"
    _write_json(
        freeze,
        {
            "schema_version": "2.0",
            "protocol_id": PROTOCOL_ID,
            "workload_revision": "r2",
            "status": "pass",
            "freeze_complete": True,
            "files": [
                {
                    "path": _relative(path, root),
                    "bytes": path.stat().st_size,
                    "sha256": _hash(path),
                }
                for path in frozen_paths
            ],
            "prompt_verification": {
                "path": _relative(prompt, root),
                "status": "pass",
                "workload_revision": "r2",
                "case_count": 100,
                "sha256": _hash(prompt),
            },
            "smoke_evidence": {
                "E9": {
                    "manifest_path": _relative(smoke_e9, root),
                    "bytes": smoke_e9.stat().st_size,
                    "sha256": _hash(smoke_e9),
                },
                "E14": {
                    "manifest_path": _relative(smoke_e14, root),
                    "bytes": smoke_e14.stat().st_size,
                    "sha256": _hash(smoke_e14),
                },
            },
            "model_profiles": {
                str(target): {
                    "served_model": MODELS[target],
                    "alias_id": ALIASES[target],
                    "effective_context_window_tokens": CONTEXTS[target],
                }
                for target in TARGETS
            },
            "test_gate": {"status": "pass", "passed": 17},
        },
    )
    return freeze, relative_paths


def _e9_jobs(e9: list[dict[str, object]]) -> list[dict[str, object]]:
    jobs: list[dict[str, object]] = []
    for target in TARGETS:
        ids = [
            str(row["case_id"])
            for row in e9
            if row["attack_dimensions"]["target_prompt_tokens"] == target  # type: ignore[index]
        ]
        for condition, guard in (("derived_normal_off", "off"), ("derived_normal_full", "full_guard")):
            jobs.append(
                {
                    "id": f"formal__ctx{target}__{condition}",
                    "protocol_id": PROTOCOL_ID,
                    "phase": "formal",
                    "served_model": MODELS[target],
                    "target_prompt_tokens": target,
                    "effective_context_window_tokens": CONTEXTS[target],
                    "condition_id": condition,
                    "workload_cohort": "long_context_attack",
                    "concurrency": 1,
                    "outer_replicate_id": 0,
                    "case_ids": ids,
                    "expected_case_runs": 15,
                }
            )
    return jobs


def _e14_jobs(e14: list[dict[str, object]]) -> list[dict[str, object]]:
    jobs: list[dict[str, object]] = []
    for target in TARGETS:
        matched = [
            str(row["case_id"])
            for row in e14
            if row["attack_dimensions"]["target_prompt_tokens"] == target  # type: ignore[index]
            and row["attack_dimensions"]["workload_cohort"] == "matched_benign_latency"  # type: ignore[index]
        ]
        mixed = [
            str(row["case_id"])
            for row in e14
            if row["attack_dimensions"]["target_prompt_tokens"] == target  # type: ignore[index]
            and row["attack_dimensions"]["workload_cohort"] == "mixed_throughput"  # type: ignore[index]
        ]
        for condition in ("e14_v2_warmup_off", "e14_v2_warmup_full_guard"):
            jobs.append(
                {
                    "id": f"warmup__ctx{target}__{condition}",
                    "protocol_id": PROTOCOL_ID,
                    "job_type": "warmup",
                    "served_model": MODELS[target],
                    "target_prompt_tokens": target,
                    "effective_context_window_tokens": CONTEXTS[target],
                    "condition_id": condition,
                    "workload_cohort": "mixed_throughput",
                    "concurrency": 1,
                    "outer_replicate_id": 0,
                    "case_ids": mixed,
                    "expected_case_runs": 6,
                }
            )
        for concurrency in (1, 2, 4):
            for outer in range(3):
                for condition in ("e14_v2_off", "e14_v2_full_guard"):
                    jobs.append(
                        {
                            "id": f"matched__ctx{target}__c{concurrency}__r{outer}__{condition}",
                            "protocol_id": PROTOCOL_ID,
                            "job_type": "formal",
                            "served_model": MODELS[target],
                            "target_prompt_tokens": target,
                            "effective_context_window_tokens": CONTEXTS[target],
                            "condition_id": condition,
                            "workload_cohort": "matched_benign_latency",
                            "concurrency": concurrency,
                            "outer_replicate_id": outer,
                            "case_ids": matched,
                            "expected_case_runs": 4,
                        }
                    )
            for condition in ("e14_v2_off", "e14_v2_full_guard"):
                jobs.append(
                    {
                        "id": f"mixed__ctx{target}__c{concurrency}__{condition}",
                        "protocol_id": PROTOCOL_ID,
                        "job_type": "formal",
                        "served_model": MODELS[target],
                        "target_prompt_tokens": target,
                        "effective_context_window_tokens": CONTEXTS[target],
                        "condition_id": condition,
                        "workload_cohort": "mixed_throughput",
                        "concurrency": concurrency,
                        "outer_replicate_id": 0,
                        "case_ids": mixed,
                        "expected_case_runs": 6,
                    }
                )
    return jobs


def _job_evidence(
    root: Path,
    bundle: Path,
    experiment_id: str,
    job: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    job_dir = bundle / "work" / str(job["id"])
    lane_dir = job_dir / "lane_0"
    rows: list[dict[str, object]] = []
    for case_id in job["case_ids"]:  # type: ignore[union-attr]
        target = int(job["target_prompt_tokens"])
        rows.append(
            {
                "run_key": f"{job['id']}::{case_id}",
                "step": 1,
                "case_id": case_id,
                "correction_protocol_id": PROTOCOL_ID,
                "correction_job_id": job["id"],
                "correction_job_type": job.get("job_type"),
                "served_model": job["served_model"],
                "condition_id": job["condition_id"],
                "target_prompt_tokens": target,
                "model_config": {"ollama_transport": "native", "num_ctx": None},
                "timed_out": False,
                "provider_attempts": 1,
                "provider_done": True,
                "usage_source": "ollama_native_prompt_eval_count",
                "prompt_eval_count": target + 2,
                "calibrated_prompt_eval_count": target + 2,
                "prompt_count_evidence": "formal_provider",
                "final_status": "completed",
            }
        )
    lane_raw = lane_dir / "lane.jsonl"
    lane_csv = lane_dir / "lane.csv"
    _write_jsonl(lane_raw, rows)
    lane_csv.parent.mkdir(parents=True, exist_ok=True)
    lane_csv.write_text("run_key,status\nsynthetic,completed\n", encoding="utf-8")
    lane_manifest = lane_dir / "manifest.json"
    _write_json(
        lane_manifest,
        {
            "status": "completed",
            "evidence_tier": "formal_model",
            "model": job["served_model"],
            "results": [
                {
                    "status": "completed",
                    "error_count": 0,
                    "jsonl": _relative(lane_raw, root),
                    "jsonl_sha256": _hash(lane_raw),
                    "csv": _relative(lane_csv, root),
                    "csv_sha256": _hash(lane_csv),
                }
            ],
        },
    )
    raw = job_dir / "raw_runs.jsonl"
    telemetry = job_dir / "telemetry.jsonl"
    _write_jsonl(raw, rows)
    _write_jsonl(telemetry, [{"phase": "synthetic"}])
    record = {
        **job,
        "status": "completed",
        "observed_case_runs": job["expected_case_runs"],
        "duplicate_run_keys": 0,
        "lane_count": 1,
        "lanes": [
            {
                "lane_id": 0,
                "status": "completed",
                "manifest_status": "completed",
                "exit_code": 0,
                "timed_out": False,
                "manifest_path": _relative(lane_manifest, root),
                "raw_paths": [_relative(lane_raw, root)],
            }
        ],
        "raw_path": _relative(raw, root),
        "raw_sha256": _hash(raw),
        "telemetry_path": _relative(telemetry, root),
        "telemetry_sha256": _hash(telemetry),
        "telemetry_sample_count": 1,
    }
    _write_json(job_dir / "job_record.json", record)
    return record, rows


def _formal_bundle(
    root: Path,
    experiment_id: str,
    fixture: Path,
    prompt: Path,
    freeze: Path,
    jobs: list[dict[str, object]],
) -> Path:
    bundle = root / "outputs" / "experiments" / f"{experiment_id}_context_correction_v2"
    bundle.mkdir(parents=True, exist_ok=True)
    plan_path = bundle / "execution_plan.json"
    if experiment_id == "E9":
        plan: dict[str, object] = {
            "protocol_id": PROTOCOL_ID,
            "workload_revision": "r2",
            "experiment_id": "E9",
            "phase": "formal",
            "expected_case_runs": 120,
            "jobs": jobs,
        }
    else:
        plan = {
            "protocol_id": PROTOCOL_ID,
            "workload_revision": "r2",
            "experiment_id": "E14",
            "phase": "formal",
            "expected_formal_case_runs": 432,
            "expected_warmup_case_runs": 48,
            "jobs": jobs,
        }
    _write_json(plan_path, plan)
    records: list[dict[str, object]] = []
    all_rows: list[dict[str, object]] = []
    for job in jobs:
        record, rows = _job_evidence(root, bundle, experiment_id, job)
        records.append(record)
        all_rows.extend(rows)
    raw = bundle / "raw_runs.jsonl"
    _write_jsonl(raw, all_rows)

    if experiment_id == "E9":
        validity = {
            "protocol_id": PROTOCOL_ID,
            "experiment_id": "E9",
            "phase": "formal",
            "status": "pass",
            "expected_case_runs": 120,
            "observed_first_step_case_runs": 120,
            "provider_incomplete_case_runs": 0,
            "checks": {"synthetic": True},
        }
        raw_index = {
            "protocol_id": PROTOCOL_ID,
            "old_v3_policy": "excluded_invalid_diagnostic_provenance",
            "records": [],
        }
        output_names = {
            "validity_checks.json",
            "raw_run_index.json",
            "metrics.csv",
            "context_position.csv",
            "primary_chart_data.csv",
            "statistics.json",
            "analysis.md",
            "primary_chart.png",
            "primary_chart.svg",
            "figure_manifest.json",
        }
    else:
        validity = {
            "protocol_id": PROTOCOL_ID,
            "experiment_id": "E14",
            "phase": "formal",
            "status": "pass",
            "expected_formal_case_runs": 432,
            "observed_formal_case_runs": 432,
            "expected_warmup_case_runs": 48,
            "observed_warmup_case_runs": 48,
            "provider_incomplete_case_runs": 0,
            "checks": {"synthetic": True},
        }
        formal_rows = [row for row in all_rows if row["correction_job_type"] == "formal"]
        formal_raw = bundle / "formal_raw_runs.jsonl"
        _write_jsonl(formal_raw, formal_rows)
        job_records = bundle / "job_records.jsonl"
        _write_jsonl(job_records, records)
        telemetry = bundle / "telemetry.jsonl"
        _write_jsonl(
            telemetry,
            [
                {"phase": "synthetic", "job_id": record["id"]}
                for record in records
            ],
        )
        raw_index = {
            "protocol_id": PROTOCOL_ID,
            "old_v3_policy": "excluded_invalid_context_axis_provenance",
            "warmup_policy": "retained_in_raw_runs_but_excluded_from_formal_raw_index",
            "records": [{"kind": "formal_raw_log", "logical_case_runs": 432}],
        }
        output_names = {
            "validity_checks.json",
            "formal_raw_runs.jsonl",
            "job_records.jsonl",
            "telemetry.jsonl",
            "raw_run_index.json",
            "performance.csv",
            "metrics.csv",
            "statistics.json",
            "analysis.md",
            "latency_by_context_data.csv",
            "latency_by_context.png",
            "latency_by_context.svg",
            "throughput_by_concurrency_data.csv",
            "throughput_by_concurrency.png",
            "throughput_by_concurrency.svg",
            "gpu_memory_by_context_data.csv",
            "gpu_memory_by_context.png",
            "gpu_memory_by_context.svg",
            "figure_manifest.json",
        }
    _write_json(bundle / "validity_checks.json", validity)
    _write_json(bundle / "raw_run_index.json", raw_index)
    _write_json(
        bundle / "statistics.json",
        {
            "protocol_id": PROTOCOL_ID,
            "evidence_tier": "formal_context_correction_v2",
            "formal_model_only": True,
        },
    )
    if experiment_id == "E14":
        performance = bundle / "performance.csv"
        performance.write_text(
            "job_id,job_type,value\n"
            + "".join(
                f"{job['id']},{job['job_type']},1\n" for job in jobs
            ),
            encoding="utf-8",
        )
    for name in output_names:
        path = bundle / name
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith(".csv"):
            path.write_text("metric,value\nsynthetic,1\n", encoding="utf-8")
        elif name.endswith(".json"):
            _write_json(path, {"synthetic": True})
        else:
            path.write_bytes(b"synthetic\n")

    artifact_kinds: dict[str, str] = {
        "execution_plan.json": "execution_plan",
        "raw_runs.jsonl": "raw_log",
        "validity_checks.json": "semantic_validity",
        "statistics.json": "statistics",
        "job_records.jsonl": "job_log",
        "telemetry.jsonl": "resource_log",
        "formal_raw_runs.jsonl": "formal_raw_log",
    }
    artifacts = [
        _file_record(plan_path, root, kind="execution_plan"),
        _file_record(prompt, root, kind="prompt_workload_verification"),
        _file_record(raw, root, kind="raw_log"),
    ]
    for name in sorted(output_names):
        path = bundle / name
        if path == raw:
            continue
        artifacts.append(
            _file_record(path, root, kind=artifact_kinds.get(name, "artifact"))
        )
    dataset_paths = [fixture, prompt, plan_path]
    expected = 120 if experiment_id == "E9" else 432
    manifest = {
        "schema_version": "2.0",
        "experiment_id": experiment_id,
        "protocol_id": PROTOCOL_ID,
        "workload_revision": "r2",
        "status": "completed",
        "correction_of": f"invalid V3 {experiment_id} context evidence",
        "denominator_policy": "V2_only_old_V3_excluded",
        "git": {"commit": "2c53f52"},
        "configuration": {
            "protocol_id": PROTOCOL_ID,
            "workload_revision": "r2",
            "phase": "formal",
            "freeze_sha256": _hash(freeze),
            "freeze_path": _relative(freeze, root),
            "prompt_verification_sha256": _hash(prompt),
            "transport": "ollama_native",
            "dynamic_num_ctx": None,
        },
        "dataset": {
            "paths": [_relative(path, root) for path in dataset_paths],
            "sha256": _dataset_hash(dataset_paths, root),
        },
        "progress": {
            "expected_runs": expected,
            "completed_runs": expected,
            "failed_jobs": 0,
            "unresolved_cases": 0,
        },
        "jobs": [{**job, "status": "completed", "attempts": 1, "last_error": None} for job in jobs],
        "validity_checks": validity,
        "artifacts": artifacts,
    }
    manifest_path = bundle / "manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def _registry(root: Path) -> Path:
    experiments: list[dict[str, object]] = []
    for index in range(18):
        experiment_id = f"E{index}"
        experiments.append(
            {
                "id": experiment_id,
                "name": f"fixture-{experiment_id}",
                "status": "running" if experiment_id in {"E9", "E14", "E17"} else "completed",
                "required_artifacts": [f"old/{experiment_id}/manifest.json"],
                "evidence": [f"old/{experiment_id}/evidence.json"],
                "error": "old invalid context evidence" if experiment_id in {"E9", "E14"} else "",
            }
        )
    registry = root / "experiments" / "registry.json"
    _write_json(registry, {"schema_version": "1.0", "experiments": experiments})
    return registry


def _repository(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "repo"
    e9_fixture, e14_fixture, e9_cases, e14_cases = _fixtures(root)
    prompt = _prompt_proof(root, e9_fixture, e14_fixture, e9_cases, e14_cases)
    smoke_e9 = _smoke(root, "E9", prompt, e9_fixture)
    smoke_e14 = _smoke(root, "E14", prompt, e14_fixture)
    freeze, expected_freeze_paths = _freeze(root, prompt, smoke_e9, smoke_e14)
    e9_manifest = _formal_bundle(
        root, "E9", e9_fixture, prompt, freeze, _e9_jobs(e9_cases)
    )
    e14_manifest = _formal_bundle(
        root, "E14", e14_fixture, prompt, freeze, _e14_jobs(e14_cases)
    )
    registry = _registry(root)
    audit_json = root / "agent" / "audits" / "context_correction_v2.json"
    audit_md = root / "agent" / "audits" / "context_correction_v2.md"
    return {
        "root": root,
        "freeze": freeze,
        "expected_freeze_paths": expected_freeze_paths,
        "e9_manifest": e9_manifest,
        "e14_manifest": e14_manifest,
        "registry": registry,
        "audit_json": audit_json,
        "audit_md": audit_md,
    }


def _run_audit(repo: dict[str, object]) -> dict[str, object]:
    return audit_context_correction_v2(
        repository_root=repo["root"],
        freeze_path=repo["freeze"],
        e9_manifest_path=repo["e9_manifest"],
        e14_manifest_path=repo["e14_manifest"],
        output_json=repo["audit_json"],
        output_markdown=repo["audit_md"],
        expected_freeze_paths=repo["expected_freeze_paths"],
    )


def test_independent_audit_verifies_full_denominators_and_dynamic_r2_paths(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    report = _run_audit(repo)
    assert report["status"] == "pass"
    assert report["failures"] == []
    assert report["experiments"]["E9"]["observed_case_runs"] == 120
    assert report["experiments"]["E14"]["observed_case_runs"] == 432
    assert report["experiments"]["E14"]["warmup_case_runs"] == 48
    assert report["experiments"]["E14"]["warmup_excluded"] is True
    assert report["prompt_proof"]["observation_count"] == 100
    assert report["inputs"]["prompt_verification"]["path"].endswith(
        "prompt_verification_r2.json"
    )
    assert Path(repo["audit_json"]).is_file()
    assert Path(repo["audit_md"]).is_file()
    derived = audit_context_correction_v2(
        repository_root=repo["root"],
        e9_manifest_path=repo["e9_manifest"],
        e14_manifest_path=repo["e14_manifest"],
        output_json=None,
        output_markdown=None,
        expected_freeze_paths=repo["expected_freeze_paths"],
    )
    assert derived["status"] == "pass"
    assert derived["evidence_fingerprint"] == report["evidence_fingerprint"]


def test_job_hash_tamper_fails_audit_and_registration_preserves_registry_bytes(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    passing = _run_audit(repo)
    assert passing["status"] == "pass"
    registry = Path(repo["registry"])
    before = registry.read_bytes()
    job_raw = next(
        (Path(repo["root"]) / "outputs" / "experiments" / "E9_context_correction_v2" / "work").glob(
            "*/raw_runs.jsonl"
        )
    )
    job_raw.write_text(job_raw.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    with pytest.raises(ContextCorrectionRegistrationError, match="fresh context correction audit failed"):
        register_context_correction(
            registry_path=registry,
            repository_root=repo["root"],
            audit_path=repo["audit_json"],
            apply=True,
            expected_freeze_paths=repo["expected_freeze_paths"],
        )
    assert registry.read_bytes() == before


def test_registrar_updates_e9_e14_in_one_atomic_payload_and_is_idempotent(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    assert _run_audit(repo)["status"] == "pass"
    registry = Path(repo["registry"])
    before = registry.read_bytes()
    dry_run = register_context_correction(
        registry_path=registry,
        repository_root=repo["root"],
        audit_path=repo["audit_json"],
        expected_freeze_paths=repo["expected_freeze_paths"],
    )
    assert dry_run["registry_written"] is False
    assert registry.read_bytes() == before

    applied = register_context_correction(
        registry_path=registry,
        repository_root=repo["root"],
        audit_path=repo["audit_json"],
        apply=True,
        expected_freeze_paths=repo["expected_freeze_paths"],
    )
    assert applied["registry_written"] is True
    stored = json.loads(registry.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in stored["experiments"]}
    for experiment_id, expected in (("E9", 120), ("E14", 432)):
        item = by_id[experiment_id]
        assert item["status"] == "completed"
        assert isinstance(item["primary_manifest"], str)
        assert item["primary_manifest"].endswith("/manifest.json")
        assert item["primary_manifest_record"]["protocol_id"] == PROTOCOL_ID
        assert item["primary_manifest_record"]["path"] == item["primary_manifest"]
        assert item["active_evidence"] == item["evidence"]
        assert set(item["required_artifacts"]).issubset(item["active_evidence"])
        assert not any(
            value.endswith("context_correction_v2.json")
            or value.endswith("context_correction_v2.md")
            or value.endswith("freeze.json")
            for value in item["required_artifacts"]
        )
        primary_path = Path(repo["root"]) / item["primary_manifest"]
        primary_payload = json.loads(primary_path.read_text(encoding="utf-8"))
        declared = {artifact["path"] for artifact in primary_payload["artifacts"]}
        assert set(item["required_artifacts"][1:]).issubset(declared)
        assert item["completion_gate"]["formal_expected_case_runs"] == expected
        assert item["completion_gate"]["all_or_nothing_pair"] == ["E9", "E14"]
        assert item["completion_gate"]["old_v3_excluded"] is True
        assert item["superseded_evidence"][0]["required_artifacts"] == [
            f"old/{experiment_id}/manifest.json"
        ]
        assert item["superseded_evidence"][0]["excluded_from_active_denominators"] is True

    completed_bytes = registry.read_bytes()
    no_op = register_context_correction(
        registry_path=registry,
        repository_root=repo["root"],
        audit_path=repo["audit_json"],
        apply=True,
        expected_freeze_paths=repo["expected_freeze_paths"],
    )
    assert no_op["no_op"] is True
    assert no_op["registry_written"] is False
    assert registry.read_bytes() == completed_bytes


def test_hand_edited_pass_audit_is_rejected_without_registry_mutation(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    assert _run_audit(repo)["status"] == "pass"
    audit_path = Path(repo["audit_json"])
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["experiments"]["E14"]["observed_case_runs"] = 431
    _write_json(audit_path, payload)
    registry = Path(repo["registry"])
    before = registry.read_bytes()
    with pytest.raises(ContextCorrectionRegistrationError, match="denominator gate"):
        register_context_correction(
            registry_path=registry,
            repository_root=repo["root"],
            audit_path=audit_path,
            apply=True,
            expected_freeze_paths=repo["expected_freeze_paths"],
        )
    assert registry.read_bytes() == before


def test_warmup_in_formal_raw_is_detected(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    formal = Path(repo["root"]) / "outputs" / "experiments" / "E14_context_correction_v2" / "formal_raw_runs.jsonl"
    aggregate = Path(repo["root"]) / "outputs" / "experiments" / "E14_context_correction_v2" / "raw_runs.jsonl"
    warmup = next(
        line
        for line in aggregate.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["correction_job_type"] == "warmup"
    )
    formal.write_text(formal.read_text(encoding="utf-8") + warmup + "\n", encoding="utf-8")
    manifest_path = Path(repo["e14_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for artifact in manifest["artifacts"]:
        if Path(artifact["path"]).name == "formal_raw_runs.jsonl":
            artifact["bytes"] = formal.stat().st_size
            artifact["sha256"] = _hash(formal)
    _write_json(manifest_path, manifest)
    report = _run_audit(repo)
    assert report["status"] == "fail"
    codes = {item["code"] for item in report["failures"]}
    assert "e14_warmup_exclusion" in codes
    assert "e14_warmup_leakage" in codes


def test_unexpected_atomic_save_failure_restores_exact_registry_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repository(tmp_path)
    assert _run_audit(repo)["status"] == "pass"
    registry = Path(repo["registry"])
    before = registry.read_bytes()

    def broken_save(_payload: object, path: str | Path) -> None:
        Path(path).write_bytes(b"unexpected partial replacement\n")
        raise OSError("simulated post-replacement failure")

    monkeypatch.setattr(registration_module, "save_registry", broken_save)
    with pytest.raises(OSError, match="simulated post-replacement failure"):
        registration_module.register_context_correction(
            registry_path=registry,
            repository_root=repo["root"],
            audit_path=repo["audit_json"],
            apply=True,
            expected_freeze_paths=repo["expected_freeze_paths"],
        )
    assert registry.read_bytes() == before
