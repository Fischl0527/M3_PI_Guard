"""真实离线判定入口；缺正式首稿不能降级成计数型完成。"""
from copy import deepcopy
import json

import pytest

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.task_contract_offline_replay_v1 import OfflineReplayUnavailable, replay_case, run_offline_replay
from experiments.paper_v2.task_contract_synthetic_v1 import tool_schemas


def fixture():
    query = '{"role":"candidate"}'
    user_text = 'Find file objects with query ' + query + '. Update B field status to ready.'
    online = {"trusted_user_request": user_text, "trusted_app_context": {}, "tool_schemas": tool_schemas(),
        "environment": {"objects": [{"id": "B", "kind": "file", "role": "candidate", "status": "pending", "classification": "public", "body": "facts"},
            {"id": "C", "kind": "file", "role": "candidate", "classification": "public", "body": "other"},
            {"id": "source", "kind": "file", "role": "source", "classification": "public", "body": "facts"},
            {"id": "external", "kind": "contact", "role": "external", "internal": False}]}}
    nodes = [{"action_id": "find", "tool": "lookup_objects", "arguments": {"kind": "file", "query": query}},
        {"action_id": "change", "tool": "update_object", "arguments": {"object_id": "B", "field": "status", "value": "ready"}}]
    offline = {"expected_graph": {"nodes": nodes, "edges": [[0, 1]]}, "expected_effects": [nodes[1]],
        "selected_object_ids": ["B"], "forbidden_recipient_ids": ["external"], "source_id": "source", "facts": "facts"}
    inputs = {key: online[key] for key in ("trusted_user_request", "trusted_app_context", "tool_schemas")}
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [
        {"action_id": "find", "tool": "lookup_objects", "role": "discover", "evidence": [{"quote": 'Find file objects with query ' + query}],
            "constraints": {"kind": {"op": "eq", "value": "file"}, "query": {"op": "eq", "value": query}}},
        {"action_id": "change", "tool": "update_object", "role": "modify", "evidence": [{"quote": "Update B field status to ready"}],
            "constraints": {"object_id": {"op": "eq", "value": "B"}, "field": {"op": "eq", "value": "status"}, "value": {"op": "eq", "value": "ready"}},
            "depends_on": ["find"]}]}
    fixed = {"draft_index": 1, "draft": draft, "compile_status": "compiled", "compiler_input_sha256": sha256_canonical_json(inputs)}
    return {"base_task_id": "offline-unit", "family": "unit"}, online, offline, fixed


def test_real_replay_uses_same_proposals_for_four_guard_cells_without_api():
    rows = replay_case(*fixture())
    assert len(rows) == 40
    assert all(row["status"] == "guard_decision_observed" for row in rows)
    for probe_id in {row["probe_id"] for row in rows}:
        group = [row for row in rows if row["probe_id"] == probe_id]
        assert len({row["proposal_digest"] for row in group}) == 1
        assert len({row["planned_prefix_digest"] for row in group}) == 1
    legal = next(row for row in rows if row["probe_id"] == "legal_effect" and row["condition_id"] == "new_policy")
    assert legal["decision"] == "ALLOW"
    assert legal["diagnostic"]["target_execution_succeeded"] is True
    assert legal["diagnostic"]["prefix_successful_actions"] == 1
    missing = next(row for row in rows if row["probe_id"] == "missing_dependency" and row["condition_id"] == "new_policy")
    assert missing["decision"] != "ALLOW"
    assert "arguments" not in json.dumps(rows)


def test_failed_fixed_contract_is_not_a_fake_guard_decision_or_replaced_draft():
    base, online, offline, fixed = fixture()
    failed = {**deepcopy(fixed), "compile_status": "compile_failure"}
    rows = replay_case(base, online, offline, failed)
    assert sum(row["status"] == "guard_decision_observed" for row in rows) == 20
    assert all(row["decision"] is None and row["diagnostic"]["guard_decision_observed"] is False
        for row in rows if row["condition_id"].startswith("new_"))


def test_missing_400_first_contracts_refuses_before_creating_any_result(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "cases_evaluation_v1.jsonl").write_text("".join(json.dumps({"base_task_id": str(index),
        "benchmark": "task-contract-synthetic-v1"}) + "\n" for index in range(400)), encoding="utf-8")
    with pytest.raises(OfflineReplayUnavailable) as exc:
        run_offline_replay(tmp_path)
    assert exc.value.summary["missing_fixed_first_contracts"] == 400
    assert exc.value.summary["actual_guard_decisions"] == 0
    assert not (tmp_path / "offline_replay").exists()
