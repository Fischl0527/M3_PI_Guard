"""Task Shield v1.5 post-hoc verifier-contract recovery patch.

The patch is prospective and process-local. It preserves v1.3 fail-closed
contribution scoring and v1.4 bounded timeout recovery, logs every raw verifier
output before parsing, retries invalid JSON/non-array contracts, and suppresses
untrusted content if extraction still fails. Trusted-user extraction stays
strict. No benchmark case is retried or excluded.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Mapping, Sequence

from . import taskshield_paper_runtime as base
from .taskshield_paper_runtime_v13 import (
    FAIL_CLOSED_REASON,
    _zero_scores,
    install_fail_closed_scoring_patch,
)
from .taskshield_paper_runtime_v14 import _is_timeout_exception


PATCH_VERSION = "m3-taskshield-paper-runtime-1.5-contract-recovery"
DEFAULT_TIMEOUT_RETRY_ATTEMPTS = 2
DEFAULT_CONTRACT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0
UNTRUSTED_SOURCES = frozenset({"assistant", "tool_output"})
UNTRUSTED_EXTRACTION_FAILURE = (
    "verifier_contract_failure_fail_closed_untrusted_content_suppressed"
)


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, "")))
    except ValueError:
        return default


def _nonnegative_float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, "")))
    except ValueError:
        return default


def _timeout_attempts() -> int:
    return _positive_int_env(
        "M3_TASKSHIELD_TIMEOUT_RETRY_ATTEMPTS",
        DEFAULT_TIMEOUT_RETRY_ATTEMPTS,
    )


def _contract_attempts() -> int:
    return _positive_int_env(
        "M3_TASKSHIELD_CONTRACT_RETRY_ATTEMPTS",
        DEFAULT_CONTRACT_RETRY_ATTEMPTS,
    )


def _retry_backoff_seconds() -> float:
    return _nonnegative_float_env(
        "M3_TASKSHIELD_RETRY_BACKOFF_SECONDS",
        DEFAULT_RETRY_BACKOFF_SECONDS,
    )


def _request_with_contract_recovery(
    self: base.TaskShieldPaperVerifier,
    kind: str,
    system: str,
    user: str,
) -> list[Any]:
    """Request, trace raw output before parse, and recover within frozen bounds."""

    timeout_failures = 0
    contract_failures = 0
    request_attempt = 0
    backoff_seconds = _retry_backoff_seconds()
    while True:
        request_attempt += 1
        started = time.perf_counter()
        try:
            raw = self._request_fn(system, user)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
            timeout = _is_timeout_exception(exc)
            if timeout:
                timeout_failures += 1
            can_retry = timeout and timeout_failures < _timeout_attempts()
            self.trace.model_requests.append(
                {
                    "kind": kind,
                    "system_prompt": system,
                    "user_prompt": user,
                    "raw_output": "",
                    "elapsed_ms": elapsed_ms,
                    "request_attempt": request_attempt,
                    "transport_error": True,
                    "transport_retry": can_retry,
                    "timeout_failure_count": timeout_failures,
                    "timeout_attempt_limit": _timeout_attempts(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "runtime_patch_version": PATCH_VERSION,
                }
            )
            if not can_retry:
                raise
            if backoff_seconds:
                time.sleep(backoff_seconds)
            continue

        request_row: dict[str, Any] = {
            "kind": kind,
            "system_prompt": system,
            "user_prompt": user,
            "raw_output": raw,
            "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 6),
            "request_attempt": request_attempt,
            "raw_output_logged_before_parse": True,
            "runtime_patch_version": PATCH_VERSION,
        }
        # Append the same mutable row before parsing. A parse error is then added
        # to the already-retained trace row, preserving the raw evidence.
        self.trace.model_requests.append(request_row)
        try:
            value = base._strict_json_array(raw)
        except base.TaskShieldVerifierError as exc:
            contract_failures += 1
            can_retry = contract_failures < _contract_attempts()
            request_row.update(
                {
                    "contract_valid": False,
                    "contract_retry": can_retry,
                    "contract_failure_count": contract_failures,
                    "contract_attempt_limit": _contract_attempts(),
                    "parse_error": str(exc),
                }
            )
            if not can_retry:
                raise
            if backoff_seconds:
                time.sleep(backoff_seconds)
            continue
        request_row["contract_valid"] = True
        return value


def _record_scoring_fail_closed(
    self: base.TaskShieldPaperVerifier,
    *,
    error: Exception,
    source: str,
) -> tuple[list[dict[str, Any]], float]:
    self.trace.model_requests.append(
        {
            "kind": "contribution_scoring_fail_closed",
            "source": source,
            "raw_output": "",
            "error_type": type(error).__name__,
            "error": str(error),
            "runtime_patch_version": PATCH_VERSION,
            "fail_closed": True,
        }
    )
    return _zero_scores(
        self.trace.user_tasks,
        FAIL_CLOSED_REASON + ": " + str(error),
    )


def _scores_fail_closed_v15(
    self: base.TaskShieldPaperVerifier,
    *,
    proposal: str,
    source: str,
    history: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], float]:
    if not self.trace.user_tasks:
        raise base.TaskShieldVerifierError("user task set is not initialized")

    task_text = json.dumps(self.trace.user_tasks, ensure_ascii=False)
    history_text = base.render_history(history, self.history_max_chars)
    user_prompt = (
        "Proposal source: "
        + source
        + "\nProposal: "
        + proposal
        + "\nTrusted user tasks: "
        + task_text
        + "\nConversation history:\n"
        + history_text
    )
    try:
        rows = self._request(
            "contribution_scoring",
            base.ALIGNMENT_SYSTEM_PROMPT,
            user_prompt,
        )
        normalized: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise base.TaskShieldVerifierError("contribution rows must be objects")
            raw_score = row.get("contribution_score", row.get("ContributeTo score"))
            score = float(raw_score)
            if not 0.0 <= score <= 1.0:
                raise base.TaskShieldVerifierError("contribution score must be in [0, 1]")
            normalized.append(
                {
                    "user_task_instruction": str(row.get("user_task_instruction", "")),
                    "contribution_score": score,
                    "reason": str(row.get("reason", "")),
                }
            )
        if len(normalized) != len(self.trace.user_tasks):
            raise base.TaskShieldVerifierError(
                "one contribution row is required per user task"
            )
    except (Exception,) as exc:
        return _record_scoring_fail_closed(self, error=exc, source=source)
    return normalized, sum(row["contribution_score"] for row in normalized)


def _check_content_fail_closed_v15(
    self: base.TaskShieldPaperVerifier,
    *,
    content: str,
    source: str,
    history: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    original = getattr(
        base.TaskShieldPaperVerifier,
        "__m3_taskshield_v15_original_check_content__",
    )
    try:
        return original(self, content=content, source=source, history=history)
    except base.TaskShieldVerifierError as exc:
        if source not in UNTRUSTED_SOURCES:
            raise
        row = {
            "source": source,
            "instructions": [],
            "checks": [],
            "misaligned": [UNTRUSTED_EXTRACTION_FAILURE],
            "verifier_failure_fail_closed": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "runtime_patch_version": PATCH_VERSION,
        }
        self.trace.content_checks.append(row)
        return row


def install_contract_recovery_patch() -> dict[str, Any]:
    """Install the v1.5 process-local behavior and return its exact policy."""

    v13_summary = install_fail_closed_scoring_patch()
    installed = not getattr(
        base.TaskShieldPaperVerifier,
        "__m3_taskshield_v15_patch__",
        False,
    )
    if installed:
        base.TaskShieldPaperVerifier.__m3_taskshield_v15_original_check_content__ = (  # type: ignore[attr-defined]
            base.TaskShieldPaperVerifier.check_content
        )
        base.TaskShieldPaperVerifier._request = _request_with_contract_recovery  # type: ignore[method-assign]
        base.TaskShieldPaperVerifier._scores = _scores_fail_closed_v15  # type: ignore[method-assign]
        base.TaskShieldPaperVerifier.check_content = _check_content_fail_closed_v15  # type: ignore[method-assign]
        base.TaskShieldPaperVerifier.__m3_taskshield_v15_patch__ = True
    return {
        "installed": installed,
        "patch_version": PATCH_VERSION,
        "v13_patch": v13_summary,
        "timeout_retry_attempts": _timeout_attempts(),
        "contract_retry_attempts": _contract_attempts(),
        "retry_backoff_seconds": _retry_backoff_seconds(),
        "raw_output_logged_before_parse": True,
        "trusted_user_extraction_policy": "strict_case_failure_after_exhaustion",
        "untrusted_content_policy": "fail_closed_suppress_after_exhaustion",
        "contribution_scoring_policy": "fail_closed_zero_after_exhaustion",
        "case_retry_policy": "no_case_retry_or_failed_row_exclusion",
    }
