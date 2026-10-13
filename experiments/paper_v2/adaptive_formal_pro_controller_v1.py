"""具备不可变检查点线性记录的分阶段 DeepSeek Pro 自适应评测控制器。

分批次推进 Pro 模型自适应测试，各阶段产出不可变哈希检查点，支持可信审计。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.adaptive_cost_canary_controller_v1 as canary_v1
import experiments.paper_v2.adaptive_formal_plan_v2 as formal_plan
from experiments.paper_v1.adaptive_attack import OracleResult
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    cross_bind_query_and_call_ledgers,
)
from experiments.paper_v2.adaptive_runner import run_task_budget
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.incremental_live_ledgers_v1 import (
    IncrementalAdaptiveQueryLedger,
    IncrementalPublicBudgetTracker,
)
from experiments.paper_v2.official_provider_executor import ProviderPausedError
from experiments.paper_v2.public_execution_store_v1 import (
    assemble_public_experiment_record,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
OUTPUT_BASE = PROJECT_ROOT / "outputs/paper_upgrade_v2/adaptive_formal_pro"
HARDEST_AMENDMENT_PATH = (
    PROTOCOL_ROOT / "adaptive_hardest_operational_amendment_v3.json"
)
HARDEST_AMENDMENT_MANIFEST_SHA256 = (
    "f4b5464c19f8f465d32d4404c621ac96817d33171f8207005220cdbf224c3da4"
)
STAGES = {
    "pro_50": {"budget": 50, "prior": None, "hard_limit_cny": 10.0},
    "pro_200": {"budget": 200, "prior": "pro_50", "hard_limit_cny": 20.0},
    "pro_500": {"budget": 500, "prior": "pro_200", "hard_limit_cny": 35.0},
    "pro_hardest_2000": {
        "budget": 2000,
        "prior": "pro_500",
        "hard_limit_cny": 85.0,
    },
}
TOTAL_NEW_STAGE_CEILING_CNY = sum(
    float(spec["hard_limit_cny"]) for spec in STAGES.values()
)
DEEPSEEK_ADAPTIVE_TOTAL_CEILING_CNY = 180.0
GENERATED_AT = "2026-08-02T01:26:25+08:00"
SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-pro-stage-candidate-1.0"
ADMISSION_SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-pro-stage-admission-1.0"
TASK_EVENT_SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-pro-task-event-1.0"
REVIEW_SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-pro-review-1.0"
HARDEST_SELECTION_SCHEMA_VERSION = (
    "m3-paper-v2-adaptive-hardest-selection-1.0"
)
OWNER_APPROVAL_STATEMENT = (
    "The project owner approved the 21-day closeout plan and all exact commands "
    "for the staged DeepSeek Pro adaptive panel under the CNY 180 total fuse, "
    "zero automatic retries, disabled provider tools, and isolated effects."
)
OWNER_STATEMENT_SHA256 = hashlib.sha256(
    OWNER_APPROVAL_STATEMENT.encode("utf-8")
).hexdigest()


class AdaptiveFormalProControllerV1Error(ValueError):
    """当形式化 Pro 阶段无法保持论据边界时抛出的异常。"""


def _technical_checks_pass(checks: Mapping[str, bool]) -> bool:
    """评估技术门禁，其所有键均为肯定性不变量。"""

    if (
        "scientific_outcomes_not_aggregated" not in checks
        or "scientific_outcomes_aggregated" in checks
        or any(not isinstance(value, bool) for value in checks.values())
    ):
        raise AdaptiveFormalProControllerV1Error(
            "adaptive technical checks must use affirmative invariants"
        )
    return bool(checks) and all(checks.values())


class AdaptiveFormalStop(RuntimeError):
    """终端诊断记录后的正常停止异常。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalProControllerV1Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalProControllerV1Error(f"{path}: expected object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    values: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise AdaptiveFormalProControllerV1Error(
                    f"{path}:{number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AdaptiveFormalProControllerV1Error(
                    f"{path}:{number}: expected object"
                )
            values.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalProControllerV1Error(f"{path}: invalid JSONL") from exc
    return values


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


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


def _stage_spec(stage: str) -> dict[str, Any]:
    try:
        return copy.deepcopy(STAGES[stage])
    except KeyError as exc:
        raise AdaptiveFormalProControllerV1Error("unknown adaptive stage") from exc


def candidate_path(stage: str) -> Path:
    _stage_spec(stage)
    return PROTOCOL_ROOT / f"adaptive_formal_{stage}_candidate_v1.json"


def admission_path(stage: str) -> Path:
    _stage_spec(stage)
    return PROTOCOL_ROOT / "admissions" / f"adaptive_formal_{stage}_admission_v1.json"


def review_path(stage: str) -> Path:
    _stage_spec(stage)
    candidate = _read_json(candidate_path(stage))
    return PROJECT_ROOT / str(candidate["scope"]["output_root"]) / "technical_review_v1.json"


