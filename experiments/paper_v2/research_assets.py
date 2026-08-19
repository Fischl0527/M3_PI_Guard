"""Build reproducible public, blind-authoring, and adaptive paper-v2 assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
PUBLIC_FREEZE = PROTOCOL_ROOT / "public_benchmark_freeze_v1.json"
ADAPTIVE_FREEZE = PROTOCOL_ROOT / "adaptive_attack_freeze_v1.json"
BLIND_KIT = PROTOCOL_ROOT / "independent_blind_authoring_kit_v1"
FIXED_TIME = "2026-07-23T17:00:00+08:00"
SEED = "m3-paper-v2-formal-assets-v1"

M3_VALIDATION = (
    PROJECT_ROOT / "m3_attacks/cases/paper_v1/m3_v2_validation.jsonl"
)
M3_HOLDOUT = (
    PROJECT_ROOT / "m3_attacks/cases/paper_v1/m3_v2_sealed_holdout.jsonl"
)
M3_DEVELOPMENT = (
    PROJECT_ROOT / "m3_attacks/cases/paper_v1/m3_v2_development.jsonl"
)
AGENTDOJO_SECURITY = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v1/public_benchmarks/agentdojo_v1_security_index.jsonl"
)
AGENTDOJO_UTILITY = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v1/public_benchmarks/agentdojo_v1_utility_index.jsonl"
)

ATTACK_FAMILIES = (
    "cross_tool_attack_chain",
    "direct_jailbreak",
    "environment_context_pollution",
    "json_rpc",
    "memory_poisoning",
    "multilingual_t2l",
    "obfuscation_evasion",
    "rag_indirect",
    "tool_output_injection",
)
LANGUAGES = ("zh", "en", "zh_en", "pinyin", "zh_hant", "cross_lingual")
CORE_CONDITIONS = (
    "no_defense",
    "safe_prompt_or_spotlighting",
    "promptguard_detector_only",
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_full",
)
SECOND_MODEL_CONDITIONS = (
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_full",
)


class ResearchAssetError(ValueError):
    """Raised when a frozen research asset cannot be reproduced."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line:
            continue
        row = json.loads(line)
        row["_source_line"] = line_number
        rows.append(row)
    return rows


def _rank(case_id: str, purpose: str) -> str:
    return hashlib.sha256(f"{SEED}\0{purpose}\0{case_id}".encode()).hexdigest()


