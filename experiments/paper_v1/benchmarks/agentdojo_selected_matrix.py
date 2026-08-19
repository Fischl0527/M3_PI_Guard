"""Resume-safe AgentDojo diagnostic runner for exact selected clusters."""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from m3_guard.task_policy import canonical_json

from .agentdojo_native_matrix import DEFAULT_OUTPUT
from .agentdojo_native_runner import DEFAULT_AGENTDOJO, run_agentdojo_native_smoke


SELECTED_MATRIX_VERSION = "m3-paper-v1-agentdojo-selected-matrix-1.0"


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _selected_clusters(selection: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    repeat = selection["same_configuration_repeat"]
    clusters: list[tuple[str, str, str, str]] = []
    for role, items in (
        ("positive", repeat["positive_clusters"]),
        ("zero_control", repeat["zero_control_clusters"]),
    ):
        for suite, user_task_id, injection_task_id in items:
            clusters.append((str(suite), str(user_task_id), str(injection_task_id), role))
    deduped: dict[tuple[str, str, str], tuple[str, str, str, str]] = {}
    for suite, user_task_id, injection_task_id, role in clusters:
        key = (suite, user_task_id, injection_task_id)
        prior = deduped.get(key)
        if prior and prior[3] != role:
            raise ValueError(f"cluster is both positive and zero_control: {key}")
        deduped[key] = (suite, user_task_id, injection_task_id, role)
    return [deduped[key] for key in sorted(deduped)]


def build_selected_jobs(
    selection: dict[str, Any],
    *,
    repeats: int | None = None,
    defenses: list[str] | None = None,
) -> list[dict[str, Any]]:
    repeat = selection["same_configuration_repeat"]
    repeat_count = int(repeats or repeat["minimum_seeds"])
    if repeat_count < 1:
        raise ValueError("repeats must be positive")
    defense_ids = defenses or [str(item) for item in repeat["defenses"]]
    jobs: list[dict[str, Any]] = []
    for replicate_id in range(repeat_count):
        for suite, user_task_id, injection_task_id, role in _selected_clusters(selection):
            for defense_id in defense_ids:
                jobs.append(
                    {
                        "suite": suite,
                        "user_task_id": user_task_id,
                        "injection_task_id": injection_task_id,
                        "cluster_role": role,
                        "defense_id": defense_id,
                        "replicate_id": replicate_id,
                    }
                )
    return jobs


def _job_key(job: dict[str, Any]) -> str:
    return "__".join(
        (
            _slug(str(job["suite"])),
            _slug(str(job["defense_id"])),
            _slug(str(job["user_task_id"])),
            _slug(str(job["injection_task_id"])),
            f"r{int(job.get('replicate_id') or 0)}",
        )
    )


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "completed":
            grouped[(str(row["suite"]), str(row["defense_id"]))].append(row)
    for (suite, defense), subset in sorted(grouped.items()):
        key = f"{suite}::{defense}"
        total = len(subset)
        summary[key] = {
            "suite": suite,
            "defense_id": defense,
            "completed_jobs": total,
            "injection_success_n": sum(
                bool(row.get("official_injection_success")) for row in subset
            ),
            "attack_block_n": sum(bool(row.get("attack_blocked")) for row in subset),
            "utility_n": sum(bool(row.get("utility")) for row in subset),
            "injection_success_rate": (
                sum(bool(row.get("official_injection_success")) for row in subset) / total
                if total
                else None
            ),
            "utility_rate": (
                sum(bool(row.get("utility")) for row in subset) / total
                if total
                else None
            ),
        }
    return summary


def run_selected_matrix(
    *,
    selection_path: Path,
    checkout: Path,
    output_dir: Path,
    backend: str,
    model: str | None,
    temperature: float | None,
    seed: int,
    max_steps: int | None,
    attack_name: str | None,
    repeats: int | None,
    defenses: list[str] | None = None,
    resume: bool = True,
) -> dict[str, Any]:
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    repeat = selection["same_configuration_repeat"]
    defense_ids = defenses or [str(item) for item in repeat["defenses"]]
    jobs = build_selected_jobs(selection, repeats=repeats, defenses=defense_ids)
    run_model = model or repeat["model"]
    run_temperature = float(temperature if temperature is not None else repeat["temperature"])
    run_max_steps = int(max_steps or repeat["max_steps"])
    run_attack = attack_name or repeat["attack"]
    config = {
        "selection_path": str(selection_path.resolve()),
        "selection_sha256": _sha256(selection),
        "checkout": str(checkout.resolve()),
        "backend": backend,
        "model": run_model,
        "temperature": run_temperature,
        "seed": seed,
        "max_steps": run_max_steps,
        "attack_name": run_attack,
        "defense_ids": list(defense_ids),
        "repeats": int(repeats or repeat["minimum_seeds"]),
        "cluster_count": len(_selected_clusters(selection)),
        "positive_cluster_count": len(repeat["positive_clusters"]),
        "zero_control_cluster_count": len(repeat["zero_control_clusters"]),
    }
    config_sha256 = _sha256(config)
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("config_sha256") != config_sha256:
            raise ValueError("refusing to resume selected matrix with configuration drift")

    output_dir.mkdir(parents=True, exist_ok=True)
    job_rows: list[dict[str, Any]] = []
    for index, job in enumerate(jobs, 1):
        key = _job_key(job)
        job_dir = output_dir / "jobs" / key
        job_manifest = job_dir / "manifest.json"
        if resume and job_manifest.exists():
            prior = json.loads(job_manifest.read_text(encoding="utf-8"))
            if prior.get("status") == "completed":
                job_rows.append({"job_key": key, **job, **prior})
                continue
        try:
            result = run_agentdojo_native_smoke(
                checkout=checkout,
                output_dir=job_dir,
                suite_name=str(job["suite"]),
                user_task_id=str(job["user_task_id"]),
                injection_task_id=str(job["injection_task_id"]),
                attack_name=run_attack,
                defense_id=str(job["defense_id"]),
                backend=backend,
                model=run_model,
                temperature=run_temperature,
                seed=seed + int(job.get("replicate_id") or 0),
                max_steps=run_max_steps,
            )
            job_rows.append({"job_key": key, **job, **result})
        except Exception as exc:
            failure = {
                "status": "failed",
                "job_key": key,
                **job,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(job_dir / "failure.json", failure)
            job_rows.append(failure)
        checkpoint = {
            "schema_version": "paper-agentdojo-selected-matrix-1.0",
            "matrix_version": SELECTED_MATRIX_VERSION,
            "evidence_status": "diagnostic_not_formal_benchmark",
            "status": "running",
            "config": config,
            "config_sha256": config_sha256,
            "total_jobs": len(jobs),
            "processed_jobs": index,
            "jobs": job_rows,
            "summary_by_suite_defense": _summaries(job_rows),
            "result_eligible_for_formal_tables": False,
        }
        _write_json(manifest_path, checkpoint)

    failed = [row for row in job_rows if row.get("status") != "completed"]
    manifest = {
        "schema_version": "paper-agentdojo-selected-matrix-1.0",
        "matrix_version": SELECTED_MATRIX_VERSION,
        "evidence_status": "diagnostic_not_formal_benchmark",
        "status": "completed" if not failed else "completed_with_failures",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "config_sha256": config_sha256,
        "total_jobs": len(jobs),
        "completed_jobs": len(job_rows) - len(failed),
        "failed_jobs": len(failed),
        "jobs": job_rows,
        "summary_by_suite_defense": _summaries(job_rows),
        "result_eligible_for_formal_tables": False,
    }
    _write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", type=Path)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_AGENTDOJO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT / "selected_matrix")
    parser.add_argument("--backend", choices=["ollama", "stub"], default="ollama")
    parser.add_argument("--model", default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--seed", type=int, default=20260718)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--attack", default=None)
    parser.add_argument("--repeats", type=int, default=None)
    parser.add_argument(
        "--defenses",
        default=None,
        help="Comma-separated defense ids. Defaults to the selection file defenses.",
    )
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    manifest = run_selected_matrix(
        selection_path=args.selection,
        checkout=args.checkout,
        output_dir=args.output_dir,
        backend=args.backend,
        model=args.model,
        temperature=args.temperature,
        seed=args.seed,
        max_steps=args.max_steps,
        attack_name=args.attack,
        repeats=args.repeats,
        defenses=(
            [item.strip() for item in args.defenses.split(",") if item.strip()]
            if args.defenses
            else None
        ),
        resume=not args.no_resume,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
