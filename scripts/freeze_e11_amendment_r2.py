"""Create the E11 amendment execution-r2 freeze before any r2 model run."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_DIR = ROOT / "protocols" / "e11_amendment_v1"
OUTPUT = PROTOCOL_DIR / "freeze_r2.json"

ARTIFACTS = (
    ("protocol", "protocols/e11_amendment_v1/protocol.md"),
    ("protocol.execution_r2", "protocols/e11_amendment_v1/protocol_r2.md"),
    ("cases", "protocols/e11_amendment_v1/cases.jsonl"),
    ("fixtures", "protocols/e11_amendment_v1/fixtures.json"),
    ("runner", "scripts/e11_amendment_runner.py"),
    ("analyzer", "scripts/e11_amendment_analyzer.py"),
    ("freeze_builder", "scripts/freeze_e11_amendment_r2.py"),
    ("registrar", "scripts/register_e11_amendment_evidence.py"),
    ("final_analysis_builder", "scripts/build_final_analysis.py"),
    ("legacy_freeze", "protocols/e11_amendment_v1/freeze.json"),
    ("v3_blind_freeze", "outputs/experiments/blind_freeze_v3.json"),
    ("e13_thresholds", "outputs/experiments/E13/frozen_thresholds.json"),
    ("runtime.agent_runner", "m3_core/agent_runner.py"),
    ("runtime.case_views", "m3_core/case_views.py"),
    ("runtime.llm_client", "m3_core/llm_client.py"),
    ("runtime.run_batch", "m3_core/run_batch.py"),
    ("runtime.run_matrix", "m3_core/run_matrix.py"),
    ("runtime.tool_sandbox", "m3_core/tool_sandbox.py"),
    ("runtime.guard_config", "m3_guard/config.py"),
    ("runtime.guard_dataflow", "m3_guard/dataflow.py"),
    ("runtime.guard_detector", "m3_guard/detector.py"),
    ("runtime.guard_engine", "m3_guard/guard_engine.py"),
    ("runtime.guard_normalizer", "m3_guard/normalizer.py"),
    ("runtime.guard_policy_engine", "m3_guard/policy_engine.py"),
    ("runtime.metrics", "m3_eval/metrics.py"),
    ("runtime.statistics", "m3_eval/statistics.py"),
    ("runtime.figure_manifest", "m3_eval/figure_manifest.py"),
    ("runtime.attack_case_schema", "schemas/attack_case.schema.json"),
    ("runtime.run_log_schema", "schemas/run_log.schema.json"),
    ("runtime.tool_call_schema", "schemas/tool_call.schema.json"),
)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write(payload: dict) -> None:
    handle, name = tempfile.mkstemp(prefix=".freeze_r2.", suffix=".tmp", dir=PROTOCOL_DIR)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(name, OUTPUT)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def build() -> dict:
    artifacts = []
    by_role = {}
    for role, relative in ARTIFACTS:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"cannot freeze missing or linked artifact: {relative}")
        item = {"role": role, "path": relative, "sha256": _sha256(path)}
        artifacts.append(item)
        by_role[role] = item
    return {
        "schema_version": "1.0",
        "protocol_id": "E11_POSTHOC_AMENDMENT_V1",
        "amendment_type": "posthoc_protocol_amendment",
        "pre_registered": False,
        "denominator_policy": "excluded_from_original_e11_denominator",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "visualization_revision": 2,
        "execution_revision": "r2",
        "revision_reason": "Current runtime drifted from the preserved historical execution freeze; r2 binds current code and requires fresh smoke and formal runs without changing the research protocol.",
        "supersedes_freeze_sha256": by_role["legacy_freeze"]["sha256"],
        "historical_v3_freeze_integrity_mode": "hash_bound_reference_only",
        "formal_model": "qwen3:4b-instruct",
        "formal_case_count": 24,
        "formal_logical_runs": 48,
        "smoke_case_count": 4,
        "smoke_logical_runs": 8,
        "v3_blind_freeze_sha256": by_role["v3_blind_freeze"]["sha256"],
        "e13_thresholds_sha256": by_role["e13_thresholds"]["sha256"],
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare the current tree with the existing r2 freeze")
    args = parser.parse_args()
    payload = build()
    if args.check:
        if not OUTPUT.is_file():
            raise FileNotFoundError(OUTPUT)
        existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        payload["created_at"] = existing.get("created_at")
        if payload != existing:
            raise RuntimeError("E11 execution-r2 freeze drift detected")
        print(json.dumps({"status": "verified", "path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": _sha256(OUTPUT)}, indent=2))
        return 0
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite existing freeze: {OUTPUT}")
    _write(payload)
    print(json.dumps({"status": "created", "path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": _sha256(OUTPUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
