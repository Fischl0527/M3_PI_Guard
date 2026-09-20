"""Standalone Gemini recovery; immutable old results, no DeepSeek dispatch."""

from __future__ import annotations

import copy
import argparse
import json
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from experiments.paper_v2.correctness_plan_v1 import OUTPUT, read_jsonl
from experiments.paper_v2.correctness_provider_v1 import (
    DevelopmentRequestClient,
    RequestPacer,
    append_row,
    now,
)
from experiments.paper_v2.correctness_runner_v1 import (
    critical_error,
    credential,
    execute_one,
    model_lock,
)
from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime
from experiments.paper_v2.live_condition_runtime import parse_strict_tool_proposal
from m3_core.project_config import parse_env_file, resolve_config_path

PROFILE = "gemini_recovery_v1"
RECOVERY_OUTPUT = OUTPUT / PROFILE


class ServiceBackoff:
    """Scheduling metadata only; HTTP clients retain zero automatic retries."""

    def __init__(self):
        self.consecutive_503 = 0
        self.delay_seconds = 0

    def observe(self, requests):
        for request in requests:
            status = request.get("http_status")
            if status == 429:
                return "provider_429"
            if status == 503:
                self.consecutive_503 += 1
                if self.consecutive_503 >= 5:
                    return "five_consecutive_503"
                self.delay_seconds = (60, 120, 240, 300)[self.consecutive_503 - 1]
            elif isinstance(status, int) and 200 <= status < 300:
                self.consecutive_503 = 0
                self.delay_seconds = 0
        return None


def has_response(row: dict[str, Any]) -> bool:
    return bool(
        row.get("response_obtained")
        or any(
            r.get("response_received") or r.get("provider_response_id")
            for r in row.get("provider_requests", [])
        )
    )


def select_pending(plan, old_rows, recovery_rows):
    """Return original-order (item, attempt, remaining_calls) without mutation."""
    original = {r["work_key"]: r for r in old_rows}
    if len(original) != len(old_rows):
        raise ValueError("duplicate original Gemini work key")
    eligible = {}
    for item in plan:
        if item["model_group"] != "gemini_flash":
            continue
        old = original[item["work_key"]]
        if has_response(old):
            continue
        calls = len(old.get("provider_requests", []))
        if old["operational_status"] == "not_run" and old["attempt"] == 0 and not calls:
            eligible[item["work_key"]] = (item, old, 1, 0)
        elif (
            old["attempt"] == 1
            and calls
            and all(r.get("http_status") == 503 for r in old["provider_requests"])
        ):
            eligible[item["work_key"]] = (item, old, 2, calls)
        else:
            raise ValueError("original item outside approved recovery scope")
    latest = {}
    for row in recovery_rows:
        key = row["work_key"]
        if key not in eligible:
            raise ValueError("recovery repeated protected or unknown work key")
        _, _, first, _ = eligible[key]
        prior = latest.get(key)
        expected = int(prior["attempt"]) + 1 if prior else first
        if (
            type(row.get("attempt")) is not int
            or row.get("attempt") != expected
            or expected > 2
        ):
            raise ValueError("invalid recovery attempt")
        if prior and (
            has_response(prior) or prior.get("operational_status") == "completed"
        ):
            raise ValueError("response-bearing work key repeated")
        if (
            row.get("generation_profile_id") != PROFILE
            or row.get("max_tokens") != 2048
            or row.get("reasoning_effort") != "low"
        ):
            raise ValueError("recovery configuration drift")
        latest[key] = row
    result = []
    for key, (item, old, first, old_calls) in eligible.items():
        rows = [r for r in recovery_rows if r["work_key"] == key]
        used = old_calls + sum(len(r.get("provider_requests", [])) for r in rows)
        if used > 8:
            raise ValueError("cumulative request cap exceeded")
        previous = latest.get(key)
        if previous and (
            has_response(previous)
            or previous["attempt"] >= 2
            or previous["operational_status"] == "completed"
        ):
            continue
        if used == 8:
            continue
        prepared = copy.deepcopy(item)
        prepared.update(
            generation_profile_id=PROFILE,
            recovery_batch_id=PROFILE,
            max_tokens=2048,
            reasoning_effort="low",
            prior_operational_status=old["operational_status"],
            original_generation_profile_id="legacy_512",
            prior_provider_call_count=used,
            max_provider_calls_remaining=8 - used,
        )
        result.append(
            (prepared, int(previous["attempt"]) + 1 if previous else first, 8 - used)
        )
    return result


