"""Build pinned AgentDojo/InjecAgent compatibility evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agentdojo_adapter import build_agentdojo_index
from .common import sha256_file, write_jsonl
from .injecagent_adapter import build_injecagent_index


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXTERNAL = ROOT / "external" / "benchmarks"
DEFAULT_OUTPUT = ROOT / "outputs" / "paper_upgrade_v1" / "public_benchmarks"


def _git(checkout: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _lock_record(
    *,
    name: str,
    checkout: Path,
    url: str,
    license_name: str,
) -> dict[str, Any]:
    license_path = checkout / license_name
    return {
        "name": name,
        "repository": url,
        "commit": _git(checkout, "rev-parse", "HEAD"),
        "commit_date": _git(checkout, "log", "-1", "--format=%cI"),
        "license": "MIT",
        "license_file": license_name,
        "license_sha256": sha256_file(license_path),
        "checkout_tracked_in_parent": False,
    }


def build_all(
    *,
    external_root: Path = DEFAULT_EXTERNAL,
    output_root: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    agentdojo_root = external_root / "agentdojo"
    injecagent_root = external_root / "injecagent"
    agentdojo = build_agentdojo_index(agentdojo_root)
    injecagent = build_injecagent_index(injecagent_root)
    output_root.mkdir(parents=True, exist_ok=True)

    agent_utility = output_root / "agentdojo_v1_utility_index.jsonl"
    agent_security = output_root / "agentdojo_v1_security_index.jsonl"
    injec_security = output_root / "injecagent_security_index.jsonl"
    write_jsonl(agent_utility, agentdojo["utility_rows"])
    write_jsonl(agent_security, agentdojo["security_rows"])
    write_jsonl(injec_security, injecagent["rows"])

    lock = {
        "schema_version": "public-benchmark-lock-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repositories": [
            _lock_record(
                name="agentdojo",
                checkout=agentdojo_root,
                url="https://github.com/ethz-spylab/agentdojo.git",
                license_name="LICENSE",
            ),
            _lock_record(
                name="injecagent",
                checkout=injecagent_root,
                url="https://github.com/uiuc-kang-lab/InjecAgent.git",
                license_name="LICENCE",
            ),
        ],
        "protocol": {
            "agentdojo_version": "v1",
            "agentdojo_utility_tasks": len(agentdojo["utility_rows"]),
            "agentdojo_security_cases": len(agentdojo["security_rows"]),
            "injecagent_security_cases": len(injecagent["rows"]),
            "no_favorable_case_filtering": True,
            "gold_authorization_used_online": False,
        },
        "compatibility": {
            "agentdojo": {
                "status": "indexed_native_smoke_ready_formal_full_run_pending",
                "suite_counts": agentdojo["suite_counts"],
                "utility_sha256": agentdojo["utility_sha256"],
                "security_sha256": agentdojo["security_sha256"],
                "native_runner": "experiments.paper_v1.benchmarks.agentdojo_native_runner",
            },
            "injecagent": {
                "status": "indexed_replay_runner_diagnostic_ready_official_runner_pending",
                "tool_schema_count": injecagent["tool_schema_count"],
                "missing_tools": injecagent["missing_tools"],
                "security_sha256": injecagent["row_sha256"],
                "diagnostic_runner": "experiments.paper_v1.benchmarks.public_replay_runner",
            },
        },
        "artifacts": {
            "agentdojo_utility": {
                "path": agent_utility.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(agent_utility),
            },
            "agentdojo_security": {
                "path": agent_security.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(agent_security),
            },
            "injecagent_security": {
                "path": injec_security.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(injec_security),
            },
        },
    }
    lock_path = external_root / "benchmark_lock.json"
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_root / "compatibility_manifest.json").write_text(
        json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return lock


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-root", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    lock = build_all(external_root=args.external_root, output_root=args.output_root)
    print(json.dumps(lock["protocol"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
