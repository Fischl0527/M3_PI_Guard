"""Analyze the frozen E11 post-hoc amendment without touching original E11.

The analyzer accepts only a completed 48-run Ollama formal matrix produced by
``e11_amendment_runner.py``. Stub output is regression evidence and is rejected
as a source of formal claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from m3_eval.figure_manifest import write_figure_manifest
from m3_eval.metrics import compare_runs, compute_metrics
from m3_eval.statistics import clustered_paired_bootstrap, holm_adjust, mcnemar_exact
from scripts.e11_amendment_runner import (
    AMENDMENT_TYPE,
    DENOMINATOR_POLICY,
    EXPECTED_CONDITIONS,
    EXECUTION_REVISION,
    FORMAL_MODEL,
    PATTERNS,
    PROTOCOL_ID,
    REPO_ROOT,
    SEED,
    VISUALIZATION_REVISION,
    canonical_action,
    load_protocol_data,
    sha256_file,
    validate_frozen_protocol,
)


METRICS = (
    "ASR",
    "UTR",
    "DSR",
    "BSR",
    "Precision",
    "Recall",
    "ParseSuccessRate",
    "UnresolvedRate",
)
CONDITION_LABELS = {"posthoc_off": "Guard off", "posthoc_full": "Full Guard"}
FIGURE_DPI = 180
BOTTOM_GUARD_ROWS = 12
PATTERN_LABELS = {
    "read_to_send": "read → send",
    "search_to_api": "search → API",
    "memory_to_file": "memory → file",
    "tool_output_to_next_action": "tool output →\nnext action",
}


def _atomic_write_json(path: Path, payload: Mapping[str, Any] | Sequence[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"expected object at {path}:{line_number}")
        rows.append(row)
    return rows


def _repo_file(relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"invalid repo-relative path: {relative!r}")
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {relative!r}") from exc
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)
    return path


def validate_formal_execution(run_root: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(run_root)
    root = root if root.is_absolute() else REPO_ROOT / root
    root = root.resolve()
    manifest_path = root / "formal" / "execution_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"formal execution manifest is missing: {manifest_path}")
    execution = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "protocol_id": PROTOCOL_ID,
        "amendment_type": AMENDMENT_TYPE,
        "visualization_revision": VISUALIZATION_REVISION,
        "execution_revision": EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": DENOMINATOR_POLICY,
        "status": "completed",
        "phase": "formal",
        "backend": "ollama",
        "model": FORMAL_MODEL,
        "evidence_tier": "formal_model_posthoc",
        "expected_logical_runs": 48,
        "actual_logical_runs": 48,
    }
    for key, expected in required.items():
        if execution.get(key) != expected:
            raise ValueError(
                f"formal execution {key} mismatch: expected {expected!r}, got {execution.get(key)!r}"
            )
    if execution.get("conditions") != list(EXPECTED_CONDITIONS):
        raise ValueError("formal execution condition order or identity has drifted")

    frozen = validate_frozen_protocol()
    expected_case_ids = [str(case["case_id"]) for case in frozen["cases"]]
    selected_case_ids = execution.get("selected_case_ids")
    if (
        not isinstance(selected_case_ids, list)
        or len(selected_case_ids) != 24
        or len(set(selected_case_ids)) != 24
        or selected_case_ids != expected_case_ids
    ):
        raise ValueError(
            "formal execution must record all 24 frozen case IDs explicitly and in protocol order"
        )
    if execution.get("amendment_freeze_sha256") != frozen["freeze"]["sha256"]:
        raise ValueError("formal execution uses a different amendment freeze")
    for path_key, hash_key in (
        ("matrix_manifest_path", "matrix_manifest_sha256"),
        ("materialized_cases_path", "materialized_cases_sha256"),
        ("v3_blind_freeze_path", "v3_blind_freeze_sha256"),
        ("e13_thresholds_path", "e13_thresholds_sha256"),
    ):
        source = _repo_file(execution.get(path_key))
        if sha256_file(source) != execution.get(hash_key):
            raise ValueError(f"formal execution source drift: {path_key}")

    matrix_path = _repo_file(execution["matrix_manifest_path"])
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    if matrix.get("status") != "completed":
        raise ValueError("matrix manifest is not completed")
    results = matrix.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise ValueError("matrix manifest must contain exactly two condition results")
    if {result.get("condition_id") for result in results} != set(EXPECTED_CONDITIONS):
        raise ValueError("matrix manifest conditions do not match the protocol")
    for result in results:
        if (
            result.get("status") != "completed"
            or int(result.get("case_count", -1)) != 24
            or int(result.get("selected_case_count", -1)) != 24
            or int(result.get("error_count", -1)) != 0
        ):
            raise ValueError(f"incomplete matrix condition: {result.get('condition_id')}")
    return execution, matrix


def load_formal_logs(
    matrix: Mapping[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_condition: dict[str, list[dict[str, Any]]] = {}
    file_index: list[dict[str, Any]] = []
    for result in matrix["results"]:
        condition = str(result["condition_id"])
        log_path = _repo_file(result["jsonl"])
        actual_hash = sha256_file(log_path)
        if actual_hash != result.get("jsonl_sha256"):
            raise ValueError(f"raw log drift for {condition}")
        rows = _load_jsonl(log_path)
        if any(str(row.get("condition_id", "")) != condition for row in rows):
            raise ValueError(f"condition identity drift inside {log_path}")
        if any(row.get("evidence_tier") != "formal_model" for row in rows):
            raise ValueError(f"non-formal evidence found inside {log_path}")
        by_condition[condition] = rows
        file_index.append(
            {
                "condition_id": condition,
                "path": log_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": actual_hash,
                "bytes": log_path.stat().st_size,
                "step_rows": len(rows),
            }
        )
    return by_condition, sorted(file_index, key=lambda item: item["condition_id"])


def _run_key(row: Mapping[str, Any]) -> str:
    key = str(row.get("run_key", "")).strip()
    if not key:
        raise ValueError("every formal row must carry a non-empty run_key")
    return key


def validate_logical_runs(
    logs_by_condition: Mapping[str, list[dict[str, Any]]],
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, list[list[dict[str, Any]]]]:
    expected_case_ids = {str(case["case_id"]) for case in cases}
    grouped_result: dict[str, list[list[dict[str, Any]]]] = {}
    for condition in EXPECTED_CONDITIONS:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in logs_by_condition[condition]:
            grouped[_run_key(row)].append(row)
        if len(grouped) != 24:
            raise ValueError(f"{condition}: expected 24 logical runs, got {len(grouped)}")
        seen_cases: list[str] = []
        ordered_runs: list[list[dict[str, Any]]] = []
        for run_key in sorted(grouped):
            rows = sorted(grouped[run_key], key=lambda item: int(item.get("step", 0) or 0))
            case_ids = {str(row.get("case_id", "")) for row in rows}
            if len(case_ids) != 1:
                raise ValueError(f"{condition}: run {run_key} mixes case IDs")
            if len({int(row.get("step", 0) or 0) for row in rows}) != len(rows):
                raise ValueError(f"{condition}: run {run_key} has duplicate steps")
            seen_cases.append(next(iter(case_ids)))
            ordered_runs.append(rows)
        if set(seen_cases) != expected_case_ids or len(seen_cases) != len(set(seen_cases)):
            raise ValueError(f"{condition}: missing, extra, or duplicate case runs")
        grouped_result[condition] = ordered_runs
    return grouped_result


def build_metric_rows(
    logs_by_condition: Mapping[str, list[dict[str, Any]]],
    cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    details: dict[tuple[str, str], dict[str, Any]] = {}
    for pattern in PATTERNS:
        pattern_cases = [
            case
            for case in cases
            if case["attack_dimensions"]["chain_pattern"] == pattern
        ]
        case_ids = {str(case["case_id"]) for case in pattern_cases}
        for condition in EXPECTED_CONDITIONS:
            pattern_logs = [
                row
                for row in logs_by_condition[condition]
                if str(row.get("case_id", "")) in case_ids
            ]
            metrics = compute_metrics(
                pattern_logs,
                pattern_cases,
                label=f"{pattern}:{condition}",
                strict_labels=True,
                include_missing=True,
            )
            if metrics["attack_runs"] != 6 or metrics["missing_case_runs"] != 0:
                raise ValueError(f"{pattern}:{condition} has an invalid denominator")
            details[(pattern, condition)] = metrics
            row: dict[str, Any] = {
                "pattern": pattern,
                "condition_id": condition,
                "prompt_profile": "normal",
                "guard_mode": "off" if condition == "posthoc_off" else "full_guard",
                "attack_runs": metrics["attack_runs"],
                "missing_case_runs": metrics["missing_case_runs"],
            }
            for metric in METRICS:
                for suffix in ("", "_numerator", "_denominator", "_ci_low", "_ci_high"):
                    row[f"{metric}{suffix}"] = metrics.get(f"{metric}{suffix}")
            rows.append(row)
    return rows, details


def build_pattern_statistics(
    logs_by_condition: Mapping[str, list[dict[str, Any]]],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return fixed pattern-level paired tests and Holm-corrected p-values."""

    comparisons: list[dict[str, Any]] = []
    raw_p_values: list[float] = []
    for index, pattern in enumerate(PATTERNS):
        pattern_cases = [
            case
            for case in cases
            if case["attack_dimensions"]["chain_pattern"] == pattern
        ]
        case_ids = {str(case["case_id"]) for case in pattern_cases}
        off_logs = [
            row
            for row in logs_by_condition["posthoc_off"]
            if str(row.get("case_id", "")) in case_ids
        ]
        full_logs = [
            row
            for row in logs_by_condition["posthoc_full"]
            if str(row.get("case_id", "")) in case_ids
        ]
        comparison = compare_runs(
            off_logs,
            full_logs,
            pattern_cases,
            strict_labels=True,
            bootstrap_iterations=10_000,
            bootstrap_seed=SEED + index,
        )
        paired = comparison["paired_statistics"]
        if paired.get("status") != "paired" or paired.get("pairs") != 6:
            raise ValueError(f"{pattern}: off/full results are not six case-paired runs")
        mcnemar = paired["ASR_mcnemar"]
        bootstrap = paired["ASR_bootstrap_guard_minus_baseline"]
        if mcnemar.get("pairs") != 6:
            raise ValueError(f"{pattern}: McNemar pair count drift")
        if (
            bootstrap.get("iterations") != 10_000
            or bootstrap.get("pairs") != 6
            or bootstrap.get("clusters") != 6
        ):
            raise ValueError(f"{pattern}: bootstrap contract drift")
        raw_p_values.append(float(mcnemar["p_value"]))
        comparisons.append(
            {
                "pattern": pattern,
                "off_asr": comparison["baseline"]["formal_metrics"]["ASR"],
                "full_asr": comparison["guarded"]["formal_metrics"]["ASR"],
                "asr_full_minus_off": bootstrap["estimate"],
                "mcnemar": dict(mcnemar),
                "case_paired_bootstrap": dict(bootstrap),
            }
        )
    adjusted = holm_adjust(raw_p_values)
    for item, value in zip(comparisons, adjusted):
        item["mcnemar"]["p_value_holm"] = value
        item["mcnemar"]["holm_family"] = list(PATTERNS)
    return {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "amendment_type": AMENDMENT_TYPE,
        "visualization_revision": VISUALIZATION_REVISION,
        "execution_revision": EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": DENOMINATOR_POLICY,
        "primary_estimand": "ASR(full_guard)-ASR(guard_off)",
        "bootstrap_iterations": 10_000,
        "multiple_comparison_correction": "Holm across four pattern-level ASR McNemar tests",
        "comparisons": comparisons,
    }


