"""Build and validate standardized public-benchmark formal case-result rows.

This module is the bridge between benchmark-specific runners and the formal
cell materializer.  Runners may produce different native objects, but every
cell must eventually provide ``case_results.jsonl`` rows with the same fields
and with IDs matching the frozen ``todo_cases.jsonl`` queue.

The default is intentionally conservative: rows remain diagnostic unless the
source outcome itself declares an accepted formal source status and the caller
explicitly admits formal evidence for that conversion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .common import canonical_json, sha256_bytes, write_jsonl
from .materialize_public_benchmark_formal_cell import FORMAL_EVIDENCE_STATUS


CASE_RESULT_SCHEMA_VERSION = "paper-public-benchmark-formal-case-result-1.0"
CASE_RESULT_BUILDER_VERSION = "m3-paper-v1-formal-case-result-row-builder-1.0"
DIAGNOSTIC_EVIDENCE_STATUS = "diagnostic_public_benchmark_case_run_not_formal"
ACCEPTED_FORMAL_SOURCE_STATUSES = frozenset(
    {
        FORMAL_EVIDENCE_STATUS,
        "agentdojo_official_formal_case_run",
        "injecagent_official_formal_case_run",
        "public_benchmark_official_formal_case_run",
    }
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "success", "succ"}


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _lookup(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _guard_decision(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        decision = value.get("decision")
        if decision is not None:
            return str(decision)
    if isinstance(value, list):
        for item in reversed(value):
            if isinstance(item, Mapping):
                decision = _guard_decision(item.get("guard_decision", item.get("decision")))
                if decision:
                    return decision
    return ""


def _source_status(outcome: Mapping[str, Any]) -> str:
    return str(
        _lookup(
            outcome,
            "evidence_status",
            "source_evidence_status",
            "runtime_evidence_status",
            default="",
        )
        or ""
    )


def _row_sha256(row: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(dict(row)).encode("utf-8"))


def _case_run_id_from_key(todo: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(todo.get("benchmark_case_id", "")),
        str(todo.get("case_kind", "")),
        str(todo.get("replicate_id", "")),
    )


def _index_outcomes(outcomes: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    by_case_run_id: dict[str, dict[str, Any]] = {}
    by_benchmark_case: dict[tuple[str, str, str], dict[str, Any]] = {}
    for outcome in outcomes:
        case_run_id = str(outcome.get("case_run_id", ""))
        if case_run_id:
            if case_run_id in by_case_run_id:
                raise ValueError("duplicate outcome case_run_id: " + case_run_id)
            by_case_run_id[case_run_id] = outcome
        key = (
            str(outcome.get("benchmark_case_id", "")),
            str(outcome.get("case_kind", "")),
            str(outcome.get("replicate_id", "")),
        )
        if all(key):
            if key in by_benchmark_case:
                raise ValueError("duplicate outcome benchmark-case key: " + repr(key))
            by_benchmark_case[key] = outcome
    return by_case_run_id, by_benchmark_case


def _matching_outcome(
    todo: Mapping[str, Any],
    by_case_run_id: Mapping[str, dict[str, Any]],
    by_benchmark_case: Mapping[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    case_run_id = str(todo.get("case_run_id", ""))
    if case_run_id in by_case_run_id:
        return by_case_run_id[case_run_id]
    return by_benchmark_case.get(_case_run_id_from_key(todo))


def standardized_evidence_status(
    outcome: Mapping[str, Any],
    *,
    admit_formal: bool = False,
) -> str:
    """Return the standardized evidence status for one outcome row."""

    source = _source_status(outcome)
    if admit_formal and source in ACCEPTED_FORMAL_SOURCE_STATUSES:
        return FORMAL_EVIDENCE_STATUS
    return source or DIAGNOSTIC_EVIDENCE_STATUS


def build_case_result_row(
    todo: Mapping[str, Any],
    outcome: Mapping[str, Any] | None,
    *,
    admit_formal: bool = False,
) -> dict[str, Any]:
    """Build one standardized case-result row from a frozen todo row."""

    outcome = dict(outcome or {})
    case_kind = str(todo.get("case_kind", ""))
    status = str(_lookup(outcome, "status", "final_status", default="missing"))
    if not outcome:
        status = "missing"
    source_status = _source_status(outcome)
    evidence_status = standardized_evidence_status(outcome, admit_formal=admit_formal)
    attack_value = _lookup(
        outcome,
        "attack_success",
        "official_injection_success",
        "injection_success",
        default=False,
    )
    utility_value = _lookup(
        outcome,
        "utility_success",
        "utility",
        "official_utility_success",
        default=False,
    )
    parse_value = _lookup(outcome, "parse_ok", "parse_success", default=status == "completed")
    row = {
        "schema_version": CASE_RESULT_SCHEMA_VERSION,
        "builder_version": CASE_RESULT_BUILDER_VERSION,
        "case_run_id": str(todo.get("case_run_id", "")),
        "cell_id": str(todo.get("cell_id", "")),
        "benchmark": str(todo.get("benchmark", "")),
        "model": str(todo.get("model", "")),
        "condition_id": str(todo.get("condition_id", "")),
        "benchmark_case_id": str(todo.get("benchmark_case_id", "")),
        "case_kind": case_kind,
        "case_index": int(todo.get("case_index", 0) or 0),
        "replicate_id": int(todo.get("replicate_id", 0) or 0),
        "status": status,
        "evidence_status": evidence_status,
        "source_evidence_status": source_status,
        "source_result_eligible_for_formal_tables": bool(
            outcome.get("result_eligible_for_formal_tables", False)
        ),
        "attack_success": bool(_coerce_bool(attack_value)) if case_kind == "security" else False,
        "utility_success": bool(_coerce_bool(utility_value)) if case_kind == "utility" else bool(_coerce_bool(utility_value)),
        "guard_decision": _guard_decision(
            _lookup(outcome, "guard_decision", "last_guard_decision", "logs", default="")
        ),
        "parse_ok": bool(_coerce_bool(parse_value)),
        "case_latency_ms": _coerce_float(
            _lookup(outcome, "case_latency_ms", "elapsed_ms", default=None)
        ),
        "model_latency_ms": _coerce_float(_lookup(outcome, "model_latency_ms", default=None)),
        "guard_latency_ms": _coerce_float(_lookup(outcome, "guard_latency_ms", default=None)),
        "total_tokens": _lookup(outcome, "total_tokens", default=None),
        "source_outcome_sha256": _row_sha256(outcome) if outcome else "",
        "conversion_boundary": (
            "Standardized row for formal-cell materialization. Formal evidence "
            "status is granted only from accepted formal source statuses with "
            "admit_formal=True."
        ),
    }
    return row


def build_case_result_rows(
    todo_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
    *,
    admit_formal: bool = False,
) -> list[dict[str, Any]]:
    by_case_run_id, by_benchmark_case = _index_outcomes(outcome_rows)
    return [
        build_case_result_row(
            todo,
            _matching_outcome(todo, by_case_run_id, by_benchmark_case),
            admit_formal=admit_formal,
        )
        for todo in todo_rows
    ]


def validate_case_result_rows(
    todo_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_ids = [str(row.get("case_run_id", "")) for row in todo_rows]
    seen_ids = [str(row.get("case_run_id", "")) for row in result_rows]
    duplicate_ids = sorted({case_id for case_id in seen_ids if seen_ids.count(case_id) > 1})
    missing_ids = sorted(set(expected_ids) - set(seen_ids))
    unexpected_ids = sorted(set(seen_ids) - set(expected_ids))
    required_fields = {
        "schema_version",
        "case_run_id",
        "cell_id",
        "benchmark",
        "model",
        "condition_id",
        "benchmark_case_id",
        "case_kind",
        "replicate_id",
        "status",
        "evidence_status",
        "attack_success",
        "utility_success",
        "parse_ok",
    }
    field_issues: list[dict[str, Any]] = []
    todo_by_id = {str(row.get("case_run_id", "")): row for row in todo_rows}
    for row in result_rows:
        row_id = str(row.get("case_run_id", ""))
        missing_fields = sorted(field for field in required_fields if field not in row)
        todo = todo_by_id.get(row_id)
        identity_ok = True
        if todo is not None:
            identity_ok = all(
                str(row.get(field, "")) == str(todo.get(field, ""))
                for field in (
                    "cell_id",
                    "benchmark",
                    "model",
                    "condition_id",
                    "benchmark_case_id",
                    "case_kind",
                    "replicate_id",
                )
            )
        if missing_fields or not identity_ok:
            field_issues.append(
                {
                    "case_run_id": row_id,
                    "missing_fields": missing_fields,
                    "identity_ok": identity_ok,
                }
            )
    nonformal_ids = sorted(
        str(row.get("case_run_id", ""))
        for row in result_rows
        if str(row.get("evidence_status", "")) != FORMAL_EVIDENCE_STATUS
    )
    noncompleted_ids = sorted(
        str(row.get("case_run_id", ""))
        for row in result_rows
        if str(row.get("status", "")) != "completed"
    )
    return {
        "schema_version": "paper-public-benchmark-case-result-row-validation-1.0",
        "expected_rows": len(todo_rows),
        "observed_rows": len(result_rows),
        "duplicate_case_run_ids": duplicate_ids,
        "missing_case_run_ids": missing_ids,
        "unexpected_case_run_ids": unexpected_ids,
        "field_issues": field_issues,
        "nonformal_evidence_case_run_ids": nonformal_ids,
        "noncompleted_case_run_ids": noncompleted_ids,
        "coverage_ok": not duplicate_ids and not missing_ids and not unexpected_ids and not field_issues,
        "formal_ready": not nonformal_ids and not noncompleted_ids,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--todo", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--admit-formal", action="store_true")
    parser.add_argument("--validation-output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    todo_rows = _read_jsonl(args.todo)
    outcome_rows = _read_jsonl(args.outcomes)
    result_rows = build_case_result_rows(
        todo_rows,
        outcome_rows,
        admit_formal=args.admit_formal,
    )
    validation = validate_case_result_rows(todo_rows, result_rows)
    write_jsonl(args.output, result_rows)
    if args.validation_output is not None:
        args.validation_output.parent.mkdir(parents=True, exist_ok=True)
        args.validation_output.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if validation["coverage_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
