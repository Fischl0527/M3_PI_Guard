from __future__ import annotations

import experiments.paper_v2.lean_authorization_analysis as analysis


def _row(
    case_id: str,
    condition: str,
    regime: str,
    value: bool,
    *,
    benchmark: str = "agentdojo-v1",
    status: str = "completed",
) -> dict:
    return {
        "case_id": case_id,
        "condition_id": condition,
        "authorization_regime": regime,
        "benchmark": benchmark,
        "evaluation_case_type": "attack",
        "unsafe_effect": value,
        "task_completion": False,
        "operational_status": status,
    }


def _provider_plan_row(work_key: str, sequence: int) -> dict:
    return {
        "work_key": work_key,
        "case_id": f"case-{sequence}",
        "benchmark": "agentdojo-v1",
        "condition_id": "m3_full",
        "authorization_regime": "auto_compiled",
        "provider_id": "gemini",
        "model_id": "gemini-3.6-flash",
        "sequence": sequence,
    }


def _provider_raw_row(
    planned: dict,
    *,
    terminal: bool,
    response_id: str | None,
    status: str,
) -> dict:
    return {
        **{
            field: planned[field]
            for field in (
                "work_key",
                "case_id",
                "benchmark",
                "condition_id",
                "authorization_regime",
                "provider_id",
            )
        },
        "configured_model": planned["model_id"],
        "attempt": 1,
        "online_forbidden_fields_present": False,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "retry_eligible": not terminal,
        "included_in_primary_itt": terminal,
        "provider_requests": (
            [{"provider_response_id": response_id}] if response_id else []
        ),
        "response_obtained": response_id is not None,
        "returned_models": [planned["model_id"]] if response_id else [],
        "operational_status": status,
    }


def test_latest_attempts_keep_raw_recovery_but_select_latest_terminal() -> None:
    rows = [
        {"work_key": "a", "attempt": 1, "response_obtained": False},
        {"work_key": "b", "attempt": 1, "response_obtained": True},
        {"work_key": "a", "attempt": 2, "response_obtained": True},
    ]
    latest, summary = analysis._latest_attempts(rows)
    assert set(latest) == {"a", "b"}
    assert latest["a"]["attempt"] == 2
    assert summary["raw_attempt_rows"] == 3
    assert summary["superseded_attempt_rows"] == 1


def test_exact_mcnemar_is_two_sided_and_exact() -> None:
    assert analysis._exact_mcnemar(0, 0) == 1.0
    assert analysis._exact_mcnemar(0, 5) == 0.0625
    assert analysis._exact_mcnemar(1, 4) == 0.375


def test_paired_stats_report_direction_and_discordance(monkeypatch) -> None:
    monkeypatch.setattr(analysis, "BOOTSTRAP_REPLICATES", 100)
    first = ("m3_policy_only", "auto_compiled")
    second = ("m3_full", "auto_compiled")
    rows = [
        _row("a", *first, False),
        _row("a", *second, True),
        _row("b", *first, False),
        _row("b", *second, False),
        _row("c", *first, True),
        _row("c", *second, False),
    ]
    result = analysis._paired_stats(
        rows,
        first=first,
        second=second,
        case_type="attack",
        endpoint="unsafe_effect",
    )
    assert result["paired_cases"] == 3
    assert result["absolute_difference_second_minus_first"] == 0.0
    assert result["discordant_first_only"] == 1
    assert result["discordant_second_only"] == 1
    assert result["exact_mcnemar_p"] == 1.0
    assert result["cluster_bootstrap"]["replicates"] == 100


def test_holm_adjustment_is_monotone_in_sorted_p_values() -> None:
    adjusted = analysis._holm({"a": 0.01, "b": 0.03, "c": 0.2, "d": 0.8})
    assert adjusted == {"a": 0.04, "b": 0.09, "c": 0.4, "d": 0.8}


