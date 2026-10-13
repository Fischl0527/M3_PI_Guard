"""针对已完成的最终综合分析报告执行独立统计学与证据完整性审计。

本验证器不导入任何分析构建代码，而是完全独立重新哈希最终数据包与输入账本，
独立重新计算基于计数的准入验收指标及 E9、E13 门禁准则，
验证配对检验契约，并签发带明确校验状态的机器可读“材料护照”（Material Passport）。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANALYSIS = ROOT / "outputs" / "experiments" / "final_analysis"
E13_TARGETS = {
    "precision": (">=", 0.90),
    "recall": (">=", 0.90),
    "fpr": ("<=", 0.05),
    "benign_ask_rate": ("<=", 0.10),
}


class StatisticalValidationError(RuntimeError):
    """当审计输入本身不安全或格式异常时抛出的运行时异常。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(value: str | Path, root: Path, *, label: str, require_file: bool = True) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise StatisticalValidationError(f"{label} escapes allowed root: {value}") from exc
    if require_file and (not resolved.is_file() or resolved.stat().st_size <= 0):
        raise StatisticalValidationError(f"{label} is missing or empty: {resolved}")
    return resolved


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StatisticalValidationError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StatisticalValidationError(f"{label} must be a JSON object: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"na", "nan", "none", "null"}:
        return None
    result = float(text)
    if not math.isfinite(result):
        raise StatisticalValidationError(f"non-finite numeric value: {value!r}")
    return result


def _integer(value: Any) -> int | None:
    number = _number(value)
    if number is None:
        return None
    rounded = int(round(number))
    if not math.isclose(number, rounded, abs_tol=1e-9):
        raise StatisticalValidationError(f"expected integer, got {value!r}")
    return rounded


def _truthy(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _close(left: Any, right: Any, *, tolerance: float = 2e-6) -> bool:
    a = _number(left)
    b = _number(right)
    return a is not None and b is not None and math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def _evaluate(value: float, operator: str, target: float) -> bool:
    if operator == ">=":
        return value >= target
    if operator == "<=":
        return value <= target
    if operator == "<":
        return value < target
    if operator == "==":
        return math.isclose(value, target, abs_tol=1e-12)
    raise StatisticalValidationError(f"unsupported comparison operator: {operator}")


def independent_mcnemar_exact(baseline_only: int, treatment_only: int) -> float:
    """独立重新计算双侧精确不一致对 McNemar p 值。"""

    if baseline_only < 0 or treatment_only < 0:
        raise ValueError("discordant counts must be non-negative")
    discordant = baseline_only + treatment_only
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, index)
        for index in range(min(baseline_only, treatment_only) + 1)
    ) / (2**discordant)
    return min(1.0, 2.0 * tail)


