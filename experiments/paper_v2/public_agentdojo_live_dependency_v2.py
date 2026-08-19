"""Public-plan AgentDojo binding for paper-v2 live execution.

The original frozen resolver is intentionally tied to the medium execution
plan. Public work items use distinct work keys and selection identifiers, so
they require a separate private resolver. This module normalizes the public
plan's ``source_reference`` records into the existing AgentDojo binding
contract without exposing evaluator-only fields to the online state.

No function in this module reads credentials or performs network I/O.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.agentdojo_live_dependency import (
    AgentDojoLiveDependencyError,
    FrozenAgentDojoCaseResolver,
    _git_output,
    _load_jsonl,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.medium_runtime import (
    DEFAULT_AGENTDOJO_CHECKOUT,
    FROZEN_AGENTDOJO_COMMIT,
)
from experiments.paper_v2.public_matrix_plan_v1 import DEFAULT_PLAN


DEPENDENCY_VERSION = "m3-paper-v2-public-agentdojo-live-dependency-2.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/"
    "public_agentdojo_live_dependency_qualification_v2.json"
)
QUALIFIED_AT = "2026-07-28T08:27:00+08:00"


def _normalized_case(row: Mapping[str, Any]) -> dict[str, Any]:
    source = row.get("source_reference")
    if not isinstance(source, Mapping):
        raise AgentDojoLiveDependencyError(
            "public AgentDojo work item lacks source_reference"
        )
    if (
        source.get("sha256") != row.get("source_record_sha256")
        or not isinstance(source.get("path"), str)
        or isinstance(source.get("line"), bool)
        or not isinstance(source.get("line"), int)
    ):
        raise AgentDojoLiveDependencyError(
            "public AgentDojo source reference drift"
        )
    return {
        "selection_id": str(row["selection_id"]),
        "case_id": str(row["case_id"]),
        "benchmark": "agentdojo-v1",
        "source_path": str(source["path"]),
        "source_line": int(source["line"]),
        "source_record_sha256": str(source["sha256"]),
    }


class PublicFrozenAgentDojoCaseResolverV2(
    FrozenAgentDojoCaseResolver
):
    """Resolve public-plan work keys against their frozen source references."""

    def __init__(
        self,
        *,
        checkout: Path = DEFAULT_AGENTDOJO_CHECKOUT,
        plan_path: Path = DEFAULT_PLAN,
    ) -> None:
        self.checkout = checkout.resolve()
        rows = _load_jsonl(plan_path)
        self._items = {str(row["work_key"]): row for row in rows}
        if len(self._items) != len(rows):
            raise AgentDojoLiveDependencyError(
                "public plan contains duplicate work keys"
            )
        self._cases: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row.get("benchmark") != "agentdojo-v1":
                continue
            normalized = _normalized_case(row)
            selection_id = str(normalized["selection_id"])
            previous = self._cases.get(selection_id)
            if previous is not None and previous != normalized:
                raise AgentDojoLiveDependencyError(
                    "public selection maps to multiple source records"
                )
            self._cases[selection_id] = normalized
        commit = _git_output(self.checkout, "rev-parse", "HEAD")
        if commit != FROZEN_AGENTDOJO_COMMIT:
            raise AgentDojoLiveDependencyError(
                "AgentDojo checkout commit drift"
            )


def build_public_resolver_qualification(
    *,
    plan_path: Path = DEFAULT_PLAN,
) -> dict[str, Any]:
    """Resolve one attack and one benign public case for each model role."""

    rows = _load_jsonl(plan_path)
    resolver = PublicFrozenAgentDojoCaseResolverV2(plan_path=plan_path)
    probes: list[dict[str, Any]] = []
    for role in ("primary", "second"):
        role_rows = [
            row
            for row in rows
            if row.get("model_role") == role
            and row.get("benchmark") == "agentdojo-v1"
        ]
        for category in ("attack", "benign"):
            item = next(
                row
                for row in role_rows
                if (
                    row.get("evaluation_case_type") == "attack"
                )
                is (category == "attack")
            )
            binding = resolver.resolve(str(item["work_key"]))
            probes.append(
                {
                    "model_role": role,
                    "category": category,
                    "work_key": binding.work_key,
                    "case_id": binding.benchmark_case_id,
                    "binding_sha256": binding.binding_sha256,
                }
            )
    return {
        "schema_version": (
            "m3-paper-v2-public-agentdojo-live-dependency-qualification-2.0"
        ),
        "status": "public_plan_agentdojo_bindings_qualified_offline",
        "generated_at": QUALIFIED_AT,
        "dependency_version": DEPENDENCY_VERSION,
        "plan_records": len(rows),
        "public_agentdojo_work_items": sum(
            row.get("benchmark") == "agentdojo-v1" for row in rows
        ),
        "private_selection_bindings": len(resolver._cases),
        "qualification_probes": probes,
        "qualification_probe_count": len(probes),
        "qualification_probe_sequence_sha256": sha256_canonical_json(probes),
        "credentials_read": False,
        "network_calls_made": 0,
        "provider_calls_made": 0,
        "formal_results_created": 0,
        "scientific_outcomes_accessed": False,
    }


def write_public_resolver_qualification(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = build_public_resolver_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_public_resolver_qualification(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = build_public_resolver_qualification()
    if observed != expected:
        raise AgentDojoLiveDependencyError(
            "public AgentDojo qualification artifact drift"
        )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    value = (
        write_public_resolver_qualification(args.output)
        if args.write
        else verify_public_resolver_qualification(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
