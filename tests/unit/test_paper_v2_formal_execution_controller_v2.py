from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import experiments.paper_v2.formal_execution_controller_v2 as controller_module
from experiments.paper_v2.formal_execution_controller_v2 import (
    ACTIVE_STATUS,
    FormalExecutionControllerV2Error,
    PilotExecutionPermit,
    _load_jsonl,
    _manifest_sha256,
    _qualification_active_manifest,
    _selected_work_item,
    authorize_single_pilot,
    build_admission_candidate,
    build_controller_qualification,
    execute_authorized_single_pilot,
    validate_admission_manifest,
    verify_admission_candidate,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    _as_official_receipt,
    _fixture_client,
)


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_frozen_candidate_reproduces_and_cannot_authorize() -> None:
    value = verify_admission_candidate()
    assert value == build_admission_candidate()
    assert value["status"] == "candidate_pending_owner_activation"
    assert value["artifact_role"] == "owner_review_candidate"
    assert value["authorization"]["candidate_only"] is True
    assert value["authorization"]["execution_authorized"] is False
    assert value["authorization"]["formal_matrix_authorized"] is False
    assert value["authorization"]["result_admission_authorized"] is False
    assert value["evidence_boundary"]["credentials_read_while_building"] is False
    assert value["evidence_boundary"]["network_calls_while_building"] == 0


def test_missing_active_manifest_rejects_before_credentials(
    tmp_path: Path,
) -> None:
    reads = 0

    def credential_loader() -> dict[str, str]:
        nonlocal reads
        reads += 1
        return {}

    with pytest.raises(
        FormalExecutionControllerV2Error,
        match="active one-pilot admission manifest is missing",
    ):
        execute_authorized_single_pilot(
            tmp_path / "missing.json",
            credential_loader=credential_loader,
        )
    assert reads == 0


def test_candidate_cannot_be_used_as_active_manifest(
    tmp_path: Path,
) -> None:
    candidate = build_admission_candidate()
    candidate_path = tmp_path / "candidate.json"
    _write(candidate_path, candidate)
    with pytest.raises(
        FormalExecutionControllerV2Error,
        match="single_pilot_execution_authorization",
    ):
        authorize_single_pilot(
            candidate_path,
            candidate_path=candidate_path,
        )


def test_active_scope_drift_rejects_before_output_or_credentials(
    tmp_path: Path,
) -> None:
    candidate = build_admission_candidate()
    candidate_path = tmp_path / "candidate.json"
    _write(candidate_path, candidate)
    active = _qualification_active_manifest(candidate)
    active["scope"]["work_item"]["work_key"] = "0" * 64
    active["scope_sha256"] = sha256_canonical_json(active["scope"])
    active["manifest_sha256"] = _manifest_sha256(active)
    active_path = tmp_path / "active.json"
    _write(active_path, active)
    reads = 0

    def credential_loader() -> dict[str, str]:
        nonlocal reads
        reads += 1
        return {}

    with pytest.raises(
        FormalExecutionControllerV2Error,
        match="does not bind the frozen candidate",
    ):
        execute_authorized_single_pilot(
            active_path,
            candidate_path=candidate_path,
            credential_loader=credential_loader,
        )
    assert reads == 0


def test_existing_single_use_output_rejects_before_credentials(
    tmp_path: Path,
) -> None:
    candidate = build_admission_candidate()
    candidate_path = tmp_path / "candidate.json"
    _write(candidate_path, candidate)
    active = _qualification_active_manifest(candidate)
    active_path = tmp_path / "active.json"
    _write(active_path, active)
    trace_path = Path(
        candidate["scope"]["outputs"]["provider_trace_path"]
    ).resolve()
    reads = 0

    def credential_loader() -> dict[str, str]:
        nonlocal reads
        reads += 1
        return {}

    with pytest.raises(
        FormalExecutionControllerV2Error,
        match="single-use pilot output already exists",
    ):
        execute_authorized_single_pilot(
            active_path,
            candidate_path=candidate_path,
            credential_loader=credential_loader,
            path_exists=lambda path: path.name == trace_path.name,
        )
    assert reads == 0


def test_active_fixture_yields_one_nonsecret_permit(
    tmp_path: Path,
) -> None:
    candidate = build_admission_candidate()
    candidate_path = tmp_path / "candidate.json"
    _write(candidate_path, candidate)
    active = _qualification_active_manifest(candidate)
    assert active["status"] == ACTIVE_STATUS
    active_path = tmp_path / "active.json"
    _write(active_path, active)
    permit = authorize_single_pilot(
        active_path,
        candidate_path=candidate_path,
        path_exists=lambda _path: False,
    )
    assert permit.work_item["work_key"] == candidate["scope"]["work_item"][
        "work_key"
    ]
    assert permit.work_item["condition_id"] == "no_defense"
    assert permit.work_item["evaluation_case_type"] == "benign_no_tool"
    assert permit.max_tokens == 512


