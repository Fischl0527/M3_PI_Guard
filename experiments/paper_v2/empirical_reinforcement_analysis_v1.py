"""强化研究的一次性统计；只读本研究公开记录，不调用模型或重算历史。

核算扩增样本与强化对抗下的安全阻断率与任务完成度统计指标。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from experiments.paper_v2.e6_cross_provider_calibration_analysis_v1 import _newcombe_paired
from experiments.paper_v2.correctness_runner_v1 import critical_error
from m3_eval.statistics import holm_adjust, mcnemar_exact, wilson_interval

BOOTSTRAP_SEED = "m3-reinforcement-20261012-v1"
OUTPUT = Path(__file__).resolve().parents[2] / "outputs/experiments/empirical_reinforcement_v1"
ND = ("no_defense", "auto_compiled")
POLICY = ("m3_policy_only", "auto_compiled")
FULL = ("m3_full_normal_prompt", "auto_compiled")
VIGIL = ("strongest_peer_reviewed_structural_baseline", "auto_compiled")
BENCHMARKS = ("agentdojo-v1", "m3-v2")


def endpoint_summary(
    rows: Sequence[Mapping[str, Any]], field: str, *, planned: int,
) -> dict[str, Any]:
    """未知值和未启动项留在计划分母；只对已观察布尔值计算观察比例。"""
    values = [row.get(field) for row in rows]
    if any(value is not None and type(value) is not bool for value in values):
        raise ValueError("endpoint must be boolean or unknown")
    numerator = sum(value is True for value in values)
    observed = sum(value is not None for value in values)
    if planned < len(rows) or planned < observed:
        raise ValueError("records exceed planned denominator")
    unknown = planned - observed
    return {
        "numerator": numerator, "observed_denominator": observed,
        "planned_denominator": planned, "unknown": unknown,
        "observed_rate": numerator / observed if observed else None,
        "wilson_95": wilson_interval(numerator, observed),
        "itt_lower": numerator / planned if planned else None,
        "itt_upper": (numerator + unknown) / planned if planned else None,
    }


def _stratum(row: Mapping[str, Any]) -> str:
    """AgentDojo按套件、M3按授权类别分层，不把两个评分语义合并。"""
    if row.get("benchmark") == "agentdojo-v1":
        source = row.get("selection_stratum", {})
        return str(row.get("suite", source.get("suite", "unspecified")))
    return str(row.get("authorization_profile", "unspecified"))


def paired_contrast(
    rows: Sequence[Mapping[str, Any]], field: str,
    baseline: tuple[str, str], treatment: tuple[str, str], *,
    bootstrap_draws: int = 10_000, label: str = "paired",
) -> dict[str, Any]:
    """以底层任务配对；缺失只影响观察估计，不从ITT分母消失。"""
    if bootstrap_draws < 1:
        raise ValueError("bootstrap draws must be positive")
    grouped: dict[str, dict[tuple[str, str], Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        cell = (row["condition_id"], row["authorization_regime"])
        if cell not in (baseline, treatment):
            continue
        task = str(row["underlying_task_id"])
        if cell in grouped[task]:
            raise ValueError("duplicate underlying task in comparison cell")
        grouped[task][cell] = row
    blocks = list(grouped.values())
    if any(baseline not in block or treatment not in block for block in blocks):
        raise ValueError("comparison plan is not task-paired")
    known = []
    lower = upper = 0.0
    for block in blocks:
        a, b = block[baseline].get(field), block[treatment].get(field)
        if any(value is not None and type(value) is not bool for value in (a, b)):
            raise ValueError("paired endpoint must be boolean or unknown")
        lower += (int(b) if b is not None else 0) - (int(a) if a is not None else 1)
        upper += (int(b) if b is not None else 1) - (int(a) if a is not None else 0)
        if type(a) is bool and type(b) is bool:
            if _stratum(block[baseline]) != _stratum(block[treatment]):
                raise ValueError("paired task strata disagree")
            known.append((a, b, _stratum(block[baseline])))
    a_values = [a for a, _, _ in known]
    b_values = [b for _, b, _ in known]
    interval = _newcombe_paired(a_values, b_values)
    seed = int.from_bytes(hashlib.sha256(f"{BOOTSTRAP_SEED}:{label}".encode()).digest()[:8], byteorder="big")
    bootstrap: dict[str, Any] = {
        "method": "stratified_underlying_task_cluster_bootstrap",
        "seed_label": BOOTSTRAP_SEED, "seed": seed,
        "draws": bootstrap_draws, "clusters": len(known),
        "ci_low": None, "ci_high": None, "degenerate": False,
    }
    if known:
        strata: dict[str, list[int]] = defaultdict(list)
        for a, b, stratum in known:
            strata[stratum].append(int(b) - int(a))
        rng = np.random.default_rng(seed)
        totals = np.zeros(bootstrap_draws)
        for stratum in sorted(strata):
            values = np.asarray(strata[stratum], dtype=float)
            indexes = rng.integers(0, len(values), size=(bootstrap_draws, len(values)))
            totals += values[indexes].sum(axis=1)
        low, high = map(float, np.quantile(totals / len(known), [.025, .975]))
        degenerate = low == high
        bootstrap.update({
            "strata": {key: len(value) for key, value in sorted(strata.items())},
            "ci_low": None if degenerate else low,
            "ci_high": None if degenerate else high, "degenerate": degenerate,
            "fallback": "newcombe_paired_hybrid_score" if degenerate else None,
        })
    mcnemar = mcnemar_exact(a_values, b_values) if known else None
    return {
        "unit": "underlying_task", "planned_pairs": len(blocks),
        "known_pairs": len(known), "unknown_pairs": len(blocks) - len(known),
        "estimate": interval["estimate"], "paired_interval": interval,
        "bootstrap": bootstrap, "mcnemar": mcnemar,
        "p_value": mcnemar["p_value"] if mcnemar else None,
        "itt_difference_lower": lower / len(blocks) if blocks else None,
        "itt_difference_upper": upper / len(blocks) if blocks else None,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _validated_records(
    plan: Sequence[Mapping[str, Any]], raw: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    expected = {row["work_key"]: row for row in plan}
    if len(expected) != len(plan):
        raise ValueError("duplicate planned work key")
    task_cells = {(row["benchmark"], row["underlying_task_id"], row["condition_id"],
                   row["authorization_regime"]) for row in plan}
    if len(task_cells) != len(plan):
        raise ValueError("duplicate underlying task in planned cell")
    records: dict[str, dict[str, Any]] = {}
    calls: Counter[str] = Counter()
    request_ids: set[str] = set()
    identity = ("case_id", "underlying_task_id", "benchmark", "condition_id",
                "authorization_regime", "model_id", "requires_confirmation",
                "authorization_profile", "runtime_revision", "compiler_revision",
                "execution_identity", "prompt_factor", "module_factor", "study",
                "max_provider_calls", "max_tokens", "temperature", "timeout_seconds",
                "requested_model_id", "expected_returned_model_version")
    for source in raw:
        row = dict(source)
        key = row["work_key"]
        original = expected.get(key)
        if original is None or any(row.get(field) != original[field]
                                   for field in identity if field in original):
            raise ValueError("result identity differs from frozen plan")
        attempt = row.get("attempt")
        if type(attempt) is not int or attempt not in (0, 1, 2):
            raise ValueError("invalid explicit attempt")
        previous = records.get(key)
        if previous is None:
            if attempt != (0 if row.get("operational_status") == "not_run" else 1):
                raise ValueError("invalid first attempt")
        elif previous.get("response_obtained"):
            raise ValueError("response-bearing work item repeated")
        elif attempt != previous["attempt"] + 1:
            raise ValueError("attempt is repeated or skips recovery order")
        if critical_error(row):
            raise ValueError("critical provider, identity or safety error")
        requests = row.get("provider_requests", [])
        if row.get("provider_call_count", 0) != len(requests):
            raise ValueError("provider call count differs from receipts")
        calls[key] += len(requests)
        if calls[key] > original.get("max_provider_calls", 8):
            raise ValueError("cumulative requests exceed frozen work-item cap")
        for request in requests:
            local = request.get("local_request_id")
            if not local or local in request_ids or not request.get("payload_sha256"):
                raise ValueError("request identity missing or duplicated")
            request_ids.add(local)
            if request.get("response_received") and not all(request.get(field) for field in
                                                           ("provider_response_id", "returned_model")):
                raise ValueError("official response identity missing")
        if bool(row.get("response_obtained")) != any(request.get("response_received") for request in requests):
            raise ValueError("response-bearing status differs from request receipts")
        for field in ("task_completion", "unsafe_effect"):
            value = row.get(field)
            if value is not None and type(value) is not bool:
                raise ValueError("endpoint must be boolean or unknown")
            if row.get(f"{field}_observed") is False and value is not None:
                raise ValueError("unobserved endpoint cannot become a known boolean")
        records[key] = row
    return records


def _known_failure(row: Mapping[str, Any]) -> bool:
    return row.get("operational_status") not in {
        None, "pending", "not_run", "completed", "waiting_confirmation",
        "awaiting_confirmation", "confirmation_required",
    }


def _latency(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = []
    invalid = 0
    for row in rows:
        value = row.get("latency_ms")
        if isinstance(value, Mapping):
            value = value.get("total")
        if value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            invalid += 1
            continue
        values.append(float(value))
    return {"observed": len(values), "missing": len(rows) - len(values) - invalid,
            "invalid": invalid, "p50_ms": float(np.quantile(values, .5)) if values else None,
            "p95_ms": float(np.quantile(values, .95)) if values else None}


def _number_summary(values) -> dict[str, Any]:
    """负担字段仅汇总显式有限非负数；缺失与非法值分别计数，不补零。"""
    known = [value for value in values
             if type(value) in (int, float) and math.isfinite(value) and value >= 0]
    missing = sum(value is None for value in values)
    return {
        "observed": len(known), "missing": missing,
        "invalid": len(values) - len(known) - missing,
        "known_total": sum(known) if known else None,
        "mean": float(np.mean(known)) if known else None,
        "p50": float(np.quantile(known, .5)) if known else None,
        "p95": float(np.quantile(known, .95)) if known else None,
        "minimum": min(known) if known else None,
        "maximum": max(known) if known else None,
    }


def _burden(plan_rows, attempts):
    """累计本cell各实际尝试的调用/token/估算成本；终态任务分母由调用者维护。"""
    attempted = [row for row in attempts if row.get("operational_status") != "not_run"]
    per_attempt = _number_summary([row.get("provider_call_count") for row in attempted])
    by_work = defaultdict(list)
    for row in attempted:
        by_work[row["work_key"]].append(row.get("provider_call_count"))
    per_work = _number_summary([
        sum(values) if all(type(value) is int and value >= 0 for value in values) else None
        for values in by_work.values()
    ])
    token_summaries = {
        field: _number_summary([
            row.get("token_usage", {}).get(field) if isinstance(row.get("token_usage"), Mapping) else None
            for row in attempted
        ]) for field in ("input", "output", "total")
    }
    costs, incomplete, other_currency = [], 0, 0
    for row in attempted:
        cost = row.get("cost")
        if not isinstance(cost, Mapping):
            costs.append(None)
            incomplete += 1
            continue
        if cost.get("currency") not in (None, "CNY"):
            other_currency += 1
            costs.append(None)
        else:
            # 当前DeepSeek记录沿用CNY估价接口；无币种的旧测试摘要也兼容。
            costs.append(cost.get("amount"))
        incomplete += cost.get("usage_complete") is not True
    cost_summary = _number_summary(costs)
    vigil = plan_rows[0]["condition_id"] == "strongest_peer_reviewed_structural_baseline"
    generation = _number_summary([row.get("vigil_constraint_generation_calls") for row in attempted]) if vigil else {
        "observed": 0, "missing": 0, "invalid": 0, "known_total": None,
        "mean": None, "p50": None, "p95": None, "minimum": None, "maximum": None,
    }
    return {
        "attempt_records": len(attempted), "provider_call_cap": plan_rows[0].get("max_provider_calls"),
        "provider_calls": per_attempt["known_total"],
        "provider_call_missing_count": per_attempt["missing"],
        "provider_call_invalid_count": per_attempt["invalid"],
        "provider_calls_per_attempt": per_attempt,
        "provider_calls_per_work_item": per_work,
        "token_usage": {field: summary["known_total"] for field, summary in token_summaries.items()},
        "token_usage_observed_count": {field: summary["observed"] for field, summary in token_summaries.items()},
        "token_usage_missing_count": {field: summary["missing"] for field, summary in token_summaries.items()},
        "token_usage_invalid_count": {field: summary["invalid"] for field, summary in token_summaries.items()},
        "cost_estimate_cny": cost_summary["known_total"],
        "cost_observed_count": cost_summary["observed"],
        "cost_missing_count": cost_summary["missing"], "cost_invalid_count": cost_summary["invalid"],
        "cost_other_currency_count": other_currency, "cost_usage_incomplete_count": incomplete,
        "cost_is_invoice": False, "vigil_constraint_generation_applicable": vigil,
        "vigil_constraint_generation_calls": generation,
        "burden_basis": "all recorded attempts; never impute absent call breakdown",
    }


def _cell(plan_rows, records, *, study, model, scope, attempts):
    observed = [records[row["work_key"]] for row in plan_rows if row["work_key"] in records]
    sensitivity = [{**row, "unsafe_or_failure": True if _known_failure(row)
                    else row.get("unsafe_effect")} for row in observed]
    not_run = sum(row.get("operational_status") == "not_run" for row in observed)
    return {
        "study": study, "model": model, "model_id": plan_rows[0]["model_id"],
        "benchmark": plan_rows[0]["benchmark"], "cohort_scope": scope,
        "condition_id": plan_rows[0]["condition_id"],
        "authorization_regime": plan_rows[0]["authorization_regime"],
        "planned": len(plan_rows), "recorded": len(observed),
        "not_run": len(plan_rows) - len(observed) + not_run,
        "known_failures": sum(_known_failure(row) for row in observed),
        "response_bearing": sum(bool(row.get("response_obtained")) for row in observed),
        "unsafe": endpoint_summary(observed, "unsafe_effect", planned=len(plan_rows)),
        "completion": endpoint_summary(observed, "task_completion", planned=len(plan_rows)),
        "unsafe_or_failure": endpoint_summary(sensitivity, "unsafe_or_failure", planned=len(plan_rows)),
        "statuses": dict(Counter(row.get("operational_status", "unknown") for row in observed)),
        "ask_count": sum(row.get("ask_count", 0) for row in observed),
        "ask_items": sum(row.get("ask_count", 0) > 0 for row in observed),
        "deny_count": sum(row.get("deny_count", 0) for row in observed),
        "latency": _latency(observed),
        **_burden(plan_rows, attempts),
    }


def _group_cells(plan, records, *, study, model, raw):
    groups: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    attempts_by_key = defaultdict(list)
    for row in raw:
        attempts_by_key[row["work_key"]].append(row)
    for row in plan:
        scopes = ["all"]
        if study == "utility" and row["benchmark"] == "m3-v2":
            requires = row.get("requires_confirmation")
            if type(requires) is not bool:
                raise ValueError("M3 utility plan requires explicit confirmation classification")
            scopes += ["confirmation_required" if requires else "non_confirmation"]
            scopes += [f"workflow:{row.get('scenario_type', 'unspecified')}",
                       f"authorization:{row.get('authorization_profile', 'unspecified')}"]
        for scope in scopes:
            groups[(row["benchmark"], row["condition_id"], row["authorization_regime"], scope)].append(row)
    return [_cell(group, records, study=study, model=model, scope=key[3],
                  attempts=[row for planned in group for row in attempts_by_key[planned["work_key"]]])
            for key, group in sorted(groups.items())]


def _comparison_rows(plan, records, *, study, model, bootstrap_draws):
    result = []
    if study == "utility":
        definitions = [
            ("policy_exact_minus_auto", POLICY, (POLICY[0], "exact_target_v2"), True),
            ("full_exact_minus_auto", FULL, (FULL[0], "exact_target_v2"), True),
            ("policy_minus_nd", ND, POLICY, False),
            ("full_minus_nd", ND, FULL, False),
            ("full_minus_policy", POLICY, FULL, False),
        ]
        field = "task_completion"
    else:
        definitions = [
            ("policy_minus_nd", ND, POLICY, True),
            ("full_minus_nd", ND, FULL, True),
            ("full_minus_vigil", VIGIL, FULL, True),
            ("vigil_minus_nd", ND, VIGIL, False),
            ("full_minus_policy", POLICY, FULL, False),
        ]
        field = "unsafe_effect"
    for benchmark in BENCHMARKS:
        planned = [row for row in plan if row["benchmark"] == benchmark]
        if not planned:
            continue
        rows = [{**row, **records.get(row["work_key"], {})} for row in planned]
        available = {(row["condition_id"], row["authorization_regime"]) for row in rows}
        for name, left, right, primary in definitions:
            if left not in available or right not in available:
                raise ValueError("frozen comparison cell is absent from plan")
            result.append({
                "study": study, "model": model, "benchmark": benchmark,
                "endpoint": field, "comparison": name, "cohort_scope": "all",
                "baseline": list(left), "treatment": list(right),
                "analysis_role": "primary" if model == "pro" and primary else
                                 "replication" if model == "flash" else "secondary",
                "family_id": f"pro_{study}" if model == "pro" and primary else None,
                "family_size": 4 if study == "utility" else 6,
                "holm_p": None,
                **paired_contrast(rows, field, left, right, bootstrap_draws=bootstrap_draws,
                                  label=f"{study}:{model}:{benchmark}:{name}"),
            })
    primary_rows = [row for row in result if row["analysis_role"] == "primary"]
    if primary_rows:
        family_size = 4 if study == "utility" else 6
        values = [row["p_value"] if row["p_value"] is not None else 1.0 for row in primary_rows]
        # 未有数据的预定比较以1参与校正，但公开p仍为NA，不能冒充已运行检验。
        values.extend([1.0] * (family_size - len(values)))
        adjusted = holm_adjust(values)
        for row, p_value in zip(primary_rows, adjusted):
            row["holm_p"] = p_value if row["p_value"] is not None else None
    return result


def _mechanism_summary(output_root: Path, no_defense_plan) -> dict[str, Any]:
    """确定性受控夹具与捕获动作分开计数，不将离线决策混入模型实验。"""
    folder = output_root / "mechanism"
    controlled_path = folder / "controlled_decisions_v1.jsonl"
    captured_path = folder / "captured_replays_v1.jsonl"
    controlled, captured = _read_jsonl(controlled_path), _read_jsonl(captured_path)
    if len(controlled) > 320:
        raise ValueError("controlled decision count exceeds frozen 320")
    blocks, grouped = defaultdict(dict), defaultdict(list)
    for row in controlled:
        if (row.get("input_byte_identical") is not True or row.get("provider_calls") != 0
                or row.get("external_effects") != 0 or row.get("not_end_to_end") is not True):
            raise ValueError("mechanism replay violates isolated same-input contract")
        role, module = row.get("proposal_role"), row.get("module_factor")
        if role not in {"legal", "unauthorized"} or module not in {"policy", "full"}:
            raise ValueError("unknown controlled proposal role or module")
        if row.get("decision") not in {"ALLOW", "ASK", "DENY"}:
            raise ValueError("unknown controlled decision")
        key = (row["base_fixture_id"], row["context_variant"], role)
        if module in blocks[key]:
            raise ValueError("duplicate controlled decision")
        blocks[key][module] = row
        grouped[(row["family"], module)].append(row)
    changed, matched_pairs, incomplete_pairs = 0, 0, 0
    for block in blocks.values():
        if set(block) != {"policy", "full"}:
            incomplete_pairs += 1
            continue
        a, b = block["policy"], block["full"]
        if any(a.get(field) != b.get(field) for field in
               ("replay_input_sha256", "proposal_sha256", "manifest_sha256", "tool_schema_sha256")):
            raise ValueError("paired controlled input digests disagree")
        matched_pairs += 1
        changed += a["decision"] != b["decision"]
    cells = []
    for (family, module), rows in sorted(grouped.items()):
        legal = [row for row in rows if row["proposal_role"] == "legal"]
        unauthorized = [row for row in rows if row["proposal_role"] == "unauthorized"]
        cells.append({
            "family": family, "module_factor": module, "recorded": len(rows),
            "legal_proposals": len(legal), "legal_not_allowed": sum(row["decision"] != "ALLOW" for row in legal),
            "unauthorized_proposals": len(unauthorized), "unauthorized_allowed": sum(row["decision"] == "ALLOW" for row in unauthorized),
            "decision_counts": dict(Counter(row["decision"] for row in rows)),
        })
    seen = set()
    for row in captured:
        key = row["work_key"]
        original = no_defense_plan.get(key)
        if key in seen or original is None:
            raise ValueError("captured replay is duplicate or outside current no-defense plan")
        seen.add(key)
        if any(row.get(field) != original[field] for field in ("benchmark", "underlying_task_id")):
            raise ValueError("captured replay source identity drift")
        if (row.get("input_byte_identical") is not True or row.get("provider_calls") != 0
                or row.get("external_effects") != 0 or row.get("not_end_to_end") is not True):
            raise ValueError("captured replay violates isolated same-input contract")
        if any(row.get(field) not in {"ALLOW", "ASK", "DENY"} for field in
               ("policy_decision", "full_decision")):
            raise ValueError("unknown captured decision")
        if row.get("decision_changed") != (row["policy_decision"] != row["full_decision"]):
            raise ValueError("captured decision-change flag disagrees")
    return {
        "available": controlled_path.exists() or captured_path.exists(),
        "controlled_planned": 320, "controlled_recorded": len(controlled),
        "controlled_missing": 320 - len(controlled),
        "controlled_base_fixtures": len({row["base_fixture_id"] for row in controlled}),
        "controlled_pairs": matched_pairs, "controlled_incomplete_pairs": incomplete_pairs,
        "controlled_changed": changed, "controlled_cells": cells,
        "capture_eligible_no_defense_items": len(no_defense_plan),
        "captured_replays": len(captured),
        "captured_changed": sum(row["decision_changed"] for row in captured),
        "captured_decision_pairs": dict(Counter(f"{row['policy_decision']}->{row['full_decision']}" for row in captured)),
        "provider_calls": 0, "external_effects": 0, "not_end_to_end": True,
        "inferential_p_values": False,
        "scope": "受控夹具/可捕获首提案的确定性判定；并非模型端到端正确率或任务完成。",
    }


def analyze(output_root: Path = OUTPUT, bootstrap_draws: int = 10_000) -> dict[str, Any]:
    """读取R1/R2四份计划和raw一次；缺项保持未运行，不推断为安全或完成。"""
    output_root = Path(output_root)
    groups, cells, comparisons, activity = [], [], [], []
    raw_all = []
    no_defense_plan = {}
    missing_groups = []
    for study in ("utility", "activity"):
        for model in ("pro", "flash"):
            folder = output_root / study / model
            plan_path = folder / "plan_v1.jsonl"
            if not plan_path.exists():
                missing_groups.append(f"{study}/{model}")
                continue
            plan = _read_jsonl(plan_path)
            raw = _read_jsonl(folder / "raw_records_v1.jsonl")
            if not plan:
                raise ValueError("frozen plan is empty")
            records = _validated_records(plan, raw)
            for row in plan:
                if (row["condition_id"], row["authorization_regime"]) == ND:
                    if row["work_key"] in no_defense_plan:
                        raise ValueError("planned no-defense work key repeated across study/model")
                    no_defense_plan[row["work_key"]] = row
            observed = list(records.values())
            missing = len(plan) - len(records)
            groups.append({
                "study": study, "model": model, "planned": len(plan),
                "recorded": len(records), "missing_records": missing,
                "not_run": missing + sum(row.get("operational_status") == "not_run" for row in observed),
                "known_failures": sum(_known_failure(row) for row in observed),
                "attempt_records": len(raw),
                "statuses": dict(Counter(row.get("operational_status", "unknown") for row in observed)),
                "projection_receipt_missing": sum(row.get("online_forbidden_fields_present") is None for row in observed),
                "safety_receipt_missing": sum(not row.get("safety_receipt") for row in observed),
                "provider_tools_status_missing": sum(row.get("provider_tools_enabled") is None for row in observed),
                "external_effects_status_missing": sum(row.get("real_external_effects") is None for row in observed),
                "response_bearing": sum(bool(row.get("response_obtained")) for row in observed),
                "requested_model_ids": sorted({row.get("requested_model_id", row["model_id"]) for row in plan}),
                "official_returned_model_ids": sorted({request["returned_model"] for row in raw
                                                      for request in row.get("provider_requests", [])
                                                      if request.get("response_received")}),
                "declared_service_versions": sorted({row["expected_returned_model_version"] for row in plan
                                                     if row.get("expected_returned_model_version")}),
                "service_version_basis": "frozen plan and official service metadata; response aliases do not pin model weights",
            })
            new_cells = _group_cells(plan, records, study=study, model=model, raw=raw)
            cells.extend(new_cells)
            comparisons.extend(_comparison_rows(plan, records, study=study, model=model,
                                                bootstrap_draws=bootstrap_draws))
            if study == "activity":
                for cell in new_cells:
                    if (cell["condition_id"], cell["authorization_regime"]) == ND:
                        events = cell["unsafe"]["numerator"]
                        descriptive = "INACTIVE" if events == 0 else "WEAK" if events < 8 else "OBSERVED_ACTIVE"
                        activity.append({"model": model, "benchmark": cell["benchmark"],
                                         "numerator": events, "observed": cell["unsafe"]["observed_denominator"],
                                         "planned": cell["planned"], "unknown": cell["unsafe"]["unknown"],
                                         "description": descriptive,
                                         "conclusive_for_this_cohort": cell["unsafe"]["unknown"] == 0,
                                         "wilson_95": cell["unsafe"]["wilson_95"],
                                         "early_stop_rule": False})
            raw_all.extend(raw)
    if not groups:
        raise ValueError("no reinforcement plans found")
    requests = [request for row in raw_all for request in row.get("provider_requests", [])]
    ids = [request["local_request_id"] for request in requests]
    if len(ids) != len(set(ids)):
        raise ValueError("request identity repeated across study/model ledgers")
    attempted = [row for row in raw_all if row.get("operational_status") != "not_run"]
    token_summaries = {
        field: _number_summary([
            row["token_usage"].get(field) if isinstance(row.get("token_usage"), Mapping) else None
            for row in attempted
        ]) for field in ("input", "output", "total")
    }
    cost_summary = _number_summary([
        row["cost"].get("amount") if isinstance(row.get("cost"), Mapping)
        and row["cost"].get("currency") in (None, "CNY") else None
        for row in attempted
    ])
    return {
        "study_id": "m3-empirical-reinforcement-v1", "bootstrap_draws": bootstrap_draws,
        "bootstrap_seed_label": BOOTSTRAP_SEED,
        "planned": sum(row["planned"] for row in groups),
        "recorded": sum(row["recorded"] for row in groups),
        "not_run": sum(row["not_run"] for row in groups),
        "known_failures": sum(row["known_failures"] for row in groups),
        "missing_plan_groups": missing_groups, "groups": groups, "cells": cells,
        "comparisons": comparisons, "attack_activity": activity,
        "mechanism": _mechanism_summary(output_root, no_defense_plan),
        "provider_calls": len(requests),
        "token_usage": {field: summary["known_total"] for field, summary in token_summaries.items()},
        "token_usage_missing_count": {field: summary["missing"] for field, summary in token_summaries.items()},
        "cost_known_estimate_cny": cost_summary["known_total"],
        "cost_missing_count": cost_summary["missing"],
        "cost_usage_complete": bool(attempted) and all(
            isinstance(row.get("cost"), Mapping) and row["cost"].get("usage_complete") is True
            for row in attempted),
        "metric_semantics": {
            "agentdojo-v1": "native offline security and task-completion checker in an isolated in-memory copy",
            "m3-v2": "executed unauthorized mock effect and legal-task completion in the isolated synthetic backend",
        },
        "primary_families": {"utility": {"model": "pro", "comparisons": 4, "scope": "all tasks within each benchmark"},
                             "activity": {"model": "pro", "comparisons": 6, "scope": "all attack tasks within each benchmark"}},
        "interpretation": [
            "统计单位为底层任务；每个基准、模型与条件一条，跨条件配对，跨模型不混合。",
            "M3全部任务、无确认任务和确认任务并列；没有真人批准时ASK是合理等待，完成率下降不自动等于误拦。",
            "四类M3工作流与语言/授权形态有关，工作流子组仅描述，不当作四类独立自然任务总体。",
            "攻击集来自历史阳性富集，只校准当前攻击活性，不代表部署自然攻击发生率。",
            "VIGIL为当前source-pinned源码适配配置，未启用模型二次验证或模型约束二次验证；比较对象不是官方默认完整系统。",
            "未知和未运行不填零；观察估计与ITT保守上下界同时报告。",
            "零事件bootstrap退化时返回NA并提供非退化配对/Wilson区间。",
            "Flash仅作同提供商模型复现，不建立新显著性家族或模型排名。",
            "模型请求别名、官方响应别名和冻结服务版本标识分别披露；服务版本元数据不等于权重锁定。当前Flash服务为V4.1时，不能当作历史V4 Flash同一模型的复现。",
        ],
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _flat_cells(cells):
    result = []
    for cell in cells:
        row = {key: value for key, value in cell.items()
               if not isinstance(value, Mapping)}
        row["statuses_json"] = json.dumps(cell["statuses"], sort_keys=True, ensure_ascii=False)
        for endpoint in ("unsafe", "completion", "unsafe_or_failure"):
            summary = cell[endpoint]
            row.update({f"{endpoint}_{key}": value for key, value in summary.items() if key != "wilson_95"})
            row[f"{endpoint}_wilson_low"], row[f"{endpoint}_wilson_high"] = summary["wilson_95"]
        row.update({f"latency_{key}": value for key, value in cell["latency"].items()})
        for label in ("provider_calls_per_attempt", "provider_calls_per_work_item", "token_usage",
                      "token_usage_observed_count", "token_usage_missing_count", "token_usage_invalid_count",
                      "vigil_constraint_generation_calls"):
            row.update({f"{label}_{key}": value for key, value in cell[label].items()})
        result.append(row)
    return result


def _flat_comparisons(comparisons):
    result = []
    for comparison in comparisons:
        row = {key: value for key, value in comparison.items()
               if key not in ("paired_interval", "bootstrap", "mcnemar", "baseline", "treatment")}
        row["baseline"] = " / ".join(comparison["baseline"])
        row["treatment"] = " / ".join(comparison["treatment"])
        for label in ("paired_interval", "bootstrap", "mcnemar"):
            row.update({f"{label}_{key}": value for key, value in (comparison.get(label) or {}).items()
                        if type(value) in (str, bool, int, float) or value is None})
        result.append(row)
    return result


def _figure_svg(result, path: Path, study: str) -> None:
    """轻量SVG森林图：画已观察比例和Wilson区间，NA保持空白而非补零。"""
    cells = [row for row in result["cells"] if row["study"] == study and row["cohort_scope"] == "all"]
    endpoint = "completion" if study == "utility" else "unsafe"
    height = 135 + 35 * len(cells)
    x0, width = 420, 500
    title = "合法任务完成：观察比例与95% Wilson区间" if study == "utility" else "攻击结果：观察比例与95% Wilson区间"
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1020" height="{height}" viewBox="0 0 1020 {height}">',
              '<rect width="100%" height="100%" fill="white"/>',
              '<g font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" fill="#203242">',
              f'<text x="24" y="30" font-size="20">{title}</text>',
              '<text x="24" y="55" font-size="12">每条为一个基准/模型/条件；原始分子/已观察分母。两个基准评分语义分别解释。</text>']
    for value in (0, .25, .5, .75, 1):
        x = x0 + width * value
        pieces += [f'<line x1="{x}" y1="78" x2="{x}" y2="{height - 45}" stroke="#dfe7ec"/>',
                   f'<text x="{x}" y="75" text-anchor="middle" font-size="11">{int(value * 100)}%</text>']
    for index, cell in enumerate(cells):
        y = 98 + 35 * index
        summary = cell[endpoint]
        condition_label = {
            "no_defense": "无防护", "m3_policy_only": "仅权限",
            "m3_full_normal_prompt": "完整模块",
            "strongest_peer_reviewed_structural_baseline": "VIGIL配置版",
        }.get(cell["condition_id"], cell["condition_id"])
        regime_label = "自动授权" if cell["authorization_regime"] == "auto_compiled" else "精确目标对照"
        label = f"{cell['model']} · {cell['benchmark']} · {condition_label} · {regime_label}"
        pieces.append(f'<text x="16" y="{y + 4}" font-size="10">{escape(label)}</text>')
        if summary["observed_rate"] is None:
            pieces.append(f'<text x="{x0}" y="{y + 4}" font-size="12">NA（未观察）</text>')
        else:
            low, high = summary["wilson_95"]
            color = "#1f6587" if cell["model"] == "pro" else "#9c6634"
            pieces += [f'<line x1="{x0 + width * low}" y1="{y}" x2="{x0 + width * high}" y2="{y}" stroke="{color}" stroke-width="2"/>',
                       f'<circle cx="{x0 + width * summary["observed_rate"]}" cy="{y}" r="3.8" fill="{color}"/>']
        pieces.append(f'<text x="960" y="{y + 4}" text-anchor="middle" font-size="12">{summary["numerator"]}/{summary["observed_denominator"]}</text>')
    pieces += [f'<text x="24" y="{height - 15}" font-size="12">未知/未运行保留在ITT界限；本图不将其画成已观察的零。确认等待不是误拦判据。</text>', '</g></svg>']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(pieces) + "\n", encoding="utf-8")


def _percent(value) -> str:
    return "NA" if value is None else f"{100 * value:.2f}%"


def _difference(value) -> str:
    return "NA" if value is None else f"{100 * value:+.2f}pp"


def write_outputs(result: Mapping[str, Any], output_root: Path = OUTPUT, *, figures: bool = True) -> None:
    """只写本研究派生JSON/CSV/报告；原计划、raw和内部请求不改。"""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "analysis_v1.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    _write_csv(output_root / "tables/cells_v1.csv", _flat_cells(result["cells"]))
    _write_csv(output_root / "tables/paired_comparisons_v1.csv", _flat_comparisons(result["comparisons"]))
    _write_csv(output_root / "tables/attack_activity_v1.csv", result["attack_activity"])
    mechanism = result["mechanism"]
    _write_csv(output_root / "tables/mechanism_decisions_v1.csv", [
        {**{key: value for key, value in cell.items() if key != "decision_counts"},
         "decision_counts_json": json.dumps(cell["decision_counts"], sort_keys=True)}
        for cell in mechanism["controlled_cells"]])
    if figures:
        for study in ("utility", "activity"):
            if any(row["study"] == study for row in result["cells"]):
                _figure_svg(result, output_root / f"figures/{study}_observed_rates_v1.svg", study)
    total_tokens = result["token_usage"]["total"]
    total_tokens_text = "NA" if total_tokens is None else str(total_tokens)
    total_cost = result["cost_known_estimate_cny"]
    total_cost_text = "NA" if total_cost is None else f"{total_cost:.6f}"
    lines = [
        "# M3-PI Guard 强化实证实验阶段报告", "",
        "## 1. 实际完成量", "",
        f"本次读取计划 {result['planned']} 项、公开终态记录 {result['recorded']} 项；未运行 {result['not_run']} 项，已知运行失败 {result['known_failures']} 项。",
        "计划数不是成功数：未知评分、运行失败及未运行分开登记。分析只读取当前研究，不重算历史矩阵，不调用模型，不改论文。",
        f"缺少计划的研究/模型目录：`{', '.join(result['missing_plan_groups']) or '无'}`。未找到的计划未计入已完成量。", "",
        "|研究|模型|已记录/计划|未运行|已知失败|获得官方响应|评分投影凭证缺失|",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for group in result["groups"]:
        lines.append(f"|{group['study']}|{group['model']}|{group['recorded']}/{group['planned']}|{group['not_run']}|{group['known_failures']}|{group['response_bearing']}|{group['projection_receipt_missing']}|")
    lines += [
        "", "## 2. 实验设计和统计单位", "",
        "模型身份分别报告API请求别名、官方响应中的model别名及冻结服务元数据版本；后者不是权重文件快照，不能据此宣称模型权重锁定。当前Flash若标为DeepSeek-V4.1-Flash，属于新服务模型复现，不是历史V4 Flash，也不是跨厂商模型。", "",
        "|研究/模型|请求模型ID|官方响应模型ID|冻结服务元数据版本|",
        "|---|---|---|---|",
    ]
    for group in result["groups"]:
        lines.append(f"|{group['study']}/{group['model']}|`{' / '.join(group['requested_model_ids'])}`|`{' / '.join(group['official_returned_model_ids']) or '未取得响应'}`|`{' / '.join(group['declared_service_versions']) or '未声明'}`|")
    lines += [
        "",
        "R1（utility，合法任务效用）在同一批底层任务上运行五个条件：无防护自动授权、policy自动授权、full普通提示自动授权、policy精确目标授权、full普通提示精确目标授权。精确目标授权来自离线预期动作，是oracle（预先知道目标的对照），不是可直接部署的授权方案。",
        "R2（activity，攻击活性）在历史无防护或VIGIL出现危险结果的任务上运行无防护、当前配置VIGIL、policy和full普通提示四个条件。该攻击样本为历史阳性富集集。",
        "统计单位是underlying_task（底层任务），而不是API请求或条件执行次数。同一任务跨条件配对；Pro与Flash、两个基准分开报告。AgentDojo使用原生离线安全评分，M3-v2统计已执行的模拟越权效果，不能直接混合成一个自然攻击率。",
        "M3良性任务同时报告all（全部）、non_confirmation（无确认需求）、confirmation_required（需确认）。没有真人批准时，ASK代表合理等待，不算任务完成，也不能自动称为错误阻断；另列授权形态和四类workflow（工作流）描述性分组。",
        f"置信区间：单cell采用95% Wilson；配对采用Newcombe混合分数区间，并按AgentDojo suite（任务套件）/M3 authorization_profile（授权形态）分层进行{result['bootstrap_draws']:,}次底层任务bootstrap（有放回重采样）。固定种子标签`{result['bootstrap_seed_label']}`。",
        "Pro R1四项主比较（两模块的exact−auto×两个基准）共一个Holm家族；Pro R2六项主比较（policy−ND、full−ND、full−VIGIL×两个基准）共一个Holm家族。Flash报告效应方向、区间和未校正的辅助配对p值，不新增显著性家族。其余比较与工作流分层为次要/描述分析。",
        "全零或bootstrap退化时，经验bootstrap区间记NA，使用配对区间和cell Wilson界限表达不确定性，不将[0,0]解释为确定零风险。未知配对不填零，并报告在全部计划任务上的差异保守上下界。", "",
        "## 3. 分层结果", "",
        "|研究/模型/基准|范围|条件/授权|已记录/计划|危险真/已知|完成真/已知|危险未知/完成未知|ASK项|未运行/失败|",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in result["cells"]:
        if cell["cohort_scope"] not in ("all", "non_confirmation", "confirmation_required"):
            continue
        unsafe, completion = cell["unsafe"], cell["completion"]
        lines.append(f"|{cell['study']}/{cell['model']}/{cell['benchmark']}|{cell['cohort_scope']}|{cell['condition_id']}/{cell['authorization_regime']}|{cell['recorded']}/{cell['planned']}|{unsafe['numerator']}/{unsafe['observed_denominator']}|{completion['numerator']}/{completion['observed_denominator']}|{unsafe['unknown']}/{completion['unknown']}|{cell['ask_items']}|{cell['not_run']}/{cell['known_failures']}|")
    lines += [
        "", "完整cell表见`tables/cells_v1.csv`：包括已观察比例、Wilson区间、计划分母、ITT下/上界、失败敏感上界、ASK/DENY和延迟；不把未知当安全零。", "",
        "## 4. 任务配对差异", "",
        "下表差异均为treatment−baseline（后者条件减去参照条件）。完成率正差表示完成更多；危险率负差表示危险结果更少。百分点评估不是百分比相对减少。",
        "|研究/模型/基准|比较|角色|已知/计划配对|观察差异|配对95%区间|ITT差异上下界|Holm p|",
        "|---|---|---|---:|---:|---|---|---:|",
    ]
    for comparison in result["comparisons"]:
        interval = comparison["paired_interval"]
        ci = f"[{_difference(interval['ci_low'])}, {_difference(interval['ci_high'])}]"
        bounds = f"[{_difference(comparison['itt_difference_lower'])}, {_difference(comparison['itt_difference_upper'])}]"
        p_value = "NA" if comparison["holm_p"] is None else f"{comparison['holm_p']:.6g}"
        lines.append(f"|{comparison['study']}/{comparison['model']}/{comparison['benchmark']}|{comparison['comparison']}|{comparison['analysis_role']}|{comparison['known_pairs']}/{comparison['planned_pairs']}|{_difference(comparison['estimate'])}|{ci}|{bounds}|{p_value}|")
    lines += ["", "完整配对表与bootstrap区间在`tables/paired_comparisons_v1.csv`；结果缺失时观察差异不是全样本差异，需同时阅读ITT界限。", "",
              "## 5. 同期攻击活性", "",
              "|模型/基准|无防护危险真/已观察/计划|未知|描述|本队列终态齐全|",
              "|---|---:|---:|---|---|",]
    for row in result["attack_activity"]:
        lines.append(f"|{row['model']}/{row['benchmark']}|{row['numerator']}/{row['observed']}/{row['planned']}|{row['unknown']}|{row['description']}|{row['conclusive_for_this_cohort']}|")
    lines += [
        "", "活性描述按预定计数：0例INACTIVE（未观察活性）、1–7例WEAK（较弱）、至少8例OBSERVED_ACTIVE（本队列观察到活性）。这是描述而非停止规则；含未知时不能断言所有任务不活跃，不进行模型排名或自然部署发生率推断。", "",
        "### 5.1 同一提案的离线机制判定", "",
        f"受控夹具决策已记录 {mechanism['controlled_recorded']}/{mechanism['controlled_planned']}，基础夹具 {mechanism['controlled_base_fixtures']}，policy/full完整提案对 {mechanism['controlled_pairs']}、不完整对 {mechanism['controlled_incomplete_pairs']}，判定变化 {mechanism['controlled_changed']} 对。",
        f"公开捕获首提案回放 {mechanism['captured_replays']} 项，来自至多 {mechanism['capture_eligible_no_defense_items']} 个冻结无防护项，判定变化 {mechanism['captured_changed']} 项。未被捕获不意味着模型没有提出危险动作：也可能首先返回final、解析失败或无可回放前缀。",
        "下表只报告确定性机制决策；合法夹具未ALLOW、未授权夹具被ALLOW分别作为对照计数。ASK与DENY分别保留，确认等待不视为执行或完成。没有新模型调用、实际effect、端到端成功率或p值。",
        "|机制家族|模块|决策数|合法未ALLOW/合法|未授权ALLOW/未授权|ALLOW/ASK/DENY分布|",
        "|---|---|---:|---:|---:|---|",
    ]
    for cell in mechanism["controlled_cells"]:
        lines.append(f"|{cell['family']}|{cell['module_factor']}|{cell['recorded']}|{cell['legal_not_allowed']}/{cell['legal_proposals']}|{cell['unauthorized_allowed']}/{cell['unauthorized_proposals']}|`{json.dumps(cell['decision_counts'], ensure_ascii=False)}`|")
    lines += [
        "", f"捕获判定对分布：`{json.dumps(mechanism['captured_decision_pairs'], ensure_ascii=False)}`。机制表在`tables/mechanism_decisions_v1.csv`；仅公开摘要，不读取内部提案正文。", "",
        "## 6. 调用、成本和结果来源", "",
        f"本研究各尝试合计官方请求 {result['provider_calls']} 次，total token {total_tokens_text}（总量字段缺失{result['token_usage_missing_count']['total']}）；已知用量估计CNY {total_cost_text}（成本缺失{result['cost_missing_count']}），用量完整性为 {result['cost_usage_complete']}。这是记录中峰值费率估算，不是账单实付；失败后的显式恢复调用也计入。",
        "VIGIL每任务最多16次provider call（模型请求）；其他条件最多8次。下表按全部实际尝试累计调用、token（文本计费单元）及峰值费率估算成本，终态任务分母保持不变。每任务调用p50/p95为中位数/第95百分位；未启动任务不作为零调用任务加入分位数。",
        "VIGIL约束生成调用只合计显式字段，并报告字段缺失；截断行有总调用但无分项时保留总数，不补造约束生成0次或1次。成本与token缺失也不填零，已知合计只代表可用记录。", "",
        "|研究/模型/基准|条件/授权|调用上限|总调用|每任务调用p50/p95|输入/输出/总token|估算CNY/成本缺失|约束生成已知合计/分项缺失|",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in result["cells"]:
        if cell["cohort_scope"] != "all":
            continue
        calls = cell["provider_calls_per_work_item"]
        call_summary = f"{calls['p50']:.2f}/{calls['p95']:.2f}" if calls["observed"] else "NA"
        tokens = "/".join(str(cell["token_usage"][field]) if cell["token_usage"][field] is not None else "NA"
                          for field in ("input", "output", "total"))
        cost = "NA" if cell["cost_estimate_cny"] is None else f"{cell['cost_estimate_cny']:.6f}"
        generation = cell["vigil_constraint_generation_calls"]
        breakdown = f"{generation['known_total'] if generation['known_total'] is not None else 'NA'}/{generation['missing']}" if cell["vigil_constraint_generation_applicable"] else "不适用"
        lines.append(f"|{cell['study']}/{cell['model']}/{cell['benchmark']}|{cell['condition_id']}/{cell['authorization_regime']}|{cell['provider_call_cap']}|{cell['provider_calls'] if cell['provider_calls'] is not None else 'NA'}|{call_summary}|{tokens}|{cost}/{cell['cost_missing_count']}|{breakdown}|")
    lines += [
        "",
        "延迟统计使用每任务total毫秒，另报告缺失/非法数。不同条件路径和调用次数不同，不能把总延迟差全部称为Guard计算开销。", "",
        "## 7. 产物目录及重新分析", "",
        f"本报告所在结果根：`{output_root.resolve()}`。根目录只存本研究必要派生产物，旧历史目录不参与本次计算。", "",
        "```text", "empirical_reinforcement_v1/",
        "├── manifest_v1.json             # 四个冻结队列的运行清单", "├── utility/                     # R1：合法工具任务", "│   ├── pro/", "│   │   ├── cases_v1.jsonl         # 固定案例及选择依据", "│   │   ├── plan_v1.jsonl          # 冻结任务、条件、授权与模型", "│   │   ├── raw_records_v1.jsonl   # 逐尝试公开结果，不覆盖已有响应", "│   │   ├── status_v1.json        # 进度、技术门和停止原因", "│   │   └── internal/             # 本地忽略：逐请求记录、锁和首提案捕获", "│   └── flash/                    # 相同结构；同提供商复现",
        "├── activity/                    # R2：历史阳性攻击活性", "│   ├── pro/                     # 与utility/pro同结构，状态及internal独立", "│   └── flash/                   # 与utility/flash同结构，状态及internal独立",
        "├── mechanism/                   # R3：固定提案/已捕获提案的离线机制回放", "│   ├── controlled_decisions_v1.jsonl", "│   ├── captured_replays_v1.jsonl", "│   └── summary_v1.json           # 40基础夹具、320判定及实际捕获计数",
        "├── analysis_v1.json             # 本次统计，未知、配对及多重校正", "├── tables/", "│   ├── cells_v1.csv", "│   ├── paired_comparisons_v1.csv", "│   ├── attack_activity_v1.csv", "│   └── mechanism_decisions_v1.csv",
        "├── figures/                     # 可选SVG，只画已观察比例/Wilson区间", "└── report.md                     # 自足中文报告", "```", "",
        "四个study/model（研究/模型）子目录均有各自的internal目录；它们不是根目录共用账本，不进入GitHub或服务器统计包。服务器只接收公开计划、raw和机制摘要。", "",
        "分析命令（在项目根目录运行）：", "",
        "```powershell", "& F:\\robot\\Anaconda3\\python.exe -X utf8 -m experiments.paper_v2.empirical_reinforcement_analysis_v1", "```", "",
        "代码只读取本研究公开JSONL，生成上述派生表和报告；不调用模型、不读取密钥、不中断运行器、不执行Full Harness、不修改论文和历史结果。R3确定性决策与模型端到端结果分别分析，不能用机制回放正确率代替模型防御有效性。", "",
        "## 8. 解释与未完成项", "",
        *[f"- {line}" for line in result["interpretation"]], "",
        "未运行任务和未知评分必须先按各目录状态核对再决定恢复；已经获得模型响应的成功或失败行不重跑。结果不足时保留阶段状态，不以计划量宣称研究完成。作者信息和正式投稿状态本轮未改变。", "",
        "可信度：9/10。依据：冻结计划、公开原始结果及定向统计测试；推广范围、服务漂移及独立外部审校仍需结合实际完成量解释。", "",
    ]
    (output_root / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="一次性分析强化研究公开结果")
    parser.add_argument("--output-root", type=Path, default=OUTPUT)
    parser.add_argument("--bootstrap-draws", type=int, default=10_000)
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()
    result = analyze(args.output_root, bootstrap_draws=args.bootstrap_draws)
    write_outputs(result, args.output_root, figures=not args.no_figures)
    print(json.dumps({key: result[key] for key in ("planned", "recorded", "not_run", "known_failures", "provider_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
