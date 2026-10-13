"""受控并行的开发先导实验运行器。

调度执行多用例并发验证，记录执行事件并在完成后自动安全落盘。
"""

from __future__ import annotations

# 48任务开发试跑入口：各模型独立输出，任务内状态隔离，已获响应的行不重跑。
# not_run（未运行）、无响应故障和有响应终态分别记录，不能用计划数量冒充完成量。

import argparse
import copy
import json
import threading
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.correctness_plan_v1 import MODELS, OUTPUT, read_jsonl, write_plan
from experiments.paper_v2.correctness_provider_v1 import (
    DevelopmentRequestClient, RequestPacer, append_row, now, request_cost,
)
from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime
from m3_core.project_config import parse_env_file, resolve_config_path


@contextmanager
def model_lock(path: Path):
    """进程退出时由操作系统释放锁，且不删除用户文件。"""
    import msvcrt

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if not path.stat().st_size:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("development model already has an active runner") from exc
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def credential(values: Mapping[str, str], group: str) -> str:
    provider = "GEMINI" if group == "gemini_flash" else "DEEPSEEK"
    expected_url = "https://generativelanguage.googleapis.com/v1beta/openai/" if provider == "GEMINI" else "https://api.deepseek.com"
    configured = values.get(f"FRONTIER_{provider}_BASE_URL", "")
    if configured.rstrip("/") != expected_url.rstrip("/"):
        raise ValueError("configured endpoint is not the approved official endpoint")
    key = values.get(f"{provider}_API_KEY", "")
    if not key or not key.strip() or "\n" in key or "\r" in key:
        raise ValueError("required provider credential missing or invalid")
    # Deliberately do not inherit the legacy Flash model from local config.
    # The immutable development plan contains the user-approved model names.
    return key


