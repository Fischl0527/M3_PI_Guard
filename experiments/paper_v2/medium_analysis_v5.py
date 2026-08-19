"""Schema-valid closed-diagnostic ITT analysis.

Version 5 supersedes the frozen v4 compatibility attempt.  The diagnostic is
projected into the closed v1 schema using its existing diagnostic-only,
unverified-response vocabulary.  The report, not the record, carries the
explicit no-response disclosure.  Mechanism eligibility uses the separately
verified technical identity policy for formal responses plus the admitted
closed diagnostic, instead of pretending that the failed request produced an
official response attestation.
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
    """Return a schema-valid v1 diagnostic analysis view."""

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
    """Run v3 with the schema-valid diagnostic compatibility view."""

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
