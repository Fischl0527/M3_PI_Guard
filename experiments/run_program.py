"""Recoverable stage orchestration for the complete M3 experiment program.

This module plans coarse jobs around :func:`m3_core.run_matrix.run_matrix`.
The matrix runner remains responsible for per-case durability; this layer adds
cross-matrix gates, exact scale checks, model failure propagation, and one
atomic program manifest spanning all stages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from experiments.catalog import (
    ALL_MODELS,
    CORE_CONDITIONS,
    CORE_MODELS,
    MAIN_SEEDS,
    STABILITY_SEEDS,
    STABILITY_TEMPERATURES,
)
from experiments.freeze import DEFAULT_FREEZE_PATH, verify_freeze
from experiments.manifest import REPO_ROOT, save_manifest, sha256_file, utc_now
from experiments.model_manager import gpu_snapshot, stop_model
from m3_core.run_matrix import run_matrix
from m3_guard.config import ALL_MODULES, MODE_MODULES


STAGES = (
    "stub",
    "smoke",
    "validation-baseline",
    "ablation",
    "main",
    "derived",
    "stability",
)
PROGRAM_SCHEMA_VERSION = "1.0"
DEFAULT_PROGRAM_MANIFEST = REPO_ROOT / "outputs" / "experiments" / "program_manifest.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs" / "experiments" / "program"
DEFAULT_THRESHOLDS_PATH = REPO_ROOT / "outputs" / "experiments" / "E13" / "frozen_thresholds.json"
POST_CALIBRATION_STAGES = frozenset({"ablation", "main", "derived", "stability"})

CANONICAL_CASES = REPO_ROOT / "m3_attacks" / "cases" / "all_cases.jsonl"
SMOKE_CASES = REPO_ROOT / "experiments" / "fixtures" / "smoke_cases.jsonl"
DERIVED_ROOT = REPO_ROOT / "experiments" / "fixtures" / "derived"

QWEN_MODEL = CORE_MODELS[0]

STUB_CONDITIONS = (
    "stub_normal_off=normal:off",
    "stub_normal_keyword=normal:keyword_only",
    "stub_normal_policy=normal:policy_only",
    "stub_normal_detector=normal:detector_only",
    "stub_normal_full=normal:full_guard",
    "stub_normal_no_dataflow=normal:no_dataflow",
    "stub_normal_no_intent_action=normal:no_intent_action",
    "stub_normal_no_structured=normal:no_structured_detector",
    "stub_normal_no_multilingual=normal:no_multilingual_detector",
    "stub_hardened_off=hardened:off",
    "stub_hardened_full=hardened:full_guard",
)
SMOKE_CONDITIONS = (
    "smoke_normal_off=normal:off",
    "smoke_normal_full=normal:full_guard",
)
DERIVED_CONDITIONS = (
    "derived_normal_off=normal:off",
    "derived_normal_full=normal:full_guard",
)
STABILITY_CONDITIONS = ("stability_normal_full=normal:full_guard",)


class ProgramError(RuntimeError):
    """Base exception for program orchestration failures."""


class ProgramGateError(ProgramError):
    """Raised when a non-negotiable pre-execution gate fails."""


class ResultValidationError(ProgramError):
    """Raised when a matrix result does not match its declared scale."""


@dataclass(frozen=True)
class ProgramJob:
    job_id: str
    stage: str
    model: str
    matrix_config: dict[str, Any]
    expected_run_count: int
    evidence_tier: str

    @property
    def condition_count(self) -> int:
        return len(_csv_values(self.matrix_config.get("conditions")))

    def to_manifest_entry(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "stage": self.stage,
            "model": self.model,
            "status": "pending",
            "evidence_tier": self.evidence_tier,
            "expected_run_count": self.expected_run_count,
            "selected_run_count": 0,
            "completed_run_count": 0,
            "error_count": 0,
            "matrix_config": dict(self.matrix_config),
            "command": matrix_command(self.matrix_config),
            "attempts": 0,
            "attempt_history": [],
            "result_manifest": None,
            "error": None,
        }


@dataclass(frozen=True)
class StagePlan:
    stage: str
    jobs: tuple[ProgramJob, ...]
    required_models: tuple[str, ...]
    freeze_required: bool = False

    @property
    def expected_run_count(self) -> int:
        return sum(job.expected_run_count for job in self.jobs)

    @property
    def condition_count(self) -> int:
        return sum(job.condition_count for job in self.jobs)

    def summary(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "job_count": len(self.jobs),
            "condition_count": self.condition_count,
            "expected_run_count": self.expected_run_count,
            "required_models": list(self.required_models),
            "freeze_required": self.freeze_required,
        }


def _relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _temperature_label(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def _guard_mode(value: str) -> str:
    return "off" if value == "none" else value


def core_condition_specs() -> tuple[str, ...]:
    return tuple(
        f"{condition.id}={condition.prompt_profile}:{_guard_mode(condition.guard_mode)}"
        for condition in CORE_CONDITIONS
    )


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(value)
    return rows


def _require_count(path: Path, expected: int) -> None:
    actual = len(_jsonl_rows(path))
    if actual != expected:
        raise ValueError(f"fixture count mismatch for {path}: expected={expected}, actual={actual}")


def _matrix_config(
    *,
    stage: str,
    job_id: str,
    cases: Path,
    backend: str,
    model: str,
    conditions: Sequence[str],
    output_root: Path,
    seed: int = 42,
    repeats: int = 1,
    temperature: float = 0.2,
    splits: str = "",
    case_ids: Sequence[str] = (),
    guard_modules: Sequence[str] = (),
    num_ctx: int | None = None,
) -> dict[str, Any]:
    out_dir = output_root / stage / job_id
    return {
        "cases": _relative_or_absolute(cases),
        "backend": backend,
        "model": model,
        "conditions": ",".join(conditions),
        "guard_modules": ",".join(guard_modules),
        "ask_threshold": 0.35,
        "deny_threshold": 0.65,
        "families": "",
        "splits": splits,
        "sample_types": "",
        "task_types": "",
        "case_ids": ",".join(case_ids),
        "limit": None,
        "out_dir": _relative_or_absolute(out_dir),
        "max_steps": 5,
        "run_prefix": job_id,
        "run_group": stage,
        "seed": seed,
        "selection_seed": seed,
        "generation_seed": seed,
        "repeats": repeats,
        "temperature": temperature,
        "max_tokens": 512,
        "num_ctx": num_ctx,
        "timeout": 120.0,
        "shuffle": False,
        "resume": False,
        "fail_fast": True,
        "allow_fallback_guard": False,
        "notes": f"M3 full experiment program stage={stage} job={job_id}",
    }


def _job(
    *,
    stage: str,
    job_id: str,
    model: str,
    selected_cases: int,
    conditions: Sequence[str],
    evidence_tier: str,
    config: dict[str, Any],
) -> ProgramJob:
    expected = selected_cases * len(conditions) * int(config.get("repeats", 1))
    return ProgramJob(job_id, stage, model, config, expected, evidence_tier)


def _build_stub(output_root: Path) -> StagePlan:
    _require_count(CANONICAL_CASES, 300)
    job_id = "stub__canonical_all_modes"
    config = _matrix_config(
        stage="stub",
        job_id=job_id,
        cases=CANONICAL_CASES,
        backend="stub",
        model="stub",
        conditions=STUB_CONDITIONS,
        output_root=output_root,
        seed=42,
        temperature=0.0,
    )
    return StagePlan(
        "stub",
        (_job(
            stage="stub",
            job_id=job_id,
            model="stub",
            selected_cases=300,
            conditions=STUB_CONDITIONS,
            evidence_tier="regression_only",
            config=config,
        ),),
        (),
    )


def _build_smoke(output_root: Path) -> StagePlan:
    _require_count(SMOKE_CASES, 6)
    jobs: list[ProgramJob] = []
    for model in ALL_MODELS:
        job_id = f"smoke__{_safe_name(model)}"
        config = _matrix_config(
            stage="smoke",
            job_id=job_id,
            cases=SMOKE_CASES,
            backend="ollama",
            model=model,
            conditions=SMOKE_CONDITIONS,
            output_root=output_root,
            seed=101,
            temperature=0.0,
        )
        jobs.append(
            _job(
                stage="smoke",
                job_id=job_id,
                model=model,
                selected_cases=6,
                conditions=SMOKE_CONDITIONS,
                evidence_tier="formal_smoke",
                config=config,
            )
        )
    return StagePlan("smoke", tuple(jobs), tuple(ALL_MODELS))


def _build_validation_baseline(output_root: Path) -> StagePlan:
    _require_count(CANONICAL_CASES, 300)
    conditions = ("validation_normal_off=normal:off",)
    job_id = "validation_baseline__qwen"
    config = _matrix_config(
        stage="validation-baseline",
        job_id=job_id,
        cases=CANONICAL_CASES,
        backend="ollama",
        model=QWEN_MODEL,
        conditions=conditions,
        output_root=output_root,
        splits="validation",
        seed=211,
        temperature=0.0,
    )
    return StagePlan(
        "validation-baseline",
        (_job(
            stage="validation-baseline",
            job_id=job_id,
            model=QWEN_MODEL,
            selected_cases=60,
            conditions=conditions,
            evidence_tier="formal_validation",
            config=config,
        ),),
        (QWEN_MODEL,),
    )


def _ablation_specs() -> list[tuple[str, str, tuple[str, ...]]]:
    specs: list[tuple[str, str, tuple[str, ...]]] = []
    all_modules = tuple(sorted(ALL_MODULES))
    for module in all_modules:
        condition_id = f"ablation_solo_{module}"
        specs.append((condition_id, f"{condition_id}=normal:full_guard", (module,)))
    for removed in all_modules:
        condition_id = f"ablation_remove_{removed}"
        modules = tuple(module for module in all_modules if module != removed)
        specs.append((condition_id, f"{condition_id}=normal:full_guard", modules))
    for mode in MODE_MODULES:
        condition_id = f"ablation_named_{mode}"
        specs.append((condition_id, f"{condition_id}=normal:{mode}", ()))
    return specs


def _build_ablation(output_root: Path) -> StagePlan:
    _require_count(CANONICAL_CASES, 300)
    jobs: list[ProgramJob] = []
    for index, (condition_id, condition, modules) in enumerate(_ablation_specs()):
        job_id = f"ablation__{condition_id}"
        config = _matrix_config(
            stage="ablation",
            job_id=job_id,
            cases=CANONICAL_CASES,
            backend="ollama",
            model=QWEN_MODEL,
            conditions=(condition,),
            output_root=output_root,
            splits="validation",
            guard_modules=modules,
            # Every ablation is paired on the same validation cases and model
            # generation seed; only the Guard component set may change.
            seed=307,
            temperature=0.0,
        )
        jobs.append(
            _job(
                stage="ablation",
                job_id=job_id,
                model=QWEN_MODEL,
                selected_cases=60,
                conditions=(condition,),
                evidence_tier="formal_validation",
                config=config,
            )
        )
    return StagePlan("ablation", tuple(jobs), (QWEN_MODEL,))


def _build_main(output_root: Path) -> StagePlan:
    _require_count(CANONICAL_CASES, 300)
    conditions = core_condition_specs()
    jobs: list[ProgramJob] = []
    for model in CORE_MODELS:
        for seed in MAIN_SEEDS:
            job_id = f"main__{_safe_name(model)}__seed_{seed}"
            config = _matrix_config(
                stage="main",
                job_id=job_id,
                cases=CANONICAL_CASES,
                backend="ollama",
                model=model,
                conditions=conditions,
                output_root=output_root,
                splits="blind",
                seed=seed,
                temperature=0.2,
            )
            jobs.append(
                _job(
                    stage="main",
                    job_id=job_id,
                    model=model,
                    selected_cases=90,
                    conditions=conditions,
                    evidence_tier="formal_blind",
                    config=config,
                )
            )
    return StagePlan("main", tuple(jobs), tuple(CORE_MODELS), freeze_required=True)


def _build_derived(output_root: Path, *, include_coverage: bool) -> StagePlan:
    paths = {
        "E7": DERIVED_ROOT / "e7_cases.jsonl",
        "E8": DERIVED_ROOT / "e8_cases.jsonl",
        "E9": DERIVED_ROOT / "e9_cases.jsonl",
        "E10": DERIVED_ROOT / "e10_cases.jsonl",
        "E11": DERIVED_ROOT / "e11_cases.jsonl",
    }
    expected_counts = {"E7": 60, "E8": 45, "E9": 60, "E10": 36, "E11": 22}
    for experiment_id, expected in expected_counts.items():
        _require_count(paths[experiment_id], expected)

    jobs: list[ProgramJob] = []
    for experiment_id in ("E8", "E10"):
        job_id = f"derived__{experiment_id.lower()}__qwen"
        config = _matrix_config(
            stage="derived",
            job_id=job_id,
            cases=paths[experiment_id],
            backend="ollama",
            model=QWEN_MODEL,
            conditions=DERIVED_CONDITIONS,
            output_root=output_root,
            seed=401 if experiment_id == "E8" else 409,
            temperature=0.2,
        )
        jobs.append(
            _job(
                stage="derived",
                job_id=job_id,
                model=QWEN_MODEL,
                selected_cases=expected_counts[experiment_id],
                conditions=DERIVED_CONDITIONS,
                evidence_tier="formal_derived",
                config=config,
            )
        )

    e9_rows = _jsonl_rows(paths["E9"])
    for num_ctx in (2048, 4096, 8192, 16384):
        case_ids = sorted(
            str(row["case_id"])
            for row in e9_rows
            if int(row.get("attack_dimensions", {}).get("context_tokens", 0)) == num_ctx
        )
        if len(case_ids) != 15:
            raise ValueError(f"E9 num_ctx={num_ctx} expected 15 cases, found {len(case_ids)}")
        job_id = f"derived__e9__qwen__ctx_{num_ctx}"
        config = _matrix_config(
            stage="derived",
            job_id=job_id,
            cases=paths["E9"],
            backend="ollama",
            model=QWEN_MODEL,
            conditions=DERIVED_CONDITIONS,
            output_root=output_root,
            case_ids=case_ids,
            num_ctx=num_ctx,
            seed=419 + num_ctx,
            temperature=0.2,
        )
        jobs.append(
            _job(
                stage="derived",
                job_id=job_id,
                model=QWEN_MODEL,
                selected_cases=15,
                conditions=DERIVED_CONDITIONS,
                evidence_tier="formal_derived",
                config=config,
            )
        )

    if include_coverage:
        for experiment_id in ("E7", "E11"):
            job_id = f"derived__{experiment_id.lower()}__qwen"
            config = _matrix_config(
                stage="derived",
                job_id=job_id,
                cases=paths[experiment_id],
                backend="ollama",
                model=QWEN_MODEL,
                conditions=DERIVED_CONDITIONS,
                output_root=output_root,
                seed=431 if experiment_id == "E7" else 433,
                temperature=0.2,
            )
            jobs.append(
                _job(
                    stage="derived",
                    job_id=job_id,
                    model=QWEN_MODEL,
                    selected_cases=expected_counts[experiment_id],
                    conditions=DERIVED_CONDITIONS,
                    evidence_tier="formal_derived",
                    config=config,
                )
            )
    return StagePlan("derived", tuple(jobs), (QWEN_MODEL,), freeze_required=True)


def _build_stability(output_root: Path) -> StagePlan:
    cases = DERIVED_ROOT / "e15_cases.jsonl"
    _require_count(cases, 30)
    jobs: list[ProgramJob] = []
    for model in CORE_MODELS:
        for temperature in STABILITY_TEMPERATURES:
            for seed in STABILITY_SEEDS:
                job_id = (
                    f"stability__{_safe_name(model)}"
                    f"__temp_{_temperature_label(temperature)}__seed_{seed}"
                )
                config = _matrix_config(
                    stage="stability",
                    job_id=job_id,
                    cases=cases,
                    backend="ollama",
                    model=model,
                    conditions=STABILITY_CONDITIONS,
                    output_root=output_root,
                    seed=seed,
                    temperature=temperature,
                )
                jobs.append(
                    _job(
                        stage="stability",
                        job_id=job_id,
                        model=model,
                        selected_cases=30,
                        conditions=STABILITY_CONDITIONS,
                        evidence_tier="formal_stability",
                        config=config,
                    )
                )
    return StagePlan("stability", tuple(jobs), tuple(CORE_MODELS), freeze_required=True)


def _load_frozen_thresholds(path: str | Path) -> dict[str, Any]:
    threshold_path = Path(path).resolve()
    raw = threshold_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("experiment_id") != "E13" or payload.get("scope") != "validation_only":
        raise ProgramGateError("threshold file is not an E13 validation-only freeze")
    ask = float(payload["ask_threshold"])
    deny = float(payload["deny_threshold"])
    if not 0.0 <= ask <= deny <= 1.0:
        raise ProgramGateError("frozen thresholds must satisfy 0 <= ASK <= DENY <= 1")
    return {
        "path": _relative_or_absolute(threshold_path),
        "status": str(payload.get("status", "unknown")),
        "ask_threshold": ask,
        "deny_threshold": deny,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _apply_frozen_thresholds(plan: StagePlan, freeze: Mapping[str, Any]) -> StagePlan:
    jobs: list[ProgramJob] = []
    for job in plan.jobs:
        config = {
            **job.matrix_config,
            "ask_threshold": float(freeze["ask_threshold"]),
            "deny_threshold": float(freeze["deny_threshold"]),
        }
        jobs.append(replace(job, matrix_config=config))
    return replace(plan, jobs=tuple(jobs))


def _verified_freeze_snapshot(
    path: str | Path,
    verifier: Callable[..., list[str]],
) -> tuple[dict[str, Any], list[str]]:
    """Verify one stable blind-freeze file and return its raw-byte identity."""

    freeze_path = Path(path).resolve()
    before = sha256_file(freeze_path) if freeze_path.is_file() else None
    problems: list[str] = []
    if before is None:
        problems.append(f"blind freeze manifest is missing: {freeze_path}")
    try:
        problems.extend(str(problem) for problem in verifier(freeze_path))
    except Exception as exc:
        problems.append(f"{type(exc).__name__}: {exc}")
    after = sha256_file(freeze_path) if freeze_path.is_file() else None
    if before != after:
        raise ProgramGateError(
            "blind freeze manifest changed during verification; refusing unstable provenance"
        )
    return (
        {
            "path": _relative_or_absolute(freeze_path),
            "sha256": after,
        },
        list(dict.fromkeys(problems)),
    )


def build_stage_plan(
    stage: str,
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    include_derived_coverage: bool = False,
) -> StagePlan:
    """Create a deterministic stage plan without starting any experiment."""

    output = Path(output_root).resolve()
    builders: dict[str, Callable[[], StagePlan]] = {
        "stub": lambda: _build_stub(output),
        "smoke": lambda: _build_smoke(output),
        "validation-baseline": lambda: _build_validation_baseline(output),
        "ablation": lambda: _build_ablation(output),
        "main": lambda: _build_main(output),
        "derived": lambda: _build_derived(output, include_coverage=include_derived_coverage),
        "stability": lambda: _build_stability(output),
    }
    if stage not in builders:
        raise ValueError(f"unknown stage {stage!r}; expected one of {', '.join(STAGES)}")
    plan = builders[stage]()
    _validate_plan(plan)
    return plan


def _validate_plan(plan: StagePlan) -> None:
    job_ids = [job.job_id for job in plan.jobs]
    outputs = [str(job.matrix_config["out_dir"]) for job in plan.jobs]
    global_condition_ids: list[str] = []
    for job in plan.jobs:
        job_condition_ids: list[str] = []
        for condition in _csv_values(job.matrix_config.get("conditions")):
            condition_id, separator, specification = condition.partition("=")
            if not separator or ":" not in specification or not condition_id:
                raise ValueError(f"condition is not explicit id=profile:mode: {condition!r}")
            job_condition_ids.append(condition_id)
            global_condition_ids.append(condition_id)
        if len(job_condition_ids) != len(set(job_condition_ids)):
            raise ValueError(f"duplicate condition id in job {job.job_id}")
    if len(job_ids) != len(set(job_ids)):
        raise ValueError(f"duplicate job id in stage {plan.stage}")
    if len(outputs) != len(set(outputs)):
        raise ValueError(f"duplicate output directory in stage {plan.stage}")
    if plan.stage == "ablation" and len(global_condition_ids) != len(set(global_condition_ids)):
        raise ValueError(f"duplicate condition id in stage {plan.stage}")
    if any(job.expected_run_count <= 0 for job in plan.jobs):
        raise ValueError(f"non-positive expected run count in stage {plan.stage}")


def matrix_command(config: Mapping[str, Any]) -> list[str]:
    """Return a CLI command equivalent to the matrix config stored in a job."""

    command = [sys.executable, "-m", "m3_core.run_matrix"]
    value_options = (
        ("cases", "--cases"),
        ("backend", "--backend"),
        ("model", "--model"),
        ("conditions", "--conditions"),
        ("guard_modules", "--guard-modules"),
        ("ask_threshold", "--ask-threshold"),
        ("deny_threshold", "--deny-threshold"),
        ("families", "--families"),
        ("splits", "--splits"),
        ("sample_types", "--sample-types"),
        ("task_types", "--task-types"),
        ("case_ids", "--case-ids"),
        ("limit", "--limit"),
        ("out_dir", "--out-dir"),
        ("max_steps", "--max-steps"),
        ("run_prefix", "--run-prefix"),
        ("run_group", "--run-group"),
        ("seed", "--seed"),
        ("selection_seed", "--selection-seed"),
        ("generation_seed", "--generation-seed"),
        ("repeats", "--repeats"),
        ("temperature", "--temperature"),
        ("max_tokens", "--max-tokens"),
        ("num_ctx", "--num-ctx"),
        ("timeout", "--timeout"),
        ("notes", "--notes"),
    )
    for key, option in value_options:
        value = config.get(key)
        if value in {None, ""}:
            continue
        command.extend((option, str(value)))
    for key, option in (
        ("shuffle", "--shuffle"),
        ("resume", "--resume"),
        ("fail_fast", "--fail-fast"),
        ("allow_fallback_guard", "--allow-fallback-guard"),
    ):
        if bool(config.get(key, False)):
            command.append(option)
    return command


def _csv_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _plan_hash(
    plan: StagePlan,
    *,
    frozen_inputs: Mapping[str, Any] | None = None,
) -> str:
    jobs = [
        {
            "job_id": job.job_id,
            "model": job.model,
            "expected_run_count": job.expected_run_count,
            "evidence_tier": job.evidence_tier,
            "matrix_config": job.matrix_config,
        }
        for job in plan.jobs
    ]
    payload: Any = jobs
    if frozen_inputs:
        payload = {
            "jobs": jobs,
            "frozen_inputs": dict(frozen_inputs),
        }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _new_program_manifest() -> dict[str, Any]:
    return {
        "schema_version": PROGRAM_SCHEMA_VERSION,
        "program_id": "M3-E0-E17-full-experiment-program",
        "status": "running",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "stages": {},
        "blocked_models": {},
        "model_lifecycle": [],
        "events": [],
        "progress": {"expected_runs": 0, "completed_runs": 0, "error_count": 0},
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _new_program_manifest()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != PROGRAM_SCHEMA_VERSION:
        raise ProgramError(f"unsupported program manifest schema: {payload.get('schema_version')!r}")
    return payload


def _initialize_stage(
    manifest: dict[str, Any],
    plan: StagePlan,
    *,
    resume: bool,
    frozen_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    stages = manifest.setdefault("stages", {})
    input_snapshot = dict(frozen_inputs or {})
    plan_hash = _plan_hash(plan, frozen_inputs=input_snapshot)
    if plan.stage in stages:
        stage = stages[plan.stage]
        if stage.get("plan_hash") != plan_hash:
            raise ProgramError(
                f"refusing configuration drift for stage {plan.stage}: plan hash changed"
            )
        if dict(stage.get("frozen_inputs") or {}) != input_snapshot:
            raise ProgramError(
                f"refusing frozen input drift for stage {plan.stage}"
            )
        if not resume:
            raise ProgramError(
                f"stage {plan.stage} already exists; pass --resume to continue or retry"
            )
        stage["status"] = "running"
        stage["resumed_at"] = utc_now()
        return stage

    stage = {
        **plan.summary(),
        "status": "running",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "completed_at": None,
        "plan_hash": plan_hash,
        "plan_hash_version": 2 if input_snapshot else 1,
        "frozen_inputs": input_snapshot,
        "freeze_verification": None,
        "jobs": [job.to_manifest_entry() for job in plan.jobs],
        "progress": {
            "expected_runs": plan.expected_run_count,
            "completed_runs": 0,
            "error_count": 0,
        },
        "error": None,
    }
    stages[plan.stage] = stage
    manifest.setdefault("events", []).append(
        {"at": utc_now(), "type": "stage_started", "stage": plan.stage}
    )
    return stage


def _job_entry(stage: Mapping[str, Any], job_id: str) -> dict[str, Any]:
    for entry in stage.get("jobs", []):
        if entry.get("job_id") == job_id:
            return entry
    raise KeyError(job_id)


def _smoke_status_by_model(manifest: Mapping[str, Any]) -> dict[str, str]:
    smoke = manifest.get("stages", {}).get("smoke", {})
    return {
        str(job.get("model")): str(job.get("status"))
        for job in smoke.get("jobs", [])
    }


def matrix_result_counts(result: Mapping[str, Any]) -> dict[str, int]:
    """Aggregate the three mandatory counters across matrix conditions."""

    matrix_results = result.get("results")
    if not isinstance(matrix_results, list) or not matrix_results:
        raise ResultValidationError("matrix result has no condition results")
    selected = sum(int(item.get("selected_run_count", -1)) for item in matrix_results)
    completed = sum(int(item.get("completed_run_count", -1)) for item in matrix_results)
    errors = sum(int(item.get("error_count", -1)) for item in matrix_results)
    return {
        "selected_run_count": selected,
        "completed_run_count": completed,
        "error_count": errors,
    }


def validate_matrix_result(
    result: Mapping[str, Any],
    expected_runs: int,
    *,
    expected_conditions: int | None = None,
) -> dict[str, int]:
    """Verify every matrix counter before a coarse job can be completed."""

    matrix_results = result.get("results")
    counts = matrix_result_counts(result)
    selected = counts["selected_run_count"]
    completed = counts["completed_run_count"]
    errors = counts["error_count"]
    failed_conditions = [
        str(item.get("condition_id", "unknown"))
        for item in matrix_results
        if item.get("status") != "completed"
    ]
    manifest_status = str(result.get("manifest", {}).get("status", ""))
    problems: list[str] = []
    if expected_conditions is not None and len(matrix_results) != expected_conditions:
        problems.append(
            f"condition_result_count={len(matrix_results)}, expected={expected_conditions}"
        )
    if expected_conditions and expected_runs % expected_conditions == 0:
        per_condition = expected_runs // expected_conditions
        for item in matrix_results:
            condition_id = str(item.get("condition_id", "unknown"))
            item_selected = int(item.get("selected_run_count", -1))
            item_completed = int(item.get("completed_run_count", -1))
            item_errors = int(item.get("error_count", -1))
            if item_selected != per_condition:
                problems.append(
                    f"{condition_id}.selected_run_count={item_selected}, expected={per_condition}"
                )
            if item_completed != per_condition:
                problems.append(
                    f"{condition_id}.completed_run_count={item_completed}, expected={per_condition}"
                )
            if item_errors != 0:
                problems.append(f"{condition_id}.error_count={item_errors}")
    if selected != expected_runs:
        problems.append(f"selected_run_count={selected}, expected={expected_runs}")
    if completed != expected_runs:
        problems.append(f"completed_run_count={completed}, expected={expected_runs}")
    if errors != 0:
        problems.append(f"error_count={errors}")
    if failed_conditions:
        problems.append("failed_conditions=" + ",".join(failed_conditions))
    if manifest_status != "completed":
        problems.append(f"matrix_manifest_status={manifest_status!r}")
    if not str(result.get("manifest_path", "")).strip():
        problems.append("missing_matrix_manifest_path")
    if problems:
        raise ResultValidationError("; ".join(problems))
    return counts


def _record_attempt(
    entry: dict[str, Any], *, status: str, error: Mapping[str, Any] | None = None
) -> None:
    item: dict[str, Any] = {"at": utc_now(), "status": status}
    if error:
        item["error"] = dict(error)
    entry.setdefault("attempt_history", []).append(item)


def _recompute_progress(manifest: dict[str, Any]) -> None:
    expected = completed = errors = 0
    stage_statuses: list[str] = []
    for stage in manifest.get("stages", {}).values():
        jobs = stage.get("jobs", [])
        stage_expected = int(stage.get("expected_run_count", 0))
        stage_completed = sum(int(job.get("completed_run_count", 0) or 0) for job in jobs)
        stage_errors = sum(int(job.get("error_count", 0) or 0) for job in jobs)
        stage["progress"] = {
            "expected_runs": stage_expected,
            "completed_runs": stage_completed,
            "error_count": stage_errors,
        }
        expected += stage_expected
        completed += stage_completed
        errors += stage_errors
        stage_statuses.append(str(stage.get("status", "pending")))
    manifest["progress"] = {
        "expected_runs": expected,
        "completed_runs": completed,
        "error_count": errors,
    }
    if any(status in {"failed", "blocked"} for status in stage_statuses):
        manifest["status"] = "failed"
    elif all(name in manifest.get("stages", {}) for name in STAGES) and all(
        manifest["stages"][name].get("status") == "completed" for name in STAGES
    ):
        manifest["status"] = "completed"
        manifest["completed_at"] = utc_now()
    else:
        manifest["status"] = "running"


def _save_program(manifest: dict[str, Any], path: Path) -> None:
    _recompute_progress(manifest)
    save_manifest(manifest, path)


def _mark_blocked_jobs(
    stage: dict[str, Any], blocked_models: Mapping[str, str]
) -> None:
    for entry in stage.get("jobs", []):
        model = str(entry.get("model"))
        if model not in blocked_models:
            continue
        entry["status"] = "blocked"
        entry["error"] = {
            "type": "SmokeGate",
            "message": blocked_models[model],
            "at": utc_now(),
        }


def _record_model_lifecycle(
    manifest: dict[str, Any],
    manifest_path: Path,
    *,
    stage_name: str,
    model: str,
    stopper: Callable[[str], None],
    snapshotter: Callable[[], dict[str, Any]],
) -> str | None:
    entry: dict[str, Any] = {
        "at": utc_now(),
        "stage": stage_name,
        "model": model,
        "action": "ollama_stop_then_gpu_snapshot",
        "stop_status": "pending",
        "gpu_snapshot": None,
        "error": None,
    }
    error_message: str | None = None
    try:
        stopper(model)
        entry["stop_status"] = "completed"
    except Exception as exc:  # lifecycle failures must be durable too
        entry["stop_status"] = "failed"
        error_message = f"{type(exc).__name__}: {exc}"
        entry["error"] = error_message
    try:
        entry["gpu_snapshot"] = snapshotter()
    except Exception as exc:
        snapshot_error = f"{type(exc).__name__}: {exc}"
        error_message = error_message or snapshot_error
        entry["error"] = (
            f"{entry['error']}; snapshot={snapshot_error}" if entry["error"] else snapshot_error
        )
    manifest.setdefault("model_lifecycle", []).append(entry)
    _save_program(manifest, manifest_path)
    return error_message


def run_stage(
    stage_name: str,
    *,
    manifest_path: str | Path = DEFAULT_PROGRAM_MANIFEST,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    freeze_path: str | Path = DEFAULT_FREEZE_PATH,
    thresholds_path: str | Path = DEFAULT_THRESHOLDS_PATH,
    resume: bool = False,
    include_derived_coverage: bool = False,
    continue_on_error: bool = False,
    matrix_runner: Callable[[dict[str, Any]], Mapping[str, Any]] = run_matrix,
    freeze_verifier: Callable[..., list[str]] = verify_freeze,
    model_stopper: Callable[[str], None] = stop_model,
    gpu_snapshotter: Callable[[], dict[str, Any]] = gpu_snapshot,
    require_frozen_thresholds: bool = True,
    manage_model_lifecycle: bool | None = None,
) -> dict[str, Any]:
    """Execute one program stage and atomically update its durable manifest."""

    path = Path(manifest_path).resolve()
    plan = build_stage_plan(
        stage_name,
        output_root=output_root,
        include_derived_coverage=include_derived_coverage,
    )
    threshold_freeze: dict[str, Any] | None = None
    if stage_name in POST_CALIBRATION_STAGES and require_frozen_thresholds:
        threshold_freeze = _load_frozen_thresholds(thresholds_path)
        plan = _apply_frozen_thresholds(plan, threshold_freeze)
    frozen_inputs: dict[str, Any] = {}
    if threshold_freeze is not None:
        frozen_inputs["thresholds"] = {
            "path": threshold_freeze["path"],
            "sha256": threshold_freeze["sha256"],
        }
    freeze_problems: list[str] = []
    if plan.freeze_required:
        freeze_snapshot, freeze_problems = _verified_freeze_snapshot(
            freeze_path, freeze_verifier
        )
        frozen_inputs["blind_freeze"] = freeze_snapshot
    if manage_model_lifecycle is None:
        manage_model_lifecycle = matrix_runner is run_matrix
    manifest = _load_manifest(path)
    stage = _initialize_stage(
        manifest,
        plan,
        resume=resume,
        frozen_inputs=frozen_inputs,
    )
    stage["threshold_freeze"] = threshold_freeze
    _save_program(manifest, path)

    if plan.freeze_required:
        stage["freeze_verification"] = {
            "at": utc_now(),
            "path": _relative_or_absolute(Path(freeze_path)),
            "sha256": frozen_inputs["blind_freeze"]["sha256"],
            "status": "pass" if not freeze_problems else "failed",
            "problems": list(freeze_problems),
        }
        if freeze_problems:
            stage["status"] = "blocked"
            stage["error"] = {
                "type": "BlindFreezeGate",
                "message": "; ".join(freeze_problems),
                "at": utc_now(),
            }
            for entry in stage.get("jobs", []):
                if entry.get("status") != "completed":
                    entry["status"] = "blocked"
                    entry["error"] = stage["error"]
            _save_program(manifest, path)
            return {"manifest": manifest, "stage": stage, "manifest_path": str(path)}

    blocked_for_stage: dict[str, str] = {}
    if stage_name not in {"stub", "smoke"}:
        smoke_status = _smoke_status_by_model(manifest)
        explicitly_blocked = manifest.get("blocked_models", {})
        for model in plan.required_models:
            if model in explicitly_blocked:
                blocked_for_stage[model] = str(explicitly_blocked[model].get("reason"))
            elif smoke_status.get(model) != "completed":
                blocked_for_stage[model] = (
                    f"model smoke status is {smoke_status.get(model, 'missing')!r}; "
                    "run or resume the smoke stage first"
                )
        _mark_blocked_jobs(stage, blocked_for_stage)
        _save_program(manifest, path)

    jobs_by_model: dict[str, list[ProgramJob]] = {}
    model_order: list[str] = []
    for job in plan.jobs:
        if job.model not in jobs_by_model:
            jobs_by_model[job.model] = []
            model_order.append(job.model)
        jobs_by_model[job.model].append(job)

    stop_requested = False
    lifecycle_errors: list[str] = []
    for model in model_order:
        if model in blocked_for_stage:
            continue
        model_executed = False
        for job in jobs_by_model[model]:
            entry = _job_entry(stage, job.job_id)
            if entry.get("status") == "completed" and resume:
                continue
            if entry.get("status") == "failed" and resume:
                manifest.setdefault("events", []).append(
                    {
                        "at": utc_now(),
                        "type": "retrying_failed_job",
                        "stage": stage_name,
                        "job_id": job.job_id,
                    }
                )
            elif entry.get("status") == "blocked" and model not in blocked_for_stage:
                entry["status"] = "pending"
                entry["error"] = None

            config = dict(job.matrix_config)
            config["resume"] = bool(resume)
            entry["matrix_config"] = config
            entry["command"] = matrix_command(config)
            entry["status"] = "running"
            entry["started_at"] = utc_now()
            entry["attempts"] = int(entry.get("attempts", 0)) + 1
            entry["error"] = None
            model_executed = True
            _save_program(manifest, path)

            try:
                result = matrix_runner(config)
                entry.update(matrix_result_counts(result))
                summary = validate_matrix_result(
                    result,
                    job.expected_run_count,
                    expected_conditions=job.condition_count,
                )
            except Exception as exc:
                error = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(limit=8),
                    "at": utc_now(),
                }
                entry["status"] = "failed"
                entry["completed_at"] = utc_now()
                entry["selected_run_count"] = int(entry.get("selected_run_count", 0) or 0)
                entry["completed_run_count"] = int(entry.get("completed_run_count", 0) or 0)
                entry["error_count"] = max(int(entry.get("error_count", 0) or 0), 1)
                entry["error"] = error
                _record_attempt(entry, status="failed", error=error)
                if stage_name == "smoke":
                    manifest.setdefault("blocked_models", {})[model] = {
                        "at": utc_now(),
                        "stage": "smoke",
                        "job_id": job.job_id,
                        "reason": f"{error['type']}: {error['message']}",
                    }
                _save_program(manifest, path)
                if stage_name != "smoke" and not continue_on_error:
                    stop_requested = True
                    break
                continue

            entry.update(summary)
            entry["status"] = "completed"
            entry["completed_at"] = utc_now()
            entry["result_manifest"] = result.get("manifest_path")
            entry["error"] = None
            _record_attempt(entry, status="completed")
            if stage_name == "smoke":
                manifest.setdefault("blocked_models", {}).pop(model, None)
            _save_program(manifest, path)

        if manage_model_lifecycle and model != "stub" and model_executed:
            lifecycle_error = _record_model_lifecycle(
                manifest,
                path,
                stage_name=stage_name,
                model=model,
                stopper=model_stopper,
                snapshotter=gpu_snapshotter,
            )
            if lifecycle_error:
                lifecycle_errors.append(f"{model}: {lifecycle_error}")
                if not continue_on_error:
                    stop_requested = True
        if stop_requested:
            break

    failed = [job for job in stage.get("jobs", []) if job.get("status") in {"failed", "blocked"}]
    pending = [job for job in stage.get("jobs", []) if job.get("status") in {"pending", "running"}]
    if failed or pending or lifecycle_errors:
        stage["status"] = "failed"
        details = []
        if failed:
            details.append(f"failed_or_blocked_jobs={len(failed)}")
        if pending:
            details.append(f"pending_jobs={len(pending)}")
        if lifecycle_errors:
            details.append("lifecycle=" + " | ".join(lifecycle_errors))
        stage["error"] = {
            "type": "StageIncomplete",
            "message": "; ".join(details),
            "at": utc_now(),
        }
    else:
        stage["status"] = "completed"
        stage["completed_at"] = utc_now()
        stage["error"] = None
    stage["updated_at"] = utc_now()
    _save_program(manifest, path)
    return {"manifest": manifest, "stage": stage, "manifest_path": str(path)}


def _plan_payload(
    stages: Iterable[str], *, output_root: Path, include_derived_coverage: bool
) -> dict[str, Any]:
    plans = [
        build_stage_plan(
            stage,
            output_root=output_root,
            include_derived_coverage=include_derived_coverage,
        )
        for stage in stages
    ]
    return {
        "stages": [plan.summary() for plan in plans],
        "total_jobs": sum(len(plan.jobs) for plan in plans),
        "total_conditions": sum(plan.condition_count for plan in plans),
        "total_expected_runs": sum(plan.expected_run_count for plan in plans),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=(*STAGES, "all"))
    parser.add_argument("--manifest", default=str(DEFAULT_PROGRAM_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--freeze-path", default=str(DEFAULT_FREEZE_PATH))
    parser.add_argument("--thresholds-path", default=str(DEFAULT_THRESHOLDS_PATH))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--include-derived-coverage", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print exact job/run counts without creating a manifest or running models.",
    )
    args = parser.parse_args(argv)
    selected_stages = STAGES if args.stage == "all" else (args.stage,)
    output_root = Path(args.output_root).resolve()
    if args.plan_only:
        print(
            json.dumps(
                _plan_payload(
                    selected_stages,
                    output_root=output_root,
                    include_derived_coverage=args.include_derived_coverage,
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    exit_code = 0
    for stage_name in selected_stages:
        result = run_stage(
            stage_name,
            manifest_path=args.manifest,
            output_root=output_root,
            freeze_path=args.freeze_path,
            thresholds_path=args.thresholds_path,
            resume=args.resume,
            include_derived_coverage=args.include_derived_coverage,
            continue_on_error=args.continue_on_error,
        )
        stage = result["stage"]
        print(
            f"{stage_name}: status={stage['status']} "
            f"completed={stage['progress']['completed_runs']}/"
            f"{stage['progress']['expected_runs']} manifest={result['manifest_path']}"
        )
        if stage["status"] != "completed":
            exit_code = 1
            if not args.continue_on_error:
                break
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
