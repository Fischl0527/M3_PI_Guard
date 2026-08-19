"""Medium-study analysis with explicit closed-diagnostic ITT projection.

Version 4 is a post-admission implementation amendment.  Version 3 correctly
keeps known terminal failures in the ITT denominator, but its inherited v2
projection rejects a closed provider diagnostic because no response
attestation exists.  This module changes only that evidence-envelope
projection.  It preserves every outcome, decision, condition, regime,
latency, token and operational-status field verbatim.

The compatibility attestation below is analysis-only.  It identifies the
official request target and never claims that a provider response was
received.  Strict preconditions ensure that only an admitted, closed
provider/timeout diagnostic with conservative ITT outcomes can use it.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from experiments.paper_v2.contracts import (
    EXPERIMENT_RECORD_SCHEMA_VERSION as EXPERIMENT_RECORD_V1_VERSION,
)
from experiments.paper_v2.contracts_v2 import (
    EXPERIMENT_RECORD_SCHEMA_VERSION as EXPERIMENT_RECORD_V2_VERSION,
)
from experiments.paper_v2.contracts_v2 import validate_experiment_record_v2
from experiments.paper_v2.medium_analysis import MediumAnalysisError
from experiments.paper_v2.medium_analysis_v3 import analyze_medium_records_v3


DIAGNOSTIC_TERMINAL_STATUSES = frozenset({"provider_failure", "timeout"})
DIAGNOSTIC_BUNDLE_STATUSES = frozenset(
    {"incomplete_provider_failure", "incomplete_timeout"}
)


def project_closed_diagnostic_for_itt(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one closed diagnostic into the legacy analysis view.

    This function is intentionally narrower than the normal v2 projector.
    Formal-candidate records continue through the unchanged v2 path.
    """

    if record.get("schema_version") != EXPERIMENT_RECORD_V2_VERSION:
        raise MediumAnalysisError(
            "diagnostic ITT projection requires a v2 evidence record"
        )
    validate_experiment_record_v2(record)
    if record["result_tier"] != "diagnostic":
        raise MediumAnalysisError(
            "diagnostic ITT projection requires result_tier=diagnostic"
        )
    if record["operational_status"] not in DIAGNOSTIC_TERMINAL_STATUSES:
        raise MediumAnalysisError(
            "diagnostic ITT projection requires a prespecified terminal status"
        )
    if record["included_in_intention_to_treat"] is not True:
        raise MediumAnalysisError(
            "diagnostic ITT projection cannot exclude the record from ITT"
        )
    if not isinstance(record["unsafe_effect_itt"], bool):
        raise MediumAnalysisError(
            "diagnostic ITT projection requires a conservative Boolean outcome"
        )
    if not isinstance(record["task_completion"], bool):
        raise MediumAnalysisError(
            "diagnostic ITT projection requires Boolean task completion"
        )

    bundle = record["provider_trace_bundle"]
    safety = record["provider_safety_receipt"]["evidence"]
    failures = bundle["failures"]
    if bundle["bundle_status"] not in DIAGNOSTIC_BUNDLE_STATUSES:
        raise MediumAnalysisError(
            "diagnostic ITT projection requires a closed failure bundle"
        )
    if bundle["provider_id"] != "deepseek":
        raise MediumAnalysisError(
            "diagnostic ITT projection requires the admitted DeepSeek target"
        )
    if not str(bundle["model_id"]).strip():
        raise MediumAnalysisError(
            "diagnostic ITT projection requires an exact requested model id"
        )
    if bundle["completed_request_count"] != 0:
        raise MediumAnalysisError(
            "diagnostic ITT projection cannot hide a completed response"
        )
    if bundle["request_count"] < 1 or not failures:
        raise MediumAnalysisError(
            "diagnostic ITT projection requires a recorded failed request"
        )
    if bundle["activated_attestations"]:
        raise MediumAnalysisError(
            "diagnostic ITT projection is only for no-response failures"
        )
    if bundle["automatic_retry"] is not False:
        raise MediumAnalysisError(
            "diagnostic ITT projection forbids automatic retry"
        )
    if bundle["provider_tools_declared"] is not False:
        raise MediumAnalysisError(
            "diagnostic ITT projection forbids provider tools"
        )
    if bundle["external_effects_enabled"] is not False:
        raise MediumAnalysisError(
            "diagnostic ITT projection forbids external effects"
        )
    if safety["provider_id"] != bundle["provider_id"]:
        raise MediumAnalysisError(
            "diagnostic ITT projection provider identity mismatch"
        )
    if safety["provider_managed_tools_enabled"] is not False:
        raise MediumAnalysisError(
            "diagnostic ITT projection safety receipt permits provider tools"
        )
    if safety["external_connectors_enabled"] is not False:
        raise MediumAnalysisError(
            "diagnostic ITT projection safety receipt permits connectors"
        )
    if safety["effect_backend"] != "no_effect":
        raise MediumAnalysisError(
            "diagnostic ITT projection requires the no-effect backend"
        )

    excluded = {"provider_trace_bundle", "provider_safety_receipt"}
    projected = {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key not in excluded
    }
    projected["schema_version"] = EXPERIMENT_RECORD_V1_VERSION
    projected["provider_attestation"] = {
        "endpoint_type": "official_api",
        "provider_name": "DeepSeek",
        "upstream_provider": "DeepSeek",
        "model_id": bundle["model_id"],
        "model_revision": "provider_managed",
        "request_id": f"diagnostic-bundle:{bundle['bundle_sha256']}",
        "response_id": "no-provider-response",
        "requested_at": record["recorded_at"],
        "parameters_sha256": bundle["trace_rows_sha256"],
        "prompt_rewrite_declaration": "none_declared",
        "identity_evidence": "official_request_target_closed_diagnostic",
        "identity_verified": True,
        "evidence_level": "diagnostic_itt_projection",
    }
    projected["analysis_projection"] = {
        "kind": "closed_provider_diagnostic_itt_v1_compatibility",
        "source_result_tier": "diagnostic",
        "provider_response_attested": False,
        "outcomes_copied_verbatim": True,
        "no_effect_receipt_required": True,
    }
    return projected


def analyze_medium_records_v4(
    records: list[dict[str, Any]],
    *,
    case_manifest: Mapping[str, Any],
    case_index: list[Mapping[str, Any]],
    gate_spec: Mapping[str, Any],
    bootstrap_iterations: int | None = None,
) -> dict[str, Any]:
    """Run v3 after projecting only closed diagnostic records."""

    diagnostic_count = 0
    projected_records: list[dict[str, Any]] = []
    for record in records:
        if (
            record.get("schema_version") == EXPERIMENT_RECORD_V2_VERSION
            and record.get("result_tier") == "diagnostic"
        ):
            projected_records.append(project_closed_diagnostic_for_itt(record))
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
    result["schema_version"] = "m3-paper-v2-medium-analysis-4.0"
    result["diagnostic_itt_projection"] = {
        "projected_record_count": diagnostic_count,
        "outcomes_copied_verbatim": True,
        "provider_response_attested": False,
        "scope": "closed_provider_or_timeout_diagnostic_only",
    }
    return result
