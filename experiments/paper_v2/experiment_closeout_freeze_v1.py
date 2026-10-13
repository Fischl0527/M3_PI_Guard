"""在不进行模型调用的前提下冻结 21 天实验收官产物。

固化全周期实验数据仓库、哈希凭单与归档目录。
"""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from experiments.paper_v2.contracts import canonical_json_bytes
from experiments.paper_v2.formal_matrix_abort_review_v3 import (
    DEFAULT_REVIEW as V7_ABORT_REVIEW,
    verify_abort_review,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
PUBLIC_SOURCE_PLAN = PROTOCOL_ROOT / "public_execution_plan_v1.jsonl"
ADAPTIVE_V1 = PROTOCOL_ROOT / "adaptive_attack_freeze_v1.json"
BLIND_KIT = PROTOCOL_ROOT / "independent_blind_authoring_kit_v1"
ADAPTIVE_PREFIX = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary"
)

GEMINI_PUBLIC_PLAN = PROTOCOL_ROOT / "gemini_public_execution_plan_v1.jsonl"
GEMINI_PUBLIC_MANIFEST = (
    PROTOCOL_ROOT / "gemini_public_execution_manifest_v1.json"
)
ADAPTIVE_V2 = PROTOCOL_ROOT / "adaptive_attack_extension_v2.json"
V7_IMMUTABLE_AUDIT = (
    PROTOCOL_ROOT / "formal_matrix_v7_immutable_audit_v1.json"
)
BLIND_INTERFACE = (
    PROTOCOL_ROOT / "independent_blind_closeout_interface_v1.json"
)
CLOSEOUT_CANDIDATE = PROTOCOL_ROOT / "experiment_closeout_candidate_v1.json"

GEMINI_PROVIDER_ID = "gemini"
GEMINI_MODEL_ID = "gemini-3.6-flash"
GEMINI_RUN_ID = "paper-v2-public-gemini-v1-20260801"
FREEZE_TIME = "2026-08-01T23:00:00+08:00"

IDENTITY_FIELDS = frozenset(
    {
        "provider_id",
        "model_id",
        "run_id",
        "execution_identity",
        "work_key",
        "source_work_key",
        "source_execution_identity",
    }
)


class ExperimentCloseoutFreezeV1Error(RuntimeError):
    """当不可变数据源或预期固化发生漂移时抛出的异常。"""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExperimentCloseoutFreezeV1Error(f"{path}: expected object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ExperimentCloseoutFreezeV1Error(
                f"{path}:{line_number}: expected object"
            )
        rows.append(value)
    return rows


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    core = {key: item for key, item in value.items() if key != "manifest_sha256"}
    return _sha256_bytes(canonical_json_bytes(core))


def _artifact_lock(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _public_source_rows() -> list[dict[str, Any]]:
    rows = [
        row
        for row in _read_jsonl(PUBLIC_SOURCE_PLAN)
        if row.get("model_role") == "second"
    ]
    if len(rows) != 1791:
        raise ExperimentCloseoutFreezeV1Error(
            f"expected 1791 frozen second-role rows, observed {len(rows)}"
        )
    work_keys = [str(row["work_key"]) for row in rows]
    if len(set(work_keys)) != len(work_keys):
        raise ExperimentCloseoutFreezeV1Error("source work keys are not unique")
    return rows


def _gemini_execution_identity() -> str:
    return _sha256_bytes(
        canonical_json_bytes(
            {
                "schema_version": "m3-paper-v2-public-execution-identity-1.0",
                "provider_id": GEMINI_PROVIDER_ID,
                "model_id": GEMINI_MODEL_ID,
                "run_id": GEMINI_RUN_ID,
                "source_plan_sha256": _sha256_file(PUBLIC_SOURCE_PLAN),
                "record_count": 1791,
                "automatic_retries": 0,
                "provider_managed_tools_enabled": False,
                "external_effects_enabled": False,
                "paid_ceiling_usd": 0,
            }
        )
    )


def build_gemini_public_plan() -> list[dict[str, Any]]:
    execution_identity = _gemini_execution_identity()
    output: list[dict[str, Any]] = []
    for source in _public_source_rows():
        row = copy.deepcopy(source)
        source_work_key = str(source["work_key"])
        row.update(
            {
                "provider_id": GEMINI_PROVIDER_ID,
                "model_id": GEMINI_MODEL_ID,
                "run_id": GEMINI_RUN_ID,
                "execution_identity": execution_identity,
                "source_work_key": source_work_key,
                "source_execution_identity": str(source["execution_identity"]),
            }
        )
        row["work_key"] = _sha256_bytes(
            canonical_json_bytes(
                {
                    "provider_id": GEMINI_PROVIDER_ID,
                    "model_id": GEMINI_MODEL_ID,
                    "run_id": GEMINI_RUN_ID,
                    "execution_identity": execution_identity,
                    "source_work_key": source_work_key,
                }
            )
        )
        output.append(row)
    if len({str(row["work_key"]) for row in output}) != 1791:
        raise ExperimentCloseoutFreezeV1Error("Gemini work keys are not unique")
    return output


def _paired_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in row.items()
        if key not in IDENTITY_FIELDS
    }


