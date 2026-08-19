"""Run the exact Pro-500 stage in a detached, single-use evidence wrapper."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from experiments.paper_v2 import adaptive_formal_pro_500_activation_gate_v1 as gate
from experiments.paper_v2 import adaptive_formal_pro_controller_v2 as controller


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/adaptive_formal_pro_500_guarded_v1_20260807"
)
RUNNING_PATH = RUN_ROOT / "running.json"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
RECEIPT_FAILURE_PATH = RUN_ROOT / "receipt_write_failure.json"
CONFIG_PATH = PROJECT_ROOT / "config/project.local.env"
CANDIDATE_PATH = controller.candidate_path("pro_500")
ADMISSION_PATH = controller.admission_path("pro_500")
ACTIVATION_GATE_PATH = gate.GATE_PATH
STAGE = "pro_500"
EXPECTED_AUTHORIZED_TASKS = 36
EXPECTED_SOURCE_BUDGET = 200
EXPECTED_TARGET_BUDGET = 500
EXPECTED_STAGE_HARD_LIMIT_CNY = 35.0
SCRUBBED_ENVIRONMENT_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "M3_CANARY_SECRET_API_KEY",
    "M3_FRONTIER_API_CONSENT",
    "OPENAI_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY",
)
SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bAQ\.[A-Za-z0-9._-]{12,}"),
)


class AdaptiveFormalPro500GuardedRunnerV1Error(ValueError):
    """Raised before or after the single permitted Pro-500 execution."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalPro500GuardedRunnerV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalPro500GuardedRunnerV1Error(
            f"{path}: expected object"
        )
    return value


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _scrubbed_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in SCRUBBED_ENVIRONMENT_VARIABLES:
        if name in environment:
            del environment[name]
    return environment


def validate_preflight(
    *,
    activation: Mapping[str, Any],
    candidate: Mapping[str, Any],
    admission: Mapping[str, Any],
    output_root_touched: bool,
) -> dict[str, Any]:
    scope = candidate.get("scope")
    controls = candidate.get("execution_controls")
    authorization = admission.get("authorization")
    if (
        not isinstance(scope, Mapping)
        or not isinstance(controls, Mapping)
        or not isinstance(authorization, Mapping)
        or activation.get("status")
        != "fresh_harness_passed_exact_pro_500_wrapper_eligible"
        or activation.get("verdict", {}).get(
            "exact_pro_500_guarded_runner_eligible"
        )
        is not True
        or activation.get("verdict", {}).get(
            "provider_execution_authorized_by_gate_alone"
        )
        is not False
        or activation.get("verdict", {}).get(
            "result_access_authorized_by_gate"
        )
        is not False
        or candidate.get("status") != "offline_qualified_execution_not_authorized"
        or scope.get("stage") != STAGE
        or scope.get("authorized_task_count") != EXPECTED_AUTHORIZED_TASKS
        or scope.get("source_checkpoint_count") != EXPECTED_AUTHORIZED_TASKS
        or scope.get("target_budget") != EXPECTED_TARGET_BUDGET
        or scope.get("stage_hard_limit_cny") != EXPECTED_STAGE_HARD_LIMIT_CNY
        or len(scope.get("cumulative_diagnostic_case_ids", [])) != 4
        or any(
            lock.get("query_count") != EXPECTED_SOURCE_BUDGET
            for lock in candidate.get("source_checkpoint_locks", [])
        )
        or controls.get("automatic_retries") != 0
        or controls.get("provider_tools_enabled") is not False
        or controls.get("external_effects_enabled") is not False
        or admission.get("status")
        != "activated_for_one_exact_order_bound_adaptive_stage"
        or admission.get("stage") != STAGE
        or admission.get("candidate_manifest_sha256")
        != candidate.get("manifest_sha256")
        or admission.get("run_id") != scope.get("run_id")
        or admission.get("execution_identity")
        != scope.get("execution_identity")
        or authorization.get("stage_execution_authorized") is not True
        or authorization.get("terminal_query_replay_authorized") is not False
        or authorization.get("automatic_retries") != 0
        or authorization.get("provider_tools_enabled") is not False
        or authorization.get("external_effects_enabled") is not False
        or authorization.get("result_admission_authorized") is not False
        or output_root_touched
    ):
        raise AdaptiveFormalPro500GuardedRunnerV1Error(
            "Pro-500 activation/candidate/admission safety boundary drift"
        )
    return {
        "run_id": str(scope["run_id"]),
        "execution_identity": str(scope["execution_identity"]),
        "output_root": str(scope["output_root"]),
        "authorized_task_count": EXPECTED_AUTHORIZED_TASKS,
        "retained_cumulative_diagnostic_count": 4,
        "source_checkpoint_budget": EXPECTED_SOURCE_BUDGET,
        "target_budget": EXPECTED_TARGET_BUDGET,
        "stage_hard_limit_cny": EXPECTED_STAGE_HARD_LIMIT_CNY,
    }


