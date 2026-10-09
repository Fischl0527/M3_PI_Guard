import json
import socket

import pytest

from scripts.portable_demo import build_demo, main, render_html, run_scenario


@pytest.fixture(autouse=True)
def no_connections(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("offline demo attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)


@pytest.mark.parametrize("scenario,decision,sends,unsafe", [
    ("public_restricted", "ALLOW", 1, False),
    ("private_archive", "ALLOW", 1, False),
    ("private_restricted", "DENY", 0, False),
    ("missing_classification", "ASK", 0, False),
])
def test_corrected_demo(scenario, decision, sends, unsafe):
    row = run_scenario(scenario, "m3_full")
    assert row["steps"][1]["decision"] == decision
    assert row["result"]["executed_send_count"] == sends
    assert row["result"]["simulated_unsafe_effect"] is unsafe
    assert row["runtime_revision"] == "corrected_v2"
    assert row["real_external_effects"] == row["api_calls"] == 0


def test_completion_can_coexist_with_simulated_violation():
    row = run_scenario("private_restricted", "m3_policy_only")
    assert row["result"]["task_completion"] is True
    assert row["result"]["simulated_unsafe_effect"] is True
    assert row["steps"][1]["outbox_before"] == []
    assert len(row["steps"][1]["outbox_after"]) == 1


def test_compiler_and_embedded_page():
    data = build_demo()
    assert len(data["scenarios"]) == 8
    assert [s["decision"] for s in data["compiler"]["steps"]] == ["ALLOW", "ASK", "ALLOW"]
    data["environment"]["system"] = "</script><script>bad</script>"
    html = render_html(data)
    assert "__DEMO_DATA__" not in html
    assert "</script><script>bad" not in html
    assert "不是现场大模型输出" in html
    assert "https://" not in html


def test_entry_writes_only_requested_output(tmp_path):
    assert main(["--output", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "demo_results.json").read_text(encoding="utf-8"))
    assert data["api_calls"] == 0
    assert (tmp_path / "index.html").is_file()
