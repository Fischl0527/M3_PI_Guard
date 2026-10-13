"""本次复杂任务研究的独立队列；已有响应及开放请求绝不自动重发。"""
from __future__ import annotations

import argparse
import copy
import json
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import partial
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.correctness_plan_v1 import ROOT, read_jsonl
from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer, append_row, now
from experiments.paper_v2.correctness_runner_v1 import critical_error, execute_one, latest_records, make_unrun, pending_rows
from experiments.paper_v2.empirical_reinforcement_v1 import study_lock
from experiments.paper_v2.task_contract_compilation_v1 import STUDY_SCOPE, first_contracts

OUTPUT = ROOT / "outputs/experiments/task_contract_compiler_v3_validation_v1"
PROVIDERS = {"pro": "deepseek_pro", "flash": "deepseek_flash", "gemini": "gemini_flash"}
STUDY_PRICING = {"checked_at": "2026-10-13", "source_url": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
    "peak_cny_per_million": {"deepseek-v4-pro": [0.30, 9.0, 27.0], "deepseek-flash": [0.04, 2.0, 8.0]},
    "basis": "official_peak_tariff_estimate_not_invoice"}


def technical_prefix(rows: list[Mapping[str, Any]], *, expected: int = 50, threshold: int = 40) -> dict[str, Any]:
    """仅检查解析、身份和隔离；不按完成率/unsafe结果择优放行。"""
    reasons = []
    if len(rows) != expected or len({r["work_key"] for r in rows}) != expected:
        reasons.append("prefix_incomplete_or_duplicate")
    parsed = sum(r.get("operational_status") in {"completed", "max_steps"} and
        any(e.get("parse_ok") is True for e in r.get("events", [])) for r in rows)
    if parsed < threshold:
        reasons.append("parsed_prefix_below_threshold")
    payloads: dict[tuple[Any, ...], set[str]] = {}
    for row in rows:
        issue = critical_error(row)
        if issue:
            reasons.append(issue)
        if row.get("online_forbidden_fields_present") is None or row.get("operational_status") == "runner_failure":
            reasons.append("runtime_or_projection_failure")
        for request in row.get("provider_requests", []):
            if request.get("response_received") and not all(request.get(k) for k in (
                "local_request_id", "payload_sha256", "provider_response_id", "returned_model")):
                reasons.append("missing_official_response_identity")
        requests = row.get("provider_requests", [])
        if requests:
            key = (row.get("base_task_id"), row.get("scenario"), row.get("replicate_index"))
            payloads.setdefault(key, set()).add(requests[0]["payload_sha256"])
    if any(len(v) > 1 for v in payloads.values()):
        reasons.append("initial_payload_mismatch_across_conditions")
    return {"passed": not reasons, "rows": len(rows), "parsed_rows": parsed,
        "reasons": sorted(set(reasons)), "outcome_blind": True}


def record_failure_reason(row: Mapping[str, Any]) -> str | None:
    issue = critical_error(row)
    if issue:
        return issue
    for request in row.get("provider_requests", []):
        status = request.get("http_status")
        if status in {401, 403, 429}:
            return f"provider_{status}"
        if status == 404 or request.get("error_type") == "ProviderIdentityError":
            return "model_unsupported_or_identity_failure"
    return None