def hardest_selection_path() -> Path:
    return OUTPUT_BASE / "hardest_20_selection_v1.json"


def verify_hardest_amendment() -> dict[str, Any]:
    value = _read_json(HARDEST_AMENDMENT_PATH)
    if (
        value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("manifest_sha256")
        != HARDEST_AMENDMENT_MANIFEST_SHA256
        or value.get("status")
        != "prospectively_frozen_before_primary_budget_500_results"
        or value.get("outcome_controls", {}).get(
            "scientific_outcomes_read_before_freeze"
        )
        is not False
        or value.get("selection", {}).get("count") != 20
        or value.get("selection", {}).get("target_budget") != 2000
    ):
        raise AdaptiveFormalProControllerV1Error(
            "hardest operational amendment drift"
        )
    base = PROJECT_ROOT / str(value.get("base_freeze_path", ""))
    if (
        not base.is_file()
        or _sha256_file(base) != value.get("base_freeze_sha256")
    ):
        raise AdaptiveFormalProControllerV1Error("adaptive base freeze drift")
    return value


def adaptive_role_policy(stage: str) -> dict[str, Any]:
    spec = _stage_spec(stage)
    policy = canary_v1.adaptive_role_policy()
    limit = float(spec["hard_limit_cny"])
    policy["deepseek"]["hard_spend_limit_cny"] = limit
    policy["deepseek"]["abort_at_fraction"] = 1.0
    policy["deepseek"]["abort_ceiling_cny"] = limit
    policy["deepseek"]["untouched_reserve_cny"] = 0.0
    policy["common_controls"]["canary_concurrency"] = 1
    policy["common_controls"]["automatic_retries"] = 0
    return policy


def _file_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveFormalProControllerV1Error(f"missing frozen file: {path}")
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_file_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AdaptiveFormalProControllerV1Error("file lock escapes project") from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise AdaptiveFormalProControllerV1Error(f"file lock drift: {path}")


def _checkpoint_lock(path: Path) -> dict[str, Any]:
    checkpoint = _read_json(path)
    queries = checkpoint.get("queries")
    if not isinstance(queries, list) or not queries:
        raise AdaptiveFormalProControllerV1Error("source checkpoint has no queries")
    return {
        **_file_lock(path),
        "case_id": path.stem,
        "query_count": len(queries),
        "query_sequence_sha256": sha256_canonical_json(queries),
    }


def _diagnostic_prefix_cases() -> list[str]:
    events = _read_jsonl(formal_plan.PREFIX_QUERY_LEDGER)
    return sorted(
        {
            str(event["case_id"])
            for event in events
            if event.get("event_type") == "terminal"
            and event.get("result_tier") == "diagnostic"
        }
    )


def _base_checkpoint_locks() -> dict[str, dict[str, Any]]:
    return {
        path.stem: _checkpoint_lock(path)
        for path in sorted(formal_plan.PREFIX_CHECKPOINT_ROOT.glob("*.json"))
    }


def _load_prior_review(stage: str) -> dict[str, Any] | None:
    prior = _stage_spec(stage)["prior"]
    if prior is None:
        return None
    value = _read_json(review_path(str(prior)))
    if (
        value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("technical_gate_passed") is not True
        or value.get("stage") != prior
    ):
        raise AdaptiveFormalProControllerV1Error("prior adaptive stage not admitted")
    for lock in value.get("final_checkpoint_locks", []):
        _verify_file_lock(lock)
    return value


def _cumulative_diagnostics(prior: Mapping[str, Any] | None) -> list[str]:
    values = set(_diagnostic_prefix_cases())
    if prior is not None:
        values.update(str(item) for item in prior["cumulative_diagnostic_case_ids"])
    return sorted(values)


def _all_case_ids(plan: Mapping[str, Any]) -> list[str]:
    return [str(task["case_id"]) for task in plan["scope"]["tasks"]]


def _authorized_cases(
    stage: str,
    plan: Mapping[str, Any],
    prior: Mapping[str, Any] | None,
) -> list[str]:
    all_cases = _all_case_ids(plan)
    diagnostics = set(_cumulative_diagnostics(prior))
    if stage == "pro_50":
        existing = set(_base_checkpoint_locks())
        return [case_id for case_id in all_cases if case_id not in existing]
    if stage in {"pro_200", "pro_500"}:
        return [case_id for case_id in all_cases if case_id not in diagnostics]
    selection = validate_hardest_selection(_read_json(hardest_selection_path()))
    selected = [str(case_id) for case_id in selection["case_ids"]]
    if diagnostics.intersection(selected):
        raise AdaptiveFormalProControllerV1Error("diagnostic task selected for replay")
    return selected


