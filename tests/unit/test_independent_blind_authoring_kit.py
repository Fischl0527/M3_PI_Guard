from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from experiments.paper_v1.benchmarks.audit_m3_v2_independent_blind import (
    EXPECTED_ATTACK_FAMILIES,
)
from experiments.paper_v1.benchmarks.prepare_independent_blind_authoring_kit import (
    build_slots,
    prepare_kit,
)


def test_authoring_slots_have_exact_distribution_and_unique_templates() -> None:
    slots = build_slots()
    assert len(slots) == 600
    assert len({row["slot_id"] for row in slots}) == 600
    assert len({row["template_id_prefix"] for row in slots}) == 600
    assert Counter(row["sample_type"] for row in slots) == {
        "attack": 360,
        "benign_no_tool": 120,
        "benign_legal_tool": 120,
    }
    attacks = [row for row in slots if row["sample_type"] == "attack"]
    assert Counter(row["attack_family"] for row in attacks) == {
        family: 40 for family in EXPECTED_ATTACK_FAMILIES
    }
    assert {row["author_group"] for row in slots} == {1, 2}


def test_authoring_kit_is_content_free_and_non_result(tmp_path: Path) -> None:
    manifest = prepare_kit(tmp_path)
    assert manifest["status"] == "completed_authoring_kit_only"
    assert manifest["candidate_cases_created"] == 0
    assert manifest["result_eligible_for_confirmatory_q2_tables"] is False
    assert manifest["assignment_slot_count"] == 600
    for artifact in manifest["artifacts"].values():
        assert not Path(artifact["path"]).is_absolute()
        assert (tmp_path / artifact["path"]).is_file()
    assert "validate_candidate_before_release.py" in manifest["artifacts"]
    template = json.loads((tmp_path / "case_template.json").read_text(encoding="utf-8"))
    assert "authorized_actions" not in template
    assert template["offline_evaluation"]["offline_only"] is True
    instructions = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Project developers must not fill" in instructions
    assert "Do not ask two people to inspect all" in instructions
    assert "validate_candidate_before_release.py" in instructions


def test_packaged_pre_release_validator_accepts_valid_candidate(tmp_path: Path) -> None:
    prepare_kit(tmp_path)
    slots = build_slots()
    sealed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    candidate_path = tmp_path / "m3_v2_independent_blind_candidate.jsonl"
    custody_path = tmp_path / "m3_v2_independent_blind_custody.json"
    rows = []
    for index, slot in enumerate(slots, 1):
        rows.append(
            {
                "schema_version": "paper-case-1.0",
                "dataset_version": "m3-v2-independent-blind-1.0",
                "case_id": f"M3V2-IB-TEST-{index:03d}",
                "template_id": f"{slot['template_id_prefix']}-TEST",
                "split": "independent_blind",
                "evidence_level": "independent_blind",
                "sample_type": slot["sample_type"],
                "attack_family": slot["attack_family"],
                "language": slot["language"],
                "authorization_profile": slot["authorization_profile"],
                "scenario_type": slot["scenario_type"],
                "mutation_id": f"test-mut-{index:03d}",
                "trusted_user_request": f"Independent synthetic request {index}",
                "trusted_app_context": {"request_id": f"ib-test-{index:03d}"},
                "untrusted_content": f"Independent synthetic untrusted content {index}",
                "untrusted_memory": [],
                "attack_dimensions": {},
                "offline_evaluation": {
                    "offline_only": True,
                    "expected_outcome": "test_label",
                    "expected_allowed_effects": [],
                    "expected_unsafe_effects": [],
                    "requires_tool_for_success": False,
                },
                "generation": {
                    "generator": "independent-test-generator",
                    "generator_kind": "independent_program",
                    "seed": "unit-test",
                },
                "custody": {
                    "independent_source": f"author-{slot['author_group']}",
                    "sealed_at": sealed_at,
                },
            }
        )
    candidate_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    candidate_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    custody_path.write_text(
        json.dumps(
            {
                "schema_version": "m3-independent-blind-custody-1.0",
                "status": "sealed_candidate",
                "candidate_filename": candidate_path.name,
                "candidate_sha256": candidate_sha,
                "candidate_row_count": 600,
                "independent_author_ids": ["author-1", "author-2"],
                "authoring_method": "independent_program unit-test",
                "authoring_environment": "isolated unit-test tempdir",
                "developer_access_before_seal": False,
                "sealed_at": sealed_at,
                "custodian_id": "custodian-test",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "pre_release_self_check.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(tmp_path / "validate_candidate_before_release.py"),
            "--candidate",
            str(candidate_path),
            "--custody-manifest",
            str(custody_path),
            "--output",
            str(report_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["passed_checks"] == report["total_checks"]
