from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "docs/research/paper_v2/manuscript"


def _json(name: str) -> dict:
    return json.loads((WORKSPACE / name).read_text(encoding="utf-8"))


def test_claim_ledger_keeps_effectiveness_and_blind_claims_locked() -> None:
    ledger = _json("claim_evidence_ledger_v1.json")
    claims = {row["claim_id"]: row for row in ledger["claims"]}

    assert (
        ledger["paper_route"]
        == "authorization_leakage_uncertainty_empirical_fallback"
    )
    assert claims["C03"]["status"] == "forbidden"
    assert (
        claims["C06"]["status"]
        == "verified_for_medium_and_public_primary_with_utility_tradeoff"
    )
    assert claims["C07"]["status"] == "falsified_in_medium_and_public_primary"
    assert claims["C08"]["status"] == "falsified_in_medium_and_public_primary"
    assert claims["C09"]["status"].startswith("partially_verified")
    assert claims["C10"]["status"] == "pending"
    assert claims["C11"]["status"] == "forbidden_pending_human_custodian"
    assert claims["C13"]["status"] == "forbidden"
    assert claims["C23"]["status"] == "verified_primary_model_only"
    assert (
        claims["C24"]["status"]
        == "verified_negative_module_gain_and_utility_noninferiority"
    )
    assert claims["C25"]["status"] == "verified_auditable_correction_chain"


def test_active_lean_claim_ledger_integrates_e1_through_e6_boundaries() -> None:
    ledger = _json("claim_evidence_ledger_lean_v1.json")
    claims = {row["claim_id"]: row for row in ledger["claims"]}

    assert ledger["scope"]["incremental_studies_completed"] == [
        "E1", "E2", "E3", "E4", "E5", "E6"
    ]
    assert ledger["scope"]["gemini_authorization_planned_work_items"] == 450
    assert ledger["scope"]["gemini_authorization_terminal_work_items"] == 32
    assert ledger["scope"]["gemini_authorization_response_bearing_work_items"] == 5
    assert ledger["scope"]["e6_gemini_planned_work_items"] == 180
    assert ledger["scope"]["e6_gemini_scientific_terminal_work_items"] == 6
    assert ledger["scope"]["e6_gemini_response_bearing_work_items"] == 5
    assert ledger["scope"]["e6_gemini_administratively_closed_work_items"] == 174
    assert claims["LC10"]["status"] == "forbidden_after_two_incomplete_gemini_studies"
    assert claims["LC15"]["observed"].startswith(
        "Across 240 unauthorized proposals"
    )
    assert claims["LC17"]["status"] == "verified_conditional_null"
    assert "not a complete B500 panel" in claims["LC17"]["boundary"]
    assert claims["LC18"]["status"] == "verified_deepseek_single_block"
    assert "temporal repeatability" in claims["LC18"]["boundary"]
    assert "47/60 tasks" in claims["LC18"]["observed"]
    assert "original multi-window activity gate" in claims["LC18"]["boundary"]


def _percent(value: float) -> str:
    return f"{100 * value:.2f}%"


def test_results_draft_matches_admitted_medium_analysis() -> None:
    text = (WORKSPACE / "results_shell.md").read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())
    analysis_path = (
        ROOT
        / "outputs/paper_upgrade_v2/formal_medium/deepseek"
        / "ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373"
        / "admitted_medium_analysis_v8.json"
    )
    analysis_bytes = analysis_path.read_bytes()
    admitted = json.loads(analysis_bytes)
    primary = admitted["analysis"]["primary_analysis"]
    secondary = admitted["analysis"]["secondary_analysis"]

    assert (
        hashlib.sha256(analysis_bytes).hexdigest()
        == "ea3d6197b0f97b5057b1d0f9fff054f3ae43743eb9cb85eb4122b6c152d7e041"
    )
    assert admitted["status"] == "complete"
    assert admitted["result_admission_sha256"] not in text
    assert primary["mechanism_paper_gate"]["status"] == "fail_redirect"
    assert "did not support a superiority claim" in normalized_text

    labels = {
        "no_defense": "No defense",
        "safe_prompt_or_spotlighting": "Safe prompt / spotlighting",
        "promptguard_detector_only": "PromptGuard (detector-only)",
        "strongest_peer_reviewed_structural_baseline": "Structural baseline",
        "m3_policy_only": "Policy package (`m3_policy_only`)",
        "m3_full": "Full package (`m3_full`)",
    }
    for condition, label in labels.items():
        metrics = primary["condition_metrics"][condition]
        security = metrics["unsafe_effect_itt"]
        utility = metrics["benign_tool_tcr"]
        expected = (
            f"| {label} | {security['numerator']}/{security['denominator']} | "
            f"{_percent(security['value'])} "
            f"({_percent(security['ci_low'])[:-1]}–"
            f"{_percent(security['ci_high'])[:-1]}) | "
            f"{utility['numerator']}/{utility['denominator']} | "
            f"{_percent(utility['value'])} "
            f"({_percent(utility['ci_low'])[:-1]}–"
            f"{_percent(utility['ci_high'])[:-1]}) | 12/12 |"
        )
        assert expected in text

        operations = secondary["condition_operational_metrics"][condition]
        failures = sum(
            count
            for status, count in operations["operational_status_counts"].items()
            if status != "completed"
        )
        operational_label = {
            "m3_policy_only": "Policy package",
            "m3_full": "Full package",
        }.get(condition, label)
        operational_prefix = (
            f"| {operational_label} | {operations['confirmation_burden']['ask_count']} | "
            f"{_percent(operations['ask_rate_benign']['value'])} | "
            f"{failures} | {operations['provider_calls']['sum']} | "
            f"{operations['provider_cost_cny']['sum']:.7f} |"
        )
        assert operational_prefix in text

    assert "all Gemini effects are not estimable" in normalized_text
    assert "do not support a defense-superiority or SOTA claim" in normalized_text


