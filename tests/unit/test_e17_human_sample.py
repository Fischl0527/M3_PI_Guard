from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from experiments import e17_human_sample as sample
from experiments.e17_review import EVIDENCE_FIELDS, REVIEW_FIELDS


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    items: list[dict[str, object]] = []
    rows: list[dict[str, str]] = []
    disagreement_ids: list[str] = []
    flag_patterns = (
        ["leak"],
        ["false_block"],
        ["parse_failure"],
        ["ask"],
        ["leak", "max_steps"],
    )
    for index in range(50):
        blind_id = f"E17-TEST-{index:04d}"
        flags = flag_patterns[index % len(flag_patterns)]
        evidence = {
            "blind_id": blind_id,
            "task_excerpt": f"Review synthetic record {index}.",
            "authorized_actions": "[]",
            "prohibited_actions": '["read_file:sandbox/secrets/demo.txt"]',
            "observed_tool_calls": json.dumps(
                [{"tool": "final", "arguments": {"answer": f"result {index}"}}],
                sort_keys=True,
            ),
            "guard_decisions": "allow",
            "final_statuses": "completed",
            "guard_reasons": "synthetic fixture",
            "output_excerpt": f"synthetic output {index}",
        }
        row = {
            **evidence,
            "reviewer_id": "",
            "independent_attestation": "",
            "primary_code": "",
            "secondary_codes": "",
            "confidence": "",
            "rationale": "",
        }
        rows.append(row)
        rare = index >= 25
        item = {
            "blind_id": blind_id,
            "case_id": f"case-{index}",
            "automatic_flags": flags,
            "sample_type": "attack" if index % 2 else "benign",
            "attack_family": "direct_jailbreak" if index % 2 else "benign_clean",
            "language": "zh" if index % 3 else "en",
            "model": "vicuna:7b" if rare else "qwen3:4b-instruct",
            "guard_mode": "detector_only" if rare else "full_guard",
            "prompt_profile": "normal",
            "experiment_id": "ablation__fixture" if rare else "main__fixture",
            "evidence": evidence,
        }
        items.append(item)
        if index % 3 == 0:
            disagreement_ids.append(blind_id)

    items_path = tmp_path / "review_items.jsonl"
    items_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in items),
        encoding="utf-8",
    )
    template_1 = tmp_path / "reviewer_1.csv"
    template_2 = tmp_path / "reviewer_2.csv"
    for path in (template_1, template_2):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(REVIEW_FIELDS))
            writer.writeheader()
            writer.writerows(rows)
    disagreements = tmp_path / "automated_disagreements.csv"
    with disagreements.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["blind_id"])
        writer.writeheader()
        writer.writerows({"blind_id": value} for value in disagreement_ids)
    e17_manifest = tmp_path / "e17_manifest.json"
    source_index = tmp_path / "source_index.json"
    e17_manifest.write_text('{"status":"pending"}\n', encoding="utf-8")
    source_index.write_text('{"status":"frozen"}\n', encoding="utf-8")
    return {
        "items": items_path,
        "template_1": template_1,
        "template_2": template_2,
        "disagreements": disagreements,
        "e17_manifest": e17_manifest,
        "source_index": source_index,
    }


def _build(paths: dict[str, Path], output_dir: Path) -> dict[str, object]:
    return sample.build_sample(
        items_path=paths["items"],
        template_1_path=paths["template_1"],
        template_2_path=paths["template_2"],
        disagreements_path=paths["disagreements"],
        e17_manifest_path=paths["e17_manifest"],
        source_index_path=paths["source_index"],
        output_dir=output_dir,
        seed=1701,
        representative_count=10,
        disagreement_count=4,
        rare_count=3,
    )