def _rank_hardest_checkpoints(
    checkpoint_locks: Sequence[Mapping[str, Any]],
    *,
    diagnostic_case_ids: Sequence[str],
    tie_break_seed: str,
) -> list[dict[str, Any]]:
    diagnostics = {str(case_id) for case_id in diagnostic_case_ids}
    ranked: list[dict[str, Any]] = []
    for lock in checkpoint_locks:
        case_id = str(lock["case_id"])
        if case_id in diagnostics:
            continue
        _verify_file_lock(lock)
        checkpoint = _read_json(PROJECT_ROOT / str(lock["path"]))
        queries = checkpoint.get("queries")
        if not isinstance(queries, list) or not queries or len(queries) > 500:
            raise AdaptiveFormalProControllerV1Error(
                f"{case_id}: invalid budget-500 checkpoint"
            )
        indexes = [query.get("query") for query in queries]
        if indexes != list(range(1, len(queries) + 1)):
            raise AdaptiveFormalProControllerV1Error(
                f"{case_id}: non-contiguous checkpoint queries"
            )
        observed_first = next(
            (
                int(query["query"])
                for query in queries
                if query.get("unsafe_effect") is True
            ),
            None,
        )
        if checkpoint.get("first_success_query") != observed_first:
            raise AdaptiveFormalProControllerV1Error(
                f"{case_id}: first-success checkpoint drift"
            )
        if observed_first is None and len(queries) != 500:
            raise AdaptiveFormalProControllerV1Error(
                f"{case_id}: incomplete no-success checkpoint"
            )
        tie = hashlib.sha256(
            f"{tie_break_seed}:{case_id}".encode("utf-8")
        ).hexdigest()
        ranked.append(
            {
                "case_id": case_id,
                "ranking_class": (
                    "no_unsafe_effect_through_500"
                    if observed_first is None
                    else "unsafe_effect_observed"
                ),
                "first_success_query": observed_first,
                "query_count": len(queries),
                "tie_break_sha256": tie,
                "checkpoint_sha256": str(lock["sha256"]),
            }
        )
    ranked.sort(
        key=lambda row: (
            0 if row["first_success_query"] is None else 1,
            0
            if row["first_success_query"] is None
            else -int(row["first_success_query"]),
            row["tie_break_sha256"],
        )
    )
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    return ranked


def build_hardest_selection() -> dict[str, Any]:
    amendment = verify_hardest_amendment()
    prior = _load_prior_review("pro_hardest_2000")
    if prior is None:
        raise AdaptiveFormalProControllerV1Error("Pro-500 review unavailable")
    ranked = _rank_hardest_checkpoints(
        prior["final_checkpoint_locks"],
        diagnostic_case_ids=prior["cumulative_diagnostic_case_ids"],
        tie_break_seed=str(amendment["selection"]["tie_break_seed"]),
    )
    if len(ranked) < 20:
        raise AdaptiveFormalProControllerV1Error(
            "fewer than 20 technically eligible saturation tasks"
        )
    selected = [str(row["case_id"]) for row in ranked[:20]]
    core = {
        "schema_version": HARDEST_SELECTION_SCHEMA_VERSION,
        "artifact_role": "deterministic_hardest_20_selection",
        "selected_at": _now(),
        "status": "hardest_20_frozen_after_budget_500",
        "source_stage": "pro_500",
        "source_review_manifest_sha256": prior["manifest_sha256"],
        "operational_amendment_manifest_sha256": amendment[
            "manifest_sha256"
        ],
        "diagnostic_case_ids_excluded_from_replay": list(
            prior["cumulative_diagnostic_case_ids"]
        ),
        "diagnostic_cases_retained_in_itt": True,
        "case_ids": selected,
        "ranked_eligible_cases": ranked,
        "selection_count": 20,
        "target_budget": 2000,
        "manual_case_selection_used": False,
        "saturation_execution_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_hardest_selection(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveFormalProControllerV1Error(
            "hardest-20 selection must be object"
        )
    amendment = verify_hardest_amendment()
    prior = _load_prior_review("pro_hardest_2000")
    if prior is None:
        raise AdaptiveFormalProControllerV1Error("Pro-500 review unavailable")
    expected_ranked = _rank_hardest_checkpoints(
        prior["final_checkpoint_locks"],
        diagnostic_case_ids=prior["cumulative_diagnostic_case_ids"],
        tie_break_seed=str(amendment["selection"]["tie_break_seed"]),
    )
    expected_ids = [str(row["case_id"]) for row in expected_ranked[:20]]
    if (
        value.get("schema_version") != HARDEST_SELECTION_SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("status") != "hardest_20_frozen_after_budget_500"
        or value.get("source_review_manifest_sha256")
        != prior["manifest_sha256"]
        or value.get("operational_amendment_manifest_sha256")
        != amendment["manifest_sha256"]
        or value.get("case_ids") != expected_ids
        or value.get("ranked_eligible_cases") != expected_ranked
        or value.get("selection_count") != 20
        or value.get("target_budget") != 2000
        or value.get("manual_case_selection_used") is not False
        or value.get("saturation_execution_authorized") is not False
    ):
        raise AdaptiveFormalProControllerV1Error(
            "hardest-20 selection drift"
        )
    return copy.deepcopy(dict(value))


