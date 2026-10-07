import copy
import csv
import json
from collections import Counter

import pytest

from experiments.paper_v2 import trusted_intent_review_v1 as review


@pytest.fixture(scope="module")
def inputs():
    return (review.read_jsonl(review.CALIBRATION / "plan.jsonl"),
            review.read_jsonl(review.CALIBRATION / "raw_records.jsonl"))


def test_all_fixed_sixty_tasks_have_evidence_and_no_parameter_bodies(inputs, tmp_path):
    rows = review.build_review(*inputs)
    assert len(rows) == len({r["underlying_task_id"] for r in rows}) == 60
    assert Counter(r["benchmark"] for r in rows) == {"agentdojo-v1": 30, "m3-v2": 30}
    assert sum(r["trusted_declaration_tools"] != "" for r in rows) == 7
    assert sum("concrete_target_not_authorized" in r["categories"] for r in rows) == 10
    assert all(r["trusted_source_locator"] and r["evidence_gap"] for r in rows)
    assert not any(r["contract_violation_verdict"] == "established" for r in rows)
    for row in rows:
        for rule in json.loads(row["generated_rule_summary"]):
            assert all("value" not in c for c in rule["constraints"].values())
        assert set(json.loads(row["condition_summaries"])) == set(review.CONDITIONS)
    review.write_review(rows, tmp_path)
    with (tmp_path / "review.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 60
    assert sorted(p.name for p in tmp_path.iterdir()) == ["report.md", "review.csv"]


def test_existing_execution_and_incomplete_score_are_not_called_compiler_defect(inputs):
    rows = {r["case_id"]: r for r in review.build_review(*inputs)}
    for case in ("M3V2-H-059-BT", "M3V2-H-065-BT", "M3V2-V-005-BT"):
        row = rows[case]
        outcome = json.loads(row["condition_summaries"])["m3_policy_only"]
        assert outcome["executed_count"] > 0 and outcome["completion"] is False
        assert "execution_observed_but_completion_not_met" in row["categories"]
        assert row["contract_violation_verdict"] != "established"


def test_unknown_and_completion_before_failure_survive_review(inputs):
    plan, original = inputs
    raw = copy.deepcopy(original)
    target = next(r for r in raw if r["evaluation_case_type"] == "benign_tool"
                  and r["condition_id"] == "m3_policy_only")
    target["task_completion"] = None
    row = next(r for r in review.build_review(plan, raw) if r["case_id"] == target["case_id"])
    assert json.loads(row["condition_summaries"])["m3_policy_only"]["completion"] is None
    assert "completion_evidence_missing" in row["categories"]
    target["task_completion"] = True
    target["operational_status"] = "parse_failure"
    row = next(r for r in review.build_review(plan, raw) if r["case_id"] == target["case_id"])
    assert json.loads(row["condition_summaries"])["m3_policy_only"]["completion"] is True
    assert "model_or_operational_failure_observed" in row["categories"]


@pytest.mark.parametrize("kind", ("missing", "duplicate", "extra"))
def test_result_count_or_identity_changes_reject(inputs, kind):
    plan, raw = inputs
    changed = list(raw)
    if kind == "missing":
        changed.pop()
    elif kind == "duplicate":
        changed.append(raw[0])
    else:
        changed.append({**raw[0], "work_key": "unplanned"})
    with pytest.raises(ValueError, match="public result"):
        review.build_review(plan, changed)


def test_declaration_loss_is_reported_not_converted_to_a_new_permission():
    note = review.explanation({"benchmark": "m3-v2"}, "Save the summary", {
        "requested_actions": [{"tool": "write_file", "arguments": {"path": "sandbox/public/x.txt"}}]
    }, {}, [])
    assert note[2] == ["contract_violation_declaration_missing"]
    assert note[-1] == "established"


def test_result_does_not_silently_change_task_or_turn_a_number_into_bool(inputs):
    plan, original = inputs
    raw = copy.deepcopy(original)
    target = next(r for r in raw if r["evaluation_case_type"] == "benign_tool"
                  and r["condition_id"] == "m3_policy_only")
    target["case_id"] = "changed"
    with pytest.raises(ValueError, match="mismatch"):
        review.build_review(plan, raw)
    target["case_id"] = next(r["case_id"] for r in plan if r["work_key"] == target["work_key"])
    target["task_completion"] = 0
    with pytest.raises(ValueError, match="bool or unknown"):
        review.build_review(plan, raw)


def test_unreviewed_or_missing_interface_never_gets_an_invented_note():
    with pytest.raises(ValueError, match="unreviewed"):
        review.explanation({"benchmark": "m3-v2"}, "Unknown new task", {}, {}, [])
    with pytest.raises(ValueError, match="absent tool"):
        review.explanation({"benchmark": "agentdojo-v1", "case_id": "agentdojo:v1:banking:user_task_0"},
                           "Pay a bill", {}, {}, [])
