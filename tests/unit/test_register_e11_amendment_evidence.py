from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_final_analysis import validate_inputs
from scripts.register_e11_amendment_evidence import RegistrationError, register
from tests.unit.test_build_final_analysis import (
    _install_synthetic_corrected_e17_loader,
    _make_repository,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_registration_is_dry_run_by_default_and_preserves_primary_e11(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_synthetic_corrected_e17_loader(monkeypatch)
    root, registry = _make_repository(tmp_path)
    before_hash = _hash(registry)
    before = json.loads(registry.read_text(encoding="utf-8"))
    before_e11 = next(item for item in before["experiments"] if item["id"] == "E11")

    dry_run = register(registry_path=registry, repository_root=root)
    assert dry_run["mode"] == "dry_run"
    assert dry_run["registry_written"] is False
    assert dry_run["pre_registered"] is False
    assert dry_run["required_artifacts_changed"] is False
    assert _hash(registry) == before_hash

    applied = register(registry_path=registry, repository_root=root, apply=True)
    assert applied["mode"] == "apply"
    assert applied["registry_written"] is True
    after = json.loads(registry.read_text(encoding="utf-8"))
    after_e11 = next(item for item in after["experiments"] if item["id"] == "E11")
    assert after_e11["required_artifacts"] == before_e11["required_artifacts"]
    assert Path(after_e11["required_artifacts"][0]).name == "manifest.json"
    assert Path(after_e11["required_artifacts"][0]).parent.name == "E11"
    assert after_e11["claim_boundary"]["pooling_prohibited"] is True
    assert after_e11["claim_boundary"]["original_e11_replaced"] is False
    assert after_e11["claim_boundary"]["posthoc_supplement"]["pre_registered"] is False
    assert after_e11["claim_boundary"]["posthoc_supplement"]["visualization_revision"] == 2
    assert applied["visualization_revision"] == 2
    assert any(
        value.endswith("E11_posthoc_amendment_v1/manifest.json")
        for value in after_e11["evidence"]
    )
    # The ordinary E0-E17 admission gate still resolves the same primary E11
    # manifest even after the independently denominated evidence append.
    _, bundles, _ = validate_inputs(registry, repository_root=root)
    assert bundles["E11"].manifest_path.name == "manifest.json"
    assert bundles["E11"].manifest_path.parent.name == "E11"


def test_apply_refuses_to_stale_an_existing_e18_bundle(tmp_path: Path) -> None:
    root, registry = _make_repository(tmp_path)
    final_analysis = root / "outputs" / "experiments" / "final_analysis"
    final_analysis.mkdir(parents=True)
    before_hash = _hash(registry)

    with pytest.raises(RegistrationError, match="after final_analysis exists"):
        register(registry_path=registry, repository_root=root, apply=True)
    assert _hash(registry) == before_hash