def test_methods_references_existing_frozen_artifacts() -> None:
    required = (
        "protocols/paper_upgrade_v2/preregistration_v1.json",
        "protocols/paper_upgrade_v2/structural_baseline_registry_v1.json",
        "protocols/paper_upgrade_v2/medium_case_manifest_v1.json",
        "protocols/paper_upgrade_v2/medium_case_index_v1.jsonl",
    )

    assert all((ROOT / path).is_file() for path in required)


def test_completion_scorecard_separates_code_from_scientific_evidence() -> None:
    scorecard = _json("completion_scorecard_v1.json")

    assert scorecard["engineering_readiness_percent"] >= 80
    assert (
        scorecard["engineering_readiness_percent"]
        > scorecard["scientific_evidence_completion_percent"]
    )
    assert 50 <= scorecard["scientific_evidence_completion_percent"] < 80
    assert (
        scorecard["paper_submission_readiness_percent"]
        <= scorecard["scientific_evidence_completion_percent"]
    )
    assert scorecard["paper_submission_readiness_percent"] < 80
    assert "remain incomplete" in scorecard["no_false_completion_rule"]


def test_post_public_scorecard_preserves_incomplete_external_gates() -> None:
    scorecard = _json("completion_scorecard_v2.json")
    points = sum(
        row["scientific_evidence_completion_points"]
        for row in scorecard["workstreams"]
    )

    assert points == scorecard["scientific_evidence_completion_points"] == 869
    assert scorecard["scientific_evidence_completion_percent_exact"] == 72.4167
    assert scorecard["scientific_evidence_completion_percent"] < 80
    assert scorecard["admitted_public_primary"]["records"] == 5082
    assert scorecard["admitted_public_primary"]["diagnostic_records"] == 76
    assert "independent blind-set author/custodian" in scorecard[
        "blocking_external_inputs"
    ]


def test_evidence_80_v3_arithmetic_and_scorecard_binding() -> None:
    scorecard_path = WORKSPACE / "completion_scorecard_v1.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    roadmap_path = (
        ROOT
        / "protocols/paper_upgrade_v2/evidence_80_execution_roadmap_v3.json"
    )
    roadmap = json.loads(roadmap_path.read_text(encoding="utf-8"))

    baseline = roadmap["baseline"]
    target = roadmap["target"]
    route = roadmap["score_route"]
    current_sum = sum(row["current"] for row in route)
    target_sum = sum(row["target"] for row in route)
    increment_sum = sum(row["increment"] for row in route)

    assert baseline["scorecard_sha256"] == (
        "82fc6248abe569ba221d3c435c45e909e4571d946c62ec763a4d2c943e55c3ea"
    )
    assert roadmap["historical_v2_immutability"] is True
    assert baseline["scientific_points"] == current_sum == 753
    assert scorecard["scientific_evidence_completion_points"] == current_sum
    assert target["scientific_points"] == target_sum == 968
    assert target_sum - current_sum == increment_sum == 215
    assert roadmap["arithmetic_controls"]["baseline_sum"] == current_sum
    assert roadmap["arithmetic_controls"]["target_sum"] == target_sum
    assert roadmap["experiment_execution_authorized"] is False
