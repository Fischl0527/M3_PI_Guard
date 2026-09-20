"""Deterministic development cohort; no new historical evidence replay."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs/experiments/correctness_repair_v1"
PLAN = OUTPUT / "plan.jsonl"
STUDY = "m3-correctness-repair-v1"
CONDITIONS = (
    "no_defense", "safe_prompt_only", "m3_policy_only",
    "m3_policy_safe_prompt", "m3_full_normal_prompt", "m3_full",
)
MODELS = {
    "deepseek_pro": "deepseek-v4-pro",
    "deepseek_flash": "deepseek-flash",
    "gemini_flash": "gemini-3.6-flash",
}
SERVICE_VERSIONS = {
    "deepseek_pro": "DeepSeek-V4-Pro-0813",
    "deepseek_flash": "DeepSeek-V4.1-Flash",
    "gemini_flash": "Gemini 3.6 Flash (request-time service)",
}
STRATA = (
    ("agentdojo-v1", "attack", 12),
    ("m3-v2", "attack", 12),
    ("agentdojo-v1", "benign_tool", 8),
    ("m3-v2", "benign_tool", 8),
    ("m3-v2", "benign_no_tool", 8),
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def underlying_task(row: Mapping[str, Any]) -> str:
    if row.get("underlying_task_id"):
        return str(row["underlying_task_id"])
    case = str(row["case_id"])
    if row["benchmark"] == "agentdojo-v1":
        return re.sub(r":injection_task_.*$", "", case)
    return re.sub(r"-A[123]$", "", case)


def _coverage(row: Mapping[str, Any]) -> str:
    value = row.get("selection_stratum", {})
    return json.dumps(value, sort_keys=True) if value else str(row.get("coverage_value", "unknown"))


def round_robin(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=lambda item: str(item["case_id"])):
        groups[_coverage(row)].append(copy.deepcopy(dict(row)))
    result = []
    while any(groups.values()):
        for key in sorted(groups):
            if groups[key]:
                result.append(groups[key].pop(0))
    return result


def select_cases() -> list[dict[str, Any]]:
    attacks = read_jsonl(ROOT / "protocols/paper_upgrade_v2/e6_cross_provider_calibration_v1/cases_deepseek_v1.jsonl")
    benign = read_jsonl(ROOT / "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl")
    by_stratum: list[list[dict[str, Any]]] = []
    seen: set[str] = set()
    for benchmark, category, count in STRATA:
        pool = attacks if category == "attack" else benign
        chosen = []
        for row in round_robin([
            item for item in pool
            if item["benchmark"] == benchmark and item["evaluation_case_type"] == category
        ]):
            task = underlying_task(row)
            if task in seen:
                continue
            seen.add(task)
            row["underlying_task_id"] = task
            row["source_record_sha256"] = row["source_reference"]["sha256"]
            chosen.append(row)
            if len(chosen) == count:
                break
        if len(chosen) != count:
            raise ValueError(f"insufficient distinct tasks: {benchmark}/{category}")
        by_stratum.append(chosen)
    # First five cases cover all five strata; continue round-robin afterwards.
    result = []
    while any(by_stratum):
        for group in by_stratum:
            if group:
                result.append(group.pop(0))
    return result


def build_plan() -> list[dict[str, Any]]:
    cases = select_cases()
    rows = []
    for model_group, model in MODELS.items():
        identity = hashlib.sha256(f"{STUDY}:{model}".encode()).hexdigest()
        sequence = 0
        for rank, case in enumerate(cases):
            rotation = rank % len(CONDITIONS)
            order = CONDITIONS[rotation:] + CONDITIONS[:rotation]
            for condition in order:
                sequence += 1
                key = hashlib.sha256(f"{STUDY}:{model}:{case['case_id']}:{condition}".encode()).hexdigest()[:32]
                rows.append({
                    "schema_version": "m3-correctness-development-plan-1.0",
                    "study_id": STUDY, "runtime_version": "corrected_v1",
                    "run_id": f"{STUDY}-{model_group}", "execution_identity": identity,
                    "work_key": f"corrected-{key}", "sequence": sequence,
                    "case_id": case["case_id"], "selection_id": case["selection_id"],
                    "underlying_task_id": case["underlying_task_id"],
                    "benchmark": case["benchmark"],
                    "evaluation_case_type": case["evaluation_case_type"],
                    "selection_stratum": case.get("selection_stratum", {}),
                    "source_reference": case["source_reference"],
                    "source_record_sha256": case["source_record_sha256"],
                    "sample_role": "development_historical_risk_enriched" if case["evaluation_case_type"] == "attack" else "development_benign",
                    "provider_id": "gemini" if model_group == "gemini_flash" else "deepseek",
                    "model_group": model_group, "model_id": model,
                    "service_version_documented": SERVICE_VERSIONS[model_group],
                    "model_role": "second" if model_group == "deepseek_flash" else "primary",
                    "condition_id": condition, "authorization_regime": "auto_compiled",
                    "max_provider_calls": 8, "max_tokens": 512, "temperature": 0,
                    "formal_prefix": rank < 5, "status": "pending",
                    "evidence_level": "development_only",
                })
    if len(rows) != 864 or len({row["work_key"] for row in rows}) != 864:
        raise ValueError("development plan shape drift")
    return rows


def write_plan() -> Path:
    rows = build_plan()
    if PLAN.exists():
        if read_jsonl(PLAN) != rows:
            raise ValueError("existing development plan differs; do not overwrite")
        return PLAN
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with PLAN.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return PLAN
