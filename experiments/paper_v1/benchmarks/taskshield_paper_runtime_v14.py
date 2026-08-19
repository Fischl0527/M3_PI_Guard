"""Task Shield paper-reproduction v1.4 runtime patch.

v1.4 composes the v1.3 fail-closed contribution-scoring patch with an explicit,
trace-logged retry policy for transient verifier-model transport timeouts.  It
does not retry cases, does not exclude failed rows, and does not alter trusted
task extraction or contribution semantics.
"""

from __future__ import annotations

import os
import time
from typing import Any

from . import taskshield_paper_runtime as base
from .taskshield_paper_runtime_v13 import (
    install_fail_closed_scoring_patch,
)


PATCH_VERSION = "m3-taskshield-paper-runtime-1.4-timeout-retry"
DEFAULT_TIMEOUT_RETRY_ATTEMPTS = 2
DEFAULT_TIMEOUT_RETRY_BACKOFF_SECONDS = 1.0
TIMEOUT_ERROR_NAMES = {
    "APITimeoutError",
    "ConnectTimeout",
    "PoolTimeout",
    "ReadTimeout",
    "TimeoutError",
    "TimeoutException",
    "WriteTimeout",
}


def _timeout_retry_attempts() -> int:
    try:
        return max(1, int(os.environ.get("M3_TASKSHIELD_TIMEOUT_RETRY_ATTEMPTS", "")))
    except ValueError:
        return DEFAULT_TIMEOUT_RETRY_ATTEMPTS


def _timeout_retry_backoff_seconds() -> float:
    try:
        return max(
            0.0,
            float(os.environ.get("M3_TASKSHIELD_TIMEOUT_RETRY_BACKOFF_SECONDS", "")),
        )
    except ValueError:
        return DEFAULT_TIMEOUT_RETRY_BACKOFF_SECONDS


def _is_timeout_exception(exc: BaseException) -> bool:
    if type(exc).__name__ in TIMEOUT_ERROR_NAMES:
        return True
    return any(parent.__name__ in TIMEOUT_ERROR_NAMES for parent in type(exc).mro())


def _request_with_timeout_retry(
    self: base.TaskShieldPaperVerifier,
    kind: str,
    system: str,
    user: str,
) -> list[Any]:
    original = getattr(
        base.TaskShieldPaperVerifier,
        "__m3_taskshield_v14_original_request__",
    )
    attempts = _timeout_retry_attempts()
    backoff_seconds = _timeout_retry_backoff_seconds()
    for attempt in range(1, attempts + 1):
        try:
            return original(self, kind, system, user)
        except Exception as exc:
            if not _is_timeout_exception(exc) or attempt >= attempts:
                raise
            self.trace.model_requests.append(
                {
                    "kind": kind,
                    "system_prompt": system,
                    "user_prompt": user,
                    "raw_output": "",
                    "elapsed_ms": 0.0,
                    "transport_retry": True,
                    "retry_attempt": attempt,
                    "max_attempts": attempts,
                    "backoff_seconds": backoff_seconds,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "runtime_patch_version": PATCH_VERSION,
                }
            )
            if backoff_seconds:
                time.sleep(backoff_seconds)
    raise AssertionError("unreachable timeout retry loop")


def install_timeout_retry_patch() -> dict[str, Any]:
    """Install v1.4 retry behavior and return a manifest-friendly summary."""

    v13_summary = install_fail_closed_scoring_patch()
    if not getattr(base.TaskShieldPaperVerifier, "__m3_taskshield_v14_patch__", False):
        base.TaskShieldPaperVerifier.__m3_taskshield_v14_original_request__ = (  # type: ignore[attr-defined]
            base.TaskShieldPaperVerifier._request
        )
        base.TaskShieldPaperVerifier._request = _request_with_timeout_retry  # type: ignore[method-assign]
        base.TaskShieldPaperVerifier.__m3_taskshield_v14_patch__ = True
    return {
        "patch_version": PATCH_VERSION,
        "v13_patch": v13_summary,
        "timeout_retry_attempts": _timeout_retry_attempts(),
        "timeout_retry_backoff_seconds": _timeout_retry_backoff_seconds(),
        "retry_scope": "verifier_model_transport_timeout_only",
        "case_retry_policy": "no_case_retry_or_failed_row_exclusion",
        "trace_logged": True,
    }
