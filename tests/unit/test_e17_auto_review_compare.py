from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from experiments.e17_review import REVIEW_FIELDS
from scripts import e17_auto_review_compare as comparator


def _evidence(blind_id: str) -> dict[str, str]:
    return {
        "blind_id": blind_id,
        "task_excerpt": f"task {blind_id}",
        "authorized_actions": "[]",
        "prohibited_actions": "[]",
        "observed_tool_calls": "[]",
        "guard_decisions": "[]",
        "final_statuses": "[\"completed\"]",
        "guard_reasons": "[]",
        "output_excerpt": "done",
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _template_rows() -> list[dict[str, str]]:
    return [
        {
            **_evidence(blind_id),
            "reviewer_id": "",
            "independent_attestation": "",
            "primary_code": "",
            "secondary_codes": "",
            "confidence": "",
            "rationale": "",
        }
        for blind_id in ("blind-1", "blind-2")
    ]


def _completed(
    templates: list[dict[str, str]], reviewer_id: str, codes: tuple[str, str]
) -> list[dict[str, str]]:
    return [
        {
            **row,
            "reviewer_id": reviewer_id,
            "independent_attestation": comparator.AUTOMATED_ATTESTATION,
            "primary_code": code,
            "secondary_codes": "",
            "confidence": "high",
            "rationale": f"visible evidence supports {code}",
        }
        for row, code in zip(templates, codes)
    ]


def test_compare_validates_and_reports_agreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparator, "EXPECTED_ROWS", 2)
    templates = _template_rows()
    template_a = tmp_path / "template_a.csv"
    template_b = tmp_path / "template_b.csv"
    reviewer_a = tmp_path / "reviewer_a.csv"
    reviewer_b = tmp_path / "reviewer_b.csv"
    _write_csv(template_a, templates)
    _write_csv(template_b, templates)
    _write_csv(reviewer_a, _completed(templates, "auto-a", ("leak", "none")))
    _write_csv(reviewer_b, _completed(templates, "auto-b", ("leak", "other")))

    result = comparator.compare(
        reviewer_a=reviewer_a,
        reviewer_b=reviewer_b,
        template_a=template_a,
        template_b=template_b,
        output_dir=tmp_path / "out",
    )

    assert result["diagnostic_only"] is True
    assert result["human_review_gate_satisfied"] is False
    assert result["primary_agreement"]["count"] == 1
    assert result["full_code_set_agreement"]["count"] == 1
    assert result["disagreements"] == 1
    saved = json.loads((tmp_path / "out" / "comparison.json").read_text(encoding="utf-8"))
    assert saved["primary_agreement"]["rate"] == 0.5
    with (tmp_path / "out" / "automated_disagreements.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        disagreements = list(csv.DictReader(handle))
    assert [row["blind_id"] for row in disagreements] == ["blind-2"]


def test_compare_rejects_evidence_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparator, "EXPECTED_ROWS", 2)
    templates = _template_rows()
    template_a = tmp_path / "template_a.csv"
    template_b = tmp_path / "template_b.csv"
    reviewer_a = tmp_path / "reviewer_a.csv"
    reviewer_b = tmp_path / "reviewer_b.csv"
    _write_csv(template_a, templates)
    _write_csv(template_b, templates)
    mutated = _completed(templates, "auto-a", ("leak", "none"))
    mutated[0]["task_excerpt"] = "changed"
    _write_csv(reviewer_a, mutated)
    _write_csv(reviewer_b, _completed(templates, "auto-b", ("leak", "none")))

    with pytest.raises(comparator.AutomatedReviewValidationError, match="evidence field"):
        comparator.compare(
            reviewer_a=reviewer_a,
            reviewer_b=reviewer_b,
            template_a=template_a,
            template_b=template_b,
            output_dir=tmp_path / "out",
        )


def test_compare_rejects_manual_attestation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparator, "EXPECTED_ROWS", 2)
    templates = _template_rows()
    template = tmp_path / "template.csv"
    review = tmp_path / "review.csv"
    _write_csv(template, templates)
    rows = _completed(templates, "auto-a", ("leak", "none"))
    rows[0]["independent_attestation"] = "independent_manual_review_completed"
    _write_csv(review, rows)

    with pytest.raises(comparator.AutomatedReviewValidationError, match="attestation"):
        comparator._validate_review(review, template)


def test_compare_binds_corrected_source_index_and_packet_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(comparator, "EXPECTED_ROWS", 2)
    templates = _template_rows()
    template_a = tmp_path / "template_a.csv"
    template_b = tmp_path / "template_b.csv"
    reviewer_a = tmp_path / "reviewer_a.csv"
    reviewer_b = tmp_path / "reviewer_b.csv"
    _write_csv(template_a, templates)
    _write_csv(template_b, templates)
    _write_csv(reviewer_a, _completed(templates, "auto-a", ("leak", "none")))
    _write_csv(reviewer_b, _completed(templates, "auto-b", ("leak", "none")))
    source_index = tmp_path / "e17_source_index_corrected_v2.json"
    source_index.write_text('{"schema_version":"2.0"}\n', encoding="utf-8")
    source_hash = comparator._sha256(source_index)
    source_record = {"path": str(source_index), "sha256": source_hash}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "configuration": {
                    "source_mode": "formal_program_corrected_context",
                    "source_index": source_record,
                },
                "plan": {
                    "source_mode": "formal_program_corrected_context",
                    "source_index": source_record,
                    "candidate_count": 2,
                },
                "artifacts": [
                    {
                        "path": str(path),
                        "bytes": path.stat().st_size,
                        "sha256": comparator._sha256(path),
                    }
                    for path in (template_a, template_b)
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        comparator,
        "load_source_index",
        lambda _path: {
            "source_mode": "formal_program_corrected_context",
            "coverage": {
                "status": "pass",
                "duplicate_logical_run_count": 0,
                "duplicate_logical_step_count": 0,
            },
        },
    )
    result = comparator.compare(
        reviewer_a=reviewer_a,
        reviewer_b=reviewer_b,
        template_a=template_a,
        template_b=template_b,
        output_dir=tmp_path / "out",
        source_index=source_index,
        e17_manifest=manifest,
    )
    assert result["source_contract"]["source_mode"] == "formal_program_corrected_context"
    assert result["source_contract"]["source_index"]["sha256"] == source_hash

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["configuration"]["source_index"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(comparator.AutomatedReviewValidationError, match="binding mismatch"):
        comparator.compare(
            reviewer_a=reviewer_a,
            reviewer_b=reviewer_b,
            template_a=template_a,
            template_b=template_b,
            output_dir=tmp_path / "out-2",
            source_index=source_index,
            e17_manifest=manifest,
        )
