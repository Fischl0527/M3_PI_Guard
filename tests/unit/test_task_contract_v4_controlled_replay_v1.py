"""同提案回放必须有真实编译与后端结果；不以公式计数冒充判定。"""
import json

import pytest

from experiments.paper_v2.task_contract_synthetic_v1 import build_synthetic_cases
from experiments.paper_v2.task_contract_v4_controlled_replay_v1 import OfflineProposalClient, fixtures, run


def test_fixtures_preserve_original_and_apply_one_controlled_target_swap():
    case = build_synthetic_cases()[0]
    before = json.dumps(case, sort_keys=True)
    values = fixtures(case["online"], case["offline_evaluation"])
    assert "reference_chain" in values
    original = values["reference_chain"][1]
    assert original == [{"tool": node["tool"], "arguments": node["arguments"]} for node in case["offline_evaluation"]["expected_graph"]["nodes"]]
    if "wrong_object" in values:
        modified = values["wrong_object"][1]
        assert sum(a != b for a, b in zip(original, modified)) == 1
    assert json.dumps(case, sort_keys=True) == before


def test_offline_client_has_no_transport_and_only_returns_fixed_proposals():
    values = [{"tool": "read_object", "arguments": {"object_id": "test"}}]
    client = OfflineProposalClient(values)
    assert not hasattr(client, "api_key") and not hasattr(client, "transport")
    assert json.loads(client.complete([], step=1).text) == values[0]
    assert json.loads(client.complete([], step=2).text)["tool"] == "final"


def test_missing_fixed_compilations_produces_no_fake_guard_counts(tmp_path):
    (tmp_path / "assets").mkdir()
    for cohort in ("debug", "qualification"):
        rows = [{"base_task_id": f"{cohort}-{index}", "benchmark": "m3-v2"} for index in range(16)]
        (tmp_path / f"assets/cases_{cohort}_v1.jsonl").write_text("\n".join(json.dumps(row) for row in rows)+"\n", encoding="utf-8")
    with pytest.raises(ValueError, match="actual fixed compilation"):
        run(tmp_path)
    assert not (tmp_path / "controlled_decisions_v1.jsonl").exists()
