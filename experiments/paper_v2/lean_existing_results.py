"""对已完成的 paper-v2 实验进行单遍扫描综合分析。

交叉比对多个研究阶段的结论一致性，剔除潜在时序退化偏差。
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = (
    PROJECT_ROOT
    / "outputs/experiments/lean_empirical/analysis/existing_results_analysis_v1.json"
)

PRIMARY_FILES = (
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-v4-primary-4b717417fec675c3540d186e4b6d6af403bb03c208ebc91e1b1e84b1e7e83e30/experiment_records.jsonl",
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-primary-continuation-s0-v2-858c4fed769c228e4f333a86e901c648cf813152397dcaf7d65d8d8ff5288b5d/experiment_records.jsonl",
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-primary-continuation-s1-v2-da215295b67215de0d2be969f85f6229e1c37ad7404e6e20f4e4c77b1e977267/experiment_records.jsonl",
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-primary-continuation-s2-v2-cf3a34798e370434b6ad4bd3a06a846cea52bb792eeade0151b8d974e8b00864/experiment_records.jsonl",
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-primary-continuation-s3-v2-ae6309d57e853267814c0e70201ce61254ff008d526dad9d933ae550e0c626b9/experiment_records.jsonl",
)
FLASH_FILES = (
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-v4-second-13e640041d69a2b4ce1d95c2471cd8644c3a1eac81885d0a5b96cf98b46a56a4/experiment_records.jsonl",
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-second-continuation-s0-v2-cb6e65e0853e25f5d84374524bf0d10ac379a5326a290b445550779b71370b2f/experiment_records.jsonl",
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-second-recovery-s0-v3-77d0f1baf7f25dc5f6a4b79c55ffc5957c0320db49418b776b7c80069256557d/experiment_records.jsonl",
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-second-continuation-s1-v2-13e751fd0b8506bb4826c3eca0c72888e5d4a187bd67b00cbf638e644f244eef/experiment_records.jsonl",
    "outputs/paper_upgrade_v2/formal_public/deepseek/public-second-recovery-s1-v3-3fe6c886e371ddf526a8d7655a711ccd1ae09161f58fdf9d80606db8ded333c5/experiment_records.jsonl",
)
MEDIUM_FILES = (
    "outputs/paper_upgrade_v2/formal_medium/deepseek/8d08cab3febccdf5a4360d208766c39cef851fa9ec8b9c15799ee30171a213bf/experiment_records_v2.jsonl",
    "outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/experiment_records_v2.jsonl",
)
ADAPTIVE_FILES = (
    "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary/query_ledger.jsonl",
    "outputs/paper_upgrade_v2/adaptive_formal_pro_v2/pro_50-45d4aa32cfc17815e720f9cfc7f41cae48563a1a0f2611d4d441844d7d45c1a7/query_ledger.jsonl",
    "outputs/paper_upgrade_v2/adaptive_formal_pro_v2/pro_200-0f3e1f04239237c56b3ece87ef8eda8a6a4daf299bfa1c88bb04bf6280737d2f/query_ledger.jsonl",
)


class LeanExistingResultsError(ValueError):
    """当紧凑单遍分析遇到无效输入时抛出的异常。"""


def _wilson(successes: int, total: int) -> dict[str, float | int]:
    if total == 0:
        return {"successes": successes, "total": total, "rate": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return {
        "successes": successes,
        "total": total,
        "rate": round(p, 8),
        "ci_low": round(max(0.0, center - radius), 8),
        "ci_high": round(min(1.0, center + radius), 8),
    }


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return round(float(ordered[index]), 4)


def _load_record_entries(paths: Sequence[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    keys: set[str] = set()
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    raise LeanExistingResultsError(f"{path}:{number}: blank row")
                entry = json.loads(line)
                if not isinstance(entry, dict) or not isinstance(entry.get("record"), dict):
                    raise LeanExistingResultsError(f"{path}:{number}: invalid record entry")
                key = str(entry.get("work_key", ""))
                if not key or key in keys:
                    raise LeanExistingResultsError(f"{path}:{number}: duplicate or missing work key")
                record = dict(entry["record"])
                digest = record.get("online_visible_field_digest")
                if not isinstance(digest, Mapping) or digest.get("forbidden_fields_present") is not False:
                    raise LeanExistingResultsError(f"{path}:{number}: online field isolation failed")
                if record.get("included_in_intention_to_treat") is not True:
                    raise LeanExistingResultsError(f"{path}:{number}: record excluded from ITT")
                record["_work_key"] = key
                records.append(record)
                keys.add(key)
    return records


def _cell_summary(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        groups[
            (
                str(row["condition_id"]),
                str(row["authorization_regime"]),
                str(row["evaluation_case_type"]),
            )
        ].append(row)
    result: list[dict[str, Any]] = []
    for (condition, regime, case_type), rows in sorted(groups.items()):
        unsafe = sum(bool(row["unsafe_effect_itt"]) for row in rows)
        complete = sum(bool(row["task_completion"]) for row in rows)
        asks = sum(row["initial_guard_decision"] == "ASK" for row in rows)
        denies = sum(row["effective_decision"] == "DENY" for row in rows)
        failures = sum(row["operational_status"] != "completed" for row in rows)
        latencies = [float(row["latency_ms"]["total"]) for row in rows]
        total_tokens = sum(int(row["token_usage"]["total"]) for row in rows)
        result.append(
            {
                "condition_id": condition,
                "authorization_regime": regime,
                "evaluation_case_type": case_type,
                "records": len(rows),
                "unsafe_effect": _wilson(unsafe, len(rows)),
                "task_completion": _wilson(complete, len(rows)),
                "ask": _wilson(asks, len(rows)),
                "deny": _wilson(denies, len(rows)),
                "operational_failures": failures,
                "latency_ms_p50": round(statistics.median(latencies), 4),
                "latency_ms_p95": _percentile(latencies, 0.95),
                "total_tokens": total_tokens,
            }
        )
    return result


def _paired_full_vs_policy(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    indexed = {
        (
            str(row["case_id"]),
            str(row["authorization_regime"]),
            str(row["condition_id"]),
        ): row
        for row in records
    }
    pairs: dict[tuple[str, str], list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = defaultdict(list)
    for (case_id, regime, condition), policy in indexed.items():
        if condition != "m3_policy_only":
            continue
        full = indexed.get((case_id, regime, "m3_full"))
        if full is None:
            continue
        pairs[(regime, str(policy["evaluation_case_type"]))].append((policy, full))
    output: list[dict[str, Any]] = []
    for (regime, case_type), rows in sorted(pairs.items()):
        metric = "unsafe_effect_itt" if case_type == "attack" else "task_completion"
        policy_positive = sum(bool(left[metric]) for left, _ in rows)
        full_positive = sum(bool(right[metric]) for _, right in rows)
        full_only = sum(not bool(left[metric]) and bool(right[metric]) for left, right in rows)
        policy_only = sum(bool(left[metric]) and not bool(right[metric]) for left, right in rows)
        output.append(
            {
                "authorization_regime": regime,
                "evaluation_case_type": case_type,
                "metric": metric,
                "pairs": len(rows),
                "policy_positive": policy_positive,
                "full_positive": full_positive,
                "full_minus_policy_pp": round(100 * (full_positive - policy_positive) / len(rows), 4),
                "discordant_full_only": full_only,
                "discordant_policy_only": policy_only,
            }
        )
    return output


def summarize_records(records: Sequence[Mapping[str, Any]], *, expected: int, label: str) -> dict[str, Any]:
    if len(records) != expected:
        raise LeanExistingResultsError(f"{label}: expected {expected} records, got {len(records)}")
    models = Counter()
    provider_calls = 0
    cost_cny = 0.0
    for row in records:
        bundle = row.get("provider_trace_bundle")
        if not isinstance(bundle, Mapping):
            raise LeanExistingResultsError(f"{label}: provider bundle missing")
        models[str(bundle.get("model_id"))] += 1
        provider_calls += int(bundle.get("completed_request_count", 0))
        usage = bundle.get("usage_summary", {})
        if isinstance(usage, Mapping):
            cost_cny += float(usage.get("cumulative_cost_cny", 0.0))
    return {
        "records": len(records),
        "unique_work_keys": len({str(row["_work_key"]) for row in records}),
        "models": dict(sorted(models.items())),
        "provider_calls": provider_calls,
        "cost_cny": round(cost_cny, 8),
        "diagnostic_records": sum(row["result_tier"] == "diagnostic" for row in records),
        "operational_failures": dict(sorted(Counter(str(row["operational_status"]) for row in records if row["operational_status"] != "completed").items())),
        "cell_statistics": _cell_summary(records),
        "paired_full_vs_policy": _paired_full_vs_policy(records),
    }


def _load_adaptive_terminals(paths: Sequence[Path]) -> list[dict[str, Any]]:
    terminal: list[dict[str, Any]] = []
    keys: set[str] = set()
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    raise LeanExistingResultsError(f"{path}:{number}: blank row")
                event = json.loads(line)
                if event.get("event_type") != "terminal":
                    continue
                key = str(event.get("work_key", ""))
                if not key or key in keys:
                    raise LeanExistingResultsError(f"{path}:{number}: duplicate adaptive terminal")
                record = event.get("record")
                if not isinstance(record, dict):
                    raise LeanExistingResultsError(f"{path}:{number}: adaptive record missing")
                terminal.append(event)
                keys.add(key)
    return terminal


def summarize_adaptive(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        by_case[str(event["case_id"])].append(event)
    if len(by_case) != 40:
        raise LeanExistingResultsError(f"adaptive: expected 40 tasks, got {len(by_case)}")
    first_success: dict[str, int] = {}
    task_rows: list[dict[str, Any]] = []
    for case_id, rows in sorted(by_case.items()):
        rows = sorted(rows, key=lambda row: int(row["query_index"]))
        successes = [
            int(row["query_index"])
            for row in rows
            if bool(row["record"]["unsafe_effect_itt"])
        ]
        if successes:
            first_success[case_id] = min(successes)
        task_rows.append(
            {
                "case_id": case_id,
                "terminal_queries": len(rows),
                "maximum_query_index": max(int(row["query_index"]) for row in rows),
                "first_unsafe_effect_query": first_success.get(case_id),
                "diagnostic_queries": sum(row["record"]["result_tier"] == "diagnostic" for row in rows),
            }
        )
    return {
        "tasks": 40,
        "terminal_queries": len(events),
        "budget_50": _wilson(sum(query <= 50 for query in first_success.values()), 40),
        "budget_200": _wilson(sum(query <= 200 for query in first_success.values()), 40),
        "first_success_queries": dict(sorted(first_success.items())),
        "task_summaries": task_rows,
        "claim_boundary": "budgets_50_and_200_only_no_saturation_claim",
    }


def analyze_existing_results() -> dict[str, Any]:
    primary = _load_record_entries(tuple(PROJECT_ROOT / path for path in PRIMARY_FILES))
    flash = _load_record_entries(tuple(PROJECT_ROOT / path for path in FLASH_FILES))
    medium = _load_record_entries(tuple(PROJECT_ROOT / path for path in MEDIUM_FILES))
    adaptive = _load_adaptive_terminals(tuple(PROJECT_ROOT / path for path in ADAPTIVE_FILES))
    return {
        "schema_version": "m3-paper-v2-lean-existing-analysis-1.0",
        "status": "completed_one_pass_existing_result_analysis",
        "analysis_policy": {
            "historical_verifiers_replayed": False,
            "full_harness_run": False,
            "provider_calls_made": 0,
            "all_failures_retained_in_itt": True,
            "online_forbidden_fields_present": False,
        },
        "public_primary_deepseek_v4_pro": summarize_records(primary, expected=5082, label="Public primary"),
        "public_second_deepseek_v4_flash": summarize_records(flash, expected=1791, label="Public Flash"),
        "medium_deepseek_v4_pro": summarize_records(medium, expected=480, label="Medium"),
        "adaptive_deepseek_v4_pro": summarize_adaptive(adaptive),
    }


def main() -> int:
    result = analyze_existing_results()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": OUTPUT_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "record_counts": {
                    "public_primary": result["public_primary_deepseek_v4_pro"]["records"],
                    "public_flash": result["public_second_deepseek_v4_flash"]["records"],
                    "medium": result["medium_deepseek_v4_pro"]["records"],
                    "adaptive_tasks": result["adaptive_deepseek_v4_pro"]["tasks"],
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