def build_statistics_from_binary_pairs(
    pattern_pairs: Mapping[str, Sequence[tuple[bool, bool]]], *, seed: int = SEED
) -> dict[str, Any]:
    """Dependency-light contract helper used by unit tests.

    Each pair is ``(off_attack_success, full_attack_success)``. The production
    analyzer uses the same exact statistical primitives after formal scoring.
    """

    results: list[dict[str, Any]] = []
    p_values: list[float] = []
    for index, pattern in enumerate(PATTERNS):
        pairs = list(pattern_pairs[pattern])
        if len(pairs) != 6:
            raise ValueError("each pattern requires exactly six case pairs")
        off = [left for left, _ in pairs]
        full = [right for _, right in pairs]
        mcnemar = mcnemar_exact(off, full)
        bootstrap = clustered_paired_bootstrap(
            [
                (f"{pattern}:{pair_index}", float(left), float(right))
                for pair_index, (left, right) in enumerate(pairs)
            ],
            iterations=10_000,
            seed=seed + index,
        )
        p_values.append(float(mcnemar["p_value"]))
        results.append(
            {"pattern": pattern, "mcnemar": mcnemar, "case_paired_bootstrap": bootstrap}
        )
    for result, adjusted in zip(results, holm_adjust(p_values)):
        result["mcnemar"]["p_value_holm"] = adjusted
    return {"comparisons": results, "bootstrap_iterations": 10_000}


