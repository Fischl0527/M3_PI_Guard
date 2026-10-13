"""严格绑定执行次序的形式化 DeepSeek Pro 自适应评测替换入口。

保障各测试用例按照预定因果顺序执行，杜绝时序混淆带来的上下文泄漏。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import experiments.paper_v2.adaptive_execution_order_gate_v2 as order_gate
import experiments.paper_v2.adaptive_formal_pro_controller_v1 as v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
OUTPUT_BASE = PROJECT_ROOT / "outputs/paper_upgrade_v2/adaptive_formal_pro_v2"
GENERATED_AT = "2026-08-03T12:10:00+08:00"
SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-pro-stage-candidate-2.0"
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-adaptive-formal-pro-stage-admission-2.0"
)
OWNER_STATEMENT_SHA256 = v1.OWNER_STATEMENT_SHA256


class AdaptiveFormalProControllerV2Error(ValueError):
    """当受顺序绑定的自适应阶段无法保持安全闭合时抛出的异常。"""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalProControllerV2Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalProControllerV2Error(f"{path}: expected object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _file_lock(path: Path, *, include_manifest: bool = False) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveFormalProControllerV2Error(f"missing file: {path}")
    lock: dict[str, Any] = {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }
    if include_manifest:
        lock["manifest_sha256"] = _read_json(path)["manifest_sha256"]
    return lock


def candidate_path(stage: str) -> Path:
    v1._stage_spec(stage)
    return PROTOCOL_ROOT / f"adaptive_formal_{stage}_candidate_v2.json"


def admission_path(stage: str) -> Path:
    v1._stage_spec(stage)
    return (
        PROTOCOL_ROOT
        / "admissions"
        / f"adaptive_formal_{stage}_admission_v2.json"
    )


def review_path(stage: str) -> Path:
    candidate = _read_json(candidate_path(stage))
    return (
        PROJECT_ROOT
        / str(candidate["scope"]["output_root"])
        / "technical_review_v2.json"
    )


def canonical_stage_command(stage: str) -> str:
    admission = admission_path(stage).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.adaptive_formal_pro_controller_v2 "
        f"--execute-stage --stage {stage} --admission {admission} "
        r"--config config\project.local.env"
    )


def _predecessor_lock(stage: str) -> dict[str, Any] | None:
    predecessor = v1._stage_spec(stage)["prior"]
    if predecessor is None:
        return None
    return order_gate.build_predecessor_review_lock(
        review_path(str(predecessor)), expected_stage=str(predecessor)
    )


@contextmanager
def _delegated_runtime() -> Iterator[None]:
    replacements = {
        "candidate_path": candidate_path,
        "admission_path": admission_path,
        "review_path": review_path,
        "canonical_stage_command": canonical_stage_command,
        "verify_stage_candidate": verify_stage_candidate,
        "validate_stage_admission": validate_stage_admission,
    }
    previous = {name: getattr(v1, name) for name in replacements}
    for name, value in replacements.items():
        setattr(v1, name, value)
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(v1, name, value)


def build_stage_candidate(stage: str) -> dict[str, Any]:
    predecessor_lock = _predecessor_lock(stage)
    order_context = order_gate.require_predecessor_before_candidate_build(
        stage, predecessor_lock
    )
    with _delegated_runtime():
        base = v1.build_stage_candidate(stage)
    scope = copy.deepcopy(base["scope"])
    run_id = f"paper-v2-adaptive-{stage}-v2"
    identity = sha256_canonical_json(
        {
            "schema_version": SCHEMA_VERSION,
            "order_gate_manifest_sha256": order_context[
                "order_gate_manifest_sha256"
            ],
            "plan_manifest_sha256": scope["plan_candidate_manifest_sha256"],
            "prior_review_manifest_sha256": scope[
                "prior_review_manifest_sha256"
            ],
            "stage": stage,
            "run_id": run_id,
            "target_budget": scope["target_budget"],
            "authorized_case_ids": scope["authorized_case_ids"],
            "source_checkpoint_sha256": [
                lock["sha256"] for lock in base["source_checkpoint_locks"]
            ],
        }
    )
    output_root = OUTPUT_BASE / f"{stage}-{identity}"
    if output_root.exists() and any(output_root.rglob("*")):
        raise AdaptiveFormalProControllerV2Error(
            "v2 adaptive output root is not fresh"
        )
    scope.update(
        {
            "run_id": run_id,
            "execution_identity": identity,
            "output_root": _display_path(output_root),
        }
    )
    artifact_locks = copy.deepcopy(base["artifact_locks"])
    artifact_locks.extend(
        [
            _file_lock(Path(__file__)),
            _file_lock(order_gate.REVIEW_PATH, include_manifest=True),
        ]
    )
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "order_bound_single_adaptive_stage_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "order_gate_schema_version": order_gate.SCHEMA_VERSION,
        "order_gate_manifest_sha256": order_context[
            "order_gate_manifest_sha256"
        ],
        "predecessor_review_lock": predecessor_lock,
        "artifact_locks": artifact_locks,
        "source_checkpoint_locks": copy.deepcopy(
            base["source_checkpoint_locks"]
        ),
        "authorization": copy.deepcopy(base["authorization"]),
        "execution_controls": copy.deepcopy(base["execution_controls"]),
        "evidence_boundary": copy.deepcopy(base["evidence_boundary"]),
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_stage_candidate(value: Any, *, stage: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveFormalProControllerV2Error("stage candidate must be object")
    scope = value.get("scope")
    predecessor_lock = _predecessor_lock(stage)
    order_context = order_gate.require_predecessor_before_candidate_build(
        stage, predecessor_lock
    )
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("stage") != stage
        or scope.get("target_budget") != v1._stage_spec(stage)["budget"]
        or scope.get("run_id") != f"paper-v2-adaptive-{stage}-v2"
        or scope.get("model_id") != v1.formal_plan.MODEL_ID
        or scope.get("prior_review_manifest_sha256")
        != (
            None
            if predecessor_lock is None
            else predecessor_lock["manifest_sha256"]
        )
        or value.get("predecessor_review_lock") != predecessor_lock
        or value.get("order_gate_schema_version") != order_gate.SCHEMA_VERSION
        or value.get("order_gate_manifest_sha256")
        != order_context["order_gate_manifest_sha256"]
        or value.get("authorization", {}).get("stage_execution_authorized")
        is not False
        or value.get("authorization", {}).get("result_admission_authorized")
        is not False
        or value.get("execution_controls", {}).get("automatic_retries") != 0
        or value.get("execution_controls", {}).get("provider_tools_enabled")
        is not False
        or value.get("execution_controls", {}).get("external_effects_enabled")
        is not False
        or value.get("evidence_boundary", {}).get("network_calls_made") != 0
        or value.get("evidence_boundary", {}).get("credentials_read") is not False
    ):
        raise AdaptiveFormalProControllerV2Error("v2 stage candidate drift")
    expected_root = _display_path(
        OUTPUT_BASE / f"{stage}-{scope['execution_identity']}"
    )
    if scope.get("output_root") != expected_root:
        raise AdaptiveFormalProControllerV2Error("v2 output identity drift")
    for lock in value.get("artifact_locks", []):
        v1._verify_file_lock(lock)
    for lock in value.get("source_checkpoint_locks", []):
        v1._verify_file_lock(lock)
    return copy.deepcopy(dict(value))


def write_stage_candidate(stage: str) -> dict[str, Any]:
    value = build_stage_candidate(stage)
    _write_json(candidate_path(stage), value)
    return value


def verify_stage_candidate(stage: str) -> dict[str, Any]:
    return validate_stage_candidate(_read_json(candidate_path(stage)), stage=stage)


def _candidate_lock(stage: str) -> dict[str, Any]:
    return _file_lock(candidate_path(stage), include_manifest=True)


def build_stage_admission(
    stage: str, *, owner_statement_sha256: str, approved_at: str
) -> dict[str, Any]:
    candidate = verify_stage_candidate(stage)
    if owner_statement_sha256 != OWNER_STATEMENT_SHA256:
        raise AdaptiveFormalProControllerV2Error("owner approval digest drift")
    predecessor_lock = _predecessor_lock(stage)
    order_context = order_gate.require_predecessor_before_admission(
        stage,
        successor_candidate_lock=_candidate_lock(stage),
        predecessor_review_lock=predecessor_lock,
    )
    command = canonical_stage_command(stage)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "order_bound_adaptive_stage_execution_authorization",
        "approved_at": approved_at,
        "status": "activated_for_one_exact_order_bound_adaptive_stage",
        "stage": stage,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "order_gate_manifest_sha256": order_context[
            "order_gate_manifest_sha256"
        ],
        "predecessor_review_lock": predecessor_lock,
        "owner_statement_sha256": owner_statement_sha256,
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "run_id": candidate["scope"]["run_id"],
        "execution_identity": candidate["scope"]["execution_identity"],
        "authorized_case_ids": candidate["scope"]["authorized_case_ids"],
        "authorization": {
            "stage_execution_authorized": True,
            "terminal_query_replay_authorized": False,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_stage_admission(
    stage: str, *, owner_statement_sha256: str, approved_at: str
) -> dict[str, Any]:
    value = build_stage_admission(
        stage,
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(admission_path(stage), value)
    return value


def validate_stage_admission(value: Any, *, stage: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveFormalProControllerV2Error("stage admission must be object")
    expected = build_stage_admission(
        stage,
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise AdaptiveFormalProControllerV2Error("v2 stage admission drift")
    return copy.deepcopy(dict(value))


def execute_stage(
    stage: str, *, selected_admission: Path, config_path: Path | None
) -> dict[str, Any]:
    with _delegated_runtime():
        return v1.execute_stage(
            stage,
            selected_admission=selected_admission,
            config_path=config_path,
        )


def write_technical_review(stage: str) -> dict[str, Any]:
    with _delegated_runtime():
        return v1.write_technical_review(stage)


def write_hardest_selection() -> dict[str, Any]:
    with _delegated_runtime():
        return v1.write_hardest_selection()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-stage", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    action.add_argument("--write-hardest-selection", action="store_true")
    parser.add_argument("--stage", choices=tuple(v1.STAGES), required=True)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    selected = args.admission or admission_path(args.stage)
    if args.write_hardest_selection:
        if args.stage != "pro_hardest_2000":
            parser.error(
                "--write-hardest-selection requires --stage pro_hardest_2000"
            )
        value = write_hardest_selection()
    elif args.write_candidate:
        value = write_stage_candidate(args.stage)
    elif args.verify_candidate:
        value = verify_stage_candidate(args.stage)
    elif args.write_admission:
        if not args.owner_statement_sha256 or not args.approved_at:
            parser.error("admission requires owner digest and approved time")
        value = write_stage_admission(
            args.stage,
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
        )
    elif args.verify_admission:
        value = validate_stage_admission(
            _read_json(selected), stage=args.stage
        )
    elif args.execute_stage:
        value = execute_stage(
            args.stage,
            selected_admission=selected,
            config_path=args.config,
        )
    else:
        value = write_technical_review(args.stage)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
