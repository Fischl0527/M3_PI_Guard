import socket
import subprocess

import pytest

from experiments.paper_v2.agentdyn_native_qualification_v1 import (
    offline_boundary,
    selected_ids,
)


def test_native_membership_is_order_invariant_and_outcome_free():
    tasks = [f"user_task_{i}" for i in range(20)]
    a = selected_ids("shopping", tasks)
    assert len(set(a)) == 6
    assert a == selected_ids("shopping", list(reversed(tasks)))
    assert a != selected_ids("github", tasks)


def test_native_physical_write_is_blocked(tmp_path):
    path = tmp_path / "must-not-exist.txt"
    with offline_boundary() as events:
        with pytest.raises(PermissionError):
            path.write_text("no", encoding="utf-8")
    assert not path.exists()
    assert events == ["open"]


def test_native_network_and_subprocess_are_blocked():
    with offline_boundary() as events:
        with pytest.raises(PermissionError):
            socket.socket()
        with pytest.raises(PermissionError):
            subprocess.run(["never-execute-this"], check=False)
    assert any(e.startswith("socket.") for e in events)
    assert any(e.startswith("subprocess.") for e in events)
