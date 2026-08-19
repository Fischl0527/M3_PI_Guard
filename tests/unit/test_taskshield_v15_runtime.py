from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v1.benchmarks import taskshield_paper_runtime as base
from experiments.paper_v1.benchmarks.build_taskshield_paper_formal_freeze_v15 import (
    build_freeze,
)
from experiments.paper_v1.benchmarks.run_taskshield_paper_formal_v15 import run
from experiments.paper_v1.benchmarks.taskshield_paper_runtime_v15 import (
    PATCH_VERSION,
    UNTRUSTED_EXTRACTION_FAILURE,
    _check_content_fail_closed_v15,
    _request_with_contract_recovery,
    _scores_fail_closed_v15,
)


ROOT = Path(__file__).resolve().parents[2]


def _verifier(responses: list[str]) -> base.TaskShieldPaperVerifier:
    iterator = iter(responses)
    return base.TaskShieldPaperVerifier(
        model_id="test-model",
        base_url="http://127.0.0.1:1/v1",
        timeout_seconds=1.0,
        epsilon=0.0,
        history_max_chars=1024,
        trace=base.TaskShieldTrace(),
        request_fn=lambda _system, _user: next(iterator),
    )


def _install_for_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        base.TaskShieldPaperVerifier,
        "__m3_taskshield_v15_original_check_content__",
        base.TaskShieldPaperVerifier.check_content,
        raising=False,
    )
    monkeypatch.setattr(base.TaskShieldPaperVerifier, "_request", _request_with_contract_recovery)
    monkeypatch.setattr(base.TaskShieldPaperVerifier, "_scores", _scores_fail_closed_v15)
    monkeypatch.setattr(
        base.TaskShieldPaperVerifier,
        "check_content",
        _check_content_fail_closed_v15,
    )


def test_v15_logs_invalid_raw_output_before_contract_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_for_test(monkeypatch)
    monkeypatch.setenv("M3_TASKSHIELD_CONTRACT_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("M3_TASKSHIELD_RETRY_BACKOFF_SECONDS", "0")
    verifier = _verifier(["not-json", '["Do the task."]'])

    verifier.initialize("Do the task.")

    first = verifier.trace.model_requests[0]
    assert first["raw_output"] == "not-json"
    assert first["raw_output_logged_before_parse"] is True
    assert first["contract_valid"] is False
    assert first["contract_retry"] is True
    assert verifier.trace.model_requests[1]["contract_valid"] is True


def test_v15_untrusted_extraction_exhaustion_is_suppressed_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_for_test(monkeypatch)
    monkeypatch.setenv("M3_TASKSHIELD_CONTRACT_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("M3_TASKSHIELD_RETRY_BACKOFF_SECONDS", "0")
    verifier = _verifier(['["Trusted task."]', "bad-1", "bad-2"])
    verifier.initialize("Trusted task.")

    result = verifier.check_content(
        content="Untrusted assistant content",
        source="assistant",
        history=[],
    )

    assert result["verifier_failure_fail_closed"] is True
    assert result["misaligned"] == [UNTRUSTED_EXTRACTION_FAILURE]
    assert verifier.trace.model_requests[-1]["raw_output"] == "bad-2"
    assert verifier.trace.model_requests[-1]["contract_retry"] is False


def test_v15_trusted_extraction_remains_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_for_test(monkeypatch)
    monkeypatch.setenv("M3_TASKSHIELD_CONTRACT_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("M3_TASKSHIELD_RETRY_BACKOFF_SECONDS", "0")
    verifier = _verifier(["bad-1", "bad-2"])

    with pytest.raises(base.TaskShieldVerifierError, match="invalid JSON"):
        verifier.initialize("Trusted task.")

    assert len(verifier.trace.model_requests) == 2
    assert all(row["raw_output"] for row in verifier.trace.model_requests)


def test_v15_contribution_contract_exhaustion_returns_zero_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_for_test(monkeypatch)
    monkeypatch.setenv("M3_TASKSHIELD_CONTRACT_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("M3_TASKSHIELD_RETRY_BACKOFF_SECONDS", "0")
    verifier = _verifier(['["Trusted task."]', "bad-1", "bad-2"])
    verifier.initialize("Trusted task.")

    decision = verifier.check_tool_call(
        call_id="call-1",
        tool="send_email",
        arguments={"to": "attacker@example.com"},
        history=[],
    )

    assert decision["decision"] == "deny"
    assert decision["total_contribution"] == 0.0
    assert verifier.trace.model_requests[-1]["kind"] == "contribution_scoring_fail_closed"


def test_v15_freeze_hash_binds_audit_runtime_and_selection() -> None:
    manifest = build_freeze(
        public_freeze_path=ROOT
        / "protocols"
        / "paper_upgrade_v1"
        / "public_benchmark_formal_freeze_v2.json",
        model_registry_path=ROOT / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json",
        agentdojo_checkout=ROOT / "external" / "benchmarks" / "agentdojo",
        paper_path=ROOT / "external" / "baselines" / "task-shield-paper" / "2025.acl-long.1435.pdf",
        model_id="m3-paper-qwen3-8b-v1:latest",
    )

    assert manifest["schema_version"] == "paper-taskshield-reproduction-freeze-1.5"
    assert manifest["status"] == "completed_frozen_formal_protocol"
    assert manifest["task_shield"]["runtime_patch_version"] == PATCH_VERSION
    assert manifest["local_adapter"]["v15_contract_recovery_patch"] is True
    assert len(manifest["qualification_case_rows"]) == 12
    assert manifest["v15_change_contract"]["full_726_case_run_authorized"] is False
    assert str(ROOT) not in json.dumps(manifest, ensure_ascii=False)


def test_v15_runner_refuses_unapproved_full_formal_before_runtime_probe(
    tmp_path: Path,
) -> None:
    freeze = tmp_path / "freeze.json"
    freeze.write_text(
        json.dumps({"v15_change_contract": {"full_726_case_run_authorized": False}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="qualification only"):
        run(
            freeze_path=freeze,
            output_dir=tmp_path / "run",
            case_limit=None,
            case_ids=None,
            admit_formal=True,
            resume=False,
        )
