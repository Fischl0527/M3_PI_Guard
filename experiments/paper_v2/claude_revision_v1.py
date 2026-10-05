"""Fresh, bounded post-repair authorization study; never replays old runs."""

from __future__ import annotations

import argparse
import copy
import json
import threading
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import partial
from pathlib import Path
from typing import Any

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.correctness_followup_v1 import build_model_plan, run_live_probe
from experiments.paper_v2.correctness_plan_v1 import ROOT, read_jsonl, underlying_task
from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer, append_row, now
from experiments.paper_v2.correctness_runner_v1 import credential, critical_error, execute_one, latest_records, model_lock, pending_rows
from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime
from m3_core.project_config import parse_env_file, resolve_config_path

STUDY = "m3-claude-revision-v1"
OUTPUT = ROOT / "outputs/experiments/claude_revision_v1"
PLAN = OUTPUT / "study_plan.jsonl"
CELLS = (
    ("m3_policy_only", "auto_compiled"),
    ("m3_policy_only", "exact_target_v2"),
    ("m3_full_normal_prompt", "auto_compiled"),
    ("m3_full_normal_prompt", "exact_target_v2"),
)


def build_plan() -> list[dict[str, Any]]:
    cases = read_jsonl(ROOT / "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl")
    if len(cases) != 180 or sum(bool(r["regime_subset"]) for r in cases) != 60:
        raise ValueError("frozen cohort shape drift")
    first = [next(r for r in cases if r["benchmark"] == b and r["evaluation_case_type"] == t)
             for b, t in (("agentdojo-v1", "attack"), ("m3-v2", "attack"), ("agentdojo-v1", "benign_tool"))]
    selected = first + [r for r in cases if r not in first]
    identity = sha256_canonical_json({"study": STUDY, "compiler": "corrected_v2", "runtime": "corrected_v2", "prompt": "normal"})
    rows = []
    for rank, case in enumerate(selected):
        cells = list(CELLS)
        if case["regime_subset"]:
            cells += [("m3_full_normal_prompt", r) for r in ("broad", "underspecified", "conflicting")]
        for condition, regime in cells:
            rows.append({
                **copy.deepcopy(case), "study_id": STUDY, "study_part": "authorization",
                "work_key": sha256_canonical_json([STUDY, case["case_id"], condition, regime]),
                "execution_identity": identity, "run_id": STUDY,
                "underlying_task_id": underlying_task(case),
                "source_record_sha256": case["source_reference"]["sha256"],
                "provider_id": "deepseek", "model_group": "deepseek_pro", "model_id": "deepseek-v4-pro", "model_role": "primary",
                "condition_id": condition, "authorization_regime": regime,
                "prompt_factor": "normal", "module_factor": "policy" if condition == "m3_policy_only" else "full",
                "compiler_revision": "corrected_v2", "runtime_revision": "corrected_v2", "runtime_version": "corrected_v2",
                "max_provider_calls": 8, "max_tokens": 512, "temperature": 0, "timeout_seconds": 180,
                "formal_prefix": rank < 3 and (condition, regime) in CELLS,
                "sample_role": "fixed_lean_cohort", "oracle_control": regime == "exact_target_v2",
            })
    # All twelve formal prefix rows precede the extension, without duplication.
    rows.sort(key=lambda r: not r["formal_prefix"])
    for old in build_model_plan():
        rows.append({
            **old, "study_id": STUDY, "study_part": "synthetic", "benchmark": "synthetic-m3",
            "case_id": "synthetic:" + old["scenario_id"], "underlying_task_id": old["scenario_id"],
            "work_key": sha256_canonical_json([STUDY, "synthetic", old["work_key"]]),
            "execution_identity": identity, "run_id": STUDY,
            "provider_id": "deepseek", "model_role": "primary" if old["model_group"] == "deepseek_pro" else "second",
            "condition_id": "m3_full_normal_prompt" if old["condition_id"] == "m3_full" else old["condition_id"],
            "compiler_revision": "trusted_synthetic_acl", "runtime_revision": "corrected_v2", "runtime_version": "corrected_v2",
            "authorization_regime": "auto_compiled", "max_tokens": 512, "temperature": 0, "timeout_seconds": 180,
            "formal_prefix": False, "evaluation_case_type": "synthetic_control", "sample_role": "classification_control",
        })
    if len(rows) != 916 or len({r["work_key"] for r in rows}) != 916:
        raise ValueError("study plan count/uniqueness drift")
    return rows


def write_plan(output: Path = OUTPUT) -> Path:
    path = output / "study_plan.jsonl"
    rows = build_plan()
    if path.exists():
        if read_jsonl(path) != rows:
            raise ValueError("existing study plan differs; cannot overwrite")
    else:
        output.mkdir(parents=True, exist_ok=True)
        for row in rows:
            append_row(path, row)
    return path


class RevisionRuntime:
    def __init__(self, plan_path: Path, identity: str):
        self.runtimes = {regime: CorrectnessRuntime(
            plan_path=plan_path, execution_identity=identity, compiler_revision="corrected_v2",
            runtime_revision="corrected_v2", authorization_regime=regime,
        ) for regime in {r[1] for r in CELLS} | {"broad", "underspecified", "conflicting"}}

    def execute(self, row, client):
        return self.runtimes[row["authorization_regime"]].execute(row, client)


