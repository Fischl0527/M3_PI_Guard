from __future__ import annotations

import copy

import experiments.paper_v2.gemini_public_technical_review_v5 as review


def _record() -> dict[str, object]:
    return {
        "record": {
            "work_key": "work-1",
            "operational_status": "runner_failure",
            "included_in_intention_to_treat": True,
            "provider_trace_bundle": {
                "bundle_status": "completed",
                "completed_request_count": 1,
                "trace_tail_sha256": "a" * 64,
            },
        }
    }


def _calls() -> list[dict[str, object]]:
    return [
        {
            "event_type": "started",
            "work_key": "work-1",
            "call_index": 1,
            "attempt_id": "attempt-1",
        },
        {
            "event_type": "failed",
            "work_key": "work-1",
            "call_index": 1,
            "attempt_id": "attempt-1",
            "error_type": "VigilLiveDependencyError",
        },
    ]


def test_exact_post_response_failure_is_reconciled_without_rewriting() -> None:
    calls = _calls()
    records = [_record()]

    observed = review.reconcile_post_response_calls(
        calls=calls, records=records
    )

    assert observed["terminal_event_count"] == 1
    assert observed["ordinary_completed_call_count"] == 0
    assert observed["reconciled_post_response_failure_count"] == 1
    assert observed[
        "per_work_terminal_count_matches_completed_trace_count"
    ] is True
    assert calls == _calls()
    assert records == [_record()]


def test_unknown_runtime_failure_is_not_reconciled() -> None:
    calls = _calls()
    calls[-1] = copy.deepcopy(calls[-1])
    calls[-1]["error_type"] = "UnexpectedRuntimeError"

    observed = review.reconcile_post_response_calls(
        calls=calls, records=[_record()]
    )

    assert observed["reconciled_post_response_failure_count"] == 0
    assert observed[
        "per_work_terminal_count_matches_completed_trace_count"
    ] is True


def test_transport_and_runtime_status_are_kept_distinct() -> None:
    observed = review.reconcile_post_response_calls(
        calls=_calls(), records=[_record()]
    )
    item = observed["reconciled_calls"][0]

    assert item["provider_transport_status"] == "completed_by_trace"
    assert item["runtime_status"] == "runner_failure_retained_in_itt"
    assert item["runtime_error_type"] == "VigilLiveDependencyError"