def test_tampered_manifest_digest_is_rejected() -> None:
    candidate = build_admission_candidate()
    tampered = copy.deepcopy(candidate)
    tampered["next_gate"] = "tampered"
    with pytest.raises(
        FormalExecutionControllerV2Error,
        match="manifest digest drift",
    ):
        validate_admission_manifest(tampered)


def test_zero_network_controller_qualification() -> None:
    value = build_controller_qualification()
    assert value["status"] == "single_pilot_controller_qualified_offline"
    assert value["positive_offline_authorization_checks"] == 1
    assert value["negative_case_count"] == 4
    assert value["credentials_read"] == 0
    assert value["rejected_path_client_creations"] == 0
    assert value["injected_fixture_client_creations"] == 1
    assert value["injected_fixture_transport_calls"] == 1
    assert value["network_calls_made"] == 0
    assert value["offline_e2e_records_created_in_temporary_directory"] == 1
    assert value["completed_calls_with_cache_cost_evidence"] == 1
    assert value["cache_accounting_complete"] is True
    assert value["within_abort_ceiling"] is True
    assert value["qualification_cumulative_cost_cny"] == 0.0000728
    assert value["formal_results_created"] == 0
    assert value["candidate_can_self_authorize"] is False


def test_controller_executes_injected_transport_into_v2_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = _selected_work_item(
        _load_jsonl(controller_module.DEFAULT_PLAN)
    )
    permit = PilotExecutionPermit(
        admission_manifest_sha256="a" * 64,
        run_id="offline-controller-e2e-qualification",
        work_item=item,
        trace_path=tmp_path / "provider-trace.jsonl",
        record_ledger_path=tmp_path / "record-ledger.jsonl",
        max_tokens=64,
        timeout_seconds=30.0,
    )
    monkeypatch.setattr(
        controller_module,
        "authorize_single_pilot",
        lambda *_args, **_kwargs: permit,
    )
    credential_reads = 0
    transport_calls = 0

    def credential_loader() -> dict[str, str]:
        nonlocal credential_reads
        credential_reads += 1
        return {"fixture": "non-secret"}

    def client_factory(_values, _policy, _permit):
        client = _fixture_client("deepseek", include_request_id=False)

        def transport(endpoint, headers, payload, timeout):
            nonlocal transport_calls
            del endpoint, headers, timeout
            transport_calls += 1
            return HTTPResponseEnvelope(
                status_code=200,
                headers={},
                body={
                    "id": "offline-controller-response-1",
                    "model": payload["model"],
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    '{"tool":"final","arguments":'
                                    '{"answer":"QUALIFIED"}}'
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 40,
                        "completion_tokens": 8,
                        "total_tokens": 48,
                        "prompt_cache_hit_tokens": 32,
                        "prompt_cache_miss_tokens": 8,
                    },
                },
            )

        client.transport = transport
        client.max_tokens = 64
        return client

    result = execute_authorized_single_pilot(
        tmp_path / "unused-active-path.json",
        credential_loader=credential_loader,
        client_factory=client_factory,
        provider_trace_receipt_adapter=_as_official_receipt,
    )

    assert credential_reads == 1
    assert transport_calls == 1
    assert result["status"] == "single_pilot_record_persisted"
    assert result["result_tier"] == "formal_candidate"
    assert result["operational_status"] == "completed"
    assert result["formal_matrix_authorized"] is False
    assert result["result_admitted"] is False
    assert result["deepseek_usage_summary"] == {
        "completed_call_count": 1,
        "prompt_tokens": 40,
        "prompt_cache_hit_tokens": 32,
        "prompt_cache_miss_tokens": 8,
        "completion_tokens": 8,
        "total_tokens": 48,
        "cache_accounting_complete": True,
        "cumulative_cost_cny": 0.0000728,
        "abort_ceiling_cny": 27.0,
        "within_abort_ceiling": True,
    }
    assert permit.trace_path.is_file()
    assert permit.record_ledger_path.is_file()
    entry = json.loads(
        permit.record_ledger_path.read_text(encoding="utf-8")
    )
    assert entry["record"]["schema_version"] == (
        "m3-paper-v2-experiment-record-2.2"
    )
    assert entry["record"]["provider_safety_receipt"][
        "credentials_stored"
    ] is False
