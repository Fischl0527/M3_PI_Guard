from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.paper_v2.deepseek_nonthinking_client_v1 import (
    DeepSeekNonThinkingOfficialClient,
    DeepSeekNonThinkingTracedProviderClient,
)
from experiments.paper_v2.formal_matrix_controller_v1 import (
    _as_official_receipt,
)
from experiments.paper_v2.medium_runtime import DEFAULT_TOOL_SCHEMAS
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    ProviderBudgetState,
)
from experiments.paper_v2.provider_safety import ProviderSafetyError
from experiments.paper_v2.trusted_context_runtime_v2 import (
    PROMPT_PROJECTION_SCHEMA_VERSION,
    TracedClientRegistry,
    TrustedContextFailurePersistingRuntime,
    build_research_messages_v2,
    project_trusted_app_context,
)
from m3_core.policy_compiler import compile_task_policy
from m3_core.research_runner import PaperRuntimeView


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASE_PATH = (
    PROJECT_ROOT / "m3_attacks/cases/paper_v1/m3_v2_development.jsonl"
)
POLICY_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"
)


def _case() -> dict:
    return json.loads(CASE_PATH.read_text(encoding="utf-8").splitlines()[6])


def test_trusted_context_projection_exposes_only_runtime_parameters() -> None:
    case = _case()
    view = PaperRuntimeView(
        trusted_user_request=case["trusted_user_request"],
        trusted_app_context=case["trusted_app_context"],
        untrusted_content=case["untrusted_content"],
        untrusted_memory=tuple(case["untrusted_memory"]),
        conversation_turns=(),
    )
    projection = project_trusted_app_context(view)
    assert set(projection) == {"requested_actions", "workspace_scope"}
    assert "request_id" not in projection
    assert projection["requested_actions"] == [
        {
            "tool": "write_file",
            "arguments": {
                "path": "sandbox/public/m3v2_d-002_summary.txt"
            },
        }
    ]
    manifest = compile_task_policy(
        trusted_user_request=view.trusted_user_request,
        trusted_app_context=view.trusted_app_context,
        tool_schemas=DEFAULT_TOOL_SCHEMAS,
        generated_at="2026-07-24T16:50:00+08:00",
    )
    messages = build_research_messages_v2(
        view,
        tool_schemas=DEFAULT_TOOL_SCHEMAS,
        manifest=manifest,
        prompt_profile="normal",
    )
    rendered = json.dumps(messages, ensure_ascii=False)
    assert PROMPT_PROJECTION_SCHEMA_VERSION.startswith("m3-paper-v2-")
    assert "<TrustedApplicationContext>" in rendered
    assert "sandbox/public/m3v2_d-002_summary.txt" in rendered
    assert '"request_id"' not in rendered
    assert "expected_effect" not in rendered
    assert "evaluation_case_type" not in rendered


def _traced_client(
    tmp_path: Path,
) -> DeepSeekNonThinkingTracedProviderClient:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def transport(
        endpoint: str,
        headers: dict,
        payload: dict,
        timeout: float,
    ) -> HTTPResponseEnvelope:
        del endpoint, headers, timeout
        assert payload["thinking"] == {"type": "disabled"}
        return HTTPResponseEnvelope(
            status_code=200,
            headers={},
            body={
                "id": "trusted-context-runtime-v2-response",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"tool":"write_file","arguments":'
                                '{"path":"outside.txt"}}'
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "prompt_cache_hit_tokens": 10,
                    "prompt_cache_miss_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 28,
                },
            },
        )

    client = DeepSeekNonThinkingOfficialClient(
        provider_id="deepseek",
        api_key="offline-trusted-context-v2-key",
        content_class="synthetic_m3_case",
        budget_state=ProviderBudgetState(
            provider_id="deepseek",
            policy=policy,
        ),
        policy=policy,
        max_tokens=64,
        timeout=30.0,
        transport=transport,
    )
    return DeepSeekNonThinkingTracedProviderClient(
        client,
        execution_identity="e" * 64,
        work_key="w" * 64,
        trace_path=tmp_path / "trace.jsonl",
        recorded_at=lambda: "2026-07-24T16:50:00+08:00",
        receipt_adapter=_as_official_receipt,
    )


def test_post_response_safety_failure_becomes_content_free_itt_trace(
    tmp_path: Path,
) -> None:
    registry = TracedClientRegistry()
    client = registry.register("w" * 64, _traced_client(tmp_path))

    class Delegate:
        def execute(self, context, profile):
            del context, profile
            client.complete(
                [{"role": "user", "content": "public fixture"}],
                step=1,
            )
            raise ProviderSafetyError(
                "fixture file path escapes sandbox/public"
            )

    runtime = TrustedContextFailurePersistingRuntime(
        Delegate(),
        client_lookup=registry.get,
        recorded_at=lambda: "2026-07-24T16:50:00+08:00",
    )
    result = runtime.execute(
        SimpleNamespace(work_key="w" * 64),
        SimpleNamespace(),
    )
    assert result["operational_status"] == "runner_failure"
    assert result["result_tier"] == "formal_candidate"
    assert result["provider_trace_bundle"]["completed_request_count"] == 1
    assert result["provider_trace_bundle"]["open_request_count"] == 0
    assert result["events"][0]["decision"] == "DENY"
    assert result["events"][0]["execution_attempted"] is False
    assert result["events"][0]["response_text"] == ""
    assert result["safety_receipt"]["evidence"]["effect_backend"] == "no_effect"
    serialized = json.dumps(result, ensure_ascii=False)
    assert "fixture file path escapes" not in serialized
    assert "outside.txt" not in serialized


def test_pre_response_failure_is_not_converted() -> None:
    class Delegate:
        def execute(self, context, profile):
            del context, profile
            raise RuntimeError("pre-response")

    runtime = TrustedContextFailurePersistingRuntime(
        Delegate(),
        client_lookup=lambda _work_key: None,
        recorded_at=lambda: "2026-07-24T16:50:00+08:00",
    )
    with pytest.raises(RuntimeError, match="pre-response"):
        runtime.execute(
            SimpleNamespace(work_key="w" * 64),
            SimpleNamespace(),
        )
