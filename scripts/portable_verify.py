"""Offline portability checks: trusted projections and raw numerators only."""

from __future__ import annotations

import argparse
import json
import platform
from collections import Counter, defaultdict
from pathlib import Path

from experiments.paper_v2.contracts import compute_online_visible_field_digest
from experiments.paper_v2.medium_runtime import FROZEN_GENERATED_AT, _runtime_inputs
from m3_core.policy_compiler_corrected_v1 import compile_task_policy_corrected_v1
from m3_core.policy_compiler_corrected_v2 import compile_generic_task_policy_corrected_v2

ROOT = Path(__file__).resolve().parents[1]
RAW_FILES = {
    "authorization": "outputs/experiments/claude_revision_v1/deepseek_pro_raw.jsonl",
    "synthetic": "outputs/experiments/claude_revision_v1/synthetic_regression_raw.jsonl",
    "calibration": "outputs/experiments/research_followup_20261006_v1/calibration/raw_records.jsonl",
}


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_projections(path: Path) -> dict:
    rows = jsonl(path)
    keys = [(r["benchmark"], r["case_id"]) for r in rows]
    if len(keys) != len(set(keys)) or len(rows) != 180:
        raise ValueError("expected 180 unique current-study online projections")
    for row in rows:
        projection = row["online_inputs"]
        if compute_online_visible_field_digest({"agent_input": projection})["forbidden_fields_present"]:
            raise ValueError("evaluator field in compiler input")
        request, context, schemas = _runtime_inputs(projection, row["benchmark"])
        compiler = compile_task_policy_corrected_v1 if row["benchmark"] == "m3-v2" else compile_generic_task_policy_corrected_v2
        actual = compiler(trusted_user_request=request, trusted_app_context=context,
                          tool_schemas=schemas, generated_at=FROZEN_GENERATED_AT).to_dict()
        if actual != row["reference_manifest"]:
            raise ValueError(f"compiled authorization changed: {row['case_id']}")
    return {"compiled_cases": len(rows), "benchmark_counts": dict(Counter(r["benchmark"] for r in rows)),
            "evaluator_fields_in_compiler_inputs": 0, "compiled_manifest_mismatches": 0}


def derive_counts(rows: list[dict]) -> dict:
    if len(rows) != len({r["work_key"] for r in rows}):
        raise ValueError("duplicate terminal work key in selected public raw file")
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("benchmark"), row.get("evaluation_case_type"), row.get("condition_id"),
                row.get("authorization_regime"), row.get("model_group"))].append(row)
    cells = []
    for key, selected in sorted(groups.items(), key=lambda item: str(item[0])):
        cell = dict(zip(("benchmark", "case_type", "condition", "regime", "model"), key))
        cell["planned_or_recorded"] = len(selected)
        for endpoint in ("unsafe_effect", "task_completion"):
            counts = Counter("true" if row.get(endpoint) is True else "false" if row.get(endpoint) is False else "unknown" for row in selected)
            cell[endpoint] = {name: counts[name] for name in ("true", "false", "unknown")}
        cell["operational_status"] = dict(Counter(row["operational_status"] for row in selected))
        cells.append(cell)
    return {"records": len(rows), "cells": cells}


def verify_raw(root: Path) -> dict:
    return {name: derive_counts(jsonl(root / relative)) for name, relative in RAW_FILES.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/portability/verification.json")
    args = parser.parse_args(argv)
    projections = verify_projections(ROOT / "fixtures/portability/current_online_inputs.jsonl")
    raw = verify_raw(ROOT)
    expected = json.loads((ROOT / "fixtures/portability/reference_counts.json").read_text(encoding="utf-8"))
    if raw != expected:
        raise ValueError("selected raw numerators/denominators differ from package build")
    data = {"environment": {"system": platform.system(), "release": platform.release(),
                            "machine": platform.machine(), "python": platform.python_version()},
            "projections": projections, "raw_counts": raw, "api_calls": 0,
            "scope": "compiler_projection_and_raw_counts_not_bootstrap_or_native_benchmark_evaluation"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"projections": projections, "raw_records": {name: value["records"] for name, value in raw.items()},
                      "api_calls": 0, "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
