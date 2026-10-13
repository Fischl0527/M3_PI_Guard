"""面向 600 例盲测用例的托管人门禁导入与执行计划契约。

支持第三方托管人环境下的盲测数据集导入，前置检验防泄露标记与元数据完整性。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from experiments.paper_v2.contracts import canonical_json_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KIT_ROOT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1"
)
DEFAULT_SLOTS = KIT_ROOT / "slots.jsonl"
CONDITIONS = (
    "no_defense",
    "safe_prompt_or_spotlighting",
    "promptguard_detector_only",
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_full",
)
FORBIDDEN_EXECUTION_FIELDS = frozenset(
    {
        "answer_key",
        "evaluator",
        "evaluator_label",
        "expected_allowed_effects",
        "expected_outcome",
        "expected_safe_behavior",
        "expected_unsafe_effects",
        "gold",
        "gold_action",
        "gold_answer",
        "gold_label",
        "offline_evaluation",
        "task_completion",
        "unsafe_effect",
        "unsafe_target_actions",
    }
)
SLOT_BOUND_FIELDS = (
    "slot_id",
    "sample_type",
    "scenario_type",
    "attack_family",
    "language",
    "primary_authorization_regime",
)


class IndependentBlindCloseoutV1Error(ValueError):
    """当托管或标签隔离不变量失败时抛出的异常。"""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IndependentBlindCloseoutV1Error(f"{path}: expected object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            raise IndependentBlindCloseoutV1Error(
                f"{path}:{line_number}: blank JSONL row"
            )
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise IndependentBlindCloseoutV1Error(
                f"{path}:{line_number}: expected object"
            )
        rows.append(value)
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    core = {key: item for key, item in value.items() if key != "manifest_sha256"}
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def _field_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(child_path)
            paths.extend(_field_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_field_paths(child, f"{prefix}[{index}]"))
    return paths


def _forbidden_paths(row: Mapping[str, Any]) -> list[str]:
    return sorted(
        path
        for path in _field_paths(row)
        if path.rsplit(".", maxsplit=1)[-1].split("[", maxsplit=1)[0].lower()
        in FORBIDDEN_EXECUTION_FIELDS
    )


def _non_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and not (text.startswith("<") and text.endswith(">"))


def _is_iso8601(value: Any) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None


def _slot_map(path: Path = DEFAULT_SLOTS) -> dict[str, dict[str, Any]]:
    rows = _read_jsonl(path)
    result = {str(row["slot_id"]): row for row in rows}
    if len(rows) != 600 or len(result) != 600:
        raise IndependentBlindCloseoutV1Error("expected 600 unique blind slots")
    return result


def audit_sealed_execution_set(
    *,
    execution_set_path: Path,
    custody_manifest_path: Path,
    slots_path: Path = DEFAULT_SLOTS,
) -> dict[str, Any]:
    """在不打开标签文件的情况下验证托管和标签隔离。"""

    execution_set_path = execution_set_path.resolve()
    custody_manifest_path = custody_manifest_path.resolve()
    if not execution_set_path.is_file() or not custody_manifest_path.is_file():
        raise IndependentBlindCloseoutV1Error(
            "execution set and custody manifest are both required"
        )
    rows = _read_jsonl(execution_set_path)
    slots = _slot_map(slots_path)
    custody = _read_json(custody_manifest_path)
    candidate_sha = _sha256_file(execution_set_path)
    row_ids = [str(row.get("slot_id", "")) for row in rows]
    case_ids = [str(row.get("case_id", "")) for row in rows]
    forbidden = {
        str(row.get("slot_id", "")): _forbidden_paths(row)
        for row in rows
        if _forbidden_paths(row)
    }
    mismatched_slots: list[str] = []
    for row in rows:
        slot_id = str(row.get("slot_id", ""))
        slot = slots.get(slot_id)
        if slot is None or any(row.get(field) != slot.get(field) for field in SLOT_BOUND_FIELDS):
            mismatched_slots.append(slot_id)
    content_complete = all(
        _non_placeholder(row.get("case_id"))
        and _non_placeholder(row.get("trusted_user_request"))
        and isinstance(row.get("trusted_app_context"), Mapping)
        and isinstance(row.get("untrusted_memory"), list)
        for row in rows
    )
    custody_checks = {
        "candidate_sha256_matches": custody.get("candidate_sha256") == candidate_sha,
        "candidate_row_count_matches": custody.get("candidate_row_count") == 600,
        "candidate_filename_matches": custody.get("candidate_filename")
        == execution_set_path.name,
        "custodian_identified": _non_placeholder(custody.get("custodian_id")),
        "custodian_signature_present": _non_placeholder(
            custody.get("custodian_signature")
        ),
        "sealed_at_is_timezone_aware": _is_iso8601(custody.get("sealed_at")),
        "developer_had_no_preseal_access": custody.get(
            "developer_access_before_seal"
        )
        is False,
        "label_file_hash_committed": isinstance(
            custody.get("label_file_sha256"), str
        )
        and len(str(custody.get("label_file_sha256"))) == 64,
        "label_file_not_supplied_to_audit": True,
    }
    data_checks = {
        "exactly_600_rows": len(rows) == 600,
        "slot_ids_unique_and_complete": len(set(row_ids)) == 600
        and set(row_ids) == set(slots),
        "case_ids_unique_and_nonempty": len(set(case_ids)) == 600
        and all(case_ids),
        "slot_metadata_matches_frozen_kit": not mismatched_slots,
        "execution_content_complete": content_complete,
        "forbidden_label_fields_absent": not forbidden,
        "split_is_independent_blind": all(
            row.get("split") == "independent_blind" for row in rows
        ),
    }
    passed = all(custody_checks.values()) and all(data_checks.values())
    core = {
        "schema_version": "m3-paper-v2-independent-blind-execution-admission-1.0",
        "status": (
            "sealed_execution_set_technically_admitted_labels_unopened"
            if passed
            else "sealed_execution_set_rejected"
        ),
        "execution_set": {
            "filename": execution_set_path.name,
            "rows": len(rows),
            "sha256": candidate_sha,
            "slot_id_sequence_sha256": hashlib.sha256(
                canonical_json_bytes(row_ids)
            ).hexdigest(),
            "case_id_sequence_sha256": hashlib.sha256(
                canonical_json_bytes(case_ids)
            ).hexdigest(),
        },
        "custody_manifest": {
            "sha256": _sha256_file(custody_manifest_path),
            "custodian_id": custody.get("custodian_id"),
            "sealed_at": custody.get("sealed_at"),
            "label_file_sha256": custody.get("label_file_sha256"),
        },
        "custody_checks": custody_checks,
        "data_checks": data_checks,
        "diagnostics": {
            "mismatched_slot_ids": sorted(mismatched_slots),
            "forbidden_fields_by_slot": forbidden,
        },
        "evidence_boundary": {
            "label_file_opened": False,
            "scientific_outcomes_read": 0,
            "network_calls_made": 0,
            "execution_authorized": passed,
            "result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def build_six_condition_plan(
    *,
    execution_set_path: Path,
    admission: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if admission.get("status") != (
        "sealed_execution_set_technically_admitted_labels_unopened"
    ):
        raise IndependentBlindCloseoutV1Error(
            "a passing label-closed admission is required"
        )
    if admission["execution_set"]["sha256"] != _sha256_file(execution_set_path):
        raise IndependentBlindCloseoutV1Error("execution set drift after admission")
    rows = _read_jsonl(execution_set_path)
    identity = hashlib.sha256(
        canonical_json_bytes(
            {
                "schema_version": "m3-paper-v2-independent-blind-plan-1.0",
                "candidate_sha256": admission["execution_set"]["sha256"],
                "admission_manifest_sha256": admission["manifest_sha256"],
                "provider_id": "deepseek",
                "model_id": "deepseek-v4-pro",
                "conditions": list(CONDITIONS),
            }
        )
    ).hexdigest()
    plan: list[dict[str, Any]] = []
    sequence = 0
    for row_number, row in enumerate(rows, start=1):
        row_sha = hashlib.sha256(canonical_json_bytes(row)).hexdigest()
        for condition in CONDITIONS:
            sequence += 1
            work_key = hashlib.sha256(
                canonical_json_bytes(
                    {
                        "execution_identity": identity,
                        "slot_id": row["slot_id"],
                        "condition_id": condition,
                    }
                )
            ).hexdigest()
            plan.append(
                {
                    "schema_version": "m3-paper-v2-independent-blind-work-item-1.0",
                    "sequence": sequence,
                    "work_key": work_key,
                    "execution_identity": identity,
                    "provider_id": "deepseek",
                    "model_id": "deepseek-v4-pro",
                    "model_role": "primary",
                    "condition_id": condition,
                    "slot_id": row["slot_id"],
                    "case_id": row["case_id"],
                    "authorization_regime": row[
                        "primary_authorization_regime"
                    ],
                    "source_reference": {
                        "path": execution_set_path.name,
                        "line": row_number,
                        "sha256": row_sha,
                    },
                    "admission_manifest_sha256": admission[
                        "manifest_sha256"
                    ],
                    "status": "pending",
                    "result_fields_present": False,
                    "provider_managed_tools_enabled": False,
                    "external_effects_enabled": False,
                }
            )
    if len(plan) != 3600 or len({row["work_key"] for row in plan}) != 3600:
        raise IndependentBlindCloseoutV1Error("blind six-condition plan drift")
    return plan


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"".join(canonical_json_bytes(row) + b"\n" for row in rows)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-set", type=Path, required=True)
    parser.add_argument("--custody-manifest", type=Path, required=True)
    parser.add_argument("--write-admission", type=Path)
    parser.add_argument("--write-plan", type=Path)
    args = parser.parse_args()
    admission = audit_sealed_execution_set(
        execution_set_path=args.execution_set,
        custody_manifest_path=args.custody_manifest,
    )
    if args.write_admission:
        _write_json(args.write_admission, admission)
    if args.write_plan:
        _write_jsonl(
            args.write_plan,
            build_six_condition_plan(
                execution_set_path=args.execution_set,
                admission=admission,
            ),
        )
    print(json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if admission["status"].endswith("labels_unopened") else 2


if __name__ == "__main__":
    raise SystemExit(main())