def test_deepseek_only_defers_gemini_without_cross_vendor_claim(monkeypatch) -> None:
    plan_rows = [
        {"provider_id": "deepseek", "work_key": "d"},
        {"provider_id": "gemini", "work_key": "g"},
    ]
    deepseek_records = [_row("case", "m3_full", "auto_compiled", False)]
    monkeypatch.setattr(analysis, "_read_jsonl", lambda path: plan_rows)
    monkeypatch.setattr(
        analysis,
        "_validate_provider",
        lambda provider, plan, raw, allow_partial, paused_work_keys: (
            deepseek_records,
            {"terminal_work_items": analysis.EXPECTED_COUNTS["deepseek"]},
        ),
    )
    monkeypatch.setattr(analysis, "_condition_metrics", lambda rows: {})
    monkeypatch.setattr(
        analysis,
        "_comparisons",
        lambda rows, comparisons: (
            {}
            if rows
            else (_ for _ in ()).throw(
                AssertionError("pending Gemini comparisons must not run")
            )
        ),
    )
    monkeypatch.setattr(analysis, "_regime_extension", lambda rows: {})
    monkeypatch.setattr(analysis, "_failure_sensitive_security", lambda *args: {})
    monkeypatch.setattr(
        analysis, "_benchmark_stratified_comparisons", lambda *args: {}
    )
    monkeypatch.setattr(analysis, "_burden", lambda rows: {})
    monkeypatch.setattr(analysis, "_burden_by_case_and_benchmark", lambda rows: {})
    monkeypatch.setattr(analysis, "_heterogeneity", lambda rows: {})

    result = analysis.build_analysis(deepseek_only=True)

    assert result["analysis_policy"]["deepseek_only"] is True
    assert result["integrity"]["gemini"]["status"] == (
        "not_analyzed_pending_provider_completion"
    )
    assert result["gemini"]["condition_metrics"] == {}
    assert result["gemini"]["cross_vendor_claim_eligible"] is False


def test_partial_provider_keeps_only_terminal_rows_for_analysis() -> None:
    terminal_plan = _provider_plan_row("g-terminal", 1)
    recoverable_plan = _provider_plan_row("g-recoverable", 2)
    records, integrity = analysis._validate_provider(
        "gemini",
        [terminal_plan, recoverable_plan],
        [
            _provider_raw_row(
                terminal_plan,
                terminal=True,
                response_id="response-1",
                status="completed",
            ),
            _provider_raw_row(
                recoverable_plan,
                terminal=False,
                response_id=None,
                status="pre_response_rate_limited",
            ),
        ],
        allow_partial=True,
    )

    assert [row["work_key"] for row in records] == ["g-terminal"]
    assert integrity["expected_work_items"] == 450
    assert integrity["observed_work_items"] == 2
    assert integrity["terminal_work_items"] == 1
    assert integrity["pending_work_items"] == 449
    assert integrity["unstarted_work_items"] == 448
    assert integrity["nonterminal_observed_work_items"] == 1
    assert integrity["response_bearing_work_items"] == 1
    assert integrity["operational_statuses"] == {"completed": 1}
    assert integrity["observed_operational_statuses"] == {
        "completed": 1,
        "pre_response_rate_limited": 1,
    }


def test_partial_provider_reuses_runner_pause_normalization() -> None:
    planned = _provider_plan_row("g-paused", 1)
    physical = _provider_raw_row(
        planned,
        terminal=True,
        response_id=None,
        status="repeated_pre_response_failure",
    )
    physical["attempt"] = 2

    records, integrity = analysis._validate_provider(
        "gemini",
        [planned],
        [physical],
        allow_partial=True,
        paused_work_keys={"g-paused"},
    )

    assert records == []
    assert integrity["terminal_work_items"] == 0
    assert integrity["nonterminal_observed_work_items"] == 1
    assert integrity["observed_operational_statuses"] == {
        "pre_response_rate_limited": 1
    }