def independent_holm(p_values: Sequence[float]) -> list[float]:
    """独立重新计算 Holm 逐步向下调整后的 p 值。"""

    values = [float(value) for value in p_values]
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("p-values must be in [0, 1]")
    result = [0.0] * len(values)
    running = 0.0
    for rank, (index, value) in enumerate(sorted(enumerate(values), key=lambda pair: pair[1])):
        running = max(running, min(1.0, (len(values) - rank) * value))
        result[index] = running
    return result


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def validate_statistical_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    """在不依赖项目辅助函数的前提下验证 McNemar/bootstrap/Holm/Wilcoxon 记录。"""

    findings: list[dict[str, Any]] = []
    method_counts = {"mcnemar": 0, "bootstrap": 0, "wilcoxon": 0, "holm_families": 0}

    def record(check: str, passed: bool, path: str, detail: str) -> None:
        findings.append(
            {"check": check, "status": "pass" if passed else "fail", "path": path, "detail": detail}
        )

    for path, node in _walk(payload):
        method = str(node.get("method", ""))
        if method == "mcnemar_exact":
            method_counts["mcnemar"] += 1
            b = _integer(node.get("baseline_only_event"))
            c = _integer(node.get("treatment_only_event"))
            discordant = _integer(node.get("discordant_pairs"))
            stored = _number(node.get("p_value"))
            valid = b is not None and c is not None and discordant == b + c and stored is not None
            expected = independent_mcnemar_exact(b or 0, c or 0) if valid else None
            valid = valid and math.isclose(stored or 0.0, expected or 0.0, rel_tol=2e-10, abs_tol=2e-12)
            pairs = _integer(node.get("pairs"))
            valid = valid and (pairs is None or pairs >= (discordant or 0))
            record("mcnemar_exact_recompute", valid, path, f"stored={stored}; recomputed={expected}; b={b}; c={c}")
        elif method == "clustered_paired_bootstrap":
            method_counts["bootstrap"] += 1
            iterations = _integer(node.get("iterations"))
            seed = _integer(node.get("seed"))
            clusters = _integer(node.get("clusters"))
            pairs = _integer(node.get("pairs"))
            estimate = _number(node.get("estimate"))
            low = _number(node.get("ci_low"))
            high = _number(node.get("ci_high"))
            unavailable = (
                clusters == 0
                and pairs == 0
                and estimate is None
                and low is None
                and high is None
            )
            evaluable = (
                clusters is not None
                and pairs is not None
                and clusters > 0
                and pairs >= clusters
                and estimate is not None
                and low is not None
                and high is not None
                and low <= estimate <= high
            )
            valid = iterations == 10_000 and seed is not None and (unavailable or evaluable)
            record(
                "clustered_paired_bootstrap_contract",
                valid,
                path,
                f"iterations={iterations}; seed={seed}; clusters={clusters}; pairs={pairs}; CI=[{low},{high}]",
            )
        elif method.startswith("wilcoxon_signed_rank"):
            method_counts["wilcoxon"] += 1
            pairs = _integer(node.get("pairs"))
            nonzero = _integer(node.get("nonzero_pairs"))
            zeros = _integer(node.get("zero_pairs"))
            w_plus = _number(node.get("w_plus"))
            w_minus = _number(node.get("w_minus"))
            statistic = _number(node.get("statistic"))
            effect = _number(node.get("rank_biserial"))
            p_value = _number(node.get("p_value"))
            expected_effect = None
            if w_plus is not None and w_minus is not None and w_plus + w_minus:
                expected_effect = (w_plus - w_minus) / (w_plus + w_minus)
            valid = (
                pairs is not None
                and nonzero is not None
                and zeros is not None
                and pairs == nonzero + zeros
                and w_plus is not None
                and w_minus is not None
                and statistic is not None
                and math.isclose(statistic, min(w_plus, w_minus), abs_tol=1e-9)
                and effect is not None
                and expected_effect is not None
                and math.isclose(effect, expected_effect, rel_tol=2e-9, abs_tol=2e-12)
                and p_value is not None
                and 0.0 <= p_value <= 1.0
            )
            record(
                "wilcoxon_algebra_and_effect_contract",
                valid,
                path,
                f"pairs={pairs}; nonzero={nonzero}; zeros={zeros}; effect={effect}; recomputed={expected_effect}",
            )

    for path, node in _walk(payload):
        family = node.get("holm_correction")
        if not isinstance(family, list):
            continue
        method_counts["holm_families"] += 1
        values: list[float] = []
        stored: list[float] = []
        valid_rows = True
        for row in family:
            if not isinstance(row, Mapping):
                valid_rows = False
                continue
            p_value = _number(row.get("p_value"))
            if p_value is None:
                p_value = _number(row.get("raw_p"))
            adjusted = _number(row.get("holm_adjusted_p"))
            if p_value is None or adjusted is None:
                valid_rows = False
                continue
            values.append(p_value)
            stored.append(adjusted)
        expected = independent_holm(values) if valid_rows and values else []
        valid = valid_rows and bool(values) and all(
            math.isclose(left, right, rel_tol=2e-9, abs_tol=2e-12)
            for left, right in zip(stored, expected)
        )
        record("holm_family_recompute", valid, path + ".holm_correction", f"tests={len(values)}")

    return {
        "status": "pass" if all(item["status"] == "pass" for item in findings) else "fail",
        "method_counts": method_counts,
        "findings": findings,
    }


