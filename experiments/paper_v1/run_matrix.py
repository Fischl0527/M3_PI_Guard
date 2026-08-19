"""Resume-safe paper-v1 matrix runner for the local M3-v2 protocol.

The runner never projects offline evaluator labels into the Agent or policy
compiler.  Failed cases remain explicit and keep the experiment manifest in a
failed state until they are successfully retried.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from m3_core.policy_compiler import DEFAULT_TOOL_SCHEMAS
from m3_core.policy_regimes import POLICY_REGIMES, build_policy_regime
from m3_core.research_runner import run_research_case

from .benchmarks.common import portable_path
from .llm_client import PaperLLMClient


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "m3_attacks" / "cases" / "paper_v1" / "m3_v2_validation.jsonl"
DEFAULT_BASELINES = ROOT / "protocols" / "paper_upgrade_v1" / "baseline_registry.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "paper_upgrade_v1" / "matrix"
CODE_PATHS = (
    ROOT / "m3_core" / "policy_compiler.py",
    ROOT / "m3_core" / "policy_regimes.py",
    ROOT / "m3_core" / "research_runner.py",
    ROOT / "m3_guard" / "task_policy.py",
    ROOT / "m3_guard" / "provenance.py",
    ROOT / "m3_guard" / "runtime_monitor.py",
    ROOT / "m3_eval" / "paper_metrics.py",
    ROOT / "m3_eval" / "paper_statistics.py",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(_canonical(dict(value)) + "\n")
        stream.flush()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _ollama_version() -> str:
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (result.stdout or result.stderr).strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unavailable"


def _code_freeze_sha256() -> str:
    records = [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256_file(path)}
        for path in CODE_PATHS
    ]
    return _sha256_bytes(_canonical(records).encode("utf-8"))


def _load_conditions(path: Path, selected: Iterable[str]) -> list[dict[str, Any]]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    ready = {
        str(row["id"]): row
        for row in registry["conditions"]
        if row.get("implementation_status") == "ready"
    }
    names = list(dict.fromkeys(selected))
    missing = [name for name in names if name not in ready]
    if missing:
        raise ValueError(
            "condition is unavailable or not exactly adapted: " + ", ".join(missing)
        )
    return [ready[name] for name in names]


def _run_key(
    *,
    experiment_id: str,
    case_id: str,
    model: str,
    condition: str,
    regime: str,
    replicate_id: int,
    seed: int,
    temperature: float,
    think: bool | None,
) -> str:
    payload = {
        "experiment_id": experiment_id,
        "case_id": case_id,
        "model": model,
        "condition": condition,
        "policy_regime": regime,
        "replicate_id": replicate_id,
        "seed": seed,
        "temperature": temperature,
        "think": think,
    }
    return "matrix-" + _sha256_bytes(_canonical(payload).encode("utf-8"))[:24]


def _case_result(
    *,
    run_key: str,
    case: Mapping[str, Any],
    logs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "paper-case-result-1.0",
        "run_key": run_key,
        "case_id": str(case.get("case_id", "")),
        "steps": len(logs),
        "final_status": logs[-1]["final_status"] if logs else "error",
        "defense_id": logs[0]["defense_id"] if logs else "",
        "model": logs[0]["model"] if logs else "",
        "policy_regime": logs[0]["policy_regime"] if logs else "",
        "replicate_id": logs[0]["replicate_id"] if logs else 0,
        "decisions": [row["guard_decision"]["decision"] for row in logs],
        "tools": [row["action_proposal"]["tool"] for row in logs],
        "effectiveness_eligible": all(row["effectiveness_eligible"] for row in logs),
        "case_latency_ms": logs[-1].get("case_latency_ms") if logs else None,
        "completed_at": _now(),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--baseline-registry", type=Path, default=DEFAULT_BASELINES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--experiment-id", default="m3-paper-v1-matrix")
    parser.add_argument("--models", nargs="+", default=["qwen3:4b-instruct"])
    parser.add_argument("--conditions", nargs="+", default=["no_defense", "m3_full"])
    parser.add_argument("--policy-regime", choices=sorted(POLICY_REGIMES), default="auto_compiled")
    parser.add_argument("--backend", choices=("ollama", "stub"), default="ollama")
    parser.add_argument("--oracle-stub", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--think",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Explicitly enable/disable Ollama thinking; omitted preserves model default.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--case-ids", nargs="*")
    parser.add_argument("--run-tier", choices=("diagnostic", "formal"), default="diagnostic")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.repeats < 1 or args.max_steps < 1:
        raise ValueError("repeats and max-steps must be positive")
    if args.run_tier == "formal" and (args.case_limit or args.oracle_stub):
        raise ValueError("formal runs cannot use case-limit or oracle-stub")
    if args.backend == "stub" and not args.oracle_stub:
        raise ValueError("stub requires --oracle-stub and remains diagnostic-only")

    dataset = args.dataset.resolve()
    output = args.output_dir.resolve()
    registry = args.baseline_registry.resolve()
    cases = _read_jsonl(dataset)
    if args.case_ids:
        selected = set(args.case_ids)
        cases = [row for row in cases if str(row.get("case_id")) in selected]
        missing = selected - {str(row.get("case_id")) for row in cases}
        if missing:
            raise ValueError("unknown case IDs: " + ", ".join(sorted(missing)))
    if args.case_limit is not None:
        if args.case_limit < 1:
            raise ValueError("case-limit must be positive")
        cases = cases[: args.case_limit]
    if not cases:
        raise ValueError("no cases selected")

    conditions = _load_conditions(registry, args.conditions)
    seeds = [args.seed + replicate for replicate in range(args.repeats)]
    expected = len(cases) * len(args.models) * len(conditions) * args.repeats
    config = {
        "schema_version": "paper-matrix-config-1.0",
        "experiment_id": args.experiment_id,
        "dataset": portable_path(dataset, root=ROOT),
        "dataset_sha256": _sha256_file(dataset),
        "baseline_registry": portable_path(registry, root=ROOT),
        "baseline_registry_sha256": _sha256_file(registry),
        "models": list(args.models),
        "conditions": [row["id"] for row in conditions],
        "policy_regime": args.policy_regime,
        "backend": args.backend,
        "oracle_stub": bool(args.oracle_stub),
        "temperature": args.temperature,
        "think": args.think,
        "seeds": seeds,
        "repeats": args.repeats,
        "max_steps": args.max_steps,
        "selected_case_ids": [str(row.get("case_id")) for row in cases],
        "run_tier": args.run_tier,
        "expected_case_runs": expected,
    }
    config_sha = _sha256_bytes(_canonical(config).encode("utf-8"))
    config_path = output / "execution_config.json"
    if config_path.exists():
        prior = json.loads(config_path.read_text(encoding="utf-8"))
        normalized_prior = dict(prior)
        for name in ("dataset", "baseline_registry"):
            normalized_prior[name] = portable_path(
                Path(str(normalized_prior.get(name, ""))),
                root=ROOT,
            )
        if _sha256_bytes(_canonical(normalized_prior).encode("utf-8")) != config_sha:
            raise RuntimeError("output directory contains a different experiment configuration")
        if not args.resume:
            raise RuntimeError("output exists; use another directory or enable --resume")
        config_sha = _sha256_bytes(_canonical(prior).encode("utf-8"))
    else:
        _write_json(config_path, config)

    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "case_results.jsonl"
    failure_path = output / "failures.jsonl"
    log_path = output / "runs.jsonl"
    completed_rows = _read_jsonl(result_path)
    failure_rows = _read_jsonl(failure_path)
    completed_keys = {str(row["run_key"]) for row in completed_rows}
    failed_keys = {str(row["run_key"]) for row in failure_rows} - completed_keys
    created_at = (
        json.loads((output / "manifest.json").read_text(encoding="utf-8"))["created_at"]
        if (output / "manifest.json").exists()
        else _now()
    )
    evidence_level = str(cases[0].get("evidence_level", "development"))
    split = str(cases[0].get("split", "unknown"))
    manifest = {
        "schema_version": "paper-experiment-manifest-1.0",
        "experiment_id": args.experiment_id,
        "status": "running",
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "code_freeze_sha256": _code_freeze_sha256(),
        "configuration_sha256": config_sha,
        "baseline_registry_sha256": _sha256_file(registry),
        "dataset": {
            "name": str(cases[0].get("dataset_version", dataset.stem)),
            "split": split,
            "sha256": _sha256_file(dataset),
            "evidence_level": evidence_level,
            "selected_cases": len(cases),
        },
        "policy_regime": args.policy_regime,
        "attack_budget": 0,
        "models": list(args.models),
        "baselines": [row["id"] for row in conditions],
        "random_seeds": seeds,
        "threshold_frozen": args.run_tier == "formal",
        "hypotheses_frozen": args.run_tier == "formal",
        "exclusion_rules_frozen": args.run_tier == "formal",
        "effectiveness_eligible": args.run_tier == "formal" and args.backend != "stub",
        "resource_blockers": [],
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "ollama": _ollama_version(),
        },
        "expected_case_runs": expected,
        "completed_case_runs": len(completed_keys),
        "failed_case_runs": len(failed_keys),
        "created_at": created_at,
        "completed_at": None,
    }
    _write_json(output / "manifest.json", manifest)

    clients: dict[tuple[str, int], PaperLLMClient] = {}
    for model in args.models:
        for condition in conditions:
            modules = frozenset(str(value) for value in condition.get("guard_modules", []))
            for replicate_id, seed in enumerate(seeds):
                client_key = (model, seed)
                if client_key not in clients:
                    clients[client_key] = PaperLLMClient(
                        backend=args.backend,
                        model=model,
                        temperature=args.temperature,
                        seed=seed,
                        timeout=args.timeout,
                        ollama_transport="native",
                        think=args.think,
                    )
                for case in cases:
                    case_id = str(case.get("case_id", ""))
                    run_key = _run_key(
                        experiment_id=args.experiment_id,
                        case_id=case_id,
                        model=model,
                        condition=str(condition["id"]),
                        regime=args.policy_regime,
                        replicate_id=replicate_id,
                        seed=seed,
                        temperature=args.temperature,
                        think=args.think,
                    )
                    if run_key in completed_keys:
                        continue
                    if run_key in failed_keys and not args.retry_failures:
                        continue
                    try:
                        policy = build_policy_regime(
                            trusted_user_request=str(case.get("trusted_user_request", "")),
                            tool_schemas=DEFAULT_TOOL_SCHEMAS,
                            trusted_app_context=case.get("trusted_app_context", {}),
                            regime=args.policy_regime,
                            generated_at=created_at,
                        )
                        policy_path = output / "policies" / f"{policy.manifest_sha256}.json"
                        if not policy_path.exists():
                            _write_json(policy_path, policy.to_dict())
                        logs = run_research_case(
                            case,
                            client=clients[client_key],
                            backend=args.backend,
                            model=model,
                            temperature=args.temperature,
                            seed=seed,
                            max_steps=args.max_steps,
                            tool_schemas=DEFAULT_TOOL_SCHEMAS,
                            defense_id=str(condition["id"]),
                            prompt_profile=str(condition["prompt_profile"]),
                            monitor_mode=str(condition["monitor_mode"]),
                            guard_modules=modules or frozenset({"policy"}),
                            oracle_stub=bool(args.oracle_stub),
                            run_id=args.experiment_id,
                            run_key=run_key,
                            policy_manifest=policy,
                            policy_regime=args.policy_regime,
                            replicate_id=replicate_id,
                        )
                        for row in logs:
                            _append_jsonl(log_path, row)
                        result = _case_result(run_key=run_key, case=case, logs=logs)
                        _append_jsonl(result_path, result)
                        completed_keys.add(run_key)
                        failed_keys.discard(run_key)
                    except Exception as exc:  # retain every provider/data/runtime failure
                        failure = {
                            "schema_version": "paper-run-failure-1.0",
                            "run_key": run_key,
                            "case_id": case_id,
                            "model": model,
                            "condition": condition["id"],
                            "policy_regime": args.policy_regime,
                            "replicate_id": replicate_id,
                            "seed": seed,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "traceback": traceback.format_exc(),
                            "failed_at": _now(),
                        }
                        _append_jsonl(failure_path, failure)
                        failed_keys.add(run_key)

    unresolved = failed_keys - completed_keys
    status = "completed" if len(completed_keys) == expected and not unresolved else "failed"
    manifest.update(
        {
            "status": status,
            "completed_case_runs": len(completed_keys),
            "failed_case_runs": len(unresolved),
            "completed_at": _now(),
        }
    )
    _write_json(output / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": status,
                "expected": expected,
                "completed": len(completed_keys),
                "failed": len(unresolved),
                "output": portable_path(output, root=ROOT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
