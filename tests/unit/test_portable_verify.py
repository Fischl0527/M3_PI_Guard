import json

import pytest

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.structural_baselines import tomllib
from m3_core.policy_compiler import _explicit_argument_value
from scripts.build_portable_package import RUNTIME_ASSETS, TEST_NODES, checked_relative, export_selected_source_rows, source_closure, write_test_list
from scripts.portable_verify import derive_counts, verify_projections


def test_unknown_is_not_safe_zero_and_failure_is_separate():
    rows = [{"work_key": "a", "operational_status": "parse_failure", "unsafe_effect": None, "task_completion": False},
            {"work_key": "b", "operational_status": "completed", "unsafe_effect": False, "task_completion": True}]
    cell = derive_counts(rows)["cells"][0]
    assert cell["unsafe_effect"] == {"true": 0, "false": 1, "unknown": 1}
    assert cell["operational_status"]["parse_failure"] == 1
    with pytest.raises(ValueError, match="duplicate"):
        derive_counts(rows + [rows[0]])


@pytest.mark.parametrize("path", ["../outside.py", "/outside.py", "E:/outside.py", "C:\\outside.py", "config/project.local.env", "outputs/internal/raw.jsonl", ".git/config", "keys/private.pem"])
def test_package_cannot_copy_private_paths(path):
    with pytest.raises(ValueError):
        checked_relative(path)


def test_source_closure_resolves_from_package_alias(tmp_path):
    package = tmp_path / "m3_core"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "first.py").write_text("from m3_core import second as example\n", encoding="utf-8")
    (package / "second.py").write_text("from . import third\n", encoding="utf-8")
    (package / "third.py").write_text("", encoding="utf-8")
    found = source_closure(tmp_path, ["m3_core/first.py"])
    assert {p.name for p in found} == {"__init__.py", "first.py", "second.py", "third.py"}


def test_missing_or_duplicate_compiler_inputs_fail(tmp_path):
    path = tmp_path / "input.jsonl"
    path.write_text(json.dumps({"case_id": "a", "benchmark": "m3-v2"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="180 unique"):
        verify_projections(path)


def test_runtime_configs_are_explicit_package_assets():
    assert {path.rsplit("/", 1)[-1] for path in RUNTIME_ASSETS} == {
        "provider_safety_policy_v1.json", "public_budget_policy_v1.json", "cases_deepseek_v1.jsonl",
    }


def test_linux_test_list_has_no_windows_carriage_returns(tmp_path):
    write_test_list(tmp_path)
    assert (tmp_path / "pytest-portable.txt").read_bytes() == ("\n".join(TEST_NODES) + "\n").encode("utf-8")


@pytest.mark.parametrize("task_text,name,kind,expected", [
    ("Set account id: alpha-17", "account_id", "string", "alpha-17"),
    ("Set account   id = beta_2", "accountId", "string", "beta_2"),
    ("Set amount: 12", "amount", "integer", 12),
    ("Set amount: 12.5", "amount", "number", 12.5),
    ("No explicit value here", "account_id", "string", None),
])
def test_older_python_regex_refactor_preserves_argument_values(task_text, name, kind, expected):
    assert _explicit_argument_value(task_text, name, kind) == expected


def test_toml_reader_has_same_contract_on_python_310_and_newer():
    assert tomllib.loads('[demo]\ncount = 2\nname = "offline"\n') == {"demo": {"count": 2, "name": "offline"}}


def test_selected_source_excerpt_preserves_lines_and_excludes_other_cases(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    rows = [{"case_id": "unselected"}, {"case_id": "selected", "offline_evaluation": {"expected": True}}]
    (source / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    reference = {"path": "rows.jsonl", "line": 2, "sha256": sha256_canonical_json(rows[1])}
    cases = [{"source_reference": reference}]
    assert export_selected_source_rows(source, target, cases) == 1
    excerpt = [json.loads(line) for line in (target / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    assert excerpt == [{}, rows[1]]
    assert "unselected" not in (target / "rows.jsonl").read_text(encoding="utf-8")
    reference["sha256"] = "not-the-record-digest"
    with pytest.raises(ValueError, match="existing reference"):
        export_selected_source_rows(source, target, cases)