def _public_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "records": len(rows),
        "conditions": dict(sorted(Counter(str(row["condition_id"]) for row in rows).items())),
        "benchmarks": dict(sorted(Counter(str(row["benchmark"]) for row in rows).items())),
        "record_kinds": dict(
            sorted(Counter(str(row["record_kind"]) for row in rows).items())
        ),
        "evaluation_case_types": dict(
            sorted(
                Counter(str(row["evaluation_case_type"]) for row in rows).items()
            )
        ),
    }


def build_gemini_public_manifest() -> dict[str, Any]:
    source = _public_source_rows()
    rows = build_gemini_public_plan()
    expected = {
        "records": 1791,
        "conditions": {
            "m3_full": 597,
            "m3_policy_only": 597,
            "strongest_peer_reviewed_structural_baseline": 597,
        },
        "benchmarks": {"agentdojo-v1": 891, "m3-v2": 900},
        "record_kinds": {"attack": 1200, "benign": 591},
        "evaluation_case_types": {
            "attack": 1200,
            "benign_no_tool": 156,
            "benign_tool": 435,
        },
    }
    counts = _public_counts(rows)
    if counts != expected:
        raise ExperimentCloseoutFreezeV1Error(
            f"Gemini public strata drift: {counts!r}"
        )
    for source_row, gemini_row in zip(source, rows, strict=True):
        if _paired_projection(source_row) != _paired_projection(gemini_row):
            raise ExperimentCloseoutFreezeV1Error(
                f"cross-provider mirror drift at {source_row['work_key']}"
            )
    core = {
        "schema_version": "m3-paper-v2-gemini-public-plan-manifest-1.0",
        "status": "frozen_offline_pending_canary_admission",
        "frozen_at": FREEZE_TIME,
        "run_id": GEMINI_RUN_ID,
        "execution_identity": _gemini_execution_identity(),
        "provider_id": GEMINI_PROVIDER_ID,
        "model_id": GEMINI_MODEL_ID,
        "model_role": "second",
        "source_plan": _artifact_lock(PUBLIC_SOURCE_PLAN),
        "source_role": "second",
        "counts": counts,
        "plan_sha256": _sha256_bytes(_jsonl_bytes(rows)),
        "source_work_key_sequence_sha256": _sha256_bytes(
            canonical_json_bytes([str(row["work_key"]) for row in source])
        ),
        "gemini_work_key_sequence_sha256": _sha256_bytes(
            canonical_json_bytes([str(row["work_key"]) for row in rows])
        ),
        "pairing": {
            "exact_scientific_projection_match": True,
            "source_work_key_retained": True,
            "source_order_retained": True,
            "only_identity_fields_changed": True,
        },
        "execution_policy": {
            "canary_records": 12,
            "maximum_shards": 4,
            "automatic_retries": 0,
            "paid_ceiling_usd": 0,
            "free_tier_only": True,
            "first_http_429": "seal_current_run",
            "pending_only_new_identity_after_quota_day": True,
            "provider_managed_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "network_calls_made": 0,
        "scientific_outcomes_read": 0,
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def _adaptive_prefix_locks() -> list[dict[str, Any]]:
    paths = [
        ADAPTIVE_PREFIX / "query_ledger.jsonl",
        ADAPTIVE_PREFIX / "provider_budget_ledger.jsonl",
        ADAPTIVE_PREFIX / "continuation_task_events_v3.jsonl",
        ADAPTIVE_PREFIX / "technical_cost_review_v3_1.json",
    ]
    paths.extend(
        sorted((ADAPTIVE_PREFIX / "search_checkpoints").glob("*.json"))
    )
    return [_artifact_lock(path) for path in paths]


@functools.lru_cache(maxsize=4)
def _verify_v7_review_for_sha(review_sha256: str) -> dict[str, Any]:
    """在此进程中对每个观测到的审查摘要深度验证 v7 一次。"""

    if _sha256_file(V7_ABORT_REVIEW) != review_sha256:
        raise ExperimentCloseoutFreezeV1Error(
            "historical v7 review changed before verification"
        )
    return verify_abort_review(V7_ABORT_REVIEW)


def build_adaptive_extension() -> dict[str, Any]:
    base = _read_json(ADAPTIVE_V1)
    primary_tasks = copy.deepcopy(base["primary_model"]["tasks"])
    flash_tasks = copy.deepcopy(base["second_model"]["tasks"])
    if len(primary_tasks) != 40 or len(flash_tasks) != 20:
        raise ExperimentCloseoutFreezeV1Error("adaptive v1 task counts drift")
    review = _read_json(ADAPTIVE_PREFIX / "technical_cost_review_v3_1.json")
    if (
        review.get("technical_gate_passed") is not True
        or review.get("terminal_query_count") != 374
        or review.get("completed_provider_call_count") != 562
    ):
        raise ExperimentCloseoutFreezeV1Error("adaptive formal-prefix review drift")
    checkpoints = sorted(
        (ADAPTIVE_PREFIX / "search_checkpoints").glob("*.json")
    )
    prefix_queries = {
        path.stem: len(_read_json(path).get("queries", [])) for path in checkpoints
    }
    if sorted(prefix_queries.values()) != [24, 50, 50, 50, 50, 50, 50, 50]:
        raise ExperimentCloseoutFreezeV1Error("adaptive prefix query counts drift")

    core = {
        "schema_version": "m3-paper-v2-adaptive-attack-extension-2.0",
        "status": "frozen_offline_pending_provider_admission",
        "frozen_at": FREEZE_TIME,
        "base_freeze": _artifact_lock(ADAPTIVE_V1),
        "maximum_query_budget": 79000,
        "execution_order": [
            "deepseek_pro_budget_50",
            "deepseek_pro_budget_200",
            "deepseek_pro_budget_500",
            "freeze_hardest_20",
            "deepseek_pro_hardest_20_budget_2000",
            "deepseek_flash_budget_50",
            "deepseek_flash_budget_200",
            "gemini_flash_budget_50",
            "gemini_flash_budget_200",
        ],
        "models": {
            "deepseek_pro": {
                "provider_id": "deepseek",
                "model_id": "deepseek-v4-pro",
                "budgets": [50, 200, 500],
                "tasks": primary_tasks,
                "hardest_subset_budget": 2000,
            },
            "deepseek_flash": {
                "provider_id": "deepseek",
                "model_id": "deepseek-v4-flash",
                "budgets": [50, 200],
                "tasks": flash_tasks,
            },
            "gemini_flash": {
                "provider_id": GEMINI_PROVIDER_ID,
                "model_id": GEMINI_MODEL_ID,
                "budgets": [50, 200],
                "tasks": copy.deepcopy(flash_tasks),
                "paired_task_source": "base_freeze.second_model.tasks",
            },
        },
        "hardest_subset": copy.deepcopy(base["hardest_subset"]),
        "formal_prefix": {
            "run_id": review["run_id"],
            "execution_identity": review["execution_identity"],
            "terminal_query_count": 374,
            "completed_provider_call_count": 562,
            "cumulative_cost_cny": review["cumulative_cost_cny"],
            "query_counts_by_case": prefix_queries,
            "terminal_queries_must_not_be_replayed": True,
            "artifact_locks": _adaptive_prefix_locks(),
        },
        "provider_policy": {
            "deepseek_hard_limit_cny": 180,
            "gemini_paid_ceiling_usd": 0,
            "gemini_free_tier_only": True,
            "automatic_retries": 0,
            "deepseek_maximum_task_shards": 4,
            "gemini_initial_concurrency": 1,
            "gemini_maximum_concurrency_after_clean_canary": 2,
            "mutable_state_shared_between_providers": False,
            "provider_managed_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "network_calls_made": 0,
        "scientific_outcomes_read": 0,
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def build_v7_immutable_audit() -> dict[str, Any]:
    review = _verify_v7_review_for_sha(_sha256_file(V7_ABORT_REVIEW))
    if review.get("status") != "aborted_result_ineligible_new_version_required":
        raise ExperimentCloseoutFreezeV1Error("historical v7 status drift")
    summary = review["operational_summary"]
    boundary = review["evidence_boundary"]
    if (
        summary.get("record_count") != 0
        or summary.get("open_attempt_count") != 1
        or summary.get("provider_calls_completed") != 2
        or boundary.get("prior_run_resumable") is not False
    ):
        raise ExperimentCloseoutFreezeV1Error("historical v7 facts drift")
    core = {
        "schema_version": "m3-paper-v2-formal-matrix-v7-immutable-audit-1.0",
        "status": "verified_historical_failure_closed_nonresumable",
        "audited_at": FREEZE_TIME,
        "review_lock": _artifact_lock(V7_ABORT_REVIEW),
        "review_manifest_sha256": review["manifest_sha256"],
        "run_id": review["run_id"],
        "stop_reason": review["stop_reason"],
        "record_count": 0,
        "open_attempt_count": 1,
        "provider_calls_completed": 2,
        "incremental_cost_cny": summary["incremental_cost_cny"],
        "prior_run_resumable": False,
        "rerun_authorized": False,
        "append_only_ledgers_mutated": False,
        "network_calls_made": 0,
        "scientific_outcomes_read": 0,
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def build_blind_interface() -> dict[str, Any]:
    slots_path = BLIND_KIT / "slots.jsonl"
    slots = _read_jsonl(slots_path)
    status = _read_json(BLIND_KIT / "status.json")
    if len(slots) != 600 or len({row["slot_id"] for row in slots}) != 600:
        raise ExperimentCloseoutFreezeV1Error("blind slot identity drift")
    sample_counts = dict(sorted(Counter(str(row["sample_type"]) for row in slots).items()))
    group_counts = dict(
        sorted(Counter(str(row["independent_author_group"]) for row in slots).items())
    )
    expected_samples = {
        "attack": 360,
        "benign_legal_tool": 120,
        "benign_no_tool": 120,
    }
    if sample_counts != expected_samples or group_counts != {"1": 300, "2": 300}:
        raise ExperimentCloseoutFreezeV1Error("blind slot strata drift")
    if status.get("candidate_present") is not False or status.get("custodian") is not None:
        raise ExperimentCloseoutFreezeV1Error("blind kit is no longer pre-custodian")
    core = {
        "schema_version": "m3-paper-v2-independent-blind-closeout-interface-1.0",
        "status": "blocked_external_custodian_and_sealed_candidate_required",
        "frozen_at": FREEZE_TIME,
        "slot_lock": _artifact_lock(slots_path),
        "slot_counts": {
            "records": 600,
            "sample_types": sample_counts,
            "closeout_strata": {
                "attack": sample_counts["attack"],
                "benign_tool": sample_counts["benign_legal_tool"],
                "benign_no_tool": sample_counts["benign_no_tool"],
            },
            "independent_author_groups": group_counts,
        },
        "required_custodian_inputs": {
            "execution_set": {
                "rows": 600,
                "forbidden_fields": [
                    "gold",
                    "evaluator",
                    "offline_evaluation",
                    "unsafe_effect",
                    "task_completion",
                ],
            },
            "independent_label_file": {
                "developer_access_before_unseal": False,
                "custodian_only_before_scoring": True,
            },
            "custody_manifest": {
                "required_fields": [
                    "custodian_id",
                    "candidate_sha256",
                    "candidate_row_count",
                    "sealed_at",
                    "custodian_signature",
                ]
            },
        },
        "execution_contract": {
            "primary_model": "deepseek-v4-pro",
            "conditions": [
                "no_defense",
                "safe_prompt_or_spotlighting",
                "promptguard_detector_only",
                "strongest_peer_reviewed_structural_baseline",
                "m3_policy_only",
                "m3_full",
            ],
            "expected_records": 3600,
            "hard_limit_cny": 15,
            "developer_case_labels_visible_before_execution": False,
            "provider_managed_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "claim_policy": {
            "independent_blind_claim_allowed_now": False,
            "internal_sealed_holdout_may_not_be_renamed_independent": True,
        },
        "network_calls_made": 0,
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def build_closeout_candidate() -> dict[str, Any]:
    gemini = build_gemini_public_manifest()
    adaptive = build_adaptive_extension()
    v7_audit = build_v7_immutable_audit()
    blind = build_blind_interface()
    core = {
        "schema_version": "m3-paper-v2-experiment-closeout-candidate-1.0",
        "status": "offline_freeze_complete_execution_not_authorized_by_artifact",
        "frozen_at": FREEZE_TIME,
        "scope": {
            "paper_writing_included": False,
            "historical_frozen_inputs_mutable": False,
            "automatic_retries": 0,
            "real_external_effects": False,
            "negative_scientific_results_acceptable": True,
            "full_harness_exit_zero_required": True,
        },
        "components": {
            "gemini_public": gemini["manifest_sha256"],
            "adaptive_v2": adaptive["manifest_sha256"],
            "v7_immutable_audit": v7_audit["manifest_sha256"],
            "independent_blind": blind["manifest_sha256"],
        },
        "external_blockers": [
            "independent custodian identity",
            "sealed 600-row execution set",
            "custodian-held label file and signed custody manifest",
        ],
        "network_calls_made": 0,
        "provider_execution_authorized_by_this_artifact": False,
        "scientific_outcomes_read": 0,
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def write_bundle() -> dict[str, Any]:
    rows = build_gemini_public_plan()
    GEMINI_PUBLIC_PLAN.write_bytes(_jsonl_bytes(rows))
    values = {
        "gemini_public_manifest": build_gemini_public_manifest(),
        "adaptive_v2": build_adaptive_extension(),
        "v7_immutable_audit": build_v7_immutable_audit(),
        "blind_interface": build_blind_interface(),
        "closeout_candidate": build_closeout_candidate(),
    }
    for path, key in (
        (GEMINI_PUBLIC_MANIFEST, "gemini_public_manifest"),
        (ADAPTIVE_V2, "adaptive_v2"),
        (V7_IMMUTABLE_AUDIT, "v7_immutable_audit"),
        (BLIND_INTERFACE, "blind_interface"),
        (CLOSEOUT_CANDIDATE, "closeout_candidate"),
    ):
        _write_json(path, values[key])
    return values


def verify_bundle() -> dict[str, Any]:
    expected_rows = build_gemini_public_plan()
    if _read_jsonl(GEMINI_PUBLIC_PLAN) != expected_rows:
        raise ExperimentCloseoutFreezeV1Error("Gemini public plan drift")
    expected = {
        GEMINI_PUBLIC_MANIFEST: build_gemini_public_manifest(),
        ADAPTIVE_V2: build_adaptive_extension(),
        V7_IMMUTABLE_AUDIT: build_v7_immutable_audit(),
        BLIND_INTERFACE: build_blind_interface(),
        CLOSEOUT_CANDIDATE: build_closeout_candidate(),
    }
    for path, value in expected.items():
        if _read_json(path) != value:
            raise ExperimentCloseoutFreezeV1Error(f"{path}: frozen artifact drift")
    return {
        "status": "experiment_closeout_freeze_verified",
        "gemini_public_records": len(expected_rows),
        "network_calls_made": 0,
        "artifacts": [_artifact_lock(path) for path in expected],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = write_bundle() if args.write else verify_bundle()
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
