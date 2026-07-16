"""Evaluation and statistical helpers for M3_PI_Guard run logs."""

from .metrics import compare_runs, compute_metrics, load_jsonl, summarize_logs
from .statistics import (
    clustered_paired_bootstrap,
    holm_adjust,
    latency_summary,
    mcnemar_exact,
    wilcoxon_signed_rank,
    wilson_interval,
)

__all__ = [
    "clustered_paired_bootstrap",
    "compare_runs",
    "compute_metrics",
    "holm_adjust",
    "latency_summary",
    "load_jsonl",
    "mcnemar_exact",
    "summarize_logs",
    "wilcoxon_signed_rank",
    "wilson_interval",
]