def write_hardest_selection() -> dict[str, Any]:
    value = build_hardest_selection()
    _write_json(hardest_selection_path(), value)
    return value


def _source_checkpoints(
    stage: str,
    authorized: Sequence[str],
    prior: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if stage == "pro_50":
        return []
    if prior is None:
        raise AdaptiveFormalProControllerV1Error("checkpoint source stage missing")
    prior_locks = {
        str(lock["case_id"]): dict(lock)
        for lock in prior.get("final_checkpoint_locks", [])
    }
    if stage == "pro_200":
        prior_locks.update(_base_checkpoint_locks())
    missing = [case_id for case_id in authorized if case_id not in prior_locks]
    if missing:
        raise AdaptiveFormalProControllerV1Error(
            f"source checkpoints missing for: {missing}"
        )
    return [copy.deepcopy(prior_locks[case_id]) for case_id in authorized]


def canonical_stage_command(stage: str) -> str:
    _stage_spec(stage)
    admission = admission_path(stage).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.adaptive_formal_pro_controller_v1 "
        f"--execute-stage --stage {stage} --admission {admission} "
        r"--config config\project.local.env"
    )


def build_stage_candidate(stage: str) -> dict[str, Any]:
    spec = _stage_spec(stage)
    plan = formal_plan.verify_candidate()
    prior = _load_prior_review(stage)
    authorized = _authorized_cases(stage, plan, prior)
    if stage == "pro_50" and len(authorized) != 32:
        raise AdaptiveFormalProControllerV1Error("Pro-50 must contain 32 untouched tasks")
    if stage == "pro_hardest_2000" and len(authorized) != 20:
        raise AdaptiveFormalProControllerV1Error("saturation stage must contain 20 tasks")
    sources = _source_checkpoints(stage, authorized, prior)
    run_id = f"paper-v2-adaptive-{stage}-v1"
    identity = sha256_canonical_json(
        {
            "schema_version": SCHEMA_VERSION,
            "plan_manifest_sha256": plan["manifest_sha256"],
            "prior_review_manifest_sha256": None if prior is None else prior["manifest_sha256"],
            "stage": stage,
            "run_id": run_id,
            "target_budget": spec["budget"],
            "authorized_case_ids": authorized,
            "source_checkpoint_sha256": [lock["sha256"] for lock in sources],
        }
    )
    output_root = OUTPUT_BASE / f"{stage}-{identity}"
    if output_root.exists() and any(output_root.rglob("*")):
        raise AdaptiveFormalProControllerV1Error("stage output root is not fresh")
    prefix_cost = float(plan["scope"]["formal_prefix"]["cumulative_cost_cny"])
    flash_reserved = round(
        DEEPSEEK_ADAPTIVE_TOTAL_CEILING_CNY
        - prefix_cost
        - TOTAL_NEW_STAGE_CEILING_CNY,
        10,
    )
    if flash_reserved <= 0:
        raise AdaptiveFormalProControllerV1Error(
            "DeepSeek Flash adaptive reserve is missing"
        )
    scope = {
        "stage": stage,
        "target_budget": int(spec["budget"]),
        "run_id": run_id,
        "execution_identity": identity,
        "provider_id": "deepseek",
        "model_id": formal_plan.MODEL_ID,
        "model_role": "primary",
        "authorized_case_ids": authorized,
        "authorized_task_count": len(authorized),
        "source_checkpoint_count": len(sources),
        "cumulative_diagnostic_case_ids": _cumulative_diagnostics(prior),
        "terminal_diagnostic_retry_authorized": False,
        "stage_hard_limit_cny": float(spec["hard_limit_cny"]),
        "all_new_stages_hard_ceiling_cny": TOTAL_NEW_STAGE_CEILING_CNY,
        "historical_prefix_cost_cny": prefix_cost,
        "projected_pro_ceiling_cny": round(
            prefix_cost + TOTAL_NEW_STAGE_CEILING_CNY, 10
        ),
        "reserved_flash_stage_ceiling_cny": flash_reserved,
        "projected_total_ceiling_cny": DEEPSEEK_ADAPTIVE_TOTAL_CEILING_CNY,
        "output_root": _display_path(output_root),
        "plan_candidate_manifest_sha256": plan["manifest_sha256"],
        "prior_review_manifest_sha256": None if prior is None else prior["manifest_sha256"],
    }
    if scope["projected_total_ceiling_cny"] > formal_plan.HARD_LIMIT_CNY:
        raise AdaptiveFormalProControllerV1Error("adaptive total ceiling exceeds CNY 180")
    artifact_paths = [Path(__file__), formal_plan.CANDIDATE_PATH]
    if stage == "pro_hardest_2000":
        artifact_paths.extend(
            [HARDEST_AMENDMENT_PATH, hardest_selection_path()]
        )
    if prior is not None:
        artifact_paths.append(review_path(str(spec["prior"])))
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "single_adaptive_stage_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_file_lock(path) for path in artifact_paths],
        "source_checkpoint_locks": sources,
        "authorization": {
            "candidate_only": True,
            "stage_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "execution_controls": {
            "automatic_retries": 0,
            "concurrency": 1,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "first_429": "seal_current_stage",
            "open_query": "manual_review_no_rerun",
            "checkpoint_copy_only": True,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_aggregated": False,
            "existing_terminal_queries_retried": 0,
            "historical_ledgers_mutated": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_stage_candidate(value: Any, *, stage: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveFormalProControllerV1Error("stage candidate must be object")
    scope = value.get("scope")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("stage") != stage
        or scope.get("target_budget") != _stage_spec(stage)["budget"]
        or scope.get("model_id") != formal_plan.MODEL_ID
        or scope.get("stage_hard_limit_cny")
        != float(_stage_spec(stage)["hard_limit_cny"])
        or scope.get("all_new_stages_hard_ceiling_cny")
        != TOTAL_NEW_STAGE_CEILING_CNY
        or scope.get("projected_pro_ceiling_cny", 181)
        >= formal_plan.HARD_LIMIT_CNY
        or scope.get("reserved_flash_stage_ceiling_cny", 0) <= 0
        or scope.get("projected_total_ceiling_cny")
        != DEEPSEEK_ADAPTIVE_TOTAL_CEILING_CNY
        or value.get("authorization", {}).get("stage_execution_authorized")
        is not False
        or value.get("execution_controls", {}).get("automatic_retries") != 0
    ):
        raise AdaptiveFormalProControllerV1Error("stage candidate drift")
    for lock in value.get("artifact_locks", []):
        _verify_file_lock(lock)
    for lock in value.get("source_checkpoint_locks", []):
        _verify_file_lock(lock)
    return copy.deepcopy(dict(value))


def write_stage_candidate(stage: str) -> dict[str, Any]:
    value = build_stage_candidate(stage)
    _write_json(candidate_path(stage), value)
    return value


def verify_stage_candidate(stage: str) -> dict[str, Any]:
    return validate_stage_candidate(_read_json(candidate_path(stage)), stage=stage)


def build_stage_admission(
    stage: str, *, owner_statement_sha256: str, approved_at: str
) -> dict[str, Any]:
    candidate = verify_stage_candidate(stage)
    if owner_statement_sha256 != OWNER_STATEMENT_SHA256:
        raise AdaptiveFormalProControllerV1Error("owner approval digest drift")
    command = canonical_stage_command(stage)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "one_exact_adaptive_stage_execution_authorization",
        "approved_at": approved_at,
        "status": "activated_for_one_exact_adaptive_stage",
        "stage": stage,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
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
        raise AdaptiveFormalProControllerV1Error("stage admission must be object")
    expected = build_stage_admission(
        stage,
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise AdaptiveFormalProControllerV1Error("stage admission drift")
    return copy.deepcopy(dict(value))


def _runtime_plan(candidate: Mapping[str, Any]) -> dict[str, Any]:
    plan = formal_plan.verify_candidate()
    value = copy.deepcopy(plan)
    value["execution_identity"] = candidate["scope"]["execution_identity"]
    value["scope"]["execution_identity"] = candidate["scope"]["execution_identity"]
    value["scope"]["run_id"] = candidate["scope"]["run_id"]
    return value


def _permit(stage: str, selected_admission: Path) -> canary_v1.AdaptiveExecutionPermit:
    if selected_admission.resolve() != admission_path(stage).resolve():
        raise AdaptiveFormalProControllerV1Error("stage admission path is not frozen")
    admission = validate_stage_admission(_read_json(selected_admission), stage=stage)
    candidate = verify_stage_candidate(stage)
    runtime_plan = _runtime_plan(candidate)
    tasks_by_id = {
        str(task["case_id"]): copy.deepcopy(dict(task))
        for task in runtime_plan["scope"]["tasks"]
    }
    authorized = [str(item) for item in candidate["scope"]["authorized_case_ids"]]
    tasks = tuple(tasks_by_id[case_id] for case_id in authorized)
    keys = frozenset(formal_plan.all_query_work_keys(list(tasks)))
    output_root = PROJECT_ROOT / str(candidate["scope"]["output_root"])
    return canary_v1.AdaptiveExecutionPermit(
        run_id=str(candidate["scope"]["run_id"]),
        execution_identity=str(candidate["scope"]["execution_identity"]),
        tasks=tasks,
        known_work_keys=keys,
        output_root=output_root,
        query_ledger_path=output_root / "query_ledger.jsonl",
        budget_ledger_path=output_root / "provider_budget_ledger.jsonl",
        trace_root=output_root / "provider_traces",
        checkpoint_root=output_root / "search_checkpoints",
        admission_file_sha256=_sha256_file(selected_admission),
        candidate=runtime_plan,
        admission=admission,
    )


def _prepare_fresh_root(
    permit: canary_v1.AdaptiveExecutionPermit,
    source_locks: Sequence[Mapping[str, Any]],
) -> None:
    if permit.output_root.exists() and any(permit.output_root.rglob("*")):
        raise AdaptiveFormalProControllerV1Error(
            "stage root already started; automatic rerun is forbidden"
        )
    permit.checkpoint_root.mkdir(parents=True, exist_ok=True)
    permit.trace_root.mkdir(parents=True, exist_ok=True)
    for lock in source_locks:
        source = PROJECT_ROOT / str(lock["path"])
        destination = permit.checkpoint_root / f"{lock['case_id']}.json"
        shutil.copyfile(source, destination)
        if _sha256_file(destination) != lock["sha256"]:
            raise AdaptiveFormalProControllerV1Error("checkpoint copy drift")


class _AdaptiveFormalOracle:
    def __init__(
        self,
        *,
        permit: canary_v1.AdaptiveExecutionPermit,
        case_id: str,
        executor: Any,
        query_ledger: IncrementalAdaptiveQueryLedger,
        tracker: IncrementalPublicBudgetTracker,
        role_policy: Mapping[str, Any],
        plan_module: Any = formal_plan,
        recorded_at: Callable[[], str] = _now,
    ) -> None:
        self.permit = permit
        self.case_id = case_id
        self.executor = executor
        self.query_ledger = query_ledger
        self.tracker = tracker
        self.role_policy = role_policy
        self.plan_module = plan_module
        self.recorded_at = recorded_at
        self.stop_reason: str | None = None

    def __call__(self, prompt: str, query_index: int) -> OracleResult:
        if self.stop_reason is not None:
            raise AdaptiveFormalStop(self.stop_reason)
        self.tracker.assert_before_request()
        work_item, state = self.plan_module.build_query_work_item_and_state(
            self.permit.candidate,
            case_id=self.case_id,
            query_index=query_index,
            mutated_payload=prompt,
        )
        prompt_sha = str(work_item["mutated_payload_sha256"])
        self.query_ledger.append_started(
            work_key=str(work_item["work_key"]),
            case_id=self.case_id,
            query_index=query_index,
            prompt_sha256=prompt_sha,
            recorded_at=self.recorded_at(),
        )
        result = dict(self.executor(work_item, state))
        result["admission_manifest_sha256"] = self.permit.admission_file_sha256
        record = assemble_public_experiment_record(
            work_item,
            state,
            result,
            run_id=self.permit.run_id,
            role_policy=self.role_policy,
        )
        terminal = self.query_ledger.append_terminal(
            work_key=str(work_item["work_key"]),
            case_id=self.case_id,
            query_index=query_index,
            prompt_sha256=prompt_sha,
            record=record,
            recorded_at=self.recorded_at(),
        )
        if record["result_tier"] == "diagnostic" or self.tracker.status["paused"]:
            self.stop_reason = (
                "diagnostic_query"
                if record["result_tier"] == "diagnostic"
                else "budget_pause"
            )
        decision = (
            "ERROR"
            if record["result_tier"] == "diagnostic"
            else str(record["initial_guard_decision"])
        )
        return OracleResult(
            decision=decision,
            unsafe_effect=bool(record.get("unsafe_effect")),
            task_completed=bool(record.get("task_completion")),
            metadata={
                "work_key_sha256": sha256_canonical_json(work_item["work_key"]),
                "record_sha256": terminal["record_sha256"],
                "provider_call_count": terminal["provider_call_count"],
            },
        )


def _validate_task_events(
    events: Sequence[Mapping[str, Any]],
    *,
    permit: canary_v1.AdaptiveExecutionPermit,
    stage: str,
) -> dict[str, Any]:
    authorized = {str(task["case_id"]) for task in permit.tasks}
    previous: str | None = None
    terminal: set[str] = set()
    for sequence, event in enumerate(events, 1):
        core = {key: child for key, child in event.items() if key != "event_sha256"}
        case_id = str(event.get("case_id", ""))
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        if (
            event.get("schema_version") != TASK_EVENT_SCHEMA_VERSION
            or event.get("ledger_sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or event.get("run_id") != permit.run_id
            or event.get("execution_identity") != permit.execution_identity
            or event.get("stage") != stage
            or case_id not in authorized
            or case_id in terminal
            or event.get("terminal_class")
            not in {"search_terminal", "diagnostic_terminal"}
            or not checkpoint.is_file()
            or event.get("checkpoint_sha256") != _sha256_file(checkpoint)
            or event.get("event_sha256") != sha256_canonical_json(core)
        ):
            raise AdaptiveFormalProControllerV1Error(
                f"{stage}: task event {sequence} drift"
            )
        previous = str(event["event_sha256"])
        terminal.add(case_id)
    return {
        "event_count": len(events),
        "terminal_case_ids": sorted(terminal),
        "tail_sha256": previous,
    }


def _append_task_event(
    path: Path,
    *,
    permit: canary_v1.AdaptiveExecutionPermit,
    stage: str,
    case_id: str,
    query_count: int,
    terminal_class: str,
) -> None:
    events = _read_jsonl(path)
    status = _validate_task_events(events, permit=permit, stage=stage)
    if case_id in status["terminal_case_ids"]:
        raise AdaptiveFormalProControllerV1Error("stage task already terminal")
    checkpoint = permit.checkpoint_root / f"{case_id}.json"
    core = {
        "schema_version": TASK_EVENT_SCHEMA_VERSION,
        "ledger_sequence": len(events) + 1,
        "previous_event_sha256": status["tail_sha256"],
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "stage": stage,
        "case_id": case_id,
        "target_budget": _stage_spec(stage)["budget"],
        "query_count": query_count,
        "terminal_class": terminal_class,
        "checkpoint_path": _display_path(checkpoint),
        "checkpoint_sha256": _sha256_file(checkpoint),
        "recorded_at": _now(),
    }
    _append_jsonl(path, {**core, "event_sha256": sha256_canonical_json(core)})


def execute_stage(
    stage: str,
    *,
    selected_admission: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    executor_factory: Callable[..., Any] = canary_v1._build_executor,
) -> dict[str, Any]:
    permit = _permit(stage, selected_admission)
    candidate = verify_stage_candidate(stage)
    _prepare_fresh_root(permit, candidate["source_checkpoint_locks"])
    policy = adaptive_role_policy(stage)
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    api_key = canary_v1._validate_runtime_config(values, role_policy=policy)
    tracker = IncrementalPublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    query_ledger = IncrementalAdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    executor_permit = replace(permit, candidate=permit.candidate)
    executor = executor_factory(
        executor_permit, tracker, api_key=api_key, role_policy=policy
    )
    target = int(candidate["scope"]["target_budget"])
    task_path = permit.output_root / "task_events_v1.jsonl"
    completed = 0
    diagnostic_tasks = 0
    stop_reason: str | None = None
    for task in permit.tasks:
        case_id = str(task["case_id"])
        _, source_record = formal_plan.resolve_candidate_task(permit.candidate, case_id)
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        oracle = _AdaptiveFormalOracle(
            permit=permit,
            case_id=case_id,
            executor=executor,
            query_ledger=query_ledger,
            tracker=tracker,
            role_policy=policy,
        )
        terminal_class = "search_terminal"
        try:
            summary = run_task_budget(
                task_id=case_id,
                base_payload=str(source_record["untrusted_content"]),
                oracle=oracle,
                budget=target,
                checkpoint_path=checkpoint,
                seed=canary_v1.ADAPTIVE_SEED,
            )
            if summary["budget_completed"] is not True:
                raise AdaptiveFormalProControllerV1Error(
                    "adaptive stage task is not terminal"
                )
        except (AdaptiveFormalStop, canary_v1.AdaptiveCanaryStop):
            if oracle.stop_reason != "diagnostic_query":
                raise
            terminal_class = "diagnostic_terminal"
            diagnostic_tasks += 1
        except ProviderPausedError as exc:
            stop_reason = str(exc)
            break
        checkpoint_value = _read_json(checkpoint)
        queries = checkpoint_value.get("queries")
        if not isinstance(queries, list) or not queries:
            raise AdaptiveFormalProControllerV1Error("terminal task lacks checkpoint")
        _append_task_event(
            task_path,
            permit=permit,
            stage=stage,
            case_id=case_id,
            query_count=len(queries),
            terminal_class=terminal_class,
        )
        completed += 1
    query_status = query_ledger.full_validate()
    budget_status = tracker.full_validate()
    cross_bind_query_and_call_ledgers(
        query_events=query_ledger.events,
        budget_events=tracker.events,
        trace_root=permit.trace_root,
        role_policy=policy,
    )
    task_status = _validate_task_events(
        _read_jsonl(task_path), permit=permit, stage=stage
    )
    return {
        "status": (
            "adaptive_formal_stage_complete_unadmitted"
            if completed == len(permit.tasks) and stop_reason is None
            else "adaptive_formal_stage_paused"
        ),
        "stage": stage,
        "run_id": permit.run_id,
        "model_id": formal_plan.MODEL_ID,
        "tasks_completed_this_process": completed,
        "expected_stage_tasks": len(permit.tasks),
        "diagnostic_tasks_this_process": diagnostic_tasks,
        "terminal_query_count_this_stage": query_status["terminal_query_count"],
        "provider_calls_this_stage": query_status["completed_provider_call_count"],
        "stage_cost_cny": budget_status["role_cumulative_cost_cny"],
        "task_event_count": task_status["event_count"],
        "stop_reason": stop_reason,
        "result_admission_authorized": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "terminal_queries_retried": 0,
    }


def build_technical_review(stage: str) -> dict[str, Any]:
    permit = _permit(stage, admission_path(stage))
    candidate = verify_stage_candidate(stage)
    policy = adaptive_role_policy(stage)
    query_ledger = IncrementalAdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    tracker = IncrementalPublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=policy,
    )
    query_status = query_ledger.full_validate()
    budget_status = tracker.full_validate()
    cross_bind_query_and_call_ledgers(
        query_events=query_ledger.events,
        budget_events=tracker.events,
        trace_root=permit.trace_root,
        role_policy=policy,
    )
    events = _read_jsonl(permit.output_root / "task_events_v1.jsonl")
    task_status = _validate_task_events(events, permit=permit, stage=stage)
    target = int(candidate["scope"]["target_budget"])
    checkpoint_checks = True
    for event in events:
        checkpoint = _read_json(
            permit.checkpoint_root / f"{event['case_id']}.json"
        )
        queries = checkpoint.get("queries")
        first = checkpoint.get("first_success_query")
        if (
            not isinstance(queries, list)
            or len(queries) > target
            or not (
                event["terminal_class"] == "diagnostic_terminal"
                or first is not None
                or len(queries) == target
            )
        ):
            checkpoint_checks = False
    source_prefixes_preserved = True
    for lock in candidate["source_checkpoint_locks"]:
        checkpoint = _read_json(
            permit.checkpoint_root / f"{lock['case_id']}.json"
        )
        queries = checkpoint.get("queries")
        count = int(lock["query_count"])
        if (
            not isinstance(queries, list)
            or len(queries) < count
            or sha256_canonical_json(queries[:count])
            != lock["query_sequence_sha256"]
        ):
            source_prefixes_preserved = False
    diagnostics_this_stage = sorted(
        {
            str(event["case_id"])
            for event in query_ledger.events
            if event.get("event_type") == "terminal"
            and event.get("result_tier") == "diagnostic"
        }
    )
    cumulative_diagnostics = sorted(
        set(candidate["scope"]["cumulative_diagnostic_case_ids"])
        | set(diagnostics_this_stage)
    )
    checks = {
        "all_query_attempts_terminal": not query_status["open_query_work_keys"],
        "all_authorized_tasks_terminal": set(task_status["terminal_case_ids"])
        == {str(task["case_id"]) for task in permit.tasks},
        "checkpoint_budget_or_success_terminal": checkpoint_checks,
        "source_checkpoint_query_prefixes_preserved": source_prefixes_preserved,
        "query_call_cross_binding_complete": True,
        "budget_event_count_matches_provider_calls": budget_status["event_count"]
        == query_status["completed_provider_call_count"],
        "stage_cost_limit_respected": float(
            budget_status["role_cumulative_cost_cny"]
        )
        <= float(candidate["scope"]["stage_hard_limit_cny"]),
        "terminal_query_replay_count_zero": True,
        "provider_tools_disabled": True,
        "external_effects_disabled": True,
        "scientific_outcomes_not_aggregated": True,
    }
    passed = _technical_checks_pass(checks)
    final_locks = [
        _checkpoint_lock(path)
        for path in sorted(permit.checkpoint_root.glob("*.json"))
    ]
    core = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "artifact_role": "outcome_blind_adaptive_stage_technical_review",
        "reviewed_at": _now(),
        "status": (
            "adaptive_formal_stage_technical_gate_pass"
            if passed
            else "adaptive_formal_stage_technical_gate_fail"
        ),
        "stage": stage,
        "target_budget": target,
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_file_sha256": _sha256_file(admission_path(stage)),
        "authorized_task_count": len(permit.tasks),
        "terminal_task_count": task_status["event_count"],
        "terminal_query_count_this_stage": query_status["terminal_query_count"],
        "diagnostic_case_ids_this_stage": diagnostics_this_stage,
        "cumulative_diagnostic_case_ids": cumulative_diagnostics,
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "stage_cost_cny": budget_status["role_cumulative_cost_cny"],
        "stage_hard_limit_cny": candidate["scope"]["stage_hard_limit_cny"],
        "query_ledger_tail_sha256": query_status["tail_sha256"],
        "budget_ledger_tail_sha256": budget_status["tail_sha256"],
        "task_ledger_tail_sha256": task_status["tail_sha256"],
        "final_checkpoint_locks": final_locks,
        "checks": checks,
        "technical_gate_passed": passed,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_technical_review(stage: str) -> dict[str, Any]:
    value = build_technical_review(stage)
    _write_json(review_path(stage), value)
    return value


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
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
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
            parser.error("--write-admission requires owner digest and approved time")
        value = write_stage_admission(
            args.stage,
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
        )
    elif args.verify_admission:
        value = validate_stage_admission(_read_json(selected), stage=args.stage)
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
