"""Classify retained failures from an AgentDojo formal-run directory.

The diagnostic is deliberately non-admitting: it reads ``run_manifest.json``,
``outcomes.jsonl`` and local stderr logs, then writes a failure taxonomy for
operators.  It never retries, edits, excludes or promotes result rows.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import portable_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_official_formal_v2_cpu_detector"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "diagnostics"
    / "agentdojo_transformers_detector_failure_v1"
)
DIAGNOSTIC_VERSION = "m3-paper-v1-agentdojo-formal-failure-diagnostic-1.0"


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _classify_failure(row: Mapping[str, Any]) -> str:
    error_text = "\n".join(
        str(row.get(key, "")) for key in ("error_type", "error")
    ).casefold()
    text = "\n".join([error_text, str(row.get("traceback", "")).casefold()])
    if "defaultcpuallocator" in text or "not enough memory" in text:
        return "resource_cpu_memory"
    if "cuda out of memory" in text or "cublas" in text and "memory" in text:
        return "resource_gpu_memory"
    if "timeout" in error_text or "timed out" in error_text:
        return "timeout"
    if (
        "jsondecodeerror" in text
        or "invalid json" in error_text
        or "toolcall" in text
        or "parse" in text
    ):
        return "model_output_or_parse"
    if "trace was not written" in text or "filenotfounderror" in text:
        return "logging_or_trace_artifact"
    if "connection" in text or "http" in text or "ollama" in text:
        return "transport_or_service"
    return "unknown_runtime"


def _stderr_logs(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("*stderr*.log")):
        text = path.read_text(encoding="utf-8", errors="replace")
        rows.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "line_count": len(text.splitlines()),
                "last_lines": text.splitlines()[-20:],
            }
        )
    return rows


def _failure_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("status", "")) != "failed":
            continue
        classification = _classify_failure(row)
        failures.append(
            {
                "benchmark_case_id": str(row.get("benchmark_case_id", "")),
                "case_index": row.get("case_index"),
                "case_kind": row.get("case_kind", ""),
                "suite": row.get("suite", ""),
                "user_task_id": row.get("user_task_id", ""),
                "injection_task_id": row.get("injection_task_id"),
                "error_type": row.get("error_type", ""),
                "error": row.get("error", ""),
                "classification": classification,
                "created_at": row.get("created_at", ""),
            }
        )
    return failures


def build_failure_diagnostic(*, run_dir: Path, output_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    run_manifest_path = run_dir / "run_manifest.json"
    outcomes_path = run_dir / "outcomes.jsonl"
    progress_path = run_dir / "progress.jsonl"
    run_manifest = _read_json(run_manifest_path)
    outcomes = _read_jsonl(outcomes_path)
    failures = _failure_rows(outcomes)
    classification_counts = Counter(str(row["classification"]) for row in failures)
    status = (
        "completed_failure_diagnostic"
        if failures
        else "completed_no_failures_observed"
        if outcomes
        else "blocked_missing_outcomes"
    )
    diagnostic = {
        "schema_version": "paper-agentdojo-formal-failure-diagnostic-1.0",
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": _path(run_dir),
        "run_manifest_path": _path(run_manifest_path),
        "run_manifest_exists": run_manifest_path.exists(),
        "run_manifest_sha256": sha256_file(run_manifest_path)
        if run_manifest_path.exists()
        else "",
        "run_manifest_status": run_manifest.get("status", ""),
        "condition_id": run_manifest.get("condition_id", ""),
        "model_id": run_manifest.get("model_id", ""),
        "outcomes_path": _path(outcomes_path),
        "outcomes_exists": outcomes_path.exists(),
        "outcomes_sha256": sha256_file(outcomes_path) if outcomes_path.exists() else "",
        "progress_path": _path(progress_path),
        "progress_exists": progress_path.exists(),
        "progress_sha256": sha256_file(progress_path) if progress_path.exists() else "",
        "counts": {
            "outcome_rows": len(outcomes),
            "failed_rows": len(failures),
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "failures": failures,
        "failures_sha256": rows_sha256(failures),
        "stderr_logs": [
            {**row, "path": portable_path(Path(str(row["path"])), root=ROOT)}
            for row in _stderr_logs(run_dir)
        ],
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Failure diagnostic only. This artifact classifies retained failures "
            "and cannot retry, exclude, repair, admit or promote AgentDojo results."
        ),
    }
    json_path = output_dir / "failure_diagnostic.json"
    md_path = output_dir / "failure_diagnostic.md"
    _write_json(json_path, diagnostic)
    _write_markdown(md_path, diagnostic)
    diagnostic["json_path"] = _path(json_path)
    diagnostic["markdown_path"] = _path(md_path)
    return diagnostic


def _write_markdown(path: Path, diagnostic: Mapping[str, Any]) -> None:
    lines = [
        "# AgentDojo formal-run failure diagnostic",
        "",
        f"Generated: {diagnostic['created_at']}",
        f"Status: `{diagnostic['status']}`",
        f"Run manifest status: `{diagnostic['run_manifest_status']}`",
        f"Formal-table eligible: `{diagnostic['result_eligible_for_formal_tables']}`",
        "",
        "## Counts",
        "",
    ]
    counts = diagnostic["counts"]
    lines.append(f"- Outcome rows: `{counts['outcome_rows']}`")
    lines.append(f"- Failed rows: `{counts['failed_rows']}`")
    lines.append(f"- Classification counts: `{counts['classification_counts']}`")
    lines.extend(["", "## Failed cases", ""])
    failures = list(diagnostic.get("failures", []))
    if failures:
        lines.extend(
            [
                "| Case | Classification | Error |",
                "|---|---|---|",
            ]
        )
        for row in failures:
            error = str(row.get("error", "")).replace("|", "\\|")
            lines.append(
                f"| `{row.get('benchmark_case_id', '')}` | "
                f"`{row.get('classification', '')}` | {error} |"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Boundary", "", str(diagnostic["boundary"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    diagnostic = build_failure_diagnostic(
        run_dir=args.run_dir.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(json.dumps(diagnostic, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
