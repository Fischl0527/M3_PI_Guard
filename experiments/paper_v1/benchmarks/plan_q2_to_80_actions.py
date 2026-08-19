"""Build a fail-closed action audit for moving Q2 readiness toward 80%.

This module is deliberately non-executing.  It reads the current readiness,
frontier, blind, baseline and execution-plan artifacts, then writes a compact
machine-readable checklist of the evidence bundles that must be completed before
the readiness score can honestly cross 80.  It never starts models, calls APIs,
edits registries, retries failures or promotes smoke/diagnostic evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import portable_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_ROOT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_OUTPUT_DIR = PROTOCOL_ROOT / "execution"
AUDIT_STEM = "q2_to_80_action_audit_v1"
AUDIT_VERSION = "m3-paper-v1-q2-to-80-action-audit-1.0"

DEFAULT_Q2_AUDIT = PROTOCOL_ROOT / "q2_readiness_audit_v1.json"
DEFAULT_EXECUTION_PLAN = PROTOCOL_ROOT / "execution" / "q2_formal_execution_plan_v1.json"
DEFAULT_STRONG_BASELINE_AUDIT = (
    PROTOCOL_ROOT / "strong_baseline_formal_readiness_audit_v1.json"
)
DEFAULT_FRONTIER_AUDIT = PROTOCOL_ROOT / "frontier_api_model_slot_admission_audit_v1.json"
DEFAULT_BLIND_AUDIT = PROTOCOL_ROOT / "m3_v2_independent_blind_admission_audit_v2.json"
DEFAULT_ADAPTIVE_MONITOR = (
    PROTOCOL_ROOT
    / "monitors"
    / "adaptive_mcts_budget_v1"
    / "adaptive_mcts_budget_formal_monitor_v1.json"
)

CHECKOUT_SPECIFIC_ABSOLUTE_PATH = re.compile(
    r"(?i)\b[A-Z]:[\\/][^\r\n]{0,200}M3_PI_Guard_test(?:[\\/]|(?=[`'\"\s;,.]))"
)


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _source(path: Path) -> dict[str, Any]:
    return {
        "path": _path(path),
        "exists": path.is_file(),
        "sha256": sha256_file(path) if path.is_file() else "",
    }


def _criterion(q2_audit: Mapping[str, Any], criterion_id: str) -> Mapping[str, Any]:
    for row in q2_audit.get("criteria", []):
        if isinstance(row, Mapping) and row.get("id") == criterion_id:
            return row
    return {}


def _formal_ready_baselines(strong_baseline_audit: Mapping[str, Any]) -> list[str]:
    rows = strong_baseline_audit.get("formal_ready_strong_baselines", [])
    if isinstance(rows, list):
        return [str(row) for row in rows]
    text = str(strong_baseline_audit.get("formal_ready_strong_baselines", ""))
    return [part.strip() for part in text.split(",") if part.strip()]


def _path_exception_reason(relative_path: str) -> str:
    name = Path(relative_path).name
    if name.startswith("m3_v2_independent_blind_admission_audit_v1"):
        return "preregistration_snapshot_preserved_do_not_rewrite"
    if name.startswith("taskshield_paper_import_preflight_v1"):
        return "taskshield_v1_import_preflight_bound_to_hash_frozen_protocol"
    if relative_path.startswith("protocols/paper_upgrade_v1/camel_source_backed_"):
        return "camel_source_backed_preflight_snapshot_bound_to_frozen_generator_evidence"
    return "requires_manual_review_before_any_rewrite"


def _scan_checkout_path_debt(root: Path = ROOT) -> dict[str, Any]:
    try:
        import scripts.audit_project_conventions as layout_audit

        frozen = set(layout_audit._frozen_file_paths()) | set(  # noqa: SLF001
            layout_audit._hash_bound_file_paths()  # noqa: SLF001
        )
    except Exception:  # pragma: no cover - defensive fallback for relocated audits.
        frozen = set()

    rows: list[dict[str, Any]] = []
    protocol_root = root / "protocols" / "paper_upgrade_v1"
    if not protocol_root.is_dir():
        return {
            "files_with_hits": 0,
            "by_kind": {},
            "remaining_non_frozen_protocol": [],
        }
    for path in protocol_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {
            ".json",
            ".md",
            ".jsonl",
            ".yaml",
            ".yml",
        }:
            continue
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = len(CHECKOUT_SPECIFIC_ABSOLUTE_PATH.findall(text))
        if not hits:
            continue
        kind = (
            "frozen_or_hash_bound"
            if relative in frozen or "freeze" in path.name.lower()
            else "non_frozen_protocol"
        )
        rows.append(
            {
                "kind": kind,
                "path": relative,
                "hits": hits,
                "exception_reason": _path_exception_reason(relative)
                if kind == "non_frozen_protocol"
                else "frozen_or_hash_bound_preserved",
            }
        )
    by_kind = Counter(str(row["kind"]) for row in rows)
    return {
        "files_with_hits": len(rows),
        "by_kind": dict(sorted(by_kind.items())),
        "remaining_non_frozen_protocol": [
            row for row in rows if row["kind"] == "non_frozen_protocol"
        ],
        "boundary": (
            "This is a path-debt inventory only.  Remaining freeze-bound or "
            "evidence-bound artifacts must not be rewritten in place; create a "
            "new revision if their path representation must change."
        ),
    }


def _action(
    *,
    gate: str,
    cap: float,
    title: str,
    current_state: Mapping[str, Any],
    proof_required: Iterable[str],
    next_action: Mapping[str, Any],
    blocking_kind: str,
) -> dict[str, Any]:
    return {
        "gate": gate,
        "cap": cap,
        "required_to_reach_80": cap < 80.0,
        "title": title,
        "current_state": dict(current_state),
        "proof_required": list(proof_required),
        "next_action": dict(next_action),
        "can_execute_now": bool(next_action.get("can_execute_now", False)),
        "blocking_kind": blocking_kind,
    }


def _cap_value(q2_audit: Mapping[str, Any], name: str, default: float) -> float:
    for cap in q2_audit.get("caps", []):
        if isinstance(cap, Mapping) and cap.get("name") == name:
            try:
                return float(cap.get("cap", default))
            except (TypeError, ValueError):
                return default
    return default


def build_q2_to_80_action_audit(
    *,
    q2_audit_path: Path = DEFAULT_Q2_AUDIT,
    execution_plan_path: Path = DEFAULT_EXECUTION_PLAN,
    strong_baseline_audit_path: Path = DEFAULT_STRONG_BASELINE_AUDIT,
    frontier_audit_path: Path = DEFAULT_FRONTIER_AUDIT,
    blind_audit_path: Path = DEFAULT_BLIND_AUDIT,
    adaptive_monitor_path: Path = DEFAULT_ADAPTIVE_MONITOR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    write_files: bool = True,
) -> dict[str, Any]:
    q2_audit = _read_json(q2_audit_path)
    execution_plan = _read_json(execution_plan_path)
    strong_baseline_audit = _read_json(strong_baseline_audit_path)
    frontier_audit = _read_json(frontier_audit_path)
    blind_audit = _read_json(blind_audit_path)
    adaptive_monitor = _read_json(adaptive_monitor_path)

    resource_gate = str(execution_plan.get("resource_gate", "unknown"))
    next_safe_action = execution_plan.get("next_safe_action", {})
    if not isinstance(next_safe_action, Mapping):
        next_safe_action = {}
    formal_ready = _formal_ready_baselines(strong_baseline_audit)
    public_criterion = _criterion(q2_audit, "public_benchmark_results")
    strong_criterion = _criterion(q2_audit, "source_backed_strong_baselines")
    blind_criterion = _criterion(q2_audit, "independent_blind_evidence")
    frontier_criterion = _criterion(q2_audit, "model_coverage")
    adaptive_criterion = _criterion(q2_audit, "adaptive_budget_attacks")

    action_rows = [
        _action(
            gate="frontier_api_model_gate",
            cap=_cap_value(q2_audit, "frontier_api_model_gate", 60.0),
            title="Register two explicit frontier API vendor slots",
            current_state={
                "configured_vendor_count": frontier_audit.get("configured_vendor_count", 0),
                "registered_vendor_count": frontier_audit.get("registered_vendor_count", 0),
                "status": frontier_audit.get("status", "missing"),
                "criterion_status": frontier_criterion.get("status", "missing"),
                "network_calls_performed": frontier_audit.get("network_calls_performed", False),
            },
            proof_required=[
                "two distinct vendors configured in ignored local config",
                "explicit network-smoke consent recorded",
                "one synthetic smoke per vendor completes with redacted logs",
                "frontier registry admission writes a hash-checked v3 candidate",
            ],
            next_action={
                "can_execute_now": False,
                "command": "python -m experiments.paper_v1.benchmarks.smoke_frontier_api_models",
                "reason": "requires user-controlled API credentials and explicit consent",
            },
            blocking_kind="user_local_config_and_external_api",
        ),
        _action(
            gate="adaptive_budget_gate",
            cap=_cap_value(q2_audit, "adaptive_budget_gate", 60.0),
            title="Run and admit the frozen 80-task adaptive MCTS budget panel",
            current_state={
                "monitor_health": adaptive_monitor.get("health_status", "missing_manifest"),
                "manifest_status": adaptive_monitor.get("manifest_status", ""),
                "criterion_status": adaptive_criterion.get("status", "missing"),
                "resource_gate": resource_gate,
            },
            proof_required=[
                "80/80 frozen tasks completed with 100/500/2000 budget rows",
                "query artifacts match manifest counts",
                "no unresolved failures",
                "formal adaptive analysis writes ASR-budget curves and admission manifest",
            ],
            next_action={
                "can_execute_now": resource_gate == "free",
                "command": (
                    "python -m experiments.paper_v1.benchmarks.run_adaptive_mcts_budget_formal "
                    "--output-dir outputs/paper_upgrade_v1/adaptive_mcts_budget_v1 --admit-formal"
                ),
                "reason": "wait for current Ollama/GPU workload to release before starting",
            },
            blocking_kind="resource_gate" if resource_gate != "free" else "ready_when_user_allows_run",
        ),
        _action(
            gate="independent_blind_gate",
            cap=_cap_value(q2_audit, "independent_blind_gate", 65.0),
            title="Admit and run an independently authored 600-case blind set",
            current_state={
                "candidate_exists": blind_audit.get("candidate_exists", False),
                "status": blind_audit.get("status", "missing"),
                "result_eligible": blind_audit.get(
                    "result_eligible_for_confirmatory_q2_tables", False
                ),
                "criterion_status": blind_criterion.get("status", "missing"),
            },
            proof_required=[
                "external/independent candidate JSONL exists with 600 cases",
                "custody sidecar matches candidate SHA-256",
                "admission audit proves no template/reference overlap",
                "formal blind run manifest is SHA-matched, complete and result-eligible",
            ],
            next_action={
                "can_execute_now": False,
                "command": (
                    "python -m experiments.paper_v1.benchmarks.audit_m3_v2_independent_blind"
                ),
                "reason": "requires independently authored candidate data not produced by this agent",
            },
            blocking_kind="independent_data_required",
        ),
        _action(
            gate="strong_baseline_gate",
            cap=_cap_value(q2_audit, "strong_baseline_gate", 70.0),
            title="Raise source-backed formal-ready strong baselines from 2 to at least 5",
            current_state={
                "formal_ready": formal_ready,
                "formal_ready_count": len(formal_ready),
                "minimum_required": 5,
                "criterion_status": strong_criterion.get("status", "missing"),
                "resource_gate": resource_gate,
            },
            proof_required=[
                "Task Shield v1.6 failed G3 and remains preserved as result-ineligible negative evidence",
                "Progent, CaMeL and IPIGuard complete qualification, full logs and admission",
                "formal-readiness audit counts at least five source-backed strong baselines",
            ],
            next_action={
                "can_execute_now": resource_gate == "free"
                and str(next_safe_action.get("status", "")).startswith("ready"),
                "command": str(next_safe_action.get("command", "")),
                "reason": str(next_safe_action.get("reason", "follow execution plan")),
            },
            blocking_kind="active_formal_workload"
            if resource_gate == "busy"
            else "formal_runs_pending",
        ),
        _action(
            gate="public_benchmark_gate",
            cap=_cap_value(q2_audit, "public_benchmark_gate", 75.0),
            title="Complete the frozen AgentDojo/InjecAgent public benchmark matrix",
            current_state={
                "criterion_status": public_criterion.get("status", "missing"),
                "resource_gate": resource_gate,
                "public_matrix": execution_plan.get("public_matrix", {}),
            },
            proof_required=[
                "all frozen public benchmark cells have complete manifests/logs",
                "public completeness audit has zero missing cells and admitted analyses",
                "failed, timeout and parse rows remain in original denominators",
            ],
            next_action={
                "can_execute_now": resource_gate == "free"
                and not execution_plan.get("active_workloads"),
                "command": str(
                    execution_plan.get("public_matrix", {})
                    .get("first_pending", {})
                    .get("command", "")
                )
                or "python -m experiments.paper_v1.benchmarks.plan_q2_formal_execution",
                "reason": "large formal matrix must wait for current formal workload and upstream baselines",
            },
            blocking_kind="resource_gate" if resource_gate != "free" else "matrix_runs_pending",
        ),
    ]

    caps_below_80 = [
        cap
        for cap in q2_audit.get("caps", [])
        if isinstance(cap, Mapping)
        and bool(cap.get("gate_missing"))
        and float(cap.get("cap", 100.0)) < 80.0
    ]
    blocking_actions = [row for row in action_rows if row["required_to_reach_80"]]
    audit = {
        "schema_version": "paper-q2-to-80-action-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "goal_80_met"
        if q2_audit.get("goal_80_met") is True
        else "blocked_by_active_hard_caps",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "q2_readiness": {
            "raw_score": q2_audit.get("raw_score", 0.0),
            "capped_score": q2_audit.get("capped_score", 0.0),
            "goal_80_met": q2_audit.get("goal_80_met", False),
            "goal_90_met": q2_audit.get("goal_90_met", False),
            "readiness_band": q2_audit.get("readiness_band", ""),
        },
        "caps_below_80": caps_below_80,
        "actions_required_before_80": blocking_actions,
        "next_safe_action": next_safe_action,
        "resource_gate": resource_gate,
        "path_portability_exceptions": _scan_checkout_path_debt(ROOT),
        "sources": {
            "q2_audit": _source(q2_audit_path),
            "execution_plan": _source(execution_plan_path),
            "strong_baseline_audit": _source(strong_baseline_audit_path),
            "frontier_audit": _source(frontier_audit_path),
            "blind_audit": _source(blind_audit_path),
            "adaptive_monitor": _source(adaptive_monitor_path),
        },
        "actions_sha256": rows_sha256(action_rows),
        "boundary": (
            "Read-only Q2-to-80 action audit. It cannot execute experiments, "
            "call external APIs, change registries, rewrite frozen evidence or "
            "promote smoke/diagnostic/running artifacts into formal results."
        ),
    }
    if write_files:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{AUDIT_STEM}.json"
        md_path = output_dir / f"{AUDIT_STEM}.md"
        json_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_markdown(md_path, audit)
        audit["json_path"] = _path(json_path)
        audit["markdown_path"] = _path(md_path)
    return audit


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    readiness = audit["q2_readiness"]
    lines = [
        "# Q2-to-80 action audit v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Status",
        "",
        f"- Status: `{audit['status']}`",
        f"- Raw score: `{readiness['raw_score']}`",
        f"- Capped score: `{readiness['capped_score']}`",
        f"- Goal 80 met: `{readiness['goal_80_met']}`",
        f"- Resource gate: `{audit['resource_gate']}`",
        "",
        "## Actions required before 80",
        "",
        "| Gate | Cap | Can execute now | Blocking kind | Next action |",
        "|---|---:|---|---|---|",
    ]
    for row in audit["actions_required_before_80"]:
        next_action = row.get("next_action", {})
        command = str(next_action.get("command", "")).replace("|", "\\|")
        lines.append(
            f"| `{row['gate']}` | {row['cap']} | `{row['can_execute_now']}` | "
            f"`{row['blocking_kind']}` | `{command}` |"
        )
    path_debt = audit["path_portability_exceptions"]
    lines.extend(
        [
            "",
            "## Path portability exceptions",
            "",
            f"- Files with hits: `{path_debt['files_with_hits']}`",
            f"- By kind: `{path_debt['by_kind']}`",
            f"- Remaining non-frozen protocol snapshots: "
            f"`{len(path_debt['remaining_non_frozen_protocol'])}`",
            "",
            "## Boundary",
            "",
            str(audit["boundary"]),
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--q2-audit", type=Path, default=DEFAULT_Q2_AUDIT)
    parser.add_argument("--execution-plan", type=Path, default=DEFAULT_EXECUTION_PLAN)
    parser.add_argument(
        "--strong-baseline-audit",
        type=Path,
        default=DEFAULT_STRONG_BASELINE_AUDIT,
    )
    parser.add_argument("--frontier-audit", type=Path, default=DEFAULT_FRONTIER_AUDIT)
    parser.add_argument("--blind-audit", type=Path, default=DEFAULT_BLIND_AUDIT)
    parser.add_argument("--adaptive-monitor", type=Path, default=DEFAULT_ADAPTIVE_MONITOR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_q2_to_80_action_audit(
        q2_audit_path=args.q2_audit,
        execution_plan_path=args.execution_plan,
        strong_baseline_audit_path=args.strong_baseline_audit,
        frontier_audit_path=args.frontier_audit,
        blind_audit_path=args.blind_audit,
        adaptive_monitor_path=args.adaptive_monitor,
        output_dir=args.output_dir,
        write_files=not args.no_write,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