def test_partial_gemini_defers_paired_inference(monkeypatch) -> None:
    plan_rows = [
        {"provider_id": "deepseek", "work_key": "d"},
        {"provider_id": "gemini", "work_key": "g"},
    ]
    deepseek_records = [_row("deepseek", "m3_full", "auto_compiled", False)]
    gemini_records = [_row("gemini", "m3_full", "auto_compiled", False)]
    monkeypatch.setattr(analysis, "_read_jsonl", lambda path: plan_rows)

    def validate(provider, plan, raw, allow_partial, paused_work_keys):
        if provider == "deepseek":
            return deepseek_records, {"terminal_work_items": 900}
        return gemini_records, {"terminal_work_items": 1}

    monkeypatch.setattr(analysis, "_validate_provider", validate)
    monkeypatch.setattr(analysis, "_condition_metrics", lambda rows: {})

    def comparisons(rows, definitions):
        if definitions is analysis.GEMINI_COMPARISONS:
            raise AssertionError("partial Gemini comparisons must not run")
        return {}

    monkeypatch.setattr(analysis, "_comparisons", comparisons)
    monkeypatch.setattr(analysis, "_regime_extension", lambda rows: {})
    monkeypatch.setattr(analysis, "_failure_sensitive_security", lambda *args: {})
    monkeypatch.setattr(
        analysis, "_benchmark_stratified_comparisons", lambda *args: {}
    )
    monkeypatch.setattr(analysis, "_burden", lambda rows: {})
    monkeypatch.setattr(analysis, "_burden_by_case_and_benchmark", lambda rows: {})
    monkeypatch.setattr(analysis, "_heterogeneity", lambda rows: {})

    result = analysis.build_analysis(allow_partial_gemini=True)

    assert result["gemini"]["analysis_status"] == "diagnostic_partial"
    assert result["gemini"]["cross_vendor_claim_eligible"] is False
    assert result["gemini"]["comparisons"] == {}


def test_complete_gemini_enables_cross_vendor_comparisons(monkeypatch) -> None:
    plan_rows = [
        {"provider_id": "deepseek", "work_key": "d"},
        {"provider_id": "gemini", "work_key": "g"},
    ]
    monkeypatch.setattr(analysis, "_read_jsonl", lambda path: plan_rows)

    def validate(provider, plan, raw, allow_partial, paused_work_keys):
        terminal = analysis.EXPECTED_COUNTS[provider]
        return [_row(provider, "m3_full", "auto_compiled", False)], {
            "terminal_work_items": terminal
        }

    monkeypatch.setattr(analysis, "_validate_provider", validate)
    monkeypatch.setattr(analysis, "_condition_metrics", lambda rows: {})
    monkeypatch.setattr(
        analysis,
        "_comparisons",
        lambda rows, definitions: {
            "provider": (
                "gemini"
                if definitions is analysis.GEMINI_COMPARISONS
                else "deepseek"
            )
        },
    )
    monkeypatch.setattr(analysis, "_regime_extension", lambda rows: {})
    monkeypatch.setattr(analysis, "_failure_sensitive_security", lambda *args: {})
    monkeypatch.setattr(
        analysis, "_benchmark_stratified_comparisons", lambda *args: {}
    )
    monkeypatch.setattr(analysis, "_burden", lambda rows: {})
    monkeypatch.setattr(analysis, "_burden_by_case_and_benchmark", lambda rows: {})
    monkeypatch.setattr(analysis, "_heterogeneity", lambda rows: {})

    result = analysis.build_analysis(allow_partial_gemini=True)

    assert result["gemini"]["analysis_status"] == "complete"
    assert result["gemini"]["cross_vendor_claim_eligible"] is True
    assert result["gemini"]["comparisons"] == {"provider": "gemini"}


def test_burden_distinguishes_event_counts_from_record_incidence() -> None:
    rows = [
        {
            "condition_id": "m3_full",
            "authorization_regime": "exact_gold",
            "ask_count": 0,
            "deny_count": 3,
            "operational_status": "completed",
            "latency_ms": {"total": 10},
            "token_usage": {"total": 20},
            "cost": {"amount": 0.1, "currency": "CNY"},
        },
        {
            "condition_id": "m3_full",
            "authorization_regime": "exact_gold",
            "ask_count": 2,
            "deny_count": 0,
            "operational_status": "parse_failure",
            "latency_ms": {"total": 20},
            "token_usage": {"total": 30},
            "cost": {"amount": 0.2, "currency": "CNY"},
        },
    ]

    result = analysis._burden(rows)["m3_full__exact_gold"]

    assert result["ask_count"] == 2
    assert result["deny_count"] == 3
    assert result["ask_record_count"] == 1
    assert result["deny_record_count"] == 1
    assert result["ask_record_rate"] == 0.5
    assert result["deny_record_rate"] == 0.5
    assert result["mean_ask_events_per_record"] == 1.0
    assert result["mean_deny_events_per_record"] == 1.5
    assert result["failure_rate"] == 0.5


