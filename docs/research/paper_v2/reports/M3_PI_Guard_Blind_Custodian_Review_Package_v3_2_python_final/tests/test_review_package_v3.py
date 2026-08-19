from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_review_package_verifies_and_has_no_powershell_wrapper() -> None:
    completed = subprocess.run(
        [sys.executable, "-B", "custodian.py", "verify"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "review_package_verified"
    assert not list(ROOT.rglob("*.ps1"))


def test_manifest_binds_active_core_and_frozen_slots() -> None:
    manifest = json.loads(
        (ROOT / "review_manifest_v3.json").read_text(encoding="utf-8")
    )
    entries = {row["path"]: row for row in manifest["files"]}
    core = ROOT / (
        "review_source/experiments/paper_v2/independent_blind_closeout_v2.py"
    )
    slots = ROOT / (
        "review_source/protocols/paper_upgrade_v2/"
        "independent_blind_authoring_kit_v1/slots.jsonl"
    )
    assert hashlib.sha256(core.read_bytes()).hexdigest() == entries[
        core.relative_to(ROOT).as_posix()
    ]["sha256"] == manifest["critical_bindings"]["closeout_core_sha256"]
    assert hashlib.sha256(slots.read_bytes()).hexdigest() == (
        "4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8"
    )


def test_mutable_config_is_work_scoped_and_private_key_is_external() -> None:
    config = json.loads(
        (ROOT / "review_package_config.json").read_text(encoding="utf-8")
    )
    assert config["work_root"] == "work"
    assert all(path.startswith("work/") for path in config["paths"].values())
    assert "private_key" not in config["paths"]
