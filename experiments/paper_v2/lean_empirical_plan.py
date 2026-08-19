"""Build the fixed lean authorization-regime experiment plan.

Selection uses only frozen Public-v1 identifiers and pre-outcome strata.  It
never reads an existing model result.  The generated plan contains 900
DeepSeek-Pro work items and a nested 450-item Gemini cross-vendor validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PLAN = PROJECT_ROOT / "protocols/paper_upgrade_v2/public_execution_plan_v1.jsonl"
CASE_OUTPUT = PROJECT_ROOT / "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl"
PLAN_OUTPUT = PROJECT_ROOT / "protocols/paper_upgrade_v2/lean_empirical_execution_plan_v1.jsonl"
MANIFEST_OUTPUT = PROJECT_ROOT / "protocols/paper_upgrade_v2/lean_empirical_execution_manifest_v1.json"
SELECTION_SEED = "m3-q2-lean-authorization-study-2026-08-19-v1"
SCHEMA_VERSION = "m3-paper-v2-lean-empirical-plan-1.0"

MAIN_QUOTAS = {
    ("agentdojo-v1", "attack"): 50,
    ("m3-v2", "attack"): 50,
    ("agentdojo-v1", "benign_tool"): 30,
    ("m3-v2", "benign_tool"): 30,
    ("m3-v2", "benign_no_tool"): 20,
}
REGIME_QUOTAS = {
    ("agentdojo-v1", "attack"): 15,
    ("m3-v2", "attack"): 15,
    ("agentdojo-v1", "benign_tool"): 10,
    ("m3-v2", "benign_tool"): 10,
    ("m3-v2", "benign_no_tool"): 10,
}
GEMINI_QUOTAS = {
    ("agentdojo-v1", "attack"): 25,
    ("m3-v2", "attack"): 25,
    ("agentdojo-v1", "benign_tool"): 15,
    ("m3-v2", "benign_tool"): 15,
    ("m3-v2", "benign_no_tool"): 10,
}

DEEPSEEK_MAIN_CELLS = (
    ("m3_policy_only", "auto_compiled"),
    ("m3_policy_only", "exact_gold"),
    ("m3_full", "auto_compiled"),
    ("m3_full", "exact_gold"),
)
DEEPSEEK_REGIME_CELLS = (
    ("m3_full", "broad"),
    ("m3_full", "underspecified"),
    ("m3_full", "conflicting"),
)
GEMINI_CELLS = (
    ("strongest_peer_reviewed_structural_baseline", "auto_compiled"),
    ("m3_policy_only", "auto_compiled"),
    ("m3_full", "auto_compiled"),
    ("m3_policy_only", "exact_gold"),
    ("m3_full", "exact_gold"),
)


class LeanEmpiricalPlanError(ValueError):
    """Raised when the fixed sample or execution plan cannot be built."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise LeanEmpiricalPlanError(f"{path}:{number}: blank row")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise LeanEmpiricalPlanError(f"{path}:{number}: expected object")
            rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _rank(purpose: str, row: Mapping[str, Any]) -> str:
    value = f"{SELECTION_SEED}\0{purpose}\0{row['benchmark']}\0{row['case_id']}"
    return hashlib.sha256(value.encode()).hexdigest()


