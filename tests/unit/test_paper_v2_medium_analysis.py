from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from experiments.paper_v2.contracts import (
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.medium_analysis import (
    DEFAULT_CASE_INDEX,
    DEFAULT_CASE_MANIFEST,
    DEFAULT_GATE_SPEC,
    MediumAnalysisError,
    analyze_medium_records,
    paired_binary_power_sample_size,
)
from experiments.paper_v2.medium_analysis_v2 import (
    analyze_medium_records_v2,
    project_record_for_primary_analysis,
)


ROOT = Path(__file__).resolve().parents[2]


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _record(case: dict, condition: str, condition_index: int) -> dict:
    case_id = case["case_id"]
    case_type = case["evaluation_case_type"]
    same_type_index = _TYPE_INDEX[(case_type, case_id)]
    if case_type == "attack":
        thresholds = {
            "no_defense": 25,
            "safe_prompt_or_spotlighting": 22,
            "promptguard_detector_only": 21,
            "strongest_peer_reviewed_structural_baseline": 20,
            "m3_policy_only": 18,
            "m3_full": 10,
        }
        unsafe = same_type_index < thresholds[condition]
        task_completion = not unsafe
    else:
        unsafe = False
        threshold = 22 if case_type == "benign_tool" else 11
        task_completion = same_type_index < threshold

    ask = condition == "m3_full" and case_type != "attack" and same_type_index < 4
    projection = {"trusted_request": "synthetic statistical golden case"}
    return {
        "schema_version": "m3-paper-v2-experiment-record-1.0",
        "record_id": f"{case_id}:{condition}",
        "run_id": "synthetic-golden",
        "case_id": case_id,
        "benchmark_id": case["benchmark"],
        "condition_id": condition,
        "evaluation_case_type": case_type,
        "authorization_regime": "auto_compiled",
        "online_visible_field_digest": compute_online_visible_field_digest(
            projection
        ),
        "initial_guard_decision": "ASK" if ask else "ALLOW",
        "effective_decision": "ALLOW",
        "ask_reason": "independent_confirmation_required" if ask else None,
        "confirmation_result": "approved" if ask else "not_requested",
        "unsafe_effect": unsafe,
        "unsafe_effect_itt": unsafe,
        "task_completion": task_completion,
        "operational_status": "completed",
        "included_in_intention_to_treat": True,
        "provider_attestation": {
            "endpoint_type": "official_api",
            "provider_name": "synthetic-provider",
            "upstream_provider": "synthetic-provider",
            "model_id": "synthetic-model",
            "model_revision": "synthetic-model-v1",
            "request_id": f"req-{condition_index}-{same_type_index}",
            "response_id": f"res-{condition_index}-{same_type_index}",
            "requested_at": "2026-07-23T16:30:00+08:00",
            "parameters_sha256": sha256_canonical_json({"temperature": 0}),
            "prompt_rewrite_declaration": "none_declared",
            "identity_evidence": "official_response",
            "identity_verified": True,
            "evidence_level": "formal_candidate",
        },
        "result_tier": "formal_candidate",
        "latency_ms": {"total": 100, "model": 80, "guard": 10, "tool": 10},
        "token_usage": {"input": 100, "output": 20, "total": 120, "available": True},
        "recorded_at": "2026-07-23T16:30:00+08:00",
    }


_INDEX = _jsonl(DEFAULT_CASE_INDEX)
_TYPE_INDEX = {}
for _case_type in ("attack", "benign_tool", "benign_no_tool"):
    _ids = sorted(
        row["case_id"]
        for row in _INDEX
        if row["evaluation_case_type"] == _case_type
    )
    _TYPE_INDEX.update(
        {(_case_type, case_id): index for index, case_id in enumerate(_ids)}
    )


def _complete_records() -> list[dict]:
    conditions = _json(DEFAULT_CASE_MANIFEST)["core_conditions"]
    return [
        _record(case, condition, condition_index)
        for case in _INDEX
        for condition_index, condition in enumerate(conditions)
    ]


def test_paired_power_planning_is_finite_only_for_nonzero_difference() -> None:
    powered = paired_binary_power_sample_size(
        baseline_only_event_probability=0.20,
        treatment_only_event_probability=0.05,
    )
    null = paired_binary_power_sample_size(
        baseline_only_event_probability=0.10,
        treatment_only_event_probability=0.10,
    )

    assert powered["required_pairs"] is not None
    assert powered["required_pairs"] > 0
    assert null["required_pairs"] is None


def test_complete_golden_matrix_passes_mechanism_gate() -> None:
    report = analyze_medium_records(
        _complete_records(),
        case_manifest=_json(DEFAULT_CASE_MANIFEST),
        case_index=_INDEX,
        gate_spec=_json(DEFAULT_GATE_SPEC),
        bootstrap_iterations=100,
    )

    assert report["status"] == "complete"
    assert report["observed_primary_records"] == 432
    assert report["mechanism_paper_gate"]["status"] == "pass"
    assert report["mechanism_paper_gate"]["mechanism_paper_candidate"] is True
    assert report["comparisons"]["security_full_vs_structural"][
        "absolute_difference_treatment_minus_baseline"
    ] < -0.1
    assert report["comparisons"]["security_full_vs_policy_only"][
        "absolute_difference_treatment_minus_baseline"
    ] < 0
    assert all(
        "holm_adjusted_p_value" in comparison["mcnemar"]
        for comparison in report["comparisons"].values()
    )


def test_incomplete_primary_matrix_fails_closed() -> None:
    records = _complete_records()[:-1]

    with pytest.raises(MediumAnalysisError, match="incomplete primary matrix"):
        analyze_medium_records(
            records,
            case_manifest=_json(DEFAULT_CASE_MANIFEST),
            case_index=_INDEX,
            gate_spec=_json(DEFAULT_GATE_SPEC),
            bootstrap_iterations=10,
        )


def test_empty_results_remain_pending_without_triggering_fallback() -> None:
    report = analyze_medium_records(
        [],
        case_manifest=_json(DEFAULT_CASE_MANIFEST),
        case_index=_INDEX,
        gate_spec=_json(DEFAULT_GATE_SPEC),
    )

    assert report["status"] == "results_pending"
    assert report["expected_total_records"] == 480
    assert report["mechanism_paper_gate"]["status"] == "not_evaluated"
    assert report["mechanism_paper_gate"]["fallback_empirical_study_triggered"] is False


def test_v2_analysis_preregisters_secondary_and_regime_metrics() -> None:
    records = _complete_records()
    probes = []
    probe_cases = [row for row in _INDEX if row["regime_probe"]]
    regimes = ("exact_gold", "broad", "underspecified", "conflicting")
    for case_index, case in enumerate(probe_cases):
        regime = regimes[case_index % len(regimes)]
        for condition in ("m3_policy_only", "m3_full"):
            source = next(
                row
                for row in records
                if row["case_id"] == case["case_id"]
                and row["condition_id"] == condition
            )
            probe = deepcopy(source)
            probe["record_id"] = f"{source['record_id']}:{regime}"
            probe["authorization_regime"] = regime
            probes.append(probe)

    report = analyze_medium_records_v2(
        records + probes,
        case_manifest=_json(DEFAULT_CASE_MANIFEST),
        case_index=_INDEX,
        gate_spec=_json(DEFAULT_GATE_SPEC),
        bootstrap_iterations=50,
    )

    assert report["status"] == "complete"
    assert report["primary_analysis"]["observed_primary_records"] == 432
    secondary = report["secondary_analysis"]
    assert secondary["condition_operational_metrics"]["m3_full"][
        "confirmation_burden"
    ]["ask_count"] == 8
    assert secondary["authorization_regime_probes"]["m3_full"][
        "probe_records"
    ] == 24
    assert set(
        secondary["authorization_regime_probes"]["m3_full"]["regimes"]
    ) == set(regimes)
    assert "benchmark" in secondary["heterogeneity"]
    assert secondary["metric_identifiability"]["UTR"]["status"].startswith(
        "not_identifiable"
    )
    assert secondary["metric_identifiability"]["DSR"]["status"].startswith(
        "not_identifiable"
    )


def test_formal_v2_record_projects_to_valid_primary_analysis_view() -> None:
    path = (
        ROOT
        / "outputs/paper_upgrade_v2/formal_pilot/deepseek"
        / "fd89c79707414a035a9d4309c3c3125bde14f7260c0e4c9cd66088164076fbe7"
        / "experiment_record_v2.jsonl"
    )
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    projected = project_record_for_primary_analysis(entry["record"])

    assert projected["schema_version"] == "m3-paper-v2-experiment-record-1.0"
    assert projected["unsafe_effect_itt"] == entry["record"]["unsafe_effect_itt"]
    assert projected["task_completion"] == entry["record"]["task_completion"]
    assert projected["provider_attestation"]["identity_verified"] is True
    assert projected["provider_attestation"]["request_id"].startswith("bundle:")
    assert "provider_trace_bundle" not in projected
    assert "provider_safety_receipt" not in projected
