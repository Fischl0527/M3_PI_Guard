from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import experiments.paper_v1.benchmarks.audit_frontier_api_model_slots as frontier_audit_module
import experiments.paper_v1.benchmarks.admit_frontier_api_model_slots as frontier_admission_module
import experiments.paper_v1.benchmarks.smoke_frontier_api_models as smoke_module

from experiments.paper_v1.benchmarks.smoke_frontier_api_models import (
    build_smoke_plan,
    execute_smokes,
)
from experiments.paper_v1.frontier_client import FrontierAPIClient
from experiments.paper_v1.benchmarks.admit_frontier_api_model_slots import (
    build_frontier_registry_admission,
)
from experiments.paper_v1.benchmarks.audit_frontier_api_model_slots import (
    build_frontier_api_model_slot_audit,
)


def test_real_transport_requires_explicit_consent() -> None:
    with pytest.raises(ValueError, match="explicit network consent"):
        FrontierAPIClient(
            provider="openai",
            model="frontier-openai-test",
            api_key="secret-test-key",
        )


def test_openai_transport_is_single_attempt_and_metadata_is_redacted() -> None:
    captured = {}

    def transport(endpoint, headers, payload, timeout):
        captured.update(
            {"endpoint": endpoint, "headers": dict(headers), "payload": dict(payload), "timeout": timeout}
        )
        return {
            "choices": [
                {"message": {"content": "SAFE"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
        }

    client = FrontierAPIClient(
        provider="openai",
        model="frontier-openai-test",
        api_key="secret-test-key",
        seed=7,
        transport=transport,
    )
    result = client.complete([{"role": "user", "content": "synthetic"}])
    assert result.text == "SAFE"
    assert result.total_tokens == 5
    assert result.provider_attempts == 1
    assert captured["payload"]["seed"] == 7
    assert captured["headers"]["Authorization"] == "Bearer secret-test-key"
    assert "secret-test-key" not in str(client.last_request_metadata)
    assert client.last_request_metadata["provider_attempts"] == 1


def test_anthropic_transport_maps_system_and_usage_without_seed() -> None:
    captured = {}

    def transport(endpoint, headers, payload, timeout):
        captured.update({"endpoint": endpoint, "headers": dict(headers), "payload": dict(payload)})
        return {
            "content": [{"type": "text", "text": "SAFE"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 6, "output_tokens": 1},
        }

    client = FrontierAPIClient(
        provider="anthropic",
        model="frontier-anthropic-test",
        api_key="secret-anthropic-key",
        seed=9,
        transport=transport,
    )
    result = client.complete(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "synthetic"},
        ]
    )
    assert result.text == "SAFE"
    assert result.total_tokens == 7
    assert captured["payload"]["system"] == "system"
    assert "seed" not in captured["payload"]
    assert captured["headers"]["x-api-key"] == "secret-anthropic-key"
    assert "secret-anthropic-key" not in str(client.last_request_metadata)


def test_smoke_plan_is_redacted_and_plan_only_never_calls_network(tmp_path: Path) -> None:
    values = {
        "OPENAI_API_KEY": "secret-openai",
        "FRONTIER_OPENAI_MODEL_ID": "frontier-openai-test",
        "FRONTIER_OPENAI_BASE_URL": "__OPTIONAL_SET_LOCALLY__",
        "ANTHROPIC_API_KEY": "__OPTIONAL_SET_LOCALLY__",
        "FRONTIER_ANTHROPIC_MODEL_ID": "__OPTIONAL_SET_LOCALLY__",
        "FRONTIER_ANTHROPIC_BASE_URL": "__OPTIONAL_SET_LOCALLY__",
        "M3_FRONTIER_API_CONSENT": "__OPTIONAL_SET_LOCALLY__",
    }
    plan = build_smoke_plan(values)
    assert plan[0]["api_key_status"] == "set_redacted"
    assert "secret-openai" not in str(plan)
    manifest = execute_smokes(values, output_dir=tmp_path, execute=False)
    assert manifest["status"] == "plan_only_no_network"
    assert manifest["network_calls_performed"] is False
    assert manifest["network_call_count"] == 0
    assert manifest["result_eligible_for_formal_tables"] is False


def test_smoke_execution_rejects_missing_two_vendor_consent_before_network(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="explicit local network consent"):
        execute_smokes({}, output_dir=tmp_path, execute=True)


def test_network_smoke_preserves_one_attempt_failure_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.provider = kwargs["provider"]
            self.model = kwargs["model"]
            self.last_request_metadata = {"provider_attempts": 1}

        def complete(self, messages):
            calls.append((self.provider, messages))
            if self.provider == "openai":
                raise RuntimeError("synthetic provider failure")
            return SimpleNamespace(
                text="SAFE",
                model_latency_ms=1.0,
                prompt_tokens=2,
                completion_tokens=1,
                total_tokens=3,
                provider_attempts=1,
            )

    monkeypatch.setattr(smoke_module, "FrontierAPIClient", FakeClient)
    values = {
        "OPENAI_API_KEY": "secret-openai",
        "FRONTIER_OPENAI_MODEL_ID": "frontier-openai-test",
        "FRONTIER_OPENAI_BASE_URL": "__OPTIONAL_SET_LOCALLY__",
        "ANTHROPIC_API_KEY": "secret-anthropic",
        "FRONTIER_ANTHROPIC_MODEL_ID": "frontier-anthropic-test",
        "FRONTIER_ANTHROPIC_BASE_URL": "__OPTIONAL_SET_LOCALLY__",
        "M3_FRONTIER_API_CONSENT": "yes_for_network_smoke",
    }
    manifest = execute_smokes(values, output_dir=tmp_path, execute=True)
    assert manifest["status"] == "failed_network_smoke_preserved"
    assert manifest["network_call_count"] == 2
    assert manifest["completed_provider_count"] == 1
    assert len(calls) == 2
    assert manifest["provider_results"][0]["provider_attempts"] == 1


def _write_base_registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "paper-model-registry-2.0",
                "models": [{"id": "local", "role": "core_local_small"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_frontier_registry_admission_blocks_plan_only_without_writing_registry(
    tmp_path: Path,
) -> None:
    base = tmp_path / "registry-v2.json"
    smoke = tmp_path / "smoke.json"
    output = tmp_path / "registry-v3.json"
    _write_base_registry(base)
    smoke.write_text(
        json.dumps(
            {
                "status": "plan_only_no_network",
                "network_calls_performed": False,
                "network_call_count": 0,
                "completed_provider_count": 0,
                "provider_results": [],
                "result_eligible_for_formal_tables": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    audit = build_frontier_registry_admission(
        base_registry_path=base,
        smoke_manifest_path=smoke,
        output_registry_path=output,
        audit_path=tmp_path / "audit.json",
    )
    assert audit["status"] == "blocked_smoke_not_qualified"
    assert audit["network_calls_performed_by_admission"] is False
    assert not output.exists()


def test_frontier_registry_admission_writes_two_nonformal_slots_after_clean_smoke(
    tmp_path: Path,
) -> None:
    base = tmp_path / "registry-v2.json"
    smoke = tmp_path / "smoke.json"
    output = tmp_path / "registry-v3.json"
    _write_base_registry(base)
    results = [
        {
            "provider": "openai",
            "model_id": "frontier-openai-exact",
            "status": "completed_network_smoke",
            "provider_attempts": 1,
            "response_exact_safe": True,
        },
        {
            "provider": "anthropic",
            "model_id": "frontier-anthropic-exact",
            "status": "completed_network_smoke",
            "provider_attempts": 1,
            "response_exact_safe": True,
        },
    ]
    smoke.write_text(
        json.dumps(
            {
                "status": "completed_two_vendor_network_smoke",
                "network_calls_performed": True,
                "network_call_count": 2,
                "completed_provider_count": 2,
                "provider_results": results,
                "result_eligible_for_formal_tables": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    audit = build_frontier_registry_admission(
        base_registry_path=base,
        smoke_manifest_path=smoke,
        output_registry_path=output,
        audit_path=tmp_path / "audit.json",
    )
    registry = json.loads(output.read_text(encoding="utf-8"))
    frontier = [row for row in registry["models"] if row["role"] == "frontier_api_vendor"]
    assert audit["status"] == "admitted_registry_candidate"
    assert len(frontier) == 2
    assert all(row["result_eligible_for_formal_tables"] is False for row in frontier)


def test_frontier_audit_uses_admitted_v3_candidate_without_printing_secrets(
    tmp_path: Path,
) -> None:
    base = tmp_path / "registry-v2.json"
    smoke = tmp_path / "smoke.json"
    output = tmp_path / "registry-v3.json"
    admission_audit = tmp_path / "admission.json"
    config = tmp_path / "project.local.env"
    _write_base_registry(base)
    smoke.write_text(
        json.dumps(
            {
                "status": "completed_two_vendor_network_smoke",
                "network_calls_performed": True,
                "network_call_count": 2,
                "completed_provider_count": 2,
                "provider_results": [
                    {
                        "provider": "openai",
                        "model_id": "frontier-openai-exact",
                        "status": "completed_network_smoke",
                        "provider_attempts": 1,
                        "response_exact_safe": True,
                    },
                    {
                        "provider": "anthropic",
                        "model_id": "frontier-anthropic-exact",
                        "status": "completed_network_smoke",
                        "provider_attempts": 1,
                        "response_exact_safe": True,
                    },
                ],
                "result_eligible_for_formal_tables": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=__OPTIONAL_SET_LOCALLY__",
                "ANTHROPIC_API_KEY=__OPTIONAL_SET_LOCALLY__",
                "FRONTIER_OPENAI_MODEL_ID=__OPTIONAL_SET_LOCALLY__",
                "FRONTIER_ANTHROPIC_MODEL_ID=__OPTIONAL_SET_LOCALLY__",
                "M3_FRONTIER_API_CONSENT=__OPTIONAL_SET_LOCALLY__",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    build_frontier_registry_admission(
        base_registry_path=base,
        smoke_manifest_path=smoke,
        output_registry_path=output,
        audit_path=admission_audit,
    )

    audit = build_frontier_api_model_slot_audit(
        config_path=config,
        model_registry_path=base,
        registry_admission_path=admission_audit,
        smoke_manifest_path=smoke,
        output_dir=tmp_path / "protocols",
    )

    assert audit["status"] == "registry_satisfied_pending_formal_runs"
    assert audit["registered_frontier_api_vendor_count"] == 2
    assert (
        audit["model_registry_selection"]["selection_reason"]
        == "admitted_frontier_registry_candidate"
    )
    assert audit["config_redacted"]["OPENAI_API_KEY"] == "<placeholder>"


def test_frontier_audit_keeps_project_paths_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    config = root / "config" / "project.local.env"
    registry = root / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json"
    admission = root / "protocols" / "paper_upgrade_v1" / "frontier_api_model_slot_registry_admission_v1.json"
    smoke = root / "outputs" / "paper_upgrade_v1" / "frontier_api_smoke_v1" / "manifest.json"
    client = root / "experiments" / "paper_v1" / "frontier_client.py"
    output_dir = root / "protocols" / "paper_upgrade_v1"
    for path in [config, registry, admission, smoke, client]:
        path.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("OPENAI_API_KEY=__OPTIONAL_SET_LOCALLY__\n", encoding="utf-8")
    _write_base_registry(registry)
    admission.write_text(
        json.dumps({"status": "blocked_smoke_not_qualified"}) + "\n",
        encoding="utf-8",
    )
    smoke.write_text(
        json.dumps(
            {
                "status": "plan_only_no_network",
                "network_calls_performed": False,
                "network_call_count": 0,
                "result_eligible_for_formal_tables": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    client.write_text("# synthetic client\n", encoding="utf-8")
    monkeypatch.setattr(frontier_audit_module, "ROOT", root)
    monkeypatch.setattr(frontier_audit_module, "FRONTIER_CLIENT", client)
    monkeypatch.setattr(frontier_audit_module, "tracked_secret_hits", lambda values, *, root: [])

    audit = frontier_audit_module.build_frontier_api_model_slot_audit(
        config_path=config,
        model_registry_path=registry,
        registry_admission_path=admission,
        smoke_manifest_path=smoke,
        output_dir=output_dir,
    )

    rendered = json.dumps(audit, ensure_ascii=False)
    assert str(root) not in rendered
    assert audit["config_path"] == "config/project.local.env"
    assert audit["model_registry_path"] == "protocols/paper_upgrade_v1/model_registry_v2.json"
    assert audit["frontier_client_path"] == "experiments/paper_v1/frontier_client.py"
    assert audit["smoke_manifest_path"] == "outputs/paper_upgrade_v1/frontier_api_smoke_v1/manifest.json"


def test_frontier_registry_admission_keeps_project_paths_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    base = root / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json"
    smoke = root / "outputs" / "paper_upgrade_v1" / "frontier_api_smoke_v1" / "manifest.json"
    output = root / "protocols" / "paper_upgrade_v1" / "model_registry_v3_candidate.json"
    audit_path = root / "protocols" / "paper_upgrade_v1" / "frontier_api_model_slot_registry_admission_v1.json"
    base.parent.mkdir(parents=True, exist_ok=True)
    smoke.parent.mkdir(parents=True, exist_ok=True)
    _write_base_registry(base)
    smoke.write_text(
        json.dumps(
            {
                "status": "completed_two_vendor_network_smoke",
                "network_calls_performed": True,
                "network_call_count": 2,
                "completed_provider_count": 2,
                "provider_results": [
                    {
                        "provider": "openai",
                        "model_id": "frontier-openai-exact",
                        "status": "completed_network_smoke",
                        "provider_attempts": 1,
                        "response_exact_safe": True,
                    },
                    {
                        "provider": "anthropic",
                        "model_id": "frontier-anthropic-exact",
                        "status": "completed_network_smoke",
                        "provider_attempts": 1,
                        "response_exact_safe": True,
                    },
                ],
                "result_eligible_for_formal_tables": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(frontier_admission_module, "ROOT", root)

    audit = frontier_admission_module.build_frontier_registry_admission(
        base_registry_path=base,
        smoke_manifest_path=smoke,
        output_registry_path=output,
        audit_path=audit_path,
    )
    registry = json.loads(output.read_text(encoding="utf-8"))
    rendered = json.dumps({"audit": audit, "registry": registry}, ensure_ascii=False)

    assert str(root) not in rendered
    assert audit["base_registry_path"] == "protocols/paper_upgrade_v1/model_registry_v2.json"
    assert audit["smoke_manifest_path"] == "outputs/paper_upgrade_v1/frontier_api_smoke_v1/manifest.json"
    assert audit["output_registry_path"] == "protocols/paper_upgrade_v1/model_registry_v3_candidate.json"
    frontier = [row for row in registry["models"] if row["role"] == "frontier_api_vendor"]
    assert {row["smoke_evidence"] for row in frontier} == {
        "outputs/paper_upgrade_v1/frontier_api_smoke_v1/manifest.json"
    }
