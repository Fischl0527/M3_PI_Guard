"""全新的同时期 ND/policy/full/VIGIL 综合校准（绝不混入旧数据）。

严格控制模型端点版本与测试提示词，消除时间漂移干扰。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import threading
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import partial
from pathlib import Path

from experiments.paper_v2.claude_revision_v1 import gate, load_key, remaining_calls
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.correctness_plan_v1 import ROOT, read_jsonl, round_robin, underlying_task
from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer, append_row, now
from experiments.paper_v2.correctness_runner_v1 import critical_error, execute_one, latest_records, model_lock, pending_rows
from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime, hydrate
from experiments.paper_v2.vigil_live_dependency import VigilLiveDependencyError, VigilOfficialConstraintFactory

STUDY = "m3-research-followup-calibration-20261006-v1"
OUTPUT = ROOT / "outputs/experiments/research_followup_20261006_v1/calibration"
CORE = ("no_defense", "m3_policy_only", "m3_full_normal_prompt")
VIGIL = "strongest_peer_reviewed_structural_baseline"
CONDITIONS = (*CORE, VIGIL)
SEED = "m3-followup-calibration-20261006-v1"


class QuietVigilConstraintFactory(VigilOfficialConstraintFactory):
    """在不替换进程 stdout 的情况下抑制包含正文的上游日志。"""

    def __call__(self, *args, **kwargs):
        owner = threading.get_ident()

        class ThisCallFilter(logging.Filter):
            def filter(self, record):
                return record.thread != owner

        logger = logging.getLogger("vigil.constraint_generator")
        silence = ThisCallFilter()
        logger.addFilter(silence)
        try:
            return super().__call__(*args, **kwargs)
        finally:
            logger.removeFilter(silence)


class CalibrationRuntime(CorrectnessRuntime):
    def execute(self, row, client):
        try:
            return {**super().execute(row, client), "runner_revision": "calibration_telemetry_v1.1"}
        except VigilLiveDependencyError:
            # A validated response explicitly reporting length truncation is a
            # response-bearing model-output failure, not a repeated code fault.
            if row["condition_id"] != VIGIL or not client.requests or client.requests[-1].get("finish_reason") != "length":
                raise
            if any(not r.get("response_received") or r.get("returned_model") != row["model_id"] for r in client.requests):
                raise
            _, digest = hydrate(row, compiler_revision="corrected_v2")
            return {"unsafe_effect": None, "unsafe_effect_observed": False, "task_completion": None, "task_completion_observed": False,
                    "operational_status": "parse_failure", "failure_stage": "vigil_constraint_generation", "failure_class": "constraint_output_truncated",
                    "evaluation_details": {"unknown_reasons": ["constraint_generation_failed_before_simulated_environment_execution"]},
                    "events": [{"step": 1, "tool": None, "parse_ok": False, "reason_code": "constraint_output_truncated", "execution_attempted": False, "simulated_action_executed": False}],
                    "ask_count": 0, "deny_count": 0, "latency_ms": None,
                    "online_forbidden_fields_present": digest["forbidden_fields_present"], "online_visible_field_digest": digest,
                    "provider_tools_enabled": False, "real_external_effects": 0, "runner_revision": "calibration_telemetry_v1.1"}


def select_cases():
    source = read_jsonl(ROOT / "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl")
    if len(source) != 180:
        raise ValueError("original cohort shape drift")
    groups = []
    for benchmark in ("agentdojo-v1", "m3-v2"):
        for category in ("attack", "benign_tool"):
            pool = [r for r in source if r["benchmark"] == benchmark and r["evaluation_case_type"] == category]
            # Stable coverage round-robin; seed resolves multiple attack instances.
            ordered = sorted(pool, key=lambda r: hashlib.sha256(f"{SEED}|{r['case_id']}".encode()).hexdigest())
            per_task = {}
            for row in ordered:
                per_task.setdefault(underlying_task(row), row)
            chosen = round_robin(list(per_task.values()))[:30] if category == "attack" else sorted(pool, key=lambda r: r["case_id"])
            if len(chosen) != 30:
                raise ValueError("need thirty cases per benchmark/category")
            groups.append(chosen)
    cases = []
    while any(groups):
        for group in groups:
            if group:
                cases.append(copy.deepcopy(group.pop(0)))
    return cases


def build_plan():
    identity = sha256_canonical_json({"study": STUDY, "conditions": CONDITIONS, "runtime": "corrected_v2", "prompt": "normal", "tokens": 512})
    rows = []
    for rank, case in enumerate(select_cases()):
        rotation = rank % len(CONDITIONS)
        order = CONDITIONS[rotation:] + CONDITIONS[:rotation]
        for position, condition in enumerate(order):
            rows.append({
                **case, "schema_version": "m3-followup-calibration-plan-1.0", "study_id": STUDY,
                "work_key": sha256_canonical_json([STUDY, case["case_id"], condition]),
                "run_id": STUDY, "execution_identity": identity, "sequence": len(rows) + 1,
                "underlying_task_id": underlying_task(case), "source_record_sha256": case["source_reference"]["sha256"],
                "condition_id": condition, "condition_order_position": position, "case_rank": rank,
                "provider_id": "deepseek", "model_group": "deepseek_pro", "model_id": "deepseek-v4-pro", "model_role": "primary",
                "authorization_regime": "auto_compiled", "prompt_factor": "normal",
                "module_factor": "none" if condition == "no_defense" else "policy" if condition == "m3_policy_only" else "full" if condition == "m3_full_normal_prompt" else "vigil_configured_adapter",
                "runtime_version": "corrected_v2", "runtime_revision": "corrected_v2", "compiler_revision": "corrected_v2",
                "max_provider_calls": 16 if condition == VIGIL else 8, "max_tokens": 512, "temperature": 0, "timeout_seconds": 180,
                "formal_prefix": rank < 4, "sample_role": "fixed_attack_calibration" if case["evaluation_case_type"] == "attack" else "fixed_benign_calibration",
                "selection_uses_new_outcomes": False, "same_physical_safety_boundary": True,
                "vigil_configuration": "pinned_hybrid_deterministic_auditor_llm_constraint_generation_no_llm_verification" if condition == VIGIL else None,
            })
    if len(rows) != 480 or len({r["work_key"] for r in rows}) != 480:
        raise ValueError("calibration shape drift")
    return rows


def write_plan(output: Path = OUTPUT):
    path = output / "plan.jsonl"
    rows = build_plan()
    if path.exists():
        if read_jsonl(path) != rows:
            raise ValueError("existing calibration plan differs; cannot overwrite")
    else:
        for row in rows:
            append_row(path, row)
    return path


def calibration_gate(rows):
    core = [r for r in rows if r["condition_id"] in CORE]
    result = gate(core)
    baseline = [r for r in rows if r["condition_id"] == VIGIL]
    reasons = list(result["reasons"])
    if len(baseline) != 4 or sum(any(e.get("parse_ok") is True for e in r.get("events", [])) for r in baseline) < 3:
        reasons.append("vigil_prefix_incomplete_or_less_than_3_parseable")
    for row in baseline:
        if critical_error(row) or row.get("operational_status") == "runner_failure" or row.get("online_forbidden_fields_present") is None:
            reasons.append("vigil_runtime_identity_or_projection_error")
        for request in row.get("provider_requests", []):
            if request.get("response_received") and not all(request.get(k) for k in ("local_request_id", "payload_sha256", "provider_response_id", "returned_model")):
                reasons.append("incomplete_vigil_response_identity")
    return {"passed": not reasons, "core": result, "vigil_rows": len(baseline), "reasons": sorted(set(reasons)), "outcome_blind": True}


def run(*, canary_only=False, retry_key=None, output=OUTPUT):
    path = write_plan(output)
    plan = read_jsonl(path)
    raw_path = output / "raw_records.jsonl"
    with model_lock(output / "internal/runner.lock"):
        history = latest_records(read_jsonl(raw_path))
        if set(history) - {r["work_key"] for r in plan} or any(critical_error(r) for r in history.values()):
            raise ValueError("prior results outside plan or critical safety error")
        pending = pending_rows(plan, history, retry_key)
        if canary_only:
            pending = [(r, a) for r, a in pending if r["formal_prefix"]]
        elif not retry_key and not calibration_gate([r for r in history.values() if r["formal_prefix"]])["passed"]:
            raise ValueError("formal prefix must pass before extension")
        runtime = CalibrationRuntime(plan_path=path, execution_identity=plan[0]["execution_identity"], compiler_revision="corrected_v2", runtime_revision="corrected_v2", vigil_factory=QuietVigilConstraintFactory())
        stop = threading.Event()
        pacer = RequestPacer(0, stop)
        key = load_key()
        reason, errors = None, {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            iterator, active = iter(pending), {}
            while True:
                while not stop.is_set() and len(active) < 2:
                    item = next(iterator, None)
                    if item is None:
                        break
                    row, attempt = item
                    factory = partial(DevelopmentRequestClient, max_provider_calls=remaining_calls(row, history, attempt), call_budget_ceiling=row["max_provider_calls"])
                    active[pool.submit(execute_one, row, attempt, runtime=runtime, api_key=key, pacer=pacer, output=output, client_factory=factory)] = row
                if not active:
                    break
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    row = active.pop(future)
                    record = future.result()
                    append_row(raw_path, record)
                    history[row["work_key"]] = record
                    if critical_error(record):
                        reason = critical_error(record)
                    if any(r.get("http_status") == 429 for r in record["provider_requests"]):
                        reason = "provider_429"
                    if record["operational_status"] in {"runner_failure", "provider_failure"}:
                        failure = str(record.get("failure_class"))
                        errors.setdefault(failure, set()).add(record["case_id"])
                        if len(errors[failure]) >= 2:
                            reason = "repeated_system_error:" + failure
                    if reason:
                        stop.set()
                    print(json.dumps({"recorded": len(history), "planned": len(plan), "status": record["operational_status"], "stop": reason}), flush=True)
        result = {"planned": len(plan), "recorded": len(history), "pending": len(plan) - len(history), "gate": calibration_gate([r for r in history.values() if r["formal_prefix"]]), "stop_reason": reason, "statuses": dict(Counter(r["operational_status"] for r in history.values())), "updated_at": now()}
        (output / "status.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--write-plan", action="store_true")
    parser.add_argument("--canary-only", action="store_true")
    parser.add_argument("--resume-pending-only", action="store_true")
    parser.add_argument("--retry-failed-work-key")
    args = parser.parse_args()
    if args.write_plan:
        print(json.dumps({"plan": str(write_plan()), "rows": len(build_plan())}))
    elif args.canary_only or args.resume_pending_only or args.retry_failed_work_key:
        result = run(canary_only=args.canary_only, retry_key=args.retry_failed_work_key)
        print(json.dumps(result, ensure_ascii=False))
        if result["stop_reason"] or args.canary_only and not result["gate"]["passed"]:
            raise SystemExit(2)
    else:
        parser.error("explicit plan/canary/pending/recovery mode required")


if __name__ == "__main__":
    main()