def test_failure_sensitive_endpoint_keeps_failure_distinct_from_unsafe() -> None:
    first = ("m3_policy_only", "auto_compiled")
    second = ("m3_policy_only", "exact_gold")
    rows = [
        _row("a", *first, False),
        _row("a", *second, False, status="parse_failure"),
        _row("b", *first, True),
        _row("b", *second, False),
    ]

    result = analysis._failure_sensitive_security(
        rows, (("policy_auto_to_exact", first, second),)
    )

    first_rate = result["condition_rates"]["m3_policy_only__auto_compiled"]
    second_rate = result["condition_rates"]["m3_policy_only__exact_gold"]
    paired = result["paired_comparisons"]["policy_auto_to_exact"]
    assert first_rate["unsafe_effects"] == 1
    assert first_rate["operational_failures"] == 0
    assert second_rate["unsafe_effects"] == 0
    assert second_rate["operational_failures"] == 1
    assert paired["absolute_difference_second_minus_first"] == 0.0
    assert "not relabeled" in result["interpretation"]


def test_benchmark_stratification_preserves_direction_reversal() -> None:
    first = ("m3_policy_only", "auto_compiled")
    second = ("m3_policy_only", "exact_gold")
    rows = []
    for benchmark, first_value, second_value in (
        ("agentdojo-v1", False, True),
        ("m3-v2", True, False),
    ):
        for case_id in ("a", "b"):
            first_row = _row(
                f"{benchmark}-{case_id}", *first, False, benchmark=benchmark
            )
            second_row = _row(
                f"{benchmark}-{case_id}", *second, False, benchmark=benchmark
            )
            first_row["evaluation_case_type"] = "benign_tool"
            second_row["evaluation_case_type"] = "benign_tool"
            first_row["task_completion"] = first_value
            second_row["task_completion"] = second_value
            rows.extend((first_row, second_row))
        for case_id in ("attack-a", "attack-b"):
            rows.extend(
                (
                    _row(
                        f"{benchmark}-{case_id}",
                        *first,
                        False,
                        benchmark=benchmark,
                    ),
                    _row(
                        f"{benchmark}-{case_id}",
                        *second,
                        False,
                        benchmark=benchmark,
                    ),
                )
            )

    result = analysis._benchmark_stratified_comparisons(
        rows, (("policy_auto_to_exact", first, second),)
    )

    assert (
        result["agentdojo-v1"]["benign_tool_tcr"]["policy_auto_to_exact"][
            "absolute_difference_second_minus_first"
        ]
        == 1.0
    )
    assert (
        result["m3-v2"]["benign_tool_tcr"]["policy_auto_to_exact"][
            "absolute_difference_second_minus_first"
        ]
        == -1.0
    )


def test_burden_stratification_keeps_case_type_and_benchmark() -> None:
    rows = []
    for case_type, benchmark in (
        ("attack", "agentdojo-v1"),
        ("benign_tool", "m3-v2"),
    ):
        rows.append(
            {
                "condition_id": "m3_full",
                "authorization_regime": "auto_compiled",
                "evaluation_case_type": case_type,
                "benchmark": benchmark,
                "ask_count": 1,
                "deny_count": 0,
                "operational_status": "completed",
                "latency_ms": {"total": 10},
                "token_usage": {"total": 20},
                "cost": {"amount": 0.1, "currency": "CNY"},
            }
        )

    result = analysis._burden_by_case_and_benchmark(rows)

    assert len(result) == 2
    assert {
        (item["case_type"], item["benchmark"]) for item in result.values()
    } == {("attack", "agentdojo-v1"), ("benign_tool", "m3-v2")}
