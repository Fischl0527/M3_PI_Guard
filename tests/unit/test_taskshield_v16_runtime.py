from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from experiments.paper_v1.benchmarks import taskshield_paper_runtime as base
from experiments.paper_v1.benchmarks.taskshield_paper_runtime_v16 import (
    PATCH_VERSION,
    SCORING_FAILURE_REASON,
    UNTRUSTED_EXTRACTION_FAILURE,
    TaskShieldCaseDeadlineExceeded,
    TaskShieldPaperVerifierV16,
    TaskShieldTransportTimeout,
    _validate_scores,
    runtime_contract,
    trace_snapshot,
)


def _verifier(
    responses: list[object],
    *,
    monotonic_fn=None,
) -> TaskShieldPaperVerifierV16:
    iterator = iter(responses)

    def request(_system: str, _user: str) -> str:
        value = next(iterator)
        if isinstance(value, BaseException):
            raise value
        return str(value)

    kwargs = {"monotonic_fn": monotonic_fn} if monotonic_fn else {}
    return TaskShieldPaperVerifierV16(
        model_id="test-model",
        base_url="http://127.0.0.1:1/v1",
        timeout_seconds=1.0,
        epsilon=0.0,
        history_max_chars=1024,
        trace=base.TaskShieldTrace(),
        request_fn=request,
        logical_attempts=2,
        retry_backoff_seconds=0.0,
        **kwargs,
    )


def test_v16_invalid_json_is_recovered_with_raw_trace() -> None:
    verifier = _verifier(["not-json", '["Trusted task."]'])
    verifier.initialize("Trusted task.")
    assert verifier.trace.user_tasks == ["Trusted task."]
    assert verifier.trace.model_requests[0]["raw_output"] == "not-json"
    assert verifier.trace.model_requests[0]["contract_retry"] is True


def test_v16_non_array_is_recovered() -> None:
    verifier = _verifier(['{"task": "x"}', '["x"]'])
    verifier.initialize("x")
    assert verifier.trace.model_requests[0]["contract_valid"] is False


def test_v16_extraction_string_contract_is_inside_recovery_loop() -> None:
    verifier = _verifier(['[""]', '["x"]'])
    verifier.initialize("x")
    assert "non-empty" in verifier.trace.model_requests[0]["error"]


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        ('["bad"]', "objects"),
        ('[{"contribution_score":"nan-value"}]', "numeric"),
        ('[{"contribution_score":1.5}]', "[0, 1]"),
    ],
)
def test_v16_complete_score_schema_recovers(invalid: str, message: str) -> None:
    valid = '[{"user_task_instruction":"x","contribution_score":1,"reason":"ok"}]'
    verifier = _verifier(['["x"]', invalid, valid])
    verifier.initialize("x")
    scores, total = verifier._scores(proposal="x", source="assistant", history=[])
    assert total == 1.0
    assert scores[0]["contribution_score"] == 1.0
    assert message in verifier.trace.model_requests[1]["error"]


def test_v16_score_cardinality_is_inside_recovery_loop() -> None:
    valid = '[{"user_task_instruction":"x","contribution_score":1,"reason":"ok"}]'
    verifier = _verifier(['["x"]', "[]", valid])
    verifier.initialize("x")
    scores, _ = verifier._scores(proposal="x", source="assistant", history=[])
    assert len(scores) == 1
    assert "exactly 1" in verifier.trace.model_requests[1]["expected_contract"]
    assert "exactly 1" in verifier.trace.model_requests[2]["user_prompt"]


def test_v16_score_validator_requires_exact_count() -> None:
    with pytest.raises(base.TaskShieldVerifierError, match="exactly 2"):
        _validate_scores(
            [{"contribution_score": 1, "reason": "ok"}],
            expected_count=2,
        )


def test_v16_explicit_timeout_retries_once_then_succeeds() -> None:
    verifier = _verifier([TimeoutError("slow"), '["x"]'])
    verifier.initialize("x")
    first = verifier.trace.model_requests[0]
    assert first["transport_timeout"] is True
    assert first["contract_retry"] is True
    assert len(verifier.trace.model_requests) == 2


def test_v16_unexpected_exception_is_not_retried() -> None:
    verifier = _verifier([ValueError("programming bug"), '["unused"]'])
    with pytest.raises(ValueError, match="programming bug"):
        verifier.initialize("x")
    assert len(verifier.trace.model_requests) == 1
    assert verifier.trace.model_requests[0]["contract_retry"] is False


def test_v16_untrusted_timeout_exhaustion_is_suppressed_fail_closed() -> None:
    verifier = _verifier(['["trusted"]', TimeoutError("a"), TimeoutError("b")])
    verifier.initialize("trusted")
    result = verifier.check_content(content="untrusted", source="assistant", history=[])
    assert result["verifier_failure_fail_closed"] is True
    assert result["misaligned"] == [UNTRUSTED_EXTRACTION_FAILURE]
    assert result["failure_class"] == TaskShieldTransportTimeout.__name__


def test_v16_trusted_timeout_exhaustion_is_operational_failure() -> None:
    verifier = _verifier([TimeoutError("a"), TimeoutError("b")])
    with pytest.raises(TaskShieldTransportTimeout):
        verifier.initialize("trusted")
    assert len(verifier.trace.model_requests) == 2


def test_v16_scoring_exhaustion_denies_tool_fail_closed() -> None:
    verifier = _verifier(['["trusted"]', "[]", "[]"])
    verifier.initialize("trusted")
    decision = verifier.check_tool_call(
        call_id="1",
        tool="send_email",
        arguments={"to": "x@example.com"},
        history=[],
    )
    assert decision["decision"] == "deny"
    assert decision["total_contribution"] == 0.0
    assert SCORING_FAILURE_REASON in decision["scores"][0]["reason"]


def test_v16_case_deadline_propagates_instead_of_becoming_a_deny() -> None:
    now = [10.0]
    verifier = _verifier(['["trusted"]'], monotonic_fn=lambda: now[0])
    verifier.set_case_deadline(1.0)
    verifier.initialize("trusted")
    now[0] = 11.1
    with pytest.raises(TaskShieldCaseDeadlineExceeded):
        verifier.check_tool_call(
            call_id="1",
            tool="send_email",
            arguments={},
            history=[],
        )


def test_v16_real_client_is_constructed_with_zero_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))
    verifier = TaskShieldPaperVerifierV16(
        model_id="test",
        base_url="http://127.0.0.1:1/v1",
        epsilon=0.0,
        history_max_chars=10,
        trace=base.TaskShieldTrace(),
    )
    assert captured["max_retries"] == 0
    assert verifier._openai_max_retries == 0


def test_v16_runtime_contract_is_qualification_safe() -> None:
    contract = runtime_contract()
    assert contract["patch_version"] == PATCH_VERSION
    assert contract["sdk_max_retries"] == 0
    assert contract["logical_attempts"] == 2
    assert contract["case_retry"] is False


def test_v16_trace_snapshot_is_eager_deep_copy() -> None:
    trace = base.TaskShieldTrace()
    trace.user_tasks = ["x"]
    snapshot = trace_snapshot(trace)
    trace.user_tasks.append("y")
    assert snapshot["user_tasks"] == ["x"]