def annotate(row: Mapping[str, Any]) -> dict[str, Any]:
    """记录本次真实参数和ITT边界；不补造缺失终态。"""
    value = copy.deepcopy(dict(row))
    gemini = value["model_group"] == "gemini_flash"
    forbidden = value.get("online_forbidden_fields_present")
    if type(forbidden) is bool:
        forbidden_count = int(forbidden)
    elif isinstance(forbidden, (list, tuple)):
        forbidden_count = len(forbidden)
    else:
        forbidden_count = None
    condition = str(value.get("condition_id", ""))
    compiler_profile = "first_pro_draft_fixed" if condition.startswith("new_") or value.get("ablation_profile") else "historical_corrected_chain" if condition.startswith("old_") else "not_enforced"
    value.update(runner_revision="task_contract_study_v1", compiler_profile=compiler_profile,
        generation_profile="task_contract_study_v1", max_tokens=2048 if gemini else 512,
        reasoning_effort="low" if gemini else None, automatic_retries=0,
        evaluator_fields_online=forbidden_count)
    value.setdefault("provider_tools_enabled", False)
    value.setdefault("real_external_effects", 0)
    value["study_pricing_attestation"] = copy.deepcopy(STUDY_PRICING)
    latency = value.get("latency_ms")
    value["latency_seconds"] = latency.get("total", 0) / 1000 if isinstance(latency, Mapping) else None
    cost = value.get("cost", {})
    value["cost_estimate_cny"] = cost.get("amount") if cost.get("currency") == "CNY" else 0 if gemini else None
    return value


class StudyRuntime:
    """原生和合成loader按案例路由，离线评价材料不进入提示或编译。"""

    def __init__(self, plan_path: Path, *, output: Path = OUTPUT) -> None:
        from experiments.paper_v2.task_contract_cases_v1 import load_compiler_inputs, load_task_contract_case
        from experiments.paper_v2.task_contract_synthetic_v1 import SyntheticTaskBackend, score_synthetic
        from experiments.paper_v2.task_contract_runtime_v1 import TaskContractNativeRuntime, TaskContractSyntheticRuntime
        plan = read_jsonl(plan_path)
        self.contracts = first_contracts(read_jsonl(output / "compilation/raw_records_v1.jsonl"))
        self.synthetic = TaskContractSyntheticRuntime(contracts=self.contracts, backend_factory=SyntheticTaskBackend,
            scorer=score_synthetic, case_loader=lambda row: self._load_synthetic(load_task_contract_case, row))
        self.native = TaskContractNativeRuntime(plan_path, plan[0]["execution_identity"], contracts=self.contracts,
            input_loader=load_compiler_inputs) if any(r["benchmark"] in {"agentdojo-v1", "m3-v2"} for r in plan) else None

    @staticmethod
    def _load_synthetic(loader: Any, row: Mapping[str, Any]) -> tuple[Any, Any]:
        case = loader(row, scenario=row["scenario"])
        return case["live_case"], case["offline_evaluation"]

    def execute(self, row: Mapping[str, Any], client: Any) -> dict[str, Any]:
        if row["condition_id"].startswith("new_") or row.get("ablation_profile"):
            fixed = self.contracts.get(row["base_task_id"])
            if fixed is None:
                raise ValueError("first compiler draft not yet attempted")
            if fixed["compile_status"] != "compiled":
                return {"unsafe_effect": None, "task_completion": None,
                    "unsafe_effect_observed": False, "task_completion_observed": False,
                    "operational_status": "compile_failure", "events": [], "ask_count": 0, "deny_count": 0,
                    "online_forbidden_fields_present": [], "latency_ms": None,
                    "observation_complete": False, "effect_evidence": {"isolated_material_observed": False,
                        "unsafe_scored": False, "completion_scored": False},
                    "evaluation_details": {"unknown_reasons": ["fixed_first_contract_failed"]}}
        runtime = self.native if row["benchmark"] in {"agentdojo-v1", "m3-v2"} else self.synthetic
        if runtime is None:
            raise ValueError("native runtime not assembled")
        return runtime.execute(row, client)


