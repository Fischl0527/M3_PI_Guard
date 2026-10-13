"""具备执行身份感知能力的公开 M3 评测器绑定（版本 V4）。

支持跨用例执行上下文的精确隔离与状态审计。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.m3_offline_evaluator import (
    M3OfflineEvaluatorError,
    M3OfflineOutcomeEvaluator,
    _load_jsonl,
)
from experiments.paper_v2.public_m3_live_dependency_v3 import (
    DEFAULT_PLAN,
    PROJECT_ROOT,
    PublicFrozenM3CaseResolverV3,
)


DEPENDENCY_VERSION = "m3-paper-v2-public-m3-live-dependency-4.0"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/"
    "public_m3_live_dependency_qualification_v4.json"
)
QUALIFIED_AT = "2026-07-29T00:45:00+08:00"


def _validate_execution_identity(value: str) -> str:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise M3OfflineEvaluatorError(
            "public M3 execution identity must be lowercase SHA-256"
        )
    return value


class PublicFrozenM3CaseResolverV4(PublicFrozenM3CaseResolverV3):
    """将公开 M3 用例绑定到活动许可执行身份。"""

    def __init__(
        self,
        *,
        execution_identity: str,
        plan_path: Path = DEFAULT_PLAN,
    ) -> None:
        identity = _validate_execution_identity(execution_identity)
        super().__init__(plan_path=plan_path)
        for item in self._items.values():
            if item.get("benchmark") == "m3-v2":
                item["execution_identity"] = identity


def _qualification_identity(model_role: str) -> str:
    return sha256_canonical_json(
        {
            "schema_version": (
                "m3-paper-v2-public-m3-evaluator-probe-4.0"
            ),
            "model_role": model_role,
        }
    )


def build_public_m3_resolver_qualification(
    *,
    plan_path: Path = DEFAULT_PLAN,
) -> dict[str, Any]:
    """对两个角色的攻击/良性探测运行实际评测器。"""

    rows = _load_jsonl(plan_path)
    probes: list[dict[str, Any]] = []
    for role in ("primary", "second"):
        identity = _qualification_identity(role)
        resolver = PublicFrozenM3CaseResolverV4(
            execution_identity=identity,
            plan_path=plan_path,
        )
        evaluator = M3OfflineOutcomeEvaluator(resolver)
        role_rows = [
            row
            for row in rows
            if row.get("model_role") == role
            and row.get("benchmark") == "m3-v2"
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
            work_item = {**item, "execution_identity": identity}
            material_digest = sha256_canonical_json(
                {
                    "execution_identity": identity,
                    "work_key": item["work_key"],
                }
            )
            outcome = evaluator.evaluate(
                work_item,
                {
                    "offline_evaluator_input": {
                        "backend_id": "m3_sandbox_fixture",
                        "work_key_sha256": material_digest,
                        "tool_events": [],
                    }
                },
            )
            binding = resolver.resolve(str(item["work_key"]))
            probes.append(
                {
                    "model_role": role,
                    "category": category,
                    "work_key": binding.work_key,
                    "case_id": binding.case_id,
                    "binding_execution_identity": (
                        binding.execution_identity
                    ),
                    "binding_digest_matches_material": (
                        binding.work_key_sha256 == material_digest
                    ),
                    "evaluator_completed": isinstance(outcome, dict),
                }
            )
    if not all(
        probe["binding_digest_matches_material"]
        and probe["evaluator_completed"]
        for probe in probes
    ):
        raise M3OfflineEvaluatorError(
            "public M3 evaluator qualification did not close the identity bind"
        )
    return {
        "schema_version": (
            "m3-paper-v2-public-m3-live-dependency-qualification-4.0"
        ),
        "status": "public_m3_active_identity_evaluator_qualified_offline",
        "generated_at": QUALIFIED_AT,
        "dependency_version": DEPENDENCY_VERSION,
        "plan_records": len(rows),
        "public_m3_work_items": sum(
            row.get("benchmark") == "m3-v2" for row in rows
        ),
        "private_selection_bindings": 750,
        "qualification_probes": probes,
        "qualification_probe_count": len(probes),
        "credentials_read": False,
        "network_calls_made": 0,
        "provider_calls_made": 0,
        "formal_results_created": 0,
        "scientific_outcomes_aggregated": False,
    }


def write_public_m3_resolver_qualification(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = build_public_m3_resolver_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_public_m3_resolver_qualification(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = build_public_m3_resolver_qualification()
    if observed != expected:
        raise M3OfflineEvaluatorError(
            "public M3 v4 qualification artifact drift"
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
        write_public_m3_resolver_qualification(args.output)
        if args.write
        else verify_public_m3_resolver_qualification(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
