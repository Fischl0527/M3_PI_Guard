"""官方 AgentDojo 环境准入与离线结果评分判定依赖。

管理 AgentDojo 基准套件的环境隔离、用例加载与基准答案校验，
保证评测遵循官方环境规范且杜绝先验泄漏。
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import OnlineExecutorContext
from experiments.paper_v2.live_condition_runtime import (
    AgentDojoInMemoryEffectBackend,
)
from experiments.paper_v2.medium_runtime import (
    DEFAULT_AGENTDOJO_CHECKOUT,
    DEFAULT_CASE_INDEX,
    DEFAULT_V2_PLAN,
    FROZEN_AGENTDOJO_COMMIT,
    _read_source_record,
    reconstruct_initial_online_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/agentdojo_live_dependency_qualification_v1.json"
)
QUALIFICATION_RECORDED_AT = "2026-07-24T01:30:00+08:00"
DEPENDENCY_VERSION = "m3-paper-v2-agentdojo-live-dependency-1.0"
OFFICIAL_ATTACK_NAME = "direct"


class AgentDojoLiveDependencyError(ValueError):
    """当用例、环境或官方检查器发生漂移时抛出的异常。"""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise AgentDojoLiveDependencyError(
                f"{path}:{line_number} must contain an object"
            )
        rows.append(value)
    return rows


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return _jsonable(dump())
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _add_agentdojo_source(checkout: Path) -> None:
    source = str((checkout / "src").resolve())
    if source not in sys.path:
        sys.path.insert(0, source)


def _git_output(checkout: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(checkout), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


@dataclass(frozen=True)
class AgentDojoCaseBinding:
    work_key: str
    selection_id: str
    benchmark_case_id: str
    benchmark_version: str
    suite: str
    user_task_id: str
    injection_task_id: str | None
    source_record_sha256: str

    @property
    def binding_sha256(self) -> str:
        return sha256_canonical_json(
            {
                "work_key": self.work_key,
                "selection_id": self.selection_id,
                "benchmark_case_id": self.benchmark_case_id,
                "benchmark_version": self.benchmark_version,
                "suite": self.suite,
                "user_task_id": self.user_task_id,
                "injection_task_id": self.injection_task_id,
                "source_record_sha256": self.source_record_sha256,
            }
        )


class FrozenAgentDojoCaseResolver:
    """在线状态之外仅由评测者解析用例身份。"""

    def __init__(
        self,
        *,
        checkout: Path = DEFAULT_AGENTDOJO_CHECKOUT,
        plan_path: Path = DEFAULT_V2_PLAN,
        case_index_path: Path = DEFAULT_CASE_INDEX,
    ) -> None:
        self.checkout = checkout.resolve()
        self._items = {
            str(row["work_key"]): row for row in _load_jsonl(plan_path)
        }
        self._cases = {
            str(row["selection_id"]): row
            for row in _load_jsonl(case_index_path)
        }
        if len(self._items) != len(_load_jsonl(plan_path)):
            raise AgentDojoLiveDependencyError(
                "paper-v2 plan contains duplicate work keys"
            )
        commit = _git_output(self.checkout, "rev-parse", "HEAD")
        if commit != FROZEN_AGENTDOJO_COMMIT:
            raise AgentDojoLiveDependencyError(
                "AgentDojo checkout commit drift"
            )

    def resolve(self, work_key: str) -> AgentDojoCaseBinding:
        item = self._items.get(str(work_key))
        if item is None:
            raise AgentDojoLiveDependencyError("unknown paper-v2 work key")
        if item.get("benchmark") != "agentdojo-v1":
            raise AgentDojoLiveDependencyError(
                "work key does not identify AgentDojo"
            )
        selection_id = str(item["selection_id"])
        case = self._cases.get(selection_id)
        if case is None:
            raise AgentDojoLiveDependencyError(
                "work key has no frozen case-index row"
            )
        record = _read_source_record(case)
        binding = AgentDojoCaseBinding(
            work_key=str(work_key),
            selection_id=selection_id,
            benchmark_case_id=str(case["case_id"]),
            benchmark_version=str(record["benchmark_version"]),
            suite=str(record["suite"]),
            user_task_id=str(record["user_task_id"]),
            injection_task_id=(
                str(record["injection_task_id"])
                if record.get("injection_task_id") is not None
                else None
            ),
            source_record_sha256=str(case["source_record_sha256"]),
        )
        if binding.benchmark_case_id != str(item["case_id"]):
            raise AgentDojoLiveDependencyError(
                "work item and source record case identity differ"
            )
        return binding

    def _official_objects(
        self, binding: AgentDojoCaseBinding
    ) -> tuple[Any, Any, Any | None]:
        _add_agentdojo_source(self.checkout)
        from agentdojo.task_suite.load_suites import get_suite

        suite = get_suite(binding.benchmark_version, binding.suite)
        user_task = suite.get_user_task_by_id(binding.user_task_id)
        injection_task = (
            suite.get_injection_task_by_id(binding.injection_task_id)
            if binding.injection_task_id is not None
            else None
        )
        return suite, user_task, injection_task

    def build_backend(
        self,
        context: OnlineExecutorContext,
        tool_schemas: Mapping[str, Mapping[str, Any]],
    ) -> AgentDojoInMemoryEffectBackend:
        binding = self.resolve(context.work_key)
        agent_input = context.online_state.get("agent_input")
        if not isinstance(agent_input, Mapping):
            raise AgentDojoLiveDependencyError(
                "AgentDojo online projection is missing"
            )
        online_inputs = agent_input.get("online_inputs")
        if not isinstance(online_inputs, Mapping):
            raise AgentDojoLiveDependencyError(
                "AgentDojo online inputs are missing"
            )
        app_context = online_inputs.get("trusted_app_context")
        if not isinstance(app_context, Mapping):
            raise AgentDojoLiveDependencyError(
                "AgentDojo trusted app context is missing"
            )
        if (
            app_context.get("suite") != binding.suite
            or app_context.get("user_task_id") != binding.user_task_id
        ):
            raise AgentDojoLiveDependencyError(
                "private case binding differs from online task identity"
            )

        suite, user_task, injection_task = self._official_objects(binding)
        available_tools = {str(tool.name) for tool in suite.tools} | {"final"}
        if available_tools != set(tool_schemas):
            raise AgentDojoLiveDependencyError(
                "official AgentDojo tools differ from the online schema"
            )
        injections: dict[str, str] = {}
        if injection_task is not None:
            import agentdojo.attacks.baseline_attacks  # noqa: F401
            from agentdojo.attacks.attack_registry import load_attack

            attack = load_attack(OFFICIAL_ATTACK_NAME, suite, object())
            injections = attack.attack(user_task, injection_task)
        environment = suite.load_and_inject_default_environment(injections)
        environment = user_task.init_environment(environment)
        from agentdojo.functions_runtime import FunctionsRuntime

        return AgentDojoInMemoryEffectBackend(
            runtime=FunctionsRuntime(suite.tools),
            environment=environment,
            evaluator_context={
                "binding_sha256": binding.binding_sha256,
                "attack_name": (
                    OFFICIAL_ATTACK_NAME
                    if injection_task is not None
                    else None
                ),
                "injection_payload_sha256": sha256_canonical_json(injections),
            },
        )


class AgentDojoOfflineOutcomeEvaluator:
    """在线执行后应用固化的官方效用/安全性检查器。"""

    def __init__(self, resolver: FrozenAgentDojoCaseResolver) -> None:
        self.resolver = resolver

    @staticmethod
    def _check(
        task: Any,
        *,
        kind: str,
        model_output: str,
        pre_environment: Any,
        post_environment: Any,
        traces: list[Any],
    ) -> bool:
        trace_method = getattr(task, f"{kind}_from_traces")
        observed = trace_method(
            model_output,
            pre_environment,
            post_environment,
            traces,
        )
        if observed is not None:
            return bool(observed)
        return bool(
            getattr(task, kind)(
                model_output,
                pre_environment,
                post_environment,
            )
        )

    def evaluate(
        self,
        work_item: Mapping[str, Any],
        raw_trace: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        binding = self.resolver.resolve(str(work_item["work_key"]))
        material = raw_trace.get("offline_evaluator_input")
        if not isinstance(material, Mapping):
            raise AgentDojoLiveDependencyError(
                "offline AgentDojo evaluator material is missing"
            )
        if material.get("backend_id") != "agentdojo_in_memory_copy":
            raise AgentDojoLiveDependencyError(
                "offline material has the wrong effect backend"
            )
        evaluator_context = material.get("evaluator_context")
        if (
            not isinstance(evaluator_context, Mapping)
            or evaluator_context.get("binding_sha256")
            != binding.binding_sha256
        ):
            raise AgentDojoLiveDependencyError(
                "offline material is not bound to this frozen work item"
            )
        pre_environment = material.get("pre_environment")
        post_environment = material.get("post_environment")
        calls = material.get("function_calls")
        if pre_environment is None or post_environment is None:
            raise AgentDojoLiveDependencyError(
                "official pre/post environments are missing"
            )
        if not isinstance(calls, list):
            raise AgentDojoLiveDependencyError(
                "official function-call trace is missing"
            )

        _add_agentdojo_source(self.resolver.checkout)
        from agentdojo.functions_runtime import FunctionCall

        traces = [FunctionCall.model_validate(call) for call in calls]
        _, user_task, injection_task = self.resolver._official_objects(binding)
        model_output = str(material.get("final_output", ""))
        utility = self._check(
            user_task,
            kind="utility",
            model_output=model_output,
            pre_environment=pre_environment,
            post_environment=post_environment,
            traces=traces,
        )
        unsafe_effect = False
        if injection_task is not None:
            unsafe_effect = self._check(
                injection_task,
                kind="security",
                model_output=model_output,
                pre_environment=pre_environment,
                post_environment=post_environment,
                traces=traces,
            )
        return {
            "unsafe_effect": bool(unsafe_effect),
            "task_completion": bool(utility),
            "metric_semantics": "agentdojo_official_v2",
            "official_injection_success": (
                bool(unsafe_effect)
                if injection_task is not None
                else None
            ),
        }


def _context_for_item(item: Mapping[str, Any]) -> OnlineExecutorContext:
    return OnlineExecutorContext(
        execution_identity=str(item["execution_identity"]),
        work_key=str(item["work_key"]),
        benchmark=str(item["benchmark"]),
        condition_id=str(item["condition_id"]),
        max_provider_calls=int(item["max_provider_calls"]),
        online_state=reconstruct_initial_online_state(item),
    )


def _ground_truth_probe(
    *,
    resolver: FrozenAgentDojoCaseResolver,
    evaluator: AgentDojoOfflineOutcomeEvaluator,
    item: Mapping[str, Any],
    target: str,
) -> dict[str, Any]:
    context = _context_for_item(item)
    schemas = context.online_state["agent_input"]["online_inputs"][
        "tool_schemas"
    ]
    schemas = {**schemas, "final": {"arguments": {"answer": {"type": "string", "required": True}}}}
    backend = resolver.build_backend(context, schemas)
    try:
        binding = resolver.resolve(context.work_key)
        _, user_task, injection_task = resolver._official_objects(binding)
        task = user_task if target == "utility" else injection_task
        if task is None:
            raise AgentDojoLiveDependencyError(
                "security probe requires an injection task"
            )
        initial = backend.evaluator_material()
        pre_environment = initial["pre_environment"]
        copy_method = getattr(pre_environment, "model_copy", None)
        ground_truth_environment = (
            copy_method(deep=True)
            if callable(copy_method)
            else copy.deepcopy(pre_environment)
        )
        calls = task.ground_truth(ground_truth_environment)
        errors: list[str] = []
        for call in calls:
            observation = backend.execute(
                str(call.function), dict(call.args)
            )
            if isinstance(observation, Mapping) and observation.get("error"):
                errors.append(str(observation["error"]))
        backend.execute("final", {"answer": str(task.GROUND_TRUTH_OUTPUT)})
        material = backend.evaluator_material()
        outcome = evaluator.evaluate(
            item, {"offline_evaluator_input": material}
        )
        return {
            "benchmark_case_id": binding.benchmark_case_id,
            "binding_sha256": binding.binding_sha256,
            "probe": target,
            "function_call_count": len(calls),
            "tool_error_count": len(errors),
            "pre_environment_sha256": sha256_canonical_json(
                _jsonable(material["pre_environment"])
            ),
            "post_environment_sha256": sha256_canonical_json(
                _jsonable(material["post_environment"])
            ),
            "injection_payload_sha256": material["evaluator_context"][
                "injection_payload_sha256"
            ],
            "unsafe_effect": outcome["unsafe_effect"],
            "task_completion": outcome["task_completion"],
        }
    finally:
        backend.close()


def build_qualification() -> dict[str, Any]:
    resolver = FrozenAgentDojoCaseResolver()
    evaluator = AgentDojoOfflineOutcomeEvaluator(resolver)
    items = _load_jsonl(DEFAULT_V2_PLAN)
    benign = next(
        item
        for item in items
        if item["benchmark"] == "agentdojo-v1"
        and item["condition_id"] == "no_defense"
        and item["analysis_tier"] == "primary"
        and "injection_task" not in item["case_id"]
    )
    attack = next(
        item
        for item in items
        if item["benchmark"] == "agentdojo-v1"
        and item["condition_id"] == "no_defense"
        and item["analysis_tier"] == "primary"
        and "injection_task" in item["case_id"]
    )
    probes = [
        _ground_truth_probe(
            resolver=resolver,
            evaluator=evaluator,
            item=benign,
            target="utility",
        ),
        _ground_truth_probe(
            resolver=resolver,
            evaluator=evaluator,
            item=attack,
            target="security",
        ),
    ]
    if probes[0]["task_completion"] is not True:
        raise AgentDojoLiveDependencyError(
            "official utility checker rejected its ground truth"
        )
    if probes[0]["unsafe_effect"] is not False:
        raise AgentDojoLiveDependencyError(
            "benign case produced an unsafe-effect label"
        )
    if probes[1]["unsafe_effect"] is not True:
        raise AgentDojoLiveDependencyError(
            "official security checker missed its ground truth"
        )
    source_files = [
        "src/agentdojo/base_tasks.py",
        "src/agentdojo/functions_runtime.py",
        "src/agentdojo/task_suite/task_suite.py",
        "src/agentdojo/attacks/baseline_attacks.py",
    ]
    return {
        "schema_version": "m3-paper-v2-agentdojo-live-dependency-qualification-1.0",
        "dependency_version": DEPENDENCY_VERSION,
        "status": "official_environment_and_offline_evaluator_qualified",
        "qualified_at": QUALIFICATION_RECORDED_AT,
        "source_lock": {
            "checkout": DEFAULT_AGENTDOJO_CHECKOUT.relative_to(
                PROJECT_ROOT
            ).as_posix(),
            "commit": _git_output(
                DEFAULT_AGENTDOJO_CHECKOUT, "rev-parse", "HEAD"
            ),
            "worktree_clean": not bool(
                _git_output(DEFAULT_AGENTDOJO_CHECKOUT, "status", "--porcelain")
            ),
            "files": {
                path: _sha256_file(DEFAULT_AGENTDOJO_CHECKOUT / path)
                for path in source_files
            },
        },
        "attack_construction": {
            "attack_name": OFFICIAL_ATTACK_NAME,
            "official_source_used": True,
            "attack_task_identity_visible_to_provider": False,
            "injection_text_persisted": False,
        },
        "environment_factory": {
            "fresh_environment_per_work_item": True,
            "user_task_init_environment_applied": True,
            "official_functions_runtime": True,
            "source_environment_mutated": False,
        },
        "offline_evaluator": {
            "official_utility_checker": True,
            "official_security_checker": True,
            "official_security_semantics": (
                "true means the injection goal was executed"
            ),
            "metric_semantics": "agentdojo_official_v2",
            "work_key_binding_required": True,
        },
        "qualification_probes": probes,
        "network_calls_made": 0,
        "api_calls_made": 0,
        "model_calls_made": 0,
        "credentials_read": False,
        "experiment_records_persisted": 0,
        "formal_results_created": 0,
        "evidence_boundary": [
            "This qualifies pinned AgentDojo v1 environment construction, direct-attack injection and official offline checker wiring.",
            "It does not qualify provider execution, any defense effect estimate, the M3-v2 offline evaluator, VIGIL constraint generation or exact-gold execution.",
        ],
    }


def write_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    artifact = build_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return artifact


def verify_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    frozen = json.loads(path.read_text(encoding="utf-8"))
    current = build_qualification()
    if current != frozen:
        raise AgentDojoLiveDependencyError(
            "AgentDojo live-dependency qualification does not reproduce"
        )
    return frozen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    artifact = (
        verify_qualification(args.output)
        if args.verify_only
        else write_qualification(args.output)
    )
    print(
        json.dumps(
            {
                "status": "verified" if args.verify_only else artifact["status"],
                "commit": artifact["source_lock"]["commit"],
                "qualification_probes": len(
                    artifact["qualification_probes"]
                ),
                "network_calls_made": artifact["network_calls_made"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
