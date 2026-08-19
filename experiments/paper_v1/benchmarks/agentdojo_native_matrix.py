"""Resume-safe diagnostic matrix for the native AgentDojo M3 adapter.

This runner keeps official utility and injection-success booleans intact while
adding unambiguous derived fields.  Outputs remain diagnostic until the formal
protocol is frozen and all declared jobs are complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from m3_guard.task_policy import canonical_json

from .agentdojo_native_runner import DEFAULT_AGENTDOJO, run_agentdojo_native_smoke


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs" / "paper_upgrade_v1" / "agentdojo_native_matrix"
MATRIX_VERSION = "m3-paper-v1-agentdojo-native-matrix-1.0"


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value).split(",") if item.strip())


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_jobs(
    *,
    user_task_ids: Iterable[str],
    injection_task_ids: Iterable[str],
    defense_ids: Iterable[str],
    include_utility: bool = True,
    repeats: int = 1,
) -> list[dict[str, Any]]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    jobs: list[dict[str, Any]] = []
    for replicate_id in range(repeats):
        for defense_id in defense_ids:
            for user_task_id in user_task_ids:
                if include_utility:
                    jobs.append(
                        {
                            "defense_id": defense_id,
                            "user_task_id": user_task_id,
                            "injection_task_id": None,
                            "replicate_id": replicate_id,
                        }
                    )
                for injection_task_id in injection_task_ids:
                    jobs.append(
                        {
                            "defense_id": defense_id,
                            "user_task_id": user_task_id,
                            "injection_task_id": injection_task_id,
                            "replicate_id": replicate_id,
                        }
                    )
    return jobs


def _job_key(job: dict[str, Any]) -> str:
    injection = job["injection_task_id"] or "clean"
    return "__".join(
        (
            _slug(str(job["defense_id"])),
            _slug(str(job["user_task_id"])),
            _slug(str(injection)),
            f"r{int(job.get('replicate_id') or 0)}",
        )
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    defenses = sorted({str(row["defense_id"]) for row in rows})
    for defense in defenses:
        subset = [row for row in rows if row["defense_id"] == defense and row["status"] == "completed"]
        clean = [row for row in subset if row.get("injection_task_id") is None]
        injected = [row for row in subset if row.get("injection_task_id") is not None]
        result[defense] = {
            "completed_jobs": len(subset),
            "clean_utility_n": len(clean),
            "clean_utility_rate": (
                sum(bool(row["utility"]) for row in clean) / len(clean) if clean else None
            ),
            "injected_utility_n": len(injected),
            "injected_utility_rate": (
                sum(bool(row["utility"]) for row in injected) / len(injected)
                if injected
                else None
            ),
            "injection_n": len(injected),
            "official_injection_success_rate": (
                sum(bool(row["official_injection_success"]) for row in injected)
                / len(injected)
                if injected
                else None
            ),
            "attack_block_rate": (
                sum(bool(row["attack_blocked"]) for row in injected) / len(injected)
                if injected
                else None
            ),
        }
    return result


def run_matrix(
    *,
    checkout: Path,
    output_dir: Path,
    suite_name: str,
    user_task_ids: tuple[str, ...],
    injection_task_ids: tuple[str, ...],
    defense_ids: tuple[str, ...],
    backend: str,
    model: str,
    temperature: float,
    seed: int,
    max_steps: int,
    attack_name: str = "direct",
    include_utility: bool = True,
    resume: bool = True,
    repeats: int = 1,
) -> dict[str, Any]:
    jobs = build_jobs(
        user_task_ids=user_task_ids,
        injection_task_ids=injection_task_ids,
        defense_ids=defense_ids,
        include_utility=include_utility,
        repeats=repeats,
    )
    config = {
        "checkout": str(checkout.resolve()),
        "suite": suite_name,
        "user_task_ids": list(user_task_ids),
        "injection_task_ids": list(injection_task_ids),
        "defense_ids": list(defense_ids),
        "backend": backend,
        "model": model,
        "temperature": temperature,
        "seed": seed,
        "max_steps": max_steps,
        "attack_name": attack_name,
        "include_utility": include_utility,
        "repeats": repeats,
    }
    config_sha256 = _sha256(config)
    root_manifest_path = output_dir / "manifest.json"
    if root_manifest_path.exists():
        existing = json.loads(root_manifest_path.read_text(encoding="utf-8"))
        if existing.get("config_sha256") != config_sha256:
            raise ValueError("refusing to resume AgentDojo matrix with configuration drift")

    output_dir.mkdir(parents=True, exist_ok=True)
    job_rows: list[dict[str, Any]] = []
    for index, job in enumerate(jobs, 1):
        key = _job_key(job)
        job_dir = output_dir / "jobs" / key
        job_manifest_path = job_dir / "manifest.json"
        if resume and job_manifest_path.exists():
            prior = json.loads(job_manifest_path.read_text(encoding="utf-8"))
            if prior.get("status") == "completed":
                job_rows.append({"job_key": key, **prior})
                continue
        try:
            result = run_agentdojo_native_smoke(
                checkout=checkout,
                output_dir=job_dir,
                suite_name=suite_name,
                user_task_id=str(job["user_task_id"]),
                injection_task_id=(
                    str(job["injection_task_id"])
                    if job["injection_task_id"] is not None
                    else None
                ),
                attack_name=attack_name,
                defense_id=str(job["defense_id"]),
                backend=backend,
                model=model,
                temperature=temperature,
                seed=seed + int(job.get("replicate_id") or 0),
                max_steps=max_steps,
            )
            job_rows.append({"job_key": key, **result})
        except Exception as exc:  # retain every failure for audit and later rerun
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
            "schema_version": "paper-agentdojo-native-matrix-1.0",
            "matrix_version": MATRIX_VERSION,
            "evidence_status": "diagnostic_not_formal_benchmark",
            "status": "running",
            "config": config,
            "config_sha256": config_sha256,
            "total_jobs": len(jobs),
            "processed_jobs": index,
            "jobs": job_rows,
            "summary_by_defense": _summaries(job_rows),
            "result_eligible_for_formal_tables": False,
        }
        _write_json(root_manifest_path, checkpoint)

    failed = [row for row in job_rows if row.get("status") != "completed"]
    manifest = {
        "schema_version": "paper-agentdojo-native-matrix-1.0",
        "matrix_version": MATRIX_VERSION,
        "evidence_status": "diagnostic_not_formal_benchmark",
        "status": "completed" if not failed else "completed_with_failures",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "config_sha256": config_sha256,
        "total_jobs": len(jobs),
        "completed_jobs": len(job_rows) - len(failed),
        "failed_jobs": len(failed),
        "jobs": job_rows,
        "summary_by_defense": _summaries(job_rows),
        "result_eligible_for_formal_tables": False,
    }
    _write_json(root_manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_AGENTDOJO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--suite", default="workspace")
    parser.add_argument(
        "--user-task-ids",
        default=",".join(f"user_task_{index}" for index in range(8)),
    )
    parser.add_argument("--injection-task-ids", default="injection_task_0")
    parser.add_argument("--defenses", default="no_defense,m3_full")
    parser.add_argument("--backend", choices=["ollama", "stub"], default="ollama")
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--attack", default="direct")
    parser.add_argument("--skip-utility", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    manifest = run_matrix(
        checkout=args.checkout,
        output_dir=args.output_dir,
        suite_name=args.suite,
        user_task_ids=_csv(args.user_task_ids),
        injection_task_ids=_csv(args.injection_task_ids),
        defense_ids=_csv(args.defenses),
        backend=args.backend,
        model=args.model,
        temperature=args.temperature,
        seed=args.seed,
        max_steps=args.max_steps,
        attack_name=args.attack,
        include_utility=not args.skip_utility,
        resume=not args.no_resume,
        repeats=args.repeats,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0 if manifest["failed_jobs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
