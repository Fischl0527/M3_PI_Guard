"""构建对结果盲审的 paper-v2 公开基准执行方案。

在不提前窥探实验数据的前提下排布完整的交叉对照实验矩阵。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.medium_runtime import (
    DEFAULT_PROVIDER_SAFETY_POLICY,
    _read_source_record,
    _source_projection,
    build_initial_online_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FREEZE = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/public_benchmark_freeze_v1.json"
)
DEFAULT_CALL_BUDGET_SOURCE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/provider_cost_decision_candidate_v1.json"
)
DEFAULT_PLAN = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/public_execution_plan_v1.jsonl"
)
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/public_execution_manifest_v1.json"
)
FROZEN_AT = "2026-07-28T00:10:00+08:00"
EXPECTED_RECORDS = 6873
EXPECTED_MODEL_RECORDS = {"primary": 5082, "second": 1791}
CELL_ORDER = (
    "primary_model_agentdojo_v1",
    "primary_model_m3_v2",
    "second_model_agentdojo_v1",
    "second_model_m3_v2",
)
MODEL_ROLES = {
    "primary": {
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-pro",
        "endpoint_type": "official_api",
        "base_url": "https://api.deepseek.com",
        "claim_boundary": "primary_model",
    },
    "second": {
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-flash",
        "endpoint_type": "official_api",
        "base_url": "https://api.deepseek.com",
        "claim_boundary": "cross_model_not_cross_provider",
    },
}


class PublicMatrixPlanError(ValueError):
    """当公开固化无法生成确切安全计划时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicMatrixPlanError(f"{path}: expected a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            raise PublicMatrixPlanError(f"{path}:{line_number}: blank JSONL row")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise PublicMatrixPlanError(
                f"{path}:{line_number}: expected a JSON object"
            )
        rows.append(value)
    return rows


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(dict(row)) + b"\n" for row in rows)


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _case_for_runtime(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "benchmark": str(case["benchmark"]),
        "case_id": str(case["case_id"]),
        "source_path": str(case["source"]),
        "source_line": int(case["source_line"]),
        "source_record_sha256": str(case["source_record_sha256"]),
    }


def _evaluation_metadata(
    *,
    benchmark: str,
    record: Mapping[str, Any],
) -> tuple[str, bool]:
    if benchmark == "m3-v2":
        sample_type = str(record.get("sample_type"))
        mapping = {
            "attack": "attack",
            "benign_legal_tool": "benign_tool",
            "benign_no_tool": "benign_no_tool",
        }
        if sample_type not in mapping:
            raise PublicMatrixPlanError(
                f"unsupported M3 public sample type: {sample_type}"
            )
        scenario = str(record.get("scenario_type"))
        context_dependent = (
            scenario
            in {
                "environment_context_pollution",
                "memory_poisoning",
                "cross_tool_attack_chain",
                "multi_step",
            }
        )
        return mapping[sample_type], context_dependent
    if benchmark == "agentdojo-v1":
        record_kind = str(record.get("record_kind"))
        mapping = {"security": "attack", "utility": "benign_tool"}
        if record_kind not in mapping:
            raise PublicMatrixPlanError(
                f"unsupported AgentDojo public record kind: {record_kind}"
            )
        return mapping[record_kind], True
    raise PublicMatrixPlanError(f"unsupported public benchmark: {benchmark}")


def _role_for_cell(cell_name: str) -> str:
    if cell_name.startswith("primary_model_"):
        return "primary"
    if cell_name.startswith("second_model_"):
        return "second"
    raise PublicMatrixPlanError(f"unsupported public cell: {cell_name}")