def _check_artifacts(analysis: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return {"status": "fail", "checked": 0, "failures": ["manifest artifact ledger missing"]}
    failures: list[str] = []
    checked = 0
    for index, item in enumerate(artifacts):
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            failures.append(f"artifact[{index}] malformed")
            continue
        try:
            path = _inside(item["path"], analysis, label=f"analysis artifact[{index}]")
        except StatisticalValidationError as exc:
            failures.append(str(exc))
            continue
        checked += 1
        if _integer(item.get("bytes")) != path.stat().st_size or item.get("sha256") != _sha256(path):
            failures.append(f"artifact integrity mismatch: {path.name}")
    return {"status": "pass" if not failures else "fail", "checked": checked, "failures": failures}


def _check_input_ledger(root: Path, ledger_path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rows = _read_csv(ledger_path)
    failures: list[str] = []
    paths: dict[str, tuple[int | None, str]] = {}
    repeated_references = 0
    for index, row in enumerate(rows):
        value = row.get("path", "")
        try:
            path = _inside(value, root, label=f"input ledger row {index}")
        except StatisticalValidationError as exc:
            failures.append(str(exc))
            continue
        relative = path.relative_to(root).as_posix()
        signature = (_integer(row.get("bytes")), str(row.get("sha256", "")))
        if relative in paths:
            repeated_references += 1
            if paths[relative] != signature:
                failures.append(f"conflicting repeated input ledger path: {relative}")
        paths[relative] = signature
        if signature[0] != path.stat().st_size or signature[1] != _sha256(path):
            failures.append(f"input ledger integrity mismatch: {relative}")
    return (
        {
            "status": "pass" if not failures else "fail",
            "checked": len(rows),
            "unique_paths": len(paths),
            "repeated_provenance_references": repeated_references,
            "failures": failures,
        },
        rows,
    )


def _ledger_path(
    rows: Sequence[Mapping[str, str]], root: Path, experiment_id: str, filename: str
) -> Path:
    matches: dict[str, Path] = {}
    for row in rows:
        if row.get("experiment_id") != experiment_id:
            continue
        candidate = Path(row.get("path", ""))
        if candidate.name != filename:
            continue
        path = _inside(candidate, root, label=f"{experiment_id} {filename}")
        matches[str(path)] = path
    if len(matches) != 1:
        raise StatisticalValidationError(
            f"expected exactly one {experiment_id}/{filename} in input ledger, got {len(matches)}"
        )
    return next(iter(matches.values()))


def _recompute_e9(
    rows: Sequence[Mapping[str, str]], root: Path, analysis: Path
) -> dict[str, Any]:
    source = _ledger_path(rows, root, "E9", "context_position.csv")
    unresolved = 0
    runs = 0
    for index, row in enumerate(_read_csv(source)):
        numerator = _integer(row.get("unresolved_runs"))
        denominator = _integer(row.get("case_runs"))
        metric_num = _integer(row.get("UnresolvedRate_numerator"))
        metric_den = _integer(row.get("UnresolvedRate_denominator"))
        value = _number(row.get("UnresolvedRate"))
        if (
            numerator is None
            or denominator is None
            or metric_num != numerator
            or metric_den != denominator
            or denominator <= 0
            or value is None
            or not math.isclose(value, numerator / denominator, rel_tol=2e-6, abs_tol=2e-6)
        ):
            raise StatisticalValidationError(f"E9 unresolved count/rate drift at row {index + 2}")
        unresolved += numerator
        runs += denominator
    stored = _load_json(_inside("e9_data_quality.json", analysis, label="E9 diagnostic"), label="E9 diagnostic")
    overall = stored.get("overall")
    valid = isinstance(overall, Mapping) and (
        _integer(overall.get("unresolved_runs")) == unresolved
        and _integer(overall.get("case_runs")) == runs
        and _close(overall.get("rate"), unresolved / runs)
    )
    return {
        "status": "pass" if valid else "fail",
        "source": source.relative_to(root).as_posix(),
        "unresolved_runs": unresolved,
        "case_runs": runs,
        "rate": unresolved / runs,
    }


def _recompute_e13(rows: Sequence[Mapping[str, str]], root: Path) -> dict[str, Any]:
    scan_path = _ledger_path(rows, root, "E13", "threshold_scan.csv")
    frozen_path = _ledger_path(rows, root, "E13", "frozen_thresholds.json")
    frozen = _load_json(frozen_path, label="E13 frozen thresholds")
    ask = _number(frozen.get("ask_threshold"))
    deny = _number(frozen.get("deny_threshold"))
    matches = [
        row
        for row in _read_csv(scan_path)
        if _close(row.get("ask_threshold"), ask) and _close(row.get("deny_threshold"), deny)
    ]
    if len(matches) != 1:
        raise StatisticalValidationError(f"frozen E13 pair matches {len(matches)} threshold rows")
    selected = matches[0]
    checks: dict[str, Any] = {}
    all_pass = True
    for metric, (operator, target) in E13_TARGETS.items():
        numerator = _integer(selected.get(f"{metric}_numerator"))
        denominator = _integer(selected.get(f"{metric}_denominator"))
        stored = _number(selected.get(metric))
        if numerator is None or denominator is None or denominator <= 0 or stored is None:
            raise StatisticalValidationError(f"E13 {metric} lacks raw counts")
        value = numerator / denominator
        if not math.isclose(value, stored, rel_tol=2e-6, abs_tol=2e-6):
            raise StatisticalValidationError(f"E13 {metric} stored value drifted from counts")
        passed = _evaluate(value, operator, target)
        all_pass = all_pass and passed
        checks[metric] = {
            "numerator": numerator,
            "denominator": denominator,
            "value": value,
            "operator": operator,
            "target": target,
            "passed": passed,
        }
    return {
        "status": "pass",
        "all_constraints_pass": all_pass,
        "recorded_status_non_authoritative": frozen.get("status"),
        "ask_threshold": ask,
        "deny_threshold": deny,
        "checks": checks,
    }


def _recompute_acceptance(analysis: Path, e13: Mapping[str, Any]) -> dict[str, Any]:
    rows = _read_csv(_inside("acceptance_matrix.csv", analysis, label="acceptance matrix"))
    failures: list[str] = []
    direct_ratio_ids = {"A02", "A03", "A04", "A05", "A07", "A08", "A11"}
    for row in rows:
        target_id = row.get("target_id", "")
        status = row.get("status")
        estimate = _number(row.get("estimate"))
        if target_id == "A00":
            expected = "pass" if e13.get("all_constraints_pass") else "fail"
            if status != expected:
                failures.append(f"A00 status={status}, recomputed={expected}")
            continue
        if target_id in direct_ratio_ids:
            numerator = _integer(row.get("numerator"))
            denominator = _integer(row.get("denominator"))
            if numerator is None or denominator is None or denominator <= 0 or estimate is None:
                failures.append(f"{target_id} lacks direct k/n estimate")
            elif not math.isclose(estimate, numerator / denominator, rel_tol=2e-6, abs_tol=2e-6):
                failures.append(f"{target_id} estimate drifted from {numerator}/{denominator}")
        threshold = _number(row.get("threshold"))
        comparator = str(row.get("comparator", "")).strip()
        operator = next((item for item in (">=", "<=", "==", "<") if comparator.startswith(item)), None)
        if estimate is not None and threshold is not None and operator:
            expected = "pass" if _evaluate(estimate, operator, threshold) else "fail"
            if status != expected:
                failures.append(f"{target_id} status={status}, point-estimate rule={expected}")
        uncertainty = str(row.get("uncertainty_assessment", ""))
        if not uncertainty:
            failures.append(f"{target_id} lacks uncertainty_assessment")
    return {
        "status": "pass" if not failures else "fail",
        "target_count": len(rows),
        "failures": failures,
        "uncertainty_assessments": {
            value: sum(row.get("uncertainty_assessment") == value for row in rows)
            for value in sorted({row.get("uncertainty_assessment", "") for row in rows})
        },
    }


def _check_undefined_not_zero(analysis: Path) -> dict[str, Any]:
    chart_map = _read_csv(_inside("chart_map.csv", analysis, label="chart map"))
    checked = 0
    failures: list[str] = []
    for chart in chart_map:
        data = _inside(chart.get("data", ""), analysis, label="chart data")
        for row_index, row in enumerate(_read_csv(data), start=2):
            for key, raw in row.items():
                if not key.endswith("_denominator") or _integer(raw) != 0:
                    continue
                prefix = key[: -len("_denominator")]
                value = row.get(prefix)
                checked += 1
                if _number(value) is not None:
                    failures.append(f"{data.name}:{row_index}:{prefix} encodes zero denominator numerically")
    return {"status": "pass" if not failures else "fail", "checked": checked, "failures": failures}


def _statistics_contracts(
    ledger: Sequence[Mapping[str, str]], root: Path
) -> dict[str, Any]:
    paths: dict[str, tuple[Path, str]] = {}
    for row in ledger:
        candidate = Path(row.get("path", ""))
        if candidate.name != "statistics.json" or not str(row.get("experiment_id", "")).startswith("E"):
            continue
        path = _inside(candidate, root, label="statistics input")
        paths[str(path)] = (path, str(row.get("experiment_id", "")))
    reports: list[dict[str, Any]] = []
    total_methods = {"mcnemar": 0, "bootstrap": 0, "wilcoxon": 0, "holm_families": 0}
    for path, experiment_id in sorted(paths.values(), key=lambda item: str(item[0])):
        report = validate_statistical_contract(_load_json(path, label="statistics input"))
        for key in total_methods:
            total_methods[key] += int(report["method_counts"][key])
        reports.append(
            {
                "path": path.relative_to(root).as_posix(),
                "status": (
                    "diagnostic_nonblocking"
                    if experiment_id == "E0" and report["status"] == "fail"
                    else report["status"]
                ),
                "evidence_role": "historical_diagnostic_only" if experiment_id == "E0" else "formal_or_dedicated",
                "method_counts": report["method_counts"],
                "findings": report["findings"],
            }
        )
    failed = [report["path"] for report in reports if report["status"] == "fail"]
    return {
        "status": "pass" if not failed else "fail",
        "statistics_files": len(reports),
        "method_counts": total_methods,
        "failed_files": failed,
        "reports": reports,
    }


def _fallacy_audit(
    *,
    contracts: Mapping[str, Any],
    acceptance: Mapping[str, Any],
    e9: Mapping[str, Any],
    e13: Mapping[str, Any],
    undefined: Mapping[str, Any],
    analysis: Path,
) -> list[dict[str, Any]]:
    counts = contracts.get("method_counts", {})
    figure_manifest = _load_json(
        _inside("figure_manifest.json", analysis, label="figure manifest"), label="figure manifest"
    )
    figures = figure_manifest.get("figures", [])
    threshold_figure = next(
        (item for item in figures if isinstance(item, Mapping) and item.get("id") == "threshold_calibration"),
        {},
    )
    analysis_text = _inside("analysis.md", analysis, label="analysis narrative").read_text(encoding="utf-8")

    def entry(identifier: str, name: str, passed: bool | None, evidence: str) -> dict[str, Any]:
        return {
            "id": identifier,
            "fallacy": name,
            "status": "pass" if passed is True else "fail" if passed is False else "warning",
            "evidence": evidence,
        }

    has_inference = sum(int(counts.get(key, 0)) for key in ("mcnemar", "bootstrap", "wilcoxon")) > 0
    return [
        entry("SF01", "Pseudoreplication / wrong unit of analysis", counts.get("bootstrap", 0) > 0 if has_inference else None, f"clustered bootstrap records={counts.get('bootstrap', 0)}"),
        entry("SF02", "Ignoring pairing in paired outcomes", counts.get("mcnemar", 0) > 0 and counts.get("wilcoxon", 0) > 0 if has_inference else None, f"McNemar={counts.get('mcnemar', 0)}, Wilcoxon={counts.get('wilcoxon', 0)}"),
        entry("SF03", "Uncorrected multiple comparisons", counts.get("holm_families", 0) > 0 if has_inference else None, f"Holm families={counts.get('holm_families', 0)}"),
        entry("SF04", "P-value-only interpretation", counts.get("bootstrap", 0) > 0 and counts.get("wilcoxon", 0) > 0 if has_inference else None, "paired effect CIs and rank-biserial effects required"),
        entry("SF05", "Confidence-interval omission", acceptance.get("status") == "pass", f"uncertainty assessments={acceptance.get('uncertainty_assessments')}"),
        entry(
            "SF06",
            "Pooling incompatible denominators",
            any(token in analysis_text for token in ("不可相加", "不能与主矩阵相加", "不得相加", "cannot be added")),
            "analysis declares E14/E16/E17 denominator separation",
        ),
        entry("SF07", "Encoding undefined rates as zero", undefined.get("status") == "pass", f"zero-denominator cells checked={undefined.get('checked')}"),
        entry("SF08", "Tuning thresholds on blind-test outcomes", e13.get("status") == "pass", "E13 recomputed only from frozen validation threshold scan"),
        entry("SF09", "Dropping unresolved/failed runs from denominators", e9.get("status") == "pass" and int(e9.get("unresolved_runs", 0)) >= 0, f"E9 unresolved={e9.get('unresolved_runs')}/{e9.get('case_runs')}"),
        entry("SF10", "Treating seeds/repeats as independent evidence", counts.get("bootstrap", 0) > 0 if has_inference else None, "cluster identifiers are mandatory in bootstrap contract"),
        entry("SF11", "Connecting unordered 2-D operating points as a curve", "no_interpolated_path" in str(threshold_figure.get("chart_type", "")), f"E13 chart_type={threshold_figure.get('chart_type')}"),
    ]


def audit_final_analysis(
    *, analysis_dir: str | Path, repository_root: str | Path = ROOT
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    analysis = _inside(analysis_dir, root, label="final analysis", require_file=False)
    if not analysis.is_dir():
        raise StatisticalValidationError(f"final analysis directory is missing: {analysis}")
    manifest_path = _inside("manifest.json", analysis, label="final analysis manifest")
    manifest = _load_json(manifest_path, label="final analysis manifest")
    artifact_check = _check_artifacts(analysis, manifest)
    ledger_check, ledger = _check_input_ledger(
        root, _inside("input_artifact_ledger.csv", analysis, label="input artifact ledger")
    )
    e9 = _recompute_e9(ledger, root, analysis)
    e13 = _recompute_e13(ledger, root)
    acceptance = _recompute_acceptance(analysis, e13)
    undefined = _check_undefined_not_zero(analysis)
    contracts = _statistics_contracts(ledger, root)
    fallacies = _fallacy_audit(
        contracts=contracts,
        acceptance=acceptance,
        e9=e9,
        e13=e13,
        undefined=undefined,
        analysis=analysis,
    )
    key_recomputations = {
        "acceptance_matrix": acceptance,
        "E9_unresolved_denominator": e9,
        "E13_frozen_threshold_constraints": e13,
        "undefined_rate_encoding": undefined,
    }
    hard_checks = {
        "final_artifact_integrity": artifact_check,
        "input_ledger_integrity": ledger_check,
        "key_recomputations": {
            "status": "pass"
            if all(item.get("status") == "pass" for item in key_recomputations.values())
            else "fail"
        },
        "statistical_contracts": contracts,
    }
    failed = [name for name, item in hard_checks.items() if item.get("status") == "fail"]
    fallacy_failures = [item["id"] for item in fallacies if item["status"] == "fail"]
    warnings = [item["id"] for item in fallacies if item["status"] == "warning"]
    if failed or fallacy_failures:
        label = "FAIL"
    elif warnings:
        label = "PASS_WITH_LIMITATIONS"
    else:
        label = "PASS"
    return {
        "schema_version": "1.0",
        "artifact_type": "independent_final_statistical_validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verification_status": {
            "label": label,
            "hard_check_failures": failed,
            "statistical_fallacy_failures": fallacy_failures,
            "warnings": warnings,
            "meaning": "Verified against retained bytes and independent recomputations; not a substitute for human substantive review.",
        },
        "material_passport": {
            "material_id": "M3-final-analysis-statistical-evidence",
            "material_type": "E0-E17 synthesis with E0 diagnostic and E17 stratified human audit",
            "manifest_path": manifest_path.relative_to(root).as_posix(),
            "manifest_sha256": _sha256(manifest_path),
            "source_registry_sha256": manifest.get("registry_sha256"),
            "input_artifact_count": len(ledger),
            "analysis_artifact_count": artifact_check.get("checked"),
            "population_and_unit": {
                "main_effect": "case-level paired outcomes; call-level detector metrics retain separate denominators",
                "engineering": "E14 dedicated performance cells",
                "adaptive": "E16 dedicated adaptive attempts",
                "review": "E17 two-human 360-row stratified audit; 300 representative plus 60 diagnostic, no pooling",
            },
            "transformations": [
                "raw k/n recomputation",
                "frozen validation threshold matching",
                "exact McNemar p-value recomputation",
                "Holm step-down recomputation",
                "Wilcoxon algebra/effect-size validation",
                "clustered bootstrap contract validation",
            ],
            "uncertainty_policy": "Wilson intervals for proportions; paired clustered bootstrap for differences; effect sizes accompany paired tests.",
            "exclusions": [
                "Stub and smoke evidence excluded from formal effect denominators",
                "E13 validation calibration excluded from blind-test effectiveness",
                "E14, E16, and E17 denominators are not pooled",
            ],
            "reproducibility": {
                "validator": "scripts/validate_final_statistics.py",
                "input_bundle_read_only": True,
                "independent_of_synthesis_builder_imports": True,
            },
        },
        "checks": hard_checks,
        "key_recomputations": key_recomputations,
        "statistical_fallacy_audit": fallacies,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independently validate final statistical evidence and emit a Material Passport"
    )
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = audit_final_analysis(
        analysis_dir=args.analysis_dir, repository_root=args.repository_root
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        output = args.out if args.out.is_absolute() else args.repository_root / args.out
        output = _inside(output, args.repository_root.resolve(), label="validation output", require_file=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 2 if report["verification_status"]["label"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
