"""v4只新增显式研究范围；不放宽旧客户端或启用Gemini。"""
import threading

import pytest

from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer
from experiments.paper_v2.official_provider_executor import ProviderPayloadError


def client(tmp_path, **changes):
    values = dict(model_group="deepseek_pro", model="deepseek-v4-pro", api_key="offline-test",
                  benchmark="synthetic-task-contract-v1", work_key="scope-test", attempt=1,
                  trace_path=tmp_path / "trace.jsonl", pacer=RequestPacer(0, threading.Event()),
                  transport=lambda *_args, **_kwargs: None, generation_profile="task_contract_study_v1",
                  max_provider_calls=12, call_budget_ceiling=12,
                  call_budget_scope="task_contract_v4_development_v1")
    values.update(changes)
    return DevelopmentRequestClient(**values)


def test_v4_explicit_scope_permits_twelve_without_network(tmp_path):
    value = client(tmp_path)
    assert value.max_provider_calls == 12
    assert value.requests == []


def test_v4_compiler_remains_pro_only(tmp_path):
    with pytest.raises(ProviderPayloadError, match="profile"):
        client(tmp_path, model_group="deepseek_flash", model="deepseek-flash",
               generation_profile="task_contract_compiler_v1")


def test_v4_cannot_activate_gemini(tmp_path):
    with pytest.raises(ProviderPayloadError, match="DeepSeek-only"):
        client(tmp_path, model_group="gemini_flash", model="gemini-3.6-flash")


def test_historical_scope_still_rejects_twelve(tmp_path):
    with pytest.raises(ProviderPayloadError, match="ceiling"):
        client(tmp_path, call_budget_scope=None, generation_profile=None)
