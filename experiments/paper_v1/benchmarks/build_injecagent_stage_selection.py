"""Build result-blind stratified selections for InjecAgent stage diagnostics.

The selection file is intentionally lightweight: it records case identifiers
and immutable public metadata, but no model outputs, attacker instructions,
tool responses, expected achievements, or Guard decisions.  A runner can then
consume the frozen case ids with ``--selection`` so expansion diagnostics do not
depend on post-hoc favorable-case picking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import rows_sha256, sha256_file
from .injecagent_stage_runner import DEFAULT_CHECKOUT, build_stage_rows


SELECTION_SCHEMA_VERSION = "paper-injecagent-stage-selection-1.0"
DEFAULT_SELECTION_OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "protocols"
    / "paper_upgrade_v1"
    / "injecagent_stage_selection_v1.json"
)
DEFAULT_SELECTION_SEED = "m3-paper-v1-injecagent-stage-selection-v1"


def _stable_key(seed: str, case_id: str) -> str:
    return hashlib.sha256(f"{seed}\n{case_id}".encode("utf-8")).hexdigest()


def _bucket_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("suite", "")),
        str(dict(row.get("offline_evaluation", {})).get("attack_type", "")),
    )


def _case_id(row: Mapping[str, Any]) -> str:
    return str(row.get("benchmark_case_id", ""))


def _safe_case_metadata(row: Mapping[str, Any], *, seed: str, rank: int) -> dict[str, Any]:
    offline = dict(row.get("offline_evaluation", {}))
    online = dict(row.get("online_inputs", {}))
    tool_schemas = dict(online.get("tool_schemas", {}))
    attacker_tools = [str(tool) for tool in offline.get("attacker_tools", [])]
    return {
        "case_id": _case_id(row),
        "suite": str(row.get("suite", "")),
        "attack_type": str(offline.get("attack_type", "")),
        "expected_user_tool": str(offline.get("expected_user_tool", "")),
        "attacker_tool_count": len(attacker_tools),
        "exposed_tool_count": len(tool_schemas),
        "stable_rank": rank,
        "stable_key": _stable_key(seed, _case_id(row)),
    }


def build_injecagent_stage_selection(
    rows: Iterable[Mapping[str, Any]],
    *,
    target_size: int = 30,
    seed: str = DEFAULT_SELECTION_SEED,
    suites: set[str] | None = None,
) -> dict[str, Any]:
    """Select a deterministic, result-blind set of InjecAgent stage cases.

    Rows are grouped by ``suite`` and official ``Attack Type``.  The selector
    then round-robins across non-empty buckets ordered by suite and attack type,
    using a stable SHA-256 rank within each bucket.  This gives balanced
    coverage when the target size is small and remains deterministic across
    machines.
    """

    if target_size <= 0:
        raise ValueError("target_size must be positive")
    source_rows = [dict(row) for row in rows]
    candidates = [
        row
        for row in source_rows
        if (not suites or str(row.get("suite", "")) in suites)
        and dict(row.get("compatibility", {})).get("index") == "compatible"
    ]
    if target_size > len(candidates):
        raise ValueError(
            f"target_size {target_size} exceeds available compatible cases {len(candidates)}"
        )

    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        buckets[_bucket_key(row)].append(row)
    for bucket_rows in buckets.values():
        bucket_rows.sort(key=lambda row: _stable_key(seed, _case_id(row)))

    bucket_order = sorted(buckets)
    pointers = {bucket: 0 for bucket in bucket_order}
    selected_rows: list[dict[str, Any]] = []
    while len(selected_rows) < target_size:
        progressed = False
        for bucket in bucket_order:
            index = pointers[bucket]
            if index >= len(buckets[bucket]):
                continue
            selected_rows.append(buckets[bucket][index])
            pointers[bucket] += 1
            progressed = True
            if len(selected_rows) >= target_size:
                break
        if not progressed:
            raise RuntimeError("selection exhausted before target size")

    selected_cases = [
        _safe_case_metadata(row, seed=seed, rank=rank)
        for rank, row in enumerate(selected_rows, 1)
    ]
    available_bucket_counts = Counter(
        f"{suite}|{attack_type}" for suite, attack_type in map(_bucket_key, candidates)
    )
    selected_bucket_counts = Counter(
        f"{case['suite']}|{case['attack_type']}" for case in selected_cases
    )
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "selection_id": f"injecagent-stage-stratified-{target_size}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": "injecagent",
        "benchmark_version": "official-release-2024",
        "evidence_status": "diagnostic_selection_not_formal_evidence",
        "result_blind": True,
        "uses_model_outputs": False,
        "uses_guard_outputs": False,
        "uses_attacker_instruction_text": False,
        "uses_tool_response_text": False,
        "uses_expected_achievement_text": False,
        "selection_rule": (
            "Compatible cases only; group by suite and official attack_type; "
            "stable SHA-256 rank within each bucket; round-robin buckets until "
            "target_size is reached."
        ),
        "seed": seed,
        "target_size": target_size,
        "selected_count": len(selected_cases),
        "source_case_count": len(source_rows),
        "compatible_candidate_count": len(candidates),
        "source_rows_sha256": rows_sha256(source_rows),
        "selected_cases_sha256": rows_sha256(selected_cases),
        "available_bucket_counts": dict(sorted(available_bucket_counts.items())),
        "selected_bucket_counts": dict(sorted(selected_bucket_counts.items())),
        "selected_cases": selected_cases,
        "runner_hint": {
            "module": "experiments.paper_v1.benchmarks.injecagent_stage_runner",
            "argument": "--selection",
            "recommended_prompt_style": "official_react_simple",
            "recommended_defenses": ["no_defense", "m3_full"],
            "result_eligible_for_formal_tables": False,
        },
    }


def write_selection(selection: Mapping[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_SELECTION_OUTPUT)
    parser.add_argument("--target-size", type=int, default=30)
    parser.add_argument("--seed", default=DEFAULT_SELECTION_SEED)
    parser.add_argument("--suite", action="append", choices=["data_security", "direct_harm"])
    args = parser.parse_args()
    rows = build_stage_rows(args.checkout)
    selection = build_injecagent_stage_selection(
        rows,
        target_size=args.target_size,
        seed=args.seed,
        suites=set(args.suite) if args.suite else None,
    )
    path = write_selection(selection, args.output)
    print(
        json.dumps(
            {
                "output": str(path),
                "sha256": sha256_file(path),
                "selected_count": selection["selected_count"],
                "selected_bucket_counts": selection["selected_bucket_counts"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
