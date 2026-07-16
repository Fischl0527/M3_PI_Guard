"""Independently audit the corrected E9/E14 context experiments.

The experiment runners are intentionally not trusted as the final admission
gate.  This script reconstructs the evidence graph from the frozen protocol,
the prompt-token proof, the formal manifests, every durable job record and the
declared artifact ledgers.  Historical V3 E9/E14 evidence is retained as
diagnostic provenance but is forbidden from the corrected denominators.

The JSON report contains a deterministic ``evidence_fingerprint``.  The paired
registrar re-runs this audit and accepts a stored report only when the fresh
fingerprint is identical.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.context_correction_runtime import EXPECTED_FREEZE_PATHS  # noqa: E402


PROTOCOL_ID = "CONTEXT_CORRECTION_V2"
AUDIT_TYPE = "context_correction_v2_independent_completion_audit"
DEFAULT_FREEZE = ROOT / "protocols" / "context_correction_v2" / "freeze_r3.json"
DEFAULT_E9_MANIFEST = (
    ROOT / "outputs" / "experiments" / "E9_context_correction_v2_r3" / "manifest.json"
)
DEFAULT_E14_MANIFEST = (
    ROOT / "outputs" / "experiments" / "E14_context_correction_v2_r3" / "manifest.json"
)
DEFAULT_JSON = ROOT / "agent" / "audits" / "context_correction_v2.json"
DEFAULT_MARKDOWN = ROOT / "agent" / "audits" / "context_correction_v2.md"

TARGETS = (2048, 4096, 8192, 16384)
MODEL_BY_TARGET = {
    2048: "m3-qwen3-4b-ctx4k:latest",
    4096: "m3-qwen3-4b-ctx8k:latest",
    8192: "m3-qwen3-4b-ctx16k:latest",
    16384: "m3-qwen3-4b-ctx32k:latest",
}
ALIAS_PREFIX_BY_TARGET = {
    2048: "0ce262040abb",
    4096: "81f2e7df722a",
    8192: "b7c705adc68a",
    16384: "ef6929a22b37",
}
CONTEXT_BY_TARGET = {2048: 4096, 4096: 8192, 8192: 16384, 16384: 32768}

EXPECTED_ARTIFACT_NAMES = {
    "E9": {
        "execution_plan.json",
        "prompt_verification.json",
        "raw_runs.jsonl",
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
    },
    "E14": {
        "execution_plan.json",
        "prompt_verification.json",
        "raw_runs.jsonl",
        "job_records.jsonl",
        "telemetry.jsonl",
        "validity_checks.json",
        "formal_raw_runs.jsonl",
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
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class _Audit:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.failures: list[dict[str, str]] = []
        self.integrity: dict[str, dict[str, Any]] = {}
        self.counters: Counter[str] = Counter()

    def fail(self, code: str, detail: str) -> None:
        self.failures.append({"code": code, "detail": detail})

    def require(self, condition: Any, code: str, detail: str) -> bool:
        if not condition:
            self.fail(code, detail)
            return False
        return True

    def path(
        self,
        value: str | Path,
        *,
        label: str,
        require_file: bool = True,
        allow_empty: bool = False,
    ) -> Path | None:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        try:
            resolved = candidate.resolve()
            resolved.relative_to(self.root)
        except (OSError, ValueError) as exc:
            self.fail("path_escape", f"{label}: {value}: {exc}")
            return None
        if require_file:
            if not resolved.is_file():
                self.fail("missing_file", f"{label}: {resolved}")
                return None
            if not allow_empty and resolved.stat().st_size <= 0:
                self.fail("empty_file", f"{label}: {resolved}")
                return None
        return resolved

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def record(
        self,
        path: Path | None,
        *,
        kind: str,
        source: str,
        declared_sha256: Any = None,
        declared_bytes: Any = None,
        allow_empty: bool = False,
    ) -> dict[str, Any] | None:
        if path is None:
            return None
        if not path.is_file():
            self.fail("missing_file", f"{source}: {path}")
            return None
        size = path.stat().st_size
        digest = _sha256(path)
        relative = self.relative(path)
        if not allow_empty and size <= 0:
            self.fail("empty_file", f"{source}: {relative}")
        if declared_sha256 is not None and str(declared_sha256) != digest:
            self.fail(
                "sha256_mismatch",
                f"{source}: {relative}: declared={declared_sha256}, observed={digest}",
            )
        if declared_bytes is not None:
            try:
                expected_size = int(declared_bytes)
            except (TypeError, ValueError):
                expected_size = -1
            if expected_size != size:
                self.fail(
                    "byte_count_mismatch",
                    f"{source}: {relative}: declared={declared_bytes}, observed={size}",
                )
        record = {
            "path": relative,
            "kind": kind,
            "bytes": size,
            "sha256": digest,
            "sources": [source],
        }
        previous = self.integrity.get(relative)
        if previous:
            previous["sources"] = sorted(set(previous["sources"] + [source]))
            if previous["bytes"] != size or previous["sha256"] != digest:
                self.fail("evidence_changed_during_audit", relative)
            return previous
        self.integrity[relative] = record
        self.counters["files_hashed"] += 1
        self.counters["bytes_hashed"] += size
        return record


def _load_json(audit: _Audit, path: Path | None, *, label: str) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        audit.fail("invalid_json", f"{label}: {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        audit.fail("invalid_json_type", f"{label}: expected object")
        return {}
    return value


def _read_jsonl(audit: _Audit, path: Path | None, *, label: str) -> list[dict[str, Any]]:
    if path is None:
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("row is not an object")
                rows.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        audit.fail("invalid_jsonl", f"{label}: {path}: {exc}")
    return rows


def _row_counter(rows: Iterable[Mapping[str, Any]]) -> Counter[str]:
    return Counter(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in rows
    )


def _dataset_hash(audit: _Audit, paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted((item.resolve() for item in paths), key=lambda item: str(item)):
        digest.update(audit.relative(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _validate_freeze(
    audit: _Audit,
    freeze_path: Path,
    *,
    expected_freeze_paths: Sequence[str],
) -> tuple[dict[str, Any], str, Path | None]:
    freeze = audit.path(freeze_path, label="freeze")
    record = audit.record(freeze, kind="freeze", source="freeze_manifest")
    payload = _load_json(audit, freeze, label="freeze")
    audit.require(payload.get("protocol_id") == PROTOCOL_ID, "freeze_protocol", "wrong protocol_id")
    audit.require(payload.get("workload_revision") == "r2", "freeze_workload_revision", "workload_revision != r2")
    audit.require(payload.get("status") == "pass", "freeze_status", "freeze status is not pass")
    audit.require(payload.get("freeze_complete") is True, "freeze_incomplete", "freeze_complete is not true")
    files = payload.get("files")
    if not isinstance(files, list):
        audit.fail("freeze_files", "freeze files is not a list")
        files = []
    declared_paths = [
        str(item.get("path", "")).replace("\\", "/")
        for item in files
        if isinstance(item, Mapping)
    ]
    audit.require(
        len(declared_paths) == len(set(declared_paths)),
        "freeze_duplicate_paths",
        "freeze file paths are not unique",
    )
    audit.require(
        set(declared_paths) == set(expected_freeze_paths),
        "freeze_allowlist",
        f"declared={len(set(declared_paths))}, expected={len(set(expected_freeze_paths))}",
    )
    for index, item in enumerate(files):
        if not isinstance(item, Mapping):
            audit.fail("freeze_file_entry", f"files[{index}] is not an object")
            continue
        path = audit.path(item.get("path", ""), label=f"freeze files[{index}]")
        audit.record(
            path,
            kind="frozen_file",
            source=f"freeze.files[{index}]",
            declared_sha256=item.get("sha256"),
            declared_bytes=item.get("bytes"),
        )

    prompt = payload.get("prompt_verification")
    if not isinstance(prompt, Mapping):
        audit.fail("freeze_prompt_record", "prompt_verification record missing")
        prompt = {}
    audit.require(prompt.get("status") == "pass", "freeze_prompt_status", "prompt proof not pass")
    audit.require(prompt.get("workload_revision") == "r2", "freeze_prompt_revision", "prompt proof revision != r2")
    audit.require(int(prompt.get("case_count", -1)) == 100, "freeze_prompt_count", "case_count != 100")
    prompt_candidates: list[str] = []
    if isinstance(prompt.get("path"), str) and str(prompt.get("path")).strip():
        prompt_candidates.append(str(prompt["path"]))
    prompt_candidates.extend(
        value
        for value in declared_paths
        if Path(value).name.startswith("prompt_verification")
        and Path(value).suffix.lower() == ".json"
    )
    unique_prompt_candidates: dict[str, str] = {}
    for value in prompt_candidates:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = audit.root / candidate
        try:
            key = str(candidate.resolve())
        except OSError:
            key = str(candidate)
        unique_prompt_candidates.setdefault(key, value)
    prompt_candidates = list(unique_prompt_candidates.values())
    audit.require(
        len(prompt_candidates) == 1,
        "freeze_prompt_path",
        f"expected one frozen prompt proof, found {prompt_candidates}",
    )
    prompt_path = audit.path(
        prompt_candidates[0] if len(prompt_candidates) == 1 else "missing_prompt_proof",
        label="frozen prompt verification",
    )
    if prompt_path is not None:
        audit.require(
            prompt.get("sha256") == _sha256(prompt_path),
            "freeze_prompt_sha256",
            "prompt proof hash differs from freeze record",
        )

    smoke = payload.get("smoke_evidence")
    if not isinstance(smoke, Mapping):
        audit.fail("freeze_smoke_evidence", "smoke_evidence missing")
        smoke = {}
    for experiment_id in ("E9", "E14"):
        item = smoke.get(experiment_id)
        if not isinstance(item, Mapping):
            audit.fail("freeze_smoke_record", f"{experiment_id} smoke record missing")
            continue
        path = audit.path(item.get("manifest_path", ""), label=f"{experiment_id} smoke manifest")
        audit.record(
            path,
            kind="smoke_manifest",
            source=f"freeze.smoke_evidence.{experiment_id}",
            declared_sha256=item.get("sha256"),
            declared_bytes=item.get("bytes"),
        )
        manifest = _load_json(audit, path, label=f"{experiment_id} smoke manifest")
        validity = manifest.get("validity_checks") or {}
        progress = manifest.get("progress") or {}
        audit.require(manifest.get("experiment_id") == experiment_id, "smoke_experiment_id", experiment_id)
        audit.require(manifest.get("status") == "completed", "smoke_status", experiment_id)
        audit.require(manifest.get("protocol_id") == PROTOCOL_ID, "smoke_protocol", experiment_id)
        audit.require(manifest.get("workload_revision") == "r2", "smoke_workload_revision", experiment_id)
        audit.require((manifest.get("configuration") or {}).get("phase") == "smoke", "smoke_phase", experiment_id)
        audit.require(validity.get("status") == "pass", "smoke_validity", experiment_id)
        smoke_checks = validity.get("checks") or {}
        audit.require(
            isinstance(smoke_checks, Mapping)
            and bool(smoke_checks)
            and all(value is True for value in smoke_checks.values()),
            "smoke_validity_checks",
            experiment_id,
        )
        audit.require(progress.get("expected_runs") == 48 and progress.get("completed_runs") == 48, "smoke_denominator", experiment_id)
        audit.require(not progress.get("failed_jobs"), "smoke_failed_jobs", experiment_id)
        configuration = manifest.get("configuration") or {}
        audit.require(
            prompt_path is not None
            and configuration.get("prompt_verification_sha256")
            == _sha256(prompt_path),
            "smoke_prompt_sha256",
            experiment_id,
        )
        jobs = manifest.get("jobs") or []
        audit.require(
            isinstance(jobs, list)
            and len(jobs) == 8
            and all(
                isinstance(job, Mapping) and job.get("status") == "completed"
                for job in jobs
            ),
            "smoke_jobs",
            experiment_id,
        )
        smoke_artifacts = manifest.get("artifacts") or []
        audit.require(
            isinstance(smoke_artifacts, list) and bool(smoke_artifacts),
            "smoke_artifacts",
            experiment_id,
        )
        smoke_prompt_paths: list[Path] = []
        for artifact_index, artifact in enumerate(smoke_artifacts):
            if not isinstance(artifact, Mapping):
                audit.fail(
                    "smoke_artifact_entry",
                    f"{experiment_id}:{artifact_index}",
                )
                continue
            artifact_path = audit.path(
                artifact.get("path", ""),
                label=f"{experiment_id} smoke artifact[{artifact_index}]",
            )
            audit.record(
                artifact_path,
                kind=str(artifact.get("kind", "smoke_artifact")),
                source=f"freeze.smoke.{experiment_id}.artifacts[{artifact_index}]",
                declared_sha256=artifact.get("sha256"),
                declared_bytes=artifact.get("bytes"),
            )
            if artifact.get("kind") == "prompt_workload_verification" and artifact_path:
                smoke_prompt_paths.append(artifact_path)
        audit.require(
            prompt_path is not None
            and len(smoke_prompt_paths) == 1
            and smoke_prompt_paths[0].resolve() == prompt_path.resolve(),
            "smoke_prompt_artifact",
            experiment_id,
        )
        dataset_paths: list[Path] = []
        for dataset_index, value in enumerate(
            (manifest.get("dataset") or {}).get("paths") or []
        ):
            dataset_path = audit.path(
                value,
                label=f"{experiment_id} smoke dataset[{dataset_index}]",
            )
            if dataset_path:
                dataset_paths.append(dataset_path)
        audit.require(
            bool(dataset_paths)
            and (manifest.get("dataset") or {}).get("sha256")
            == _dataset_hash(audit, dataset_paths),
            "smoke_dataset_sha256",
            experiment_id,
        )

    profiles = payload.get("model_profiles")
    if not isinstance(profiles, Mapping):
        audit.fail("freeze_model_profiles", "model_profiles missing")
        profiles = {}
    for target in TARGETS:
        item = profiles.get(str(target)) or {}
        audit.require(item.get("served_model") == MODEL_BY_TARGET[target], "freeze_model_alias", str(target))
        audit.require(
            str(item.get("alias_id", "")).lower().startswith(ALIAS_PREFIX_BY_TARGET[target]),
            "freeze_model_id",
            str(target),
        )
        audit.require(
            item.get("effective_context_window_tokens") == CONTEXT_BY_TARGET[target],
            "freeze_model_context",
            str(target),
        )
    test_gate = payload.get("test_gate") or {}
    audit.require(test_gate.get("status") == "pass", "freeze_test_gate", "test status is not pass")
    audit.require(int(test_gate.get("passed", 0)) >= 1, "freeze_test_count", "no passing tests recorded")
    return payload, str((record or {}).get("sha256", "")), prompt_path


def _validate_prompt_proof(
    audit: _Audit,
    prompt_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Path]]:
    path = audit.path(prompt_path, label="prompt verification")
    audit.record(path, kind="prompt_workload_verification", source="prompt_proof")
    payload = _load_json(audit, path, label="prompt verification")
    audit.require(payload.get("protocol_id") == PROTOCOL_ID, "prompt_protocol", "wrong protocol")
    audit.require(payload.get("workload_revision") == "r2", "prompt_workload_revision", "workload_revision != r2")
    audit.require(payload.get("status") == "pass", "prompt_status", "status is not pass")
    checks = payload.get("checks")
    audit.require(
        isinstance(checks, Mapping) and bool(checks) and all(value is True for value in checks.values()),
        "prompt_checks",
        "not every prompt-proof check is true",
    )
    audit.require(payload.get("measurement_role") == "frozen_first_turn_workload_proof_not_model_outcome", "prompt_role", "wrong measurement role")
    audit.require(payload.get("num_predict") == 1, "prompt_num_predict", "num_predict != 1")
    audit.require(float(payload.get("temperature", -1)) == 0.0, "prompt_temperature", "temperature != 0")
    audit.require(int(payload.get("seed", -1)) == 419, "prompt_seed", "seed != 419")
    audit.require(bool(str(payload.get("ollama_version", "")).strip()), "prompt_ollama_version", "Ollama version missing")
    model_evidence = payload.get("model_evidence")
    if not isinstance(model_evidence, Mapping):
        audit.fail("prompt_model_evidence", "model_evidence missing")
        model_evidence = {}
    for target in TARGETS:
        item = model_evidence.get(str(target)) or {}
        audit.require(item.get("served_model") == MODEL_BY_TARGET[target], "prompt_model_evidence_alias", str(target))
        audit.require(
            str(item.get("installed_alias_id", "")).lower().startswith(
                ALIAS_PREFIX_BY_TARGET[target]
            ),
            "prompt_model_evidence_id",
            str(target),
        )
        audit.require(
            item.get("expected_effective_context_window_tokens")
            == CONTEXT_BY_TARGET[target],
            "prompt_model_evidence_context",
            str(target),
        )
        resident = (item.get("resident_snapshot") or {}).get("models") or []
        audit.require(
            any(
                isinstance(model, Mapping)
                and model.get("name") == MODEL_BY_TARGET[target]
                and model.get("context_length") == CONTEXT_BY_TARGET[target]
                for model in resident
            ),
            "prompt_resident_context",
            str(target),
        )

    fixture_paths: dict[str, Path] = {}
    fixture_ids: dict[str, set[str]] = {}
    fixture_targets: dict[str, int] = {}
    fixture_files = payload.get("fixture_files")
    if not isinstance(fixture_files, Mapping):
        audit.fail("prompt_fixture_files", "fixture_files missing")
        fixture_files = {}
    for experiment_id, expected_count in (("E9", 60), ("E14", 40)):
        item = fixture_files.get(experiment_id) or {}
        fixture = audit.path(item.get("path", ""), label=f"{experiment_id} fixture")
        fixture_paths[experiment_id] = fixture or audit.root / "missing"
        audit.record(
            fixture,
            kind="case_fixture",
            source=f"prompt.fixture_files.{experiment_id}",
            declared_sha256=item.get("sha256"),
        )
        rows = _read_jsonl(audit, fixture, label=f"{experiment_id} fixture")
        ids = [str(row.get("case_id", "")) for row in rows]
        audit.require(len(rows) == expected_count, "fixture_case_count", f"{experiment_id}: {len(rows)}")
        audit.require(len(ids) == len(set(ids)) and all(ids), "fixture_case_ids", experiment_id)
        fixture_ids[experiment_id] = set(ids)
        for row in rows:
            try:
                fixture_targets[str(row["case_id"])] = int(
                    (row.get("attack_dimensions") or {})["target_prompt_tokens"]
                )
            except (KeyError, TypeError, ValueError):
                audit.fail("fixture_target", f"{experiment_id}:{row.get('case_id')}")

    observations = payload.get("observations")
    if not isinstance(observations, list):
        audit.fail("prompt_observations", "observations is not a list")
        observations = []
    observation_ids = [str(item.get("case_id", "")) for item in observations if isinstance(item, Mapping)]
    expected_ids = fixture_ids.get("E9", set()) | fixture_ids.get("E14", set())
    audit.require(len(observations) == 100, "prompt_observation_count", str(len(observations)))
    audit.require(len(observation_ids) == len(set(observation_ids)), "prompt_duplicate_cases", "duplicate case IDs")
    audit.require(set(observation_ids) == expected_ids, "prompt_fixture_coverage", "observations do not exactly cover both fixtures")
    mapping: dict[str, dict[str, Any]] = {}
    values_by_target: dict[int, list[int]] = {target: [] for target in TARGETS}
    for index, raw in enumerate(observations):
        if not isinstance(raw, Mapping):
            audit.fail("prompt_observation_type", f"observations[{index}]")
            continue
        row = dict(raw)
        case_id = str(row.get("case_id", ""))
        mapping[case_id] = row
        try:
            target = int(row.get("target_prompt_tokens"))
            observed = int(row.get("observed_prompt_eval_count"))
        except (TypeError, ValueError):
            audit.fail("prompt_observation_count", case_id)
            continue
        expected_experiment = "E9" if case_id in fixture_ids.get("E9", set()) else "E14"
        audit.require(row.get("experiment_id") == expected_experiment, "prompt_experiment_id", case_id)
        audit.require(target == fixture_targets.get(case_id), "prompt_target_fixture_mismatch", case_id)
        audit.require(target in TARGETS, "prompt_target", case_id)
        audit.require(row.get("usage_source") == "ollama_native_prompt_eval_count", "prompt_usage_source", case_id)
        audit.require(row.get("provider_done") is True, "prompt_provider_done", case_id)
        audit.require(row.get("within_tolerance") is True, "prompt_tolerance_flag", case_id)
        audit.require(abs(observed - target) / target <= 0.01, "prompt_tolerance", case_id)
        audit.require(row.get("served_model") == MODEL_BY_TARGET.get(target), "prompt_model", case_id)
        audit.require(row.get("effective_context_window_tokens") == CONTEXT_BY_TARGET.get(target), "prompt_context", case_id)
        audit.require(int(row.get("provider_attempts", -1)) == 1, "prompt_provider_attempts", case_id)
        audit.require(int(row.get("verification_request_attempts", -1)) == 1, "prompt_request_attempts", case_id)
        audit.require(len(str(row.get("fixture_row_sha256", ""))) == 64, "prompt_fixture_row_hash", case_id)
        audit.require(len(str(row.get("rendered_messages_sha256", ""))) == 64, "prompt_rendered_hash", case_id)
        if target in values_by_target:
            values_by_target[target].append(observed)
    observed_medians = {
        str(target): statistics.median(values_by_target[target])
        if values_by_target[target]
        else None
        for target in TARGETS
    }
    audit.require(payload.get("target_medians") == observed_medians, "prompt_target_medians", "stored medians differ")
    medians = [observed_medians[str(target)] for target in TARGETS]
    audit.require(
        all(left is not None and right is not None and left < right for left, right in zip(medians, medians[1:])),
        "prompt_monotonicity",
        "target medians are collapsed",
    )
    return payload, mapping, fixture_paths


def _provider_incomplete_safe(row: Mapping[str, Any]) -> bool:
    if row.get("provider_done") is not False:
        return True
    parsed = row.get("parsed_tool_call") or {}
    arguments = parsed.get("arguments") if isinstance(parsed, Mapping) else {}
    return bool(
        row.get("parse_ok") is False
        and "provider_incomplete_response" in str(row.get("parse_error", ""))
        and row.get("final_status") == "error"
        and row.get("guard_decision") == "error"
        and row.get("tool_execution_attempted") is False
        and float(row.get("guard_latency_ms") or 0.0) == 0.0
        and isinstance(parsed, Mapping)
        and parsed.get("tool") == "final"
        and isinstance(arguments, Mapping)
        and arguments.get("answer") == "PROVIDER_INCOMPLETE_RESPONSE_NOT_EXECUTED"
        and row.get("observation") == "PROVIDER_INCOMPLETE_RESPONSE_NOT_EXECUTED"
    )


def _validate_lane_manifest(
    audit: _Audit,
    lane: Mapping[str, Any],
    *,
    experiment_id: str,
    job_id: str,
) -> list[dict[str, Any]]:
    prefix = f"{experiment_id}:{job_id}:lane{lane.get('lane_id')}"
    audit.require(lane.get("status") == "completed", "lane_status", prefix)
    audit.require(lane.get("manifest_status") == "completed", "lane_manifest_status", prefix)
    audit.require(lane.get("exit_code") == 0, "lane_exit_code", prefix)
    audit.require(lane.get("timed_out") is False, "lane_timeout", prefix)
    manifest_path = audit.path(lane.get("manifest_path", ""), label=f"{prefix} manifest")
    audit.record(manifest_path, kind="lane_manifest", source=f"job.{prefix}.manifest")
    manifest = _load_json(audit, manifest_path, label=f"{prefix} manifest")
    audit.require(manifest.get("status") == "completed", "lane_matrix_status", prefix)
    audit.require(manifest.get("evidence_tier") != "formal_stub", "lane_stub_forbidden", prefix)
    audit.require(manifest.get("model") in set(MODEL_BY_TARGET.values()), "lane_model", prefix)
    results = manifest.get("results")
    if isinstance(results, Mapping):
        results = [results]
    if not isinstance(results, list) or not results:
        audit.fail("lane_results", prefix)
        return []
    rows: list[dict[str, Any]] = []
    declared_raw: set[str] = set()
    for index, result in enumerate(results):
        if not isinstance(result, Mapping):
            audit.fail("lane_result_type", f"{prefix}:{index}")
            continue
        audit.require(result.get("status") == "completed", "lane_result_status", f"{prefix}:{index}")
        audit.require(int(result.get("error_count", -1)) == 0, "lane_result_errors", f"{prefix}:{index}")
        for extension, kind in (("jsonl", "lane_raw_log"), ("csv", "lane_csv_log")):
            output = audit.path(result.get(extension, ""), label=f"{prefix} {extension}")
            audit.record(
                output,
                kind=kind,
                source=f"lane_manifest.{prefix}.results[{index}]",
                declared_sha256=result.get(f"{extension}_sha256"),
            )
            if extension == "jsonl" and output is not None:
                declared_raw.add(str(output))
                rows.extend(_read_jsonl(audit, output, label=f"{prefix} result raw"))
    raw_paths: set[str] = set()
    for value in lane.get("raw_paths") or []:
        path = audit.path(value, label=f"{prefix} raw_paths", allow_empty=False)
        if path is not None:
            raw_paths.add(str(path))
    audit.require(raw_paths == declared_raw, "lane_raw_path_set", prefix)
    return rows


def _validate_jobs(
    audit: _Audit,
    *,
    experiment_id: str,
    bundle_dir: Path,
    plan_jobs: Sequence[Mapping[str, Any]],
    manifest_jobs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest_by_id = {
        str(item.get("id", "")): item for item in manifest_jobs if isinstance(item, Mapping)
    }
    plan_ids = [str(item.get("id", "")) for item in plan_jobs]
    audit.require(len(plan_ids) == len(set(plan_ids)) and all(plan_ids), "plan_job_ids", experiment_id)
    audit.require(set(manifest_by_id) == set(plan_ids), "manifest_plan_jobs", experiment_id)
    all_rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for plan_job in plan_jobs:
        job_id = str(plan_job.get("id", ""))
        manifest_job = manifest_by_id.get(job_id, {})
        audit.require(manifest_job.get("status") == "completed", "manifest_job_status", f"{experiment_id}:{job_id}")
        audit.require(not manifest_job.get("last_error"), "manifest_job_error", f"{experiment_id}:{job_id}")
        for key, expected in plan_job.items():
            audit.require(manifest_job.get(key) == expected, "manifest_job_drift", f"{experiment_id}:{job_id}:{key}")
        record_path = audit.path(
            bundle_dir / "work" / job_id / "job_record.json",
            label=f"{experiment_id}:{job_id} job record",
        )
        audit.record(record_path, kind="job_record", source=f"{experiment_id}.job.{job_id}")
        record = _load_json(audit, record_path, label=f"{experiment_id}:{job_id} job record")
        records.append(record)
        audit.require(record.get("id") == job_id, "job_record_id", f"{experiment_id}:{job_id}")
        audit.require(record.get("status") == "completed", "job_record_status", f"{experiment_id}:{job_id}")
        expected_runs = int(plan_job.get("expected_case_runs", -1))
        audit.require(record.get("observed_case_runs") == expected_runs, "job_case_runs", f"{experiment_id}:{job_id}")
        audit.require(record.get("duplicate_run_keys") == 0, "job_duplicate_runs", f"{experiment_id}:{job_id}")
        for key in (
            "protocol_id",
            "condition_id",
            "served_model",
            "target_prompt_tokens",
            "effective_context_window_tokens",
            "expected_case_runs",
            "case_ids",
            "workload_cohort",
            "concurrency",
            "outer_replicate_id",
        ):
            audit.require(record.get(key) == plan_job.get(key), "job_plan_drift", f"{experiment_id}:{job_id}:{key}")
        if "job_type" in plan_job:
            audit.require(record.get("job_type") == plan_job.get("job_type"), "job_type_drift", f"{experiment_id}:{job_id}")
        raw_path = audit.path(record.get("raw_path", ""), label=f"{experiment_id}:{job_id} raw")
        audit.record(
            raw_path,
            kind="job_raw_log",
            source=f"{experiment_id}.job.{job_id}",
            declared_sha256=record.get("raw_sha256"),
        )
        job_rows = _read_jsonl(audit, raw_path, label=f"{experiment_id}:{job_id} raw")
        all_rows.extend(job_rows)
        first = [row for row in job_rows if int(row.get("step") or 0) == 1]
        audit.require(len(first) == expected_runs, "job_first_step_count", f"{experiment_id}:{job_id}")
        audit.require({str(row.get("case_id")) for row in first} == {str(value) for value in plan_job.get("case_ids", [])}, "job_case_selector", f"{experiment_id}:{job_id}")
        telemetry_path = audit.path(
            record.get("telemetry_path", ""),
            label=f"{experiment_id}:{job_id} telemetry",
            allow_empty=True,
        )
        audit.record(
            telemetry_path,
            kind="job_telemetry",
            source=f"{experiment_id}.job.{job_id}",
            declared_sha256=record.get("telemetry_sha256"),
            allow_empty=True,
        )
        telemetry_rows = _read_jsonl(
            audit, telemetry_path, label=f"{experiment_id}:{job_id} telemetry"
        )
        audit.require(
            record.get("telemetry_sample_count") == len(telemetry_rows),
            "job_telemetry_sample_count",
            f"{experiment_id}:{job_id}",
        )
        lanes = record.get("lanes")
        if not isinstance(lanes, list) or not lanes:
            audit.fail("job_lanes", f"{experiment_id}:{job_id}")
            lanes = []
        audit.require(record.get("lane_count") == len(lanes), "job_lane_count", f"{experiment_id}:{job_id}")
        lane_rows: list[dict[str, Any]] = []
        for lane in lanes:
            if isinstance(lane, Mapping):
                lane_rows.extend(
                    _validate_lane_manifest(
                        audit, lane, experiment_id=experiment_id, job_id=job_id
                    )
                )
            else:
                audit.fail("lane_type", f"{experiment_id}:{job_id}")
        # Lane logs are the unannotated source.  The job log adds correction
        # metadata, so compare stable run/step identities rather than bytes.
        lane_keys = Counter(
            (str(row.get("run_key")), int(row.get("step") or 0)) for row in lane_rows
        )
        job_keys = Counter(
            (str(row.get("run_key")), int(row.get("step") or 0)) for row in job_rows
        )
        audit.require(lane_keys == job_keys, "lane_job_row_identity", f"{experiment_id}:{job_id}")
    return all_rows, records


def _artifact_map(
    audit: _Audit, manifest: Mapping[str, Any], *, experiment_id: str
) -> dict[str, Path]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        audit.fail("manifest_artifacts", f"{experiment_id}: ledger missing")
        return {}
    paths: dict[str, Path] = {}
    prompt_artifacts: list[Path] = []
    for index, item in enumerate(artifacts):
        if not isinstance(item, Mapping):
            audit.fail("artifact_entry", f"{experiment_id}:{index}")
            continue
        path = audit.path(item.get("path", ""), label=f"{experiment_id} artifact[{index}]")
        record = audit.record(
            path,
            kind=str(item.get("kind", "artifact")),
            source=f"{experiment_id}.manifest.artifacts[{index}]",
            declared_sha256=item.get("sha256"),
            declared_bytes=item.get("bytes"),
        )
        if path is not None:
            relative = audit.relative(path)
            if relative in paths:
                audit.fail("duplicate_artifact", f"{experiment_id}:{relative}")
            paths[relative] = path
            if record is None:
                audit.fail("artifact_unreadable", relative)
            if item.get("kind") == "prompt_workload_verification":
                prompt_artifacts.append(path)
    observed_names = {
        path.name for path in paths.values() if path not in prompt_artifacts
    }
    expected_names = EXPECTED_ARTIFACT_NAMES[experiment_id] - {
        "prompt_verification.json"
    }
    audit.require(
        observed_names == expected_names,
        "artifact_contract",
        f"{experiment_id}: observed={sorted(observed_names)}",
    )
    audit.require(
        len(prompt_artifacts) == 1,
        "prompt_artifact_contract",
        f"{experiment_id}: expected exactly one prompt_workload_verification artifact",
    )
    return paths


def _find_artifact(paths: Mapping[str, Path], name: str) -> Path | None:
    matches = [path for path in paths.values() if path.name == name]
    return matches[0] if len(matches) == 1 else None


def _validate_formal_rows(
    audit: _Audit,
    *,
    experiment_id: str,
    rows: Sequence[Mapping[str, Any]],
    plan_jobs: Sequence[Mapping[str, Any]],
    prompt_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    job_by_id = {str(job.get("id")): job for job in plan_jobs}
    first = [row for row in rows if int(row.get("step") or 0) == 1]
    identities = [(str(row.get("run_key")), int(row.get("step") or 0)) for row in rows]
    audit.require(len(identities) == len(set(identities)), "duplicate_run_step", experiment_id)
    for row in rows:
        job_id = str(row.get("correction_job_id", ""))
        job = job_by_id.get(job_id)
        if job is None:
            audit.fail("unknown_correction_job", f"{experiment_id}:{job_id}")
            continue
        audit.require(row.get("correction_protocol_id") == PROTOCOL_ID, "row_protocol", f"{experiment_id}:{job_id}")
        audit.require(row.get("served_model") == job.get("served_model"), "row_model", f"{experiment_id}:{job_id}")
        audit.require(row.get("condition_id") == job.get("condition_id"), "row_condition", f"{experiment_id}:{job_id}")
        audit.require(row.get("target_prompt_tokens") == job.get("target_prompt_tokens"), "row_target", f"{experiment_id}:{job_id}")
        audit.require((row.get("model_config") or {}).get("ollama_transport") == "native", "row_transport", f"{experiment_id}:{job_id}")
        audit.require((row.get("model_config") or {}).get("num_ctx") in {None, ""}, "row_dynamic_num_ctx", f"{experiment_id}:{job_id}")
        audit.require(
            int(row.get("provider_attempts") or 0) == 1,
            "row_provider_attempts",
            f"{experiment_id}:{job_id}",
        )
        audit.require(
            (
                row.get("usage_source") == "ollama_native_prompt_eval_count"
                and row.get("prompt_eval_count") is not None
            )
            or row.get("provider_done") is False,
            "row_native_usage",
            f"{experiment_id}:{job_id}",
        )
        audit.require(not bool(row.get("timed_out")), "row_timeout", f"{experiment_id}:{job_id}")
        audit.require(
            row.get("final_status") != "error"
            or row.get("provider_done") is False,
            "row_unexplained_error",
            f"{experiment_id}:{job_id}",
        )
        audit.require(_provider_incomplete_safe(row), "provider_incomplete_execution", f"{experiment_id}:{job_id}")
    for row in first:
        case_id = str(row.get("case_id", ""))
        proof = prompt_map.get(case_id)
        if proof is None:
            audit.fail("formal_prompt_proof_missing", f"{experiment_id}:{case_id}")
            continue
        calibrated = row.get("calibrated_prompt_eval_count")
        audit.require(calibrated == proof.get("observed_prompt_eval_count"), "formal_prompt_calibration", f"{experiment_id}:{case_id}")
        raw_count = row.get("prompt_eval_count")
        evidence = row.get("prompt_count_evidence")
        audit.require(
            (raw_count is not None and evidence == "formal_provider")
            or (
                raw_count is None
                and row.get("provider_done") is False
                and evidence == "frozen_one_token_preflight"
            ),
            "formal_prompt_evidence_policy",
            f"{experiment_id}:{case_id}",
        )
        effective = raw_count if raw_count is not None else calibrated
        try:
            target = int(row.get("target_prompt_tokens"))
            within = effective is not None and abs(int(effective) - target) / target <= 0.05
        except (TypeError, ValueError, ZeroDivisionError):
            within = False
        audit.require(within, "formal_prompt_tolerance", f"{experiment_id}:{case_id}")
    formal_count = sum(
        (job_by_id.get(str(row.get("correction_job_id"))) or {}).get("job_type") == "formal"
        for row in first
    )
    warmup_count = sum(
        (job_by_id.get(str(row.get("correction_job_id"))) or {}).get("job_type") == "warmup"
        for row in first
    )
    return {"all_first_step": len(first), "formal": formal_count, "warmup": warmup_count}


def _validate_manifest_bundle(
    audit: _Audit,
    *,
    experiment_id: str,
    manifest_path: Path,
    freeze_sha256: str,
    prompt_path: Path,
    prompt_map: Mapping[str, Mapping[str, Any]],
    fixture_path: Path,
) -> dict[str, Any]:
    manifest_file = audit.path(manifest_path, label=f"{experiment_id} formal manifest")
    manifest_record = audit.record(
        manifest_file, kind="formal_manifest", source=f"{experiment_id}.manifest"
    )
    manifest = _load_json(audit, manifest_file, label=f"{experiment_id} manifest")
    expected = 120 if experiment_id == "E9" else 432
    audit.require(manifest.get("experiment_id") == experiment_id, "manifest_experiment_id", experiment_id)
    audit.require(manifest.get("status") == "completed", "manifest_status", experiment_id)
    audit.require(manifest.get("protocol_id") == PROTOCOL_ID, "manifest_protocol", experiment_id)
    audit.require(manifest.get("workload_revision") == "r2", "manifest_workload_revision", experiment_id)
    audit.require(manifest.get("denominator_policy") == "V2_only_old_V3_excluded", "manifest_denominator_policy", experiment_id)
    audit.require("invalid V3" in str(manifest.get("correction_of")), "manifest_correction_boundary", experiment_id)
    progress = manifest.get("progress") or {}
    audit.require(progress.get("expected_runs") == expected, "manifest_expected_runs", experiment_id)
    audit.require(progress.get("completed_runs") == expected, "manifest_completed_runs", experiment_id)
    audit.require(progress.get("failed_jobs") == 0, "manifest_failed_jobs", experiment_id)
    audit.require(bool((manifest.get("git") or {}).get("commit")), "manifest_git_commit", experiment_id)
    configuration = manifest.get("configuration") or {}
    audit.require(configuration.get("protocol_id") == PROTOCOL_ID, "configuration_protocol", experiment_id)
    audit.require(configuration.get("workload_revision") == "r2", "configuration_workload_revision", experiment_id)
    audit.require(configuration.get("phase") == "formal", "configuration_phase", experiment_id)
    audit.require(configuration.get("freeze_sha256") == freeze_sha256, "configuration_freeze_sha", experiment_id)
    declared_freeze = audit.path(
        configuration.get("freeze_path", ""),
        label=f"{experiment_id} declared freeze",
    )
    audit.require(
        declared_freeze is not None and _sha256(declared_freeze) == freeze_sha256,
        "configuration_freeze_path",
        experiment_id,
    )
    audit.require(configuration.get("prompt_verification_sha256") == _sha256(prompt_path), "configuration_prompt_sha", experiment_id)
    audit.require(configuration.get("transport") == "ollama_native", "configuration_transport", experiment_id)
    audit.require(configuration.get("dynamic_num_ctx") is None, "configuration_num_ctx", experiment_id)

    artifact_paths = _artifact_map(audit, manifest, experiment_id=experiment_id)
    manifest_dir = manifest_file.parent if manifest_file is not None else audit.root
    for relative, path in artifact_paths.items():
        permitted_external = path.resolve() == prompt_path.resolve()
        audit.require(
            permitted_external or path.parent.resolve() == manifest_dir.resolve(),
            "artifact_bundle_escape",
            f"{experiment_id}:{relative}",
        )
        audit.require(
            "/outputs/experiments/E9/" not in f"/{relative}"
            and "/outputs/experiments/E14/" not in f"/{relative}",
            "old_v3_artifact_forbidden",
            f"{experiment_id}:{relative}",
        )
    prompt_artifact_paths = [
        path
        for path in artifact_paths.values()
        if path.resolve() == prompt_path.resolve()
    ]
    audit.require(
        len(prompt_artifact_paths) == 1,
        "manifest_prompt_proof_drift",
        f"{experiment_id} does not reference the uniquely frozen prompt proof",
    )

    dataset = manifest.get("dataset") or {}
    dataset_paths: list[Path] = []
    for index, value in enumerate(dataset.get("paths") or []):
        path = audit.path(value, label=f"{experiment_id} dataset[{index}]")
        if path is not None:
            dataset_paths.append(path)
    audit.require(prompt_path.resolve() in {path.resolve() for path in dataset_paths}, "dataset_prompt_missing", experiment_id)
    audit.require(fixture_path.resolve() in {path.resolve() for path in dataset_paths}, "dataset_fixture_missing", experiment_id)
    if dataset_paths:
        audit.require(dataset.get("sha256") == _dataset_hash(audit, dataset_paths), "dataset_sha256", experiment_id)

    plan_path = _find_artifact(artifact_paths, "execution_plan.json")
    plan = _load_json(audit, plan_path, label=f"{experiment_id} execution plan")
    audit.require(plan.get("protocol_id") == PROTOCOL_ID, "plan_protocol", experiment_id)
    audit.require(plan.get("workload_revision") == "r2", "plan_workload_revision", experiment_id)
    audit.require(plan.get("experiment_id") == experiment_id, "plan_experiment_id", experiment_id)
    audit.require(plan.get("phase") == "formal", "plan_phase", experiment_id)
    plan_jobs = plan.get("jobs")
    if not isinstance(plan_jobs, list):
        audit.fail("plan_jobs", experiment_id)
        plan_jobs = []
    if experiment_id == "E9":
        audit.require(plan.get("expected_case_runs") == 120, "e9_plan_denominator", "expected_case_runs != 120")
        audit.require(len(plan_jobs) == 8, "e9_plan_job_count", str(len(plan_jobs)))
        audit.require(sum(int(job.get("expected_case_runs", 0)) for job in plan_jobs) == 120, "e9_plan_job_sum", "job sum != 120")
    else:
        audit.require(plan.get("expected_formal_case_runs") == 432, "e14_plan_formal_denominator", "formal != 432")
        audit.require(plan.get("expected_warmup_case_runs") == 48, "e14_plan_warmup_denominator", "warmup != 48")
        audit.require(len(plan_jobs) == 104, "e14_plan_job_count", str(len(plan_jobs)))
        audit.require(sum(int(job.get("expected_case_runs", 0)) for job in plan_jobs if job.get("job_type") == "formal") == 432, "e14_plan_formal_sum", "formal job sum != 432")
        audit.require(sum(int(job.get("expected_case_runs", 0)) for job in plan_jobs if job.get("job_type") == "warmup") == 48, "e14_plan_warmup_sum", "warmup job sum != 48")
        audit.require(sum(job.get("job_type") == "formal" and job.get("workload_cohort") == "matched_benign_latency" for job in plan_jobs) == 72, "e14_matched_job_count", "matched jobs != 72")
        audit.require(sum(int(job.get("expected_case_runs", 0)) for job in plan_jobs if job.get("job_type") == "formal" and job.get("workload_cohort") == "matched_benign_latency") == 288, "e14_matched_denominator", "matched != 288")
        audit.require(sum(int(job.get("expected_case_runs", 0)) for job in plan_jobs if job.get("job_type") == "formal" and job.get("workload_cohort") == "mixed_throughput") == 144, "e14_mixed_denominator", "mixed != 144")

    manifest_jobs = manifest.get("jobs")
    if not isinstance(manifest_jobs, list):
        audit.fail("manifest_jobs", experiment_id)
        manifest_jobs = []
    job_rows, job_records = _validate_jobs(
        audit,
        experiment_id=experiment_id,
        bundle_dir=manifest_dir,
        plan_jobs=plan_jobs,
        manifest_jobs=manifest_jobs,
    )
    aggregate_path = _find_artifact(artifact_paths, "raw_runs.jsonl")
    aggregate_rows = _read_jsonl(audit, aggregate_path, label=f"{experiment_id} aggregate raw")
    audit.require(_row_counter(aggregate_rows) == _row_counter(job_rows), "aggregate_job_rows", experiment_id)
    counts = _validate_formal_rows(
        audit,
        experiment_id=experiment_id,
        rows=aggregate_rows,
        plan_jobs=plan_jobs,
        prompt_map=prompt_map,
    )
    if experiment_id == "E9":
        audit.require(counts["all_first_step"] == 120, "e9_formal_case_runs", str(counts))
    else:
        audit.require(counts["all_first_step"] == 480, "e14_all_case_runs", str(counts))
        audit.require(counts["formal"] == 432, "e14_formal_case_runs", str(counts))
        audit.require(counts["warmup"] == 48, "e14_warmup_case_runs", str(counts))
        formal_path = _find_artifact(artifact_paths, "formal_raw_runs.jsonl")
        formal_rows = _read_jsonl(audit, formal_path, label="E14 formal-only raw")
        job_by_id = {str(job.get("id")): job for job in plan_jobs}
        expected_formal_rows = [
            row
            for row in aggregate_rows
            if (job_by_id.get(str(row.get("correction_job_id"))) or {}).get("job_type") == "formal"
        ]
        audit.require(_row_counter(formal_rows) == _row_counter(expected_formal_rows), "e14_warmup_exclusion", "formal_raw_runs is not the exact formal subset")
        audit.require(
            all((job_by_id.get(str(row.get("correction_job_id"))) or {}).get("job_type") == "formal" for row in formal_rows),
            "e14_warmup_leakage",
            "warmup row entered formal_raw_runs",
        )
        job_records_path = _find_artifact(artifact_paths, "job_records.jsonl")
        aggregate_records = _read_jsonl(audit, job_records_path, label="E14 aggregate job records")
        audit.require(_row_counter(aggregate_records) == _row_counter(job_records), "e14_job_record_aggregate", "job_records.jsonl differs from durable records")
        telemetry_path = _find_artifact(artifact_paths, "telemetry.jsonl")
        aggregate_telemetry = _read_jsonl(
            audit, telemetry_path, label="E14 aggregate telemetry"
        )
        expected_telemetry: list[dict[str, Any]] = []
        for record in job_records:
            durable_path = audit.path(
                record.get("telemetry_path", ""),
                label=f"E14:{record.get('id')} durable telemetry",
                allow_empty=True,
            )
            expected_telemetry.extend(
                {**row, "job_id": record.get("id")}
                for row in _read_jsonl(
                    audit,
                    durable_path,
                    label=f"E14:{record.get('id')} durable telemetry",
                )
            )
        audit.require(
            _row_counter(aggregate_telemetry) == _row_counter(expected_telemetry),
            "e14_telemetry_aggregate",
            "telemetry.jsonl differs from durable job telemetry",
        )
        performance_path = _find_artifact(artifact_paths, "performance.csv")
        if performance_path is not None:
            try:
                with performance_path.open(encoding="utf-8-sig", newline="") as stream:
                    performance_rows = list(csv.DictReader(stream))
                audit.require(
                    len(performance_rows) == 104,
                    "e14_performance_job_count",
                    f"performance rows={len(performance_rows)}",
                )
                audit.require(
                    sum(row.get("job_type") == "warmup" for row in performance_rows)
                    == 8
                    and sum(
                        row.get("job_type") == "formal"
                        for row in performance_rows
                    )
                    == 96,
                    "e14_performance_job_types",
                    "warmup/formal job rows are not 8/96",
                )
                audit.require(
                    {row.get("job_id") for row in performance_rows}
                    == {str(job.get("id")) for job in plan_jobs},
                    "e14_performance_job_set",
                    "performance.csv does not exactly cover the plan jobs",
                )
            except (OSError, UnicodeError, csv.Error) as exc:
                audit.fail("e14_performance_csv", str(exc))

    validity_path = _find_artifact(artifact_paths, "validity_checks.json")
    validity = _load_json(audit, validity_path, label=f"{experiment_id} validity")
    audit.require(validity.get("status") == "pass", "validity_status", experiment_id)
    audit.require(validity.get("protocol_id") == PROTOCOL_ID, "validity_protocol", experiment_id)
    audit.require(validity.get("experiment_id") == experiment_id, "validity_experiment", experiment_id)
    audit.require(validity.get("phase") == "formal", "validity_phase", experiment_id)
    audit.require(manifest.get("validity_checks") == validity, "manifest_validity_copy", experiment_id)
    checks = validity.get("checks") or {}
    audit.require(isinstance(checks, Mapping) and bool(checks) and all(value is True for value in checks.values()), "validity_checks", experiment_id)
    if experiment_id == "E9":
        audit.require(validity.get("expected_case_runs") == 120 and validity.get("observed_first_step_case_runs") == 120, "e9_validity_denominator", "validity != 120/120")
    else:
        audit.require(validity.get("expected_formal_case_runs") == 432 and validity.get("observed_formal_case_runs") == 432, "e14_validity_formal", "validity != 432/432")
        audit.require(validity.get("expected_warmup_case_runs") == 48 and validity.get("observed_warmup_case_runs") == 48, "e14_validity_warmup", "validity != 48/48")

    raw_index_path = _find_artifact(artifact_paths, "raw_run_index.json")
    raw_index = _load_json(audit, raw_index_path, label=f"{experiment_id} raw index")
    audit.require(raw_index.get("protocol_id") == PROTOCOL_ID, "raw_index_protocol", experiment_id)
    if experiment_id == "E9":
        audit.require(raw_index.get("old_v3_policy") == "excluded_invalid_diagnostic_provenance", "e9_old_v3_policy", "raw index policy")
    else:
        audit.require(raw_index.get("old_v3_policy") == "excluded_invalid_context_axis_provenance", "e14_old_v3_policy", "raw index policy")
        audit.require(raw_index.get("warmup_policy") == "retained_in_raw_runs_but_excluded_from_formal_raw_index", "e14_raw_index_warmup_policy", "raw index policy")
        formal_records = [record for record in raw_index.get("records") or [] if isinstance(record, Mapping) and record.get("kind") == "formal_raw_log"]
        audit.require(len(formal_records) == 1 and formal_records[0].get("logical_case_runs") == 432, "e14_raw_index_denominator", "formal record is not 432")

    statistics_path = _find_artifact(artifact_paths, "statistics.json")
    statistics_payload = _load_json(audit, statistics_path, label=f"{experiment_id} statistics")
    audit.require(statistics_payload.get("protocol_id") == PROTOCOL_ID, "statistics_protocol", experiment_id)
    audit.require(statistics_payload.get("evidence_tier") == "formal_context_correction_v2", "statistics_evidence_tier", experiment_id)
    audit.require(
        statistics_payload.get("formal_model_only") is True,
        "statistics_formal_model_only",
        experiment_id,
    )

    active_artifacts = sorted(artifact_paths)
    return {
        "experiment_id": experiment_id,
        "status": "pass",
        "manifest": manifest_record,
        "expected_case_runs": expected,
        "observed_case_runs": counts["formal"] if experiment_id == "E14" else counts["all_first_step"],
        "warmup_case_runs": counts["warmup"] if experiment_id == "E14" else 0,
        "warmup_excluded": experiment_id != "E14" or counts["warmup"] == 48,
        "job_count": len(plan_jobs),
        "artifact_count": len(artifact_paths),
        "active_artifacts": active_artifacts,
        "provider_incomplete_case_runs": int(validity.get("provider_incomplete_case_runs", 0)),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Context Correction V2 independent completion audit",
        "",
        f"- Status: **{report.get('status')}**",
        f"- Protocol: `{report.get('protocol_id')}`",
        f"- Workload revision: `{report.get('workload_revision')}`",
        f"- Evidence fingerprint: `{report.get('evidence_fingerprint')}`",
        f"- Files hashed: {report.get('integrity_summary', {}).get('files_hashed', 0)}",
        f"- Bytes hashed: {report.get('integrity_summary', {}).get('bytes_hashed', 0)}",
        "- Historical V3 E9/E14 evidence: preserved as invalid diagnostic provenance and excluded from V2 denominators.",
        "",
        "## Denominator gates",
        "",
    ]
    for experiment_id in ("E9", "E14"):
        item = (report.get("experiments") or {}).get(experiment_id) or {}
        lines.append(
            f"- {experiment_id}: formal {item.get('observed_case_runs')}/{item.get('expected_case_runs')}; "
            f"warmup {item.get('warmup_case_runs', 0)}; jobs {item.get('job_count')}; "
            f"artifacts {item.get('artifact_count')}."
        )
    failures = report.get("failures") or []
    lines.extend(["", "## Failures", ""])
    if failures:
        lines.extend(f"- `{item.get('code')}`: {item.get('detail')}" for item in failures)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Admission boundary",
            "",
            "Only `scripts/register_context_correction.py` may promote E9 and E14 from this audit. "
            "The registrar re-runs the audit and requires an identical evidence fingerprint.",
            "",
        ]
    )
    return "\n".join(lines)


def audit_context_correction_v2(
    *,
    repository_root: str | Path = ROOT,
    freeze_path: str | Path | None = None,
    e9_manifest_path: str | Path | None = None,
    e14_manifest_path: str | Path | None = None,
    output_json: str | Path | None = DEFAULT_JSON,
    output_markdown: str | Path | None = DEFAULT_MARKDOWN,
    expected_freeze_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Audit all corrected evidence and optionally write JSON/Markdown reports.

    ``expected_freeze_paths`` exists for isolated unit fixtures.  Production
    callers and the CLI always use the code-owned exact allowlist.
    """

    root = Path(repository_root).resolve()
    audit = _Audit(root)
    e9_manifest = Path(e9_manifest_path or root / DEFAULT_E9_MANIFEST.relative_to(ROOT))
    e14_manifest = Path(e14_manifest_path or root / DEFAULT_E14_MANIFEST.relative_to(ROOT))
    if freeze_path is None:
        declared_freezes: list[str] = []
        for manifest_path in (e9_manifest, e14_manifest):
            try:
                manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                value = (manifest_payload.get("configuration") or {}).get("freeze_path")
                if isinstance(value, str) and value.strip():
                    declared_freezes.append(value)
            except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
                continue
        freeze = Path(
            declared_freezes[0]
            if len(declared_freezes) == 2
            and len(set(declared_freezes)) == 1
            else root / DEFAULT_FREEZE.relative_to(ROOT)
        )
        if not freeze.is_absolute():
            freeze = root / freeze
    else:
        freeze = Path(freeze_path)
    freeze_payload, freeze_sha, prompt_path = _validate_freeze(
        audit,
        freeze,
        expected_freeze_paths=tuple(expected_freeze_paths or EXPECTED_FREEZE_PATHS),
    )
    prompt_payload, prompt_map, fixtures = _validate_prompt_proof(
        audit, prompt_path or root / "missing_prompt_verification.json"
    )
    experiments: dict[str, Any] = {}
    for experiment_id, manifest_path in (("E9", e9_manifest), ("E14", e14_manifest)):
        experiments[experiment_id] = _validate_manifest_bundle(
            audit,
            experiment_id=experiment_id,
            manifest_path=manifest_path,
            freeze_sha256=freeze_sha,
            prompt_path=prompt_path or root / "missing_prompt_verification.json",
            prompt_map=prompt_map,
            fixture_path=fixtures.get(experiment_id, root / "missing_fixture.jsonl"),
        )

    ledger = sorted(audit.integrity.values(), key=lambda item: item["path"])
    fingerprint_payload = {
        "protocol_id": PROTOCOL_ID,
        "freeze_sha256": freeze_sha,
        "prompt_verification_sha256": _sha256(prompt_path) if prompt_path and prompt_path.is_file() else "",
        "experiments": {
            key: {
                "manifest": (value.get("manifest") or {}).get("sha256"),
                "expected_case_runs": value.get("expected_case_runs"),
                "observed_case_runs": value.get("observed_case_runs"),
                "warmup_case_runs": value.get("warmup_case_runs"),
                "active_artifacts": value.get("active_artifacts"),
            }
            for key, value in experiments.items()
        },
        "integrity": [
            {key: item[key] for key in ("path", "bytes", "sha256")}
            for item in ledger
        ],
    }
    report: dict[str, Any] = {
        "schema_version": "2.0",
        "audit_type": AUDIT_TYPE,
        "protocol_id": PROTOCOL_ID,
        "workload_revision": "r2",
        "checked_at": _utc_now(),
        "repository_root": str(root),
        "status": "pass" if not audit.failures else "fail",
        "old_v3_policy": "preserved_invalid_diagnostic_provenance_excluded_from_v2_denominators",
        "inputs": {
            "freeze": {
                "path": audit.relative(freeze.resolve()) if freeze.resolve().is_relative_to(root) else str(freeze),
                "sha256": freeze_sha,
            },
            "prompt_verification": {
                "path": audit.relative(prompt_path) if prompt_path else "",
                "sha256": _sha256(prompt_path) if prompt_path and prompt_path.is_file() else "",
                "observation_count": len(prompt_payload.get("observations") or []),
            },
            "formal_manifests": {
                experiment_id: (experiments.get(experiment_id, {}).get("manifest") or {})
                for experiment_id in ("E9", "E14")
            },
        },
        "freeze": {
            "status": "pass" if freeze_payload.get("status") == "pass" else "fail",
            "freeze_complete": freeze_payload.get("freeze_complete") is True,
            "file_count": len(freeze_payload.get("files") or []),
        },
        "prompt_proof": {
            "status": prompt_payload.get("status"),
            "observation_count": len(prompt_payload.get("observations") or []),
            "all_checks_pass": bool(prompt_payload.get("checks"))
            and all(value is True for value in (prompt_payload.get("checks") or {}).values()),
        },
        "experiments": experiments,
        "integrity_summary": {
            "status": "pass" if not audit.failures else "fail",
            "files_hashed": audit.counters["files_hashed"],
            "bytes_hashed": audit.counters["bytes_hashed"],
            "ledger_entry_count": len(ledger),
        },
        "integrity_ledger": ledger,
        "failures": audit.failures,
        "evidence_fingerprint": _stable_hash(fingerprint_payload),
    }

    markdown_path: Path | None = None
    if output_markdown is not None:
        markdown_path = Path(output_markdown)
        if not markdown_path.is_absolute():
            markdown_path = root / markdown_path
        try:
            markdown_path.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("audit markdown output escapes repository root") from exc
        _atomic_write(markdown_path, _markdown(report))
        report["markdown_report"] = {
            "path": audit.relative(markdown_path),
            "bytes": markdown_path.stat().st_size,
            "sha256": _sha256(markdown_path),
        }
    if output_json is not None:
        json_path = Path(output_json)
        if not json_path.is_absolute():
            json_path = root / json_path
        try:
            json_path.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("audit JSON output escapes repository root") from exc
        _atomic_write(
            json_path,
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--freeze",
        type=Path,
        default=None,
        help="freeze path; default derives the identical path declared by both formal manifests",
    )
    parser.add_argument("--e9-manifest", type=Path, default=DEFAULT_E9_MANIFEST)
    parser.add_argument("--e14-manifest", type=Path, default=DEFAULT_E14_MANIFEST)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = audit_context_correction_v2(
        repository_root=ROOT,
        freeze_path=args.freeze,
        e9_manifest_path=args.e9_manifest,
        e14_manifest_path=args.e14_manifest,
        output_json=args.json,
        output_markdown=args.markdown,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "evidence_fingerprint": report["evidence_fingerprint"],
                "failures": len(report["failures"]),
                "json": str(args.json),
                "markdown": str(args.markdown),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