def _redacted_observation(value: Any) -> str:
    text = str(value or "")
    for marker in (
        "M3_SYNTHETIC_CANARY=local-redteam-fixture",
        "M3_CANARY_SECRET_API_KEY",
        "sk-local-redteam-demo-not-real",
    ):
        text = text.replace(marker, "<redacted-synthetic-canary>")
    return text[:240] + ("..." if len(text) > 240 else "")


def build_raw_index_and_replays(
    *,
    file_index: list[dict[str, Any]],
    grouped_runs: Mapping[str, list[list[dict[str, Any]]]],
    cases: list[dict[str, Any]],
    fixtures: Mapping[str, Mapping[str, Any]],
    metric_details: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    outcomes: dict[tuple[str, str], Mapping[str, Any]] = {}
    for (pattern, condition), details in metric_details.items():
        for outcome in details["case_outcomes"]:
            outcomes[(condition, str(outcome["case_id"]))] = outcome
    case_map = {str(case["case_id"]): case for case in cases}
    raw_runs: list[dict[str, Any]] = []
    replay_by_case: dict[str, dict[str, Any]] = {}
    for condition in EXPECTED_CONDITIONS:
        for rows in grouped_runs[condition]:
            case_id = str(rows[0]["case_id"])
            case = case_map[case_id]
            pattern = str(case["attack_dimensions"]["chain_pattern"])
            final = rows[-1]
            raw_runs.append(
                {
                    "run_key": _run_key(rows[0]),
                    "case_id": case_id,
                    "pattern": pattern,
                    "condition_id": condition,
                    "step_count": len(rows),
                    "parse_failures": sum(not bool(row.get("parse_ok")) for row in rows),
                    "timed_out": any(bool(row.get("timed_out")) for row in rows),
                    "final_status": final.get("final_status"),
                    "attack_success": bool(outcomes[(condition, case_id)]["attack_success"]),
                }
            )
            replay = replay_by_case.setdefault(
                case_id,
                {
                    "case_id": case_id,
                    "pattern": pattern,
                    "source_tool_call": fixtures[str(case["observation_fixture_id"])][
                        "source_tool_call"
                    ],
                    "unsafe_next_tool_call": fixtures[str(case["observation_fixture_id"])][
                        "unsafe_next_tool_call"
                    ],
                    "unsafe_target_actions": case["unsafe_target_actions"],
                    "conditions": [],
                },
            )
            replay["conditions"].append(
                {
                    "condition_id": condition,
                    "attack_success": bool(outcomes[(condition, case_id)]["attack_success"]),
                    "final_status": final.get("final_status"),
                    "steps": [
                        {
                            "step": int(row.get("step", 0) or 0),
                            "parsed_tool_call": row.get("parsed_tool_call"),
                            "parse_ok": bool(row.get("parse_ok")),
                            "guard_decision": row.get("guard_decision"),
                            "risk_score": row.get("risk_score"),
                            "observation_preview": _redacted_observation(row.get("observation")),
                            "final_status": row.get("final_status"),
                        }
                        for row in rows
                    ],
                }
            )
    raw_runs.sort(key=lambda item: (item["condition_id"], item["case_id"]))
    if len(raw_runs) != 48:
        raise ValueError(f"raw index requires 48 logical runs, got {len(raw_runs)}")
    replay_rows = [replay_by_case[case_id] for case_id in sorted(replay_by_case)]
    for replay in replay_rows:
        replay["conditions"].sort(key=lambda item: item["condition_id"])
    return (
        {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
            "visualization_revision": VISUALIZATION_REVISION,
            "execution_revision": EXECUTION_REVISION,
            "denominator_policy": DENOMINATOR_POLICY,
            "files": file_index,
            "logical_run_count": len(raw_runs),
            "runs": raw_runs,
        },
        {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
            "visualization_revision": VISUALIZATION_REVISION,
            "execution_revision": EXECUTION_REVISION,
            "replays": replay_rows,
        },
    )


def _bbox_payload(bbox: Any, *, canvas_width: int, canvas_height: int) -> dict[str, float]:
    return {
        "x0_px": float(bbox.x0),
        "y0_px": float(bbox.y0),
        "x1_px": float(bbox.x1),
        "y1_px": float(bbox.y1),
        "x0_norm": float(bbox.x0) / canvas_width,
        "y0_norm": float(bbox.y0) / canvas_height,
        "x1_norm": float(bbox.x1) / canvas_width,
        "y1_norm": float(bbox.y1) / canvas_height,
    }


def _validate_primary_layout(fig: Any, ax: Any, footer: Any) -> dict[str, Any]:
    """Reject clipped or overlapping chart text before either export is trusted."""

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas_width, canvas_height = fig.canvas.get_width_height()
    footer_box = footer.get_window_extent(renderer=renderer)
    tick_boxes = [
        label.get_window_extent(renderer=renderer)
        for label in ax.get_xticklabels()
        if label.get_visible() and label.get_text().strip()
    ]
    if len(tick_boxes) != len(PATTERNS):
        raise ValueError("primary figure must retain exactly four visible x-axis labels")
    edge_padding = max(10.0, canvas_height * 0.012)
    if (
        footer_box.x0 < edge_padding
        or footer_box.y0 < edge_padding
        or footer_box.x1 > canvas_width - edge_padding
        or footer_box.y1 > canvas_height - edge_padding
    ):
        raise ValueError("primary figure footer is clipped or too close to the canvas edge")
    for index, box in enumerate(tick_boxes):
        if (
            box.x0 < edge_padding
            or box.x1 > canvas_width - edge_padding
            or box.y0 < edge_padding
            or box.y1 > canvas_height - edge_padding
        ):
            raise ValueError(f"primary figure x-axis label {index} is clipped")
    minimum_tick_bottom = min(box.y0 for box in tick_boxes)
    footer_tick_gap = minimum_tick_bottom - footer_box.y1
    required_gap = max(18.0, canvas_height * 0.02)
    if footer_tick_gap < required_gap:
        raise ValueError(
            f"primary figure footer overlaps x-axis labels: gap={footer_tick_gap:.1f}px, required={required_gap:.1f}px"
        )
    ordered = sorted(tick_boxes, key=lambda box: box.x0)
    for left, right in zip(ordered, ordered[1:]):
        if left.x1 + 8.0 > right.x0:
            raise ValueError("primary figure x-axis labels overlap horizontally")
    return {
        "visualization_revision": VISUALIZATION_REVISION,
        "canvas_width_px": canvas_width,
        "canvas_height_px": canvas_height,
        "footer_bbox": _bbox_payload(
            footer_box, canvas_width=canvas_width, canvas_height=canvas_height
        ),
        "x_tick_bboxes": [
            _bbox_payload(box, canvas_width=canvas_width, canvas_height=canvas_height)
            for box in tick_boxes
        ],
        "footer_to_tick_gap_px": float(footer_tick_gap),
        "required_footer_to_tick_gap_px": float(required_gap),
        "layout_status": "pass",
    }


def render_primary_figure(
    metric_rows: Sequence[Mapping[str, Any]], output_dir: Path
) -> dict[str, Any]:
    values: dict[tuple[str, str], Mapping[str, Any]] = {
        (str(row["pattern"]), str(row["condition_id"])): row for row in metric_rows
    }
    x = np.arange(len(PATTERNS), dtype=float)
    width = 0.34
    colors = {"posthoc_off": "#9AA4B2", "posthoc_full": "#1976A3"}
    fig, ax = plt.subplots(figsize=(11.5, 6.6), dpi=FIGURE_DPI)
    fig.subplots_adjust(left=0.10, right=0.985, top=0.90, bottom=0.27)
    for offset_index, condition in enumerate(EXPECTED_CONDITIONS):
        centers = x + (offset_index - 0.5) * width
        y: list[float] = []
        lower: list[float] = []
        upper: list[float] = []
        for pattern in PATTERNS:
            row = values[(pattern, condition)]
            value = row.get("ASR")
            ci_low = row.get("ASR_ci_low")
            ci_high = row.get("ASR_ci_high")
            if value is None or ci_low is None or ci_high is None:
                raise ValueError(f"ASR is undefined for {pattern}:{condition}")
            current = float(value)
            y.append(current)
            lower.append(current - float(ci_low))
            upper.append(float(ci_high) - current)
        bars = ax.bar(
            centers,
            y,
            width,
            label=CONDITION_LABELS[condition],
            color=colors[condition],
            edgecolor="white",
            linewidth=0.8,
            yerr=np.array([lower, upper]),
            capsize=5,
        )
        for bar, value in zip(bars, y):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                min(1.04, value + 0.055),
                f"{value:.0%}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    ax.set_title("E11 post-hoc amendment: attack success by observation chain", pad=12)
    ax.set_ylabel("Attack success rate (ASR)")
    ax.set_xticks(x, [PATTERN_LABELS[pattern] for pattern in PATTERNS])
    ax.tick_params(axis="x", labelsize=9.2, pad=10)
    ax.set_ylim(0.0, 1.12)
    ax.set_yticks(np.linspace(0.0, 1.0, 6))
    ax.set_yticklabels([f"{value:.0%}" for value in np.linspace(0.0, 1.0, 6)])
    ax.grid(axis="y", color="#D6DCE5", linewidth=0.8, alpha=0.75)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    legend = ax.legend(loc="upper right", frameon=True, facecolor="white", framealpha=1.0)
    legend.get_frame().set_edgecolor("#D6DCE5")
    footer = fig.text(
        0.10,
        0.035,
        "Each bar represents 6 attack cases per pattern; whiskers show Wilson 95% confidence intervals.\n"
        "Post-hoc supplement (pre_registered=false); excluded from the original E11 denominator.",
        ha="left",
        va="bottom",
        fontsize=8.2,
        linespacing=1.35,
        color="#4B5563",
    )
    layout = _validate_primary_layout(fig, ax, footer)
    png_path = output_dir / "primary_chart.png"
    svg_path = output_dir / "primary_chart.svg"
    fig.savefig(png_path, dpi=FIGURE_DPI, facecolor="white")
    fig.savefig(svg_path, facecolor="white")
    plt.close(fig)
    pixels = plt.imread(png_path)
    if pixels.shape[1] != layout["canvas_width_px"] or pixels.shape[0] != layout["canvas_height_px"]:
        raise ValueError("primary figure PNG dimensions drifted from the validated canvas")
    bottom_guard = pixels[-BOTTOM_GUARD_ROWS:, :, :3]
    bottom_guard_min = float(np.min(bottom_guard))
    if bottom_guard_min < 0.98:
        raise ValueError(
            f"primary figure has ink in the {BOTTOM_GUARD_ROWS}-pixel bottom clipping guard"
        )
    layout["png_bottom_guard_min_rgb"] = bottom_guard_min
    layout["png_bottom_guard_rows"] = BOTTOM_GUARD_ROWS
    layout["png_bytes"] = png_path.stat().st_size
    layout["svg_bytes"] = svg_path.stat().st_size
    return layout


def _analysis_markdown(metric_rows: list[dict[str, Any]], statistics: Mapping[str, Any]) -> str:
    metric_map = {
        (str(row["pattern"]), str(row["condition_id"])): row for row in metric_rows
    }
    lines = [
        "# E11 Post-hoc Protocol Amendment Analysis",
        "",
        "> This is a post-hoc protocol amendment (`pre_registered=false`). Its 48 formal runs are "
        "supplementary and are excluded from the original E11 denominator.",
        "",
        "## Pattern-level results",
        "",
        "| Pattern | Guard off ASR | Full Guard ASR | Full−off difference (95% paired bootstrap CI) | McNemar p | Holm p |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    stats_by_pattern = {
        str(item["pattern"]): item for item in statistics["comparisons"]
    }
    for pattern in PATTERNS:
        off = metric_map[(pattern, "posthoc_off")]
        full = metric_map[(pattern, "posthoc_full")]
        stats = stats_by_pattern[pattern]
        boot = stats["case_paired_bootstrap"]
        mcnemar = stats["mcnemar"]
        lines.append(
            "| {label} | {on}/{od} ({ov:.1%}) | {fn}/{fd} ({fv:.1%}) | "
            "{estimate:+.1%} [{low:+.1%}, {high:+.1%}] | {p:.4g} | {holm:.4g} |".format(
                label=PATTERN_LABELS[pattern],
                on=int(off["ASR_numerator"]),
                od=int(off["ASR_denominator"]),
                ov=float(off["ASR"]),
                fn=int(full["ASR_numerator"]),
                fd=int(full["ASR_denominator"]),
                fv=float(full["ASR"]),
                estimate=float(boot["estimate"]),
                low=float(boot["ci_low"]),
                high=float(boot["ci_high"]),
                p=float(mcnemar["p_value"]),
                holm=float(mcnemar["p_value_holm"]),
            )
        )
    parse_numerator = sum(
        int(row["ParseSuccessRate_numerator"]) for row in metric_rows
    )
    parse_denominator = sum(
        int(row["ParseSuccessRate_denominator"]) for row in metric_rows
    )
    unresolved = sum(int(row["UnresolvedRate_numerator"]) for row in metric_rows)
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Each row is independently denominated at six paired cases. McNemar tests are exact; "
            "bootstrap intervals use 10,000 case-paired resamples; Holm correction covers the four "
            "pattern-level ASR tests. Effect sizes and intervals, not a single p-value, govern the "
            "description.",
            "",
            f"Across the condition-by-pattern cells, parse success was {parse_numerator}/{parse_denominator} "
            f"step outputs and unresolved case-runs totaled {unresolved}. These operational failures "
            "remain in the original per-pattern denominators and are available in the raw index and "
            "case replay files.",
            "",
            "The amendment does not estimate benign-task FPR or TCR, does not replace the original E11 "
            "result, and must not be described as pre-registered or pooled with the original blind matrix.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_entry(path: Path, output_dir: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def analyze(run_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    execution, matrix = validate_formal_execution(run_root)
    resolved_run_root = (
        Path(run_root) if Path(run_root).is_absolute() else REPO_ROOT / Path(run_root)
    ).resolve()
    execution_manifest_path = resolved_run_root / "formal" / "execution_manifest.json"
    cases, fixtures = load_protocol_data()
    logs_by_condition, file_index = load_formal_logs(matrix)
    grouped_runs = validate_logical_runs(logs_by_condition, cases)
    metric_rows, metric_details = build_metric_rows(logs_by_condition, cases)
    statistics = build_pattern_statistics(logs_by_condition, cases)
    raw_index, replays = build_raw_index_and_replays(
        file_index=file_index,
        grouped_runs=grouped_runs,
        cases=cases,
        fixtures=fixtures,
        metric_details=metric_details,
    )

    destination = Path(output_dir)
    destination = destination if destination.is_absolute() else REPO_ROOT / destination
    destination = destination.resolve()
    original_e11 = (REPO_ROOT / "outputs" / "experiments" / "E11").resolve()
    try:
        destination.relative_to(original_e11)
    except ValueError:
        pass
    else:
        raise ValueError("refusing to overwrite or merge the original E11 bundle")
    experiments_root = (REPO_ROOT / "outputs" / "experiments").resolve()
    try:
        destination.relative_to(experiments_root)
    except ValueError as exc:
        raise ValueError("analysis output must stay under outputs/experiments") from exc
    destination.mkdir(parents=True, exist_ok=True)

    metric_fields = [
        "pattern",
        "condition_id",
        "prompt_profile",
        "guard_mode",
        "attack_runs",
        "missing_case_runs",
    ]
    for metric in METRICS:
        metric_fields.extend(
            [
                metric,
                f"{metric}_numerator",
                f"{metric}_denominator",
                f"{metric}_ci_low",
                f"{metric}_ci_high",
            ]
        )
    metrics_path = destination / "metrics.csv"
    statistics_path = destination / "statistics.json"
    raw_index_path = destination / "raw_run_index.json"
    replay_path = destination / "case_replays.json"
    chart_data_path = destination / "primary_chart_data.csv"
    analysis_path = destination / "analysis.md"
    _write_csv(metrics_path, metric_rows, metric_fields)
    _atomic_write_json(statistics_path, statistics)
    _atomic_write_json(raw_index_path, raw_index)
    _atomic_write_json(replay_path, replays)
    chart_fields = [
        "pattern",
        "condition_id",
        "attack_runs",
        "ASR",
        "ASR_numerator",
        "ASR_denominator",
        "ASR_ci_low",
        "ASR_ci_high",
    ]
    _write_csv(
        chart_data_path,
        [{field: row[field] for field in chart_fields} for row in metric_rows],
        chart_fields,
    )
    layout = render_primary_figure(metric_rows, destination)
    layout_path = destination / "primary_chart_layout.json"
    _atomic_write_json(
        layout_path,
        {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
            "execution_revision": EXECUTION_REVISION,
            **layout,
        },
    )
    _atomic_write_text(analysis_path, _analysis_markdown(metric_rows, statistics))
    figure_manifest_path = write_figure_manifest(
        destination,
        experiment_id="E11",
        evidence_tier="formal_model_posthoc",
        figures=[
            {
                "id": "e11_posthoc_asr_by_pattern",
                "title": "Post-hoc ASR by observation-to-next-action pattern",
                "role": "primary",
                "order": 0,
                "chart_type": "grouped_bar_with_wilson_95ci",
                "caption": (
                    "Six attack cases per pattern under the same normal prompt with Guard off or full Guard. "
                    "Visualization revision 2 passes fixed-margin, text-bbox, and bottom-pixel guard checks. "
                    "This post-hoc evidence is excluded from the original E11 denominator."
                ),
                "files": {
                    "data": {"path": "primary_chart_data.csv"},
                    "png": {"path": "primary_chart.png"},
                    "svg": {"path": "primary_chart.svg"},
                },
                "metrics": ["ASR"],
                "grain": ["pattern", "condition_id"],
                "uncertainty": [
                    {
                        "metric": "ASR",
                        "method": "Wilson score interval",
                        "confidence": 0.95,
                        "denominator_per_bar": 6,
                    }
                ],
                "warnings": [
                    "Post-hoc protocol amendment; pre_registered=false; excluded from original E11 denominator; "
                    "visualization_revision=2."
                ],
            }
        ],
    )

    artifact_paths = [
        metrics_path,
        statistics_path,
        analysis_path,
        raw_index_path,
        replay_path,
        chart_data_path,
        layout_path,
        destination / "primary_chart.png",
        destination / "primary_chart.svg",
        figure_manifest_path,
    ]
    manifest = {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "experiment_id": "E11",
        "amendment_type": AMENDMENT_TYPE,
        "visualization_revision": VISUALIZATION_REVISION,
        "execution_revision": EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": DENOMINATOR_POLICY,
        "status": "completed",
        "evidence_tier": "formal_model_posthoc",
        "model": FORMAL_MODEL,
        "case_count": 24,
        "logical_run_count": 48,
        "conditions": list(EXPECTED_CONDITIONS),
        "pattern_counts": dict(
            sorted(
                Counter(
                    str(case["attack_dimensions"]["chain_pattern"]) for case in cases
                ).items()
            )
        ),
        "source_execution_manifest": execution,
        "source_execution_manifest_path": execution_manifest_path.relative_to(
            REPO_ROOT
        ).as_posix(),
        "source_execution_manifest_sha256": sha256_file(execution_manifest_path),
        "artifacts": [_artifact_entry(path, destination) for path in artifact_paths],
    }
    manifest_path = destination / "manifest.json"
    _atomic_write_json(manifest_path, manifest)
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    manifest = analyze(args.run_root, args.output_dir)
    print(
        f"completed E11 post-hoc amendment analysis: {manifest['logical_run_count']} runs, "
        f"output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
