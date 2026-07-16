"""CLI for evaluating M3_PI_Guard RunLog JSONL files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .metrics import (
    SUMMARY_FIELDS,
    blocked_records,
    build_summary_rows,
    compare_runs,
    load_jsonl,
    summarize_logs,
)
from .statistics import holm_adjust


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate M3_PI_Guard RunLog JSONL files.")
    parser.add_argument("--logs", nargs="*", help="RunLog JSONL files")
    parser.add_argument("--log-dir", help="Directory containing RunLog JSONL files")
    parser.add_argument("--baseline", help="Baseline RunLog JSONL path")
    parser.add_argument("--guarded", help="Guarded RunLog JSONL path")
    parser.add_argument("--cases", help="AttackCase JSONL file")
    parser.add_argument("--out", help="Output summary CSV path, or JSON path for legacy mode")
    parser.add_argument(
        "--strict-labels",
        action="store_true",
        help="Require explicit sample_type=attack|benign on every case",
    )
    parser.add_argument(
        "--legacy-observed-only",
        action="store_true",
        help="Compatibility only: do not retain cases missing from RunLog in denominators",
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    args = parser.parse_args(argv)

    cases = load_jsonl(_repo_path(args.cases)) if args.cases else []

    log_paths = list(args.logs or [])
    if args.log_dir:
        log_paths.extend(_logs_from_dir(_repo_path(args.log_dir)))

    if log_paths:
        if not args.out:
            raise SystemExit("--out is required when using --logs or --log-dir")
        logs_by_file = {str(log_path): load_jsonl(_repo_path(str(log_path))) for log_path in log_paths}
        rows = build_summary_rows(
            logs_by_file,
            cases,
            strict_labels=args.strict_labels,
            include_missing=not args.legacy_observed_only,
        )
        out_csv = _repo_path(args.out)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(out_csv, rows, SUMMARY_FIELDS)

        grouped_by_family = [row for row in rows if row.get("scope") == "attack_family"]
        family_csv = out_csv.with_name(f"{out_csv.stem}_grouped_by_family.csv")
        _write_csv(family_csv, grouped_by_family, SUMMARY_FIELDS)

        out_json = out_csv.with_suffix(".json")
        payload = {
            "cases_file": Path(args.cases).as_posix() if args.cases else "",
            "log_files": [Path(path).as_posix() for path in log_paths],
            "summary_csv": out_csv.as_posix(),
            "grouped_by_family_csv": family_csv.as_posix(),
            "rows": rows,
            "grouped_by_family": grouped_by_family,
            "blocked_records": blocked_records(logs_by_file),
            "pairwise_comparisons": _pairwise_comparisons(
                logs_by_file,
                cases,
                strict_labels=args.strict_labels,
                bootstrap_iterations=args.bootstrap_iterations,
                bootstrap_seed=args.bootstrap_seed,
            ),
            "data_quality_warnings": sorted(
                {
                    warning
                    for row in rows
                    if row.get("scope") == "overall"
                    for warning in str(row.get("DataWarnings") or "").split(" | ")
                    if warning
                }
            ),
        }
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out_csv}")
        print(f"wrote {out_json}")
        print(f"wrote {family_csv}")
        return 0

    if args.baseline and args.guarded:
        result: dict[str, Any] = compare_runs(
            load_jsonl(_repo_path(args.baseline)),
            load_jsonl(_repo_path(args.guarded)),
            cases,
            strict_labels=args.strict_labels,
            bootstrap_iterations=args.bootstrap_iterations,
            bootstrap_seed=args.bootstrap_seed,
        )
    elif args.baseline:
        result = summarize_logs(
            load_jsonl(_repo_path(args.baseline)),
            cases,
            strict_labels=args.strict_labels,
        )
    elif args.guarded:
        result = summarize_logs(
            load_jsonl(_repo_path(args.guarded)),
            cases,
            strict_labels=args.strict_labels,
        )
    else:
        raise SystemExit("Provide --logs or --baseline/--guarded")

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out_path = _repo_path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def _repo_path(value: str | None) -> Path:
    if not value:
        raise ValueError("path value is required")
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _logs_from_dir(path: Path) -> list[Path]:
    if not path.exists():
        raise SystemExit(f"--log-dir does not exist: {path}")
    if not path.is_dir():
        raise SystemExit(f"--log-dir is not a directory: {path}")
    logs = sorted(item for item in path.glob("*.jsonl") if item.is_file())
    if not logs:
        raise SystemExit(f"No JSONL files found in --log-dir: {path}")
    return logs


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _pairwise_comparisons(
    logs_by_file: dict[str, list[dict[str, Any]]],
    cases: list[dict[str, Any]],
    *,
    strict_labels: bool,
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    """Pair baseline files with compatible guarded-condition files."""

    entries: list[tuple[str, list[dict[str, Any]], str, str, str]] = []
    for path, logs in logs_by_file.items():
        if not logs:
            continue
        first = logs[0]
        mode = str(first.get("guard_mode") or first.get("defense_mode") or "")
        model = str(first.get("model", ""))
        prompt = str(first.get("prompt_profile", ""))
        entries.append((path, logs, mode, model, prompt))

    no_guard_modes = {"baseline", "none", "no_guard", "off"}
    baselines = [entry for entry in entries if entry[2] in no_guard_modes]
    guarded = [entry for entry in entries if entry[2] not in no_guard_modes]
    comparisons: list[dict[str, Any]] = []
    for baseline_path, baseline_logs, _, model, prompt in baselines:
        for guarded_path, guarded_logs, mode, guarded_model, guarded_prompt in guarded:
            if guarded_model != model or guarded_prompt != prompt:
                continue
            comparison = compare_runs(
                baseline_logs,
                guarded_logs,
                cases,
                strict_labels=strict_labels,
                bootstrap_iterations=bootstrap_iterations,
                bootstrap_seed=bootstrap_seed,
            )
            comparisons.append(
                {
                    "baseline_log": Path(baseline_path).as_posix(),
                    "guarded_log": Path(guarded_path).as_posix(),
                    "model": model,
                    "prompt_profile": prompt,
                    "guard_mode": mode,
                    "delta": comparison["delta"],
                    "paired_statistics": comparison["paired_statistics"],
                }
            )
    hypotheses: list[tuple[dict[str, Any], str, float]] = []
    for comparison in comparisons:
        paired = comparison.get("paired_statistics", {})
        for metric in ("ASR", "DSR", "TCR"):
            key = f"{metric}_mcnemar"
            test = paired.get(key)
            if isinstance(test, dict) and isinstance(test.get("p_value"), (int, float)):
                hypotheses.append((paired, key, float(test["p_value"])))
    if hypotheses:
        adjusted = holm_adjust([item[2] for item in hypotheses])
        for (paired, key, _), adjusted_p in zip(hypotheses, adjusted):
            paired[key]["holm_adjusted_p"] = adjusted_p
    return comparisons


if __name__ == "__main__":
    raise SystemExit(main())