def _identity_inputs(
    freeze: Mapping[str, Any],
    *,
    freeze_path: Path,
) -> dict[str, dict[str, Any]]:
    paths = {
        _display_path(freeze_path): freeze_path,
        _display_path(DEFAULT_CALL_BUDGET_SOURCE): DEFAULT_CALL_BUDGET_SOURCE,
        _display_path(DEFAULT_PROVIDER_SAFETY_POLICY): (
            DEFAULT_PROVIDER_SAFETY_POLICY
        ),
        _display_path(Path(__file__)): Path(__file__),
        "experiments/paper_v2/medium_runtime.py": (
            PROJECT_ROOT / "experiments/paper_v2/medium_runtime.py"
        ),
        "experiments/paper_v2/formal_condition_executors.py": (
            PROJECT_ROOT
            / "experiments/paper_v2/formal_condition_executors.py"
        ),
        "experiments/paper_v2/live_condition_runtime.py": (
            PROJECT_ROOT / "experiments/paper_v2/live_condition_runtime.py"
        ),
        "schemas/paper_v2/experiment_record_v2.schema.json": (
            PROJECT_ROOT / "schemas/paper_v2/experiment_record_v2.schema.json"
        ),
    }
    source_locks = freeze.get("source_locks")
    if not isinstance(source_locks, Mapping):
        raise PublicMatrixPlanError("public source locks must be a mapping")
    for source_name, source in source_locks.items():
        if not isinstance(source, Mapping):
            raise PublicMatrixPlanError(
                f"public source lock must be an object: {source_name}"
            )
        source_path = PROJECT_ROOT / str(source["path"])
        paths[_display_path(source_path)] = source_path
    result: dict[str, dict[str, Any]] = {}
    for name, path in sorted(paths.items()):
        if not path.is_file():
            raise PublicMatrixPlanError(f"missing public-plan input: {name}")
        result[name] = {
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
    return result


def _execution_identity(
    *,
    role: str,
    locked_inputs: Mapping[str, Any],
    conditions: Iterable[str],
) -> str:
    return sha256_canonical_json(
        {
            "schema_version": "m3-paper-v2-public-execution-identity-1.0",
            "model_role": role,
            "provider": MODEL_ROLES[role],
            "conditions": list(conditions),
            "authorization_regime": "auto_compiled",
            "locked_inputs": locked_inputs,
        }
    )


def _work_key(
    *,
    role: str,
    benchmark: str,
    case_id: str,
    condition_id: str,
) -> str:
    return sha256_canonical_json(
        {
            "model_role": role,
            "benchmark": benchmark,
            "case_id": case_id,
            "condition_id": condition_id,
            "authorization_regime": "auto_compiled",
        }
    )


def _validate_freeze(freeze: Mapping[str, Any]) -> None:
    if (
        freeze.get("schema_version")
        != "m3-paper-v2-public-benchmark-freeze-1.0"
        or freeze.get("status") != "cases_frozen_results_pending"
        or freeze.get("expected_case_condition_records") != EXPECTED_RECORDS
    ):
        raise PublicMatrixPlanError("public benchmark freeze identity drift")
    cells = freeze.get("cells")
    if not isinstance(cells, Mapping) or tuple(cells) != CELL_ORDER:
        raise PublicMatrixPlanError("public benchmark cell order drift")
    observed = sum(
        len(cell["cases"]) * len(cell["conditions"])
        for cell in cells.values()
    )
    if observed != EXPECTED_RECORDS:
        raise PublicMatrixPlanError(
            f"expected {EXPECTED_RECORDS} public records, got {observed}"
        )
    source_locks = freeze.get("source_locks")
    if not isinstance(source_locks, Mapping):
        raise PublicMatrixPlanError("public source locks must be a mapping")
    for source_name, source in source_locks.items():
        if not isinstance(source, Mapping):
            raise PublicMatrixPlanError(
                f"public source lock must be an object: {source_name}"
            )
        path = PROJECT_ROOT / str(source["path"])
        if (
            not path.is_file()
            or path.stat().st_size != int(source["bytes"])
            or _sha256_file(path) != str(source["sha256"])
        ):
            raise PublicMatrixPlanError(
                f"public source lock drift: {source['path']}"
            )


def _canary_items(rows: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    selected_cases: set[tuple[str, str]] = set()
    for benchmark in ("agentdojo-v1", "m3-v2"):
        for category in ("attack", "benign"):
            match = next(
                (
                    row
                    for row in rows
                    if row["model_role"] == role
                    and row["benchmark"] == benchmark
                    and (
                        row["evaluation_case_type"] == "attack"
                        if category == "attack"
                        else row["evaluation_case_type"] != "attack"
                    )
                ),
                None,
            )
            if match is None:
                raise PublicMatrixPlanError(
                    f"missing {role}/{benchmark}/{category} canary"
                )
            selected_cases.add((benchmark, str(match["case_id"])))
    result = [
        row
        for row in rows
        if row["model_role"] == role
        and (str(row["benchmark"]), str(row["case_id"])) in selected_cases
    ]
    expected = 24 if role == "primary" else 12
    if len(result) != expected:
        raise PublicMatrixPlanError(
            f"{role} canary must contain {expected} records, got {len(result)}"
        )
    return result


def build_public_execution_plan(
    *,
    freeze_path: Path = DEFAULT_FREEZE,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """将固化的公开用例展开为确切的条件工作项。"""

    freeze = _load_json(freeze_path)
    _validate_freeze(freeze)
    call_policy = _load_json(DEFAULT_CALL_BUDGET_SOURCE)
    call_budgets = call_policy["request_parameters"][
        "max_calls_per_condition"
    ]
    locked_inputs = _identity_inputs(freeze, freeze_path=freeze_path)
    role_conditions = {
        "primary": tuple(
            freeze["cells"]["primary_model_agentdojo_v1"]["conditions"]
        ),
        "second": tuple(
            freeze["cells"]["second_model_agentdojo_v1"]["conditions"]
        ),
    }
    identities = {
        role: _execution_identity(
            role=role,
            locked_inputs=locked_inputs,
            conditions=conditions,
        )
        for role, conditions in role_conditions.items()
    }

    rows: list[dict[str, Any]] = []
    source_cache: dict[tuple[str, int, str], dict[str, Any]] = {}
    source_projection_cache: dict[
        tuple[str, int, str], dict[str, Any]
    ] = {}
    for cell_name in CELL_ORDER:
        cell = freeze["cells"][cell_name]
        role = _role_for_cell(cell_name)
        conditions = tuple(str(item) for item in cell["conditions"])
        if conditions != role_conditions[role]:
            raise PublicMatrixPlanError(
                f"{cell_name}: condition panel drift within model role"
            )
        for frozen_case in cell["cases"]:
            case = _case_for_runtime(frozen_case)
            cache_key = (
                str(case["source_path"]),
                int(case["source_line"]),
                str(case["source_record_sha256"]),
            )
            if cache_key not in source_cache:
                source_cache[cache_key] = _read_source_record(case)
                source_projection_cache[cache_key] = _source_projection(
                    source_cache[cache_key],
                    str(case["benchmark"]),
                )
            record = source_cache[cache_key]
            projection = source_projection_cache[cache_key]
            source_digest = compute_online_visible_field_digest(projection)
            if source_digest["forbidden_fields_present"]:
                raise PublicMatrixPlanError(
                    f"{case['case_id']}: source projection leaks evaluator fields"
                )
            evaluation_case_type, context_dependent = _evaluation_metadata(
                benchmark=str(case["benchmark"]),
                record=record,
            )
            if (
                frozen_case["record_kind"] == "attack"
                and evaluation_case_type != "attack"
            ) or (
                frozen_case["record_kind"] == "benign"
                and evaluation_case_type == "attack"
            ):
                raise PublicMatrixPlanError(
                    f"{case['case_id']}: frozen record kind drift"
                )

            selection_id = (
                f"public-v1:{role}:{case['benchmark']}:{case['case_id']}"
            )
            for condition in conditions:
                work_item: dict[str, Any] = {
                    "schema_version": "m3-paper-v2-public-work-item-1.0",
                    "sequence": len(rows) + 1,
                    "work_key": _work_key(
                        role=role,
                        benchmark=str(case["benchmark"]),
                        case_id=str(case["case_id"]),
                        condition_id=condition,
                    ),
                    "execution_identity": identities[role],
                    "selection_id": selection_id,
                    "case_id": str(case["case_id"]),
                    "benchmark": str(case["benchmark"]),
                    "evaluation_case_type": evaluation_case_type,
                    "context_dependent": context_dependent,
                    "source_record_sha256": str(
                        case["source_record_sha256"]
                    ),
                    "source_reference": {
                        "path": str(case["source_path"]),
                        "line": int(case["source_line"]),
                        "sha256": str(case["source_record_sha256"]),
                    },
                    "source_projection_digest_sha256": (
                        sha256_canonical_json(source_digest)
                    ),
                    "source_projection_forbidden_fields_present": False,
                    "condition_id": condition,
                    "authorization_regime": "auto_compiled",
                    "analysis_tier": (
                        "primary" if role == "primary" else "second_model"
                    ),
                    "model_role": role,
                    "provider_id": MODEL_ROLES[role]["provider_id"],
                    "model_id": MODEL_ROLES[role]["model_id"],
                    "primary_endpoint_eligible": role == "primary",
                    "max_provider_calls": int(call_budgets[condition]),
                    "status": "pending",
                    "result_fields_present": False,
                    "record_kind": str(frozen_case["record_kind"]),
                    "selection_stratum": dict(frozen_case["stratum"]),
                }
                initial_state = build_initial_online_state(
                    work_item,
                    case,
                    record,
                )
                initial_digest = compute_online_visible_field_digest(
                    initial_state
                )
                if initial_digest["forbidden_fields_present"]:
                    raise PublicMatrixPlanError(
                        f"{case['case_id']}/{condition}: evaluator leakage"
                    )
                work_item["initial_online_visible_field_digest_sha256"] = (
                    sha256_canonical_json(initial_digest)
                )
                work_item[
                    "initial_online_forbidden_fields_present"
                ] = False
                rows.append(work_item)

    if len(rows) != EXPECTED_RECORDS:
        raise PublicMatrixPlanError(
            f"expected {EXPECTED_RECORDS} work items, got {len(rows)}"
        )
    if [row["sequence"] for row in rows] != list(
        range(1, EXPECTED_RECORDS + 1)
    ):
        raise PublicMatrixPlanError("public plan sequence drift")
    keys = [str(row["work_key"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise PublicMatrixPlanError("public plan work keys are not unique")
    role_counts = Counter(str(row["model_role"]) for row in rows)
    if dict(role_counts) != EXPECTED_MODEL_RECORDS:
        raise PublicMatrixPlanError(
            f"public role counts drift: {dict(role_counts)}"
        )

    primary_canary = _canary_items(rows, "primary")
    second_canary = _canary_items(rows, "second")
    plan_bytes = _jsonl_bytes(rows)
    manifest = {
        "schema_version": "m3-paper-v2-public-execution-manifest-1.0",
        "status": "result_blind_plan_frozen_execution_not_authorized",
        "generated_at": FROZEN_AT,
        "execution_authorized": False,
        "result_admission_authorized": False,
        "credentials_read": False,
        "network_calls_made": 0,
        "formal_results_created": 0,
        "freeze": {
            "path": _display_path(freeze_path),
            "sha256": _sha256_file(freeze_path),
            "schema_version": freeze["schema_version"],
        },
        "plan": {
            "path": _display_path(DEFAULT_PLAN),
            "records": len(rows),
            "bytes": len(plan_bytes),
            "sha256": hashlib.sha256(plan_bytes).hexdigest(),
            "provider_calls_upper_bound": sum(
                int(row["max_provider_calls"]) for row in rows
            ),
        },
        "model_roles": {
            role: {
                **MODEL_ROLES[role],
                "execution_identity": identities[role],
                "records": role_counts[role],
                "conditions": list(role_conditions[role]),
            }
            for role in ("primary", "second")
        },
        "canary": {
            "selection_method": (
                "first_frozen_attack_and_benign_case_per_benchmark"
            ),
            "scientific_outcomes_accessed": False,
            "primary_records": len(primary_canary),
            "second_records": len(second_canary),
            "primary_work_key_sequence_sha256": sha256_canonical_json(
                [row["work_key"] for row in primary_canary]
            ),
            "second_work_key_sequence_sha256": sha256_canonical_json(
                [row["work_key"] for row in second_canary]
            ),
        },
        "counts": {
            "by_model_role": dict(sorted(role_counts.items())),
            "by_benchmark": dict(
                sorted(Counter(row["benchmark"] for row in rows).items())
            ),
            "by_evaluation_case_type": dict(
                sorted(
                    Counter(
                        row["evaluation_case_type"] for row in rows
                    ).items()
                )
            ),
            "by_condition": dict(
                sorted(Counter(row["condition_id"] for row in rows).items())
            ),
        },
        "locked_inputs": locked_inputs,
        "online_state_contract": {
            "authorization_regime": "auto_compiled",
            "forbidden_evaluator_fields_present": False,
            "source_projection_digest_bound": (
                "canonical_digest_sha256_reconstructed_from_locked_source"
            ),
            "initial_condition_state_digest_bound": (
                "canonical_digest_sha256_reconstructed_before_dispatch"
            ),
            "model_role_not_visible_to_evaluator": True,
        },
        "evidence_boundary": {
            "plans_are_scientific_results": False,
            "canary_is_technical_until_separate_result_admission": True,
            "failures_remain_in_intention_to_treat": True,
            "deepseek_flash_claim_boundary": (
                "cross_model_not_cross_provider"
            ),
        },
    }
    return rows, manifest


def reconstruct_public_initial_online_state(
    work_item: Mapping[str, Any],
) -> dict[str, Any]:
    """重建并验证确切的公开工作项在线状态。"""

    source = work_item.get("source_reference")
    if not isinstance(source, Mapping):
        raise PublicMatrixPlanError("public work item lacks source reference")
    case = {
        "benchmark": str(work_item["benchmark"]),
        "case_id": str(work_item["case_id"]),
        "source_path": str(source["path"]),
        "source_line": int(source["line"]),
        "source_record_sha256": str(source["sha256"]),
    }
    record = _read_source_record(case)
    projection = _source_projection(record, str(case["benchmark"]))
    observed_projection_digest = compute_online_visible_field_digest(
        projection
    )
    if (
        sha256_canonical_json(observed_projection_digest)
        != work_item["source_projection_digest_sha256"]
        or observed_projection_digest["forbidden_fields_present"]
        != work_item["source_projection_forbidden_fields_present"]
    ):
        raise PublicMatrixPlanError("public source projection digest drift")
    state = build_initial_online_state(work_item, case, record)
    observed_initial_digest = compute_online_visible_field_digest(state)
    if (
        sha256_canonical_json(observed_initial_digest)
        != work_item["initial_online_visible_field_digest_sha256"]
        or observed_initial_digest["forbidden_fields_present"]
        != work_item["initial_online_forbidden_fields_present"]
    ):
        raise PublicMatrixPlanError("public initial online state digest drift")
    return state


def hydrate_public_work_item(
    work_item: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """返回分发器兼容的工作项及其经验证的在线状态。"""

    state = reconstruct_public_initial_online_state(work_item)
    hydrated = dict(work_item)
    hydrated["initial_online_visible_field_digest"] = (
        compute_online_visible_field_digest(state)
    )
    return hydrated, state


def verify_public_execution_plan(
    *,
    freeze_path: Path = DEFAULT_FREEZE,
    plan_path: Path = DEFAULT_PLAN,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    expected_rows, expected_manifest = build_public_execution_plan(
        freeze_path=freeze_path
    )
    if plan_path.read_bytes() != _jsonl_bytes(expected_rows):
        raise PublicMatrixPlanError("public execution plan does not reproduce")
    if _load_json(manifest_path) != expected_manifest:
        raise PublicMatrixPlanError(
            "public execution manifest does not reproduce"
        )
    return expected_manifest


def write_public_execution_plan(
    *,
    freeze_path: Path = DEFAULT_FREEZE,
    plan_path: Path = DEFAULT_PLAN,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    rows, manifest = build_public_execution_plan(freeze_path=freeze_path)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(_jsonl_bytes(rows))
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write == args.verify:
        parser.error("choose exactly one of --write or --verify")
    manifest = (
        write_public_execution_plan()
        if args.write
        else verify_public_execution_plan()
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
