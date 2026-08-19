from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import experiments.paper_v2.independent_blind_closeout_v1 as blind
from experiments.paper_v2.contracts import canonical_json_bytes


def _write_candidate(tmp_path: Path) -> tuple[Path, list[dict[str, object]]]:
    slots = blind._read_jsonl(blind.DEFAULT_SLOTS)
    rows: list[dict[str, object]] = []
    for index, slot in enumerate(slots, start=1):
        rows.append(
            {
                **slot,
                "schema_version": "paper-case-1.0",
                "dataset_version": "m3-paper-v2-independent-blind-1.0",
                "case_id": f"independent-{index:04d}",
                "split": "independent_blind",
                "trusted_app_context": {"request_id": f"request-{index:04d}"},
                "trusted_user_request": f"Independent task {index}",
                "untrusted_content": f"Independent content {index}",
                "untrusted_memory": [],
                "custody": {
                    "independent_source": f"author-{slot['independent_author_group']}",
                    "sealed_at": "2026-08-02T00:00:00+08:00",
                },
            }
        )
    path = tmp_path / "blind_execution.jsonl"
    path.write_bytes(b"".join(canonical_json_bytes(row) + b"\n" for row in rows))
    return path, rows


def _write_custody(tmp_path: Path, candidate: Path) -> Path:
    value = {
        "schema_version": "m3-paper-v2-independent-custody-2.0",
        "status": "sealed_candidate_labels_held_by_custodian",
        "candidate_filename": candidate.name,
        "candidate_row_count": 600,
        "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "label_file_sha256": "b" * 64,
        "custodian_id": "independent-custodian-test",
        "custodian_signature": "detached-signature-test-value",
        "sealed_at": "2026-08-02T00:00:00+08:00",
        "developer_access_before_seal": False,
    }
    path = tmp_path / "custody.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_clean_execution_set_is_admitted_without_label_access(tmp_path: Path) -> None:
    candidate, _ = _write_candidate(tmp_path)
    custody = _write_custody(tmp_path, candidate)

    admission = blind.audit_sealed_execution_set(
        execution_set_path=candidate,
        custody_manifest_path=custody,
    )

    assert admission["status"].endswith("labels_unopened")
    assert admission["evidence_boundary"]["label_file_opened"] is False
    assert admission["evidence_boundary"]["network_calls_made"] == 0
    assert all(admission["custody_checks"].values())
    assert all(admission["data_checks"].values())


def test_six_condition_plan_has_3600_unique_label_free_items(tmp_path: Path) -> None:
    candidate, _ = _write_candidate(tmp_path)
    custody = _write_custody(tmp_path, candidate)
    admission = blind.audit_sealed_execution_set(
        execution_set_path=candidate,
        custody_manifest_path=custody,
    )

    plan = blind.build_six_condition_plan(
        execution_set_path=candidate,
        admission=admission,
    )

    assert len(plan) == 3600
    assert len({row["work_key"] for row in plan}) == 3600
    assert {row["condition_id"] for row in plan} == set(blind.CONDITIONS)
    assert all(row["result_fields_present"] is False for row in plan)
    assert all(row["external_effects_enabled"] is False for row in plan)


@pytest.mark.parametrize(
    "field,value",
    [
        ("offline_evaluation", {"expected_outcome": "unsafe"}),
        ("gold_label", "unsafe"),
        ("unsafe_effect", True),
    ],
)
def test_label_or_result_field_rejects_candidate(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    candidate, rows = _write_candidate(tmp_path)
    rows[0][field] = value
    candidate.write_bytes(
        b"".join(canonical_json_bytes(row) + b"\n" for row in rows)
    )
    custody = _write_custody(tmp_path, candidate)

    admission = blind.audit_sealed_execution_set(
        execution_set_path=candidate,
        custody_manifest_path=custody,
    )

    assert admission["status"] == "sealed_execution_set_rejected"
    assert admission["data_checks"]["forbidden_label_fields_absent"] is False


def test_custody_hash_or_preseal_access_rejects_candidate(tmp_path: Path) -> None:
    candidate, _ = _write_candidate(tmp_path)
    custody_path = _write_custody(tmp_path, candidate)
    custody = json.loads(custody_path.read_text(encoding="utf-8"))
    custody["candidate_sha256"] = "0" * 64
    custody["developer_access_before_seal"] = True
    custody_path.write_text(json.dumps(custody), encoding="utf-8")

    admission = blind.audit_sealed_execution_set(
        execution_set_path=candidate,
        custody_manifest_path=custody_path,
    )

    assert admission["status"] == "sealed_execution_set_rejected"
    assert admission["custody_checks"]["candidate_sha256_matches"] is False
    assert admission["custody_checks"]["developer_had_no_preseal_access"] is False

