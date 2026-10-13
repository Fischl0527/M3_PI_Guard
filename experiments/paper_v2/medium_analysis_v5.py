"""符合 Schema 规范校验的关闭诊断性 ITT 分析模块。

确保分析输出严格遵循 `experiment_record_v1.schema.json` 架构。
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from experiments.paper_v2.contracts_v2 import (
    EXPERIMENT_RECORD_SCHEMA_VERSION as EXPERIMENT_RECORD_V2_VERSION,
)
from experiments.paper_v2.medium_analysis_v3 import analyze_medium_records_v3
from experiments.paper_v2.medium_analysis_v4 import (
    project_closed_diagnostic_for_itt,
)


def project_closed_diagnostic_for_itt_v5(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """返回符合 Schema 规范的 v1 诊断分析视图。"""

    projected = project_closed_diagnostic_for_itt(record)
    projected.pop("analysis_projection")
    attestation = projected["provider_attestation"]
    attestation.update(
        {
            "response_id": None,
            "identity_evidence": "unverified",
            "identity_verified": False,
            "evidence_level": "diagnostic_only",
        }
    )
    return projected


def analyze_medium_records_v5(
    records: list[dict[str, Any]],
    *,
    case_manifest: Mapping[str, Any],
    case_index: list[Mapping[str, Any]],
    gate_spec: Mapping[str, Any],
    technical_identity_policy_satisfied: bool,
    bootstrap_iterations: int | None = None,
) -> dict[str, Any]:
    """使用符合 Schema 规范的诊断兼容性视图运行 v3。"""

    diagnostic_count = 0
    projected_records: list[dict[str, Any]] = []
    for record in records:
        if (
            record.get("schema_version") == EXPERIMENT_RECORD_V2_VERSION
            and record.get("result_tier") == "diagnostic"
        ):
            projected_records.append(
                project_closed_diagnostic_for_itt_v5(record)
            )
            diagnostic_count += 1
        else:
            projected_records.append(copy.deepcopy(record))

    report = analyze_medium_records_v3(
        projected_records,
        case_manifest=case_manifest,
        case_index=case_index,
        gate_spec=gate_spec,
        bootstrap_iterations=bootstrap_iterations,
    )
    result = copy.deepcopy(report)
    result["schema_version"] = "m3-paper-v2-medium-analysis-5.0"
    result["diagnostic_itt_projection"] = {
        "projected_record_count": diagnostic_count,
        "outcomes_copied_verbatim": True,
        "provider_response_attested": False,
        "analysis_view_identity_evidence": "unverified",
        "analysis_view_evidence_level": "diagnostic_only",
        "scope": "closed_provider_or_timeout_diagnostic_only",
    }
    result["technical_identity_policy_satisfied"] = (
        technical_identity_policy_satisfied
    )
    if result["status"] != "complete":
        return result

    mechanism = result["primary_analysis"]["mechanism_paper_gate"]
    checks = mechanism["checks"]
    checks["legacy_all_rows_have_response_attestation"] = checks.pop(
        "auditable_provider"
    )
    checks["admitted_technical_identity_policy"] = (
        technical_identity_policy_satisfied
    )
    claim_checks = {
        key: value
        for key, value in checks.items()
        if key
        not in {
            "legacy_zero_operational_failures_observed",
            "legacy_all_rows_have_response_attestation",
        }
    }
    eligible = all(bool(value) for value in claim_checks.values())
    mechanism["status"] = "pass" if eligible else "fail_redirect"
    mechanism["mechanism_paper_candidate"] = eligible
    mechanism["fallback_empirical_study_triggered"] = not eligible
    mechanism["provider_identity_interpretation"] = (
        "Formal response bundles require exact official identity. The closed "
        "diagnostic remains in ITT with diagnostic-only response evidence; "
        "the separately frozen technical gate controls identity eligibility."
    )
    return result
