"""Read-only integrity audit for completed M3 experiment-program stages.

The auditor deliberately refuses to inspect a stage until the program manifest
marks it ``completed``.  This avoids racing a writer and makes one final audit
command suitable for ``main``, ``derived`` and ``stability`` evidence.

Only compact counters and identifiers are retained.  Model response text is
discarded immediately after each JSONL row is decoded and is never copied into
the generated reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_STAGES = ("main", "derived", "stability")
SUCCESS_TERMINAL_STATUSES = {
    "completed",
    "blocked",
    "needs_confirmation",
    "max_steps_reached",
}
RESULT_SUFFIXES = {".json", ".jsonl", ".csv"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _resolve_path(repo_root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _safe_path(
    repo_root: Path,
    value: str | Path,
    *,
    allowed_root: Path | None = None,
    suffixes: set[str] | None = None,
) -> Path:
    path = _resolve_path(repo_root, value)
    boundary = (allowed_root or repo_root).resolve()
    if not _is_within(path, boundary):
        raise ValueError(f"path escapes allowed root: {path}")
    relative_parts = [part.lower() for part in path.relative_to(repo_root.resolve()).parts]
    if len(relative_parts) >= 2 and relative_parts[:2] == ["sandbox", "secrets"]:
        raise ValueError("secret-store paths are forbidden")
    if suffixes is not None and path.suffix.lower() not in suffixes:
        raise ValueError(f"unsupported artifact suffix: {path.suffix}")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _csv_values(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


@dataclass
class Findings:
    items: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        code: str,
        message: str,
        *,
        severity: str = "error",
        **context: Any,
    ) -> None:
        self.items.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
                "context": {key: value for key, value in context.items() if value is not None},
            }
        )

    @property
    def error_count(self) -> int:
        return sum(item["severity"] == "error" for item in self.items)

    @property
    def warning_count(self) -> int:
        return sum(item["severity"] == "warning" for item in self.items)


def _check_equal(
    findings: Findings,
    *,
    code: str,
    label: str,
    expected: Any,
    actual: Any,
    context: Mapping[str, Any],
) -> bool:
    if actual == expected:
        return True
    findings.add(
        code,
        f"{label} mismatch: expected={expected!r}, actual={actual!r}",
        **dict(context),
    )
    return False


def _selected_case_ids(dataset_path: Path, config: Mapping[str, Any]) -> list[str]:
    rows: list[dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"dataset row {line_number} is not an object")
            rows.append(value)

    filters = (
        ("families", "attack_family"),
        ("splits", "split"),
        ("sample_types", "sample_type"),
        ("task_types", "task_type"),
        ("case_ids", "case_id"),
    )
    selected = rows
    for config_key, row_key in filters:
        accepted = set(_csv_values(config.get(config_key)))
        if accepted:
            selected = [row for row in selected if str(row.get(row_key, "")).strip() in accepted]

    if bool(config.get("shuffle", False)):
        seed = int(config.get("selection_seed", config.get("seed", 42)))
        random.Random(seed).shuffle(selected)
    limit = config.get("limit")
    if limit not in {None, ""}:
        selected = selected[: int(limit)]

    case_ids = [str(row.get("case_id", "")).strip() for row in selected]
    if any(not case_id for case_id in case_ids):
        raise ValueError("selected dataset contains an empty case_id")
    return case_ids


def _expected_identities(
    condition_id: str,
    case_ids: Sequence[str],
    config: Mapping[str, Any],
) -> set[tuple[str, str, int, int]]:
    repeats = int(config.get("repeats", 1))
    seed_base = int(config.get("generation_seed", config.get("seed", 42)))
    return {
        (condition_id, case_id, replicate_id, seed_base + replicate_id)
        for replicate_id in range(repeats)
        for case_id in case_ids
    }


def _identity_label(identity: tuple[str, str, int, int]) -> str:
    condition, case_id, replicate, seed = identity
    return f"{condition}|{case_id}|r{replicate}|s{seed}"


def _csv_data_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def _audit_condition(
    *,
    repo_root: Path,
    artifact_root: Path,
    stage_name: str,
    job_id: str,
    job_model: str,
    config: Mapping[str, Any],
    condition: Mapping[str, Any],
    selected_case_ids: Sequence[str],
    findings: Findings,
    global_instance_owners: dict[str, str],
) -> dict[str, Any]:
    condition_id = str(condition.get("condition_id", "")).strip()
    context = {"stage": stage_name, "job_id": job_id, "condition_id": condition_id}
    summary: dict[str, Any] = {
        "condition_id": condition_id,
        "status": condition.get("status"),
        "expected_runs": 0,
        "logical_runs": 0,
        "log_rows": 0,
        "parse_failure_rows": 0,
        "parse_failure_runs": 0,
        "timeout_rows": 0,
        "timeout_runs": 0,
        "max_step_runs": 0,
        "nonterminal_runs": 0,
        "missing_runs": 0,
        "extra_runs": 0,
        "duplicate_run_steps": 0,
        "duplicate_logical_runs": 0,
        "sandbox_missing_instances": 0,
        "sandbox_reused_instances": 0,
        "sandbox_cleanup_failures": 0,
        "final_status_counts": {},
        "hashes": {},
    }
    if not condition_id:
        findings.add("condition_id_missing", "condition_id is empty", **context)
        return summary
    if condition.get("status") != "completed":
        findings.add("condition_not_completed", "condition is not completed", **context)
        return summary

    try:
        jsonl_path = _safe_path(
            repo_root,
            str(condition.get("jsonl", "")),
            allowed_root=artifact_root,
            suffixes=RESULT_SUFFIXES,
        )
        csv_path = _safe_path(
            repo_root,
            str(condition.get("csv", "")),
            allowed_root=artifact_root,
            suffixes=RESULT_SUFFIXES,
        )
    except (ValueError, OSError) as exc:
        findings.add("artifact_path_invalid", str(exc), **context)
        return summary
    for path, kind in ((jsonl_path, "jsonl"), (csv_path, "csv")):
        if not path.is_file():
            findings.add("artifact_missing", f"{kind} artifact is missing", path=str(path), **context)
            return summary

    actual_jsonl_sha = _sha256(jsonl_path)
    actual_csv_sha = _sha256(csv_path)
    summary["hashes"] = {
        "jsonl": actual_jsonl_sha,
        "csv": actual_csv_sha,
    }
    _check_equal(
        findings,
        code="jsonl_sha_mismatch",
        label="JSONL SHA256",
        expected=condition.get("jsonl_sha256"),
        actual=actual_jsonl_sha,
        context=context,
    )
    _check_equal(
        findings,
        code="csv_sha_mismatch",
        label="CSV SHA256",
        expected=condition.get("csv_sha256"),
        actual=actual_csv_sha,
        context=context,
    )

    expected = _expected_identities(condition_id, selected_case_ids, config)
    summary["expected_runs"] = len(expected)
    _check_equal(
        findings,
        code="condition_selected_count_mismatch",
        label="condition selected_run_count",
        expected=len(expected),
        actual=int(condition.get("selected_run_count", -1)),
        context=context,
    )

    run_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_run_step: set[tuple[str, int]] = set()
    duplicate_run_steps = 0
    parse_failure_runs: set[str] = set()
    timeout_runs: set[str] = set()
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                findings.add(
                    "jsonl_decode_error",
                    f"invalid JSON at line {line_number}: {exc.msg}",
                    **context,
                )
                continue
            if not isinstance(row, dict):
                findings.add(
                    "jsonl_row_not_object",
                    f"line {line_number} is not a JSON object",
                    **context,
                )
                continue
            # Never retain model response text in memory used to build reports.
            row.pop("raw_model_output", None)
            run_key = str(row.get("run_key", "")).strip()
            if not run_key:
                findings.add("run_key_missing", f"line {line_number} has no run_key", **context)
                continue
            try:
                step = int(row.get("step", 0))
            except (TypeError, ValueError):
                step = 0
            run_step = (run_key, step)
            if run_step in seen_run_step:
                duplicate_run_steps += 1
            seen_run_step.add(run_step)
            minimal = {
                "condition_id": str(row.get("condition_id", "")).strip(),
                "case_id": str(row.get("case_id", "")).strip(),
                "replicate_id": row.get("replicate_id"),
                "seed": row.get("seed"),
                "step": step,
                "final_status": str(row.get("final_status", "")).strip(),
                "parse_ok": row.get("parse_ok"),
                "timed_out": bool(row.get("timed_out", False)),
                "model": str(row.get("model", "")).strip(),
                "sandbox_instance_id": str(row.get("sandbox_instance_id", "")).strip(),
                "sandbox_reset_status": str(row.get("sandbox_reset_status", "")).strip(),
                "sandbox_fixture_sha256": str(row.get("sandbox_fixture_sha256", "")).strip(),
                "sandbox_seed_sha256": str(row.get("sandbox_seed_sha256", "")).strip(),
            }
            run_rows[run_key].append(minimal)
            if not isinstance(minimal["parse_ok"], bool):
                findings.add(
                    "parse_flag_invalid",
                    f"line {line_number} parse_ok is not boolean",
                    **context,
                )
            if minimal["parse_ok"] is False:
                summary["parse_failure_rows"] += 1
                parse_failure_runs.add(run_key)
            if minimal["timed_out"]:
                summary["timeout_rows"] += 1
                timeout_runs.add(run_key)

    summary["log_rows"] = sum(len(rows) for rows in run_rows.values())
    summary["logical_runs"] = len(run_rows)
    summary["duplicate_run_steps"] = duplicate_run_steps
    summary["parse_failure_runs"] = len(parse_failure_runs)
    summary["timeout_runs"] = len(timeout_runs)
    if duplicate_run_steps:
        findings.add(
            "duplicate_run_step",
            f"found {duplicate_run_steps} duplicate (run_key, step) rows",
            **context,
        )

    identities: dict[tuple[str, str, int, int], set[str]] = defaultdict(set)
    successful_runs = 0
    final_status_counts: Counter[str] = Counter()
    condition_instances: dict[str, str] = {}
    expected_fixture_sha = str(condition.get("sandbox_fixture_sha256", "")).strip()
    expected_seed_shas = {
        str(key): str(value)
        for key, value in dict(condition.get("sandbox_seed_sha256") or {}).items()
    }
    for run_key, rows in run_rows.items():
        ordered = sorted(rows, key=lambda row: int(row["step"]))
        steps = [int(row["step"]) for row in ordered]
        if not steps or steps != list(range(1, max(steps) + 1)):
            findings.add(
                "run_step_sequence_invalid",
                "run steps are not a contiguous sequence starting at 1",
                run_key_sha256=hashlib.sha256(run_key.encode("utf-8")).hexdigest(),
                **context,
            )
        first = ordered[0]
        try:
            identity = (
                str(first["condition_id"]),
                str(first["case_id"]),
                int(first["replicate_id"]),
                int(first["seed"]),
            )
        except (TypeError, ValueError):
            findings.add(
                "run_identity_invalid",
                "logical run identity has missing or invalid fields",
                run_key_sha256=hashlib.sha256(run_key.encode("utf-8")).hexdigest(),
                **context,
            )
            continue
        identities[identity].add(run_key)
        if any(
            (
                str(row["condition_id"]),
                str(row["case_id"]),
                row["replicate_id"],
                row["seed"],
            )
            != (identity[0], identity[1], identity[2], identity[3])
            for row in ordered
        ):
            findings.add("run_identity_drift", "identity changes between steps", **context)
        if any(row["model"] != job_model for row in ordered):
            findings.add("run_model_mismatch", "row model differs from job model", **context)

        final_status = str(ordered[-1]["final_status"])
        final_status_counts[final_status or "<empty>"] += 1
        if any(str(row["final_status"]) in SUCCESS_TERMINAL_STATUSES for row in ordered):
            successful_runs += 1
        if final_status not in SUCCESS_TERMINAL_STATUSES:
            summary["nonterminal_runs"] += 1
        if final_status == "max_steps_reached":
            summary["max_step_runs"] += 1
            if int(ordered[-1]["step"]) != int(config.get("max_steps", 5)):
                findings.add(
                    "max_step_terminal_mismatch",
                    "max_steps_reached was not recorded at configured max_steps",
                    **context,
                )
        if max(steps, default=0) > int(config.get("max_steps", 5)):
            findings.add(
                "run_exceeds_max_steps",
                "logical run contains a step above configured max_steps",
                **context,
            )

        instances = {str(row["sandbox_instance_id"]) for row in ordered if row["sandbox_instance_id"]}
        if len(instances) != 1:
            summary["sandbox_missing_instances"] += 1
            findings.add(
                "sandbox_instance_invalid",
                "logical run must have exactly one non-empty sandbox instance",
                **context,
            )
        else:
            instance = next(iter(instances))
            owner = f"{stage_name}/{job_id}/{condition_id}/{_identity_label(identity)}"
            previous = global_instance_owners.setdefault(instance, owner)
            if previous != owner:
                summary["sandbox_reused_instances"] += 1
                findings.add(
                    "sandbox_instance_reused",
                    "sandbox instance is shared by multiple logical runs",
                    **context,
                )
            condition_instances[instance] = owner
        bad_cleanup = sum(row["sandbox_reset_status"] != "fresh_cleaned" for row in ordered)
        summary["sandbox_cleanup_failures"] += bad_cleanup
        if bad_cleanup:
            findings.add(
                "sandbox_cleanup_failure",
                f"{bad_cleanup} rows do not record fresh_cleaned",
                **context,
            )
        for row in ordered:
            if expected_fixture_sha and row["sandbox_fixture_sha256"] != expected_fixture_sha:
                findings.add("sandbox_fixture_sha_mismatch", "row sandbox fixture SHA differs", **context)
                break
        expected_seed_sha = expected_seed_shas.get(str(identity[3]), "")
        if expected_seed_sha and any(row["sandbox_seed_sha256"] != expected_seed_sha for row in ordered):
            findings.add("sandbox_seed_sha_mismatch", "row sandbox seed SHA differs", **context)

    duplicate_logical_runs = sum(max(0, len(keys) - 1) for keys in identities.values())
    summary["duplicate_logical_runs"] = duplicate_logical_runs
    summary["final_status_counts"] = dict(sorted(final_status_counts.items()))
    if duplicate_logical_runs:
        findings.add(
            "duplicate_logical_run",
            f"found {duplicate_logical_runs} additional run_keys for existing identities",
            **context,
        )
    observed = set(identities)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    summary["missing_runs"] = len(missing)
    summary["extra_runs"] = len(extra)
    if missing:
        findings.add(
            "logical_runs_missing",
            f"{len(missing)} expected logical runs are missing",
            examples=[_identity_label(item) for item in missing[:20]],
            **context,
        )
    if extra:
        findings.add(
            "logical_runs_extra",
            f"{len(extra)} unexpected logical runs are present",
            examples=[_identity_label(item) for item in extra[:20]],
            **context,
        )
    if summary["nonterminal_runs"]:
        findings.add(
            "nonterminal_logical_runs",
            f"{summary['nonterminal_runs']} logical runs lack a success terminal status",
            **context,
        )

    csv_rows = _csv_data_row_count(csv_path)
    _check_equal(
        findings,
        code="csv_jsonl_row_count_mismatch",
        label="CSV/JSONL row count",
        expected=summary["log_rows"],
        actual=csv_rows,
        context=context,
    )
    for field_name, expected_value, actual_value in (
        ("log_count", summary["log_rows"], int(condition.get("log_count", -1))),
        ("completed_run_count", successful_runs, int(condition.get("completed_run_count", -1))),
    ):
        _check_equal(
            findings,
            code=f"condition_{field_name}_mismatch",
            label=f"condition {field_name}",
            expected=expected_value,
            actual=actual_value,
            context=context,
        )
    jsonl_after_sha = _sha256(jsonl_path)
    csv_after_sha = _sha256(csv_path)
    if jsonl_after_sha != actual_jsonl_sha or csv_after_sha != actual_csv_sha:
        findings.add(
            "artifact_changed_during_audit",
            "JSONL or CSV changed while it was being audited",
            **context,
        )
    return summary


def _audit_job(
    *,
    repo_root: Path,
    artifact_root: Path,
    stage_name: str,
    job: Mapping[str, Any],
    findings: Findings,
    model_identities: dict[str, dict[str, set[str]]],
    global_instance_owners: dict[str, str],
) -> dict[str, Any]:
    job_id = str(job.get("job_id", "")).strip()
    context = {"stage": stage_name, "job_id": job_id}
    summary: dict[str, Any] = {
        "job_id": job_id,
        "model": job.get("model"),
        "status": job.get("status"),
        "expected_runs": int(job.get("expected_run_count", 0) or 0),
        "completed_runs": int(job.get("completed_run_count", 0) or 0),
        "condition_count": 0,
        "logical_runs": 0,
        "log_rows": 0,
        "parse_failure_rows": 0,
        "parse_failure_runs": 0,
        "timeout_rows": 0,
        "timeout_runs": 0,
        "max_step_runs": 0,
        "nonterminal_runs": 0,
        "missing_runs": 0,
        "duplicate_logical_runs": 0,
        "duplicate_run_steps": 0,
        "sandbox_cleanup_failures": 0,
        "sandbox_reused_instances": 0,
        "final_status_counts": {},
        "manifest_sha256": None,
        "conditions": [],
    }
    if job.get("status") != "completed":
        findings.add("job_not_completed", "job is not completed", **context)
        return summary
    try:
        manifest_path = _safe_path(
            repo_root,
            str(job.get("result_manifest", "")),
            allowed_root=artifact_root,
            suffixes={".json"},
        )
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        matrix = _read_json(manifest_path)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        findings.add("matrix_manifest_invalid", str(exc), **context)
        return summary
    summary["manifest_sha256"] = _sha256(manifest_path)
    if matrix.get("status") != "completed":
        findings.add("matrix_manifest_not_completed", "matrix manifest is not completed", **context)

    config = matrix.get("config")
    if not isinstance(config, dict):
        findings.add("matrix_config_missing", "matrix manifest config is missing", **context)
        return summary
    _check_equal(
        findings,
        code="matrix_config_hash_mismatch",
        label="matrix config_hash",
        expected=matrix.get("config_hash"),
        actual=_json_hash(config),
        context=context,
    )

    job_model = str(job.get("model", "")).strip()
    identity = matrix.get("model_identity")
    if not isinstance(identity, dict):
        findings.add("model_identity_missing", "matrix model_identity is missing", **context)
    else:
        tag = str(identity.get("tag", "")).strip()
        digest = str(identity.get("digest", "")).strip()
        version = str(identity.get("ollama_version", "")).strip()
        _check_equal(
            findings,
            code="model_tag_mismatch",
            label="model identity tag",
            expected=job_model,
            actual=tag,
            context=context,
        )
        if not digest:
            findings.add("model_digest_missing", "model digest is empty", **context)
        if not version:
            findings.add("ollama_version_missing", "Ollama version is empty", **context)
        record = model_identities.setdefault(tag or job_model, {"digests": set(), "versions": set()})
        if digest:
            record["digests"].add(digest)
        if version:
            record["versions"].add(version)

    dataset = matrix.get("dataset")
    if not isinstance(dataset, dict):
        findings.add("dataset_identity_missing", "matrix dataset identity is missing", **context)
        return summary
    try:
        dataset_path = _safe_path(
            repo_root,
            str(dataset.get("path", "")),
            suffixes={".jsonl"},
        )
        if not dataset_path.is_file():
            raise FileNotFoundError(dataset_path)
        dataset_sha = _sha256(dataset_path)
    except (ValueError, OSError) as exc:
        findings.add("dataset_path_invalid", str(exc), **context)
        return summary
    _check_equal(
        findings,
        code="dataset_sha_mismatch",
        label="dataset SHA256",
        expected=dataset.get("sha256"),
        actual=dataset_sha,
        context=context,
    )
    _check_equal(
        findings,
        code="config_dataset_sha_mismatch",
        label="config dataset_sha256",
        expected=dataset_sha,
        actual=config.get("dataset_sha256"),
        context=context,
    )
    _check_equal(
        findings,
        code="dataset_row_count_mismatch",
        label="dataset row_count",
        expected=int(dataset.get("row_count", -1)),
        actual=sum(1 for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()),
        context=context,
    )
    try:
        configured_dataset_path = _safe_path(
            repo_root,
            str(config.get("cases", "")),
            suffixes={".jsonl"},
        )
    except ValueError as exc:
        findings.add("config_dataset_path_invalid", str(exc), **context)
    else:
        _check_equal(
            findings,
            code="config_dataset_path_mismatch",
            label="config/dataset path",
            expected=str(dataset_path),
            actual=str(configured_dataset_path),
            context=context,
        )
    try:
        selected_case_ids = _selected_case_ids(dataset_path, config)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        findings.add("dataset_selection_invalid", str(exc), **context)
        return summary
    duplicate_case_ids = len(selected_case_ids) - len(set(selected_case_ids))
    if duplicate_case_ids:
        findings.add(
            "selected_case_ids_duplicate",
            f"selected dataset contains {duplicate_case_ids} duplicate case ids",
            **context,
        )

    conditions = matrix.get("conditions")
    if not isinstance(conditions, list):
        findings.add("conditions_missing", "matrix conditions is not a list", **context)
        return summary
    condition_ids = [str(item.get("condition_id", "")) for item in conditions if isinstance(item, dict)]
    if len(condition_ids) != len(set(condition_ids)):
        findings.add("condition_ids_duplicate", "matrix condition ids are not unique", **context)
    result_rows = [item for item in matrix.get("results", []) if isinstance(item, dict)]
    result_ids = [str(item.get("condition_id", "")) for item in result_rows]
    if len(result_ids) != len(set(result_ids)):
        findings.add("result_condition_ids_duplicate", "matrix result condition ids are not unique", **context)
    if set(condition_ids) != set(result_ids):
        findings.add("condition_results_mismatch", "conditions/results ids differ", **context)
    result_by_id = {str(item.get("condition_id", "")): item for item in result_rows}
    mirror_fields = (
        "status",
        "jsonl",
        "csv",
        "jsonl_sha256",
        "csv_sha256",
        "selected_run_count",
        "completed_run_count",
        "error_count",
        "log_count",
    )
    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        condition_id = str(condition.get("condition_id", ""))
        result = result_by_id.get(condition_id)
        if result is None:
            continue
        for field_name in mirror_fields:
            _check_equal(
                findings,
                code="condition_result_field_mismatch",
                label=f"conditions/results {field_name}",
                expected=condition.get(field_name),
                actual=result.get(field_name),
                context={**context, "condition_id": condition_id},
            )

    for condition in conditions:
        if not isinstance(condition, dict):
            findings.add("condition_not_object", "matrix condition is not an object", **context)
            continue
        condition_summary = _audit_condition(
            repo_root=repo_root,
            artifact_root=artifact_root,
            stage_name=stage_name,
            job_id=job_id,
            job_model=job_model,
            config=config,
            condition=condition,
            selected_case_ids=selected_case_ids,
            findings=findings,
            global_instance_owners=global_instance_owners,
        )
        summary["conditions"].append(condition_summary)

    summary["condition_count"] = len(summary["conditions"])
    aggregate_fields = (
        "logical_runs",
        "log_rows",
        "parse_failure_rows",
        "parse_failure_runs",
        "timeout_rows",
        "timeout_runs",
        "max_step_runs",
        "nonterminal_runs",
        "missing_runs",
        "duplicate_logical_runs",
        "duplicate_run_steps",
        "sandbox_cleanup_failures",
        "sandbox_reused_instances",
    )
    for field_name in aggregate_fields:
        summary[field_name] = sum(int(item.get(field_name, 0)) for item in summary["conditions"])
    job_status_counts: Counter[str] = Counter()
    for item in summary["conditions"]:
        job_status_counts.update(item.get("final_status_counts", {}))
    summary["final_status_counts"] = dict(sorted(job_status_counts.items()))
    _check_equal(
        findings,
        code="job_expected_run_count_mismatch",
        label="job expected_run_count",
        expected=sum(int(item["expected_runs"]) for item in summary["conditions"]),
        actual=int(job.get("expected_run_count", -1)),
        context=context,
    )
    _check_equal(
        findings,
        code="job_selected_run_count_mismatch",
        label="job selected_run_count",
        expected=summary["logical_runs"],
        actual=int(job.get("selected_run_count", -1)),
        context=context,
    )
    _check_equal(
        findings,
        code="job_completed_run_count_mismatch",
        label="job completed_run_count",
        expected=sum(int(item.get("expected_runs", 0)) - int(item.get("nonterminal_runs", 0)) for item in summary["conditions"]),
        actual=int(job.get("completed_run_count", -1)),
        context=context,
    )
    if int(job.get("error_count", 0) or 0) != 0:
        findings.add("job_error_count_nonzero", "completed job records nonzero errors", **context)
    if _sha256(manifest_path) != summary["manifest_sha256"]:
        findings.add(
            "matrix_manifest_changed_during_audit",
            "matrix manifest changed while its artifacts were audited",
            **context,
        )
    if _sha256(dataset_path) != dataset_sha:
        findings.add(
            "dataset_changed_during_audit",
            "dataset changed while the job was audited",
            **context,
        )
    return summary


def _audit_frozen_inputs(
    *,
    repo_root: Path,
    stage_name: str,
    stage: Mapping[str, Any],
    freeze_path: Path,
    threshold_path: Path,
    freeze_sha: str,
    threshold_sha: str,
    threshold_values: Mapping[str, Any],
    findings: Findings,
) -> None:
    context = {"stage": stage_name}
    frozen = stage.get("frozen_inputs")
    if not isinstance(frozen, dict):
        findings.add("frozen_inputs_missing", "stage frozen_inputs is missing", **context)
        return
    for key, path, actual_sha in (
        ("blind_freeze", freeze_path, freeze_sha),
        ("thresholds", threshold_path, threshold_sha),
    ):
        record = frozen.get(key)
        if not isinstance(record, dict):
            findings.add("frozen_input_missing", f"frozen input {key} is missing", **context)
            continue
        _check_equal(
            findings,
            code=f"{key}_sha_mismatch",
            label=f"{key} SHA256",
            expected=actual_sha,
            actual=record.get("sha256"),
            context=context,
        )
        try:
            recorded_path = _resolve_path(repo_root, str(record.get("path", "")))
        except (ValueError, OSError):
            recorded_path = Path(".")
        _check_equal(
            findings,
            code=f"{key}_path_mismatch",
            label=f"{key} path",
            expected=str(path.resolve()),
            actual=str(recorded_path),
            context=context,
        )
    verification = stage.get("freeze_verification")
    if not isinstance(verification, dict):
        findings.add("freeze_verification_missing", "stage freeze verification is missing", **context)
    else:
        if verification.get("status") != "pass" or verification.get("problems"):
            findings.add("freeze_verification_failed", "stage freeze verification is not a clean pass", **context)
        _check_equal(
            findings,
            code="freeze_verification_sha_mismatch",
            label="freeze verification SHA256",
            expected=freeze_sha,
            actual=verification.get("sha256"),
            context=context,
        )
    threshold_freeze = stage.get("threshold_freeze")
    if not isinstance(threshold_freeze, dict):
        findings.add("threshold_freeze_missing", "stage threshold freeze is missing", **context)
    else:
        for key in ("ask_threshold", "deny_threshold"):
            _check_equal(
                findings,
                code=f"threshold_{key}_mismatch",
                label=f"frozen {key}",
                expected=float(threshold_values[key]),
                actual=float(threshold_freeze.get(key, -1)),
                context=context,
            )
        _check_equal(
            findings,
            code="threshold_freeze_sha_mismatch",
            label="threshold freeze SHA256",
            expected=threshold_sha,
            actual=threshold_freeze.get("sha256"),
            context=context,
        )
    for job in stage.get("jobs", []):
        config = job.get("matrix_config") if isinstance(job, dict) else None
        if not isinstance(config, dict):
            continue
        for key in ("ask_threshold", "deny_threshold"):
            _check_equal(
                findings,
                code=f"job_{key}_mismatch",
                label=f"job {key}",
                expected=float(threshold_values[key]),
                actual=float(config.get(key, -1)),
                context={**context, "job_id": job.get("job_id")},
            )


def _audit_lifecycle(
    *,
    stage_name: str,
    stage: Mapping[str, Any],
    lifecycle: Sequence[Mapping[str, Any]],
    findings: Findings,
) -> dict[str, Any]:
    required_models = [str(item) for item in stage.get("required_models", [])]
    job_models = {str(job.get("model", "")) for job in stage.get("jobs", []) if isinstance(job, dict)}
    if set(required_models) != job_models:
        findings.add(
            "required_models_mismatch",
            "stage required_models differs from job models",
            stage=stage_name,
        )
    verified_models: list[str] = []
    for model in required_models:
        context = {"stage": stage_name, "model": model}
        events = [
            event
            for event in lifecycle
            if str(event.get("stage", "")) == stage_name and str(event.get("model", "")) == model
        ]
        clean = [
            event
            for event in events
            if event.get("action") == "ollama_stop_then_gpu_snapshot"
            and event.get("stop_status") == "completed"
            and not event.get("error")
            and isinstance(event.get("gpu_snapshot"), dict)
            and bool(event.get("gpu_snapshot", {}).get("available"))
        ]
        if not clean:
            findings.add(
                "model_lifecycle_missing",
                "no clean stop-plus-GPU-snapshot lifecycle event exists",
                **context,
            )
            continue
        verified_models.append(model)
        latest_job = max(
            (
                str(job.get("completed_at", ""))
                for job in stage.get("jobs", [])
                if isinstance(job, dict) and str(job.get("model", "")) == model
            ),
            default="",
        )
        if max(str(event.get("at", "")) for event in clean) < latest_job:
            findings.add(
                "model_lifecycle_stale",
                "latest clean lifecycle event predates the model's final job",
                **context,
            )
    return {
        "required_models": len(required_models),
        "verified_models": len(verified_models),
        "verified_model_tags": sorted(verified_models),
        "matching_event_count": sum(
            1
            for event in lifecycle
            if str(event.get("stage", "")) == stage_name
            and str(event.get("model", "")) in set(required_models)
        ),
    }


def _audit_freeze_files(
    *,
    repo_root: Path,
    freeze: Mapping[str, Any],
    findings: Findings,
) -> dict[str, Any]:
    files = freeze.get("files")
    if not isinstance(files, dict):
        findings.add("freeze_files_missing", "blind freeze file map is missing")
        return {"declared_files": 0, "verified_files": 0, "mismatches": 1}
    verified = 0
    mismatches = 0
    for relative, expected_sha in files.items():
        try:
            path = _safe_path(repo_root, str(relative))
        except ValueError as exc:
            findings.add("freeze_file_path_invalid", str(exc), path=str(relative))
            mismatches += 1
            continue
        if not path.is_file():
            findings.add("freeze_file_missing", "frozen file is missing", path=str(relative))
            mismatches += 1
            continue
        actual_sha = _sha256(path)
        if actual_sha != expected_sha:
            findings.add("freeze_file_sha_mismatch", "frozen file SHA256 changed", path=str(relative))
            mismatches += 1
            continue
        verified += 1
    _check_equal(
        findings,
        code="freeze_file_count_mismatch",
        label="freeze file_count",
        expected=int(freeze.get("file_count", -1)),
        actual=len(files),
        context={},
    )
    return {"declared_files": len(files), "verified_files": verified, "mismatches": mismatches}


def audit_program(
    *,
    repo_root: str | Path,
    program_manifest: str | Path,
    freeze_path: str | Path,
    threshold_path: str | Path,
    stages: Sequence[str] = DEFAULT_STAGES,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Audit completed stages and return a JSON-serializable report."""

    root = Path(repo_root).resolve()
    artifacts = _resolve_path(root, artifact_root or "outputs/experiments")
    findings = Findings()
    manifest_path = _safe_path(
        root,
        program_manifest,
        allowed_root=artifacts,
        suffixes={".json"},
    )
    freeze_file = _safe_path(root, freeze_path, suffixes={".json"})
    threshold_file = _safe_path(root, threshold_path, suffixes={".json"})
    for path in (manifest_path, freeze_file, threshold_file):
        if not path.is_file():
            raise FileNotFoundError(path)

    program = _read_json(manifest_path)
    program_sha_before = _sha256(manifest_path)
    freeze = _read_json(freeze_file)
    thresholds = _read_json(threshold_file)
    freeze_sha = _sha256(freeze_file)
    threshold_sha = _sha256(threshold_file)
    threshold_values = {
        "ask_threshold": float(thresholds["ask_threshold"]),
        "deny_threshold": float(thresholds["deny_threshold"]),
    }
    freeze_summary = _audit_freeze_files(repo_root=root, freeze=freeze, findings=findings)

    requested = list(dict.fromkeys(str(stage).strip() for stage in stages if str(stage).strip()))
    if not requested:
        raise ValueError("at least one stage is required")
    stage_results: list[dict[str, Any]] = []
    model_identities: dict[str, dict[str, set[str]]] = {}
    global_instance_owners: dict[str, str] = {}
    program_stages = program.get("stages")
    if not isinstance(program_stages, dict):
        raise ValueError("program manifest has no stages object")
    lifecycle = [
        item for item in program.get("model_lifecycle", []) if isinstance(item, dict)
    ]

    for stage_name in requested:
        stage = program_stages.get(stage_name)
        if not isinstance(stage, dict):
            findings.add("stage_missing", "requested stage is absent", stage=stage_name)
            stage_results.append({"stage": stage_name, "status": "missing", "scanned": False})
            continue
        stage_summary: dict[str, Any] = {
            "stage": stage_name,
            "status": stage.get("status"),
            "scanned": False,
            "job_count": len(stage.get("jobs", [])) if isinstance(stage.get("jobs"), list) else 0,
            "condition_count": 0,
            "expected_runs": int(stage.get("expected_run_count", 0) or 0),
            "logical_runs": 0,
            "log_rows": 0,
            "parse_failure_rows": 0,
            "parse_failure_runs": 0,
            "timeout_rows": 0,
            "timeout_runs": 0,
            "max_step_runs": 0,
            "nonterminal_runs": 0,
            "missing_runs": 0,
            "duplicate_logical_runs": 0,
            "duplicate_run_steps": 0,
            "sandbox_cleanup_failures": 0,
            "sandbox_reused_instances": 0,
            "final_status_counts": {},
            "lifecycle": {"required_models": 0, "verified_models": 0},
            "jobs": [],
        }
        # Critical concurrency rule: do not open any job artifact while a stage
        # can still be writing it.
        if stage.get("status") != "completed":
            findings.add(
                "stage_not_completed",
                "stage is not completed; job artifacts were intentionally not scanned",
                stage=stage_name,
                status=stage.get("status"),
            )
            stage_results.append(stage_summary)
            continue
        jobs = stage.get("jobs")
        if not isinstance(jobs, list):
            findings.add("stage_jobs_missing", "stage jobs is not a list", stage=stage_name)
            stage_results.append(stage_summary)
            continue
        job_ids = [str(job.get("job_id", "")) for job in jobs if isinstance(job, dict)]
        if len(job_ids) != len(set(job_ids)):
            findings.add("job_ids_duplicate", "stage job ids are not unique", stage=stage_name)
        _check_equal(
            findings,
            code="stage_job_count_mismatch",
            label="stage job_count",
            expected=int(stage.get("job_count", -1)),
            actual=len(jobs),
            context={"stage": stage_name},
        )
        _audit_frozen_inputs(
            repo_root=root,
            stage_name=stage_name,
            stage=stage,
            freeze_path=freeze_file,
            threshold_path=threshold_file,
            freeze_sha=freeze_sha,
            threshold_sha=threshold_sha,
            threshold_values=threshold_values,
            findings=findings,
        )
        for job in jobs:
            if not isinstance(job, dict):
                findings.add("job_not_object", "stage job is not an object", stage=stage_name)
                continue
            stage_summary["jobs"].append(
                _audit_job(
                    repo_root=root,
                    artifact_root=artifacts,
                    stage_name=stage_name,
                    job=job,
                    findings=findings,
                    model_identities=model_identities,
                    global_instance_owners=global_instance_owners,
                )
            )
        stage_summary["scanned"] = True
        stage_summary["condition_count"] = sum(item["condition_count"] for item in stage_summary["jobs"])
        aggregate_fields = (
            "logical_runs",
            "log_rows",
            "parse_failure_rows",
            "parse_failure_runs",
            "timeout_rows",
            "timeout_runs",
            "max_step_runs",
            "nonterminal_runs",
            "missing_runs",
            "duplicate_logical_runs",
            "duplicate_run_steps",
            "sandbox_cleanup_failures",
            "sandbox_reused_instances",
        )
        for field_name in aggregate_fields:
            stage_summary[field_name] = sum(int(item.get(field_name, 0)) for item in stage_summary["jobs"])
        stage_status_counts: Counter[str] = Counter()
        for item in stage_summary["jobs"]:
            stage_status_counts.update(item.get("final_status_counts", {}))
        stage_summary["final_status_counts"] = dict(sorted(stage_status_counts.items()))
        _check_equal(
            findings,
            code="stage_condition_count_mismatch",
            label="stage condition_count",
            expected=int(stage.get("condition_count", -1)),
            actual=stage_summary["condition_count"],
            context={"stage": stage_name},
        )
        _check_equal(
            findings,
            code="stage_expected_run_count_mismatch",
            label="stage expected_run_count",
            expected=stage_summary["logical_runs"],
            actual=int(stage.get("expected_run_count", -1)),
            context={"stage": stage_name},
        )
        progress = stage.get("progress") if isinstance(stage.get("progress"), dict) else {}
        _check_equal(
            findings,
            code="stage_progress_completed_mismatch",
            label="stage progress completed_runs",
            expected=stage_summary["logical_runs"] - stage_summary["nonterminal_runs"],
            actual=int(progress.get("completed_runs", -1)),
            context={"stage": stage_name},
        )
        declared_stage_errors = sum(int(job.get("error_count", 0) or 0) for job in jobs if isinstance(job, dict))
        _check_equal(
            findings,
            code="stage_progress_error_count_mismatch",
            label="stage progress error_count",
            expected=declared_stage_errors,
            actual=int(progress.get("error_count", -1)),
            context={"stage": stage_name},
        )
        if declared_stage_errors:
            findings.add(
                "stage_error_count_nonzero",
                "completed stage records nonzero job errors",
                stage=stage_name,
            )
        stage_summary["lifecycle"] = _audit_lifecycle(
            stage_name=stage_name,
            stage=stage,
            lifecycle=lifecycle,
            findings=findings,
        )
        stage_results.append(stage_summary)

    identity_report: dict[str, Any] = {}
    all_versions: set[str] = set()
    for tag, values in sorted(model_identities.items()):
        digests = sorted(values["digests"])
        versions = sorted(values["versions"])
        identity_report[tag] = {"digests": digests, "ollama_versions": versions}
        all_versions.update(versions)
        if len(digests) != 1:
            findings.add(
                "model_digest_inconsistent",
                f"model tag maps to {len(digests)} digests",
                model=tag,
                digests=digests,
            )
        if len(versions) != 1:
            findings.add(
                "model_ollama_version_inconsistent",
                f"model tag maps to {len(versions)} Ollama versions",
                model=tag,
                versions=versions,
            )
    if len(all_versions) > 1:
        findings.add(
            "ollama_version_inconsistent",
            "audited jobs use more than one Ollama version",
            versions=sorted(all_versions),
        )

    program_sha_after = _sha256(manifest_path)
    freeze_sha_after = _sha256(freeze_file)
    threshold_sha_after = _sha256(threshold_file)
    if program_sha_after != program_sha_before:
        findings.add(
            "program_manifest_changed_during_audit",
            "program manifest changed while the audit was running",
        )
    if freeze_sha_after != freeze_sha:
        findings.add("blind_freeze_changed_during_audit", "blind freeze changed during audit")
    if threshold_sha_after != threshold_sha:
        findings.add("thresholds_changed_during_audit", "frozen thresholds changed during audit")

    report = {
        "schema_version": "1.0",
        "generated_at": _utc_now(),
        "status": "pass" if findings.error_count == 0 else "fail",
        "scope": {
            "program_manifest": str(manifest_path),
            "program_manifest_sha256": program_sha_before,
            "blind_freeze": str(freeze_file),
            "blind_freeze_sha256": freeze_sha,
            "thresholds": str(threshold_file),
            "thresholds_sha256": threshold_sha,
            "stages": requested,
        },
        "freeze_files": freeze_summary,
        "models": identity_report,
        "stages": stage_results,
        "totals": {
            "jobs": sum(int(stage.get("job_count", 0)) for stage in stage_results if stage.get("scanned")),
            "conditions": sum(int(stage.get("condition_count", 0)) for stage in stage_results if stage.get("scanned")),
            "logical_runs": sum(int(stage.get("logical_runs", 0)) for stage in stage_results if stage.get("scanned")),
            "log_rows": sum(int(stage.get("log_rows", 0)) for stage in stage_results if stage.get("scanned")),
            "parse_failure_rows": sum(int(stage.get("parse_failure_rows", 0)) for stage in stage_results if stage.get("scanned")),
            "timeout_runs": sum(int(stage.get("timeout_runs", 0)) for stage in stage_results if stage.get("scanned")),
            "max_step_runs": sum(int(stage.get("max_step_runs", 0)) for stage in stage_results if stage.get("scanned")),
            "nonterminal_runs": sum(int(stage.get("nonterminal_runs", 0)) for stage in stage_results if stage.get("scanned")),
        },
        "finding_counts": {
            "errors": findings.error_count,
            "warnings": findings.warning_count,
        },
        "findings": findings.items,
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a compact human-readable companion to the JSON report."""

    lines = [
        "# Experiment Result Integrity Audit",
        "",
        f"- Status: **{str(report['status']).upper()}**",
        f"- Generated: `{report['generated_at']}`",
        f"- Program manifest SHA256: `{report['scope']['program_manifest_sha256']}`",
        f"- Blind freeze SHA256: `{report['scope']['blind_freeze_sha256']}`",
        f"- Threshold SHA256: `{report['scope']['thresholds_sha256']}`",
        "",
        "## Stage summary",
        "",
        "| Stage | Scanned | Jobs | Conditions | Logical runs | Log rows | Parse-fail rows | Timeouts | Max-step | Nonterminal |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for stage in report.get("stages", []):
        lines.append(
            "| {stage} | {scanned} | {jobs} | {conditions} | {runs} | {rows} | {parse} | {timeouts} | {maxstep} | {nonterminal} |".format(
                stage=stage.get("stage", ""),
                scanned="yes" if stage.get("scanned") else "no",
                jobs=stage.get("job_count", 0),
                conditions=stage.get("condition_count", 0),
                runs=stage.get("logical_runs", 0),
                rows=stage.get("log_rows", 0),
                parse=stage.get("parse_failure_rows", 0),
                timeouts=stage.get("timeout_runs", 0),
                maxstep=stage.get("max_step_runs", 0),
                nonterminal=stage.get("nonterminal_runs", 0),
            )
        )
    lines.extend(
        [
            "",
            "## Model provenance",
            "",
            "| Model tag | Digest | Ollama version |",
            "|---|---|---|",
        ]
    )
    for model, identity in report.get("models", {}).items():
        lines.append(
            f"| `{model}` | `{', '.join(identity.get('digests', []))}` | `{', '.join(identity.get('ollama_versions', []))}` |"
        )
    findings = list(report.get("findings", []))
    lines.extend(
        [
            "",
            "## Findings",
            "",
            f"Errors: **{report['finding_counts']['errors']}**; warnings: **{report['finding_counts']['warnings']}**.",
            "",
        ]
    )
    if not findings:
        lines.append("No integrity finding was detected.")
    else:
        lines.extend(["| Severity | Code | Message |", "|---|---|---|"])
        for item in findings[:100]:
            message = str(item.get("message", "")).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {item.get('severity')} | `{item.get('code')}` | {message} |")
        if len(findings) > 100:
            lines.append(f"\nOnly the first 100 of {len(findings)} findings are shown; see the JSON report.")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of agent/)",
    )
    parser.add_argument(
        "--program-manifest",
        default="outputs/experiments/program_manifest_final.json",
    )
    parser.add_argument("--freeze", default="outputs/experiments/blind_freeze.json")
    parser.add_argument(
        "--thresholds",
        default="outputs/experiments/E13/frozen_thresholds.json",
    )
    parser.add_argument("--artifact-root", default="outputs/experiments")
    parser.add_argument("--stages", nargs="+", default=list(DEFAULT_STAGES))
    parser.add_argument(
        "--json-out",
        default="agent/audits/final_result_integrity.json",
    )
    parser.add_argument(
        "--markdown-out",
        default="agent/audits/final_result_integrity.md",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repo_root.resolve()
    try:
        report = audit_program(
            repo_root=root,
            program_manifest=args.program_manifest,
            freeze_path=args.freeze,
            threshold_path=args.thresholds,
            stages=args.stages,
            artifact_root=args.artifact_root,
        )
        json_out = _safe_path(root, args.json_out, allowed_root=root / "agent", suffixes={".json"})
        markdown_out = _safe_path(root, args.markdown_out, allowed_root=root / "agent", suffixes={".md"})
        _atomic_json(json_out, report)
        _atomic_text(markdown_out, render_markdown(report))
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        f"integrity_audit status={report['status']} errors={report['finding_counts']['errors']} "
        f"runs={report['totals']['logical_runs']} json={json_out} markdown={markdown_out}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
