"""审计 E9/E14 实验是否实际检验了所声明的上下文长度。

检查模型输入 token 长度分布，防止上下文截断导致评估失真。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_E9_ROOT = ROOT / "outputs" / "experiments" / "program_final_v3" / "derived"
DEFAULT_E14_CSV = ROOT / "outputs" / "experiments" / "E14" / "performance.csv"
DEFAULT_JSON = ROOT / "agent" / "audits" / "context_experiment_validity.json"
DEFAULT_MD = ROOT / "agent" / "audits" / "context_experiment_validity.md"
EXPECTED_CONTEXTS = (2048, 4096, 8192, 16384)
E9_JOB_RE = re.compile(r"derived__e9__qwen__ctx_(\d+)$")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, raw in enumerate(stream, start=1):
            text = raw.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: row must be an object")
            yield value


def audit_e9(root: Path, *, tolerance: float = 0.05) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for job_dir in sorted(root.glob("derived__e9__qwen__ctx_*")):
        match = E9_JOB_RE.fullmatch(job_dir.name)
        if not match:
            continue
        target = int(match.group(1))
        first_steps: list[Mapping[str, Any]] = []
        for log_path in sorted(job_dir.glob("*.jsonl")):
            first_steps.extend(row for row in _read_jsonl(log_path) if row.get("step") == 1)
        prompts = [
            int(row["prompt_tokens"])
            for row in first_steps
            if isinstance(row.get("prompt_tokens"), int)
        ]
        median_prompt = statistics.median(prompts) if prompts else None
        relative_error = (
            abs(float(median_prompt) - target) / target if median_prompt is not None else None
        )
        parse_count = sum(bool(row.get("parse_ok")) for row in first_steps)
        cells.append(
            {
                "target_prompt_tokens": target,
                "first_step_rows": len(first_steps),
                "usage_rows": len(prompts),
                "prompt_tokens_min": min(prompts) if prompts else None,
                "prompt_tokens_median": median_prompt,
                "prompt_tokens_max": max(prompts) if prompts else None,
                "relative_error": relative_error,
                "within_tolerance": relative_error is not None and relative_error <= tolerance,
                "parse_success_count": parse_count,
                "parse_success_rate": parse_count / len(first_steps) if first_steps else None,
            }
        )

    observed_contexts = tuple(sorted(cell["target_prompt_tokens"] for cell in cells))
    medians = [cell["prompt_tokens_median"] for cell in sorted(cells, key=lambda row: row["target_prompt_tokens"])]
    numeric_medians = [float(value) for value in medians if value is not None]
    all_targets_calibrated = (
        observed_contexts == EXPECTED_CONTEXTS
        and all(bool(cell["within_tolerance"]) for cell in cells)
    )
    strictly_increasing = len(numeric_medians) == len(EXPECTED_CONTEXTS) and all(
        right > left for left, right in zip(numeric_medians, numeric_medians[1:])
    )
    no_context_collapse = len(set(numeric_medians)) == len(EXPECTED_CONTEXTS)
    status = "pass" if all_targets_calibrated and strictly_increasing and no_context_collapse else "fail"
    return {
        "status": status,
        "expected_contexts": list(EXPECTED_CONTEXTS),
        "observed_contexts": list(observed_contexts),
        "relative_tolerance": tolerance,
        "all_targets_calibrated": all_targets_calibrated,
        "strictly_increasing_prompt_load": strictly_increasing,
        "no_context_collapse": no_context_collapse,
        "cells": cells,
        "interpretation": (
            "Declared E9 lengths are represented by actual first-step prompt usage."
            if status == "pass"
            else "Declared E9 lengths are not represented by calibrated prompt usage; security rates from collapsed/truncated cells are not interpretable as long-context robustness."
        ),
    }


def audit_e14(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_condition: dict[str, dict[int, list[float]]] = {}
    for row in rows:
        try:
            context = int(row.get("num_ctx", ""))
        except ValueError:
            continue
        prompt_median = _finite(row.get("prompt_tokens_median"))
        if prompt_median is None:
            continue
        condition = str(row.get("condition", "")).strip() or "unknown"
        by_condition.setdefault(condition, {}).setdefault(context, []).append(prompt_median)

    summaries: list[dict[str, Any]] = []
    conditions_valid = True
    for condition, context_values in sorted(by_condition.items()):
        context_medians = {
            context: statistics.median(values) for context, values in sorted(context_values.items())
        }
        observed = tuple(sorted(context_medians))
        ordered = [context_medians[context] for context in observed]
        strictly_increasing = len(ordered) == len(EXPECTED_CONTEXTS) and all(
            right > left for left, right in zip(ordered, ordered[1:])
        )
        workload_ratio = ordered[-1] / ordered[0] if len(ordered) >= 2 and ordered[0] else None
        material_scaling = workload_ratio is not None and workload_ratio >= 4.0
        valid = observed == EXPECTED_CONTEXTS and strictly_increasing and material_scaling
        conditions_valid = conditions_valid and valid
        summaries.append(
            {
                "condition": condition,
                "observed_contexts": list(observed),
                "prompt_tokens_median_by_context": {
                    str(context): value for context, value in context_medians.items()
                },
                "strictly_increasing_prompt_load": strictly_increasing,
                "largest_to_smallest_prompt_ratio": workload_ratio,
                "material_workload_scaling": material_scaling,
                "valid": valid,
            }
        )

    status = "pass" if summaries and conditions_valid else "fail"
    return {
        "status": status,
        "row_count": len(rows),
        "expected_contexts": list(EXPECTED_CONTEXTS),
        "conditions": summaries,
        "interpretation": (
            "E14 prompt workload scales with the declared context grid."
            if status == "pass"
            else "E14 changes a context label/configuration without materially changing prompt workload; it cannot support latency/throughput claims by context length."
        ),
    }


def build_report(e9_root: Path, e14_csv: Path) -> dict[str, Any]:
    e9 = audit_e9(e9_root)
    e14 = audit_e14(e14_csv)
    return {
        "schema_version": "1.0",
        "audit_type": "post_freeze_context_design_validity",
        "status": "pass" if e9["status"] == e14["status"] == "pass" else "fail",
        "non_causal": True,
        "original_bundles_mutated": False,
        "e9_root": str(e9_root),
        "e14_csv": str(e14_csv),
        "E9": e9,
        "E14": e14,
        "required_action": (
            "None."
            if e9["status"] == e14["status"] == "pass"
            else "Reopen failed experiments, create a new protocol/freeze with token-calibrated workloads and effective Ollama context configuration, rerun all affected cells, rebuild E17 source input and final analysis."
        ),
    }


def _write_outputs(payload: Mapping[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# E9/E14 Context Experiment Validity Audit",
        "",
        f"- Status: `{payload['status']}`",
        "- Audit type: post-freeze, non-causal metadata audit",
        "- Original bundles mutated: no",
        "",
        "## E9",
        "",
        f"- Status: `{payload['E9']['status']}`",
        f"- Interpretation: {payload['E9']['interpretation']}",
        "",
        "| Target prompt tokens | Rows | Observed min | Observed median | Observed max | Within 5% | Parse success |",
        "| ---: | ---: | ---: | ---: | ---: | :---: | ---: |",
    ]
    for cell in payload["E9"]["cells"]:
        rate = cell["parse_success_rate"]
        lines.append(
            "| {target_prompt_tokens} | {first_step_rows} | {prompt_tokens_min} | {prompt_tokens_median} | {prompt_tokens_max} | {within} | {parse_success_count}/{first_step_rows} ({rate}) |".format(
                **cell,
                within="yes" if cell["within_tolerance"] else "no",
                rate=f"{rate:.2%}" if rate is not None else "NA",
            )
        )
    lines.extend(
        [
            "",
            "## E14",
            "",
            f"- Status: `{payload['E14']['status']}`",
            f"- Interpretation: {payload['E14']['interpretation']}",
            "",
            "| Condition | Prompt-token medians by declared context | Largest/smallest ratio | Valid scaling |",
            "| --- | --- | ---: | :---: |",
        ]
    )
    for item in payload["E14"]["conditions"]:
        medians = ", ".join(
            f"{context}={value:g}"
            for context, value in item["prompt_tokens_median_by_context"].items()
        )
        ratio = item["largest_to_smallest_prompt_ratio"]
        lines.append(
            f"| {item['condition']} | {medians} | {ratio:.3f} | {'yes' if item['valid'] else 'no'} |"
        )
    lines.extend(["", "## Required Action", "", str(payload["required_action"]), ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e9-root", type=Path, default=DEFAULT_E9_ROOT)
    parser.add_argument("--e14-csv", type=Path, default=DEFAULT_E14_CSV)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--allow-fail", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_report(args.e9_root, args.e14_csv)
    _write_outputs(payload, args.json_out, args.markdown_out)
    print(json.dumps({"status": payload["status"], "json": str(args.json_out), "markdown": str(args.markdown_out)}))
    return 0 if payload["status"] == "pass" or args.allow_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
