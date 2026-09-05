import json
from collections import Counter

import pytest

from experiments.paper_v2.e7_confirmation_plan_v1 import (
    build_cases,
    build_plan,
    online_state,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.e7_confirmation_runner_v1 import (
    analyze,
    canary_gate,
    cost_estimate,
    journal_state,
    role_policy,
    run,
    score_proposal,
)
from experiments.paper_v2.official_provider_executor import HTTPResponseEnvelope
from experiments.paper_v2.public_deepseek_client_v1 import (
    PublicDeepSeekJsonOfficialClient,
)
from experiments.paper_v2.public_provider_budget_v1 import PublicProviderBudgetState


def factory(output, *, broken=False):
    policy = role_policy()

    def transport(endpoint, headers, payload, timeout):
        assert endpoint.startswith("https://api.deepseek.com/")
        assert "tools" not in payload and "tool_choice" not in payload
        lines = (
            (output / "raw_records_v1.jsonl").read_text(encoding="utf-8").splitlines()
        )
        last = json.loads(lines[-1])
        assert last["event"] == "request_started"  # pretransport persistence
        assert last["payload_hash"] == sha256_canonical_json(payload)
        index = int(last["case_id"].split("-")[-1])
        case = build_cases()[index]
        text = json.dumps(
            {
                "tool": case["tool"],
                "arguments": case["controller_authorized_arguments"][1],
            }
        )
        return HTTPResponseEnvelope(
            status_code=200,
            headers={},
            body={
                "id": f"official-test-{len(lines)}",
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "message": {"content": "not json" if broken else text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "prompt_cache_hit_tokens": 50,
                    "prompt_cache_miss_tokens": 50,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                },
            },
        )

    return PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-placeholder",
        content_class="synthetic_m3_case",
        budget_state=PublicProviderBudgetState("deepseek", policy),
        policy=policy,
        model_role="primary",
        temperature=0,
        max_tokens=512,
        timeout=90,
        network_consent=False,
        transport=transport,
    )


def test_design_is_balanced_and_no_evaluator_forwarded():
    plan, cases = build_plan(), build_cases()
    assert len(plan) == len({r["work_key"] for r in plan}) == 96
    assert set(Counter((r["granularity"], r["module"]) for r in plan).values()) == {24}
    assert Counter(r["case_type"] for r in plan[:8]) == {"benign_tool": 4, "attack": 4}
    cases[0]["gold"] = "NEVER_FORWARD"
    assert "NEVER_FORWARD" not in json.dumps(online_state(cases[0]))


def test_granularity_and_confirmation_are_separate_factors():
    case = build_cases()[0]
    text = json.dumps(
        {"tool": case["tool"], "arguments": case["controller_authorized_arguments"][1]}
    )
    strict, bounded = (score_proposal(case, work, text) for work in build_plan()[:2])
    assert not any(c["simulated_effect"] for c in strict["confirmation_cells"])
    assert [c["simulated_effect"] for c in bounded["confirmation_cells"]] == [
        True,
        False,
        False,
        False,
    ]
    assert not any(c["unsafe_effect"] for c in bounded["confirmation_cells"])


def test_formal_prefix_then_pending_never_replays(tmp_path):
    def make():
        return factory(tmp_path)

    first = run(canary_only=True, output=tmp_path, client_factory=make)
    assert first["terminal"] == 8 and first["canary_passed"]
    second = run(canary_only=False, output=tmp_path, client_factory=make)
    assert second["executed_this_run"] == 88 and second["terminal"] == 96
    assert (
        run(canary_only=False, output=tmp_path, client_factory=make)[
            "executed_this_run"
        ]
        == 0
    )
    result = analyze(tmp_path)
    assert result["response_bearing"] == 96
    assert result["planned_calls"] == 96
    assert all(r["planned_n"] == 12 for r in result["cells"])


def test_parse_failures_do_not_pass_technical_gate(tmp_path):
    result = run(
        canary_only=True,
        output=tmp_path,
        client_factory=lambda: factory(tmp_path, broken=True),
    )
    assert result["terminal"] == 8 and not result["canary_passed"]
    with pytest.raises(ValueError, match="prefix"):
        run(
            canary_only=False, output=tmp_path, client_factory=lambda: factory(tmp_path)
        )


def test_open_or_duplicate_requests_fail_closed():
    plan = build_plan()
    event = {
        **plan[0],
        "event": "request_started",
        "attempt": 1,
        "request_id": "x",
        "payload_hash": "y",
    }
    with pytest.raises(ValueError, match="open"):
        journal_state([event], plan)
    with pytest.raises(ValueError, match="duplicate"):
        journal_state([event, event], plan)
    assert not canary_gate({}, plan)


def test_current_price_has_weekend_and_peak_boundaries():
    usage = {
        "prompt_tokens": 1_000_000,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 1_000_000,
        "completion_tokens": 0,
    }
    assert cost_estimate(usage, "2026-09-05T03:00:00+00:00") == 4.5
    assert cost_estimate(usage, "2026-09-07T01:00:00+00:00") == 9
    assert cost_estimate(usage, "2026-09-07T04:00:00+00:00") == 4.5
