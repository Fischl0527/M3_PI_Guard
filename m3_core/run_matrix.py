"""Experiment matrix runner for M3_PI_Guard.
This module keeps run_batch.py as the single-case-set executor, and adds a
thin orchestration layer for repeated ablation runs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from m3_core.llm_client import DEFAULT_MODEL
    from m3_core.run_batch import run_batch
else:
    from .llm_client import DEFAULT_MODEL
    from .run_batch import run_batch


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_VERSION = "v1.0-day6"
GUARD_VERSION = "guard-v1.0"
DATASET_VERSION = "cases-v1.0"
EXPERIMENT_VERSION = "exp-day6-release"
SUPPORTED_DEFENSE_MODES = {
    "baseline",
    "guarded",
    "keyword_only",
    "policy_only",
    "full_guard",
}

# 直接运行本文件时优先修改这里。命令行参数仍然可用于脚本和自动化。
CONFIG = {
    "cases": "fixtures/demo_cases.jsonl",
    "backend": "stub",
    "model": "",
    "defense_modes": "baseline,full_guard",
    "families": "",
    "limit": None,
    "out_dir": "outputs/runs/day6_demo_stub_matrix",
    "max_steps": 5,
    "run_prefix": "day6_demo_stub",
    "run_group": "day6",
    "seed": 42,
    "shuffle": False,
    "resume": False,
    "fail_fast": False,
    "notes": "DAY6 release validation demo run",
}


def main(argv: List[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    config = _parse_args(argv) if argv else dict(CONFIG)
    result = run_matrix(config)
    print(
        f"OK: ran {len(result['results'])} defense modes, "
        f"manifest={result['manifest_path']}"
    )
    for item in result["results"]:
        print(
            f"  {item['defense_mode']}: {item['jsonl']} "
            f"({item['log_count']} log rows)"
        )


def run_matrix(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run one case set under multiple defense modes and write a manifest."""

    cases_path = _repo_path(str(config["cases"]))
    out_dir = _repo_path(str(config["out_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)

    backend = str(config.get("backend", "stub")).strip().lower()
    model = _resolve_model(backend, str(config.get("model", "")))
    defense_modes = _defense_modes(config.get("defense_modes"))
    run_prefix = str(config.get("run_prefix") or _default_run_prefix(backend))
    max_steps = int(config.get("max_steps", 5))
    run_group = str(config.get("run_group") or "day5")

    results: List[Dict[str, Any]] = []
    for defense_mode in defense_modes:
        # 每个 mode 复用 run_batch，保证 DAY2/DAY3 的批跑逻辑不分叉。
        jsonl_path = out_dir / f"{run_prefix}_{defense_mode}.jsonl"
        csv_path = out_dir / f"{run_prefix}_{defense_mode}.csv"
        batch_config = {
            "cases": str(cases_path),
            "backend": backend,
            "model": model,
            "defense": defense_mode,
            "out": str(jsonl_path),
            "csv_out": str(csv_path),
            "max_steps": max_steps,
            "limit": config.get("limit"),
            "families": str(config.get("families") or ""),
            "case_ids": str(config.get("case_ids") or ""),
            "seed": int(config.get("seed", 42)),
            "shuffle": bool(config.get("shuffle", False)),
            "resume": bool(config.get("resume", False)),
            "fail_fast": bool(config.get("fail_fast", False)),
            "experiment_id": run_prefix,
            "experiment_version": EXPERIMENT_VERSION,
            "project_version": PROJECT_VERSION,
            "guard_version": GUARD_VERSION,
            "dataset_version": DATASET_VERSION,
            "case_source": _relative_or_name(cases_path),
            "run_group": run_group,
            "temperature": float(config.get("temperature", 0.2)),
        }
        batch_result = run_batch(batch_config)
        results.append(
            {
                "defense_mode": defense_mode,
                "jsonl": _relative_or_name(jsonl_path),
                "csv": _relative_or_name(csv_path),
                "case_count": batch_result["case_count"],
                "selected_case_count": batch_result["selected_case_count"],
                "skipped_case_count": batch_result["skipped_case_count"],
                "error_count": batch_result["error_count"],
                "log_count": batch_result["log_count"],
            }
        )

    manifest = {
        "run_prefix": run_prefix,
        "experiment_id": run_prefix,
        "experiment_version": EXPERIMENT_VERSION,
        "project_version": PROJECT_VERSION,
        "run_group": run_group,
        "backend": backend,
        "model": model,
        "cases": _relative_or_name(cases_path),
        "defense_modes": defense_modes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "guard_version": GUARD_VERSION,
        "dataset_version": DATASET_VERSION,
        "model_config": {
            "temperature": float(config.get("temperature", 0.2)),
            "max_steps": max_steps,
        },
        "filters": {
            "families": _csv_values(config.get("families")),
            "case_ids": _csv_values(config.get("case_ids")),
            "limit": config.get("limit"),
            "shuffle": bool(config.get("shuffle", False)),
            "seed": int(config.get("seed", 42)),
        },
        "notes": str(config.get("notes") or ""),
        "results": results,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "manifest_path": _relative_or_name(manifest_path),
        "manifest": manifest,
        "results": results,
    }


def _parse_args(argv: List[str]) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run M3 experiment matrix.")
    parser.add_argument("--cases", required=True, help="Input AttackCase JSONL path")
    parser.add_argument("--backend", choices=["ollama", "stub"], default="stub")
    parser.add_argument("--model", default="", help="Model name; defaults to stub or m3-target-qwen25-7b")
    parser.add_argument(
        "--defense-modes",
        default="baseline,keyword_only,policy_only,full_guard",
        help="Comma-separated modes: baseline,keyword_only,policy_only,full_guard",
    )
    parser.add_argument("--families", default="", help="Comma-separated attack_family filter")
    parser.add_argument("--case-ids", default="", help="Comma-separated case_id filter")
    parser.add_argument("--limit", type=int, help="Only run first N selected cases")
    parser.add_argument("--out-dir", required=True, help="Output directory for matrix logs")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--run-prefix", required=True, help="Prefix for output files and experiment_id")
    parser.add_argument("--run-group", default="day6", help="Run group label written to RunLog")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for --shuffle")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle selected cases before limit")
    parser.add_argument("--resume", action="store_true", help="Resume each output file by completed case_id")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failed case")
    parser.add_argument("--notes", default="DAY6 release validation demo run")
    args = parser.parse_args(argv)
    return vars(args)


def _defense_modes(value: Any) -> List[str]:
    modes = []
    for item in _csv_values(value):
        mode = "full_guard" if item == "guarded" else item
        if mode not in SUPPORTED_DEFENSE_MODES:
            raise SystemExit(f"Unsupported defense mode: {item}")
        if mode not in modes:
            modes.append(mode)
    if not modes:
        raise SystemExit("At least one defense mode is required")
    return modes


def _resolve_model(backend: str, model: str) -> str:
    model = model.strip()
    if model:
        return model
    return "stub" if backend == "stub" else DEFAULT_MODEL


def _default_run_prefix(backend: str) -> str:
    return "day6_demo_stub" if backend == "stub" else "day6_demo_qwen"


def _csv_values(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _git_commit() -> str:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return output.strip()
    except Exception:
        return "unknown"


def _relative_or_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


if __name__ == "__main__":
    main()