class DiagnosticRuntime:
    """六个独立synthetic JSON提案；不加载旧Gemini结果、不执行工具。"""

    def execute(self, row: Mapping[str, Any], client: Any) -> dict[str, Any]:
        from experiments.paper_v2.live_condition_runtime import parse_strict_tool_proposal
        from experiments.paper_v2.provider_safety import build_safety_receipt
        from experiments.paper_v2.task_contract_synthetic_v1 import tool_schemas
        schemas = tool_schemas()
        schemas["final"] = {"arguments": {"answer": {"type": "string", "required": True}}, "side_effect": False}
        kind = row["diagnostic_kind"]
        expected = {"read": {"tool": "read_object", "arguments": {"object_id": "diagnostic-object"}},
            "write": {"tool": "update_object", "arguments": {"object_id": "diagnostic-object", "field": "status", "value": "reviewed"}},
            "final": {"tool": "final", "arguments": {"answer": "synthetic-diagnostic"}}}[kind]
        messages = [{"role": "system", "content": "Return exactly the requested synthetic JSON tool proposal. No tool is actually executed."},
            {"role": "user", "content": "Return this JSON proposal: " + json.dumps(expected, sort_keys=True)}]
        try:
            result = client.complete(messages)
        except Exception as exc:
            status, parsed = "provider_failure", False
            failure = type(exc).__name__
        else:
            try:
                proposal = parse_strict_tool_proposal(result.text, tool_schemas=schemas)
                if proposal.tool != expected["tool"] or proposal.arguments != expected["arguments"]:
                    raise ValueError("diagnostic JSON proposal differs from requested shape")
            except Exception as exc:
                status, parsed = "parse_failure", False
                failure = type(exc).__name__
            else:
                status, parsed, failure = "completed", True, None
        return {"unsafe_effect": None, "task_completion": None,
            "unsafe_effect_observed": False, "task_completion_observed": False,
            "operational_status": status, "failure_class": failure,
            "events": [{"parse_ok": parsed, "execution_attempted": False, "simulated_action_executed": False}],
            "ask_count": 0, "deny_count": 0, "online_forbidden_fields_present": [],
            "safety_receipt": build_safety_receipt(provider_id=client.provider_id, endpoint_url=client.endpoint,
                effect_backend="no_effect", tool="final", arguments={"answer": ""})}


def diagnostic_plan() -> list[dict[str, Any]]:
    """读/写/final各二项，独立synthetic诊断身份不接续旧Gemini任务。"""
    from experiments.paper_v2.contracts import sha256_canonical_json
    rows = []
    for index, kind in enumerate(("read", "write", "final", "read", "write", "final"), 1):
        key = "diagnostic-" + sha256_canonical_json({"study": STUDY_SCOPE, "index": index, "kind": kind})[:24]
        rows.append({"work_key": key, "base_task_id": key, "underlying_task_id": key, "cluster_id": key,
            "model_key": "gemini", "model_group": "gemini_flash", "model_id": "gemini-3.6-flash",
            "benchmark": "task-contract-synthetic-v1", "condition_id": "no_defense", "scenario": "benign",
            "replicate_index": 1, "diagnostic_kind": kind, "formal_prefix": False,
            "max_provider_calls": 1, "study_id": STUDY_SCOPE})
    return rows


