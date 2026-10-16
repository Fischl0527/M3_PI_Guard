"""单次读取历史 Public 事件证据（严禁重新打分或重播旧记录）。

规范化提取历史运行日志中的执行收据并转换为 V2 兼容结构。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from experiments.paper_v2.lean_existing_results import FLASH_FILES, PRIMARY_FILES

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs/experiments/correctness_repair_v1/followup_v1/legacy_endpoint_recovery.json"
BOUNDARY = "isolated_effect_boundary_rejection_v3"


def classify_saved_events(entry: Mapping[str, Any]) -> dict[str, Any]:
    """描述论据，而不重建缺失的状态或标准答案标签。"""
    record = entry.get("record")
    if not isinstance(record, Mapping):
        raise ValueError("record must be an object")
    events = entry.get("runtime_visibility_events")
    usable = isinstance(events, list) and bool(events)
    boundary_count = 0
    success_count = 0
    if usable:
        for event in events:
            if not isinstance(event, Mapping):
                usable = False
                break
            proposal = event.get("action_proposal")
            decision = event.get("guard_decision")
            if (
                not isinstance(proposal, Mapping)
                or not isinstance(proposal.get("tool"), str)
                or not isinstance(decision, Mapping)
                or not isinstance(event.get("execution_attempted"), bool)
                or not isinstance(event.get("execution_succeeded"), bool)
            ):
                usable = False
                break
            attempted = event["execution_attempted"]
            succeeded = event["execution_succeeded"]
            if succeeded and not attempted:
                usable = False
                break
            is_boundary = decision.get("reason_code") == BOUNDARY
            if is_boundary and (
                decision.get("decision") != "ALLOW" or not attempted or succeeded
            ):
                usable = False
                break
            boundary_count += int(is_boundary)
            success_count += int(succeeded and proposal["tool"] != "final")

    if not usable:
        category = "insufficient_event_evidence"
    elif success_count:
        category = "successful_nonfinal_action_authorization_unknown"
    elif boundary_count and record.get("operational_status") == "completed":
        category = "boundary_rejected_no_successful_nonfinal_action"
    else:
        category = "insufficient_event_evidence"
    return {
        "category": category,
        "usable_saved_event_shape": usable,
        "boundary_rejection_events": boundary_count if usable else None,
        "successful_nonfinal_action_events": success_count if usable else None,
        "corrected_unauthorized_effect": None,
    }


def summarize_public_files(
    sources: Iterable[tuple[str, Path]], *, root: Path
) -> dict[str, Any]:
    """对每个提供的原始数据流式读取一次；拒绝重复项而非选择胜出者。"""
    groups: dict[tuple[str, str, str, str, str], Counter] = defaultdict(Counter)
    seen: set[tuple[str, str]] = set()
    files = []
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for model_slot, path in sources:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        lines = 0
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                entry = json.loads(line)
                if not isinstance(entry, dict) or not isinstance(entry.get("record"), dict):
                    raise ValueError(f"{relative}:{number}: missing record")
                key = entry.get("work_key")
                if not isinstance(key, str) or not key or (model_slot, key) in seen:
                    raise ValueError(f"{relative}:{number}: missing or duplicate work key")
                seen.add((model_slot, key))
                row = entry["record"]
                for field in ("unsafe_effect", "unsafe_effect_itt"):
                    if row.get(field) is not None and not isinstance(row[field], bool):
                        raise ValueError(f"{relative}:{number}: non-boolean {field}")
                group = groups[(
                    model_slot,
                    str(row.get("benchmark_id", "unknown")),
                    str(row.get("condition_id", "unknown")),
                    str(row.get("authorization_regime", "unknown")),
                    str(row.get("evaluation_case_type", "unknown")),
                )]
                facts = classify_saved_events(entry)
                group["records"] += 1
                group["included_in_itt"] += row.get("included_in_intention_to_treat") is True
                group["operational_failure"] += row.get("operational_status") != "completed"
                group["legacy_unsafe_positive"] += row.get("unsafe_effect") is True
                group["legacy_unsafe_unknown"] += row.get("unsafe_effect") is None
                group["legacy_itt_positive"] += row.get("unsafe_effect_itt") is True
                group["legacy_itt_positive_without_direct_positive"] += (
                    row.get("unsafe_effect_itt") is True and row.get("unsafe_effect") is not True
                )
                if row.get("unsafe_effect") is True:
                    category = facts["category"]
                    group[f"positive_{category}"] += 1
                    if len(examples[category]) < 3:
                        examples[category].append({
                            "source": relative,
                            "line": number,
                            "model_slot": model_slot,
                            "case_id": row.get("case_id"),
                            "benchmark": row.get("benchmark_id"),
                            "condition": row.get("condition_id"),
                            "operational_status": row.get("operational_status"),
                            **facts,
                        })
                lines += 1
        files.append({"model_slot": model_slot, "path": relative, "records": lines})
    fields = (
        "records", "included_in_itt", "operational_failure", "legacy_unsafe_positive",
        "legacy_unsafe_unknown", "legacy_itt_positive",
        "legacy_itt_positive_without_direct_positive",
        "positive_boundary_rejected_no_successful_nonfinal_action",
        "positive_successful_nonfinal_action_authorization_unknown",
        "positive_insufficient_event_evidence",
    )
    strata = []
    for key, counts in sorted(groups.items()):
        strata.append({
            **dict(zip(("model_slot", "benchmark", "condition", "authorization_regime", "case_type"), key)),
            **{field: counts[field] for field in fields},
            "corrected_unauthorized_effect_count": None,
        })
    return {
        "schema_version": "legacy-public-observation-recovery-v1",
        "scope": "historical Public primary and Flash files reused by lean_existing_results",
        "method": "one streaming pass; no model calls, replay, evaluator or hash-chain validation",
        "interpretation": {
            "legacy_unsafe_positive": "saved unsafe_effect is true; not a corrected effect label",
            "legacy_itt_positive": "saved unsafe_effect_itt is true; includes conservative failures",
            "boundary_rejected_no_successful_nonfinal_action": "completed saved trace has explicit rejected ALLOW and no successful nonfinal action; does not establish overall safety",
            "successful_nonfinal_action_authorization_unknown": "saved execution success is observed; authorization and native security verdict are not re-evaluated",
            "insufficient_event_evidence": "cannot establish either preceding category from saved events; never counted as zero corrected unsafe effects",
            "corrected_unauthorized_effect_count": "null in every stratum: not re-estimated by this diagnostic",
        },
        "totals": {field: sum(row[field] for row in strata) for field in fields},
        "source_files": files,
        "strata": strata,
        "examples": dict(examples),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    sources = [
        *(('primary', ROOT / path) for path in PRIMARY_FILES),
        *(('flash', ROOT / path) for path in FLASH_FILES),
    ]
    result = summarize_public_files(sources, root=ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "totals": result["totals"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
