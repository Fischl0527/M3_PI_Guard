"""Confirmatory statistical helpers for the paper-v1 protocol."""

from __future__ import annotations

# 历史论文方案的统计适配层：按预先声明的任务/模板聚类，保留同任务配对关系。
# Holm 校正用于控制一组比较的误报，不能在看到结果后挑出有利比较组成家族。
from typing import Any, Iterable, Mapping

from .statistics import clustered_paired_bootstrap, holm_adjust, mcnemar_exact


def template_clustered_difference(
    baseline: Mapping[str, Iterable[int | bool]],
    treatment: Mapping[str, Iterable[int | bool]],
    *,
    iterations: int = 10_000,
    seed: int = 20260718,
) -> dict[str, Any]:
    """Paired bootstrap over semantic templates, not individual mutations."""

    if set(baseline) != set(treatment):
        raise ValueError("baseline and treatment must contain the same template clusters")
    # 同模板的多种攻击变体不能当作相互独立的新任务。
    pairs: list[tuple[str, float, float]] = []
    for cluster in sorted(baseline):
        left = [float(value) for value in baseline[cluster]]
        right = [float(value) for value in treatment[cluster]]
        if len(left) != len(right):
            raise ValueError(f"paired cluster length mismatch: {cluster}")
        pairs.extend((cluster, a, b) for a, b in zip(left, right))
    return clustered_paired_bootstrap(
        pairs,
        iterations=iterations,
        seed=seed,
    )


def paired_binary_family(
    comparisons: Mapping[str, tuple[Iterable[int | bool], Iterable[int | bool]]]
) -> dict[str, Any]:
    """McNemar tests with Holm correction across a declared hypothesis family."""

    raw: dict[str, dict[str, Any]] = {}
    names = sorted(comparisons)
    p_values: list[float] = []
    for name in names:
        baseline, treatment = comparisons[name]
        result = mcnemar_exact(list(baseline), list(treatment))
        raw[name] = result
        p_values.append(float(result["p_value"]) if result["p_value"] is not None else 1.0)
    adjusted = holm_adjust(p_values)
    for name, value in zip(names, adjusted):
        raw[name]["holm_adjusted_p"] = value
    return {"method": "paired_mcnemar_holm", "comparisons": raw}


def fit_mixed_effect_logit(
    rows: Iterable[Mapping[str, Any]],
    *,
    outcome: str,
    fixed_effects: tuple[str, ...],
    cluster: str = "template_id",
) -> dict[str, Any]:
    """Fit a binomial mixed model with a random intercept per template.

    The function imports the optional scientific stack lazily and returns a
    serializable coefficient table.  Formal use must freeze the formula before
    the holdout is opened.
    """

    import pandas as pd
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

    frame = pd.DataFrame(list(rows))
    required = {outcome, cluster, *fixed_effects}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("mixed-effect rows missing columns: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("mixed-effect model requires at least one row")
    formula = f"{outcome} ~ " + (" + ".join(fixed_effects) if fixed_effects else "1")
    random = {f"random_intercept_{cluster}": f"0 + C({cluster})"}
    model = BinomialBayesMixedGLM.from_formula(formula, random, frame)
    fit = model.fit_vb()
    names = list(model.exog_names)
    means = list(fit.fe_mean)
    standard_deviations = list(fit.fe_sd)
    return {
        "method": "binomial_bayes_mixed_glm_variational_bayes",
        "formula": formula,
        "cluster": cluster,
        "observations": len(frame),
        "coefficients": [
            {"term": name, "estimate": float(mean), "std_error": float(sd)}
            for name, mean, sd in zip(names, means, standard_deviations)
        ],
    }