def latest_records(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    # 恢复最多一次，只允许此前完全未取得响应的任务；成功/有响应失败均保留。
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if type(row.get("attempt")) is not int:
            raise ValueError("attempt must be an integer")
        key = row["work_key"]
        previous = result.get(key)
        if previous is None:
            valid_first = (row.get("operational_status") == "not_run" and row.get("attempt") == 0) or (row.get("operational_status") != "not_run" and row.get("attempt") == 1)
            if not valid_first:
                raise ValueError("invalid first attempt for work key")
        if previous is not None:
            if previous.get("response_obtained") or previous.get("operational_status") in {"completed", "not_run"}:
                raise ValueError("successful or response-bearing work key was repeated")
            if int(row["attempt"]) != int(previous["attempt"]) + 1 or int(row["attempt"]) > 2:
                raise ValueError("invalid explicit recovery attempt")
        result[key] = row
    return result


def pending_rows(plan: list[dict[str, Any]], prior: Mapping[str, Any], retry_key: str | None = None) -> list[tuple[dict[str, Any], int]]:
    if retry_key:
        chosen = next((row for row in plan if row["work_key"] == retry_key), None)
        old = prior.get(retry_key)
        if chosen is None or old is None or old.get("response_obtained") or int(old.get("attempt", 0)) != 1:
            raise ValueError("recovery requires exactly one prior no-response attempt")
        if old.get("operational_status") in {"completed", "not_run"}:
            raise ValueError("successful or administratively unrun work cannot be retried")
        return [(chosen, 2)]
    return [(row, 1) for row in plan if row["work_key"] not in prior]


def make_unrun(item: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        **copy.deepcopy(dict(item)), "attempt": 0, "status": "not_run",
        "operational_status": "not_run", "not_run_reason": reason,
        "unsafe_effect": None, "task_completion": None, "response_obtained": False,
        "provider_requests": [], "provider_call_count": 0,
        "evaluation_details": {}, "ask_count": 0, "deny_count": 0,
        "token_usage": {"input": 0, "output": 0, "total": 0}, "latency_ms": None,
        "cost": request_cost([], str(item["model_id"])), "recorded_at": now(),
    }


def execute_one(item: dict[str, Any], attempt: int, *, runtime: Any, api_key: str, pacer: RequestPacer, output: Path = OUTPUT, client_factory: Any = DevelopmentRequestClient) -> dict[str, Any]:
    trace = output / "internal" / item["model_group"] / f"{item['work_key']}.attempt{attempt}.jsonl"
    if trace.exists():
        # 已开放但无终态的请求须先诊断，不能猜测失败并再次发送。
        raise RuntimeError("request trace exists without selected terminal record")
    client = client_factory(
        model_group=item["model_group"], model=item["model_id"], api_key=api_key,
        benchmark=item["benchmark"], work_key=item["work_key"], attempt=attempt,
        trace_path=trace, pacer=pacer,
    )
    started = now()
    append_row(trace, {"event": "work_started", "work_key": item["work_key"], "attempt": attempt, "recorded_at": started})
    try:
        outcome = runtime.execute(item, client)
    except Exception as exc:
        # 后续评价/关闭异常不抹去已收到的 HTTP 回执；只公开异常类型，不泄露上下文。
        outcome = {
            "unsafe_effect": None, "task_completion": None, "evaluation_details": {},
            "operational_status": "runner_failure", "failure_stage": "runtime_or_evaluator",
            "failure_class": type(exc).__name__, "ask_count": 0, "deny_count": 0,
            "latency_ms": None, "events": [],
        }
    requests = copy.deepcopy(client.requests)
    usage = {
        "input": sum(r.get("usage", {}).get("prompt_tokens", 0) for r in requests),
        "output": sum(r.get("usage", {}).get("completion_tokens", 0) for r in requests),
        "total": sum(r.get("usage", {}).get("total_tokens", 0) for r in requests),
    }
    record = {
        # 保存完整评价摘要，尤其未知值与细分端点；后续分析读取这些实际记录。
        **copy.deepcopy(item), **outcome, "attempt": attempt, "status": "terminal",
        "provider_requests": requests, "provider_call_count": len(requests),
        "response_obtained": any(r.get("response_received") for r in requests),
        "token_usage": usage, "cost": request_cost(requests, item["model_id"]),
        "started_at": started, "recorded_at": now(),
        "provider_tools_enabled": outcome.get("provider_tools_enabled", False),
        "real_external_effects": outcome.get("real_external_effects", 0),
    }
    if item["model_group"] == "gemini_flash":
        record["free_tier_attestation"] = {
            "billing_tier": "free", "paid_ceiling_usd": 0,
            "basis": "user-confirmed free project; billing status not independently queried",
            "paid_fallback": False, "project_or_key_rotation": False,
        }
    return record


def critical_error(row: Mapping[str, Any]) -> str | None:
    if row.get("online_forbidden_fields_present"):
        return "online_field_leak"
    if row.get("provider_tools_enabled") or row.get("real_external_effects"):
        return "external_safety_violation"
    for request in row.get("provider_requests", []):
        if request.get("error_type") in {"ProviderIdentityError", "ProviderPayloadError", "ProviderBudgetExceeded"}:
            return str(request["error_type"])
        if request.get("returned_model") and request["returned_model"] != row["model_id"]:
            return "model_identity_drift"
    return None


def run_model(group: str, plan_path: Path, values: Mapping[str, str], stop: threading.Event, *, prefix_only: bool = False, retry_key: str | None = None, output: Path = OUTPUT) -> dict[str, Any]:
    plan = [r for r in read_jsonl(plan_path) if r["model_group"] == group]
    raw_path = output / group / "raw_records.jsonl"
    with model_lock(output / "internal" / group / "runner.lock"):
        history = latest_records(read_jsonl(raw_path))
        pending = pending_rows(plan, history, retry_key)
        if prefix_only:
            pending = [(r, a) for r, a in pending if r["formal_prefix"]]
        api_key = credential(values, group)
        runtime = CorrectnessRuntime(plan_path=plan_path, execution_identity=plan[0]["execution_identity"])
        pacer = RequestPacer(15.0 if group == "gemini_flash" else 0.0, stop)
        worker_count = 1 if group == "gemini_flash" else 2
        error_cases: dict[str, set[str]] = defaultdict(set)
        stop_reason = "external_dispatch_stop"
        # Completed prefix is reused, never rerun to obtain a green gate.
        for old in (() if retry_key else history.values()):
            issue = critical_error(old)
            if issue:
                stop.set()
                stop_reason = issue
            if old.get("operational_status") in {"runner_failure", "provider_failure"} and old.get("failure_class") != "DispatchStopped":
                error_cases[str(old.get("failure_class"))].add(old["case_id"])
        if any(len(cases) >= 2 for cases in error_cases.values()):
            stop.set()
            stop_reason = "repeated_system_error"

        phases = [pending] if retry_key else [
            [(r, a) for r, a in pending if r["formal_prefix"]],
            [(r, a) for r, a in pending if not r["formal_prefix"]],
        ]
        for batch in phases:
            iterator = iter(batch)
            with ThreadPoolExecutor(max_workers=worker_count) as pool:
                active: dict[Any, Any] = {}
                while True:
                    while not stop.is_set() and len(active) < worker_count:
                        item = next(iterator, None)
                        if item is None:
                            break
                        row, attempt = item
                        future = pool.submit(execute_one, row, attempt, runtime=runtime, api_key=api_key, pacer=pacer, output=output)
                        active[future] = row
                    if not active:
                        break
                    finished, _ = wait(active, return_when=FIRST_COMPLETED)
                    for future in finished:
                        item = active.pop(future)
                        try:
                            record = future.result()
                        except Exception:
                            # Do not paper over an open trace/locking/config failure.
                            stop.set()
                            stop_reason = "unresolved_execution_record"
                            raise
                        append_row(raw_path, record)
                        history[item["work_key"]] = record
                        issue = critical_error(record)
                        if issue:
                            stop.set()
                            stop_reason = issue
                        if any(r.get("http_status") == 429 for r in record["provider_requests"]):
                            stop.set()
                            stop_reason = "provider_429"
                        if record["operational_status"] in {"runner_failure", "provider_failure"} and record.get("failure_class") != "DispatchStopped":
                            error_cases[str(record.get("failure_class"))].add(record["case_id"])
                            if len(error_cases[str(record.get("failure_class"))]) >= 2:
                                stop.set()
                                stop_reason = "repeated_system_error"
                        print(json.dumps({"model_group": group, "recorded": len(history), "planned": len(plan), "status": record["operational_status"]}), flush=True)
            if stop.is_set():
                break
        if not prefix_only and not retry_key:
            for item in plan:
                if item["work_key"] not in history:
                    record = make_unrun(item, stop_reason)
                    append_row(raw_path, record)
                    history[item["work_key"]] = record
        return {"model_group": group, "planned": len(plan), "recorded": len(history), "stop_reason": stop_reason if stop.is_set() else None}


def run_all(plan_path: Path, values: Mapping[str, str]) -> list[dict[str, Any]]:
    stops = {group: threading.Event() for group in MODELS}
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(run_model, group, plan_path, values, stops[group]): group for group in MODELS}
        deepseek_remaining = {"deepseek_pro", "deepseek_flash"}
        while jobs:
            done, _ = wait(jobs, return_when=FIRST_COMPLETED)
            for job in done:
                group = jobs.pop(job)
                try:
                    results.append(job.result())
                except Exception as exc:
                    results.append({"model_group": group, "error_type": type(exc).__name__, "state": "requires_diagnosis"})
                deepseek_remaining.discard(group)
                if not deepseek_remaining:
                    stops["gemini_flash"].set()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run-all", action="store_true")
    parser.add_argument("--provider", choices=tuple(MODELS))
    parser.add_argument("--prefix-only", action="store_true")
    parser.add_argument("--resume-pending-only", action="store_true")
    parser.add_argument("--retry-failed-work-key")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    path = write_plan()
    if args.prepare:
        print(json.dumps({"plan": str(path), "records": len(read_jsonl(path))}))
        return
    if not args.run_all and not args.provider:
        parser.error("choose --prepare, --run-all, or --provider")
    values = parse_env_file(resolve_config_path(args.config))
    try:
        if args.run_all:
            if args.retry_failed_work_key or args.prefix_only:
                parser.error("run-all cannot combine with explicit recovery/prefix-only")
            result = run_all(path, values)
        else:
            result = run_model(args.provider, path, values, threading.Event(), prefix_only=args.prefix_only, retry_key=args.retry_failed_work_key)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        values.clear()


if __name__ == "__main__":
    main()