class SyntheticRuntime:
    def execute(self, row, client):
        old = next(r for r in build_model_plan() if r["scenario_id"] == row["scenario_id"] and r["model_group"] == row["model_group"]
                   and r["module_factor"] == row["module_factor"])
        raw = run_live_probe(old, client, runtime_revision="corrected_v2")
        return {
            **raw, "work_key": row["work_key"], "condition_id": row["condition_id"],
            "unsafe_effect": raw["simulated_unsafe_effect"],
            "evaluation_details": {k: raw[k] for k in ("simulated_unsafe_effect", "executed_send_count", "boundary_rejection_count", "effect_semantics")},
            "ask_count": sum(r["guard_decision"] == "ASK" for r in raw["events"]),
            "deny_count": sum(r["guard_decision"] == "DENY" for r in raw["events"]),
            "online_forbidden_fields_present": [],
            "provider_tools_enabled": False, "real_external_effects": 0,
        }


def gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed = sum(any(e.get("parse_ok") is True for e in r.get("events", [])) for r in rows)
    reasons = []
    if len(rows) != 12:
        reasons.append("prefix_incomplete")
    if parsed < 9:
        reasons.append("less_than_9_parseable")
    for row in rows:
        if critical_error(row):
            reasons.append(critical_error(row))
        if row.get("operational_status") == "runner_failure" or row.get("online_forbidden_fields_present") is None:
            reasons.append("runner_or_projection_error")
        for request in row.get("provider_requests", []):
            if request.get("response_received") and not all(request.get(k) for k in ("local_request_id", "payload_sha256", "provider_response_id", "returned_model")):
                reasons.append("incomplete_request_identity")
    return {"passed": not reasons, "rows": len(rows), "parsed_rows": parsed, "reasons": sorted(set(reasons)), "outcome_blind": True}


def run(part: str, *, canary_only: bool, retry_key: str | None = None, output: Path = OUTPUT) -> dict[str, Any]:
    plan_path = write_plan(output)
    full_plan = read_jsonl(plan_path)
    plan = [r for r in full_plan if r["study_part"] == part]
    raw_path = output / ("deepseek_pro_raw.jsonl" if part == "authorization" else "synthetic_regression_raw.jsonl")
    with model_lock(output / "internal" / f"{part}.lock"):
        history = latest_records(read_jsonl(raw_path))
        unknown = set(history) - {r["work_key"] for r in plan}
        if unknown:
            raise ValueError("raw results outside study plan")
        pending = pending_rows(plan, history, retry_key)
        prefix_keys = {r["work_key"] for r in plan if r["formal_prefix"]}
        if canary_only:
            pending = [(r, a) for r, a in pending if r["formal_prefix"]]
        elif part == "authorization" and not retry_key:
            checked = gate([history[k] for k in prefix_keys if k in history])
            if not checked["passed"]:
                raise ValueError("formal prefix has not passed; run canary first")
        stop = threading.Event()
        pacer = RequestPacer(0, stop)
        values = parse_env_file(resolve_config_path(None, project_root=ROOT))
        key = credential(values, "deepseek_pro")
        runtime = RevisionRuntime(plan_path, plan[0]["execution_identity"]) if part == "authorization" else SyntheticRuntime()
        factory = DevelopmentRequestClient if part == "authorization" else partial(DevelopmentRequestClient, max_provider_calls=3)
        reason = None
        errors: dict[str, set[str]] = {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            iterator = iter(pending)
            active = {}
            while True:
                while not stop.is_set() and len(active) < 2:
                    item = next(iterator, None)
                    if item is None:
                        break
                    row, attempt = item
                    active[pool.submit(execute_one, row, attempt, runtime=runtime, api_key=key, pacer=pacer, output=output, client_factory=factory)] = row
                if not active:
                    break
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    item = active.pop(future)
                    record = future.result()
                    append_row(raw_path, record)
                    history[item["work_key"]] = record
                    issue = critical_error(record)
                    if issue:
                        reason = issue
                    if any(r.get("http_status") == 429 for r in record["provider_requests"]):
                        reason = "provider_429"
                    if record["operational_status"] in {"runner_failure", "provider_failure"}:
                        name = str(record.get("failure_class"))
                        errors.setdefault(name, set()).add(record["case_id"])
                        if len(errors[name]) >= 2:
                            reason = "repeated_system_error:" + name
                    if reason:
                        stop.set()
                    print(json.dumps({"part": part, "recorded": len(history), "planned": len(plan), "status": record["operational_status"], "failure_class": record.get("failure_class"), "stop": reason}), flush=True)
        checked = gate([history[k] for k in prefix_keys if k in history]) if part == "authorization" else None
        result = {"part": part, "planned": len(plan), "recorded": len(history), "pending": len(plan) - len(history),
                  "gate": checked, "stop_reason": reason, "statuses": dict(Counter(r["operational_status"] for r in history.values())), "updated_at": now()}
        (output / f"{part}_status.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--write-plan", action="store_true")
    parser.add_argument("--part", choices=("authorization", "synthetic"))
    parser.add_argument("--canary-only", action="store_true")
    parser.add_argument("--resume-pending-only", action="store_true")
    parser.add_argument("--retry-failed-work-key")
    args = parser.parse_args()
    if args.write_plan:
        path = write_plan()
        print(json.dumps({"plan": str(path), "rows": len(read_jsonl(path))}))
    elif args.part and (args.canary_only or args.resume_pending_only or args.retry_failed_work_key):
        result = run(args.part, canary_only=args.canary_only, retry_key=args.retry_failed_work_key)
        print(json.dumps(result, ensure_ascii=False))
        if result["stop_reason"] or args.canary_only and not result["gate"]["passed"]:
            raise SystemExit(2)
    else:
        parser.error("select plan creation or an explicit canary/pending/recovery mode")


if __name__ == "__main__":
    main()
