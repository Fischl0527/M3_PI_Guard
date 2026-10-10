"""Dependency-free statistical helpers for M3_PI_Guard experiments.

The functions in this module deliberately return plain dictionaries so their
results can be written directly to experiment manifests and JSON reports.
"""

from __future__ import annotations

# 比例同时返回分子、分母与区间。分母为零是未定义，不是观察到零风险。
# 调用方须先处理未知和失败；本模块不会替实验决定哪些记录应进入分母。
import math
import random
from collections import defaultdict
from statistics import NormalDist, mean, median
from typing import Any, Iterable, Sequence


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    """Return a proportion, or ``None`` when its denominator is zero."""

    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def wilson_interval(
    successes: int,
    total: int,
    *,
    confidence: float = 0.95,
) -> tuple[float | None, float | None]:
    """Wilson score interval for a binomial proportion.

    A zero denominator is undefined and therefore returns ``(None, None)``;
    callers must not turn that state into a numeric zero.
    """

    if total < 0 or successes < 0 or successes > total:
        raise ValueError("require 0 <= successes <= total")
    if total == 0:
        return None, None
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")

    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(p * (1.0 - p) / total + z2 / (4.0 * total * total))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def proportion_result(
    numerator: int,
    denominator: int,
    *,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Return counts, value, and Wilson interval for a proportion."""

    low, high = wilson_interval(numerator, denominator, confidence=confidence)
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "value": safe_ratio(numerator, denominator),
        "ci_low": low,
        "ci_high": high,
        "confidence": confidence,
    }


def percentile(values: Iterable[float], q: float) -> float | None:
    """Linear-interpolated percentile with an explicit empty-data state."""

    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def latency_summary(values: Iterable[float]) -> dict[str, Any]:
    """Validate and summarize a non-negative latency sample."""

    sample = [float(value) for value in values]
    if any(not math.isfinite(value) or value < 0.0 for value in sample):
        raise ValueError("latencies must be finite and non-negative")
    return {
        "count": len(sample),
        "mean": mean(sample) if sample else None,
        "median": median(sample) if sample else None,
        "p50": percentile(sample, 0.50),
        "p95": percentile(sample, 0.95),
    }


def mcnemar_exact(
    baseline: Sequence[bool] | None = None,
    treatment: Sequence[bool] | None = None,
    *,
    baseline_only_success: int | None = None,
    treatment_only_success: int | None = None,
) -> dict[str, Any]:
    """Two-sided exact McNemar test using the discordant-pair binomial test.

    Pass either two equally-sized boolean sequences, or the two discordant
    counts explicitly. A ``True`` value denotes the measured event (for
    example, attack success), not whether the result is desirable.
    """

    if baseline is not None or treatment is not None:
        if baseline is None or treatment is None:
            raise ValueError("baseline and treatment must be provided together")
        if len(baseline) != len(treatment):
            raise ValueError("paired samples must have equal length")
        b = sum(bool(left) and not bool(right) for left, right in zip(baseline, treatment))
        c = sum(not bool(left) and bool(right) for left, right in zip(baseline, treatment))
        pair_count = len(baseline)
    else:
        if baseline_only_success is None or treatment_only_success is None:
            raise ValueError("discordant counts are required")
        b = int(baseline_only_success)
        c = int(treatment_only_success)
        pair_count = None
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")

    # 配对检验只利用两配置结论不同的任务；事件为 True 不一定表示好结果。
    discordant = b + c
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(min(b, c) + 1)) / (2**discordant)
        p_value = min(1.0, 2.0 * tail)
    return {
        "method": "mcnemar_exact",
        "pairs": pair_count,
        "baseline_only_event": b,
        "treatment_only_event": c,
        "discordant_pairs": discordant,
        "p_value": p_value,
    }


def clustered_paired_bootstrap(
    pairs: Iterable[tuple[str, float, float]],
    *,
    iterations: int = 10_000,
    seed: int = 42,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Cluster-resampled CI for ``treatment - baseline`` mean difference.

    Each tuple is ``(cluster_id, baseline_value, treatment_value)``. Entire
    clusters are sampled with replacement, preserving within-template or
    within-case dependence.
    """

    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")

    grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for cluster, baseline_value, treatment_value in pairs:
        left = float(baseline_value)
        right = float(treatment_value)
        if not math.isfinite(left) or not math.isfinite(right):
            raise ValueError("bootstrap values must be finite")
        grouped[str(cluster)].append((left, right))
    clusters = sorted(grouped)
    if not clusters:
        return {
            "method": "clustered_paired_bootstrap",
            "iterations": iterations,
            "seed": seed,
            "clusters": 0,
            "pairs": 0,
            "estimate": None,
            "ci_low": None,
            "ci_high": None,
        }

    observed = [right - left for cluster in clusters for left, right in grouped[cluster]]
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(iterations):
        sampled_clusters = [rng.choice(clusters) for _ in clusters]
        differences = [
            right - left
            for cluster in sampled_clusters
            for left, right in grouped[cluster]
        ]
        estimates.append(mean(differences))

    alpha = (1.0 - confidence) / 2.0
    return {
        "method": "clustered_paired_bootstrap",
        "iterations": iterations,
        "seed": seed,
        "clusters": len(clusters),
        "pairs": len(observed),
        "estimate": mean(observed),
        "ci_low": percentile(estimates, alpha),
        "ci_high": percentile(estimates, 1.0 - alpha),
    }


def wilcoxon_signed_rank(
    baseline: Sequence[float],
    treatment: Sequence[float],
) -> dict[str, Any]:
    """Paired Wilcoxon signed-rank test and rank-biserial effect size.

    Exact sign enumeration is used for up to 20 non-zero pairs; larger samples
    use a tie-corrected normal approximation. Differences are defined as
    ``treatment - baseline``.
    """

    if len(baseline) != len(treatment):
        raise ValueError("paired samples must have equal length")
    differences = [float(right) - float(left) for left, right in zip(baseline, treatment)]
    if any(not math.isfinite(value) for value in differences):
        raise ValueError("paired values must be finite")
    nonzero = [value for value in differences if value != 0.0]
    zero_count = len(differences) - len(nonzero)
    if not nonzero:
        return {
            "method": "wilcoxon_signed_rank",
            "pairs": len(differences),
            "nonzero_pairs": 0,
            "zero_pairs": zero_count,
            "w_plus": 0.0,
            "w_minus": 0.0,
            "statistic": 0.0,
            "p_value": 1.0,
            "rank_biserial": 0.0,
            "median_difference": 0.0,
        }

    ranks = _average_ranks([abs(value) for value in nonzero])
    w_plus = sum(rank for rank, value in zip(ranks, nonzero) if value > 0.0)
    w_minus = sum(rank for rank, value in zip(ranks, nonzero) if value < 0.0)
    statistic = min(w_plus, w_minus)
    total_rank = w_plus + w_minus
    effect = (w_plus - w_minus) / total_rank if total_rank else 0.0

    if len(nonzero) <= 20:
        p_value = _wilcoxon_exact_p_value(ranks, statistic)
        method = "wilcoxon_signed_rank_exact"
    else:
        expected = len(nonzero) * (len(nonzero) + 1) / 4.0
        tie_counts: dict[float, int] = defaultdict(int)
        for value in (abs(item) for item in nonzero):
            tie_counts[value] += 1
        variance = len(nonzero) * (len(nonzero) + 1) * (2 * len(nonzero) + 1) / 24.0
        variance -= sum(
            count**3 - count for count in tie_counts.values() if count > 1
        ) / 48.0
        if variance <= 0.0:
            p_value = 1.0
        else:
            continuity = 0.5 if statistic < expected else -0.5
            z_score = (statistic - expected + continuity) / math.sqrt(variance)
            p_value = min(1.0, 2.0 * NormalDist().cdf(z_score))
        method = "wilcoxon_signed_rank_normal"

    return {
        "method": method,
        "pairs": len(differences),
        "nonzero_pairs": len(nonzero),
        "zero_pairs": zero_count,
        "w_plus": w_plus,
        "w_minus": w_minus,
        "statistic": statistic,
        "p_value": p_value,
        "rank_biserial": effect,
        "median_difference": median(differences),
    }


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Holm step-down family-wise error correction."""

    values = [float(value) for value in p_values]
    if any(not 0.0 <= value <= 1.0 for value in values):
        raise ValueError("p-values must be between 0 and 1")
    count = len(values)
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    adjusted = [0.0] * count
    running_max = 0.0
    for rank, (original_index, value) in enumerate(ordered):
        candidate = min(1.0, (count - rank) * value)
        running_max = max(running_max, candidate)
        adjusted[original_index] = running_max
    return adjusted


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for index in range(cursor, end):
            ranks[ordered[index][0]] = average_rank
        cursor = end
    return ranks


def _wilcoxon_exact_p_value(ranks: Sequence[float], observed: float) -> float:
    scaled = [int(round(rank * 2.0)) for rank in ranks]
    total = sum(scaled)
    observed_scaled = int(round(observed * 2.0))
    extreme = 0
    assignments = 1 << len(scaled)
    for mask in range(assignments):
        w_plus = sum(rank for index, rank in enumerate(scaled) if mask & (1 << index))
        statistic = min(w_plus, total - w_plus)
        if statistic <= observed_scaled:
            extreme += 1
    return extreme / assignments


__all__ = [
    "clustered_paired_bootstrap",
    "holm_adjust",
    "latency_summary",
    "mcnemar_exact",
    "percentile",
    "proportion_result",
    "safe_ratio",
    "wilcoxon_signed_rank",
    "wilson_interval",
]