def _run_step(
    *,
    name: str,
    arguments: Iterable[str],
    environment: Mapping[str, str],
) -> dict[str, Any]:
    stdout_path = RUN_ROOT / f"{name}.stdout.log"
    stderr_path = RUN_ROOT / f"{name}.stderr.log"
    started_at = _now()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        completed = subprocess.run(
            [sys.executable, *arguments],
            cwd=PROJECT_ROOT,
            env=dict(environment),
            stdout=stdout,
            stderr=stderr,
            check=False,
            shell=False,
        )
    return {
        "started_at": started_at,
        "completed_at": _now(),
        "operating_system_exit_code_directly_observed": True,
        "exit_code": completed.returncode,
        "stdout_path": stdout_path.relative_to(PROJECT_ROOT).as_posix(),
        "stderr_path": stderr_path.relative_to(PROJECT_ROOT).as_posix(),
        "stdout_sha256": _sha256_file(stdout_path),
        "stderr_sha256": _sha256_file(stderr_path),
    }


def _secret_hit_count(paths: Iterable[Path]) -> int:
    hits = 0
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            hits += len(pattern.findall(text))
    return hits


def run() -> dict[str, Any]:
    if RUN_ROOT.exists():
        raise AdaptiveFormalPro500GuardedRunnerV1Error(
            "Pro-500 guarded run root already exists; retry is forbidden"
        )
    if not CONFIG_PATH.is_file():
        raise AdaptiveFormalPro500GuardedRunnerV1Error(
            "local provider config is missing"
        )
    activation = gate.verify_gate()
    candidate = controller.verify_stage_candidate(STAGE)
    admission = controller.validate_stage_admission(
        _read_json(ADMISSION_PATH),
        stage=STAGE,
    )
    output_root = PROJECT_ROOT / str(candidate["scope"]["output_root"])
    output_root_touched = output_root.exists() and any(output_root.rglob("*"))
    preflight = validate_preflight(
        activation=activation,
        candidate=candidate,
        admission=admission,
        output_root_touched=output_root_touched,
    )
    RUN_ROOT.mkdir(parents=True, exist_ok=False)
    started_at = _now()
    running = {
        "schema_version": "m3-paper-v2-adaptive-formal-pro-500-running-1.0",
        "status": "running_detached_single_use",
        "started_at": started_at,
        "process_id": os.getpid(),
        "python_executable": sys.executable,
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-pro",
        "model_role": "primary",
        "stage": STAGE,
        **preflight,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "scientific_outcomes_accessed": False,
        "result_admission_authorized": False,
    }
    _atomic_write(RUNNING_PATH, running)
    environment = _scrubbed_environment()
    steps: dict[str, Any] = {}
    final_exit = 1
    technical_review_summary: dict[str, Any] | None = None
    failure: dict[str, str] | None = None
    try:
        commands = (
            (
                "01_activation_gate",
                (
                    "-B",
                    "-m",
                    "experiments.paper_v2."
                    "adaptive_formal_pro_500_activation_gate_v1",
                    "--verify-gate",
                ),
            ),
            (
                "02_order_gate",
                (
                    "-B",
                    "-m",
                    "experiments.paper_v2.adaptive_execution_order_gate_v2",
                    "--verify-review",
                ),
            ),
            (
                "03_candidate",
                (
                    "-B",
                    "-m",
                    "experiments.paper_v2.adaptive_formal_pro_controller_v2",
                    "--verify-candidate",
                    "--stage",
                    STAGE,
                ),
            ),
            (
                "04_admission",
                (
                    "-B",
                    "-m",
                    "experiments.paper_v2.adaptive_formal_pro_controller_v2",
                    "--verify-admission",
                    "--stage",
                    STAGE,
                    "--admission",
                    ADMISSION_PATH.relative_to(PROJECT_ROOT).as_posix(),
                ),
            ),
            (
                "05_execute",
                (
                    "-B",
                    "-m",
                    "experiments.paper_v2.adaptive_formal_pro_controller_v2",
                    "--execute-stage",
                    "--stage",
                    STAGE,
                    "--admission",
                    ADMISSION_PATH.relative_to(PROJECT_ROOT).as_posix(),
                    "--config",
                    CONFIG_PATH.relative_to(PROJECT_ROOT).as_posix(),
                ),
            ),
            (
                "06_technical_review",
                (
                    "-B",
                    "-m",
                    "experiments.paper_v2.adaptive_formal_pro_controller_v2",
                    "--write-technical-review",
                    "--stage",
                    STAGE,
                ),
            ),
        )
        for name, arguments in commands:
            step = _run_step(
                name=name,
                arguments=arguments,
                environment=environment,
            )
            steps[name] = step
            if step["exit_code"] != 0:
                raise AdaptiveFormalPro500GuardedRunnerV1Error(
                    f"{name} sealed nonzero"
                )
        technical_review_path = output_root / "technical_review_v2.json"
        technical_review = _read_json(technical_review_path)
        if (
            technical_review.get("status")
            != "adaptive_formal_stage_technical_gate_pass"
            or technical_review.get("technical_gate_passed") is not True
            or technical_review.get("result_admission_authorized") is not False
            or technical_review.get("authorized_task_count")
            != EXPECTED_AUTHORIZED_TASKS
            or technical_review.get("terminal_task_count")
            != EXPECTED_AUTHORIZED_TASKS
            or technical_review.get("target_budget") != EXPECTED_TARGET_BUDGET
            or float(technical_review.get("stage_cost_cny", 1e9))
            > EXPECTED_STAGE_HARD_LIMIT_CNY
        ):
            raise AdaptiveFormalPro500GuardedRunnerV1Error(
                "Pro-500 technical review did not pass"
            )
        technical_review_summary = {
            "path": technical_review_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": _sha256_file(technical_review_path),
            "manifest_sha256": technical_review["manifest_sha256"],
            "terminal_task_count": technical_review["terminal_task_count"],
            "terminal_query_count": technical_review[
                "terminal_query_count_this_stage"
            ],
            "completed_provider_call_count": technical_review[
                "completed_provider_call_count"
            ],
            "stage_cost_cny": technical_review["stage_cost_cny"],
            "technical_gate_passed": True,
            "result_admission_authorized": False,
        }
        final_exit = 0
    except Exception as exc:  # noqa: BLE001 - sealed in the immutable receipt
        failure = {
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
    log_paths = sorted(RUN_ROOT.glob("*.log"))
    secret_hits = _secret_hit_count(log_paths)
    if secret_hits:
        final_exit = 1
        failure = {
            "error_type": "SecretPatternDetected",
            "message": "guarded log secret scan failed closed",
        }
    receipt = {
        "schema_version": "m3-paper-v2-adaptive-formal-pro-500-receipt-1.0",
        "status": (
            "completed_technical_gate_pass"
            if final_exit == 0
            else "sealed_nonzero_or_gate_fail"
        ),
        "started_at": started_at,
        "completed_at": _now(),
        "process_id": os.getpid(),
        "python_executable": sys.executable,
        "runner_sha256": _sha256_file(Path(__file__)),
        "activation_gate_sha256": _sha256_file(ACTIVATION_GATE_PATH),
        "candidate_sha256": _sha256_file(CANDIDATE_PATH),
        "admission_sha256": _sha256_file(ADMISSION_PATH),
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-pro",
        "model_role": "primary",
        "stage": STAGE,
        **preflight,
        "steps": steps,
        "technical_review": technical_review_summary,
        "failure": failure,
        "final_exit_code": final_exit,
        "secret_pattern_hit_count": secret_hits,
        "provider_environment_variables_scrubbed": list(
            SCRUBBED_ENVIRONMENT_VARIABLES
        ),
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "scientific_outcomes_accessed_by_runner": False,
        "result_admission_authorized": False,
    }
    try:
        _atomic_write(RECEIPT_PATH, receipt)
    except Exception as exc:  # noqa: BLE001 - last-resort evidence only
        failure_receipt = {
            "schema_version": (
                "m3-paper-v2-adaptive-formal-pro-500-receipt-write-failure-1.0"
            ),
            "failed_at": _now(),
            "error_type": type(exc).__name__,
            "message": str(exc),
            "intended_final_exit_code": final_exit,
            "scientific_outcomes_accessed": False,
        }
        _atomic_write(RECEIPT_FAILURE_PATH, failure_receipt)
        raise
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.parse_args()
    receipt = run()
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return int(receipt["final_exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
