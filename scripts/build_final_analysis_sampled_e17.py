"""Build the final synthesis with the admitted E17 stratified human audit.

The historical ``build_final_analysis.py`` is hash-bound by the completed E11
post-hoc execution freeze and therefore remains byte-for-byte unchanged.  This
adapter adds the later E17 sampled-human evidence admission boundary, records
its own hash in the final input ledger, and delegates every other calculation
and rendering path to the frozen builder.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import e17_review
from experiments.e17_human_sample_review import (
    EVIDENCE_TIER,
    PROHIBITED_CLAIM,
    PROTOCOL_ID,
    SOURCE_MODE,
)
from scripts import build_final_analysis as base


ADAPTER_RELATIVE = Path("scripts/build_final_analysis_sampled_e17.py")
REGISTRAR = "scripts/register_e17_sample_evidence.py"

_ORIGINAL_VALIDATE_INPUTS = base.validate_inputs
_ORIGINAL_BUILD_FAILURE_SUMMARY = base.build_failure_summary
_ORIGINAL_BUILD_EXECUTIVE_SUMMARY = base.build_executive_summary
_ORIGINAL_BUILD_ANALYSIS_MARKDOWN = base.build_analysis_markdown
_ORIGINAL_BUILD_FAMILY = base._build_family
_ORIGINAL_SAVE_FIGURE = base._save_figure


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sample_contract(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    configuration = manifest.get("configuration")
    contract = manifest.get("sampling_contract")
    coverage = configuration.get("coverage") if isinstance(configuration, Mapping) else None
    if (
        manifest.get("protocol_id") != PROTOCOL_ID
        or not isinstance(configuration, Mapping)
        or configuration.get("source_mode") != SOURCE_MODE
        or configuration.get("evidence_tier") != EVIDENCE_TIER
        or configuration.get("registry_eligible") is not True
        or not isinstance(contract, Mapping)
        or not isinstance(coverage, Mapping)
        or int(contract.get("population_rows", -1)) != 3299
        or int(contract.get("sample_rows", -1)) != 360
        or int(contract.get("representative_rows", -1)) != 300
        or int(contract.get("targeted_rows", -1)) != 60
        or contract.get("targeted_groups_pooled_into_population_estimates") is not False
        or contract.get("prohibited_claim") != PROHIBITED_CLAIM
        or coverage.get("full_population_human_reviewed") is not False
    ):
        raise base.FinalAnalysisError("E17 stratified human-audit scope contract drifted")
    return contract


def _validate_formal_identity(
    experiment_id: str,
    manifest: Mapping[str, Any],
    files: Mapping[str, Path],
) -> None:
    if experiment_id != "E17":
        base._FROZEN_VALIDATE_FORMAL_IDENTITY(experiment_id, manifest, files)
        return
    _sample_contract(manifest)
    progress = manifest.get("progress") or {}
    review_progress = manifest.get("review_progress") or {}
    if (
        int(progress.get("expected_runs", -1)) != 360
        or int(progress.get("completed_runs", -1)) != 360
        or int(progress.get("failed_jobs", -1)) != 0
        or int(progress.get("unresolved_cases", -1)) != 0
        or int(review_progress.get("reviewers_received", -1)) != 2
        or int(review_progress.get("code_set_agreements", -1)) != 360
        or int(review_progress.get("code_set_disagreements", -1)) != 0
        or len(set(str(value).casefold() for value in review_progress.get("reviewer_ids", []))) != 2
    ):
        raise base.FinalAnalysisError("E17 sampled human-review completion contract drifted")


def _validate_e17_source_admission(
    *,
    manifest: Mapping[str, Any],
    registry_item: Mapping[str, Any],
    registered_paths: Sequence[Path],
    root: Path,
) -> dict[str, Any]:
    contract = _sample_contract(manifest)
    configuration = manifest.get("configuration")
    plan = manifest.get("plan")
    registry_source = registry_item.get("source_index")
    sampling = registry_item.get("sampling_contract")
    if not all(isinstance(value, Mapping) for value in (configuration, plan, registry_source, sampling)):
        raise base.FinalAnalysisError("E17 sampled source binding is incomplete")
    assert isinstance(configuration, Mapping) and isinstance(plan, Mapping)
    assert isinstance(registry_source, Mapping) and isinstance(sampling, Mapping)
    if registry_item.get("completion_registrar") != REGISTRAR:
        raise base.FinalAnalysisError("E17 sampled audit was not admitted by its dedicated registrar")
    if (
        sampling.get("protocol_id") != PROTOCOL_ID
        or sampling.get("source_mode") != SOURCE_MODE
        or sampling.get("evidence_tier") != EVIDENCE_TIER
        or int(sampling.get("population_rows", -1)) != 3299
        or int(sampling.get("sample_rows", -1)) != 360
        or int(sampling.get("representative_rows", -1)) != 300
        or int(sampling.get("targeted_rows", -1)) != 60
        or sampling.get("full_population_human_reviewed") is not False
        or sampling.get("targeted_groups_pooled_into_population_estimates") is not False
        or sampling.get("prohibited_claim") != PROHIBITED_CLAIM
        or contract.get("prohibited_claim") != sampling.get("prohibited_claim")
    ):
        raise base.FinalAnalysisError("E17 registry sampling contract drifted")

    resolved: list[tuple[Path, str]] = []
    for label, record in (
        ("configuration.source_index", configuration.get("source_index")),
        ("plan.source_index", plan.get("source_index")),
        ("registry.source_index", registry_source),
    ):
        if not isinstance(record, Mapping):
            raise base.FinalAnalysisError(f"E17 lacks {label}")
        path = base._strict_path(Path(str(record.get("path", ""))), root, label=label)
        digest = _sha256(path)
        if digest != str(record.get("sha256", "")):
            raise base.FinalAnalysisError(f"E17 {label} hash mismatch")
        resolved.append((path, digest))
    if len({path for path, _ in resolved}) != 1 or len({digest for _, digest in resolved}) != 1:
        raise base.FinalAnalysisError("E17 source-index bindings disagree")
    source_index = resolved[0][0]
    registered = {path.resolve() for path in registered_paths}
    if source_index not in registered:
        raise base.FinalAnalysisError("E17 corrected source index is absent from active evidence")

    previous_root = e17_review.REPO_ROOT
    try:
        e17_review.REPO_ROOT = root
        source_bundle = e17_review.load_source_index(source_index)
    except Exception as exc:
        raise base.FinalAnalysisError(f"E17 corrected source index failed validation: {exc}") from exc
    finally:
        e17_review.REPO_ROOT = previous_root
    coverage = source_bundle.get("coverage")
    if (
        source_bundle.get("source_mode") != e17_review.SOURCE_MODE_FORMAL_CORRECTED
        or not isinstance(coverage, Mapping)
        or coverage.get("status") != "pass"
        or int(coverage.get("duplicate_logical_run_count", -1)) != 0
        or int(coverage.get("duplicate_logical_step_count", -1)) != 0
    ):
        raise base.FinalAnalysisError("E17 corrected source coverage is not duplicate-free")

    for label in ("sampling_manifest", "packet_manifest"):
        record = sampling.get(label)
        if not isinstance(record, Mapping):
            raise base.FinalAnalysisError(f"E17 registry lacks {label}")
        path = base._strict_path(Path(str(record.get("path", ""))), root, label=f"registry.{label}")
        if _sha256(path) != str(record.get("sha256", "")):
            raise base.FinalAnalysisError(f"E17 registry {label} hash mismatch")
        if path not in registered:
            raise base.FinalAnalysisError(f"E17 registry {label} is absent from active evidence")
    return {"path": source_index, "sha256": resolved[0][1], "coverage": dict(coverage)}


def _build_failure_taxonomy(bundles: Mapping[str, base.Bundle]) -> base.ChartResult:
    rows: list[dict[str, Any]] = []
    for source in base._bundle_csv(bundles["E17"], "failure_class_counts.csv"):
        rows.append(
            base._plain_long(
                "E17",
                panel="Representative sampled primary class",
                series="two-human stratified audit",
                x=source.get("failure_class", ""),
                metric="failure_share",
                value=(
                    None
                    if base._float(source.get("percent"), label="E17 percent") is None
                    else float(source["percent"]) / 100.0
                ),
                numerator=source.get("count"),
                denominator=source.get("total"),
                ci_low=(
                    None
                    if base._float(source.get("ci_low_percent"), label="E17 ci low") is None
                    else float(source["ci_low_percent"]) / 100.0
                ),
                ci_high=(
                    None
                    if base._float(source.get("ci_high_percent"), label="E17 ci high") is None
                    else float(source["ci_high_percent"]) / 100.0
                ),
                limitation="Unweighted 300-row representative stratum; the 60 targeted audit rows are excluded.",
            )
        )
    positive = [
        row for row in rows if row.get("value") is not None and int(row.get("numerator") or 0) > 0
    ]
    use_donut = 2 <= len(positive) <= 5 and min(float(row["value"]) for row in positive) >= 0.05
    chart_type = (
        "authoritative_count_bar_plus_composition_donut"
        if use_donut
        else "authoritative_count_bar_plus_share_dot_with_wilson_95ci"
    )
    composition_note = (
        "the donut is a rough composition aid only"
        if use_donut
        else "the share panel uses dots and Wilson 95% intervals because the composition is too dense for an honest donut"
    )
    return base.ChartResult(
        "failure_taxonomy",
        "Stratified human-audit failure taxonomy",
        "E17",
        rows,
        chart_type,
        (
            "E17 primary classes in the 300-row representative audit stratum. "
            f"The 60 targeted rows are excluded; {composition_note}. Labels show count/total."
        ),
        ["failure_share", "failure_count"],
        ["representative_sample_primary_failure_class"],
        [{"method": "Wilson score interval", "level": 0.95}],
        ["Weighted population estimates and targeted-group diagnostics remain in the E17 source bundle."],
        _render_sampled_failure,
    )


def _render_sampled_failure(
    rows: Sequence[Mapping[str, Any]],
    png: Path,
    svg: Path,
    title: str,
    caption: str,
) -> None:
    plt = base._plot_imports()
    observed = sorted(
        base._observed(rows),
        key=lambda row: (-int(row.get("numerator") or 0), str(row.get("x"))),
    )
    fig, (bar_axis, share_axis) = plt.subplots(
        1, 2, figsize=(12.8, 6.5), gridspec_kw={"width_ratios": [1.5, 1.0]}
    )
    labels = [str(row.get("x", "")) for row in observed]
    counts = [int(row.get("numerator") or 0) for row in observed]
    positions = list(range(len(observed)))
    bars = bar_axis.barh(positions, counts, color="#4F86C6", edgecolor="#315C8A")
    for bar, row in zip(bars, observed):
        _, label = base._display_value(row)
        bar_axis.text(
            bar.get_width() + max(0.1, max(counts, default=1) * 0.015),
            bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            fontsize=7.4,
        )
    bar_axis.set_yticks(positions, labels)
    bar_axis.invert_yaxis()
    bar_axis.set_xlim(0.0, max(1.0, max(counts, default=1) * 1.35))
    bar_axis.set_xlabel("Human-reviewed count in representative sample")
    bar_axis.grid(axis="x", alpha=0.2)
    bar_axis.spines[["top", "right"]].set_visible(False)

    shares = [float(row.get("value") or 0.0) * 100.0 for row in observed]
    lows = [float(row.get("ci_low") or 0.0) * 100.0 for row in observed]
    highs = [float(row.get("ci_high") or 0.0) * 100.0 for row in observed]
    for position, share, lower, upper in zip(positions, shares, lows, highs):
        share_axis.errorbar(
            share,
            position,
            xerr=[[max(0.0, share - lower)], [max(0.0, upper - share)]],
            fmt="o",
            color="#315C8A",
            ecolor="#17212B",
            capsize=3,
            markersize=4.5,
            linewidth=1.0,
        )
        label_x = min(98.5, upper + 1.5)
        share_axis.text(
            label_x,
            position,
            f"{share:.1f}%",
            va="center",
            ha="right" if upper + 1.5 > 95.0 else "left",
            fontsize=7.3,
        )
    share_axis.set_yticks(positions, labels)
    share_axis.invert_yaxis()
    share_axis.set_xlim(0.0, 100.0)
    share_axis.set_xlabel("Share of 300 representative reviewed items (%)")
    share_axis.set_title("Wilson 95% CI")
    share_axis.grid(axis="x", alpha=0.2)
    share_axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title, x=0.01, ha="left", fontsize=14)
    base._figure_footer(fig, caption)
    base._save_figure(fig, png, svg)
    plt.close(fig)


def _adaptive_save_figure(fig: Any, png: Path, svg: Path) -> None:
    """Expand dense categorical plots before the frozen layout QA runs."""

    max_dense_labels = 0
    max_label_length = 0
    for axis in fig.axes:
        labels = [
            label
            for label in axis.get_xticklabels()
            if label.get_visible() and str(label.get_text()).strip()
        ]
        if not labels:
            continue
        max_dense_labels = max(max_dense_labels, len(labels))
        max_label_length = max(
            max_label_length,
            max(len(str(label.get_text())) for label in labels),
        )
        if len(labels) >= 6 and max(len(str(label.get_text())) for label in labels) >= 8:
            for label in labels:
                label.set_rotation(42)
                label.set_ha("right")
                label.set_fontsize(min(float(label.get_fontsize()), 6.6))
    if max_dense_labels >= 6 and max_label_length >= 8:
        width, height = fig.get_size_inches()
        target_width = min(28.0, max(float(width), max_dense_labels * 2.0))
        fig.set_size_inches(target_width, float(height), forward=True)
    _ORIGINAL_SAVE_FIGURE(fig, png, svg)


def _render_family_heatmap(
    rows: Sequence[Mapping[str, Any]],
    png: Path,
    svg: Path,
    title: str,
    caption: str,
) -> None:
    plt = base._plot_imports()
    import numpy as np

    panels = list(dict.fromkeys(str(row.get("panel", "")) for row in rows))
    fig, axes = plt.subplots(
        len(panels),
        1,
        figsize=(16.2, max(5.4, 4.0 * len(panels))),
        squeeze=False,
    )
    last_image = None
    for axis, panel in zip(axes[:, 0], panels):
        selected = [row for row in rows if str(row.get("panel", "")) == panel]
        x_values = sorted({str(row.get("x", "")) for row in selected}, key=base._sort_token)
        y_values = sorted({str(row.get("series", "")) for row in selected})
        lookup = {(str(row.get("series", "")), str(row.get("x", ""))): row for row in selected}
        matrix = np.full((len(y_values), len(x_values)), np.nan)
        for y_index, y_value in enumerate(y_values):
            for x_index, x_value in enumerate(x_values):
                row = lookup.get((y_value, x_value))
                if row is not None and row.get("value") is not None:
                    matrix[y_index, x_index] = float(row["value"]) * 100.0
        masked = np.ma.masked_invalid(matrix)
        cmap = plt.get_cmap("Blues").copy()
        cmap.set_bad("#E6E8EB")
        last_image = axis.imshow(masked, aspect="auto", vmin=0.0, vmax=100.0, cmap=cmap)
        for y_index, y_value in enumerate(y_values):
            for x_index, x_value in enumerate(x_values):
                row = lookup.get((y_value, x_value))
                if row is None or row.get("value") is None:
                    label = "NA"
                else:
                    _, label = base._display_value(row)
                    label = label.replace(" · ", "\n")
                axis.text(
                    x_index,
                    y_index,
                    label,
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color=(
                        "white"
                        if not np.isnan(matrix[y_index, x_index]) and matrix[y_index, x_index] >= 55
                        else "#17212B"
                    ),
                )
        axis.set_xticks(range(len(x_values)), x_values, rotation=42, ha="right", fontsize=6.4)
        axis.set_yticks(range(len(y_values)), y_values, fontsize=7.4)
        axis.set_title(panel, loc="left", fontsize=10.5)
    if last_image is not None:
        # The frozen base saver reapplies subplot margins.  A colorbar created
        # with ``ax=...`` is therefore moved back on top of the heatmaps during
        # final QA.  Give it a fixed, non-subplot axis beyond the base saver's
        # right=0.96 boundary so labels and cells remain unobstructed.
        color_axis = fig.add_axes([0.975, 0.22, 0.012, 0.54])
        fig.colorbar(last_image, cax=color_axis, label="Percent")
    fig.suptitle(title, x=0.01, ha="left", fontsize=14, color="#17212B")
    base._figure_footer(fig, caption)
    base._save_figure(fig, png, svg)
    plt.close(fig)


def _build_family(bundles: Mapping[str, base.Bundle]) -> base.ChartResult:
    chart = _ORIGINAL_BUILD_FAMILY(bundles)
    return base.ChartResult(
        chart.chart_id,
        chart.title,
        chart.source_experiments,
        chart.rows,
        chart.chart_type,
        chart.caption,
        chart.metrics,
        chart.grain,
        chart.uncertainty,
        chart.warnings,
        _render_family_heatmap,
    )


def _build_failure_summary(bundles: Mapping[str, base.Bundle]) -> list[dict[str, Any]]:
    rows = _ORIGINAL_BUILD_FAILURE_SUMMARY(bundles)
    for row in rows:
        if row.get("source_experiment") == "E17":
            row["source_scope"] = "two-human reviewed 300-row representative sample stratum"
            row["overlap_note"] = (
                "Authoritative for the unweighted representative sample only; targeted 60 rows excluded; "
                "weighted population estimates remain separate; do not sum with E14/E16."
            )
    return rows


def _build_executive_summary(
    acceptance_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    *,
    input_ledger: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    value = _ORIGINAL_BUILD_EXECUTIVE_SUMMARY(
        acceptance_rows, failure_rows, input_ledger=input_ledger
    )
    value["formal_claim_scope"]["review"] = (
        "E17 two-human 300-row representative sample; 60 targeted rows excluded from population estimates and main matrix"
    )
    value["authoritative_failure_source"] = (
        "E17 within its two-human reviewed 300-row representative sample stratum"
    )
    value["e17_sampling_contract"] = {
        "population_rows": 3299,
        "reviewed_sample_rows": 360,
        "representative_rows": 300,
        "targeted_rows": 60,
        "full_population_human_reviewed": False,
        "targeted_rows_pooled": False,
        "prohibited_claim": PROHIBITED_CLAIM,
    }
    return value


def _build_analysis_markdown(*args: Any, **kwargs: Any) -> str:
    text = _ORIGINAL_BUILD_ANALYSIS_MARKDOWN(*args, **kwargs)
    replacements = {
        "主比例使用原始计数与 Wilson 95% 置信区间。": (
            "主比例使用原始计数与 Wilson 95% 置信区间。E17 抽样审计另以冻结的分层权重给出 "
            "Hajek 比例和 10,000 次分层 percentile-bootstrap 95% 区间。"
        ),
        (
            "E17 提供 8 行相互排斥的人工裁决主分类，是其 review-candidate cohort 内的权威分类。"
        ): (
            "E17 的 8 行互斥主分类来自两名真人独立复核的 300 行代表性抽样层；另有 40 行自动分歧定向样本和 "
            "20 行稀有/复杂定向样本，仅作诊断且不进入该分母。总体估计及分层 bootstrap 区间保留在 E17 的 "
            "`weighted_population_estimates.csv`。"
        ),
        (
            "- E16 的轮次和 E10 的回合是离散设计条件，不是连续时间趋势；E17 是自动筛选的复核 cohort，而不是主矩阵的随机样本。"
        ): (
            "- E16 的轮次和 E10 的回合是离散设计条件，不是连续时间趋势；E17 是从自动筛选 cohort 冻结得到的分层抽样审计，"
            "只有 300 行代表性层可用于加权估计，不能描述成 3,299 行全量真人评审。"
        ),
        "python scripts/build_final_analysis.py --registry": (
            "python scripts/build_final_analysis_sampled_e17.py --registry"
        ),
    }
    for source, target in replacements.items():
        if source not in text:
            raise base.FinalAnalysisError(f"sampled-E17 narrative patch anchor drifted: {source[:80]}")
        text = text.replace(source, target)
    return text


def _validate_inputs(
    registry_path: str | Path,
    *,
    repository_root: str | Path,
) -> tuple[dict[str, Any], dict[str, base.Bundle], list[dict[str, Any]]]:
    registry, bundles, ledger = _ORIGINAL_VALIDATE_INPUTS(
        registry_path, repository_root=repository_root
    )
    root = Path(repository_root).resolve()
    adapter = (root / ADAPTER_RELATIVE).resolve()
    ledger.append(
        {
            "experiment_id": "E17",
            "source": "sampled_e17_reporting_adapter",
            "path": adapter.relative_to(root).as_posix(),
            "bytes": adapter.stat().st_size,
            "sha256": _sha256(adapter),
        }
    )
    ledger.sort(key=lambda row: (row["experiment_id"], row["path"], row["source"]))
    return registry, bundles, ledger


def _install_adapter() -> None:
    if not hasattr(base, "_FROZEN_VALIDATE_FORMAL_IDENTITY"):
        base._FROZEN_VALIDATE_FORMAL_IDENTITY = base._validate_formal_identity
    base.EXPECTED_FIGURE_TIERS["E17"] = EVIDENCE_TIER
    base._validate_formal_identity = _validate_formal_identity
    base._validate_e17_source_admission = _validate_e17_source_admission
    base._build_failure_taxonomy = _build_failure_taxonomy
    base._build_family = _build_family
    base._save_figure = _adaptive_save_figure
    base.build_failure_summary = _build_failure_summary
    base.build_executive_summary = _build_executive_summary
    base.build_analysis_markdown = _build_analysis_markdown
    base.validate_inputs = _validate_inputs


def validate_inputs_sampled_e17(
    registry_path: str | Path,
    *,
    repository_root: str | Path,
) -> tuple[dict[str, Any], dict[str, base.Bundle], list[dict[str, Any]]]:
    """Run sampled-E17 admission without leaking monkeypatches to callers."""

    names = (
        "_validate_formal_identity",
        "_validate_e17_source_admission",
        "_build_failure_taxonomy",
        "_build_family",
        "_save_figure",
        "build_failure_summary",
        "build_executive_summary",
        "build_analysis_markdown",
        "validate_inputs",
    )
    snapshot = {name: getattr(base, name) for name in names}
    tier = base.EXPECTED_FIGURE_TIERS["E17"]
    had_frozen = hasattr(base, "_FROZEN_VALIDATE_FORMAL_IDENTITY")
    frozen = getattr(base, "_FROZEN_VALIDATE_FORMAL_IDENTITY", None)
    _install_adapter()
    try:
        return base.validate_inputs(registry_path, repository_root=repository_root)
    finally:
        for name, value in snapshot.items():
            setattr(base, name, value)
        base.EXPECTED_FIGURE_TIERS["E17"] = tier
        if had_frozen:
            base._FROZEN_VALIDATE_FORMAL_IDENTITY = frozen
        elif hasattr(base, "_FROZEN_VALIDATE_FORMAL_IDENTITY"):
            delattr(base, "_FROZEN_VALIDATE_FORMAL_IDENTITY")


def _finalize_manifest(output_dir: Path) -> None:
    manifest_path = output_dir / "manifest.json"
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    value["formal_evidence_policy"]["E17"] = (
        "two_human_stratified_sample_300_representative_plus_60_diagnostic_no_pooling"
    )
    command = value.get("repro_command") or []
    if len(command) < 2 or command[1] != "scripts/build_final_analysis.py":
        raise base.FinalAnalysisError("final manifest reproduction command drifted")
    command[1] = ADAPTER_RELATIVE.as_posix()
    adapter = ROOT / ADAPTER_RELATIVE
    value["reporting_adapter"] = {
        "path": ADAPTER_RELATIVE.as_posix(),
        "bytes": adapter.stat().st_size,
        "sha256": _sha256(adapter),
        "reason": "preserve hash-bound E11 builder while admitting later E17 sampled-human evidence",
    }
    manifest_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    _install_adapter()
    parser = base.build_parser()
    parser.description = "Validate E0-E17 and build the final synthesis with admitted sampled E17 human review"
    args = parser.parse_args(argv)
    try:
        if args.validate_only:
            return base.main(argv)
        result = base.generate_final_analysis(
            registry_path=args.registry,
            repository_root=args.repository_root,
            output_dir=args.out,
            program_manifest_path=args.program_manifest,
            integrity_audit_path=args.integrity_audit,
            e11_supplement_dir=args.e11_supplement,
            force=args.force,
        )
        _finalize_manifest(Path(result["output_dir"]).resolve())
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except base.FinalAnalysisError as exc:
        parser.exit(2, f"final analysis rejected: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
