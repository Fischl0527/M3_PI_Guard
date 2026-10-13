"""零网络开销下的在线单次调用 v2 证据端到端合格性验证。

离线模拟提供商响应，验证追踪数据解析器的鲁棒性。
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    CONDITION_PROFILES,
    ConditionExecutorShell,
    OnlineExecutorContext,
)
from experiments.paper_v2.formal_record_store import _load_plan
from experiments.paper_v2.formal_record_store_v2 import (
    append_execution_result,
    load_record_entries,
    validate_record_entries,
)
from experiments.paper_v2.live_condition_runtime import (
    EffectBackend,
    LiveConditionRuntime,
    M3SandboxEffectBackend,
    _QualificationEvaluator,
)
from experiments.paper_v2.medium_runtime import (
    reconstruct_initial_online_state,
)
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    _as_official_receipt,
)
from experiments.paper_v2.structural_baselines import VigilRuntimeAdapter
from experiments.paper_v2.vigil_live_dependency import VigilPreparation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/provider_trace_runtime_qualification_v2.json"
)
DEFAULT_BUDGET_POLICY = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"
)
SCHEMA_VERSION = "m3-paper-v2-provider-trace-runtime-qualification-2.0"
RECORDED_AT = "2026-07-24T03:30:00+08:00"


class ProviderTraceRuntimeQualificationError(ValueError):
    """当实时 v2 布线无法再复现时抛出的异常。"""


class _OneCallVigilFactory:
    provider_calls_consumed = 1

    def __call__(
        self,
        context: OnlineExecutorContext,
        trusted_user_request: str,
        client: OfficialProviderClient,
    ) -> VigilPreparation:
        del context
        completion = client.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Return one inert qualification constraint object."
                    ),
                },
                {
                    "role": "user",
                    "content": trusted_user_request,
                },
            ],
            step=1,
        )
        adapter = VigilRuntimeAdapter()
        adapter.prepare_from_constraint_payload(
            user_query=trusted_user_request,
            constraints=[],
            global_rules=["Offline qualification only."],
        )
        return VigilPreparation(
            adapter=adapter,
            completions=(completion,),
            constraint_count=0,
            constraint_set_sha256=sha256_canonical_json(
                {
                    "trusted_user_request": trusted_user_request,
                    "constraints": [],
                }
            ),
        )


def _selected_items() -> list[dict[str, Any]]:
    plan = [
        item
        for item in _load_plan()
        if item["benchmark"] == "m3-v2"
    ]
    selected: list[dict[str, Any]] = []
    requirements = (
        ("no_defense", "success_single"),
        ("strongest_peer_reviewed_structural_baseline", "success_vigil"),
        ("m3_full", "failure_agent"),
        ("strongest_peer_reviewed_structural_baseline", "failure_vigil"),
    )
    used: set[str] = set()
    for condition_id, scenario in requirements:
        item = next(
            candidate
            for candidate in plan
            if candidate["condition_id"] == condition_id
            and candidate["work_key"] not in used
        )
        copied = dict(item)
        copied["_qualification_scenario"] = scenario
        selected.append(copied)
        used.add(str(item["work_key"]))
    return selected


def _transport_for(
    *,
    model: str,
    scenario: str,
):
    call_count = 0

    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> HTTPResponseEnvelope:
        nonlocal call_count
        del endpoint, headers, timeout
        call_count += 1
        should_pause = (
            scenario == "failure_agent"
            or scenario == "failure_vigil"
        )
        if should_pause:
            return HTTPResponseEnvelope(
                status_code=429,
                headers={},
                body={},
            )
        return HTTPResponseEnvelope(
            status_code=200,
            headers={},
            body={
                "id": f"{scenario}-response-{call_count}",
                "model": model,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"tool":"final","arguments":'
                                '{"answer":"QUALIFIED"}}'
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": 8,
                    "total_tokens": 48,
                    "prompt_cache_hit_tokens": 32,
                    "prompt_cache_miss_tokens": 8,
                },
            },
        )

    return transport


def build_qualification() -> dict[str, Any]:
    selected = _selected_items()
    execution_identity = str(selected[0]["execution_identity"])
    if any(
        item["execution_identity"] != execution_identity
        for item in selected
    ):
        raise ProviderTraceRuntimeQualificationError(
            "qualification work items do not share one frozen identity"
        )
    scenario_by_key = {
        str(item["work_key"]): str(item["_qualification_scenario"])
        for item in selected
    }
    clean_items = [
        {
            key: value
            for key, value in item.items()
            if key != "_qualification_scenario"
        }
        for item in selected
    ]
    policy = json.loads(DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8"))
    run_id = "offline-provider-trace-runtime-qualification-not-scientific"
    result_rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(
        prefix="m3-provider-trace-runtime-v2-"
    ) as directory:
        root = Path(directory)

        def provider_factory(
            context: OnlineExecutorContext,
        ) -> OfficialProviderClient:
            scenario = scenario_by_key[context.work_key]
            state = ProviderBudgetState(
                provider_id="deepseek",
                policy=policy,
            )
            model = str(policy["deepseek"]["model_id"])
            return OfficialProviderClient(
                provider_id="deepseek",
                api_key="offline-qualification-key",
                content_class="public_benchmark_case",
                budget_state=state,
                policy=policy,
                transport=_transport_for(
                    model=model,
                    scenario=scenario,
                ),
                temperature=0.0,
                max_tokens=64,
            )

        def backend_factory(
            context: OnlineExecutorContext,
            tool_schemas: Mapping[str, Mapping[str, Any]],
        ) -> EffectBackend:
            del tool_schemas
            return M3SandboxEffectBackend(context)

        def trace_path_factory(
            context: OnlineExecutorContext,
        ) -> Path:
            digest = sha256_canonical_json(
                {"work_key": context.work_key}
            )[:24]
            return root / "traces" / f"{digest}.jsonl"

        runtime = LiveConditionRuntime(
            provider_client_factory=provider_factory,
            effect_backend_factory=backend_factory,
            vigil_factory=_OneCallVigilFactory(),
            provider_trace_path_factory=trace_path_factory,
            provider_trace_receipt_adapter=_as_official_receipt,
            recorded_at=lambda: RECORDED_AT,
        )
        ledger = root / "records-v2.jsonl"
        for item in clean_items:
            initial = reconstruct_initial_online_state(item)
            shell = ConditionExecutorShell(
                profile=CONDITION_PROFILES[str(item["condition_id"])],
                runtime=runtime,
                evaluator=_QualificationEvaluator(),
            )
            result = shell(item, initial)
            entry = append_execution_result(
                ledger,
                work_items=clean_items,
                work_item=item,
                initial_online_state=initial,
                execution_result=result,
                execution_identity=execution_identity,
                run_id=run_id,
            )
            bundle = entry["record"]["provider_trace_bundle"]
            result_rows.append(
                {
                    "scenario": scenario_by_key[str(item["work_key"])],
                    "condition_id": item["condition_id"],
                    "operational_status": entry["record"][
                        "operational_status"
                    ],
                    "result_tier": entry["record"]["result_tier"],
                    "request_count": bundle["request_count"],
                    "completed_request_count": bundle[
                        "completed_request_count"
                    ],
                    "open_request_count": bundle[
                        "open_request_count"
                    ],
                    "bundle_status": bundle["bundle_status"],
                    "usage_evidence_count": len(
                        bundle["usage_evidence"]
                    ),
                    "cache_accounting_complete": bundle[
                        "usage_summary"
                    ]["cache_accounting_complete"],
                    "cumulative_cost_cny": bundle["usage_summary"][
                        "cumulative_cost_cny"
                    ],
                    "within_abort_ceiling": bundle["usage_summary"][
                        "within_abort_ceiling"
                    ],
                    "unsafe_effect_itt": entry["record"][
                        "unsafe_effect_itt"
                    ],
                }
            )
        entries = load_record_entries(ledger)
        ledger_summary = validate_record_entries(
            entries,
            work_items=clean_items,
            execution_identity=execution_identity,
            run_id=run_id,
        )

    by_scenario = {item["scenario"]: item for item in result_rows}
    expected = {
        "success_single": ("formal_candidate", 1, 1, 0),
        "success_vigil": ("formal_candidate", 2, 2, 0),
        "failure_agent": ("diagnostic", 1, 0, 1),
        "failure_vigil": ("diagnostic", 1, 0, 1),
    }
    for scenario, expectation in expected.items():
        row = by_scenario[scenario]
        observed = (
            row["result_tier"],
            row["request_count"],
            row["completed_request_count"],
            row["open_request_count"],
        )
        if observed != expectation:
            raise ProviderTraceRuntimeQualificationError(
                f"{scenario}: live v2 trace expectation drift"
            )
    if any(
        row["operational_status"] != "provider_failure"
        or row["unsafe_effect_itt"] is not True
        for row in result_rows
        if row["scenario"].startswith("failure_")
    ):
        raise ProviderTraceRuntimeQualificationError(
            "failed provider calls did not remain in the ITT denominator"
        )
    if any(
        row["usage_evidence_count"] != row["completed_request_count"]
        or row["cache_accounting_complete"] is not True
        or row["within_abort_ceiling"] is not True
        for row in result_rows
    ):
        raise ProviderTraceRuntimeQualificationError(
            "per-call cache/cost evidence is incomplete"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "live_per_call_v2_wiring_qualified",
        "recorded_at": RECORDED_AT,
        "scenario_count": len(result_rows),
        "result_rows": result_rows,
        "formal_candidate_records": 2,
        "diagnostic_itt_failure_records": 2,
        "vigil_success_request_count": 2,
        "completed_calls_with_cache_cost_evidence": sum(
            row["usage_evidence_count"] for row in result_rows
        ),
        "all_completed_calls_have_cache_cost_evidence": True,
        "vigil_preparation_failure_retained": True,
        "agent_provider_failure_retained": True,
        "append_flush_fsync_before_every_transport": True,
        "automatic_retry": False,
        "hash_chain_complete": ledger_summary["hash_chain_complete"],
        "transient_record_entries": ledger_summary["entry_count"],
        "network_calls_made": 0,
        "provider_tools_declared": False,
        "external_effects": False,
        "project_experiment_records_persisted": 0,
        "formal_results_created": 0,
        "qualification_evidence_only": True,
    }


def validate_qualification(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or dict(value) != build_qualification():
        raise ProviderTraceRuntimeQualificationError(
            "live per-call v2 qualification drift"
        )
    return dict(value)


def write_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    return validate_qualification(
        json.loads(path.read_text(encoding="utf-8"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    path = (
        args.output
        if args.output.is_absolute()
        else PROJECT_ROOT / args.output
    )
    value = (
        verify_qualification(path)
        if args.verify_only
        else write_qualification(path)
    )
    print(
        json.dumps(
            {
                "status": value["status"],
                "scenario_count": value["scenario_count"],
                "network_calls_made": 0,
                "formal_results_created": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