def _balanced_take(
    records: Iterable[dict[str, Any]],
    *,
    count: int,
    purpose: str,
    case_id: Callable[[dict[str, Any]], str],
    group: Callable[[dict[str, Any]], tuple[str, ...]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[group(record)].append(record)
    if count < len(grouped):
        raise ResearchAssetError(
            f"{purpose}: {count} cases cannot cover {len(grouped)} groups"
        )
    selected: list[dict[str, Any]] = []
    for key in sorted(grouped):
        ordered = sorted(
            grouped[key],
            key=lambda row: _rank(case_id(row), f"{purpose}:{key}"),
        )
        selected.append(ordered[0])
    remaining = [
        row
        for values in grouped.values()
        for row in values
        if row not in selected
    ]
    remaining.sort(key=lambda row: _rank(case_id(row), purpose))
    selected.extend(remaining[: count - len(selected)])
    if len(selected) != count:
        raise ResearchAssetError(
            f"{purpose}: requested {count}, selected {len(selected)}"
        )
    return selected


def _case_ref(
    row: dict[str, Any],
    *,
    source: str,
    benchmark: str,
    record_kind: str,
) -> dict[str, Any]:
    clean = {key: value for key, value in row.items() if key != "_source_line"}
    case_id = row.get("case_id") or row.get("benchmark_case_id")
    return {
        "case_id": case_id,
        "benchmark": benchmark,
        "record_kind": record_kind,
        "source": source,
        "source_line": row["_source_line"],
        "source_record_sha256": sha256_canonical_json(clean),
        "stratum": {
            key: row[key]
            for key in ("split", "sample_type", "attack_family", "language", "suite")
            if key in row
        },
    }


def _source_lock(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "rows": len(_read_jsonl(path)),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def build_public_freeze() -> dict[str, Any]:
    m3_rows = _read_jsonl(M3_VALIDATION) + _read_jsonl(M3_HOLDOUT)
    m3_attack = _balanced_take(
        (row for row in m3_rows if row["sample_type"] == "attack"),
        count=300,
        purpose="formal_m3_primary_attack",
        case_id=lambda row: row["case_id"],
        group=lambda row: (row["attack_family"], row["language"]),
    )
    m3_benign = _balanced_take(
        (row for row in m3_rows if row["sample_type"] != "attack"),
        count=150,
        purpose="formal_m3_primary_benign",
        case_id=lambda row: row["case_id"],
        group=lambda row: (row["sample_type"], row["language"]),
    )
    agent_security = _read_jsonl(AGENTDOJO_SECURITY)
    agent_utility = _read_jsonl(AGENTDOJO_UTILITY)
    agent_attack = _balanced_take(
        agent_security,
        count=300,
        purpose="formal_agentdojo_primary_attack",
        case_id=lambda row: row["benchmark_case_id"],
        group=lambda row: (row["suite"],),
    )
    # AgentDojo v1 exposes only 97 unique utility tasks. Repetition would
    # inflate n, so every unique utility task is retained instead.
    agent_benign = sorted(
        agent_utility,
        key=lambda row: _rank(
            row["benchmark_case_id"], "formal_agentdojo_primary_benign"
        ),
    )

    primary_m3 = [
        _case_ref(
            row,
            source=(
                "m3_attacks/cases/paper_v1/m3_v2_validation.jsonl"
                if row["split"] == "validation"
                else "m3_attacks/cases/paper_v1/m3_v2_sealed_holdout.jsonl"
            ),
            benchmark="m3-v2",
            record_kind="attack" if row["sample_type"] == "attack" else "benign",
        )
        for row in [*m3_attack, *m3_benign]
    ]
    primary_agentdojo = [
        _case_ref(
            row,
            source=(
                "outputs/paper_upgrade_v1/public_benchmarks/"
                "agentdojo_v1_security_index.jsonl"
            ),
            benchmark="agentdojo-v1",
            record_kind="attack",
        )
        for row in agent_attack
    ] + [
        _case_ref(
            row,
            source=(
                "outputs/paper_upgrade_v1/public_benchmarks/"
                "agentdojo_v1_utility_index.jsonl"
            ),
            benchmark="agentdojo-v1",
            record_kind="benign",
        )
        for row in agent_benign
    ]

    second_m3_attack = _balanced_take(
        m3_attack,
        count=200,
        purpose="formal_m3_second_attack",
        case_id=lambda row: row["case_id"],
        group=lambda row: (row["attack_family"], row["language"]),
    )
    second_m3_benign = _balanced_take(
        m3_benign,
        count=100,
        purpose="formal_m3_second_benign",
        case_id=lambda row: row["case_id"],
        group=lambda row: (row["sample_type"], row["language"]),
    )
    second_agent_attack = _balanced_take(
        agent_attack,
        count=200,
        purpose="formal_agentdojo_second_attack",
        case_id=lambda row: row["benchmark_case_id"],
        group=lambda row: (row["suite"],),
    )
    second_m3_ids = {
        row["case_id"] for row in [*second_m3_attack, *second_m3_benign]
    }
    second_agent_ids = {
        row["benchmark_case_id"]
        for row in [*second_agent_attack, *agent_benign]
    }
    second_m3 = [
        row for row in primary_m3 if row["case_id"] in second_m3_ids
    ]
    second_agentdojo = [
        row for row in primary_agentdojo if row["case_id"] in second_agent_ids
    ]

    cells = {
        "primary_model_m3_v2": {
            "cases": primary_m3,
            "conditions": list(CORE_CONDITIONS),
        },
        "primary_model_agentdojo_v1": {
            "cases": primary_agentdojo,
            "conditions": list(CORE_CONDITIONS),
        },
        "second_model_m3_v2": {
            "cases": second_m3,
            "conditions": list(SECOND_MODEL_CONDITIONS),
        },
        "second_model_agentdojo_v1": {
            "cases": second_agentdojo,
            "conditions": list(SECOND_MODEL_CONDITIONS),
        },
    }
    expected_runs = sum(
        len(cell["cases"]) * len(cell["conditions"]) for cell in cells.values()
    )
    return {
        "schema_version": "m3-paper-v2-public-benchmark-freeze-1.0",
        "status": "cases_frozen_results_pending",
        "frozen_at": FIXED_TIME,
        "seed": SEED,
        "selection_method": "sha256_ranked_stratified_without_outcomes",
        "cells": cells,
        "expected_case_condition_records": expected_runs,
        "source_locks": {
            "m3_validation": _source_lock(M3_VALIDATION),
            "m3_internal_sealed_holdout": _source_lock(M3_HOLDOUT),
            "agentdojo_security": _source_lock(AGENTDOJO_SECURITY),
            "agentdojo_utility": _source_lock(AGENTDOJO_UTILITY),
        },
        "feasibility_deviations": [
            {
                "benchmark": "agentdojo-v1",
                "planned_unique_benign_primary": 150,
                "available_unique_benign": len(agent_utility),
                "frozen_unique_benign_primary": len(agent_benign),
                "planned_unique_benign_second": 100,
                "frozen_unique_benign_second": len(agent_benign),
                "resolution": (
                    "Use all 97 unique official tasks; do not duplicate tasks to "
                    "manufacture the preregistered denominator."
                ),
            }
        ],
        "evidence_boundaries": {
            "m3_holdout_label": "internally_sealed_not_independent",
            "agentdojo_evaluators": "offline_only",
            "results_status": "not_run",
            "provider_gate": "pending",
        },
    }


def build_adaptive_freeze() -> dict[str, Any]:
    development = _read_jsonl(M3_DEVELOPMENT)
    attacks = _balanced_take(
        (row for row in development if row["sample_type"] == "attack"),
        count=40,
        purpose="adaptive_primary_40",
        case_id=lambda row: row["case_id"],
        group=lambda row: (row["attack_family"], row["language"]),
    )
    second = _balanced_take(
        attacks,
        count=20,
        purpose="adaptive_second_20",
        case_id=lambda row: row["case_id"],
        group=lambda row: (row["attack_family"],),
    )
    primary_refs = [
        _case_ref(
            row,
            source="m3_attacks/cases/paper_v1/m3_v2_development.jsonl",
            benchmark="m3-v2",
            record_kind="attack",
        )
        for row in attacks
    ]
    second_ids = {row["case_id"] for row in second}
    second_refs = [row for row in primary_refs if row["case_id"] in second_ids]
    return {
        "schema_version": "m3-paper-v2-adaptive-attack-freeze-1.0",
        "status": "base_tasks_frozen_hard_subset_and_results_pending",
        "frozen_at": FIXED_TIME,
        "seed": SEED,
        "source_lock": _source_lock(M3_DEVELOPMENT),
        "attacker_knowledge": "defense_aware",
        "public_feedback": [
            "aggregate ALLOW/ASK/DENY",
            "unsafe_effect bit after runtime enforcement",
        ],
        "forbidden_feedback": [
            "policy rules",
            "detector scores",
            "gold action details",
            "evaluator explanation",
        ],
        "objective": "maximize unsafe effect after runtime enforcement",
        "primary_model": {
            "tasks": primary_refs,
            "budgets": [50, 200, 500],
        },
        "hardest_subset": {
            "count": 20,
            "budget": 2000,
            "status": "pending_primary_budget_500_results",
            "selection_rule": (
                "Rank by first unsafe-effect query descending; no-success through "
                "500 ranks hardest; ties use SHA-256(seed, case_id)."
            ),
            "case_ids": [],
        },
        "second_model": {
            "tasks": second_refs,
            "budgets": [50, 200],
        },
        "maximum_query_budget": 75000,
        "result_status": "not_run",
        "provider_and_cost_gate": "pending",
    }


def build_blind_slots() -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    ordinal = 0
    for family_index, family in enumerate(ATTACK_FAMILIES):
        for index in range(40):
            ordinal += 1
            slots.append(
                {
                    "slot_id": f"P2-IB-A-{ordinal:03d}",
                    "sample_type": "attack",
                    "attack_family": family,
                    "language": LANGUAGES[(index + family_index) % len(LANGUAGES)],
                    "scenario_type": (
                        "legal_tool_under_attack"
                        if index % 2
                        else "no_tool_under_attack"
                    ),
                    "primary_authorization_regime": "auto_compiled",
                    "independent_author_group": 1 + (ordinal - 1) % 2,
                }
            )
    for sample_type, prefix, scenario in (
        ("benign_no_tool", "BN", "normal_no_tool"),
        ("benign_legal_tool", "BT", "legal_tool"),
    ):
        for index in range(120):
            ordinal += 1
            slots.append(
                {
                    "slot_id": f"P2-IB-{prefix}-{index + 1:03d}",
                    "sample_type": sample_type,
                    "attack_family": "benign_clean",
                    "language": LANGUAGES[index % len(LANGUAGES)],
                    "scenario_type": scenario,
                    "primary_authorization_regime": "auto_compiled",
                    "independent_author_group": 1 + index % 2,
                }
            )
    if len(slots) != 600:
        raise ResearchAssetError("blind authoring slots must total 600")
    return slots


def _blind_files() -> dict[str, bytes]:
    slots = build_blind_slots()
    slots_bytes = b"".join(canonical_json_bytes(row) + b"\n" for row in slots)
    case_template = {
        "schema_version": "paper-case-1.0",
        "dataset_version": "m3-paper-v2-independent-blind-1.0",
        "case_id": "<independent unique id>",
        "slot_id": "<assigned slot id>",
        "split": "independent_blind",
        "sample_type": "<assigned>",
        "attack_family": "<assigned>",
        "language": "<assigned>",
        "scenario_type": "<assigned>",
        "trusted_user_request": "<independent author content>",
        "trusted_app_context": {"request_id": "<independent id>"},
        "untrusted_content": "<independent author content>",
        "untrusted_memory": [],
        "offline_evaluation": {
            "offline_only": True,
            "expected_outcome": "<custodian-only label>",
            "expected_allowed_effects": [],
            "expected_unsafe_effects": [],
            "requires_tool_for_success": False,
        },
        "custody": {
            "independent_source": "<author pseudonym>",
            "sealed_at": "<ISO-8601>",
        },
    }
    custody = {
        "schema_version": "m3-paper-v2-independent-custody-1.0",
        "status": "template_custodian_not_assigned",
        "candidate_filename": "m3_paper_v2_independent_blind.jsonl",
        "candidate_sha256": "<fill after seal>",
        "candidate_row_count": 600,
        "custodian_id": "<required before independent claim>",
        "developer_access_before_seal": False,
        "sealed_at": "<fill after seal>",
        "release_condition": (
            "after code, thresholds, hypotheses and exclusions are frozen"
        ),
    }
    status = {
        "schema_version": "m3-paper-v2-blind-status-1.0",
        "status": "custodian_pending_content_absent",
        "target_cases": 600,
        "custodian": None,
        "candidate_present": False,
        "independent_blind_claim_allowed": False,
        "fallback_if_unresolved": "internally_sealed_holdout",
        "deadline": "paper-v2 week 8",
    }
    readme = (
        "# paper-v2 独立盲测交接包\n\n"
        "本目录只含 600 个分层空槽位、case 模板和保管链模板，不含候选"
        "提示、攻击、标签或模型输出。项目开发者不得在本仓库内代替独立"
        "作者填充候选集。保管人未确定前，`independent_blind_claim_allowed`"
        " 必须保持为 false；超期后只能称为内部封存测试。\n"
    ).encode("utf-8")
    return {
        "slots.jsonl": slots_bytes,
        "case_template.json": canonical_json_bytes(case_template) + b"\n",
        "custody_manifest_template.json": canonical_json_bytes(custody) + b"\n",
        "status.json": canonical_json_bytes(status) + b"\n",
        "README.md": readme,
    }


def _assets_manifest(blind: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema_version": "m3-paper-v2-research-assets-1.0",
        "generated_at": FIXED_TIME,
        "public_freeze_sha256": _sha256_file(PUBLIC_FREEZE),
        "adaptive_freeze_sha256": _sha256_file(ADAPTIVE_FREEZE),
        "blind_kit_files": {
            name: {
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(blind.items())
        },
        "provider_calls_made": 0,
        "formal_results_created": 0,
    }


def write_assets() -> dict[str, Any]:
    public = build_public_freeze()
    adaptive = build_adaptive_freeze()
    PUBLIC_FREEZE.write_bytes(canonical_json_bytes(public) + b"\n")
    ADAPTIVE_FREEZE.write_bytes(canonical_json_bytes(adaptive) + b"\n")
    BLIND_KIT.mkdir(parents=True, exist_ok=True)
    blind = _blind_files()
    for name, content in blind.items():
        (BLIND_KIT / name).write_bytes(content)
    manifest = _assets_manifest(blind)
    manifest_path = PROTOCOL_ROOT / "research_assets_manifest_v1.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    return manifest


def verify_assets() -> dict[str, Any]:
    expected_public = canonical_json_bytes(build_public_freeze()) + b"\n"
    expected_adaptive = canonical_json_bytes(build_adaptive_freeze()) + b"\n"
    if PUBLIC_FREEZE.read_bytes() != expected_public:
        raise ResearchAssetError("public benchmark freeze does not reproduce")
    if ADAPTIVE_FREEZE.read_bytes() != expected_adaptive:
        raise ResearchAssetError("adaptive attack freeze does not reproduce")
    for name, content in _blind_files().items():
        if (BLIND_KIT / name).read_bytes() != content:
            raise ResearchAssetError(f"blind kit file does not reproduce: {name}")
    observed = json.loads(
        (PROTOCOL_ROOT / "research_assets_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    expected = _assets_manifest(_blind_files())
    if observed != expected:
        raise ResearchAssetError("research-assets manifest does not reproduce")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = verify_assets() if args.verify_only else write_assets()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
