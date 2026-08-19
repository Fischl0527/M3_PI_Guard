from __future__ import annotations

import math

import experiments.paper_v2.public_primary_analysis_review_v1 as review


def _record(
    *,
    case_id: str,
    condition: str,
    case_type: str,
    event: bool,
) -> dict:
    return {
        "case_id": case_id,
        "condition_id": condition,
        "evaluation_case_type": case_type,
        "unsafe_effect_itt": event if case_type == "attack" else False,
        "task_completion": event if case_type != "attack" else False,
    }


def test_independent_wilson_matches_known_boundary() -> None:
    rate, low, high = review._independent_wilson(0, 36)

    assert rate == 0.0
    assert low == 0.0
    assert math.isclose(high, 0.0964186286, rel_tol=1e-8)


def test_exact_mcnemar_is_two_sided_and_tracks_direction() -> None:
    result = review._exact_mcnemar(
        [True, True, True, False],
        [False, False, False, True],
    )

    assert result == {
        "baseline_only_event": 3,
        "treatment_only_event": 1,
        "discordant_pairs": 4,
        "p_value": 0.625,
    }


def test_paired_summary_uses_case_matched_records_only() -> None:
    records = [
        _record(
            case_id="case-1",
            condition="baseline",
            case_type="attack",
            event=True,
        ),
        _record(
            case_id="case-1",
            condition="treatment",
            case_type="attack",
            event=False,
        ),
        _record(
            case_id="case-2",
            condition="baseline",
            case_type="attack",
            event=False,
        ),
        _record(
            case_id="case-2",
            condition="treatment",
            case_type="attack",
            event=True,
        ),
        _record(
            case_id="unpaired",
            condition="baseline",
            case_type="attack",
            event=True,
        ),
    ]

    result = review._paired_summary(
        records,
        baseline="baseline",
        treatment="treatment",
        case_type="attack",
        field="unsafe_effect_itt",
    )

    assert result["pairs"] == 2
    assert result["baseline_events"] == 1
    assert result["treatment_events"] == 1
    assert result["absolute_difference_treatment_minus_baseline"] == 0.0
    assert result["mcnemar"]["p_value"] == 1.0