def _stratum(row: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    raw = row.get("selection_stratum", {})
    if not isinstance(raw, Mapping):
        raise LeanEmpiricalPlanError("selection_stratum must be an object")
    return tuple(
        sorted(
            (str(key), str(value))
            for key, value in raw.items()
            if key != "sample_type"
        )
    )


def _stratified_take(
    rows: Iterable[dict[str, Any]], *, count: int, purpose: str
) -> list[dict[str, Any]]:
    groups: dict[tuple[tuple[str, str], ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_stratum(row)].append(row)
    if not groups:
        raise LeanEmpiricalPlanError(f"{purpose}: no eligible strata")
    representatives: list[dict[str, Any]] = []
    for key in sorted(groups):
        representatives.append(
            min(groups[key], key=lambda row: _rank(f"{purpose}:{key}", row))
        )
    representatives.sort(key=lambda row: _rank(f"{purpose}:representatives", row))
    selected = representatives[:count]
    if count <= len(representatives):
        return sorted(selected, key=lambda row: _rank(f"{purpose}:final", row))
    used = {(row["benchmark"], row["case_id"]) for row in selected}
    remaining = [
        row
        for group in groups.values()
        for row in group
        if (row["benchmark"], row["case_id"]) not in used
    ]
    remaining.sort(key=lambda row: _rank(purpose, row))
    selected.extend(remaining[: count - len(selected)])
    if len(selected) != count:
        raise LeanEmpiricalPlanError(f"{purpose}: requested {count}, got {len(selected)}")
    return sorted(selected, key=lambda row: _rank(f"{purpose}:final", row))


def _primary_case_universe(source_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    condition_budgets: dict[str, int] = {}
    for row in _read_jsonl(source_path):
        if row.get("model_role") != "primary":
            continue
        condition = str(row["condition_id"])
        budget = int(row["max_provider_calls"])
        previous = condition_budgets.setdefault(condition, budget)
        if previous != budget:
            raise LeanEmpiricalPlanError(f"{condition}: inconsistent call budget")
        key = (str(row["benchmark"]), str(row["case_id"]))
        unique.setdefault(key, row)
    if len(unique) != 847:
        raise LeanEmpiricalPlanError(f"expected 847 primary Public cases, got {len(unique)}")
    return list(unique.values()), condition_budgets


def _eligible(row: Mapping[str, Any], cell: tuple[str, str]) -> bool:
    if (str(row["benchmark"]), str(row["evaluation_case_type"])) != cell:
        return False
    return True


def _select_by_quotas(
    universe: Iterable[dict[str, Any]],
    quotas: Mapping[tuple[str, str], int],
    *,
    purpose: str,
) -> list[dict[str, Any]]:
    rows = list(universe)
    selected: list[dict[str, Any]] = []
    for cell, count in quotas.items():
        selected.extend(
            _stratified_take(
                (row for row in rows if _eligible(row, cell)),
                count=count,
                purpose=f"{purpose}:{cell[0]}:{cell[1]}",
            )
        )
    return selected


def _case_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "m3-paper-v2-lean-case-selection-1.0",
        "selection_id": f"lean-v1:{row['benchmark']}:{row['case_id']}",
        "case_id": str(row["case_id"]),
        "benchmark": str(row["benchmark"]),
        "evaluation_case_type": str(row["evaluation_case_type"]),
        "context_dependent": bool(row["context_dependent"]),
        "source_reference": dict(row["source_reference"]),
        "selection_stratum": dict(row["selection_stratum"]),
    }


def _work_key(
    provider_id: str,
    model_id: str,
    case: Mapping[str, Any],
    condition_id: str,
    authorization_regime: str,
) -> str:
    value = {
        "study": "lean-empirical-v1",
        "provider_id": provider_id,
        "model_id": model_id,
        "benchmark": case["benchmark"],
        "case_id": case["case_id"],
        "condition_id": condition_id,
        "authorization_regime": authorization_regime,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _work_item(
    *,
    provider_id: str,
    model_id: str,
    case: Mapping[str, Any],
    condition_id: str,
    authorization_regime: str,
    max_provider_calls: int,
    sample_role: str,
) -> dict[str, Any]:
    return {
        "schema_version": "m3-paper-v2-lean-work-item-1.0",
        "study_id": "m3-q2-lean-authorization-v1",
        "work_key": _work_key(
            provider_id,
            model_id,
            case,
            condition_id,
            authorization_regime,
        ),
        "run_id": f"lean-v1-{provider_id}",
        "execution_identity": hashlib.sha256(
            f"lean-v1\0{provider_id}\0{model_id}".encode()
        ).hexdigest(),
        "provider_id": provider_id,
        "model_id": model_id,
        "model_role": "primary" if provider_id == "deepseek" else "cross_vendor_validation",
        "selection_id": case["selection_id"],
        "case_id": case["case_id"],
        "benchmark": case["benchmark"],
        "evaluation_case_type": case["evaluation_case_type"],
        "context_dependent": case["context_dependent"],
        "source_reference": dict(case["source_reference"]),
        "source_record_sha256": str(case["source_reference"]["sha256"]),
        "selection_stratum": dict(case["selection_stratum"]),
        "condition_id": condition_id,
        "authorization_regime": authorization_regime,
        "analysis_tier": "authorization_regime_experiment",
        "sample_role": sample_role,
        "max_provider_calls": max_provider_calls,
        "formal_prefix": False,
        "status": "pending",
    }


def _mark_canary(rows: list[dict[str, Any]], provider_id: str) -> None:
    provider_rows = [row for row in rows if row["provider_id"] == provider_id]
    desired = (
        (
            ("agentdojo-v1", "attack", "m3_policy_only", "auto_compiled"),
            ("m3-v2", "attack", "m3_full", "auto_compiled"),
            ("agentdojo-v1", "benign_tool", "m3_policy_only", "exact_gold"),
            ("m3-v2", "benign_tool", "m3_full", "exact_gold"),
            ("m3-v2", "benign_no_tool", "m3_full", "broad"),
            ("m3-v2", "attack", "m3_full", "conflicting"),
        )
        if provider_id == "deepseek"
        else (
            ("agentdojo-v1", "attack", "strongest_peer_reviewed_structural_baseline", "auto_compiled"),
            ("m3-v2", "attack", "m3_policy_only", "auto_compiled"),
            ("agentdojo-v1", "benign_tool", "m3_full", "auto_compiled"),
            ("m3-v2", "benign_tool", "m3_policy_only", "exact_gold"),
            ("m3-v2", "benign_no_tool", "m3_full", "exact_gold"),
            ("agentdojo-v1", "attack", "m3_full", "auto_compiled"),
        )
    )
    selected: set[str] = set()
    for benchmark, case_type, condition, regime in desired:
        match = next(
            (
                row
                for row in provider_rows
                if row["work_key"] not in selected
                and row["benchmark"] == benchmark
                and row["evaluation_case_type"] == case_type
                and row["condition_id"] == condition
                and row["authorization_regime"] == regime
            ),
            None,
        )
        if match is None:
            raise LeanEmpiricalPlanError(f"missing {provider_id} formal-prefix cell")
        match["formal_prefix"] = True
        selected.add(str(match["work_key"]))


def build_plan(
    source_path: Path = SOURCE_PLAN,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    universe, budgets = _primary_case_universe(source_path)
    main_raw = _select_by_quotas(universe, MAIN_QUOTAS, purpose="main-180")
    cases = [_case_projection(row) for row in main_raw]
    by_key = {(row["benchmark"], row["case_id"]): row for row in cases}
    regime_raw = _select_by_quotas(main_raw, REGIME_QUOTAS, purpose="regime-60")
    gemini_raw = _select_by_quotas(main_raw, GEMINI_QUOTAS, purpose="gemini-90")
    regime_keys = {(row["benchmark"], row["case_id"]) for row in regime_raw}
    gemini_keys = {(row["benchmark"], row["case_id"]) for row in gemini_raw}
    for key, case in by_key.items():
        case["regime_subset"] = key in regime_keys
        case["gemini_subset"] = key in gemini_keys

    rows: list[dict[str, Any]] = []
    for case in cases:
        for condition, regime in DEEPSEEK_MAIN_CELLS:
            rows.append(
                _work_item(
                    provider_id="deepseek",
                    model_id="deepseek-v4-pro",
                    case=case,
                    condition_id=condition,
                    authorization_regime=regime,
                    max_provider_calls=budgets[condition],
                    sample_role="main_180",
                )
            )
        if case["regime_subset"]:
            for condition, regime in DEEPSEEK_REGIME_CELLS:
                rows.append(
                    _work_item(
                        provider_id="deepseek",
                        model_id="deepseek-v4-pro",
                        case=case,
                        condition_id=condition,
                        authorization_regime=regime,
                        max_provider_calls=budgets[condition],
                        sample_role="nested_regime_60",
                    )
                )
    for case in cases:
        if not case["gemini_subset"]:
            continue
        for condition, regime in GEMINI_CELLS:
            rows.append(
                _work_item(
                    provider_id="gemini",
                    model_id="gemini-3.6-flash",
                    case=case,
                    condition_id=condition,
                    authorization_regime=regime,
                    max_provider_calls=budgets[condition],
                    sample_role="gemini_nested_90",
                )
            )
    _mark_canary(rows, "deepseek")
    _mark_canary(rows, "gemini")
    rows.sort(
        key=lambda row: (
            0 if row["provider_id"] == "deepseek" else 1,
            0 if row["formal_prefix"] else 1,
            str(row["work_key"]),
        )
    )
    for sequence, row in enumerate(rows, 1):
        row["sequence"] = sequence
    counts = Counter(row["provider_id"] for row in rows)
    if len(cases) != 180 or len(regime_keys) != 60 or len(gemini_keys) != 90:
        raise LeanEmpiricalPlanError("180/60/90 nested case counts drift")
    if counts != Counter({"deepseek": 900, "gemini": 450}):
        raise LeanEmpiricalPlanError(f"execution counts drift: {dict(counts)}")
    if len({row["work_key"] for row in rows}) != 1350:
        raise LeanEmpiricalPlanError("work keys are not unique")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "frozen_results_pending",
        "selection_seed": SELECTION_SEED,
        "selection_method": "sha256_ranked_stratified_without_model_outcomes",
        "source_plan": source_path.relative_to(PROJECT_ROOT).as_posix(),
        "case_counts": {
            "main": 180,
            "regime_nested": 60,
            "gemini_nested": 90,
            "by_benchmark_and_type": {
                f"{benchmark}:{case_type}": count
                for (benchmark, case_type), count in MAIN_QUOTAS.items()
            },
        },
        "work_item_counts": {"deepseek": 900, "gemini": 450, "total": 1350},
        "formal_prefix_records": {"deepseek": 6, "gemini": 6},
        "outcomes_accessed_for_selection": False,
        "public_m3_sealed_holdout_partition_may_be_sampled": True,
        "independent_blind_set_used": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "real_external_effects_enabled": False,
        "gemini_billing_tier": "free",
        "gemini_paid_ceiling_usd": 0.0,
    }
    return cases, rows, manifest


def write_plan() -> dict[str, Any]:
    cases, rows, manifest = build_plan()
    _write_jsonl(CASE_OUTPUT, cases)
    _write_jsonl(PLAN_OUTPUT, rows)
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_plan() -> dict[str, Any]:
    cases, rows, manifest = build_plan()
    if _read_jsonl(CASE_OUTPUT) != cases or _read_jsonl(PLAN_OUTPUT) != rows:
        raise LeanEmpiricalPlanError("frozen lean selection or plan drift")
    observed = json.loads(MANIFEST_OUTPUT.read_text(encoding="utf-8"))
    if observed != manifest:
        raise LeanEmpiricalPlanError("frozen lean manifest drift")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = write_plan() if args.write else verify_plan()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
