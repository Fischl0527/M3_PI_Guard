"""Source-locked adapters for the paper-v2 structural baselines.

The adapters import the pinned official source trees.  They do not copy or
reimplement VIGIL/DRIFT algorithms, and they fail closed when source identity or
the required AgentDojo 0.1.35 interface differs.
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 uses the compatible TOML backport.
    import tomli as tomllib
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Literal, Mapping

from experiments.paper_v2.contracts import canonical_json_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIGIL_ROOT = PROJECT_ROOT / "external/paper_v2_audits/vigil"
DRIFT_ROOT = PROJECT_ROOT / "external/paper_v2_audits/drift"
AGENTDOJO_ROOT = PROJECT_ROOT / "external/benchmarks/agentdojo"
REGISTRY_PATH = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/structural_baseline_registry_v1.json"
)

VIGIL_COMMIT = "af8eb9c70d32f8a3cc07b308e823c813b2285772"
DRIFT_COMMIT = "6fd3df4763fad77398c3c273c2a4fe14dd50f7ea"
AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
REQUIRED_AGENTDOJO_VERSION = "0.1.35"


class StructuralBaselineError(RuntimeError):
    """Raised when an official structural baseline cannot be used faithfully."""


@dataclass(frozen=True)
class NormalizedGuardDecision:
    decision: Literal["ALLOW", "ASK", "DENY"]
    reason: str | None
    baseline: str
    raw_result: dict[str, Any]


def _git_commit(path: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _assert_source(path: Path, expected_commit: str, required: tuple[str, ...]) -> None:
    if not path.is_dir():
        raise StructuralBaselineError(f"source checkout missing: {path}")
    observed = _git_commit(path)
    if observed != expected_commit:
        raise StructuralBaselineError(
            f"source commit mismatch for {path}: {observed} != {expected_commit}"
        )
    missing = [name for name in required if not (path / name).is_file()]
    if missing:
        raise StructuralBaselineError(
            f"source checkout {path} is missing required files: {missing}"
        )


@contextmanager
def _source_import_path(*paths: Path) -> Iterator[None]:
    additions = [str(path) for path in paths if str(path) not in sys.path]
    sys.path[:0] = additions
    try:
        yield
    finally:
        for addition in additions:
            if addition in sys.path:
                sys.path.remove(addition)


def _agentdojo_version() -> str:
    value = tomllib.loads(
        (AGENTDOJO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    return value["project"]["version"]


class VigilRuntimeAdapter:
    """Normalize the official VIGIL RuntimeAuditor decision boundary."""

    def __init__(
        self,
        *,
        auditor_mode: Literal["strict", "permissive", "hybrid"] = "hybrid",
        allow_provider_calls: bool = False,
        constraint_generator_model: str = "gpt-4o-2024-08-06",
    ) -> None:
        _assert_source(
            VIGIL_ROOT,
            VIGIL_COMMIT,
            (
                "vigil/config.py",
                "vigil/types.py",
                "vigil/runtime_auditor.py",
                "vigil/constraint_generator.py",
            ),
        )
        _assert_source(
            AGENTDOJO_ROOT,
            AGENTDOJO_COMMIT,
            ("pyproject.toml", "src/agentdojo/__init__.py"),
        )
        with _source_import_path(AGENTDOJO_ROOT / "src", VIGIL_ROOT):
            config_module = importlib.import_module("vigil.config")
            auditor_module = importlib.import_module("vigil.runtime_auditor")
            self._types = importlib.import_module("vigil.types")
        self.config = config_module.VIGILConfig(
            auditor_mode=auditor_mode,
            enable_llm_verification=False,
            enable_llm_constraint_verification=False,
            constraint_generator_model=constraint_generator_model,
        )
        self._auditor = auditor_module.RuntimeAuditor(self.config)
        self._allow_provider_calls = allow_provider_calls
        self._prepared = False

    def prepare_from_constraint_payload(
        self,
        *,
        user_query: str,
        constraints: list[Mapping[str, Any]],
        global_rules: list[str] | None = None,
    ) -> None:
        """Load an official-schema constraint set for deterministic qualification."""

        constraint_set = self._types.ConstraintSet(
            user_query=user_query,
            constraints=[
                self._types.SecurityConstraint(**dict(item)) for item in constraints
            ],
            global_rules=global_rules,
            metadata={"adapter_path": "official_schema_payload"},
        )
        self._auditor.update_constraints(constraint_set)
        self._prepared = True

    def prepare_from_official_constraint_set(
        self, constraint_set: Any
    ) -> None:
        """Bind a ConstraintSet returned by the pinned official generator."""

        if not isinstance(constraint_set, self._types.ConstraintSet):
            raise StructuralBaselineError(
                "VIGIL generator returned a non-official ConstraintSet"
            )
        if not isinstance(constraint_set.metadata, Mapping) or not isinstance(
            constraint_set.metadata.get("raw_response"), Mapping
        ):
            raise StructuralBaselineError(
                "VIGIL constraint generation fell back without model evidence"
            )
        self._auditor.update_constraints(constraint_set)
        self._prepared = True

    def prepare_from_user_query(self, user_query: str) -> None:
        """Run the official VIGIL constraint generator after the cost gate opens."""

        if not self._allow_provider_calls:
            raise StructuralBaselineError(
                "official VIGIL constraint generation is disabled until the "
                "provider/cost gate explicitly enables model calls"
            )
        with _source_import_path(VIGIL_ROOT):
            generator_module = importlib.import_module("vigil.constraint_generator")
        generator = generator_module.ConstraintGenerator(self.config)
        self._auditor.update_constraints(generator.generate_constraints(user_query))
        self._prepared = True

    def decide(
        self,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        tool_call_id: str | None = None,
    ) -> NormalizedGuardDecision:
        if not self._prepared:
            raise StructuralBaselineError("VIGIL adapter must be prepared before decide")
        raw = self._auditor.audit_tool_call(
            {
                "tool_name": tool_name,
                "arguments": dict(arguments),
                "tool_call_id": tool_call_id,
            }
        )
        raw_dict = raw.model_dump(mode="json")
        if raw.require_confirmation:
            decision: Literal["ALLOW", "ASK", "DENY"] = "ASK"
        elif raw.allowed:
            decision = "ALLOW"
        else:
            decision = "DENY"
        return NormalizedGuardDecision(
            decision=decision,
            reason=raw.feedback_message,
            baseline="vigil",
            raw_result=raw_dict,
        )


def default_drift_args(model: str = "provider-model-pending") -> SimpleNamespace:
    """Return the exact three defense switches used by the official README."""

    return SimpleNamespace(
        model=model,
        build_constraints=True,
        injection_isolation=True,
        dynamic_validation=True,
        adaptive_attack=False,
        do_attack=False,
        attack_type="important_instructions",
        benchmark_version=(1, 2, 1),
        force_rerun=False,
        seed=42,
        suites="banking,slack,travel,workspace",
        target_injection_tasks=None,
        target_user_tasks=None,
    )


def build_official_drift_pipeline(
    *,
    client: Any,
    logger: Any,
    args: SimpleNamespace | None = None,
) -> Any:
    """Construct the official DRIFT AgentDojo pipeline without making a model call."""

    _assert_source(
        DRIFT_ROOT,
        DRIFT_COMMIT,
        (
            "DRIFTLLM.py",
            "DRIFTToolsExecutionLoop.py",
            "pipeline_main.py",
            "requirements.txt",
        ),
    )
    _assert_source(
        AGENTDOJO_ROOT,
        AGENTDOJO_COMMIT,
        ("pyproject.toml", "src/agentdojo/__init__.py"),
    )
    if _agentdojo_version() != REQUIRED_AGENTDOJO_VERSION:
        raise StructuralBaselineError(
            f"DRIFT requires AgentDojo {REQUIRED_AGENTDOJO_VERSION}, observed "
            f"{_agentdojo_version()}"
        )
    args = args or default_drift_args()
    with _source_import_path(AGENTDOJO_ROOT / "src", DRIFT_ROOT):
        drift_module = importlib.import_module("DRIFTLLM")
        loop_module = importlib.import_module("DRIFTToolsExecutionLoop")
        agent_pipeline_module = importlib.import_module("agentdojo.agent_pipeline")
    llm = drift_module.DRIFTLLM(
        args,
        client,
        model=args.model,
        temperature=0.0,
        logger=logger,
    )
    tools_loop = loop_module.DRIFTToolsExecutionLoop(
        [agent_pipeline_module.ToolsExecutor(), llm]
    )
    pipeline = agent_pipeline_module.AgentPipeline(
        [agent_pipeline_module.InitQuery(), llm, tools_loop]
    )
    pipeline.name = f"{args.model}-drift"
    return pipeline


class _NoCallClient:
    total_tokens = 0

    def __getattr__(self, name: str) -> Any:
        raise StructuralBaselineError(
            f"qualification client forbids provider method access: {name}"
        )


class _MemoryLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(str(message))


def qualify_structural_baselines(*, write: bool = True) -> dict[str, Any]:
    """Run source/import/behavior checks with zero external model calls."""

    vigil = VigilRuntimeAdapter()
    vigil.prepare_from_constraint_payload(
        user_query="Send the report only after confirmation.",
        constraints=[
            {
                "constraint_id": "confirm_send",
                "constraint_type": "require_confirmation",
                "description": "Confirm sending the report.",
                "condition": {"tool_name": "send_report"},
                "priority": 1,
            },
            {
                "constraint_id": "forbid_delete",
                "constraint_type": "forbid",
                "description": "Forbid deleting records.",
                "condition": {"tool_name": "delete_record"},
                "priority": 1,
            },
        ],
    )
    decisions = {
        name: asdict(vigil.decide(tool_name=name, arguments={}))
        for name in ("read_report", "send_report", "delete_record")
    }
    if {name: item["decision"] for name, item in decisions.items()} != {
        "read_report": "ALLOW",
        "send_report": "ASK",
        "delete_record": "DENY",
    }:
        raise StructuralBaselineError("VIGIL decision normalization smoke failed")

    pipeline = build_official_drift_pipeline(
        client=_NoCallClient(),
        logger=_MemoryLogger(),
    )
    registry = {
        "schema_version": "m3-paper-v2-structural-baseline-registry-1.0",
        "generated_at": "2026-07-23T16:00:00+08:00",
        "provider_calls_made": 0,
        "baselines": {
            "vigil": {
                "paper_status": "peer_reviewed_acl_2026",
                "source_commit": VIGIL_COMMIT,
                "source_lock_verified": True,
                "adapter": (
                    "experiments.paper_v2.structural_baselines."
                    "VigilRuntimeAdapter"
                ),
                "qualification": "pass",
                "qualification_decisions": decisions,
                "official_constraint_generator_executed": False,
                "medium_result_status": "pending_provider_and_cost_gate",
                "formal_admission": False,
            },
            "drift": {
                "paper_status": "peer_reviewed_neurips_2025",
                "source_commit": DRIFT_COMMIT,
                "agentdojo_commit": AGENTDOJO_COMMIT,
                "agentdojo_version": _agentdojo_version(),
                "source_lock_verified": True,
                "adapter": (
                    "experiments.paper_v2.structural_baselines."
                    "build_official_drift_pipeline"
                ),
                "qualification": "pass",
                "pipeline_element_types": [
                    type(element).__name__ for element in pipeline.elements
                ],
                "model_query_executed": False,
                "medium_result_status": "pending_provider_and_cost_gate",
                "formal_admission": False,
            },
        },
        "medium_baseline_resolution": {
            "preferred": "vigil",
            "fallback": "drift",
            "resolved": False,
            "reason": (
                "Both official-source adapters pass zero-call qualification, but no "
                "paired medium result exists yet."
            ),
        },
    }
    if write:
        REGISTRY_PATH.write_bytes(canonical_json_bytes(registry) + b"\n")
    return registry


def verify_registry() -> dict[str, Any]:
    observed = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    expected = qualify_structural_baselines(write=False)
    if observed != expected:
        raise StructuralBaselineError("structural baseline registry does not reproduce")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    registry = verify_registry() if args.verify_only else qualify_structural_baselines()
    print(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
