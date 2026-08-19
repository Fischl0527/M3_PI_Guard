"""Task Shield v1.3 fail-closed scoring compatibility patch.

The v1.2 disclosed Task Shield reproduction intentionally failed a case when
the local verifier returned a contribution-scoring JSON array whose row count
did not exactly match the extracted trusted user-task count.  The first full
formal attempt exposed that this strict parser can terminate otherwise
scorable AgentDojo utility cases.

This module leaves the v1.2 hash-bound runtime untouched and installs a
process-local patch for the v1.3 runner only: contribution-scoring parse,
schema, score or cardinality errors are converted to one zero-contribution row
per trusted user task.  Tool calls/content are therefore denied or suppressed
instead of crashing the benchmark case.  Trusted task extraction remains strict.
"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping, Sequence

from . import taskshield_paper_runtime as base


PATCH_VERSION = "m3-paper-v1-taskshield-runtime-compat-1.3"
FAIL_CLOSED_REASON = "verifier_contribution_scoring_parse_or_cardinality_error_fail_closed"


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


def _scores_fail_closed(
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
    started = time.perf_counter()
    raw = self._request_fn(base.ALIGNMENT_SYSTEM_PROMPT, user_prompt)
    request_row: dict[str, Any] = {
        "kind": "contribution_scoring",
        "system_prompt": base.ALIGNMENT_SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "raw_output": raw,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 6),
        "runtime_patch_version": PATCH_VERSION,
    }
    try:
        rows = base._strict_json_array(raw)
    except base.TaskShieldVerifierError as exc:
        request_row["parse_error"] = str(exc)
        self.trace.model_requests.append(request_row)
        return _zero_scores(self.trace.user_tasks, FAIL_CLOSED_REASON + ": " + str(exc))

    self.trace.model_requests.append(request_row)
    normalized: list[dict[str, Any]] = []
    try:
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
    except (TypeError, ValueError, base.TaskShieldVerifierError) as exc:
        request_row["normalization_error"] = str(exc)
        return _zero_scores(self.trace.user_tasks, FAIL_CLOSED_REASON + ": " + str(exc))

    if len(normalized) != len(self.trace.user_tasks):
        request_row["cardinality_error"] = {
            "expected_rows": len(self.trace.user_tasks),
            "observed_rows": len(normalized),
        }
        return _zero_scores(
            self.trace.user_tasks,
            FAIL_CLOSED_REASON
            + f": expected {len(self.trace.user_tasks)} rows, observed {len(normalized)}",
        )
    return normalized, sum(row["contribution_score"] for row in normalized)


def install_fail_closed_scoring_patch() -> dict[str, Any]:
    if getattr(base.TaskShieldPaperVerifier, "__m3_taskshield_v13_patch__", False):
        return {"installed": False, "patch_version": PATCH_VERSION, "reason": "already_installed"}
    base.TaskShieldPaperVerifier._scores = _scores_fail_closed  # type: ignore[method-assign]
    base.TaskShieldPaperVerifier.__m3_taskshield_v13_patch__ = True
    return {
        "installed": True,
        "patch_version": PATCH_VERSION,
        "policy": "contribution_scoring_parse_schema_score_or_cardinality_errors_return_zero_scores",
    }
