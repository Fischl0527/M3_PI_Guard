from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.audit_context_experiments import audit_e9, audit_e14


def _write_e9_job(root: Path, context: int, prompt_tokens: int) -> None:
    job = root / f"derived__e9__qwen__ctx_{context}"
    job.mkdir(parents=True)
    rows = [
        {
            "step": 1,
            "prompt_tokens": prompt_tokens,
            "parse_ok": True,
        }
        for _ in range(3)
    ]
    (job / "condition.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def _write_e14(path: Path, values: dict[str, list[float]]) -> None:
    fields = ["num_ctx", "condition", "prompt_tokens_median"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for condition, medians in values.items():
            for context, median in zip((2048, 4096, 8192, 16384), medians):
                writer.writerow(
                    {
                        "num_ctx": context,
                        "condition": condition,
                        "prompt_tokens_median": median,
                    }
                )


def test_e9_passes_only_for_calibrated_increasing_workloads(tmp_path: Path) -> None:
    for context in (2048, 4096, 8192, 16384):
        _write_e9_job(tmp_path, context, context)
    result = audit_e9(tmp_path)
    assert result["status"] == "pass"
    assert result["no_context_collapse"] is True


def test_e9_rejects_collapsed_contexts(tmp_path: Path) -> None:
    for context, observed in zip((2048, 4096, 8192, 16384), (6300, 8192, 8192, 8192)):
        _write_e9_job(tmp_path, context, observed)
    result = audit_e9(tmp_path)
    assert result["status"] == "fail"
    assert result["no_context_collapse"] is False


def test_e14_accepts_material_prompt_scaling(tmp_path: Path) -> None:
    path = tmp_path / "performance.csv"
    _write_e14(path, {"off": [2048, 4096, 8192, 16384], "full_guard": [2048, 4096, 8192, 16384]})
    assert audit_e14(path)["status"] == "pass"


def test_e14_rejects_flat_prompt_workloads(tmp_path: Path) -> None:
    path = tmp_path / "performance.csv"
    _write_e14(path, {"off": [486.5] * 4, "full_guard": [230.5] * 4})
    result = audit_e14(path)
    assert result["status"] == "fail"
    assert all(not item["valid"] for item in result["conditions"])
