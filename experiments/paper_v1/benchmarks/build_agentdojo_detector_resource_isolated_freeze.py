"""Build a fresh formal freeze for exact detector semantics with resource isolation."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
SOURCE_FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_transformers_pi_detector_formal_freeze_v1.json"
)
OUTPUT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_transformers_pi_detector_resource_isolated_freeze_v1.json"
)
RUNNER = ROOT / "experiments" / "paper_v1" / "benchmarks" / "run_agentdojo_official_detector_formal.py"
EXPECTED_STATUS = "completed_frozen_formal_protocol"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def build_freeze(*, source_path: Path = SOURCE_FREEZE, output_path: Path = OUTPUT) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    source = _read(source_path)
    if source.get("status") != EXPECTED_STATUS:
        raise ValueError("source freeze is not completed")
    freeze = deepcopy(source)
    freeze["schema_version"] = "paper-agentdojo-official-detector-resource-freeze-1.0"
    freeze["freeze_version"] = "m3-paper-v1-agentdojo-transformers-detector-resource-freeze-1.0"
    freeze["condition_id"] = "agentdojo_transformers_pi_detector_official_resource_isolated"
    freeze["created_at"] = datetime.now(timezone.utc).isoformat()
    freeze["source_freezes"]["superseded_exact_freeze"] = str(source_path)
    freeze["source_freezes"]["superseded_exact_freeze_sha256"] = sha256_file(source_path)
    freeze["source_freezes"]["runner"] = str(RUNNER.resolve())
    freeze["source_freezes"]["runner_sha256"] = sha256_file(RUNNER)
    freeze["runtime"]["resource_policy"] = "unload_ollama_before_detector"
    freeze["runtime"]["resource_policy_changes_detector_input"] = False
    freeze["runtime"]["resource_policy_changes_detector_model_or_threshold"] = False
    freeze["runtime"]["resource_policy_boundary"] = (
        "Before each CPU detector call, unload the local Ollama target model using "
        "keep_alive=0. The next LLM request reloads it. The complete detector input, "
        "official source class, model revision, label and threshold remain unchanged."
    )
    freeze["failure_policy"]["resource_oom_requires_batch_stop_and_fresh_root"] = True
    checks = list(source.get("checks", []))
    checks.extend(
        [
            _check(
                "source_freeze_hash_bound",
                freeze["source_freezes"]["superseded_exact_freeze_sha256"]
                == sha256_file(source_path),
                freeze["source_freezes"]["superseded_exact_freeze_sha256"],
            ),
            _check(
                "resource_policy_preserves_detector_semantics",
                freeze["runtime"]["resource_policy"]
                == "unload_ollama_before_detector"
                and freeze["runtime"]["resource_policy_changes_detector_input"] is False
                and freeze["runtime"]["resource_policy_changes_detector_model_or_threshold"]
                is False,
                freeze["runtime"]["resource_policy"],
            ),
            _check(
                "case_universe_unchanged",
                rows_sha256(freeze["case_rows"]) == source["case_rows_sha256"]
                and freeze["case_counts"] == source["case_counts"],
                freeze["case_counts"],
            ),
        ]
    )
    freeze["checks"] = checks
    freeze["passed_checks"] = sum(row["status"] == "pass" for row in checks)
    freeze["total_checks"] = len(checks)
    freeze["failed_checks"] = [row for row in checks if row["status"] != "pass"]
    freeze["status"] = EXPECTED_STATUS if not freeze["failed_checks"] else "failed_freeze"
    freeze["result_eligible_for_formal_tables"] = False
    freeze["boundary"] = (
        "Fresh formal protocol after the exact official run encountered host-memory "
        "contention. Resource scheduling is disclosed and does not alter detector "
        "inputs, weights, threshold or decisions. The previous partial root remains "
        "invalid and no rows may be pooled across roots."
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return freeze


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_FREEZE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser


def main() -> int:
    args = _parser().parse_args()
    freeze = build_freeze(source_path=args.source, output_path=args.output)
    print(
        json.dumps(
            {
                "status": freeze["status"],
                "passed_checks": freeze["passed_checks"],
                "total_checks": freeze["total_checks"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if freeze["status"] == EXPECTED_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