def run_provider(provider: str, *, plan_path: Path, output: Path = OUTPUT, api_key: str,
                 prefix_only: bool = False, resume_pending_only: bool = False, runtime: Any = None,
                 client_factory: Any = DevelopmentRequestClient, stopped: threading.Event | None = None,
                 diagnostics: bool = False, allow_diagnostic_no_response_retry: bool = False,
                 free_tier_confirmed: bool = False, ablation: bool = False,
                 retry_failed_work_key: str | None = None) -> dict[str, Any]:
    """任务累积12call，独立模型目录；Gem单并发15秒，DS各双并发。"""
    if provider not in PROVIDERS or prefix_only and resume_pending_only or ablation and provider != "pro":
        raise ValueError("unsupported provider or contradictory selection")
    group = PROVIDERS[provider]
    plan = [r for r in read_jsonl(plan_path) if r["model_group"] == group]
    if not plan:
        raise ValueError("empty model plan")
    destination = output / ("diagnostics/gemini" if diagnostics else "ablation/pro" if ablation else provider)
    if provider == "gemini" and not free_tier_confirmed:
        return seal_provider(plan_path=plan_path, provider=provider, output=output,
            reason="free_project_not_confirmed_skip", diagnostics=diagnostics)
    raw_path = destination / "raw_records_v1.jsonl"
    stop = stopped if stopped is not None else threading.Event()
    marker = output / "deepseek_dispatch_closed_v1.json"
    with study_lock(destination / "internal/runner.lock"):
        prior_rows = read_jsonl(raw_path)
        history = latest_records(prior_rows)
        used_calls = {}
        for prior in prior_rows:
            key = prior["work_key"]
            used_calls[key] = used_calls.get(key, 0) + prior.get("provider_call_count", 0)
        if set(history) - {r["work_key"] for r in plan}:
            raise ValueError("raw results outside this study plan")
        if any(record_failure_reason(r) for r in history.values()):
            return {"provider": provider, "stop_reason": "prior_fatal_provider_error", "recorded": len(history)}
        prefix = {r["work_key"] for r in plan if r.get("formal_prefix")}
        check = technical_prefix([history[k] for k in prefix if k in history]) if not diagnostics else None
        if resume_pending_only and not retry_failed_work_key and check is not None and not check["passed"]:
            raise ValueError("formal prefix not qualified; no pending extension")
        if retry_failed_work_key:
            old = history.get(retry_failed_work_key, {})
            requests = old.get("provider_requests", [])
            if not requests or any(r.get("response_received") for r in requests) or old.get("attempt") != 1:
                raise ValueError("unique recovery requires one prior actual no-response attempt")
            if old.get("operational_status") != "provider_failure" or any(
                r.get("http_status") not in {None, 503} for r in requests):
                raise ValueError("only transport/HTTP503 no-response failures permit one recovery")
        pending = pending_rows(plan, history, retry_failed_work_key)
        if prefix_only:
            pending = [(r, a) for r, a in pending if r["work_key"] in prefix]
        if diagnostics:
            if provider != "gemini" or len(plan) != 6:
                raise ValueError("diagnostics require exactly six independent Gemini proposals")
            if allow_diagnostic_no_response_retry:
                retryable = [r for r in history.values() if not r.get("response_obtained") and r.get("attempt") == 1 and
                    r.get("operational_status") == "provider_failure" and not record_failure_reason(r)]
                pending += [(next(p for p in plan if p["work_key"] == r["work_key"]), 2) for r in retryable]
        # 先检查所有待派发请求，任何旧trace存在都拒绝发出第一个新请求。
        for row, attempt in pending:
            trace = destination / "internal" / group / f"{row['work_key']}.attempt{attempt}.jsonl"
            if trace.exists():
                raise RuntimeError("open trace requires diagnosis; cannot automatically replay")
        if not pending:
            return {"provider": provider, "planned": len(plan), "recorded": len(history), "pending": len(plan) - len(history), "prefix": check}
        runner = runtime if runtime is not None else DiagnosticRuntime() if diagnostics else StudyRuntime(plan_path, output=output)
        pacer = RequestPacer(15 if provider == "gemini" else 0, stop)
        reason = None
        errors: dict[str, set[str]] = {}
        if provider == "gemini" and any(a == 2 for _, a in pending):
            # 仅诊断无响应一次补发，明确60秒；生产正式队列永不补发已有行。
            if stop.wait(60):
                return {"provider": provider, "stop_reason": "dispatch_stop_before_diagnostic_retry"}
        with ThreadPoolExecutor(max_workers=1 if provider == "gemini" else 2) as pool:
            iterator, active = iter(pending), {}
            while True:
                while not stop.is_set() and len(active) < (1 if provider == "gemini" else 2):
                    if provider == "gemini" and not diagnostics and marker.exists():
                        reason = "deepseek_finished_no_new_gemini_tasks"
                        stop.set()
                        break
                    item = next(iterator, None)
                    if item is None:
                        break
                    row, attempt = item
                    used = used_calls.get(row["work_key"], 0)
                    remaining = (1 if diagnostics else 12) - used if not diagnostics or attempt == 1 else 1
                    if remaining < 1:
                        raise ValueError("cumulative task provider call cap exhausted")
                    factory = partial(client_factory, max_provider_calls=remaining, call_budget_ceiling=12,
                        call_budget_scope=STUDY_SCOPE, generation_profile="task_contract_study_v1")
                    active[pool.submit(execute_one, row, attempt, runtime=runner, api_key=api_key,
                        pacer=pacer, output=destination, client_factory=factory)] = row
                if not active:
                    break
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    row = active.pop(future)
                    try:
                        record = annotate(future.result())
                    except Exception:
                        stop.set()
                        raise  # 开放请求不伪装为可重发失败。
                    append_row(raw_path, record)
                    history[row["work_key"]] = record
                    used_calls[row["work_key"]] = used_calls.get(row["work_key"], 0) + record["provider_call_count"]
                    if record["attempt"] == 2 and not record.get("response_obtained"):
                        reason = "no_response_recovery_exhausted"
                        stop.set()
                    fatal = record_failure_reason(record)
                    if fatal:
                        reason = fatal
                        stop.set()
                    if record.get("operational_status") in {"runner_failure", "provider_failure"}:
                        failure = str(record.get("failure_class", "unknown"))
                        errors.setdefault(failure, set()).add(row["base_task_id"])
                        if len(errors[failure]) >= 2:
                            reason = "repeated_system_error:" + failure
                            stop.set()
        summary = {"provider": provider, "planned": len(plan), "recorded": len(history),
            "pending": len(plan) - len(history), "stop_reason": reason, "updated_at": now(),
            "prefix": technical_prefix([history[k] for k in prefix if k in history]) if not diagnostics else None}
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "status_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if provider in {"pro", "flash"} and not prefix_only and not ablation:
            close_deepseek_dispatch(output, provider, reason=reason)
        if provider == "gemini" and reason and not diagnostics:
            for item in plan:
                if item["work_key"] not in history:
                    record = annotate(make_unrun(item, reason))
                    record.update(online_forbidden_fields_present=[], evaluator_fields_online=0,
                        observation_complete=False, effect_evidence={"isolated_material_observed": False})
                    append_row(raw_path, record)
        return summary


