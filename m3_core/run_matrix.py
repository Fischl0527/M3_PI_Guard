"""多条件/多模型交叉矩阵调度运行器（Run Matrix）。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from m3_core.llm_client import DEFAULT_MODEL
    from m3_core.run_batch import run_batch
    from m3_core.tool_sandbox import (
        CLEANUP_POLICY,
        FIXTURE_SHA256,
        FIXTURE_VERSION,
        ISOLATION_POLICY,
        SANDBOX_RUNTIME_VERSION,
        SECRET_POLICY,
        sandbox_seed_sha256,
    )
else:
    from .llm_client import DEFAULT_MODEL
    from .run_batch import run_batch
    from .tool_sandbox import (
        CLEANUP_POLICY,
        FIXTURE_SHA256,
        FIXTURE_VERSION,
        ISOLATION_POLICY,
        SANDBOX_RUNTIME_VERSION,
        SECRET_POLICY,
        sandbox_seed_sha256,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_VERSION = "v1.1-experiments"
GUARD_VERSION = "guard-v1.1-modular"
DATASET_VERSION = "cases-v1.1"
EXPERIMENT_VERSION = "exp-v1.1-reproducible"
SUPPORTED_GUARD_MODES = {
    "off",
    "keyword_only",
    "policy_only",
    "detector_only",
    "full_guard",
    "no_dataflow",
    "no_intent_action",
    "no_structured_detector",
    "no_multilingual_detector",
}

CONFIG = {
    "cases": "fixtures/demo_cases.jsonl",
    "backend": "stub",
    "model": "",
    "defense_modes": "baseline,full_guard",
    "conditions": "",
    "condition_label": "",
    "prompt_profiles": "",
    "guard_modes": "",
    "guard_modules": "",
    "ask_threshold": 0.35,
    "deny_threshold": 0.65,
    "families": "",
    "splits": "",
    "sample_types": "",
    "task_types": "",
    "case_ids": "",
    "limit": None,
    "out_dir": "outputs/runs/day6_demo_stub_matrix",
    "max_steps": 5,
    "recover_guard_stops": False,
    "max_guard_recoveries": 2,
    "recover_incomplete_tasks": False,
    "max_task_recoveries": 2,
    "recover_parse_errors": False,
    "max_parse_recoveries": 2,
    "run_prefix": "day6_demo_stub",
    "run_group": "day6",
    "seed": 42,
    "selection_seed": 42,
    "generation_seed": 42,
    "repeats": 1,
    "temperature": 0.2,
    "max_tokens": 512,
    "num_ctx": None,
    "ollama_transport": "openai_compat",
    "timeout": 120.0,
    "shuffle": False,
    "resume": False,
    "fail_fast": False,
    "allow_fallback_guard": False,
    "notes": "Recoverable experiment matrix",
}


def main(argv: List[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    config = _parse_args(argv) if argv else dict(CONFIG)
    result = run_matrix(config)
    print(
        f"OK: processed {len(result['results'])} conditions, "
        f"status={result['manifest']['status']}, manifest={result['manifest_path']}"
    )


def run_matrix(config: Dict[str, Any]) -> Dict[str, Any]:
    cases_path = _repo_path(str(config["cases"]))
    out_dir = _repo_path(str(config["out_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    if not cases_path.exists():
        raise FileNotFoundError(cases_path)

    backend = str(config.get("backend", "stub")).strip().lower()
    model = _resolve_model(backend, str(config.get("model", "")))
    conditions = _conditions(config)
    run_prefix = str(config.get("run_prefix") or _default_run_prefix(backend))
    manifest_path = out_dir / "manifest.json"
    request_config = _request_config(config, cases_path, backend, model, conditions)
    config_hash = _json_hash(request_config)
    resume = bool(config.get("resume", False))

    manifest: Dict[str, Any]
    if resume and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key, expected in _sandbox_manifest_fields(request_config).items():
            if manifest.get(key) != expected:
                raise RuntimeError(
                    f"Refusing to resume: manifest {key} does not match current sandbox identity"
                )
        existing_hash = str(manifest.get("config_hash", ""))
        if existing_hash != config_hash:
            raise RuntimeError(
                "Refusing to resume: manifest config_hash does not match current configuration"
            )
        manifest["status"] = "running"
        manifest["resumed_at"] = _utc_now()
        manifest["updated_at"] = _utc_now()
    else:
        manifest = _initial_manifest(
            config=config,
            request_config=request_config,
            config_hash=config_hash,
            cases_path=cases_path,
            backend=backend,
            model=model,
            conditions=conditions,
            run_prefix=run_prefix,
        )
    _write_json_atomic(manifest_path, manifest)

    results: List[Dict[str, Any]] = []
    for condition in conditions:
        entry = _condition_entry(manifest, condition["condition_id"])
        entry["status"] = "running"
        entry["started_at"] = _utc_now()
        entry["updated_at"] = _utc_now()
        _write_json_atomic(manifest_path, manifest)

        suffix = _safe_name(condition.get("output_suffix", condition["condition_id"]))
        jsonl_path = out_dir / f"{run_prefix}_{suffix}.jsonl"
        csv_path = out_dir / f"{run_prefix}_{suffix}.csv"
        batch_config = {
            "cases": str(cases_path),
            "backend": backend,
            "model": model,
            "defense": _legacy_defense(condition["guard_mode"]),
            "prompt_profile": condition["prompt_profile"],
            "guard_mode": condition["guard_mode"],
            "guard_modules": config.get("guard_modules") or "",
            "ask_threshold": float(config.get("ask_threshold", 0.35)),
            "deny_threshold": float(config.get("deny_threshold", 0.65)),
            "allow_fallback_guard": bool(config.get("allow_fallback_guard", False)),
            "condition_id": condition["condition_id"],
            "out": str(jsonl_path),
            "csv_out": str(csv_path),
            "max_steps": int(config.get("max_steps", 5)),
            "recover_guard_stops": bool(config.get("recover_guard_stops", False)),
            "max_guard_recoveries": int(config.get("max_guard_recoveries", 2)),
            "recover_incomplete_tasks": bool(config.get("recover_incomplete_tasks", False)),
            "max_task_recoveries": int(config.get("max_task_recoveries", 2)),
            "recover_parse_errors": bool(config.get("recover_parse_errors", False)),
            "max_parse_recoveries": int(config.get("max_parse_recoveries", 2)),
            "limit": config.get("limit"),
            "families": str(config.get("families") or ""),
            "splits": str(config.get("splits") or ""),
            "sample_types": str(config.get("sample_types") or ""),
            "task_types": str(config.get("task_types") or ""),
            "case_ids": str(config.get("case_ids") or ""),
            "seed": int(config.get("seed", 42)),
            "selection_seed": int(
                config.get("selection_seed")
                if config.get("selection_seed") is not None
                else config.get("seed", 42)
            ),
            "generation_seed": int(
                config.get("generation_seed")
                if config.get("generation_seed") is not None
                else config.get("seed", 42)
            ),
            "repeats": int(config.get("repeats", 1)),
            "shuffle": bool(config.get("shuffle", False)),
            "resume": resume,
            "fail_fast": bool(config.get("fail_fast", False)),
            "experiment_id": run_prefix,
            "experiment_version": EXPERIMENT_VERSION,
            "project_version": PROJECT_VERSION,
            "guard_version": GUARD_VERSION,
            "dataset_version": DATASET_VERSION,
            "case_source": _relative_or_name(cases_path),
            "run_group": str(config.get("run_group") or "experiment"),
            "temperature": float(config.get("temperature", 0.2)),
            "max_tokens": int(config.get("max_tokens", 512)),
            "num_ctx": config.get("num_ctx"),
            "ollama_transport": str(
                config.get("ollama_transport") or "openai_compat"
            ),
            "timeout": float(config.get("timeout", 120.0)),
        }

        try:
            batch_result = run_batch(batch_config)
            status = "completed" if batch_result["error_count"] == 0 else "failed"
            result = {
                "condition_id": condition["condition_id"],
                "prompt_profile": condition["prompt_profile"],
                "guard_mode": condition["guard_mode"],
                "defense_mode": batch_config["defense"],
                "status": status,
                "jsonl": _relative_or_name(jsonl_path),
                "csv": _relative_or_name(csv_path),
                "jsonl_sha256": _file_sha256(jsonl_path),
                "csv_sha256": _file_sha256(csv_path),
                **_sandbox_manifest_fields(request_config),
                **{
                    key: batch_result[key]
                    for key in (
                        "case_count",
                        "selected_case_count",
                        "selected_run_count",
                        "skipped_case_count",
                        "completed_run_count",
                        "error_count",
                        "log_count",
                    )
                    if key in batch_result
                },
            }
        except Exception as exc:
            status = "failed"
            result = {
                "condition_id": condition["condition_id"],
                "prompt_profile": condition["prompt_profile"],
                "guard_mode": condition["guard_mode"],
                "status": status,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            entry.update(result)
            entry["completed_at"] = _utc_now()
            entry["updated_at"] = _utc_now()
            manifest["status"] = "failed"
            manifest["updated_at"] = _utc_now()
            _write_json_atomic(manifest_path, manifest)
            results.append(result)
            if bool(config.get("fail_fast", False)):
                raise
            continue

        entry.update(result)
        entry["completed_at"] = _utc_now()
        entry["updated_at"] = _utc_now()
        results.append(result)
        manifest["updated_at"] = _utc_now()
        _write_json_atomic(manifest_path, manifest)

    manifest["status"] = (
        "completed"
        if all(item.get("status") == "completed" for item in manifest["conditions"])
        else "failed"
    )
    manifest["completed_at"] = _utc_now()
    manifest["updated_at"] = _utc_now()
    manifest["results"] = results
    _write_json_atomic(manifest_path, manifest)
    return {
        "manifest_path": _relative_or_name(manifest_path),
        "manifest": manifest,
        "results": results,
    }


def _initial_manifest(
    *,
    config: Dict[str, Any],
    request_config: Dict[str, Any],
    config_hash: str,
    cases_path: Path,
    backend: str,
    model: str,
    conditions: List[Dict[str, str]],
    run_prefix: str,
) -> Dict[str, Any]:
    git = _git_state()
    return {
        "schema_version": "1.1",
        "run_prefix": run_prefix,
        "experiment_id": run_prefix,
        "experiment_version": EXPERIMENT_VERSION,
        "project_version": PROJECT_VERSION,
        "guard_version": GUARD_VERSION,
        "dataset_version": DATASET_VERSION,
        "status": "running",
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "config": request_config,
        "config_hash": config_hash,
        **_sandbox_manifest_fields(request_config),
        "git_commit": git["commit"],
        "git_dirty": git["dirty"],
        "dataset": {
            "path": _relative_or_name(cases_path),
            "sha256": _file_sha256(cases_path),
            "row_count": _jsonl_row_count(cases_path),
        },
        "backend": backend,
        "oracle_stub": backend == "stub",
        "evidence_tier": "regression_only" if backend == "stub" else "formal_model",
        "model": model,
        "model_identity": _model_identity(backend, model),
        "defense_modes": [_legacy_defense(item["guard_mode"]) for item in conditions],
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "run_group": str(config.get("run_group") or "experiment"),
        "notes": str(config.get("notes") or ""),
        "conditions": [
            {
                **condition,
                "guard_modules": _resolved_guard_modules(
                    condition["guard_mode"], config.get("guard_modules")
                ),
                "ask_threshold": float(config.get("ask_threshold", 0.35)),
                "deny_threshold": float(config.get("deny_threshold", 0.65)),
                "status": "pending",
            }
            for condition in conditions
        ],
        "results": [],
    }


def _request_config(
    config: Dict[str, Any],
    cases_path: Path,
    backend: str,
    model: str,
    conditions: List[Dict[str, str]],
) -> Dict[str, Any]:
    generation_seed = int(
        config.get("generation_seed")
        if config.get("generation_seed") is not None
        else config.get("seed", 42)
    )
    repeats = int(config.get("repeats", 1))
    return {
        "cases": _relative_or_name(cases_path),
        "dataset_sha256": _file_sha256(cases_path),
        "implementation_sha256": _implementation_sha256(),
        "backend": backend,
        "model": model,
        "run_prefix": str(config.get("run_prefix") or _default_run_prefix(backend)),
        "run_group": str(config.get("run_group") or "experiment"),
        "conditions": conditions,
        "guard_modules": sorted(_csv_values(config.get("guard_modules"))),
        "ask_threshold": float(config.get("ask_threshold", 0.35)),
        "deny_threshold": float(config.get("deny_threshold", 0.65)),
        "max_steps": int(config.get("max_steps", 5)),
        "recover_guard_stops": bool(config.get("recover_guard_stops", False)),
        "max_guard_recoveries": int(config.get("max_guard_recoveries", 2)),
        "recover_incomplete_tasks": bool(config.get("recover_incomplete_tasks", False)),
        "max_task_recoveries": int(config.get("max_task_recoveries", 2)),
        "recover_parse_errors": bool(config.get("recover_parse_errors", False)),
        "max_parse_recoveries": int(config.get("max_parse_recoveries", 2)),
        "limit": config.get("limit"),
        "families": _csv_values(config.get("families")),
        "splits": _csv_values(config.get("splits")),
        "sample_types": _csv_values(config.get("sample_types")),
        "task_types": _csv_values(config.get("task_types")),
        "case_ids": _csv_values(config.get("case_ids")),
        "shuffle": bool(config.get("shuffle", False)),
        "selection_seed": int(
            config.get("selection_seed")
            if config.get("selection_seed") is not None
            else config.get("seed", 42)
        ),
        "generation_seed": generation_seed,
        "repeats": repeats,
        "temperature": float(config.get("temperature", 0.2)),
        "max_tokens": int(config.get("max_tokens", 512)),
        "num_ctx": config.get("num_ctx"),
        "ollama_transport": str(
            config.get("ollama_transport") or "openai_compat"
        ),
        "timeout": float(config.get("timeout", 120.0)),
        "allow_fallback_guard": bool(config.get("allow_fallback_guard", False)),
        **_sandbox_identity(generation_seed, repeats),
    }


def _sandbox_identity(generation_seed: int, repeats: int) -> Dict[str, Any]:
    return {
        "sandbox_runtime_version": SANDBOX_RUNTIME_VERSION,
        "sandbox_fixture_version": FIXTURE_VERSION,
        "sandbox_fixture_sha256": FIXTURE_SHA256,
        "sandbox_seed_sha256": {
            str(generation_seed + replicate_id): sandbox_seed_sha256(
                generation_seed + replicate_id
            )
            for replicate_id in range(repeats)
        },
        "sandbox_isolation_policy": ISOLATION_POLICY,
        "sandbox_secret_policy": SECRET_POLICY,
        "sandbox_cleanup_policy": CLEANUP_POLICY,
    }


def _sandbox_manifest_fields(request_config: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "sandbox_runtime_version",
        "sandbox_fixture_version",
        "sandbox_fixture_sha256",
        "sandbox_seed_sha256",
        "sandbox_isolation_policy",
        "sandbox_secret_policy",
        "sandbox_cleanup_policy",
    )
    return {key: request_config[key] for key in keys}


def _conditions(config: Dict[str, Any]) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    explicit = _csv_values(config.get("conditions"))
    if explicit:
        for item in explicit:
            explicit_id, equals, specification = item.partition("=")
            if not equals:
                explicit_id = ""
                specification = item
            profile, separator, mode = specification.partition(":")
            if not separator:
                raise ValueError("conditions must use prompt_profile:guard_mode")
            result.append(_condition(profile, mode, condition_id=explicit_id))
    elif _csv_values(config.get("prompt_profiles")) or _csv_values(config.get("guard_modes")):
        profiles = _csv_values(config.get("prompt_profiles")) or ["normal"]
        modes = _csv_values(config.get("guard_modes")) or ["off"]
        for profile in profiles:
            for mode in modes:
                result.append(_condition(profile, mode))
    else:
        for defense in _defense_modes(config.get("defense_modes")):
            if defense == "baseline":
                result.append(_condition("normal", "off", output_suffix="baseline"))
            elif defense in {"guarded", "full_guard"}:
                result.append(_condition("hardened", "full_guard", output_suffix="full_guard"))
            else:
                result.append(_condition("hardened", defense, output_suffix=defense))

    label = str(config.get("condition_label") or "").strip()
    module_override = sorted(_csv_values(config.get("guard_modules")))
    nondefault_threshold = (
        float(config.get("ask_threshold", 0.35)) != 0.35
        or float(config.get("deny_threshold", 0.65)) != 0.65
    )
    if label:
        for item in result:
            item["condition_id"] = (
                label if len(result) == 1 else f"{label}__{item['condition_id']}"
            )
            item.pop("output_suffix", None)
    else:
        if module_override:
            module_label = "_".join(module_override)
            if len(module_label) > 80:
                module_label = hashlib.sha256(module_label.encode("utf-8")).hexdigest()[:12]
            for item in result:
                if item.get("_explicit_id") != "true":
                    item["condition_id"] += f"__modules_{module_label}"
                    item.pop("output_suffix", None)
        if nondefault_threshold:
            threshold_label = (
                f"ask_{float(config.get('ask_threshold', 0.35)):g}"
                f"__deny_{float(config.get('deny_threshold', 0.65)):g}"
            )
            for item in result:
                if item.get("_explicit_id") != "true":
                    item["condition_id"] += f"__{threshold_label}"
                    item.pop("output_suffix", None)

    unique: Dict[str, Dict[str, str]] = {}
    for item in result:
        item.pop("_explicit_id", None)
        unique[item["condition_id"]] = item
    if not unique:
        raise ValueError("At least one experiment condition is required")
    return list(unique.values())


def _condition(
    profile: str,
    mode: str,
    *,
    output_suffix: str = "",
    condition_id: str = "",
) -> Dict[str, str]:
    profile = str(profile).strip().lower()
    mode = str(mode).strip().lower()
    mode = "off" if mode == "baseline" else "full_guard" if mode == "guarded" else mode
    if profile not in {"normal", "hardened"}:
        raise ValueError(f"Unsupported prompt profile: {profile}")
    if mode not in SUPPORTED_GUARD_MODES:
        raise ValueError(f"Unsupported Guard mode: {mode}")
    result = {
        "condition_id": condition_id or f"{profile}__{mode}",
        "prompt_profile": profile,
        "guard_mode": mode,
    }
    if condition_id:
        result["_explicit_id"] = "true"
    if output_suffix:
        result["output_suffix"] = output_suffix
    return result


def _parse_args(argv: List[str]) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run a recoverable M3 experiment matrix.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--backend", choices=["ollama", "stub"], default="stub")
    parser.add_argument("--model", default="")
    parser.add_argument("--defense-modes", default="baseline,keyword_only,policy_only,full_guard")
    parser.add_argument("--conditions", default="", help="Comma-separated normal:off style pairs")
    parser.add_argument(
        "--condition-label",
        default="",
        help="Explicit logical id for a single ablation/threshold condition",
    )
    parser.add_argument("--prompt-profiles", default="")
    parser.add_argument("--guard-modes", default="")
    parser.add_argument("--guard-modules", default="")
    parser.add_argument("--ask-threshold", type=float, default=0.35)
    parser.add_argument("--deny-threshold", type=float, default=0.65)
    parser.add_argument("--families", default="")
    parser.add_argument("--splits", default="")
    parser.add_argument("--sample-types", default="")
    parser.add_argument("--task-types", default="")
    parser.add_argument("--case-ids", default="")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--recover-guard-stops", action="store_true")
    parser.add_argument("--max-guard-recoveries", type=int, default=2)
    parser.add_argument("--recover-incomplete-tasks", action="store_true")
    parser.add_argument("--max-task-recoveries", type=int, default=2)
    parser.add_argument("--recover-parse-errors", action="store_true")
    parser.add_argument("--max-parse-recoveries", type=int, default=2)
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--run-group", default="experiment")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--selection-seed", type=int)
    parser.add_argument("--generation-seed", type=int)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--num-ctx", type=int)
    parser.add_argument(
        "--ollama-transport",
        choices=["openai_compat", "native"],
        default="openai_compat",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--allow-fallback-guard", action="store_true")
    parser.add_argument("--notes", default="Recoverable experiment matrix")
    args = vars(parser.parse_args(argv))
    if args["selection_seed"] is None:
        args["selection_seed"] = args["seed"]
    if args["generation_seed"] is None:
        args["generation_seed"] = args["seed"]
    return args


def _defense_modes(value: Any) -> List[str]:
    modes: List[str] = []
    supported = SUPPORTED_GUARD_MODES | {"baseline", "guarded"}
    for item in _csv_values(value):
        mode = item.strip().lower()
        if mode not in supported:
            raise ValueError(f"Unsupported defense mode: {item}")
        if mode not in modes:
            modes.append(mode)
    return modes


def _legacy_defense(guard_mode: str) -> str:
    if guard_mode == "off":
        return "baseline"
    return guard_mode


def _resolved_guard_modules(mode: str, override: Any) -> List[str]:
    from m3_guard.config import GuardConfig

    return sorted(GuardConfig.resolve(mode, modules=override or None).modules or [])


def _condition_entry(manifest: Dict[str, Any], condition_id: str) -> Dict[str, Any]:
    for entry in manifest.get("conditions", []):
        if entry.get("condition_id") == condition_id:
            return entry
    raise KeyError(condition_id)


def _git_state() -> Dict[str, Any]:
    commit = _command_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT) or "unknown"
    dirty = bool(_command_output(["git", "status", "--porcelain"], cwd=REPO_ROOT))
    return {"commit": commit, "dirty": dirty}


def _model_identity(backend: str, model: str) -> Dict[str, Any]:
    if backend == "stub":
        return {"tag": "stub", "digest": _git_state()["commit"], "ollama_version": "not_applicable"}
    executable = _ollama_executable()
    if not executable:
        return {
            "tag": model,
            "digest": "unknown",
            "ollama_version": "unknown",
            "executable": "not_found",
        }
    version = _command_output([executable, "--version"], cwd=REPO_ROOT)
    details = _command_output([executable, "show", model, "--json"], cwd=REPO_ROOT)
    digest = hashlib.sha256(details.encode("utf-8")).hexdigest() if details else ""
    if not digest:
        listing = _command_output([executable, "list"], cwd=REPO_ROOT)
        digest = _digest_from_ollama_list(listing, model)
    return {
        "tag": model,
        "digest": digest or "unknown",
        "ollama_version": version or "unknown",
        "executable": executable,
    }


def _ollama_executable() -> str:
    configured = os.getenv("M3_OLLAMA_EXE", "").strip()
    candidates = [
        configured,
        shutil.which("ollama") or "",
        r"D:\Ollama\app\ollama.exe",
        str(Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"),
        str(Path(os.getenv("LOCALAPPDATA", "")) / "Ollama" / "ollama.exe"),
        str(Path(os.getenv("ProgramFiles", "")) / "Ollama" / "ollama.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    return ""


def _digest_from_ollama_list(listing: str, model: str) -> str:
    for line in listing.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 2 and columns[0] == model:
            return columns[1]
    return ""


def _command_output(command: List[str], *, cwd: Path) -> str:
    try:
        return subprocess.check_output(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except Exception:
        return ""


def _write_json_atomic(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(path)


def _file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonl_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _implementation_sha256() -> str:
    digest = hashlib.sha256()
    paths: List[Path] = []
    for relative in ("m3_core", "m3_guard", "schemas"):
        root = REPO_ROOT / relative
        if root.exists():
            paths.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix.lower() in {".py", ".json"}
            )
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(REPO_ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _resolve_model(backend: str, model: str) -> str:
    return model.strip() or ("stub" if backend == "stub" else DEFAULT_MODEL)


def _default_run_prefix(backend: str) -> str:
    return "experiment_stub" if backend == "stub" else "experiment_ollama"


def _csv_values(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _relative_or_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


if __name__ == "__main__":
    main()
