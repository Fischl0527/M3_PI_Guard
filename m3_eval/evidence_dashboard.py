"""Paper-v2 可追溯证据全景看板与审计追踪可视化面板。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from m3_eval.figure_manifest import (
    FIGURE_MANIFEST_FILENAME,
    FigureManifestError,
    load_figure_manifest,
    sha256_file,
)
from m3_eval.metrics import compute_metrics


REPO_ROOT = Path(__file__).resolve().parents[1]

PROPORTION_METRICS = (
    "ASR",
    "DSR",
    "TCR",
    "FPR",
    "ASK",
    "ParseSuccessRate",
)
SUPPORTING_METRICS = ("Precision", "Recall", "F1", "UnresolvedRate")
LATENCY_METRICS = (
    "GuardLatencyP50",
    "GuardLatencyP95",
    "CaseLatencyP50",
    "CaseLatencyP95",
)
FILTER_FIELDS = (
    "evidence_layer",
    "model",
    "defense_condition",
    "attack_family",
    "language",
    "experiment_batch",
)

# Run logs are produced by reusable runtime stages (for example ``main``),
# while the derived metric bundles are published under experiment IDs such as
# E1, E2, and E6.  Keep the physical stage as provenance, but expose the
# experiment IDs that legitimately reuse that stage through an alias field so
# one experiment-batch filter can retain both its metrics and replay rows.
FILTER_ALIAS_FIELDS = {"experiment_batch": "experiment_batches"}
MAIN_STAGE_EXPERIMENTS = ("E1", "E2", "E3", "E5", "E6", "E12")

EVIDENCE_LABELS = {
    "formal_real_model": "Formal real-model evidence",
    "invalid_context_diagnostic": "Superseded context diagnostic",
    "stub_regression_only": "Stub regression only",
    "historical_diagnostic": "Historical diagnostic only",
    "smoke_gate_diagnostic": "Smoke-gate diagnostic",
    "unknown_diagnostic": "Unclassified diagnostic",
}

STOP_DECISIONS = {"ask", "deny"}
STOP_STATUSES = {"blocked", "needs_confirmation"}
RISKY_TOOLS = {"read_file", "write_file", "send_email", "call_api", "run_code"}
OVERLAPPING_SCOPES = {
    "family_all_models": "family_by_model",
    "utility_overall": "utility_by_tool_requirement",
    "stability_temperature": "stability_seed",
}

SENSITIVE_KEY_RE = re.compile(
    r"(?i)(api[_ -]?key|access[_ -]?token|token|password|passwd|secret|authorization)"
    r"(\s*[:=]\s*)([^\s,;\]\}\"']+)"
)
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{8,}=*\b")
CANARY_RE = re.compile(r"(?i)M3_SYNTHETIC_CANARY\s*=\s*[^\s]+")


def parse_optional_number(value: Any) -> float | None:
    """解析可选数值，同时将缺失或未定义的值保留为 ``None``。"""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    text = str(value).strip()
    if text.casefold() in {"", "na", "n/a", "none", "null", "nan", "undefined"}:
        return None
    try:
        numeric = float(text)
    except ValueError:
        return None
    return numeric if math.isfinite(numeric) else None


def _string(value: Any) -> str:
    return str(value or "").strip()


def _json_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return [value] if value else []
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
    return [str(value)] if value is not None and value != "" else []


def derive_evidence_layer(record: Mapping[str, Any], source: str = "") -> str:
    """对论据层级进行分类，防止将 Stub/冒烟/历史测试混入正式主张中。"""

    source_text = source.replace("\\", "/").casefold()
    if _string(record.get("context_validity_status")).casefold().startswith(
        "invalid_superseded"
    ):
        return "invalid_context_diagnostic"
    tier = _string(record.get("evidence_tier")).casefold()
    backend = _string(record.get("backend")).casefold()
    experiment = _string(record.get("experiment_id")).casefold()
    run_group = _string(record.get("run_group")).casefold()
    batch = _string(record.get("experiment_batch")).casefold()
    oracle_stub = record.get("oracle_stub") is True
    if (
        backend == "stub"
        or oracle_stub
        or "regression" in tier
        or "stub" in batch
        or "stub" in experiment
        or "stub" in run_group
        or "/stub" in source_text
    ):
        return "stub_regression_only"
    if (
        experiment == "e0"
        or "historical" in tier
        or "historical" in source_text
        or re.search(r"/day[2-6]_", source_text)
    ):
        return "historical_diagnostic"
    if (
        "smoke" in experiment
        or "smoke" in run_group
        or "smoke" in batch
        or "/smoke" in source_text
        or "smoke_gate" in tier
    ):
        return "smoke_gate_diagnostic"
    formal_program_batches = {
        "validation-baseline",
        "ablation",
        "main",
        "derived",
        "stability",
        "performance",
    }
    if backend == "ollama" or tier.startswith("formal") or batch in formal_program_batches:
        return "formal_real_model"
    return "unknown_diagnostic"


def _downgrade_superseded_context_records(
    rows: Sequence[dict[str, Any]],
) -> int:
    """将旧版 E9/E14 明确标记为不合格的诊断数据，仅作可见保留。

    V3 程序仍可作为 E0-E8/E10-E13/E15-E16 的有效溯源，但其 E9/E14 上下文轴
    在后续语义审计中未通过。修正后的 r2 数据包按协议/修订标识准入；
    所有不具备该标识的孤立 E9/E14 数据行在计算过滤默认值或 KPI 卡片前均会被降级。
    """

    changed = 0
    targets = {"E9", "E14"}
    for row in rows:
        batches = set(_json_list(row.get("experiment_batches")))
        direct = _string(row.get("experiment_batch")) or _string(
            row.get("experiment_id")
        )
        if direct in targets:
            batches.add(direct)
        if not (batches & targets) or not batches.issubset(targets):
            continue
        source = _string(row.get("source_path")).replace("\\", "/").casefold()
        protocol_values = {
            _string(row.get("protocol_id")),
            _string(row.get("correction_protocol_id")),
            _string(row.get("context_correction_protocol")),
        }
        corrected = (
            "CONTEXT_CORRECTION_V2" in protocol_values
            and _string(row.get("workload_revision")) == "r2"
        ) or "context_correction_v2_r2" in source or "context_correction_v2_r3" in source
        if corrected:
            continue
        row["context_validity_status"] = "invalid_superseded_v3"
        row["claim_eligible"] = False
        row["evidence_layer"] = "invalid_context_diagnostic"
        row["evidence_warning"] = (
            "Superseded E9/E14 context evidence; excluded from formal claims and "
            "never pooled with Context Correction V2 r2."
        )
        changed += 1
    return changed


def normalize_metric_record(
    row: Mapping[str, Any],
    *,
    source: str = "",
    batch_hint: str = "",
    evidence_hint: str = "",
) -> dict[str, Any]:
    """返回规范化的指标记录，且不修改原始数据行。"""

    result = deepcopy(dict(row))
    if evidence_hint and not result.get("evidence_tier"):
        result["evidence_tier"] = evidence_hint
    condition_id = _string(result.get("condition_id") or result.get("run_name"))
    prompt_profile = _string(
        result.get("prompt_profile") or result.get("historical_prompt_profile")
    )
    guard_mode = _string(
        result.get("guard_mode")
        or result.get("defense_mode")
        or result.get("historical_guard_mode")
        or result.get("legacy_defense_mode")
    )
    experiment_batch = _string(
        result.get("experiment_batch") or result.get("experiment_id") or batch_hint
    )
    result.update(
        {
            "record_type": "metric",
            "source_path": source,
            "experiment_batch": experiment_batch or Path(source).stem,
            "defense_condition": condition_id
            or " | ".join(value for value in (prompt_profile, guard_mode) if value)
            or "unspecified",
            "guard_mode": guard_mode,
            "attack_family": _string(result.get("attack_family")),
            "language": _string(result.get("language")),
        }
    )
    result["evidence_layer"] = derive_evidence_layer(result, source)
    for metric in (*PROPORTION_METRICS, *SUPPORTING_METRICS):
        result[metric] = parse_optional_number(result.get(metric))
        result[f"{metric}_numerator"] = parse_optional_number(
            result.get(f"{metric}_numerator")
        )
        result[f"{metric}_denominator"] = parse_optional_number(
            result.get(f"{metric}_denominator")
        )
        result[f"{metric}_ci_low"] = parse_optional_number(result.get(f"{metric}_ci_low"))
        result[f"{metric}_ci_high"] = parse_optional_number(result.get(f"{metric}_ci_high"))
    for metric in LATENCY_METRICS:
        result[metric] = parse_optional_number(result.get(metric))
    return result


def _safe_dimension(log: Mapping[str, Any], key: str) -> str:
    if log.get(key) not in {None, ""}:
        return _string(log.get(key))
    metadata = log.get("evaluation_metadata")
    if isinstance(metadata, Mapping):
        return _string(metadata.get(key))
    return ""


def normalize_log_record(
    row: Mapping[str, Any],
    *,
    source: str = "",
    batch_hint: str = "",
    batch_aliases: Sequence[str] = (),
    evidence_hint: str = "",
) -> dict[str, Any]:
    """添加安全的仪表盘维度，同时在内存中保留原始日志行。"""

    result = deepcopy(dict(row))
    if evidence_hint and not result.get("evidence_tier"):
        result["evidence_tier"] = evidence_hint
    condition_id = _string(result.get("condition_id"))
    prompt_profile = _string(result.get("prompt_profile"))
    guard_mode = _string(result.get("guard_mode") or result.get("defense_mode"))
    experiment_batch = _string(
        result.get("run_group")
        or result.get("experiment_batch")
        or result.get("experiment_id")
        or batch_hint
        or Path(source).stem
    )
    experiment_batches = sorted(
        {
            value
            for value in (
                (_string(alias) for alias in batch_aliases)
                if batch_aliases
                else (experiment_batch,)
            )
            if value
        },
        key=str.casefold,
    )
    run_key = _string(result.get("run_key"))
    if not run_key:
        run_id = _string(result.get("run_id")) or "missing-run-id"
        case_id = _string(result.get("case_id")) or "missing-case-id"
        run_key = f"legacy:{Path(source).name}:{run_id}:{case_id}"
    experiment_id = _string(result.get("experiment_id")) or experiment_batch or "legacy"
    run_id = _string(result.get("run_id")) or run_key
    source_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:8]
    replay_key = f"{experiment_id}::{run_id}::{run_key}::s{source_digest}"
    result.update(
        {
            "record_type": "runlog",
            "source_path": source,
            "experiment_batch": experiment_batch,
            "experiment_batches": experiment_batches,
            "defense_condition": condition_id
            or " | ".join(value for value in (prompt_profile, guard_mode) if value)
            or "unspecified",
            "guard_mode": guard_mode,
            "attack_family": _safe_dimension(result, "attack_family"),
            "language": _safe_dimension(result, "language"),
            "run_key": run_key,
            "replay_key": replay_key,
        }
    )
    result["evidence_layer"] = derive_evidence_layer(result, source)
    return result


def normalize_manifest_records(
    payload: Mapping[str, Any],
    *,
    source: str = "",
) -> list[dict[str, Any]]:
    """将程序、清单包与矩阵清单展平为注册表记录行。"""

    rows: list[dict[str, Any]] = []
    stages = payload.get("stages")
    if isinstance(stages, Mapping):
        for stage_name, stage_value in stages.items():
            stage = stage_value if isinstance(stage_value, Mapping) else {}
            jobs = stage.get("jobs") if isinstance(stage.get("jobs"), list) else []
            stage_batches = sorted(
                {
                    experiment
                    for job_value in jobs
                    if isinstance(job_value, Mapping)
                    for experiment in _program_job_experiment_batches(
                        str(stage_name), job_value
                    )
                }
                or {_string(stage_name)},
                key=str.casefold,
            )
            progress = stage.get("progress") if isinstance(stage.get("progress"), Mapping) else {}
            stage_record = {
                "record_type": "program_stage",
                "source_path": source,
                "experiment_batch": str(stage_name),
                "experiment_batches": stage_batches,
                "stage": str(stage_name),
                "job_id": "",
                "model": "",
                "defense_condition": "all",
                "status": _string(stage.get("status")),
                "expected_runs": parse_optional_number(
                    progress.get("expected_runs", stage.get("expected_run_count"))
                ),
                "completed_runs": parse_optional_number(
                    progress.get("completed_runs", stage.get("completed_run_count"))
                ),
                "error_count": parse_optional_number(
                    progress.get("error_count", stage.get("error_count"))
                ),
                "evidence_tier": _string(stage.get("evidence_tier")),
            }
            stage_record["evidence_layer"] = derive_evidence_layer(stage_record, source)
            rows.append(stage_record)
            for job_value in jobs:
                job = job_value if isinstance(job_value, Mapping) else {}
                matrix = job.get("matrix_config") if isinstance(job.get("matrix_config"), Mapping) else {}
                job_record = {
                    "record_type": "program_job",
                    "source_path": source,
                    "experiment_batch": str(stage_name),
                    "experiment_batches": list(
                        _program_job_experiment_batches(str(stage_name), job)
                    ),
                    "stage": str(stage_name),
                    "job_id": _string(job.get("job_id")),
                    "model": _string(job.get("model") or matrix.get("model")),
                    "defense_condition": _string(matrix.get("conditions")) or "unspecified",
                    "status": _string(job.get("status")),
                    "expected_runs": parse_optional_number(job.get("expected_run_count")),
                    "completed_runs": parse_optional_number(job.get("completed_run_count")),
                    "error_count": parse_optional_number(job.get("error_count")),
                    "evidence_tier": _string(job.get("evidence_tier")),
                    "result_manifest": _string(job.get("result_manifest")),
                }
                job_record["evidence_layer"] = derive_evidence_layer(job_record, source)
                rows.append(job_record)
        return rows

    config = payload.get("config") if isinstance(payload.get("config"), Mapping) else {}
    progress = payload.get("progress") if isinstance(payload.get("progress"), Mapping) else {}
    batch = _string(payload.get("experiment_id") or payload.get("run_group") or payload.get("program_id"))
    if not batch:
        batch = Path(source).parent.name or Path(source).stem
    row = {
        "record_type": "bundle_or_matrix_manifest",
        "source_path": source,
        "experiment_batch": batch,
        "stage": _string(payload.get("run_group")),
        "job_id": _string(payload.get("run_prefix")),
        "model": _string(payload.get("model") or config.get("model")),
        "defense_condition": " | ".join(_json_list(payload.get("defense_modes")))
        or _string(config.get("conditions"))
        or "unspecified",
        "status": _string(payload.get("status")),
        "expected_runs": parse_optional_number(
            progress.get("expected_runs", payload.get("expected_run_count"))
        ),
        "completed_runs": parse_optional_number(
            progress.get("completed_runs", payload.get("completed_run_count"))
        ),
        "error_count": parse_optional_number(
            progress.get("error_count", progress.get("failed_jobs", payload.get("error_count")))
        ),
        "evidence_tier": _string(payload.get("evidence_tier")),
    }
    row["evidence_layer"] = derive_evidence_layer(row, source)
    return [row]


def available_filter_values(
    metric_rows: Sequence[Mapping[str, Any]],
    logs: Sequence[Mapping[str, Any]],
    manifests: Sequence[Mapping[str, Any]] = (),
) -> dict[str, list[str]]:
    """返回跨所有仪表盘粒度的已排序非空过滤取值。"""

    records = [*metric_rows, *logs, *manifests]
    result: dict[str, list[str]] = {}
    for field in FILTER_FIELDS:
        values: set[str] = set()
        alias_field = FILTER_ALIAS_FIELDS.get(field)
        for record in records:
            aliases = record.get(alias_field) if alias_field else None
            if isinstance(aliases, Sequence) and not isinstance(aliases, (str, bytes)):
                values.update(_string(value) for value in aliases if _string(value))
            elif _string(record.get(field)):
                values.add(_string(record.get(field)))
        result[field] = sorted(values, key=str.casefold)
    return result


def apply_filters(
    rows: Sequence[Mapping[str, Any]],
    selections: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    """精确过滤记录；缺失的维度绝不伪装成匹配项。"""

    selected = {
        field: {str(value) for value in values if str(value)}
        for field, values in selections.items()
        if values
    }
    def matches(row: Mapping[str, Any], field: str, values: set[str]) -> bool:
        alias_field = FILTER_ALIAS_FIELDS.get(field)
        aliases = row.get(alias_field) if alias_field else None
        if isinstance(aliases, Sequence) and not isinstance(aliases, (str, bytes)):
            return bool({_string(value) for value in aliases if _string(value)} & values)
        return _string(row.get(field)) in values

    return [
        deepcopy(dict(row))
        for row in rows
        if all(matches(row, field, values) for field, values in selected.items())
    ]


def select_nonoverlapping_metric_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """当存在不相交的明细粒度数据时，移除上层汇总范围记录。"""

    scopes_by_batch: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        scopes_by_batch[_string(row.get("experiment_batch"))].add(_string(row.get("scope")))
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in rows:
        row = deepcopy(dict(source))
        batch = _string(row.get("experiment_batch"))
        scope = _string(row.get("scope"))
        detailed_scope = OVERLAPPING_SCOPES.get(scope)
        if detailed_scope and detailed_scope in scopes_by_batch[batch]:
            continue
        identity = json.dumps(
            {
                key: row.get(key)
                for key in (
                    "source_path",
                    "experiment_batch",
                    "scope",
                    "model",
                    "defense_condition",
                    "attack_family",
                    "language",
                    "requires_tool",
                    "seed",
                    "temperature",
                )
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if identity not in seen:
            result.append(row)
            seen.add(identity)
    return result


def wilson_interval(successes: float, total: float, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if total <= 0 or successes < 0 or successes > total:
        return None
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(
        (proportion * (1.0 - proportion) + z * z / (4.0 * total)) / total
    ) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def aggregate_metric_cards(
    rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[str] = PROPORTION_METRICS,
) -> dict[str, dict[str, Any]]:
    """汇总包含计数的不相交指标记录；绝不将缺失值自动转换为零。"""

    canonical = select_nonoverlapping_metric_rows(rows)
    result: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        count_rows: list[tuple[float, float]] = []
        reported_rows: list[Mapping[str, Any]] = []
        for row in canonical:
            numerator = parse_optional_number(row.get(f"{metric}_numerator"))
            denominator = parse_optional_number(row.get(f"{metric}_denominator"))
            if numerator is not None and denominator is not None and denominator > 0:
                count_rows.append((numerator, denominator))
            elif parse_optional_number(row.get(metric)) is not None:
                reported_rows.append(row)
        if count_rows and reported_rows:
            result[metric] = {
                "value": None,
                "numerator": None,
                "denominator": None,
                "ci_low": None,
                "ci_high": None,
                "status": "NA_mixed_count_and_value_only_rows",
                "source_group_count": len(count_rows) + len(reported_rows),
            }
        elif count_rows:
            numerator = sum(value[0] for value in count_rows)
            denominator = sum(value[1] for value in count_rows)
            interval = wilson_interval(numerator, denominator)
            result[metric] = {
                "value": numerator / denominator,
                "numerator": numerator,
                "denominator": denominator,
                "ci_low": interval[0] if interval else None,
                "ci_high": interval[1] if interval else None,
                "status": "pooled_disjoint_counts",
                "source_group_count": len(count_rows),
            }
        elif len(reported_rows) == 1:
            row = reported_rows[0]
            result[metric] = {
                "value": parse_optional_number(row.get(metric)),
                "numerator": parse_optional_number(row.get(f"{metric}_numerator")),
                "denominator": parse_optional_number(row.get(f"{metric}_denominator")),
                "ci_low": parse_optional_number(row.get(f"{metric}_ci_low")),
                "ci_high": parse_optional_number(row.get(f"{metric}_ci_high")),
                "status": "single_reported_value",
                "source_group_count": 1,
            }
        else:
            result[metric] = {
                "value": None,
                "numerator": None,
                "denominator": None,
                "ci_low": None,
                "ci_high": None,
                "status": "NA_no_compatible_denominator",
                "source_group_count": 0,
            }
    return result


def _na_metric_cards(status: str) -> dict[str, dict[str, Any]]:
    return {
        metric: {
            "value": None,
            "numerator": None,
            "denominator": None,
            "ci_low": None,
            "ci_high": None,
            "status": status,
            "source_group_count": 0,
        }
        for metric in PROPORTION_METRICS
    }


def recompute_metric_cards_from_logs(
    logs: Sequence[Mapping[str, Any]],
    *,
    repository_root: str | Path = REPO_ROOT,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """从过滤切片对应的确切 RunLog 记录行中重新计算 KPI 指标卡片。

    公开发布的指标表格在 E0-E17 间特意采用了不同的粒度。
    若在模型/家族/语言过滤后直接复用汇总行，会隐式误标为子组结果。
    此路径通过解析选定 RunLog 中记录的固化 ``case_source`` 文件，
    重新运行实验流水线所采用的完全相同的形式化指标实现。
    """

    if not logs:
        status = "NA_no_selected_runlogs"
        return _na_metric_cards(status), {"status": status, "case_sources": []}

    root = Path(repository_root).resolve()
    source_paths: dict[Path, str] = {}
    for row in logs:
        reference = _string(row.get("case_source"))
        if not reference:
            continue
        log_source = Path(_string(row.get("source_path")))
        anchors = (root, log_source.parent if _string(row.get("source_path")) else root)
        resolved = _resolve_reference(reference, anchors=anchors)
        if resolved is not None:
            source_paths[resolved] = reference

    if not source_paths:
        status = "NA_missing_case_source"
        return _na_metric_cards(status), {"status": status, "case_sources": []}

    case_ids = {_string(row.get("case_id")) for row in logs if _string(row.get("case_id"))}
    case_map: dict[str, dict[str, Any]] = {}
    for path in sorted(source_paths, key=lambda value: str(value).casefold()):
        for case in _read_jsonl(path):
            case_id = _string(case.get("case_id"))
            if case_id in case_ids and case_id not in case_map:
                case_map[case_id] = case
    missing = sorted(case_ids - set(case_map), key=str.casefold)
    if missing:
        status = "NA_missing_case_metadata"
        return _na_metric_cards(status), {
            "status": status,
            "case_sources": [
                str(path) for path in sorted(source_paths, key=lambda value: str(value).casefold())
            ],
            "missing_case_ids": missing,
        }

    try:
        formal = compute_metrics(
            [deepcopy(dict(row)) for row in logs],
            [case_map[case_id] for case_id in sorted(case_map, key=str.casefold)],
            label="dashboard_filtered_slice",
            strict_labels=True,
            include_missing=False,
        )
    except (TypeError, ValueError) as exc:
        status = "NA_runlog_recompute_error"
        return _na_metric_cards(status), {
            "status": status,
            "case_sources": [
                str(path) for path in sorted(source_paths, key=lambda value: str(value).casefold())
            ],
            "error": str(exc),
        }

    cards: dict[str, dict[str, Any]] = {}
    for metric in PROPORTION_METRICS:
        cards[metric] = {
            "value": parse_optional_number(formal.get(metric)),
            "numerator": parse_optional_number(formal.get(f"{metric}_numerator")),
            "denominator": parse_optional_number(formal.get(f"{metric}_denominator")),
            "ci_low": parse_optional_number(formal.get(f"{metric}_ci_low")),
            "ci_high": parse_optional_number(formal.get(f"{metric}_ci_high")),
            "status": "recomputed_from_selected_runlogs",
            "source_group_count": 1,
        }
    return cards, {
        "status": "completed",
        "case_sources": [
            str(path) for path in sorted(source_paths, key=lambda value: str(value).casefold())
        ],
        "case_runs": int(formal.get("case_runs", 0) or 0),
        "runlog_rows": len(logs),
        "data_quality_warnings": list(formal.get("data_quality_warnings", [])),
    }


def runlog_slice_fingerprint(logs: Sequence[Mapping[str, Any]]) -> str:
    """返回已加载仪表盘切片的内容绑定标识指纹。"""

    digest = hashlib.sha256()
    identities = sorted(
        (
            _string(row.get("source_path")),
            _string(row.get("replay_key")) or _string(row.get("run_key")),
            int(parse_optional_number(row.get("step")) or 0),
            _string(row.get("case_source")),
        )
        for row in logs
    )
    for identity in identities:
        digest.update(json.dumps(identity, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _cached_dashboard_metric_cards(
    st: Any,
    logs: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """在当前 Streamlit 会话中仅缓存小型派生 KPI 指标卡片。"""

    fingerprint = runlog_slice_fingerprint(logs)
    state_key = "_m3_filtered_metric_card_cache_v1"
    if state_key not in st.session_state:
        st.session_state[state_key] = {}
    cache = st.session_state[state_key]
    if fingerprint in cache:
        cards, provenance = cache[fingerprint]
        result_provenance = deepcopy(provenance)
        result_provenance["cache_hit"] = True
        return deepcopy(cards), result_provenance

    cards, provenance = recompute_metric_cards_from_logs(logs)
    cache[fingerprint] = (deepcopy(cards), deepcopy(provenance))
    while len(cache) > 24:
        cache.pop(next(iter(cache)))
    result_provenance = deepcopy(provenance)
    result_provenance["cache_hit"] = False
    return cards, result_provenance


def _recomputed_breakdown_rows(
    st: Any,
    logs: Sequence[Mapping[str, Any]],
    *,
    dimension: str,
    selected_batch: str = "",
) -> list[dict[str, Any]]:
    """基于相同的已过滤 RunLog 证据构建维度拆解行。"""

    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in logs:
        value = selected_batch if dimension == "experiment_batch" else _string(row.get(dimension))
        if value:
            groups[value].append(row)
    output: list[dict[str, Any]] = []
    for value in sorted(groups, key=str.casefold):
        cards, provenance = _cached_dashboard_metric_cards(st, groups[value])
        if provenance.get("status") != "completed":
            continue
        record: dict[str, Any] = {dimension: value}
        for metric in PROPORTION_METRICS:
            card = cards[metric]
            record[metric] = card["value"]
            record[f"{metric}_ci_low"] = card["ci_low"]
            record[f"{metric}_ci_high"] = card["ci_high"]
            record[f"{metric}_denominator"] = card["denominator"]
        output.append(record)
    return output


def build_breakdown_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    dimension: str,
    metrics: Sequence[str] = PROPORTION_METRICS,
) -> list[dict[str, Any]]:
    """从包含计数的不相交记录中聚合每个可见维度切片。"""

    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in select_nonoverlapping_metric_rows(rows):
        value = _string(row.get(dimension))
        if value:
            groups[value].append(row)
    output: list[dict[str, Any]] = []
    for value in sorted(groups, key=str.casefold):
        cards = aggregate_metric_cards(groups[value], metrics)
        record: dict[str, Any] = {dimension: value}
        for metric in metrics:
            card = cards[metric]
            record[metric] = card["value"]
            record[f"{metric}_ci_low"] = card["ci_low"]
            record[f"{metric}_ci_high"] = card["ci_high"]
            record[f"{metric}_denominator"] = card["denominator"]
        output.append(record)
    return output


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    finite = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not finite:
        return None
    if len(finite) == 1:
        return finite[0]
    position = (len(finite) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    return finite[lower] + (finite[upper] - finite[lower]) * (position - lower)


def summarize_latencies(
    logs: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, dict[str, Any]]:
    """汇总原始延迟时间，并在缺失时回退至报告的包级汇总。"""

    guard_values = [
        value
        for row in logs
        if (value := parse_optional_number(row.get("guard_latency_ms"))) is not None
    ]
    latest_by_run: dict[str, tuple[int, Mapping[str, Any]]] = {}
    for row in logs:
        key = _string(row.get("replay_key")) or _string(row.get("run_key"))
        step = int(parse_optional_number(row.get("step")) or 0)
        if key not in latest_by_run or step >= latest_by_run[key][0]:
            latest_by_run[key] = (step, row)
    case_values = [
        value
        for _, row in latest_by_run.values()
        if (
            value := parse_optional_number(
                row.get("case_latency_ms") or row.get("case_total_ms")
            )
        )
        is not None
    ]
    result = {
        "GuardLatencyP50": {
            "value": _percentile(guard_values, 0.50),
            "status": "raw_step_logs" if guard_values else "NA",
            "observations": len(guard_values),
        },
        "GuardLatencyP95": {
            "value": _percentile(guard_values, 0.95),
            "status": "raw_step_logs" if guard_values else "NA",
            "observations": len(guard_values),
        },
        "CaseLatencyP50": {
            "value": _percentile(case_values, 0.50),
            "status": "raw_case_runs" if case_values else "NA",
            "observations": len(case_values),
        },
        "CaseLatencyP95": {
            "value": _percentile(case_values, 0.95),
            "status": "raw_case_runs" if case_values else "NA",
            "observations": len(case_values),
        },
    }
    if guard_values or case_values:
        return result
    for metric in LATENCY_METRICS:
        reported = [
            value
            for row in select_nonoverlapping_metric_rows(metric_rows)
            if (value := parse_optional_number(row.get(metric))) is not None
        ]
        if reported:
            result[metric] = {
                "value": median(reported),
                "status": "median_of_reported_metric_groups",
                "observations": len(reported),
            }
    return result


def evidence_layer_summary(
    metrics: Sequence[Mapping[str, Any]],
    logs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metric_counts = Counter(_string(row.get("evidence_layer")) for row in metrics)
    log_counts = Counter(_string(row.get("evidence_layer")) for row in logs)
    layers = sorted(set(metric_counts) | set(log_counts), key=str.casefold)
    return [
        {
            "evidence_layer": layer,
            "label": EVIDENCE_LABELS.get(layer, layer),
            "metric_rows": metric_counts[layer],
            "runlog_steps": log_counts[layer],
            "formal_claim_eligible": layer == "formal_real_model",
        }
        for layer in layers
        if layer
    ]


def redact_sensitive_text(value: Any) -> str:
    """对凭证类文本进行脱敏脱除，同时保留用于诊断的原因标签。"""

    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = OPENAI_KEY_RE.sub("<redacted-api-key>", text)
    text = BEARER_RE.sub("Bearer <redacted-token>", text)
    text = CANARY_RE.sub("<redacted-synthetic-canary>", text)
    text = SENSITIVE_KEY_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text)
    return text


def _safe_tool_call(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"tool": "unparsed", "arguments": "<not-available>"}
    tool = _string(value.get("tool"))
    arguments = value.get("arguments") if isinstance(value.get("arguments"), Mapping) else {}
    if tool in {"read_file", "write_file"}:
        path = _string(arguments.get("path") or arguments.get("file")).replace("\\", "/")
        safe = path.casefold().startswith("sandbox/") and ".." not in path
        return {"tool": tool, "arguments": {"path": path if safe else "<redacted-non-sandbox-path>"}}
    if tool == "send_email":
        address = _string(arguments.get("to"))
        safe = address.casefold().endswith(".test")
        return {"tool": tool, "arguments": {"to": address if safe else "<redacted-recipient>"}}
    if tool == "call_api":
        endpoint = _string(arguments.get("endpoint"))
        safe = endpoint.casefold().startswith("/mock/")
        return {"tool": tool, "arguments": {"endpoint": endpoint if safe else "<redacted-endpoint>"}}
    if tool == "run_code":
        return {"tool": tool, "arguments": "<redacted-code>"}
    if tool == "final":
        return {"tool": tool, "arguments": "<final-output-redacted>"}
    return {"tool": tool or "unknown", "arguments": "<redacted-arguments>"}


def _safe_guard_trace(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
            rows.append(
                {
                    "module": _string(item.get("module") or item.get("name")),
                    "decision": _string(item.get("decision")),
                    "risk": parse_optional_number(item.get("risk")),
                    "latency_ms": parse_optional_number(item.get("latency_ms")),
                    "reasons": [redact_sensitive_text(reason) for reason in reasons],
                }
            )
        elif item:
            rows.append(
                {
                    "module": redact_sensitive_text(item),
                    "decision": "",
                    "risk": None,
                    "latency_ms": None,
                    "reasons": [],
                }
            )
    return rows


def sanitize_runlog_for_replay(row: Mapping[str, Any]) -> dict[str, Any]:
    """返回白名单允许的重放记录，并剔除模型输入和数值数据。"""

    reasons = row.get("reasons") if isinstance(row.get("reasons"), list) else []
    observation = _string(row.get("observation"))
    if observation in {"BLOCKED_BY_M3_GUARD", "NEED_HUMAN_CONFIRMATION_DEFAULT_REJECT"}:
        observation_status = observation
    elif observation.upper().startswith("ERROR"):
        observation_status = "ERROR_REDACTED"
    elif observation:
        observation_status = "TOOL_OUTPUT_REDACTED"
    else:
        observation_status = ""
    return {
        "replay_key": _string(row.get("replay_key")) or _string(row.get("run_key")),
        "run_key": _string(row.get("run_key")),
        "run_id": _string(row.get("run_id")),
        "case_id": _string(row.get("case_id")),
        "step": int(parse_optional_number(row.get("step")) or 0),
        "experiment_batch": _string(row.get("experiment_batch")),
        "evidence_layer": _string(row.get("evidence_layer")),
        "model": _string(row.get("model")),
        "defense_condition": _string(row.get("defense_condition")),
        "attack_family": _string(row.get("attack_family")),
        "language": _string(row.get("language")),
        "sample_type": _string(row.get("sample_type")),
        "parsed_tool_call": _safe_tool_call(row.get("parsed_tool_call")),
        "parse_ok": row.get("parse_ok") if isinstance(row.get("parse_ok"), bool) else None,
        "parse_error_type": "present_redacted" if row.get("parse_error") else "",
        "guard_decision": _string(row.get("guard_decision")),
        "risk_score": parse_optional_number(row.get("risk_score")),
        "reasons": [redact_sensitive_text(reason) for reason in reasons],
        "guard_modules": _json_list(row.get("guard_modules")),
        "guard_trace": _safe_guard_trace(row.get("guard_trace") or row.get("module_trace")),
        "observation_status": observation_status,
        "final_status": _string(row.get("final_status")),
        "timed_out": row.get("timed_out") is True,
        "model_latency_ms": parse_optional_number(row.get("model_latency_ms")),
        "guard_latency_ms": parse_optional_number(row.get("guard_latency_ms")),
        "tool_latency_ms": parse_optional_number(row.get("tool_latency_ms")),
        "total_latency_ms": parse_optional_number(
            row.get("total_latency_ms") or row.get("step_total_ms")
        ),
        "case_latency_ms": parse_optional_number(
            row.get("case_latency_ms") or row.get("case_total_ms")
        ),
        "payload_redacted": any(
            key in row
            for key in (
                "raw_model_output",
                "model_input",
                "runtime_model_input",
                "prompt",
                "messages",
                "observation",
            )
        ),
    }


def select_replay(
    logs: Sequence[Mapping[str, Any]],
    *,
    run_key: str = "",
    case_id: str = "",
) -> list[dict[str, Any]]:
    """选择并净化完整的重放标识或用例 ID 攻击链。"""

    if not run_key and not case_id:
        return []
    selected = [
        row
        for row in logs
        if (
            run_key
            and (_string(row.get("replay_key")) or _string(row.get("run_key"))) == run_key
        )
        or (not run_key and case_id and _string(row.get("case_id")) == case_id)
    ]
    selected.sort(
        key=lambda row: (
            _string(row.get("replay_key")) or _string(row.get("run_key")),
            int(parse_optional_number(row.get("step")) or 0),
        )
    )
    return [sanitize_runlog_for_replay(row) for row in selected]


def replay_options(logs: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    return {
        "run_keys": sorted(
            {
                _string(row.get("replay_key")) or _string(row.get("run_key"))
                for row in logs
                if _string(row.get("replay_key")) or _string(row.get("run_key"))
            }
        ),
        "case_ids": sorted({_string(row.get("case_id")) for row in logs if _string(row.get("case_id"))}),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object at {path}:{line_number}")
            records.append(value)
    return records


def _declared_artifact_path(reference: str, *, bundle_dir: Path) -> Path | None:
    raw = Path(reference)
    candidates = [raw] if raw.is_absolute() else [REPO_ROOT / raw, bundle_dir / raw]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


def _verify_figure_manifest_anchor(
    manifest: Mapping[str, Any],
    *,
    bundle_dir: Path,
    figure_manifest_path: Path,
) -> str | None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return "figure bundle is not anchored by a main manifest artifact list"
    target = figure_manifest_path.resolve()
    matches: list[Mapping[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or artifact.get("kind") != "figure_manifest":
            continue
        resolved = _declared_artifact_path(_string(artifact.get("path")), bundle_dir=bundle_dir)
        if resolved == target:
            matches.append(artifact)
    if len(matches) != 1:
        return f"main manifest must declare exactly one figure_manifest artifact; found {len(matches)}"
    record = matches[0]
    declared_bytes = record.get("bytes")
    declared_sha = _string(record.get("sha256"))
    if isinstance(declared_bytes, bool) or not isinstance(declared_bytes, int):
        return "main manifest figure_manifest artifact has invalid bytes"
    actual_bytes = target.stat().st_size
    if declared_bytes != actual_bytes:
        return (
            "main manifest figure_manifest byte-size mismatch: "
            f"expected {declared_bytes}, got {actual_bytes}"
        )
    actual_sha = sha256_file(target)
    if declared_sha != actual_sha:
        return "main manifest figure_manifest SHA-256 mismatch"
    return None


def _load_figure_bundle(
    bundle_dir: Path,
    manifest: Mapping[str, Any],
    *,
    batch: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    figure_manifest_path = bundle_dir / FIGURE_MANIFEST_FILENAME
    if not figure_manifest_path.exists():
        return [], []
    anchor_problem = _verify_figure_manifest_anchor(
        manifest,
        bundle_dir=bundle_dir,
        figure_manifest_path=figure_manifest_path,
    )
    if anchor_problem:
        return [], [f"{bundle_dir}: {anchor_problem}"]
    expected_experiment = _string(manifest.get("experiment_id")) or None
    try:
        verified = load_figure_manifest(
            figure_manifest_path,
            expected_experiment_id=expected_experiment,
        )
    except FigureManifestError as exc:
        return [], [f"{figure_manifest_path}: {exc}"]
    figures: list[dict[str, Any]] = []
    for figure in verified["figures"]:
        files = figure["files"]
        evidence_tier = verified["evidence_tier"]
        figures.append(
            {
                "bundle": batch,
                "experiment_batch": verified["experiment_id"],
                "status": _string(manifest.get("status")) or "unknown",
                "evidence_tier": evidence_tier,
                "evidence_layer": derive_evidence_layer(
                    {
                        "experiment_id": verified["experiment_id"],
                        "evidence_tier": evidence_tier,
                    },
                    source=str(figure_manifest_path),
                ),
                "figure_id": figure["id"],
                "title": figure["title"],
                "role": figure["role"],
                "order": figure["order"],
                "chart_type": figure["chart_type"],
                "caption": figure["caption"],
                "metrics": list(figure["metrics"]),
                "grain": list(figure["grain"]),
                "uncertainty": deepcopy(figure["uncertainty"]),
                "warnings": list(figure["warnings"]),
                "data_path": files["data"]["resolved_path"],
                "png_path": files["png"]["resolved_path"],
                "svg_path": files["svg"]["resolved_path"],
                "source": str(figure_manifest_path),
            }
        )
    figures.sort(key=lambda row: (str(row["experiment_batch"]), int(row["order"]), str(row["figure_id"])))
    return figures, []


def _resolve_reference(reference: str, *, anchors: Sequence[Path]) -> Path | None:
    candidate = Path(reference)
    candidates = [candidate] if candidate.is_absolute() else [anchor / candidate for anchor in anchors]
    for value in candidates:
        resolved = value.resolve()
        if resolved.is_file():
            return resolved
    return None


def _discover_bundle_dirs(paths: Sequence[str | Path]) -> list[Path]:
    result: set[Path] = set()
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file():
            result.add(path.parent)
        elif path.is_dir() and (
            (path / "metrics.csv").exists()
            or (path / "analysis.md").exists()
            or (path / "raw_run_index.json").exists()
            or (path / FIGURE_MANIFEST_FILENAME).exists()
        ):
            result.add(path)
        elif path.is_dir():
            for manifest_path in path.rglob("manifest.json"):
                bundle = manifest_path.parent
                if (
                    (bundle / "analysis.md").exists()
                    or (bundle / "metrics.csv").exists()
                    or (bundle / FIGURE_MANIFEST_FILENAME).exists()
                ):
                    result.add(bundle)
        else:
            raise FileNotFoundError(path)
    return sorted(result, key=lambda value: str(value).casefold())


def _expand_files(paths: Sequence[str | Path], pattern: str) -> list[Path]:
    result: set[Path] = set()
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file():
            result.add(path)
        elif path.is_dir():
            result.update(item.resolve() for item in path.rglob(pattern) if item.is_file())
        else:
            raise FileNotFoundError(path)
    return sorted(result, key=lambda value: str(value).casefold())


def _load_referenced_logs(
    index: Mapping[str, Any],
    *,
    bundle_dir: Path,
    batch_hint: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    logs: list[dict[str, Any]] = []
    warnings: list[str] = []
    records = index.get("records") if isinstance(index.get("records"), list) else []
    program_root = Path(_string(index.get("program_root"))) if index.get("program_root") else REPO_ROOT
    anchors = (REPO_ROOT, program_root, bundle_dir)
    for record in records:
        if not isinstance(record, Mapping):
            continue
        kind = _string(record.get("kind"))
        if kind not in {"formal_raw_log", "smoke_gate_raw_log", "run_log"}:
            continue
        reference = _string(record.get("path"))
        path = _resolve_reference(reference, anchors=anchors)
        if path is None:
            warnings.append(f"missing referenced RunLog: {reference}")
            continue
        evidence_hint = "smoke_gate" if kind == "smoke_gate_raw_log" else _string(record.get("evidence_tier"))
        for row in _read_jsonl(path):
            logs.append(
                normalize_log_record(
                    row,
                    source=str(path),
                    batch_hint=batch_hint,
                    batch_aliases=(batch_hint,) if batch_hint else (),
                    evidence_hint=evidence_hint,
                )
            )
    return logs, warnings


def _load_matrix_manifest_logs(
    payload: Mapping[str, Any],
    *,
    manifest_path: Path,
    batch_hint: str,
    batch_aliases: Sequence[str] = (),
) -> tuple[list[dict[str, Any]], list[str]]:
    logs: list[dict[str, Any]] = []
    warnings: list[str] = []
    entries: list[Mapping[str, Any]] = []
    for field in ("results", "conditions"):
        values = payload.get(field)
        if isinstance(values, list):
            entries.extend(item for item in values if isinstance(item, Mapping))
    seen: set[Path] = set()
    for entry in entries:
        reference = _string(entry.get("jsonl"))
        if not reference:
            continue
        path = _resolve_reference(reference, anchors=(REPO_ROOT, manifest_path.parent))
        if path is None:
            warnings.append(f"missing program RunLog: {reference}")
            continue
        if path in seen:
            continue
        seen.add(path)
        for row in _read_jsonl(path):
            logs.append(
                normalize_log_record(
                    row,
                    source=str(path),
                    batch_hint=batch_hint,
                    batch_aliases=batch_aliases,
                    evidence_hint=_string(payload.get("evidence_tier")),
                )
            )
    return logs, warnings


def _program_job_experiment_batches(
    stage_name: str,
    job: Mapping[str, Any],
) -> tuple[str, ...]:
    """将一个物理程序作业映射到其所支持的公开实验批次。"""

    stage = _string(stage_name).casefold()
    job_id = _string(job.get("job_id")).casefold()
    if stage == "main":
        return MAIN_STAGE_EXPERIMENTS
    if stage == "ablation":
        return ("E4",)
    if stage == "stability":
        return ("E15",)
    if stage in {"validation-baseline", "validation_baseline"}:
        return ("E13",)
    if stage == "derived":
        match = re.search(r"(?:^|__)e(?P<number>\d+)(?:__|$)", job_id)
        if match:
            return (f"E{int(match.group('number'))}",)
    if stage == "smoke":
        return ("smoke",)
    if stage == "stub":
        return ("stub",)
    return (_string(stage_name),) if _string(stage_name) else ()


def _deduplicate_logs(logs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, int], int] = {}
    for row in logs:
        key = (
            _string(row.get("source_path")),
            _string(row.get("run_key")),
            int(parse_optional_number(row.get("step")) or 0),
        )
        if key not in seen:
            result.append(deepcopy(dict(row)))
            seen[key] = len(result) - 1
            continue
        existing = result[seen[key]]
        merged_batches = {
            _string(value)
            for source in (existing.get("experiment_batches"), row.get("experiment_batches"))
            if isinstance(source, Sequence) and not isinstance(source, (str, bytes))
            for value in source
            if _string(value)
        }
        if merged_batches:
            existing["experiment_batches"] = sorted(merged_batches, key=str.casefold)
    return result


def load_dashboard_sources(
    *,
    bundle_paths: Sequence[str | Path] = (),
    program_manifest_paths: Sequence[str | Path] = (),
    log_paths: Sequence[str | Path] = (),
    metric_paths: Sequence[str | Path] = (),
) -> dict[str, Any]:
    """将支持的本地构件加载为统一规范的仪表盘数据模型。"""

    metrics: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    warnings: list[str] = []

    for bundle_dir in _discover_bundle_dirs(bundle_paths):
        manifest_path = bundle_dir / "manifest.json"
        manifest: dict[str, Any] = {}
        if manifest_path.exists():
            manifest = _read_json(manifest_path)
            manifests.extend(normalize_manifest_records(manifest, source=str(manifest_path)))
        batch = _string(manifest.get("experiment_id")) or bundle_dir.name
        metric_candidates = [
            path
            for path in (
                bundle_dir / "metrics.csv",
                bundle_dir / "historical_metrics.csv",
                bundle_dir / "round_metrics.csv",
            )
            if path.exists()
        ]
        loaded_metric_count = 0
        for metric_path in metric_candidates:
            for source_row in _read_csv(metric_path):
                row: dict[str, Any] = dict(source_row)
                if metric_path.name == "round_metrics.csv":
                    row.update(
                        {
                            "experiment_id": batch,
                            "scope": "adaptive_round",
                            "model": (
                                manifest.get("plan", {}).get("model", "")
                                if isinstance(manifest.get("plan"), Mapping)
                                else ""
                            ),
                            "condition_id": "e16_normal_full",
                            "prompt_profile": "normal",
                            "guard_mode": "full_guard",
                            "ASR": row.get("asr"),
                            "ASR_numerator": row.get("successes"),
                            "ASR_denominator": row.get("denominator"),
                            "ASR_ci_low": row.get("ci_low"),
                            "ASR_ci_high": row.get("ci_high"),
                        }
                    )
                metrics.append(
                    normalize_metric_record(
                        row,
                        source=str(metric_path),
                        batch_hint=batch,
                        evidence_hint=_string(manifest.get("evidence_tier")),
                    )
                )
                loaded_metric_count += 1
        raw_index_path = bundle_dir / "raw_run_index.json"
        if raw_index_path.exists():
            referenced, issues = _load_referenced_logs(
                _read_json(raw_index_path), bundle_dir=bundle_dir, batch_hint=batch
            )
            logs.extend(referenced)
            warnings.extend(issues)
        bundle_figures, figure_issues = _load_figure_bundle(
            bundle_dir,
            manifest,
            batch=batch,
        )
        figures.extend(bundle_figures)
        warnings.extend(figure_issues)
        bundles.append(
            {
                "bundle": batch,
                "path": str(bundle_dir),
                "status": _string(manifest.get("status")) or "unknown",
                "metrics_loaded": loaded_metric_count,
                "figures_loaded": len(bundle_figures),
                "analysis_available": (bundle_dir / "analysis.md").is_file(),
            }
        )

    for metric_path in _expand_files(metric_paths, "*.csv"):
        for row in _read_csv(metric_path):
            metrics.append(
                normalize_metric_record(
                    row,
                    source=str(metric_path),
                    batch_hint=metric_path.parent.name,
                )
            )

    for log_path in _expand_files(log_paths, "*.jsonl"):
        for row in _read_jsonl(log_path):
            logs.append(
                normalize_log_record(
                    row,
                    source=str(log_path),
                    batch_hint=log_path.parent.name,
                )
            )

    for manifest_path in _expand_files(program_manifest_paths, "*manifest.json"):
        payload = _read_json(manifest_path)
        manifests.extend(normalize_manifest_records(payload, source=str(manifest_path)))
        stages = payload.get("stages") if isinstance(payload.get("stages"), Mapping) else {}
        if stages:
            for stage_name, stage_value in stages.items():
                stage = stage_value if isinstance(stage_value, Mapping) else {}
                for job_value in stage.get("jobs", []) if isinstance(stage.get("jobs"), list) else []:
                    if not isinstance(job_value, Mapping):
                        continue
                    reference = _string(job_value.get("result_manifest"))
                    if not reference:
                        continue
                    job_manifest_path = _resolve_reference(reference, anchors=(REPO_ROOT, manifest_path.parent))
                    if job_manifest_path is None:
                        warnings.append(f"missing result manifest: {reference}")
                        continue
                    job_manifest = _read_json(job_manifest_path)
                    batch_aliases = _program_job_experiment_batches(
                        str(stage_name), job_value
                    )
                    job_manifest_rows = normalize_manifest_records(
                        job_manifest, source=str(job_manifest_path)
                    )
                    for row in job_manifest_rows:
                        row["experiment_batches"] = list(batch_aliases)
                    manifests.extend(job_manifest_rows)
                    job_logs, issues = _load_matrix_manifest_logs(
                        job_manifest,
                        manifest_path=job_manifest_path,
                        batch_hint=str(stage_name),
                        batch_aliases=batch_aliases,
                    )
                    logs.extend(job_logs)
                    warnings.extend(issues)
        else:
            program_logs, issues = _load_matrix_manifest_logs(
                payload,
                manifest_path=manifest_path,
                batch_hint=_string(payload.get("run_group") or payload.get("experiment_id")),
            )
            logs.extend(program_logs)
            warnings.extend(issues)

    logs = _deduplicate_logs(logs)
    downgraded = sum(
        _downgrade_superseded_context_records(rows)
        for rows in (metrics, logs, manifests)
    )
    if downgraded:
        warnings.append(
            f"downgraded {downgraded} superseded E9/E14 context records to diagnostic-only"
        )
    return {
        "metrics": metrics,
        "logs": logs,
        "manifests": manifests,
        "bundles": bundles,
        "figures": figures,
        "warnings": sorted(set(warnings)),
    }


def _display_percent(value: Any) -> str:
    numeric = parse_optional_number(value)
    return "NA" if numeric is None else f"{numeric * 100.0:.1f}%"


def _display_metric(value: Any) -> str:
    """旧版评测测试所使用的向下兼容标量格式化工具。"""

    numeric = parse_optional_number(value)
    if numeric is None:
        text = _string(value)
        return (
            "NA"
            if not text or text.casefold() in {"na", "n/a", "none", "null", "nan"}
            else text
        )
    return f"{numeric:.4f}"


def _display_latency(value: Any) -> str:
    numeric = parse_optional_number(value)
    return "NA" if numeric is None else f"{numeric:.1f} ms"


def _metric_help(card: Mapping[str, Any]) -> str:
    if card.get("value") is None:
        return "NA: no compatible non-zero denominator in the selected evidence."
    numerator = card.get("numerator")
    denominator = card.get("denominator")
    interval = (
        f"Wilson 95% CI [{_display_percent(card.get('ci_low'))}, "
        f"{_display_percent(card.get('ci_high'))}]"
        if card.get("ci_low") is not None and card.get("ci_high") is not None
        else "CI unavailable"
    )
    count = "counts unavailable" if numerator is None or denominator is None else f"{numerator:g}/{denominator:g}"
    return f"{count}; {interval}; {card.get('status', '')}"


def _metric_table_rows(cards: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "metric": metric,
            "value": _display_percent(card.get("value")),
            "numerator": card.get("numerator"),
            "denominator": card.get("denominator"),
            "Wilson 95% CI": (
                "NA"
                if card.get("ci_low") is None or card.get("ci_high") is None
                else f"[{_display_percent(card['ci_low'])}, {_display_percent(card['ci_high'])}]"
            ),
            "status": card.get("status"),
        }
        for metric, card in cards.items()
    ]


def _safe_replay_table(replay: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in replay:
        call = item.get("parsed_tool_call") if isinstance(item.get("parsed_tool_call"), Mapping) else {}
        rows.append(
            {
                "replay_key": item.get("replay_key"),
                "run_key": item.get("run_key"),
                "case_id": item.get("case_id"),
                "step": item.get("step"),
                "tool": call.get("tool"),
                "safe_arguments": json.dumps(call.get("arguments"), ensure_ascii=False),
                "decision": item.get("guard_decision"),
                "risk": item.get("risk_score"),
                "status": item.get("final_status"),
                "reasons": " | ".join(str(reason) for reason in item.get("reasons", [])),
                "model_ms": item.get("model_latency_ms"),
                "guard_ms": item.get("guard_latency_ms"),
            }
        )
    return rows


def _apply_sidebar_filters(st: Any, data: Mapping[str, Any]) -> dict[str, list[str]]:
    values = available_filter_values(data["metrics"], data["logs"], data["manifests"])
    formal = "formal_real_model"
    layer_defaults = [formal] if formal in values["evidence_layer"] else values["evidence_layer"]
    selections: dict[str, list[str]] = {}
    selections["evidence_layer"] = st.sidebar.multiselect(
        "Evidence layer / 证据层",
        values["evidence_layer"],
        default=layer_defaults,
        format_func=lambda value: EVIDENCE_LABELS.get(value, value),
    )
    labels = {
        "model": "Model / 模型",
        "defense_condition": "Defense condition / 防御条件",
        "attack_family": "Attack family / 攻击族",
        "language": "Language / 语言",
        "experiment_batch": "Experiment batch / 实验批次",
    }
    layer_filtered = {
        name: apply_filters(data[name], {"evidence_layer": selections["evidence_layer"]})
        for name in ("metrics", "logs", "manifests")
    }
    narrowed = available_filter_values(
        layer_filtered["metrics"], layer_filtered["logs"], layer_filtered["manifests"]
    )
    for field, label in labels.items():
        selections[field] = st.sidebar.multiselect(label, narrowed[field], default=[])
    return selections


def select_static_figures(
    figures: Sequence[Mapping[str, Any]],
    selections: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    """仅根据图表实际代表的维度来过滤包级别的静态图表。"""

    result: list[dict[str, Any]] = []
    for source in figures:
        row = dict(source)
        if selections.get("evidence_layer") and row.get("evidence_layer") not in set(
            selections["evidence_layer"]
        ):
            continue
        if selections.get("experiment_batch") and row.get("experiment_batch") not in set(
            selections["experiment_batch"]
        ):
            continue
        result.append(row)
    return sorted(
        result,
        key=lambda row: (
            str(row.get("experiment_batch", "")),
            int(row.get("order", 0) or 0),
            str(row.get("figure_id", "")),
        ),
    )


def render_figure_bundle_section(st: Any, figures: Sequence[Mapping[str, Any]]) -> None:
    """渲染已验证的静态图表，无需重新实现其底层统计计算。"""

    st.subheader("Experiment figures / 专用实验图")
    st.caption(
        "These hash-verified aggregate figures respond only to evidence-layer and experiment-batch filters. "
        "Use the KPI chart, breakdown table, and replay below for model, defense, attack-family, and language filters."
    )
    if not figures:
        st.info("No verified figure bundle matches the selected evidence layer and experiment batch.")
        return
    for figure in figures:
        experiment = _string(figure.get("experiment_batch"))
        title = _string(figure.get("title"))
        st.markdown(f"#### {experiment} · {title}")
        st.image(
            _string(figure.get("png_path")),
            caption=_string(figure.get("caption")),
            use_container_width=True,
        )
        methods = sorted(
            {
                _string(item.get("method"))
                for item in figure.get("uncertainty", [])
                if isinstance(item, Mapping) and _string(item.get("method"))
            }
        )
        details = [
            f"role={_string(figure.get('role'))}",
            f"chart={_string(figure.get('chart_type'))}",
            f"metrics={','.join(str(value) for value in figure.get('metrics', [])) or 'NA'}",
            f"grain={','.join(str(value) for value in figure.get('grain', [])) or 'NA'}",
        ]
        if methods:
            details.append(f"uncertainty={','.join(methods)}")
        st.caption(" · ".join(details))
        if _string(figure.get("status")) != "completed":
            st.warning(
                f"{experiment}/{figure.get('figure_id')}: bundle status is "
                f"{_string(figure.get('status')) or 'unknown'}"
            )
        for warning in figure.get("warnings", []):
            st.warning(f"{experiment}/{figure.get('figure_id')}: {warning}")


def render_dashboard(st: Any, data: Mapping[str, Any]) -> None:
    """渲染 Streamlit 仪表盘页面；与命令行加载逻辑解耦隔离。"""

    st.title("M3_PI_Guard — Final Evidence Dashboard")
    st.caption(
        "Formal real-model evidence is isolated from Stub regression, smoke gates, and historical diagnostics. "
        "Undefined metrics remain NA; they are never replaced with zero."
    )
    selections = _apply_sidebar_filters(st, data)
    metric_rows = apply_filters(data["metrics"], selections)
    logs = apply_filters(data["logs"], selections)
    manifests = apply_filters(data["manifests"], selections)

    layers = evidence_layer_summary(data["metrics"], data["logs"])
    st.subheader("Evidence coverage / 证据分层")
    st.dataframe(layers, use_container_width=True, hide_index=True)
    selected_layers = set(selections.get("evidence_layer", []))
    if selected_layers - {"formal_real_model"}:
        st.warning(
            "The selected view includes diagnostic-only evidence. Stub, smoke, and historical rows must not be "
            "used for formal effect claims."
        )
    for warning in data.get("warnings", []):
        st.warning(warning)

    figure_rows = select_static_figures(data.get("figures", []), selections)
    render_figure_bundle_section(st, figure_rows)

    selected_batches = list(selections.get("experiment_batch", []))
    if len(selected_batches) == 1:
        cards, card_provenance = _cached_dashboard_metric_cards(st, logs)
    else:
        status = "NA_select_exactly_one_experiment_batch"
        cards = _na_metric_cards(status)
        card_provenance = {"status": status, "case_sources": []}
    st.subheader("Safety and utility KPIs / 核心指标")
    if card_provenance.get("status") == "completed":
        st.caption(
            "KPIs and the bar chart are recomputed from the exact filtered RunLog slice using the frozen case "
            f"metadata ({card_provenance.get('case_runs', 0)} logical runs; "
            f"{card_provenance.get('runlog_rows', 0)} step rows; "
            f"cache={'hit' if card_provenance.get('cache_hit') else 'miss'})."
        )
        for warning in card_provenance.get("data_quality_warnings", []):
            st.warning(f"Filtered KPI recomputation: {warning}")
    elif len(selected_batches) != 1:
        st.info(
            "Select exactly one experiment batch to compute KPIs. Cross-batch pooling is disabled because "
            "several experiments reuse the same RunLogs or use independent denominators."
        )
    else:
        st.warning(
            "KPIs are NA for this filtered slice because the frozen case metadata required for exact RunLog "
            f"recomputation is unavailable ({card_provenance.get('status')})."
        )
    for start in range(0, len(PROPORTION_METRICS), 3):
        columns = st.columns(min(3, len(PROPORTION_METRICS) - start))
        for column, metric in zip(columns, PROPORTION_METRICS[start : start + 3]):
            card = cards[metric]
            column.metric(metric, _display_percent(card.get("value")), help=_metric_help(card))
    st.dataframe(_metric_table_rows(cards), use_container_width=True, hide_index=True)

    chart_rows = [
        {"metric": metric, "percent": card["value"] * 100.0}
        for metric, card in cards.items()
        if card.get("value") is not None
    ]
    if chart_rows:
        st.vega_lite_chart(
            {"values": chart_rows},
            {
                "mark": {"type": "bar", "color": "#4C78A8"},
                "encoding": {
                    "x": {
                        "field": "metric",
                        "type": "nominal",
                        "sort": list(PROPORTION_METRICS),
                        "axis": {"title": None},
                    },
                    "y": {
                        "field": "percent",
                        "type": "quantitative",
                        "scale": {"domain": [0, 100]},
                        "axis": {"title": "Percent", "format": ".1f"},
                    },
                    "tooltip": [
                        {"field": "metric", "type": "nominal", "title": "Metric"},
                        {
                            "field": "percent",
                            "type": "quantitative",
                            "title": "Percent",
                            "format": ".2f",
                        },
                    ],
                },
            },
            use_container_width=True,
        )
    else:
        st.info("No compatible metric denominators for the selected filters; KPIs are NA.")

    latency = summarize_latencies(logs, metric_rows)
    st.subheader("Latency / 延迟")
    latency_columns = st.columns(4)
    for column, metric in zip(latency_columns, LATENCY_METRICS):
        summary = latency[metric]
        column.metric(
            metric,
            _display_latency(summary.get("value")),
            help=f"{summary.get('status')}; observations={summary.get('observations', 0)}",
        )

    st.subheader("Metric breakdown / 分组指标")
    dimension = st.selectbox(
        "Breakdown dimension",
        ("attack_family", "language", "model", "defense_condition", "experiment_batch"),
    )
    if len(selected_batches) == 1 and logs:
        breakdown = _recomputed_breakdown_rows(
            st,
            logs,
            dimension=dimension,
            selected_batch=selected_batches[0],
        )
        st.caption("Breakdown rows are recomputed from the exact filtered RunLog slice.")
    else:
        breakdown = build_breakdown_rows(metric_rows, dimension=dimension)
    if breakdown:
        st.dataframe(breakdown, use_container_width=True, hide_index=True)
    else:
        st.info(f"No `{dimension}` metric grain is available for the selected evidence.")

    st.subheader("Experiment registry / 实验注册表")
    if manifests:
        st.dataframe(manifests, use_container_width=True, hide_index=True)
    else:
        st.info("No manifest rows match the selected filters.")

    st.subheader("Safe RunLog replay / 原始攻击链回放")
    st.caption(
        "Replay includes every selected step and Guard module trace. Runtime model input, raw model output, "
        "tool observations, code, and non-sandbox/non-mock targets are redacted."
    )
    options = replay_options(logs)
    if not options["run_keys"] and not options["case_ids"]:
        st.info("No RunLog records match the selected filters.")
        return
    mode = st.radio("Replay key", ("replay_key", "case_id"), horizontal=True)
    if mode == "replay_key":
        selected_run = st.selectbox("replay_key", options["run_keys"])
        replay = select_replay(logs, run_key=selected_run)
    else:
        selected_case = st.selectbox("case_id", options["case_ids"])
        replay = select_replay(logs, case_id=selected_case)
    st.dataframe(_safe_replay_table(replay), use_container_width=True, hide_index=True)
    for item in replay:
        label = (
            f"{item['replay_key']} · step {item['step']} · "
            f"{item['guard_decision'] or 'no decision'} · {item['final_status'] or 'no status'}"
        )
        with st.expander(label):
            st.json(item)
            trace = item.get("guard_trace", [])
            if trace:
                st.markdown("**Guard module trace**")
                st.dataframe(trace, use_container_width=True, hide_index=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M3_PI_Guard final evidence dashboard")
    parser.add_argument("--bundle", action="append", default=[], help="Analysis bundle directory; repeatable")
    parser.add_argument("--program-manifest", action="append", default=[], help="Program/matrix manifest JSON; repeatable")
    parser.add_argument("--logs", action="append", default=[], help="RunLog JSONL file/directory; repeatable")
    parser.add_argument("--metrics", action="append", default=[], help="Metric CSV file/directory; repeatable")
    args = parser.parse_args(argv)
    if not any((args.bundle, args.program_manifest, args.logs, args.metrics)):
        parser.error("provide at least one --bundle, --program-manifest, --logs, or --metrics source")

    import streamlit as st

    # Streamlit requires this to be the first Streamlit API call.  In
    # particular, it must precede the cache_data decorator below.
    st.set_page_config(page_title="M3_PI_Guard Evidence Dashboard", layout="wide")

    @st.cache_data(show_spinner="Loading and validating local experiment evidence...")
    def cached_load_dashboard_sources(
        bundle_paths: tuple[str, ...],
        program_manifest_paths: tuple[str, ...],
        log_paths: tuple[str, ...],
        metric_paths: tuple[str, ...],
    ) -> dict[str, Any]:
        return load_dashboard_sources(
            bundle_paths=bundle_paths,
            program_manifest_paths=program_manifest_paths,
            log_paths=log_paths,
            metric_paths=metric_paths,
        )

    data = cached_load_dashboard_sources(
        tuple(args.bundle),
        tuple(args.program_manifest),
        tuple(args.logs),
        tuple(args.metrics),
    )

    render_dashboard(st, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
