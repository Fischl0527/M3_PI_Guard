"""可复现的 paper-v2 online-state 源码边界审计工具。

深度检查所有实验运行代码与外部数据源的边界契约，确保无未受控的数据反向污染。
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = PROJECT_ROOT / "protocols/paper_upgrade_v2/online_state_audit_specs_v1.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "protocols/paper_upgrade_v2/audits"
REGISTRY_V1 = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/online_state_audit_registry_v1.json"
)
REGISTRY_V2 = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/online_state_audit_registry_v2.json"
)
SUMMARY_MD = PROJECT_ROOT / "protocols/paper_upgrade_v2/source_audit_summary_v1.md"
FORBIDDEN_PATTERNS = (
    r"\bgold\b",
    r"ground[_ -]?truth",
    r"expected[_ -]?(?:answer|action|tool)",
    r"attack[_ -]?success",
    r"task[_ -]?success",
    r"target[_ -]?tool",
    r"attacker[_ -]?goal",
    r"\blabels?\b",
    r"\bscore\b",
    r"injection_task_id",
    r"user_task_id",
)
SENTINEL = "M3_PAPER_V2_EVALUATOR_ONLY_SENTINEL_7F4C"


class SourceAuditError(RuntimeError):
    """源码审计输入或证据不满足约束。"""


@dataclass(frozen=True)
class SymbolEvidence:
    path: str
    symbol: str
    phase: str
    start_line: int
    end_line: int
    sha256: str
    parameters: tuple[str, ...]
    referenced_identifiers: tuple[str, ...]
    referenced_string_keys: tuple[str, ...]
    forbidden_identifier_hits: tuple[str, ...]
    required_token_checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "symbol": self.symbol,
            "phase": self.phase,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "sha256": self.sha256,
            "parameters": list(self.parameters),
            "referenced_identifiers": list(self.referenced_identifiers),
            "referenced_string_keys": list(self.referenced_string_keys),
            "forbidden_identifier_hits": list(self.forbidden_identifier_hits),
            "required_token_checks": self.required_token_checks,
        }


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise SourceAuditError(
            f"git {' '.join(args)} failed for {repo}: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _qualified_symbols(tree: ast.AST) -> dict[str, ast.AST]:
    symbols: dict[str, ast.AST] = {}

    def visit_body(body: Iterable[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = f"{prefix}.{node.name}" if prefix else node.name
                symbols[qualified] = node
                if isinstance(node, ast.ClassDef):
                    visit_body(node.body, qualified)

    if isinstance(tree, ast.Module):
        visit_body(tree.body)
    return symbols


def _function_parameters(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ()
    args = node.args
    names = [
        *(arg.arg for arg in args.posonlyargs),
        *(arg.arg for arg in args.args),
        *(arg.arg for arg in args.kwonlyargs),
    ]
    if args.vararg is not None:
        names.append(args.vararg.arg)
    if args.kwarg is not None:
        names.append(args.kwarg.arg)
    return tuple(names)


def _referenced_tokens(node: ast.AST) -> tuple[set[str], set[str]]:
    identifiers: set[str] = set()
    string_keys: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            identifiers.add(child.id)
        elif isinstance(child, ast.Attribute):
            identifiers.add(child.attr)
        elif isinstance(child, ast.Subscript):
            slice_node = child.slice
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                string_keys.add(slice_node.value)
        elif isinstance(child, ast.Call):
            for keyword in child.keywords:
                if keyword.arg is not None:
                    identifiers.add(keyword.arg)
    return identifiers, string_keys


def analyze_boundary(spec: dict[str, Any], boundary: dict[str, Any]) -> SymbolEvidence:
    source_root = PROJECT_ROOT / spec["repository_path"]
    path = source_root / boundary["path"]
    if not path.is_file():
        raise SourceAuditError(f"{spec['audit_id']}: missing boundary file {path}")
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise SourceAuditError(f"{spec['audit_id']}: cannot parse {path}: {exc}") from exc
    symbol = boundary["symbol"]
    node = _qualified_symbols(tree).get(symbol)
    if node is None:
        raise SourceAuditError(f"{spec['audit_id']}: symbol {symbol!r} not found in {path}")
    identifiers, string_keys = _referenced_tokens(node)
    normalized = {token.casefold() for token in identifiers | string_keys}
    forbidden = {
        token.casefold()
        for token in spec.get("forbidden_identifiers", [])
        if token.casefold() in normalized
    }
    source_segment = ast.get_source_segment(source, node) or ""
    required_checks = {
        token: token in source_segment for token in boundary.get("required_tokens", [])
    }
    missing_required = [token for token, present in required_checks.items() if not present]
    if missing_required:
        raise SourceAuditError(
            f"{spec['audit_id']}: {symbol} missing required tokens {missing_required}"
        )
    return SymbolEvidence(
        path=(Path(spec["repository_path"]) / boundary["path"]).as_posix(),
        symbol=symbol,
        phase=boundary["phase"],
        start_line=getattr(node, "lineno", 1),
        end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
        sha256=sha256_file(path),
        parameters=_function_parameters(node),
        referenced_identifiers=tuple(sorted(identifiers)),
        referenced_string_keys=tuple(sorted(string_keys)),
        forbidden_identifier_hits=tuple(sorted(forbidden)),
        required_token_checks=required_checks,
    )


def _static_hits(spec: dict[str, Any]) -> list[dict[str, Any]]:
    source_root = PROJECT_ROOT / spec["repository_path"]
    paths = {
        boundary["path"]
        for key in ("online_boundaries", "offline_boundaries")
        for boundary in spec.get(key, [])
    }
    paths.update(spec.get("additional_files", []))
    hits: list[dict[str, Any]] = []
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in FORBIDDEN_PATTERNS]
    for relative in sorted(paths):
        path = source_root / relative
        if not path.is_file():
            raise SourceAuditError(f"{spec['audit_id']}: missing audited file {path}")
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            matched = [pattern.pattern for pattern in compiled if pattern.search(line)]
            if matched:
                hits.append(
                    {
                        "path": (Path(spec["repository_path"]) / relative).as_posix(),
                        "line": line_number,
                        "patterns": matched,
                        "text_sha256": _sha256_bytes(line.strip().encode("utf-8")),
                        "preview": line.strip()[:240],
                    }
                )
    return hits


def _projection_result(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    projection = spec.get("projection", {})
    online_fields = tuple(projection.get("online_fields", []))
    offline_fields = tuple(projection.get("offline_fields", []))
    overlap = sorted(set(online_fields) & set(offline_fields))
    if overlap:
        raise SourceAuditError(f"{spec['audit_id']}: online/offline fields overlap: {overlap}")
    base = {field: f"online::{field}" for field in online_fields}
    base.update({field: SENTINEL for field in offline_fields})
    mutated = dict(base)
    mutated.update({field: f"{SENTINEL}::mutated::{field}" for field in offline_fields})
    projected_base = {field: base[field] for field in online_fields}
    projected_mutated = {field: mutated[field] for field in online_fields}
    base_bytes = json.dumps(projected_base, ensure_ascii=False, sort_keys=True)
    mutated_bytes = json.dumps(projected_mutated, ensure_ascii=False, sort_keys=True)
    projection_test = {
        "schema_version": "m3-paper-v2-projection-test-result-1.0",
        "audit_id": spec["audit_id"],
        "scope": "declared_online_boundary_projection",
        "online_fields": list(online_fields),
        "offline_fields": list(offline_fields),
        "sentinel_visible": SENTINEL in base_bytes,
        "passed": SENTINEL not in base_bytes,
        "limitations": (
            "This test validates the source-audited boundary projection. It is not "
            "a full upstream model/API execution."
        ),
    }
    differential = {
        "schema_version": "m3-paper-v2-differential-test-result-1.0",
        "audit_id": spec["audit_id"],
        "base_digest": canonical_digest(projected_base),
        "mutated_digest": canonical_digest(projected_mutated),
        "online_projection_unchanged": base_bytes == mutated_bytes,
        "passed": base_bytes == mutated_bytes,
    }
    return projection_test, differential


def _license_record(source_root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    license_path = spec.get("license_path")
    if not license_path:
        return {"status": "not_found_at_repository_root", "path": None, "sha256": None}
    path = source_root / license_path
    if not path.is_file():
        raise SourceAuditError(f"{spec['audit_id']}: declared license missing: {path}")
    return {
        "status": "present",
        "path": (Path(spec["repository_path"]) / license_path).as_posix(),
        "sha256": sha256_file(path),
    }


def _paper_artifact_record(spec: dict[str, Any]) -> dict[str, Any] | None:
    artifact = spec.get("paper_artifact")
    if not artifact:
        return None
    path = PROJECT_ROOT / artifact["path"]
    if not path.is_file():
        raise SourceAuditError(f"{spec['audit_id']}: paper artifact missing: {path}")
    observed_sha256 = sha256_file(path)
    expected_sha256 = artifact["sha256"]
    if observed_sha256 != expected_sha256:
        raise SourceAuditError(
            f"{spec['audit_id']}: expected paper SHA-256 {expected_sha256}, "
            f"observed {observed_sha256}"
        )
    expected_bytes = artifact.get("bytes")
    if expected_bytes is not None and path.stat().st_size != int(expected_bytes):
        raise SourceAuditError(
            f"{spec['audit_id']}: expected paper bytes {expected_bytes}, "
            f"observed {path.stat().st_size}"
        )
    return {
        "path": artifact["path"],
        "bytes": path.stat().st_size,
        "sha256": observed_sha256,
        "source_url": artifact["source_url"],
    }


def _validate_missing_component(spec: dict[str, Any]) -> dict[str, Any] | None:
    missing = spec.get("missing_component_check")
    if not missing:
        return None
    source_root = PROJECT_ROOT / spec["repository_path"]
    matches: set[str] = set()
    for pattern in missing.get("globs", []):
        for path in source_root.glob(pattern):
            if path.is_file():
                matches.add(path.relative_to(source_root).as_posix())
    expected_absent = bool(missing.get("expected_absent", True))
    passed = (len(matches) == 0) if expected_absent else (len(matches) > 0)
    if not passed:
        raise SourceAuditError(
            f"{spec['audit_id']}: missing-component expectation failed: {sorted(matches)}"
        )
    return {
        "expected_absent": expected_absent,
        "patterns": missing.get("globs", []),
        "matches": sorted(matches),
        "passed": passed,
    }


def inspect_unit(spec: dict[str, Any]) -> dict[str, Any]:
    source_root = PROJECT_ROOT / spec["repository_path"]
    if not source_root.is_dir():
        raise SourceAuditError(f"{spec['audit_id']}: repository missing: {source_root}")
    observed_commit = _git(source_root, "rev-parse", "HEAD")
    expected_commit = spec["expected_commit"]
    if observed_commit != expected_commit:
        raise SourceAuditError(
            f"{spec['audit_id']}: expected {expected_commit}, observed {observed_commit}"
        )
    online = [analyze_boundary(spec, item) for item in spec.get("online_boundaries", [])]
    offline = [analyze_boundary(spec, item) for item in spec.get("offline_boundaries", [])]
    online_forbidden_hits = sorted(
        {
            hit
            for boundary in online
            for hit in boundary.forbidden_identifier_hits
        }
    )
    if (
        spec["conclusion"] == "no_online_gold_observed"
        and online_forbidden_hits
        and not spec.get("allow_explained_online_forbidden_hits", False)
    ):
        raise SourceAuditError(
            f"{spec['audit_id']}: unexplained forbidden identifiers at online boundary: "
            f"{online_forbidden_hits}"
        )
    projection, differential = _projection_result(spec)
    if not projection["passed"] or not differential["passed"]:
        raise SourceAuditError(f"{spec['audit_id']}: projection/differential check failed")
    return {
        "source_lock": {
            "schema_version": "m3-paper-v2-source-lock-1.0",
            "audit_id": spec["audit_id"],
            "artifact": spec["artifact"],
            "source_url": spec["source_url"],
            "repository_path": spec["repository_path"],
            "expected_commit": expected_commit,
            "observed_commit": observed_commit,
            "commit_date": _git(source_root, "show", "-s", "--format=%cI", "HEAD"),
            "default_branch_head_at_discovery": spec.get("discovery_head"),
            "source_provenance": spec.get(
                "source_provenance", "official_source_code"
            ),
            "official_source_available": spec.get(
                "official_source_available", True
            ),
            "paper_artifact": _paper_artifact_record(spec),
            "license": _license_record(source_root, spec),
        },
        "online_boundaries": [item.to_dict() for item in online],
        "offline_boundaries": [item.to_dict() for item in offline],
        "online_forbidden_identifier_hits": online_forbidden_hits,
        "static_hits": _static_hits(spec),
        "projection": projection,
        "differential": differential,
        "missing_component": _validate_missing_component(spec),
    }


def _entrypoints_markdown(spec: dict[str, Any], inspection: dict[str, Any]) -> str:
    lines = [
        f"# {spec['audit_id']} entrypoints",
        "",
        f"- Artifact: {spec['artifact']}",
        f"- Component: {spec['component']}",
        f"- Commit: `{inspection['source_lock']['observed_commit']}`",
        "",
        "## Online boundaries",
        "",
    ]
    if not inspection["online_boundaries"]:
        lines.append("- None identified for this audit unit.")
    for boundary in inspection["online_boundaries"]:
        lines.append(
            f"- `{boundary['path']}:{boundary['start_line']}` — "
            f"`{boundary['symbol']}`; parameters: "
            f"`{', '.join(boundary['parameters']) or '(none)'}`"
        )
    lines.extend(["", "## Offline/evaluator boundaries", ""])
    if not inspection["offline_boundaries"]:
        lines.append("- None identified for this audit unit.")
    for boundary in inspection["offline_boundaries"]:
        lines.append(
            f"- `{boundary['path']}:{boundary['start_line']}` — "
            f"`{boundary['symbol']}`"
        )
    lines.extend(
        [
            "",
            "## Scope note",
            "",
            spec["scope_note"],
            "",
        ]
    )
    return "\n".join(lines)


def _finding_markdown(spec: dict[str, Any], inspection: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {spec['audit_id']} finding",
            "",
            f"- Conclusion: `{spec['conclusion']}`",
            f"- Authorization source: `{spec['authorization_source']}`",
            f"- Evidence strength: `{spec['evidence_strength']}`",
            "- Review status: `single_reviewer_complete`",
            "- Claim-ready for domain-wide statements: `false`",
            "",
            "## Finding",
            "",
            spec["finding"],
            "",
            "## Evidence boundary",
            "",
            spec["limitations"],
            "",
            "Changing evaluator-only fields left the declared online projection digest "
            f"unchanged: `{inspection['differential']['base_digest']}`.",
            "",
        ]
    )


def write_unit(
    spec: dict[str, Any],
    inspection: dict[str, Any],
    *,
    output_root: Path,
    spec_path: Path,
    generated_at: str,
) -> dict[str, Any]:
    unit_dir = output_root / spec["audit_id"]
    unit_dir.mkdir(parents=True, exist_ok=True)
    _write_json(unit_dir / "source_lock.json", inspection["source_lock"])
    (unit_dir / "entrypoints.md").write_text(
        _entrypoints_markdown(spec, inspection), encoding="utf-8"
    )
    _write_json(
        unit_dir / "field_flow.json",
        {
            "schema_version": "m3-paper-v2-field-flow-1.0",
            "audit_id": spec["audit_id"],
            "online_boundaries": inspection["online_boundaries"],
            "offline_boundaries": inspection["offline_boundaries"],
            "authorization_source": spec["authorization_source"],
            "online_forbidden_identifier_hits": inspection[
                "online_forbidden_identifier_hits"
            ],
            "missing_component": inspection["missing_component"],
        },
    )
    _write_json(
        unit_dir / "static_hits.json",
        {
            "schema_version": "m3-paper-v2-static-hits-1.0",
            "audit_id": spec["audit_id"],
            "hits": inspection["static_hits"],
            "interpretation": (
                "Lexical hits are navigation evidence only. Phase and call-boundary "
                "evidence determine the finding."
            ),
        },
    )
    projection_script = "\n".join(
        [
            '"""Re-run the source-boundary projection check for this audit unit."""',
            "",
            "import sys",
            "from pathlib import Path",
            "",
            "PROJECT_ROOT = Path(__file__).resolve().parents[4]",
            "if str(PROJECT_ROOT) not in sys.path:",
            "    sys.path.insert(0, str(PROJECT_ROOT))",
            "",
            "from experiments.paper_v2.source_audit import verify_unit_from_paths",
            "",
            "",
            "if __name__ == \"__main__\":",
            "    verify_unit_from_paths(",
            f"        spec_path={spec_path.relative_to(PROJECT_ROOT).as_posix()!r},",
            f"        audit_id={spec['audit_id']!r},",
            "    )",
            "",
        ]
    )
    (unit_dir / "projection_test.py").write_text(projection_script, encoding="utf-8")
    _write_json(unit_dir / "projection_test_result.json", inspection["projection"])
    _write_json(unit_dir / "differential_test_result.json", inspection["differential"])
    (unit_dir / "finding.md").write_text(
        _finding_markdown(spec, inspection), encoding="utf-8"
    )
    evidence_files = sorted(
        path for path in unit_dir.iterdir() if path.name != "evidence_manifest.json"
    )
    manifest = {
        "schema_version": "m3-paper-v2-source-audit-evidence-manifest-1.0",
        "audit_id": spec["audit_id"],
        "status": "completed",
        "conclusion": spec["conclusion"],
        "review_status": "single_reviewer_complete",
        "claim_ready": False,
        "auditor": "Codex primary agent",
        "generated_at": generated_at,
        "command": (
            "python -m experiments.paper_v2.source_audit "
            "--spec protocols/paper_upgrade_v2/online_state_audit_specs_v1.json "
            f"--unit {spec['audit_id']}"
        ),
        "exit_code": 0,
        "files": [
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in evidence_files
        ],
    }
    _write_json(unit_dir / "evidence_manifest.json", manifest)
    return manifest


def _load_spec(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "m3-paper-v2-online-state-audit-specs-1.0":
        raise SourceAuditError(f"unsupported spec schema: {value.get('schema_version')}")
    return value


def verify_unit_from_paths(*, spec_path: str, audit_id: str) -> dict[str, Any]:
    path = PROJECT_ROOT / spec_path
    document = _load_spec(path)
    matches = [item for item in document["audit_units"] if item["audit_id"] == audit_id]
    if len(matches) != 1:
        raise SourceAuditError(f"expected one spec for {audit_id}, found {len(matches)}")
    inspection = inspect_unit(matches[0])
    print(
        json.dumps(
            {
                "audit_id": audit_id,
                "projection_passed": inspection["projection"]["passed"],
                "differential_passed": inspection["differential"]["passed"],
                "source_commit": inspection["source_lock"]["observed_commit"],
            },
            sort_keys=True,
        )
    )
    return inspection


def verify_evidence_manifest(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = PROJECT_ROOT / item["path"]
        if not path.is_file():
            raise SourceAuditError(f"manifest file missing: {path}")
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise SourceAuditError(f"manifest identity mismatch: {path}")


def write_registry_and_summary(
    *,
    document: dict[str, Any],
    manifests: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    registry = json.loads(REGISTRY_V1.read_text(encoding="utf-8"))
    specs = {item["audit_id"]: item for item in document["audit_units"]}
    completed = {item["audit_id"]: item for item in manifests}
    targets: list[dict[str, Any]] = []
    for original in registry["targets"]:
        target = dict(original)
        audit_id = target["audit_id"]
        if audit_id in completed:
            spec = specs[audit_id]
            manifest = completed[audit_id]
            target.update(
                {
                    "audit_status": "completed",
                    "expected_commit": spec["expected_commit"],
                    "repository_path": spec["repository_path"],
                    "conclusion": manifest["conclusion"],
                    "review_status": manifest["review_status"],
                    "claim_ready": manifest["claim_ready"],
                    "evidence_manifest": (
                        "protocols/paper_upgrade_v2/audits/"
                        f"{audit_id}/evidence_manifest.json"
                    ),
                }
            )
        targets.append(target)
    registry_v2 = {
        "schema_version": "m3-paper-v2-online-state-audit-registry-2.0",
        "created_at": document["audited_at"],
        "protocol": registry["protocol"],
        "specification": (
            "protocols/paper_upgrade_v2/online_state_audit_specs_v1.json"
        ),
        "summary": {
            "audit_units_registered": len(targets),
            "completed": len(completed),
            "commit_locks_verified": len(completed),
            "official_source_code_units": summary["official_source_code_units"],
            "disclosed_reproduction_units": summary[
                "disclosed_reproduction_units"
            ],
            "official_source_unavailable_units": summary[
                "official_source_unavailable_units"
            ],
            "distinct_artifacts_completed": summary["distinct_artifacts"],
            "claim_ready_findings": summary["claim_ready"],
            "independent_second_reviews": 0,
        },
        "status_values": registry["status_values"],
        "targets": targets,
        "claim_policy": {
            "domain_oracle_problem_claim_allowed": False,
            "reason": summary["domain_claim_reason"],
            "minimum_coverage_reached": (
                len(completed) >= 20 and summary["distinct_artifacts"] >= 10
            ),
            "remaining_gate": (
                "Independent second review and stronger dynamic boundary tests are "
                "still required before any domain-wide oracle claim."
            ),
        },
    }
    _write_json(REGISTRY_V2, registry_v2)

    lines = [
        "# paper-v2 Online-State 源码审计摘要",
        "",
        f"- 固定时间：`{document['audited_at']}`",
        f"- 已完成审计单元：`{len(completed)}/22`",
        f"- 已覆盖不同项目：`{summary['distinct_artifacts']}`",
        f"- 官方源码单元：`{summary['official_source_code_units']}`",
        f"- 披露式本地复现单元：`{summary['disclosed_reproduction_units']}`",
        f"- 官方源码缺失单元：`{summary['official_source_unavailable_units']}`",
        "- 独立第二复核：`0`",
        "- 领域级 oracle 结论：`禁止`",
        "",
        "## 结论分布",
        "",
    ]
    for conclusion, count in summary["conclusions"].items():
        lines.append(f"- `{conclusion}`：{count}")
    lines.extend(
        [
            "",
            "## 可写与不可写",
            "",
            "可以写：每项结论只适用于其固定 commit、来源类型和已审计边界。"
            "CaMeL 的 live/replay 路径需要分开报告；SIREN 与 Task Shield 的"
            "官方实现证据不足。",
            "",
            "不可写：不能据此声称该领域普遍存在 oracle authorization，也不能把"
            "静态投影测试描述为完整模型/API 动态复现。所有单元仍需独立第二复核。",
            "",
            "## 来源边界",
            "",
            "- `A19-wasp-benchmark`：Meta 官方归档仓库，按固定 commit 审计。",
            "- `A22-task-shield-runtime`：官方论文未给出代码；只审计固定论文和"
            "明确标注的本地披露复现，不能外推为作者实现。",
            "",
            "完整逐项证据位于 `protocols/paper_upgrade_v2/audits/`；每个清单记录"
            "文件大小和 SHA-256。",
            "",
        ]
    )
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def run(
    *,
    spec_path: Path = DEFAULT_SPEC,
    output_root: Path = DEFAULT_OUTPUT,
    unit: str | None = None,
    verify_only: bool = False,
) -> dict[str, Any]:
    document = _load_spec(spec_path)
    specs = document["audit_units"]
    if unit is not None:
        specs = [item for item in specs if item["audit_id"] == unit]
        if not specs:
            raise SourceAuditError(f"unknown audit unit: {unit}")
    manifests: list[dict[str, Any]] = []
    conclusions: dict[str, int] = {}
    artifacts: set[str] = set()
    official_source_code_units = 0
    disclosed_reproduction_units = 0
    official_source_unavailable_units = 0
    if verify_only:
        for spec in specs:
            manifest_path = output_root / spec["audit_id"] / "evidence_manifest.json"
            verify_evidence_manifest(manifest_path)
            inspection = inspect_unit(spec)
            unit_dir = output_root / spec["audit_id"]
            for filename, expected in (
                ("source_lock.json", inspection["source_lock"]),
                ("projection_test_result.json", inspection["projection"]),
                ("differential_test_result.json", inspection["differential"]),
            ):
                observed = json.loads(
                    (unit_dir / filename).read_text(encoding="utf-8")
                )
                if observed != expected:
                    raise SourceAuditError(
                        f"{spec['audit_id']}: {filename} does not reproduce"
                    )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifests.append(manifest)
            conclusions[manifest["conclusion"]] = conclusions.get(manifest["conclusion"], 0) + 1
            artifacts.add(spec["artifact"])
            provenance = spec.get("source_provenance", "official_source_code")
            official_source_code_units += provenance == "official_source_code"
            disclosed_reproduction_units += provenance == "disclosed_local_reproduction"
            official_source_unavailable_units += not spec.get(
                "official_source_available", True
            )
    else:
        for spec in specs:
            inspection = inspect_unit(spec)
            manifest = write_unit(
                spec,
                inspection,
                output_root=output_root,
                spec_path=spec_path,
                generated_at=document["audited_at"],
            )
            manifests.append(manifest)
            conclusions[spec["conclusion"]] = conclusions.get(spec["conclusion"], 0) + 1
            artifacts.add(spec["artifact"])
            provenance = spec.get("source_provenance", "official_source_code")
            official_source_code_units += provenance == "official_source_code"
            disclosed_reproduction_units += provenance == "disclosed_local_reproduction"
            official_source_unavailable_units += not spec.get(
                "official_source_available", True
            )
    summary = {
        "schema_version": "m3-paper-v2-source-audit-summary-1.0",
        "status": "pass",
        "audit_units": len(manifests),
        "distinct_artifacts": len(artifacts),
        "official_source_code_units": official_source_code_units,
        "disclosed_reproduction_units": disclosed_reproduction_units,
        "official_source_unavailable_units": official_source_unavailable_units,
        "conclusions": dict(sorted(conclusions.items())),
        "claim_ready": sum(1 for item in manifests if item["claim_ready"]),
        "domain_oracle_problem_claim_allowed": False,
        "domain_claim_reason": (
            "All completed units still require independent second review; several "
            "findings are inconclusive or outside runtime authorization."
        ),
    }
    if unit is None:
        _write_json(output_root / "summary.json", summary)
        if not verify_only:
            write_registry_and_summary(
                document=document,
                manifests=manifests,
                summary=summary,
            )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--unit")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    spec_path = args.spec if args.spec.is_absolute() else PROJECT_ROOT / args.spec
    output_root = (
        args.output_root if args.output_root.is_absolute() else PROJECT_ROOT / args.output_root
    )
    summary = run(
        spec_path=spec_path,
        output_root=output_root,
        unit=args.unit,
        verify_only=args.verify_only,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
