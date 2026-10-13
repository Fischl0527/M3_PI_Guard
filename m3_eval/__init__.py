"""M3_PI_Guard 评测与统计分析包。

包含攻击防御指标计算（metrics）、无外部依赖的高级统计方法（statistics: Wilson, Newcombe, Bootstrap, Holm）、
可视化看板（dashboard）以及论文专用指标生成工具。
"""

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
