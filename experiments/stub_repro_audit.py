"""Compare two Stub matrices at the semantic-result level.

Wall-clock fields and run identifiers are intentionally excluded.  The audit
compares the deterministic inputs, model actions, Guard decisions, tool
observations, and terminal states for every case/condition/step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .manifest import REPO_ROOT, save_manifest, utc_now


VOLATILE_KEYS = {
    "run_id",
    "started_at",
    "step_completed_at",
    "completed_at",
    "created_at",
    "updated_at",
    "model_latency_ms",
    "guard_latency_ms",
    "tool_latency_ms",
    "total_latency_ms",
    "case_latency_ms",
    "latency_ms",
    "elapsed_ms",
    "duration_ms",
}
SANDBOX_EVENT_IDENTITY_KEYS = {
    "event_id",
    "run_id",
    "sandbox_instance_id",
    "timestamp",
    "ts",
}
TRACE_VOLATILE_KEYS = {
    "duration_ms",
    "elapsed_ms",
    "guard_latency_ms",
    "latency_ms",
    "model_latency_ms",
    "tool_latency_ms",
    "total_latency_ms",
}
_TEMP_SANDBOX_ROOT = re.compile(
    r"(?i)(?:(?:[a-z]:)?/(?:[^/\r\n]+/)*)"
    r"m3-pi-guard-sandbox-[^/\r\n]+/sandbox"
)


def _canonical(value: Any) -> Any:
    """Canonicalize one complete RunLog row for semantic comparison."""

    if isinstance(value, dict):
        canonical_observation = (
            _canonical_value(value.get("observation")) if "observation" in value else None
        )
        result: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            if key in VOLATILE_KEYS or key == "sandbox_instance_id":
                continue
            if key == "guard_trace":
                result[key] = _canonical_trace(item)
            elif key == "sandbox_event":
                result[key] = _canonical_sandbox_event(
                    item,
                    canonical_observation=canonical_observation,
                )
            else:
                result[key] = _canonical_value(item)
        return result
    return _canonical_value(value)


def _canonical_value(value: Any) -> Any:
    """Preserve semantic payloads while normalizing ephemeral runtime roots."""

    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, str):
        return _logicalize_temp_sandbox_paths(value)
    return value


def _canonical_trace(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonical_trace(item)
            for key, item in sorted(value.items())
            if key not in TRACE_VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_canonical_trace(item) for item in value]
    return _canonical_value(value)


def _canonical_sandbox_event(
    value: Any,
    *,
    canonical_observation: Any,
) -> Any:
    if not isinstance(value, dict):
        return _canonical_value(value)

    result = {
        key: _canonical_value(item)
        for key, item in sorted(value.items())
        if key not in SANDBOX_EVENT_IDENTITY_KEYS
    }
    if "arguments" in result and "arguments_sha256" in result:
        result["arguments_sha256"] = _semantic_value_sha256(result["arguments"])
    if canonical_observation is not None and "observation_sha256" in result:
        result["observation_sha256"] = _semantic_value_sha256(canonical_observation)
    return result


def _semantic_value_sha256(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _logicalize_temp_sandbox_paths(value: str) -> str:
    normalized = value.replace("\\", "/")
    logical, replacements = _TEMP_SANDBOX_ROOT.subn("sandbox", normalized)
    return logical if replacements else value


def _resolve_log(path_text: str, *, manifest_path: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    repo_candidate = REPO_ROOT / path
    if repo_candidate.exists():
        return repo_candidate
    return manifest_path.parent / path


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: expected an object")
            yield payload


def semantic_rows(manifest: str | Path) -> dict[str, dict[str, Any]]:
    manifest_path = Path(manifest).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("backend") != "stub" or not payload.get("oracle_stub"):
        raise ValueError(f"not a Stub matrix manifest: {manifest_path}")
    if payload.get("status") != "completed":
        raise ValueError(f"matrix is not completed: {manifest_path}")

    rows: dict[str, dict[str, Any]] = {}
    for result in payload.get("results", []):
        if result.get("status") != "completed" or result.get("error_count") != 0:
            raise ValueError(f"incomplete condition: {result.get('condition_id')}")
        log_path = _resolve_log(str(result["jsonl"]), manifest_path=manifest_path)
        for row in _read_jsonl(log_path):
            key = "|".join(
                [
                    str(row.get("condition_id", "")),
                    str(row.get("case_id", "")),
                    str(row.get("replicate_id", "")),
                    str(row.get("seed", "")),
                    str(row.get("step", "")),
                ]
            )
            if key in rows:
                raise ValueError(f"duplicate semantic row key: {key}")
            rows[key] = _canonical(row)
    return rows


def _digest(rows: dict[str, dict[str, Any]]) -> str:
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compare_stub_runs(
    first_manifest: str | Path,
    second_manifest: str | Path,
) -> dict[str, Any]:
    first = semantic_rows(first_manifest)
    second = semantic_rows(second_manifest)
    first_keys = set(first)
    second_keys = set(second)
    shared = sorted(first_keys & second_keys)
    mismatches = [key for key in shared if first[key] != second[key]]
    missing_from_second = sorted(first_keys - second_keys)
    extra_in_second = sorted(second_keys - first_keys)
    passed = not mismatches and not missing_from_second and not extra_in_second
    return {
        "schema_version": "1.0",
        "experiment_id": "STUB-REPRO",
        "created_at": utc_now(),
        "status": "completed" if passed else "failed",
        "first_manifest": str(Path(first_manifest)),
        "second_manifest": str(Path(second_manifest)),
        "first_row_count": len(first),
        "second_row_count": len(second),
        "shared_row_count": len(shared),
        "mismatch_count": len(mismatches),
        "missing_from_second_count": len(missing_from_second),
        "extra_in_second_count": len(extra_in_second),
        "first_semantic_sha256": _digest(first),
        "second_semantic_sha256": _digest(second),
        "exact_semantic_match": passed,
        "mismatch_examples": mismatches[:20],
        "missing_examples": missing_from_second[:20],
        "extra_examples": extra_in_second[:20],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first_manifest")
    parser.add_argument("second_manifest")
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "outputs" / "experiments" / "stub_reproducibility.json"),
    )
    args = parser.parse_args(argv)
    result = compare_stub_runs(args.first_manifest, args.second_manifest)
    save_manifest(result, args.out)
    print(
        f"Stub semantic reproducibility: {result['status']} "
        f"rows={result['shared_row_count']} mismatches={result['mismatch_count']}"
    )
    return 0 if result["exact_semantic_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
