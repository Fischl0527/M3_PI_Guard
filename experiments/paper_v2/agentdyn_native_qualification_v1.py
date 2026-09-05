"""Bounded native AgentDyn loader/evaluator qualification, no provider calls.

Known-answer execution below is an OFFLINE fixture check, never online policy
compilation or experimental model evidence. No default benchmark script runs.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "external/benchmarks/agentdyn"
COMMIT = "5353cf7615b135cace8d07c8f12dac53a16b6db3"
SEED = "m3-e8-agentdyn-native-2026-09-05"
OUTPUT = ROOT / "outputs/experiments/agentdyn_native_qualification_v1"
PROTOCOL = ROOT / "protocols/paper_upgrade_v2/e8_agentdyn_native_v1"


def selected_ids(suite: str, ids: list[str]) -> list[str]:
    return sorted(
        ids,
        key=lambda task: hashlib.sha256(f"{SEED}|{suite}|{task}".encode()).hexdigest(),
    )[:6]


@contextlib.contextmanager
def offline_boundary():
    """Block network, process creation and physical writes during native execution."""
    active = [True]
    observed: list[str] = []

    def audit(event, args):
        if not active[0]:
            return
        prohibited = event.startswith(
            ("socket.", "subprocess.", "os.exec", "os.spawn")
        ) or event in {"os.system", "os.remove", "os.rename", "os.mkdir", "os.rmdir"}
        if event == "open":
            mode, flags = args[1], args[2]
            prohibited = bool(
                isinstance(mode, str) and any(c in mode for c in "wax+")
            ) or bool(isinstance(flags, int) and flags & (1 | 2 | 64 | 512 | 1024))
        if prohibited:
            observed.append(event)
            raise PermissionError("native qualification prohibited physical effect")

    sys.addaudithook(audit)
    try:
        yield observed
    finally:
        active[0] = False


def qualify() -> dict[str, Any]:
    if not sys.flags.utf8_mode:
        raise ValueError(
            "AgentDyn YAML requires process-local Python -X utf8 on Windows"
        )
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True
    ).strip()
    if actual != COMMIT or "agentdojo" in sys.modules:
        raise ValueError("native source identity/collision")
    sys.path.insert(
        0, str(SOURCE / "src")
    )  # current worker only; no installation/env writes
    from agentdojo.agent_pipeline.ground_truth_pipeline import GroundTruthPipeline
    from agentdojo.task_suite import get_suite

    metadata, selected = [], []
    for name in ("shopping", "github", "dailylife"):
        suite = get_suite("v1", name)
        ids = selected_ids(name, list(suite.user_tasks))
        metadata.append(
            {
                "suite": name,
                "user_task_count": len(suite.user_tasks),
                "injection_task_class_count": len(suite.injection_tasks),
                "selected_ids": ids,
            }
        )
        selected.extend({"suite": name, "user_task_id": task} for task in ids)
    # Freeze deterministic task membership before evaluating any control outcome.
    PROTOCOL.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source_url": "https://github.com/SaFo-Lab/AgentDyn",
        "source_commit": COMMIT,
        "seed": SEED,
        "native_version": "v1",
        "sample": selected,
        "selection_does_not_use_model_or_utility_outcomes": True,
        "status": "offline_qualification_sample_not_final_attack_plan",
    }
    path = PROTOCOL / "qualification_sample_v1.json"
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise ValueError("native sample drift")
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    results = []
    for item in selected:
        suite = get_suite("v1", item["suite"])
        task = suite.get_user_task_by_id(item["user_task_id"])
        row = dict(item)
        with offline_boundary() as blocked, contextlib.redirect_stdout(io.StringIO()):
            try:
                env = task.init_environment(
                    suite.load_and_inject_default_environment({})
                )
                row["noop_utility"] = bool(
                    task.utility(
                        "", env.model_copy(deep=True), env.model_copy(deep=True)
                    )
                )
                # Local native framework only. No LLM, endpoint or real user account exists.
                utility, _ = suite.run_task_with_pipeline(
                    GroundTruthPipeline(task), task, None, {}, verbose=False
                )
                row.update(status="completed", known_answer_utility=bool(utility))
            except Exception as exc:
                row.update(
                    status="native_qualification_failure", error_type=type(exc).__name__
                )
            row["blocked_physical_effect_attempts"] = len(blocked)
        results.append(row)
    result = {
        "source_commit": COMMIT,
        "native_suites": metadata,
        "selected_tasks": 18,
        "results": results,
        "provider_calls": 0,
        "known_answer_successes": sum(
            r.get("known_answer_utility") is True for r in results
        ),
        "noop_utility_true": sum(r.get("noop_utility") is True for r in results),
        "failures": sum(r["status"] != "completed" for r in results),
        "blocked_physical_effect_attempts": sum(
            r["blocked_physical_effect_attempts"] for r in results
        ),
        "inference": "native_fixture_check_only_not_agent_performance",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "qualification_v2.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = qualify()
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"results", "native_suites"}}
        )
    )
