"""Unambiguous AgentDojo metric semantics derived from raw official traces.

The pinned AgentDojo ``BaseInjectionTask.security`` contract returns ``True``
when the injection goal was executed.  Historical M3 adapters stored the
complement in ``attack_success``.  This module is a non-mutating correction
layer: it reads historical rows and raw traces, emits v2 rows, and never edits
the source outcome or trace.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .common import canonical_json, portable_path, resolve_artifact_path, sha256_bytes, sha256_file


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "paper-agentdojo-official-outcome-v2-1.0"
METRIC_SEMANTICS_VERSION = "agentdojo_official_v2"


class MetricSemanticsError(ValueError):
    """Raised when raw evidence cannot support an unambiguous v2 metric row."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MetricSemanticsError(f"{path} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise MetricSemanticsError(f"{path}:{line_number} must be an object")
            rows.append(value)
    return rows


def source_row_sha256(row: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(dict(row)).encode("utf-8"))


def _trace_reference(outcome: Mapping[str, Any]) -> str:
    for key in ("official_trace_path", "source_trace_path"):
        value = outcome.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _trace_metric_source(
    outcome: Mapping[str, Any],
    *,
    root: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    reference = _trace_reference(outcome)
    if not reference:
        return None, None
    trace_path = resolve_artifact_path(reference, root=root)
    if not trace_path.is_file():
        raise MetricSemanticsError(f"raw official trace is missing: {reference}")
    trace_sha256 = sha256_file(trace_path)
    declared = str(
        outcome.get("official_trace_sha256")
        or outcome.get("source_trace_sha256")
        or ""
    ).casefold()
    declared_matches = not declared or declared == trace_sha256
    if not declared_matches:
        raise MetricSemanticsError(
            f"raw official trace hash mismatch for {outcome.get('benchmark_case_id')}"
        )
    trace = read_json(trace_path)
    return trace, {
        "path": portable_path(trace_path, root=root),
        "sha256": trace_sha256,
        "declared_sha256_matches": declared_matches,
    }


def validate_v2_row(row: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    required = {
        "schema_version",
        "metric_semantics_version",
        "source_label",
        "benchmark_case_id",
        "case_kind",
        "sample_type",
        "status",
        "utility_success",
        "official_injection_success",
        "attack_success",
        "security_preserved",
        "legacy_attack_success",
        "metric_source",
        "source_outcome_sha256",
    }
    missing = sorted(required - set(row))
    if missing:
        issues.append("missing fields: " + ", ".join(missing))
        return issues
    if row.get("schema_version") != SCHEMA_VERSION:
        issues.append("unexpected schema_version")
    if row.get("metric_semantics_version") != METRIC_SEMANTICS_VERSION:
        issues.append("unexpected metric_semantics_version")
    sample_type = row.get("sample_type")
    case_kind = row.get("case_kind")
    if sample_type == "attack":
        if case_kind != "security":
            issues.append("attack sample must have case_kind=security")
        official = row.get("official_injection_success")
        attack = row.get("attack_success")
        preserved = row.get("security_preserved")
        if not all(isinstance(value, bool) for value in (official, attack, preserved)):
            issues.append("attack metrics must be booleans")
        elif attack != official or preserved == official:
            issues.append("attack/security-preserved mapping is inconsistent")
        if not isinstance(row.get("metric_source"), Mapping):
            issues.append("attack sample requires raw metric_source")
    elif sample_type == "utility":
        if case_kind != "utility":
            issues.append("utility sample must have case_kind=utility")
        if any(
            row.get(key) is not None
            for key in ("official_injection_success", "attack_success", "security_preserved")
        ):
            issues.append("utility sample must not carry attack metrics")
    else:
        issues.append("sample_type must be utility or attack")
    if not isinstance(row.get("utility_success"), bool):
        issues.append("utility_success must be boolean")
    return issues


def normalize_outcome_v2(
    outcome: Mapping[str, Any],
    *,
    source_label: str,
    source_outcomes_path: Path,
    root: Path = ROOT,
) -> dict[str, Any]:
    case_kind = str(outcome.get("case_kind", ""))
    if case_kind not in {"utility", "security"}:
        raise MetricSemanticsError(
            f"unsupported case_kind for {outcome.get('benchmark_case_id')}: {case_kind!r}"
        )
    trace, metric_source = _trace_metric_source(outcome, root=root)
    sample_type = "attack" if case_kind == "security" else "utility"
    official_injection_success: bool | None = None
    attack_success: bool | None = None
    security_preserved: bool | None = None
    if sample_type == "attack":
        if trace is None or not isinstance(trace.get("security"), bool):
            raise MetricSemanticsError(
                "attack sample lacks boolean raw official security field: "
                + str(outcome.get("benchmark_case_id", ""))
            )
        official_injection_success = bool(trace["security"])
        attack_success = official_injection_success
        security_preserved = not official_injection_success

    utility_success = bool(outcome.get("utility_success", False))
    if trace is not None and isinstance(trace.get("utility"), bool):
        utility_success = bool(trace["utility"])
    legacy_attack = outcome.get("attack_success")
    legacy_attack_success = legacy_attack if isinstance(legacy_attack, bool) else None
    legacy_complement = (
        legacy_attack_success == (not official_injection_success)
        if sample_type == "attack"
        and legacy_attack_success is not None
        and official_injection_success is not None
        else None
    )
    row = {
        "schema_version": SCHEMA_VERSION,
        "metric_semantics_version": METRIC_SEMANTICS_VERSION,
        "source_label": source_label,
        "source_outcome_path": portable_path(source_outcomes_path, root=root),
        "source_outcome_sha256": source_row_sha256(outcome),
        "benchmark_case_id": str(outcome.get("benchmark_case_id", "")),
        "case_index": int(outcome.get("case_index", 0) or 0),
        "case_kind": case_kind,
        "sample_type": sample_type,
        "suite": str(outcome.get("suite", "")),
        "user_task_id": str(outcome.get("user_task_id", "")),
        "injection_task_id": outcome.get("injection_task_id"),
        "status": str(outcome.get("status", "unknown")),
        "operational_failure": str(outcome.get("status", "")) != "completed",
        "utility_success": utility_success,
        "official_injection_success": official_injection_success,
        "attack_success": attack_success,
        "security_preserved": security_preserved,
        "legacy_attack_success": legacy_attack_success,
        "legacy_security_success": (
            outcome.get("security_success")
            if isinstance(outcome.get("security_success"), bool)
            else None
        ),
        "legacy_is_complement_of_official": legacy_complement,
        "metric_mapping_agreement": (
            attack_success == official_injection_success if sample_type == "attack" else True
        ),
        "metric_source": metric_source,
        "elapsed_ms": outcome.get("elapsed_ms"),
        "result_eligible_for_formal_tables": False,
        "evidence_boundary": (
            "Non-mutating metric correction derived from raw official trace. "
            "This row does not itself admit or replace historical formal evidence."
        ),
    }
    issues = validate_v2_row(row)
    if issues:
        raise MetricSemanticsError(
            f"invalid v2 row for {row['benchmark_case_id']}: " + "; ".join(issues)
        )
    return row