DIAGNOSTIC_ACTIONS = (
    {"tool": "read_file", "arguments": {"path": "sandbox/public/diagnostic.txt"}},
    {
        "tool": "write_file",
        "arguments": {"path": "sandbox/public/diagnostic.txt", "content": "SAFE"},
    },
    {"tool": "final", "arguments": {"answer": "SAFE"}},
)


def diagnostics_passed(rows):
    expected = {f"gemini-recovery-diagnostic-{i}" for i in range(6)}
    return (
        len(rows) == 6
        and {r.get("diagnostic_id") for r in rows} == expected
        and all(
            r.get("passed") is True and r.get("generation_profile_id") == PROFILE
            for r in rows
        )
    )


def run_diagnostics(
    api_key,
    *,
    output=RECOVERY_OUTPUT,
    client_factory=DevelopmentRequestClient,
    interval=15,
):
    """Six independently logged synthetic proposals, never execute a tool."""
    output = Path(output)
    raw = output / "diagnostics.jsonl"
    with model_lock(output / "internal/runner.lock"):
        history = read_jsonl(raw)
        if any(not row.get("passed") for row in history):
            return {
                "passed": False,
                "reason": "existing_diagnostic_failure",
                "records": len(history),
            }
        known = {row["diagnostic_id"] for row in history}
        expected = {f"gemini-recovery-diagnostic-{i}" for i in range(6)}
        if len(known) != len(history) or not known <= expected:
            raise ValueError("invalid diagnostic history")
        stop = threading.Event()
        pacer = RequestPacer(interval, stop)
        for index in range(6):
            key = f"gemini-recovery-diagnostic-{index}"
            if key in known:
                continue
            action = DIAGNOSTIC_ACTIONS[index // 2]
            trace = output / "internal/diagnostics" / f"{key}.jsonl"
            if trace.exists():
                raise RuntimeError("open diagnostic trace requires diagnosis")
            client = client_factory(
                model_group="gemini_flash",
                model="gemini-3.6-flash",
                api_key=api_key,
                benchmark="m3-v2",
                work_key=key,
                attempt=1,
                trace_path=trace,
                pacer=pacer,
                generation_profile=PROFILE,
                max_provider_calls=1,
            )
            passed, failure = False, None
            try:
                completion = client.complete(
                    [
                        {
                            "role": "system",
                            "content": "Return only one JSON action proposal. Do not execute any action.",
                        },
                        {
                            "role": "user",
                            "content": "Return exactly this JSON proposal: "
                            + json.dumps(action),
                        },
                    ]
                )
                schema = {
                    action["tool"]: {
                        "arguments": {
                            name: {"type": "string", "required": True}
                            for name in action["arguments"]
                        }
                    }
                }
                parsed = parse_strict_tool_proposal(
                    completion.text, tool_schemas=schema
                )
                passed = (
                    completion.finish_reason == "stop"
                    and parsed.tool == action["tool"]
                    and parsed.arguments == action["arguments"]
                )
                if not passed:
                    failure = "UnexpectedOrTruncatedDiagnostic"
            except Exception as exc:
                failure = type(exc).__name__
            row = {
                "diagnostic_id": key,
                "action_kind": action["tool"],
                "repetition": index % 2 + 1,
                "generation_profile_id": PROFILE,
                "max_tokens": 2048,
                "reasoning_effort": "low",
                "passed": passed,
                "failure_class": failure,
                "provider_requests": copy.deepcopy(client.requests),
                "recorded_at": now(),
            }
            append_row(raw, row)
            history.append(row)
            print(
                json.dumps(
                    {
                        "diagnostic": index + 1,
                        "passed": passed,
                        "failure_class": failure,
                    }
                ),
                flush=True,
            )
            if not passed:
                break
        return {"passed": diagnostics_passed(history), "records": len(history)}


def bounded_sleep(seconds):
    # Short chunks keep interrupt/termination responsive during provider backoff.
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(min(15, max(0, deadline - time.monotonic())))


def record_issue(row):
    issue = critical_error(row)
    if issue:
        return issue
    for request in row.get("provider_requests", []):
        if request.get("provider_tools_enabled") or request.get(
            "external_effects_enabled"
        ):
            return "external_safety_violation"
        if request.get("response_received") and (
            not request.get("provider_response_id")
            or request.get("returned_model") != "gemini-3.6-flash"
        ):
            return "response_identity_incomplete"
        if not request.get("local_request_id") or not request.get("payload_sha256"):
            return "missing_request_identity"
    return None


def technical_prefix(plan, old_rows, new_rows):
    """No unsafe/task-completion outcome participates in expansion."""
    prior = {r["work_key"]: r for r in old_rows}
    latest = {r["work_key"]: r for r in new_rows}
    pending = {r["work_key"] for r, _, _ in select_pending(plan, old_rows, new_rows)}
    keys = {
        r["work_key"]
        for r in plan
        if r["model_group"] == "gemini_flash" and r["formal_prefix"]
    }
    errors = defaultdict(set)
    for key in keys:
        row = prior[key] if has_response(prior[key]) else latest.get(key)
        if row is None or key in pending:
            return False
        if record_issue(row):
            return False
        if (
            row.get("operational_status") in {"runner_failure", "provider_failure"}
            and row.get("failure_class") != "ServiceUnavailable"
        ):
            errors[str(row.get("failure_class"))].add(row["case_id"])
    return not any(len(cases) >= 2 for cases in errors.values())


def run_recovery(
    api_key,
    *,
    old_root=OUTPUT,
    output=RECOVERY_OUTPUT,
    prefix_only=False,
    client_factory=DevelopmentRequestClient,
    runtime=None,
    interval=15,
    sleeper=bounded_sleep,
):
    """Explicit bounded attempts, no automatic HTTP retry or other-model jobs."""
    old_root, output = Path(old_root), Path(output)
    if output.resolve() == old_root.resolve():
        raise ValueError("recovery output must be separate from historical output")
    plan_path = old_root / "plan.jsonl"
    plan = read_jsonl(plan_path)
    original = read_jsonl(old_root / "gemini_flash/raw_records.jsonl")
    raw_path = output / "raw_records.jsonl"
    with model_lock(output / "internal/runner.lock"):
        if not diagnostics_passed(read_jsonl(output / "diagnostics.jsonl")):
            raise RuntimeError("six successful diagnostics required")
        history = read_jsonl(raw_path)
        pending = select_pending(plan, original, history)
        # Fail before sending any request if an interrupted attempt lacks raw closure.
        for item, attempt, _ in pending:
            trace = (
                output
                / "internal/gemini_flash"
                / f"{item['work_key']}.attempt{attempt}.jsonl"
            )
            if trace.exists():
                raise RuntimeError("open request trace requires diagnosis")
        gemini_plan = [r for r in plan if r["model_group"] == "gemini_flash"]
        active_runtime = runtime or CorrectnessRuntime(
            plan_path=plan_path, execution_identity=gemini_plan[0]["execution_identity"]
        )
        stop = threading.Event()
        pacer = RequestPacer(interval, stop)
        backoff = ServiceBackoff()
        error_cases = defaultdict(set)
        reason = None
        for row in history:
            reason = record_issue(row) or reason
            if row.get("operational_status") in {
                "runner_failure",
                "provider_failure",
            } and row.get("failure_class") not in {
                "ServiceUnavailable",
                "ProviderTransportError",
                "DispatchStopped",
            }:
                error_cases[str(row.get("failure_class"))].add(row["case_id"])
        if any(len(cases) >= 2 for cases in error_cases.values()):
            reason = reason or "repeated_system_error"
        # A new invocation is an explicit continuation after diagnosis; 503 streak
        # is local to this invocation, but logical attempts/call budgets persist.
        for is_prefix in (True, False):
            if reason or (prefix_only and not is_prefix):
                break
            if not is_prefix and not technical_prefix(plan, original, history):
                reason = "prefix_not_qualified"
                break
            batch = [
                (r, a, cap)
                for r, a, cap in pending
                if bool(r["formal_prefix"]) == is_prefix
            ]
            for item, attempt, remaining in batch:
                while True:
                    if backoff.delay_seconds:
                        print(
                            json.dumps({"service_wait_seconds": backoff.delay_seconds}),
                            flush=True,
                        )
                        sleeper(backoff.delay_seconds)
                        backoff.delay_seconds = 0

                    def factory(**kwargs):
                        return client_factory(
                            **kwargs,
                            generation_profile=PROFILE,
                            max_provider_calls=remaining,
                        )

                    row = execute_one(
                        item,
                        attempt,
                        runtime=active_runtime,
                        api_key=api_key,
                        pacer=pacer,
                        output=output,
                        client_factory=factory,
                    )
                    requests = row["provider_requests"]
                    is_503 = bool(requests) and requests[-1].get("http_status") == 503
                    if is_503:
                        row["original_failure_class"] = row.get("failure_class")
                        row["failure_class"] = "ServiceUnavailable"
                        row["failure_stage"] = "provider_service"
                        row["operational_status"] = "provider_failure"
                    row["cumulative_provider_call_count"] = item[
                        "prior_provider_call_count"
                    ] + len(requests)
                    append_row(raw_path, row)
                    history.append(row)
                    reason = record_issue(row) or backoff.observe(requests)
                    if (
                        not reason
                        and row["operational_status"]
                        in {"runner_failure", "provider_failure"}
                        and not is_503
                    ):
                        statuses = {r.get("http_status") for r in requests}
                        if not has_response(row):
                            reason = "no_response_requires_diagnosis"
                        elif any(s in {400, 401, 403, 404, 422} for s in statuses):
                            reason = "provider_configuration_rejected"
                        else:
                            error_cases[str(row.get("failure_class"))].add(
                                row["case_id"]
                            )
                            if len(error_cases[str(row.get("failure_class"))]) >= 2:
                                reason = "repeated_system_error"
                    print(
                        json.dumps(
                            {
                                "recovery_records": len(history),
                                "work_key": item["work_key"],
                                "attempt": attempt,
                                "status": row["operational_status"],
                                "stop_reason": reason,
                            }
                        ),
                        flush=True,
                    )
                    if reason:
                        break
                    # Only diagnosed service-unavailable failures are rescheduled
                    # within this invocation; other engineering faults pause first.
                    retry = [
                        t
                        for t in select_pending(plan, original, history)
                        if t[0]["work_key"] == item["work_key"]
                    ]
                    if not is_503 or not retry:
                        break
                    item, attempt, remaining = retry[0]
                if reason:
                    break
        pending_after = select_pending(plan, original, history)
        all_eligible = select_pending(plan, original, [])
        touched = {r["work_key"] for r in history}
        result = {
            "state": "paused"
            if reason
            else ("prefix_complete" if prefix_only and pending_after else "completed"),
            "stop_reason": reason,
            "profile": PROFILE,
            "planned_recovery": len(all_eligible),
            "attempt_records": len(history),
            "touched_work_keys": len(touched),
            "pending_work_keys": len(pending_after),
            "recorded_at": now(),
            "not_executed": [
                {
                    "work_key": r["work_key"],
                    "next_attempt": a,
                    "reason": reason or "prefix_only",
                }
                for r, a, _ in pending_after
            ],
        }
        if pending_after and not prefix_only and not reason:
            result["state"] = "paused"
            result["stop_reason"] = "unresolved_no_response_items"
        (output / "run_status.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--diagnostics", action="store_true")
    mode.add_argument("--prefix-only", action="store_true")
    mode.add_argument("--resume-pending-only", action="store_true")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    values = parse_env_file(resolve_config_path(args.config))
    try:
        api_key = credential(values, "gemini_flash")
        result = (
            run_diagnostics(api_key)
            if args.diagnostics
            else run_recovery(api_key, prefix_only=args.prefix_only)
        )
        if args.diagnostics and not result["passed"]:
            pending = select_pending(
                read_jsonl(OUTPUT / "plan.jsonl"),
                read_jsonl(OUTPUT / "gemini_flash/raw_records.jsonl"),
                read_jsonl(RECOVERY_OUTPUT / "raw_records.jsonl"),
            )
            status = {
                "state": "paused",
                "stop_reason": "diagnostics_not_passed",
                "profile": PROFILE,
                "planned_recovery": 283,
                "pending_work_keys": len(pending),
                "recorded_at": now(),
                "not_executed": [
                    {
                        "work_key": r["work_key"],
                        "next_attempt": a,
                        "reason": "diagnostics_not_passed",
                    }
                    for r, a, _ in pending
                ],
            }
            (RECOVERY_OUTPUT / "run_status.json").write_text(
                json.dumps(status, indent=2) + "\n", encoding="utf-8"
            )
        print(
            json.dumps(
                {k: v for k, v in result.items() if k != "not_executed"},
                ensure_ascii=False,
            ),
            flush=True,
        )
    except Exception as exc:
        # No error message/context/credential or request content is published.
        print(
            json.dumps(
                {"state": "requires_diagnosis", "error_class": type(exc).__name__}
            ),
            flush=True,
        )
        raise SystemExit(2) from None
    finally:
        values.clear()


if __name__ == "__main__":
    main()
