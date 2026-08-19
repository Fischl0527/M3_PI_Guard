"""Freeze the 80-task query-budgeted adaptive attack panel.

This builder selects a deterministic, stratified M3-v2 attack panel for the
paper-v1 black-box adaptive MCTS protocol.  It does not run attacks, does not
start model services and does not create formal results.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from experiments.paper_v1.adaptive_attack import (
    ADAPTIVE_ATTACK_VERSION,
    DEFAULT_QUERY_BUDGETS,
    MUTATIONS,
)

from .common import canonical_json, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASETS = (
    ROOT / "m3_attacks" / "cases" / "paper_v1" / "m3_v2_development.jsonl",
    ROOT / "m3_attacks" / "cases" / "paper_v1" / "m3_v2_validation.jsonl",
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
FREEZE_STEM = "adaptive_mcts_budget_freeze_v1"
FREEZE_VERSION = "m3-paper-v1-adaptive-mcts-budget-freeze-1.0"
DEFAULT_TARGET_CASES = 80
DEFAULT_SELECTION_SEED = 20260721


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            row = dict(value)
            row["_source_path"] = str(path)
            row["_source_line"] = line_number
            rows.append(row)
    return rows


def _rank(seed: int, *parts: object) -> str:
    import hashlib

    return hashlib.sha256(
        canonical_json({"seed": seed, "parts": [str(part) for part in parts]}).encode("utf-8")
    ).hexdigest()


def _case_row(row: Mapping[str, Any]) -> dict[str, Any]:
    dimensions = row.get("attack_dimensions", {})
    if not isinstance(dimensions, Mapping):
        dimensions = {}
    return {
        "case_id": str(row["case_id"]),
        "template_id": str(row.get("template_id", "")),
        "split": str(row.get("split", "")),
        "dataset_version": str(row.get("dataset_version", "")),
        "attack_family": str(row.get("attack_family", "")),
        "language": str(row.get("language", "")),
        "authorization_profile": str(row.get("authorization_profile", "")),
        "scenario_type": str(row.get("scenario_type", "")),
        "mutation_id": str(row.get("mutation_id", "")),
        "attack_budget_group": int(dimensions.get("attack_budget_group") or 0),
        "carrier": str(dimensions.get("carrier", "")),
        "source_path": str(row.get("_source_path", "")),
        "source_line": int(row.get("_source_line", 0) or 0),
        "trusted_request_sha256": _rank(0, row.get("trusted_user_request", "")),
        "untrusted_content_sha256": _rank(0, row.get("untrusted_content", "")),
    }


def select_adaptive_panel(
    rows: Iterable[Mapping[str, Any]],
    *,
    target_cases: int = DEFAULT_TARGET_CASES,
    selection_seed: int = DEFAULT_SELECTION_SEED,
) -> list[dict[str, Any]]:
    attacks = [
        row
        for row in rows
        if row.get("sample_type") == "attack" and row.get("split") != "sealed_holdout"
    ]
    if target_cases <= 0:
        raise ValueError("target_cases must be positive")
    families = sorted({str(row.get("attack_family", "")) for row in attacks if row.get("attack_family")})
    if not families:
        raise ValueError("no attack families available for adaptive panel")
    languages = sorted({str(row.get("language", "")) for row in attacks if row.get("language")})
    budget_groups = sorted(
        {
            int(row.get("attack_dimensions", {}).get("attack_budget_group") or 0)
            for row in attacks
        }
    )

    def quota(values: list[Any]) -> dict[Any, int]:
        base = target_cases // len(values)
        remainder = target_cases % len(values)
        return {value: base + (1 if index < remainder else 0) for index, value in enumerate(values)}

    family_targets = quota(families)
    language_targets = quota(languages)
    budget_targets = quota(budget_groups)
    selected: list[dict[str, Any]] = []
    used_cases: set[str] = set()
    used_templates: set[str] = set()
    family_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    budget_counts: Counter[int] = Counter()
    remaining = list(attacks)

    while len(selected) < target_cases:
        candidates = []
        for row in remaining:
            case_id = str(row.get("case_id", ""))
            template_id = str(row.get("template_id", ""))
            family = str(row.get("attack_family", ""))
            language = str(row.get("language", ""))
            budget = int(row.get("attack_dimensions", {}).get("attack_budget_group") or 0)
            if case_id in used_cases or template_id in used_templates:
                continue
            if family_counts[family] >= family_targets.get(family, 0):
                continue
            candidates.append((row, family, language, budget))
        if not candidates:
            break
        row, family, language, budget = min(
            candidates,
            key=lambda item: (
                family_counts[item[1]] / family_targets[item[1]],
                language_counts[item[2]] / language_targets[item[2]],
                budget_counts[item[3]] / budget_targets[item[3]],
                _rank(selection_seed, item[0].get("case_id", "")),
            ),
        )
        case_id = str(row.get("case_id", ""))
        template_id = str(row.get("template_id", ""))
        selected.append(_case_row(row))
        used_cases.add(case_id)
        used_templates.add(template_id)
        family_counts[family] += 1
        language_counts[language] += 1
        budget_counts[budget] += 1

    if len(selected) < target_cases:
        ordered_remaining = sorted(
            attacks,
            key=lambda row: _rank(
                selection_seed,
                "fill",
                row.get("attack_family", ""),
                row.get("language", ""),
                row.get("case_id", ""),
            ),
        )
        for row in ordered_remaining:
            if len(selected) >= target_cases:
                break
            case_id = str(row.get("case_id", ""))
            template_id = str(row.get("template_id", ""))
            if case_id in used_cases or template_id in used_templates:
                continue
            selected.append(_case_row(row))
            used_cases.add(case_id)
            used_templates.add(template_id)

    if len(selected) != target_cases:
        raise ValueError(f"adaptive panel selection failed: {len(selected)} != {target_cases}")
    return sorted(selected, key=lambda row: row["case_id"])


def _counts(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "")) for row in rows).items()))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, freeze: Mapping[str, Any]) -> None:
    lines = [
        "# Adaptive MCTS budget freeze v1",
        "",
        f"- Status: `{freeze['status']}`",
        f"- Selected attack tasks: {freeze['case_count']}",
        f"- Query budgets: {', '.join(str(item) for item in freeze['query_budgets'])}",
        f"- Result eligible: `{freeze['result_eligible_for_formal_tables']}`",
        "",
        "## Distribution",
        "",
        "| Field | Counts |",
        "|---|---|",
    ]
    for field, counts in freeze["distribution"].items():
        text = ", ".join(f"{key}: {value}" for key, value in counts.items())
        lines.append(f"| `{field}` | {text} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            str(freeze["boundary"]),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_freeze(
    *,
    dataset_paths: Iterable[Path] = DEFAULT_DATASETS,
    output_dir: Path = DEFAULT_OUTPUT,
    target_cases: int = DEFAULT_TARGET_CASES,
    selection_seed: int = DEFAULT_SELECTION_SEED,
) -> dict[str, Any]:
    paths = tuple(Path(path) for path in dataset_paths)
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(_read_jsonl(path))
    selected = select_adaptive_panel(
        rows,
        target_cases=target_cases,
        selection_seed=selection_seed,
    )
    freeze = {
        "schema_version": "paper-adaptive-mcts-budget-freeze-1.0",
        "freeze_version": FREEZE_VERSION,
        "status": "completed_frozen_protocol",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result_eligible_for_formal_tables": False,
        "adaptive_attack_version": ADAPTIVE_ATTACK_VERSION,
        "selection_seed": selection_seed,
        "case_count": len(selected),
        "query_budgets": list(DEFAULT_QUERY_BUDGETS),
        "max_queries_per_task": max(DEFAULT_QUERY_BUDGETS),
        "mutations": list(MUTATIONS),
        "attacker_observation": [
            "public ALLOW/ASK/DENY decision",
            "whether an unsafe effect occurred",
            "whether the trusted task completed",
        ],
        "attacker_hidden_state": [
            "internal policy rules",
            "detector scores",
            "offline gold labels",
            "expected unsafe actions",
        ],
        "dataset_sources": [
            {"path": str(path), "sha256": sha256_file(path), "row_count": len(_read_jsonl(path))}
            for path in paths
        ],
        "holdout_policy": "sealed_holdout_excluded_from_adaptive_freeze_v1",
        "case_rows": selected,
        "case_rows_sha256": rows_sha256(selected),
        "distribution": {
            "split": _counts(selected, "split"),
            "attack_family": _counts(selected, "attack_family"),
            "language": _counts(selected, "language"),
            "authorization_profile": _counts(selected, "authorization_profile"),
            "attack_budget_group": _counts(selected, "attack_budget_group"),
        },
        "boundary": (
            "This artifact freezes an 80-task adaptive attack panel only. It does "
            "not run the MCTS search, does not start models or services, and is "
            "not formal adaptive robustness evidence until a separate run manifest "
            "reports completed_formal with complete query logs and figures."
        ),
    }
    json_path = output_dir / f"{FREEZE_STEM}.json"
    md_path = output_dir / f"{FREEZE_STEM}.md"
    _write_json(json_path, freeze)
    _write_markdown(md_path, freeze)
    freeze["json_path"] = str(json_path)
    freeze["markdown_path"] = str(md_path)
    return freeze


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-cases", type=int, default=DEFAULT_TARGET_CASES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    freeze = build_freeze(output_dir=args.output_dir, target_cases=args.target_cases)
    print(json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