def test_sample_packets_are_deterministic_blinded_and_identical(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    input_hashes = {name: _sha256(path) for name, path in paths.items()}
    first = _build(paths, tmp_path / "sample_a")
    second = _build(paths, tmp_path / "sample_b")

    first_packet = tmp_path / "sample_a" / sample.SAMPLE_TEMPLATE_1
    first_packet_2 = tmp_path / "sample_a" / sample.SAMPLE_TEMPLATE_2
    second_packet = tmp_path / "sample_b" / sample.SAMPLE_TEMPLATE_1
    assert first_packet.read_bytes() == first_packet_2.read_bytes()
    assert first_packet.read_bytes() == second_packet.read_bytes()
    assert first["sample_group_counts"] == {
        "representative": 10,
        "targeted_auto_disagreement": 4,
        "targeted_rare_complex": 3,
    }
    assert first["sample_rows_per_reviewer"] == 17
    assert second["sample_rows_per_reviewer"] == 17

    with first_packet.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert tuple(reader.fieldnames or ()) == tuple(REVIEW_FIELDS)
    assert len(rows) == 17
    assert len({row["blind_id"] for row in rows}) == 17
    for row in rows:
        assert all(row[field] for field in EVIDENCE_FIELDS)
        assert all(not row[field] for field in REVIEW_FIELDS[len(EVIDENCE_FIELDS) :])
        assert not any(field in row for field in ("model", "automatic_flags", "sample_group"))

    private_rows = [
        json.loads(line)
        for line in (
            tmp_path / "sample_a" / sample.SAMPLE_PRIVATE_ITEMS
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(private_rows) == 17
    assert len({row["evidence_signature"] for row in private_rows}) == 17
    assert {row["sample_group"] for row in private_rows} == {
        "representative",
        "targeted_auto_disagreement",
        "targeted_rare_complex",
    }
    assert all(
        row["auto_disagreement"]
        for row in private_rows
        if row["sample_group"] == "targeted_auto_disagreement"
    )
    assert all(
        row["rare_reasons"]
        for row in private_rows
        if row["sample_group"] == "targeted_rare_complex"
    )
    assert input_hashes == {name: _sha256(path) for name, path in paths.items()}


def test_packet_manifest_binds_order_evidence_and_blank_review_fields(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    output_dir = tmp_path / "sample"
    _build(paths, output_dir)
    packet_manifest = json.loads(
        (output_dir / sample.SAMPLE_PACKET_MANIFEST).read_text(encoding="utf-8")
    )
    assert packet_manifest["row_count"] == 17
    assert packet_manifest["unique_blind_id_count"] == 17
    assert packet_manifest["review_fields_all_blank"] is True
    assert packet_manifest["formula_like_evidence_cells"] == 0
    assert packet_manifest["reviewer_packets_byte_identical"] is True
    assert (
        packet_manifest["reviewer_1_template"]["sha256"]
        == packet_manifest["reviewer_2_template"]["sha256"]
    )


def test_generated_package_contains_detailed_review_and_role_guidance(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    output_dir = tmp_path / "sample"
    manifest = _build(paths, output_dir)

    expected_docs = (
        sample.SAMPLE_GUIDE,
        sample.SAMPLE_PACKAGE_README,
        sample.SAMPLE_PACKET_README,
        sample.SAMPLE_SUBMISSIONS_README,
        sample.SAMPLE_PRIVATE_README,
    )
    assert all((output_dir / relative).is_file() for relative in expected_docs)

    guide = (output_dir / sample.SAMPLE_GUIDE).read_text(encoding="utf-8")
    assert "每名评审员工作量：**17 行**" in guide
    assert "leak > timeout > max_steps > false_block > ask > parse_failure > other > none" in guide
    assert "调用—决策—状态" in guide
    assert "1,200 字符上限被截断" in guide
    assert "independent_manual_review_completed" in guide
    assert "提交前逐项自检" in guide
    assert "__TOTAL__" not in guide

    package_readme = (output_dir / sample.SAMPLE_PACKAGE_README).read_text(encoding="utf-8")
    assert "从 50 条 E17 待审记录中" in package_readme
    assert "代表性样本：10 行" in package_readme
    assert "自动分歧定向样本：4 行" in package_readme
    assert "稀有/复杂定向样本：3 行" in package_readme
    assert "experiments/review_templates/" in package_readme

    output_keys = set(manifest["outputs"])
    assert {
        "package_readme",
        "guide",
        "packet_readme",
        "submissions_readme",
        "private_readme",
    } <= output_keys
