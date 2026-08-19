"""Task Shield v1.6 correctness-first runtime.

This prospective runtime fixes three independently audited defects without
modifying the sealed v1.3--v1.5 implementations:

* the OpenAI-compatible client performs no hidden SDK retries;
* both JSON syntax and the complete extraction/scoring schema are validated
  inside one bounded two-attempt recovery loop;
* exhausted verifier failures on assistant or tool-originated content are
  converted to explicit fail-closed decisions, while trusted-user failures
  remain operational case failures.

Construction performs no network or model request.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any, Callable, Mapping, Sequence, TypeVar

from . import taskshield_paper_runtime as base


PATCH_VERSION = "m3-taskshield-paper-runtime-1.6-correctness"
DEFAULT_LOGICAL_ATTEMPTS = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0
DEFAULT_CASE_TIMEOUT_SECONDS = 600.0
UNTRUSTED_SOURCES = frozenset({"assistant", "tool_output"})
UNTRUSTED_EXTRACTION_FAILURE = (
    "verifier_failure_fail_closed_untrusted_content_suppressed"
)
SCORING_FAILURE_REASON = "verifier_scoring_failure_fail_closed_zero_contribution"

T = TypeVar("T")


class TaskShieldTransportTimeout(base.TaskShieldVerifierError):
    """Raised after the bounded verifier transport timeout budget is exhausted."""


class TaskShieldCaseDeadlineExceeded(base.TaskShieldVerifierError):
    """Raised when the frozen case-level deadline has been reached."""


def _timeout_classes() -> tuple[type[BaseException], ...]:
    """Return only explicitly supported timeout exception classes.

    There is intentionally no message or class-name matching here.  That was a
    source of ambiguity in earlier recovery code.
    """

    classes: list[type[BaseException]] = [TimeoutError]
    try:
        import httpx

        classes.append(httpx.TimeoutException)
    except ImportError:
        pass
    try:
        import openai

        classes.append(openai.APITimeoutError)
    except ImportError:
        pass
    return tuple(dict.fromkeys(classes))


def is_supported_timeout(exc: BaseException) -> bool:
    """Return whether *exc* is an explicitly supported transport timeout."""

    return isinstance(exc, _timeout_classes())


def _validate_extraction(rows: list[Any]) -> list[str]:
    if not all(isinstance(row, str) and row.strip() for row in rows):
        raise base.TaskShieldVerifierError(
            "instruction extraction requires only non-empty JSON strings"
        )
    return [str(row).strip() for row in rows]


def _validate_scores(rows: list[Any], *, expected_count: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise base.TaskShieldVerifierError("contribution rows must be JSON objects")
        raw_score = row.get("contribution_score", row.get("ContributeTo score"))
        try:
            score = float(raw_score)
        except (TypeError, ValueError) as exc:
            raise base.TaskShieldVerifierError(
                "contribution_score must be numeric"
            ) from exc
        if not 0.0 <= score <= 1.0:
            raise base.TaskShieldVerifierError(
                "contribution_score must be in [0, 1]"
            )
        normalized.append(
            {
                "user_task_instruction": str(row.get("user_task_instruction", "")),
                "contribution_score": score,
                "reason": str(row.get("reason", "")),
            }
        )
    if len(normalized) != expected_count:
        raise base.TaskShieldVerifierError(
            f"expected exactly {expected_count} contribution rows, got {len(normalized)}"
        )
    return normalized


def _zero_scores(tasks: Sequence[str], reason: str) -> tuple[list[dict[str, Any]], float]:
    return (
        [
            {
                "user_task_instruction": str(task),
                "contribution_score": 0.0,
                "reason": reason,
            }
            for task in tasks
        ],
        0.0,
    )


class TaskShieldPaperVerifierV16(base.TaskShieldPaperVerifier):
    """Verifier with a single visible retry owner and complete contracts."""

    def __init__(
        self,
        *,
        model_id: str,
        base_url: str,
        timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        epsilon: float,
        history_max_chars: int,
        trace: base.TaskShieldTrace,
        request_fn: Callable[[str, str], str] | None = None,
        logical_attempts: int = DEFAULT_LOGICAL_ATTEMPTS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        monotonic_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if logical_attempts < 1:
            raise ValueError("logical_attempts must be at least 1")
        if timeout_seconds <= 0 or retry_backoff_seconds < 0:
            raise ValueError("timeouts must be positive and backoff non-negative")
        self.model_id = model_id
        self.epsilon = float(epsilon)
        self.history_max_chars = int(history_max_chars)
        self.trace = trace
        self.logical_attempts = int(logical_attempts)
        self.retry_backoff_seconds = float(retry_backoff_seconds)
        self.request_timeout_seconds = float(timeout_seconds)
        self._monotonic = monotonic_fn
        self._sleep = sleep_fn
        self._case_deadline: float | None = None
        self._openai_max_retries = 0
        self._openai_client: Any | None = None

        if request_fn is not None:
            self._request_fn = request_fn
            return

        import openai

        client = openai.OpenAI(
            api_key="ollama-local",
            base_url=base_url,
            timeout=self.request_timeout_seconds,
            max_retries=0,
        )
        self._openai_client = client

        def request(system: str, user: str) -> str:
            timeout = min(self.request_timeout_seconds, self.remaining_case_seconds())
            if timeout <= 0:
                raise TaskShieldCaseDeadlineExceeded("case deadline reached before request")
            response = client.with_options(timeout=timeout, max_retries=0).chat.completions.create(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                model=model_id,
                temperature=0.0,
                seed=0,
            )
            return str(response.choices[0].message.content or "")

        self._request_fn = request

    def set_case_deadline(self, seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS) -> None:
        if seconds <= 0:
            raise ValueError("case deadline must be positive")
        self._case_deadline = self._monotonic() + float(seconds)

    def clear_case_deadline(self) -> None:
        self._case_deadline = None

    def remaining_case_seconds(self) -> float:
        if self._case_deadline is None:
            return self.request_timeout_seconds
        return max(0.0, self._case_deadline - self._monotonic())

    def _assert_case_deadline(self) -> None:
        if self._case_deadline is not None and self.remaining_case_seconds() <= 0:
            raise TaskShieldCaseDeadlineExceeded("case deadline of 600 seconds exceeded")

    @staticmethod
    def _recovery_prompt(user: str, *, expectation: str, error: str) -> str:
        return (
            user
            + "\n\nCONTRACT CORRECTION: The previous response was invalid: "
            + error
            + ". Return only "
            + expectation
            + ". Do not add markdown or explanation."
        )

    def _request_contract(
        self,
        *,
        kind: str,
        system: str,
        user: str,
        expectation: str,
        validator: Callable[[list[Any]], T],
    ) -> T:
        prompt = user
        last_error: Exception | None = None
        for attempt in range(1, self.logical_attempts + 1):
            self._assert_case_deadline()
            started = self._monotonic()
            trace_row: dict[str, Any] = {
                "kind": kind,
                "system_prompt": system,
                "user_prompt": prompt,
                "request_attempt": attempt,
                "logical_attempt_limit": self.logical_attempts,
                "expected_contract": expectation,
                "runtime_patch_version": PATCH_VERSION,
                "sdk_max_retries": 0,
                "raw_output": "",
            }
            try:
                raw = self._request_fn(system, prompt)
                trace_row["raw_output"] = raw
                trace_row["raw_output_logged_before_validation"] = True
                rows = base._strict_json_array(raw)
                value = validator(rows)
                trace_row.update(
                    {
                        "contract_valid": True,
                        "contract_retry": False,
                    }
                )
                return value
            except Exception as exc:
                last_error = exc
                supported_timeout = is_supported_timeout(exc)
                contract_failure = isinstance(exc, base.TaskShieldVerifierError)
                retryable = supported_timeout or contract_failure
                can_retry = retryable and attempt < self.logical_attempts
                trace_row.update(
                    {
                        "contract_valid": False,
                        "contract_retry": can_retry,
                        "transport_timeout": supported_timeout,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                if not retryable:
                    raise
                if not can_retry:
                    if supported_timeout:
                        raise TaskShieldTransportTimeout(
                            f"verifier timeout exhausted after {attempt} attempts"
                        ) from exc
                    raise
                prompt = self._recovery_prompt(
                    user,
                    expectation=expectation,
                    error=str(exc),
                )
                if self.retry_backoff_seconds:
                    remaining = self.remaining_case_seconds()
                    if remaining <= self.retry_backoff_seconds:
                        raise TaskShieldCaseDeadlineExceeded(
                            "case deadline reached during verifier retry backoff"
                        ) from exc
                    self._sleep(self.retry_backoff_seconds)
            finally:
                trace_row["duration_ms"] = round(
                    (self._monotonic() - started) * 1000.0,
                    6,
                )
                self.trace.model_requests.append(trace_row)
        raise base.TaskShieldVerifierError(str(last_error or "verifier contract failed"))

    def _request(self, kind: str, system: str, user: str) -> list[Any]:
        return self._request_contract(
            kind=kind,
            system=system,
            user=user,
            expectation="a valid JSON array",
            validator=lambda rows: rows,
        )

    def extract(self, *, content: str, source: str) -> list[str]:
        return self._request_contract(
            kind="instruction_extraction",
            system=base.EXTRACTION_SYSTEM_PROMPT,
            user=f"Source: {source}\nMessage:\n{content}",
            expectation="a JSON array containing only non-empty instruction strings",
            validator=_validate_extraction,
        )

    def _scores(
        self,
        *,
        proposal: str,
        source: str,
        history: Sequence[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], float]:
        if not self.trace.user_tasks:
            raise base.TaskShieldVerifierError("user task set is not initialized")
        expected_count = len(self.trace.user_tasks)
        user_prompt = (
            "Proposal source: "
            + source
            + "\nProposal: "
            + proposal
            + "\nTrusted user tasks: "
            + json.dumps(self.trace.user_tasks, ensure_ascii=False)
            + "\nConversation history:\n"
            + base.render_history(history, self.history_max_chars)
        )
        try:
            normalized = self._request_contract(
                kind="contribution_scoring",
                system=base.ALIGNMENT_SYSTEM_PROMPT,
                user=user_prompt,
                expectation=(
                    f"a JSON array of exactly {expected_count} objects; each object must "
                    "contain user_task_instruction, numeric contribution_score in [0,1], "
                    "and reason"
                ),
                validator=lambda rows: _validate_scores(
                    rows,
                    expected_count=expected_count,
                ),
            )
        except TaskShieldCaseDeadlineExceeded:
            raise
        except (base.TaskShieldVerifierError, TaskShieldTransportTimeout) as exc:
            reason = f"{SCORING_FAILURE_REASON}: {type(exc).__name__}: {exc}"
            self.trace.model_requests.append(
                {
                    "kind": "contribution_scoring_fail_closed",
                    "source": source,
                    "fail_closed": True,
                    "failure_class": type(exc).__name__,
                    "error": str(exc),
                    "runtime_patch_version": PATCH_VERSION,
                }
            )
            return _zero_scores(self.trace.user_tasks, reason)
        return normalized, sum(row["contribution_score"] for row in normalized)

    def check_content(
        self,
        *,
        content: str,
        source: str,
        history: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        try:
            return super().check_content(content=content, source=source, history=history)
        except TaskShieldCaseDeadlineExceeded:
            raise
        except (base.TaskShieldVerifierError, TaskShieldTransportTimeout) as exc:
            if source not in UNTRUSTED_SOURCES:
                raise
            row = {
                "source": source,
                "instructions": [],
                "checks": [],
                "misaligned": [UNTRUSTED_EXTRACTION_FAILURE],
                "verifier_failure_fail_closed": True,
                "failure_class": type(exc).__name__,
                "error": str(exc),
                "runtime_patch_version": PATCH_VERSION,
            }
            self.trace.content_checks.append(row)
            return row


def build_taskshield_pipeline_v16(freeze: Mapping[str, Any]):
    """Build a pipeline using v1.6 without mutating the sealed base module."""

    original = base.TaskShieldPaperVerifier
    base.TaskShieldPaperVerifier = TaskShieldPaperVerifierV16
    try:
        pipeline = base.build_taskshield_pipeline(freeze)
    finally:
        base.TaskShieldPaperVerifier = original
    pipeline.m3_taskshield_runtime_version = PATCH_VERSION
    return pipeline


def runtime_contract() -> dict[str, Any]:
    """Return the auditable non-model v1.6 runtime policy."""

    return {
        "patch_version": PATCH_VERSION,
        "logical_attempts": DEFAULT_LOGICAL_ATTEMPTS,
        "retry_backoff_seconds": DEFAULT_RETRY_BACKOFF_SECONDS,
        "request_timeout_seconds": DEFAULT_REQUEST_TIMEOUT_SECONDS,
        "case_timeout_seconds": DEFAULT_CASE_TIMEOUT_SECONDS,
        "sdk_max_retries": 0,
        "timeout_detection": "explicit_exception_types_only",
        "contract_validation": (
            "json_array_plus_extraction_strings_or_complete_scoring_schema_and_cardinality"
        ),
        "trusted_user_exhaustion": "operational_case_failure",
        "untrusted_exhaustion": "fail_closed_suppression_or_zero_contribution",
        "case_retry": False,
    }


def trace_snapshot(trace: base.TaskShieldTrace) -> dict[str, Any]:
    """Take an eager deep snapshot for both terminal success and failure rows."""

    return copy.deepcopy(trace.snapshot())