def seal_provider(*, plan_path: Path, provider: str, output: Path = OUTPUT,
                  reason: str, diagnostics: bool = False) -> dict[str, Any]:
    """明确封闭尚未派发的计划行；响应行及失败尝试原样保留。"""
    if provider not in PROVIDERS or not reason:
        raise ValueError("explicit provider and stop reason required")
    plan = [r for r in read_jsonl(plan_path) if r["model_group"] == PROVIDERS[provider]]
    destination = output / ("diagnostics/gemini" if diagnostics else provider)
    raw_path = destination / "raw_records_v1.jsonl"
    with study_lock(destination / "internal/runner.lock"):
        history = latest_records(read_jsonl(raw_path))
        for row in plan:
            if row["work_key"] in history:
                continue
            trace = destination / "internal" / row["model_group"] / f"{row['work_key']}.attempt1.jsonl"
            if trace.exists():
                raise RuntimeError("open trace cannot be sealed as unstarted; diagnose first")
            record = annotate(make_unrun(row, reason))
            record.update(online_forbidden_fields_present=[],evaluator_fields_online=0,
                observation_complete=False,effect_evidence={"isolated_material_observed":False})
            append_row(raw_path, record)
            history[row["work_key"]] = record
        result = {"provider":provider,"planned":len(plan),"recorded":len(history),"provider_calls":0,
            "not_run":sum(r.get("operational_status") == "not_run" for r in history.values()),
            "stop_reason":reason,"sealed":True,"updated_at":now()}
        (destination / "status_v1.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return result


def close_deepseek_dispatch(output: Path, provider: str, *, reason: str | None) -> None:
    """主队列结束标记只属于本study；两DS都结束后Gem不再领新任务。"""
    if provider not in {"pro", "flash"}:
        raise ValueError("only primary DeepSeek queues can close this dispatch")
    path = output / provider / "dispatch_closed_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"study_id": STUDY_SCOPE, "provider": provider, "dispatch_closed": True,
        "stop_reason": reason, "recorded_at": now()}
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
    other = "flash" if provider == "pro" else "pro"
    other_path = output / other / "dispatch_closed_v1.json"
    if not other_path.exists():
        return
    old = json.loads(other_path.read_text(encoding="utf-8"))
    if old.get("study_id") == STUDY_SCOPE and old.get("dispatch_closed") is True:
        marker = output / "deepseek_dispatch_closed_v1.json"
        marker.write_text(json.dumps({"study_id": STUDY_SCOPE, "dispatch_closed": True,
            "providers": ["pro", "flash"], "recorded_at": now()}, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=tuple(PROVIDERS))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--prefix-only", action="store_true")
    parser.add_argument("--resume-pending-only", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--compile-contracts", action="store_true")
    parser.add_argument("--ablation", action="store_true")
    parser.add_argument("--offline-replay", action="store_true")
    parser.add_argument("--free-project-confirmed", action="store_true")
    parser.add_argument("--compile-limit", type=int)
    parser.add_argument("--compile-stage", choices=("development", "evaluation"), default="development")
    parser.add_argument("--retry-diagnostic-no-response", action="store_true")
    parser.add_argument("--retry-failed-work-key")
    parser.add_argument("--seal-provider", action="store_true")
    parser.add_argument("--stop-reason", default="explicit_provider_stop")
    args = parser.parse_args()
    if args.offline_replay:
        from experiments.paper_v2.task_contract_offline_replay_v1 import OfflineReplayUnavailable, run_offline_replay
        try:
            result = run_offline_replay(args.output)
        except OfflineReplayUnavailable as exc:
            print(json.dumps(exc.summary, ensure_ascii=False))
            raise SystemExit(2) from None
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.compile_contracts:
        from experiments.paper_v2.claude_revision_v1 import load_key
        from experiments.paper_v2.task_contract_cases_v1 import build_case_cohorts, load_compiler_inputs
        from experiments.paper_v2.task_contract_compilation_v1 import compile_contract_drafts
        cohorts = build_case_cohorts()
        bases = cohorts[args.compile_stage]
        if args.compile_limit is not None:
            if args.compile_limit < 1:
                parser.error("--compile-limit must be positive")
            bases = bases[:args.compile_limit]
        rows = compile_contract_drafts(bases,
            input_loader=load_compiler_inputs, output=args.output, api_key=load_key())
        print(json.dumps({"compiler_records": len(rows)}))
        return
    if args.diagnostics and args.provider == "gemini" and args.plan is None:
        args.plan = args.output / "diagnostics/gemini/plan_v1.jsonl"
        expected = diagnostic_plan()
        if args.plan.exists() and read_jsonl(args.plan) != expected:
            raise ValueError("diagnostic plan differs from this study")
        if not args.plan.exists():
            for row in expected:
                append_row(args.plan, row)
    if not args.provider or not args.plan:
        parser.error("live study requires --provider and --plan")
    if args.seal_provider or args.provider == "gemini" and not args.free_project_confirmed:
        reason = args.stop_reason if args.seal_provider else "free_project_not_confirmed_skip"
        print(json.dumps(seal_provider(plan_path=args.plan,provider=args.provider,output=args.output,
            reason=reason,diagnostics=args.diagnostics),ensure_ascii=False))
        return
    if args.ablation and args.provider != "pro":
        parser.error("conservative ablations are Pro-only")
    # 只有用户显式调用此在线入口时才使用现有凭据装配，不在离线测试读配置。
    from experiments.paper_v2.correctness_runner_v1 import credential
    from m3_core.project_config import parse_env_file, resolve_config_path
    values = parse_env_file(resolve_config_path(None))
    result = run_provider(args.provider, plan_path=args.plan, output=args.output,
        api_key=credential(values, PROVIDERS[args.provider]), prefix_only=args.prefix_only,
        resume_pending_only=args.resume_pending_only, diagnostics=args.diagnostics,
        free_tier_confirmed=args.free_project_confirmed, ablation=args.ablation,
        allow_diagnostic_no_response_retry=args.retry_diagnostic_no_response,
        retry_failed_work_key=args.retry_failed_work_key)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
