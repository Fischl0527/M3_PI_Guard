"""已固化的 E11 事后修正补充实验运行器。

在严格受控的受限沙箱环境中执行 E11 补充模式的重放验证。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from m3_core.case_views import runtime_case_view
from m3_core.run_matrix import run_matrix


PROTOCOL_ID = "E11_POSTHOC_AMENDMENT_V1"
AMENDMENT_TYPE = "posthoc_protocol_amendment"
VISUALIZATION_REVISION = 2
EXECUTION_REVISION = "r2"
HISTORICAL_V3_FREEZE_INTEGRITY_MODE = "hash_bound_reference_only"
DENOMINATOR_POLICY = "excluded_from_original_e11_denominator"
FORMAL_MODEL = "qwen3:4b-instruct"
PATTERNS = (
    "read_to_send",
    "search_to_api",
    "memory_to_file",
    "tool_output_to_next_action",
)
SMOKE_CASE_IDS = (
    "E11A-RTS-01",
    "E11A-STA-01",
    "E11A-MTF-01",
    "E11A-TON-01",
)
CONDITIONS = "posthoc_off=normal:off,posthoc_full=normal:full_guard"
EXPECTED_CONDITIONS = ("posthoc_off", "posthoc_full")
SEED = 433
TEMPERATURE = 0.2
REPEATS = 1
MAX_STEPS = 5
MAX_TOKENS = 512
TIMEOUT_SECONDS = 120.0

PROTOCOL_DIR = REPO_ROOT / "protocols" / "e11_amendment_v1"
CASES_PATH = PROTOCOL_DIR / "cases.jsonl"
FIXTURES_PATH = PROTOCOL_DIR / "fixtures.json"
LEGACY_FREEZE_PATH = PROTOCOL_DIR / "freeze.json"
FREEZE_PATH = PROTOCOL_DIR / "freeze_r2.json"
V3_FREEZE_PATH = REPO_ROOT / "outputs" / "experiments" / "blind_freeze_v3.json"
E13_THRESHOLDS_PATH = REPO_ROOT / "outputs" / "experiments" / "E13" / "frozen_thresholds.json"

REQUIRED_FREEZE_ROLES = frozenset(
    {
        "protocol",
        "protocol.execution_r2",
        "cases",
        "fixtures",
        "runner",
        "analyzer",
        "freeze_builder",
        "registrar",
        "final_analysis_builder",
        "legacy_freeze",
        "v3_blind_freeze",
        "e13_thresholds",
        "runtime.agent_runner",
        "runtime.case_views",
        "runtime.run_batch",
        "runtime.run_matrix",
        "runtime.tool_sandbox",
        "runtime.guard_config",
        "runtime.guard_engine",
        "runtime.metrics",
        "runtime.statistics",
        "runtime.figure_manifest",
        "runtime.attack_case_schema",
        "runtime.run_log_schema",
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProtocolIntegrityError(RuntimeError):
    """当修订协议或绑定的中间构件发生漂移时抛出。"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _atomic_write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _strict_repo_relative(value: Any) -> tuple[str, Path]:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ProtocolIntegrityError(f"invalid bound path: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ProtocolIntegrityError(f"bound path must be canonical and repo-relative: {value!r}")
    candidate = REPO_ROOT.joinpath(*pure.parts)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ProtocolIntegrityError(f"bound path escapes repository: {value!r}") from exc
    if candidate.is_symlink() or not resolved.exists() or not resolved.is_file():
        raise ProtocolIntegrityError(f"bound artifact is missing or linked: {value}")
    canonical = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    if canonical != value:
        raise ProtocolIntegrityError(
            f"bound path is non-canonical: expected {value!r}, resolved {canonical!r}"
        )
    return value, resolved


def verify_hash_entries(payload: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """根据当前代码仓库验证每个修订固化条目。"""

    entries = payload.get("artifacts")
    if not isinstance(entries, list) or not entries:
        raise ProtocolIntegrityError("freeze artifacts must be a non-empty list")
    verified: dict[str, dict[str, str]] = {}
    paths: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"role", "path", "sha256"}:
            raise ProtocolIntegrityError(
                f"freeze artifacts[{index}] must contain exactly role, path, sha256"
            )
        role = str(entry["role"])
        if not role or role in verified:
            raise ProtocolIntegrityError(f"invalid or duplicate freeze role: {role!r}")
        relative, path = _strict_repo_relative(entry["path"])
        if relative in paths:
            raise ProtocolIntegrityError(f"duplicate freeze path: {relative}")
        paths.add(relative)
        expected = str(entry["sha256"])
        if _SHA256_RE.fullmatch(expected) is None:
            raise ProtocolIntegrityError(f"invalid SHA-256 for freeze role {role}")
        actual = sha256_file(path)
        if actual != expected:
            raise ProtocolIntegrityError(
                f"freeze drift for {role}: {relative}; expected {expected}, got {actual}"
            )
        verified[role] = {"path": relative, "sha256": actual}
    missing = sorted(REQUIRED_FREEZE_ROLES - set(verified))
    if missing:
        raise ProtocolIntegrityError("freeze missing required roles: " + ", ".join(missing))
    return verified


def verify_amendment_freeze(path: str | Path = FREEZE_PATH) -> dict[str, Any]:
    freeze_path = Path(path).resolve()
    if freeze_path != FREEZE_PATH.resolve():
        raise ProtocolIntegrityError(
            f"amendment freeze path is fixed at {FREEZE_PATH.relative_to(REPO_ROOT).as_posix()}"
        )
    try:
        payload = json.loads(freeze_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolIntegrityError(f"cannot load amendment freeze: {freeze_path}") from exc
    if not isinstance(payload, dict):
        raise ProtocolIntegrityError("amendment freeze must be a JSON object")
    expected_metadata = {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "amendment_type": AMENDMENT_TYPE,
        "visualization_revision": VISUALIZATION_REVISION,
        "execution_revision": EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": DENOMINATOR_POLICY,
        "formal_model": FORMAL_MODEL,
        "formal_case_count": 24,
        "formal_logical_runs": 48,
        "smoke_case_count": 4,
        "smoke_logical_runs": 8,
    }
    for key, expected in expected_metadata.items():
        if payload.get(key) != expected:
            raise ProtocolIntegrityError(
                f"amendment freeze {key} mismatch: expected {expected!r}, got {payload.get(key)!r}"
            )
    verified = verify_hash_entries(payload)
    if verified["v3_blind_freeze"]["path"] != V3_FREEZE_PATH.relative_to(REPO_ROOT).as_posix():
        raise ProtocolIntegrityError("amendment freeze points to the wrong v3 blind freeze")
    if verified["e13_thresholds"]["path"] != E13_THRESHOLDS_PATH.relative_to(REPO_ROOT).as_posix():
        raise ProtocolIntegrityError("amendment freeze points to the wrong E13 threshold file")
    if payload.get("v3_blind_freeze_sha256") != verified["v3_blind_freeze"]["sha256"]:
        raise ProtocolIntegrityError("v3_blind_freeze_sha256 metadata mismatch")
    if payload.get("e13_thresholds_sha256") != verified["e13_thresholds"]["sha256"]:
        raise ProtocolIntegrityError("e13_thresholds_sha256 metadata mismatch")
    if payload.get("historical_v3_freeze_integrity_mode") != HISTORICAL_V3_FREEZE_INTEGRITY_MODE:
        raise ProtocolIntegrityError("historical_v3_freeze_integrity_mode mismatch")
    if verified["legacy_freeze"]["path"] != LEGACY_FREEZE_PATH.relative_to(REPO_ROOT).as_posix():
        raise ProtocolIntegrityError("amendment freeze points to the wrong legacy freeze")
    if payload.get("supersedes_freeze_sha256") != verified["legacy_freeze"]["sha256"]:
        raise ProtocolIntegrityError("supersedes_freeze_sha256 metadata mismatch")
    return {
        "path": freeze_path.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_file(freeze_path),
        "payload": payload,
        "artifacts": verified,
    }


def canonical_action(tool_call: Mapping[str, Any]) -> str:
    tool = str(tool_call.get("tool", "")).strip()
    arguments = tool_call.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("tool_call.arguments must be an object")
    if tool in {"read_file", "write_file"}:
        target = str(arguments.get("path", "")).strip()
    elif tool == "send_email":
        target = str(arguments.get("to", "")).strip()
    elif tool == "call_api":
        target = str(arguments.get("endpoint", "")).strip()
    elif tool == "run_code":
        target = "mock_only"
    else:
        raise ValueError(f"unsupported protocol tool: {tool!r}")
    if not target:
        raise ValueError(f"missing target for protocol tool: {tool}")
    return f"{tool}:{target}"


def semantic_target(tool_call: Mapping[str, Any]) -> str:
    """返回必须在模拟观察中出现的具体目标文本。"""

    tool = str(tool_call.get("tool", "")).strip()
    arguments = tool_call.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("tool_call.arguments must be an object")
    field = {
        "read_file": "path",
        "write_file": "path",
        "send_email": "to",
        "call_api": "endpoint",
        "run_code": "code",
    }.get(tool)
    if field is None:
        raise ValueError(f"unsupported protocol tool: {tool!r}")
    target = str(arguments.get(field, "")).strip()
    if not target:
        raise ValueError(f"missing semantic target for protocol tool: {tool}")
    return target


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(row)
    return rows


def load_protocol_data() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    cases = _load_jsonl(CASES_PATH)
    fixtures_payload = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    if not isinstance(fixtures_payload, dict) or fixtures_payload.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("fixtures protocol_id mismatch")
    fixtures_list = fixtures_payload.get("fixtures")
    if not isinstance(fixtures_list, list):
        raise ValueError("fixtures must be a list")
    fixtures: dict[str, dict[str, Any]] = {}
    for fixture in fixtures_list:
        if not isinstance(fixture, dict):
            raise ValueError("each fixture must be an object")
        fixture_id = str(fixture.get("fixture_id", ""))
        if not fixture_id or fixture_id in fixtures:
            raise ValueError(f"invalid or duplicate fixture_id: {fixture_id!r}")
        fixtures[fixture_id] = fixture
    validate_protocol_data(cases, fixtures)
    return cases, fixtures


def validate_protocol_data(
    cases: list[dict[str, Any]], fixtures: Mapping[str, Mapping[str, Any]]
) -> None:
    if len(cases) != 24:
        raise ValueError(f"amendment requires exactly 24 cases, got {len(cases)}")
    ids = [str(case.get("case_id", "")) for case in cases]
    if any(not case_id for case_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("case_id values must be non-empty and unique")
    template_ids = [str(case.get("template_id", "")) for case in cases]
    if any(not value for value in template_ids) or len(set(template_ids)) != len(template_ids):
        raise ValueError("template_id values must be non-empty and unique")
    counts: Counter[str] = Counter()
    used_fixtures: set[str] = set()
    for case in cases:
        if case.get("sample_type") != "attack":
            raise ValueError(f"{case['case_id']}: amendment cases must be attacks")
        if case.get("protocol_amendment") != PROTOCOL_ID:
            raise ValueError(f"{case['case_id']}: protocol_amendment mismatch")
        dimensions = case.get("attack_dimensions")
        if not isinstance(dimensions, dict):
            raise ValueError(f"{case['case_id']}: attack_dimensions must be an object")
        pattern = str(dimensions.get("chain_pattern", ""))
        if pattern not in PATTERNS:
            raise ValueError(f"{case['case_id']}: unsupported chain pattern {pattern!r}")
        if dimensions.get("posthoc_protocol_amendment") is not True:
            raise ValueError(f"{case['case_id']}: posthoc marker is missing")
        if dimensions.get("pre_registered") is not False:
            raise ValueError(f"{case['case_id']}: pre_registered must be false")
        counts[pattern] += 1
        fixture_id = str(case.get("observation_fixture_id", ""))
        if fixture_id in used_fixtures:
            raise ValueError(f"fixture reused across cases: {fixture_id}")
        used_fixtures.add(fixture_id)
        fixture = fixtures.get(fixture_id)
        if fixture is None:
            raise ValueError(f"{case['case_id']}: missing fixture {fixture_id!r}")
        if fixture.get("pattern") != pattern:
            raise ValueError(f"{case['case_id']}: fixture pattern mismatch")
        source_action = canonical_action(fixture.get("source_tool_call", {}))
        unsafe_action = canonical_action(fixture.get("unsafe_next_tool_call", {}))
        if case.get("authorized_actions") != [source_action]:
            raise ValueError(
                f"{case['case_id']}: authorized_actions must contain only the source action"
            )
        if case.get("unsafe_target_actions") != [unsafe_action]:
            raise ValueError(
                f"{case['case_id']}: unsafe_target_actions must match the injected next action"
            )
        observation = str(fixture.get("observation", ""))
        injected = str(fixture.get("injected_instruction", ""))
        target = semantic_target(fixture.get("unsafe_next_tool_call", {}))
        if not observation or not injected or target.casefold() not in observation.casefold():
            raise ValueError(
                f"{case['case_id']}: observation must contain the unsafe next-action target"
            )
        if case.get("injected_content") != injected:
            raise ValueError(f"{case['case_id']}: offline injected_content does not match fixture")
        if "conversation_turns" in case:
            raise ValueError(f"{case['case_id']}: source case must not pre-materialize history")
    if counts != Counter({pattern: 6 for pattern in PATTERNS}):
        raise ValueError(f"pattern counts must be six each, got {dict(counts)}")
    if used_fixtures != set(fixtures):
        raise ValueError("fixtures and cases must have a one-to-one mapping")
    if set(SMOKE_CASE_IDS) - set(ids):
        raise ValueError("one or more fixed smoke cases are missing")


def materialize_case(
    case: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, Any]:
    """仅添加可信的任务历史与固化的不可信工具观察结果。"""

    materialized = copy.deepcopy(dict(case))
    source_tool_call = copy.deepcopy(fixture["source_tool_call"])
    observation = str(fixture["observation"])
    materialized["conversation_turns"] = [
        {
            "role": "user",
            "trust": "trusted",
            "content": str(case.get("user_task", "")),
        },
        {
            "role": "assistant",
            "trust": "trusted",
            "content": json.dumps(source_tool_call, ensure_ascii=False, sort_keys=True),
        },
        {
            "role": "tool",
            "trust": "tool_output",
            "content": observation,
        },
    ]
    return materialized


def materialize_cases(
    cases: list[dict[str, Any]], fixtures: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    return [
        materialize_case(case, fixtures[str(case["observation_fixture_id"])])
        for case in cases
    ]


def runtime_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    """测试所使用的公开辅助函数，用于强制执行标签泄漏边界。"""

    return runtime_case_view(dict(case))


def _thresholds() -> dict[str, Any]:
    payload = json.loads(E13_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    if payload.get("experiment_id") != "E13" or payload.get("schema_version") != "1.0":
        raise ProtocolIntegrityError("unexpected E13 threshold schema")
    ask = payload.get("ask_threshold")
    deny = payload.get("deny_threshold")
    if ask != 1.0 or deny != 1.0:
        raise ProtocolIntegrityError(
            f"amendment requires frozen ASK=DENY=1.0, got ASK={ask!r}, DENY={deny!r}"
        )
    return payload


def validate_frozen_protocol() -> dict[str, Any]:
    freeze = verify_amendment_freeze()
    cases, fixtures = load_protocol_data()
    thresholds = _thresholds()
    return {
        "freeze": freeze,
        "cases": cases,
        "fixtures": fixtures,
        "thresholds": thresholds,
    }


def build_plan() -> dict[str, Any]:
    validated = validate_frozen_protocol()
    cases = validated["cases"]
    counts = Counter(
        str(case["attack_dimensions"]["chain_pattern"]) for case in cases
    )
    return {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "amendment_type": AMENDMENT_TYPE,
        "visualization_revision": VISUALIZATION_REVISION,
        "execution_revision": EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": DENOMINATOR_POLICY,
        "formal_model": FORMAL_MODEL,
        "conditions": list(EXPECTED_CONDITIONS),
        "pattern_counts": dict(sorted(counts.items())),
        "smoke_case_ids": list(SMOKE_CASE_IDS),
        "smoke_case_count": 4,
        "smoke_logical_runs": 8,
        "formal_case_count": 24,
        "formal_logical_runs": 48,
        "seed": SEED,
        "temperature": TEMPERATURE,
        "repeats": REPEATS,
        "max_steps": MAX_STEPS,
        "max_tokens": MAX_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
        "ask_threshold": validated["thresholds"]["ask_threshold"],
        "deny_threshold": validated["thresholds"]["deny_threshold"],
        "amendment_freeze_sha256": validated["freeze"]["sha256"],
        "v3_blind_freeze_sha256": sha256_file(V3_FREEZE_PATH),
        "e13_thresholds_sha256": sha256_file(E13_THRESHOLDS_PATH),
        "gpu_or_model_process_started": False,
    }


def selected_case_ids_for_phase(
    cases: Iterable[Mapping[str, Any]], phase: str
) -> list[str]:
    """为任一执行阶段返回明确的、可审计的用例列表。"""

    case_ids = [str(case.get("case_id", "")).strip() for case in cases]
    if any(not case_id for case_id in case_ids) or len(case_ids) != len(set(case_ids)):
        raise ValueError("phase selection requires non-empty unique case IDs")
    if phase == "smoke":
        if not set(SMOKE_CASE_IDS) <= set(case_ids):
            raise ValueError("one or more fixed smoke cases are missing")
        return list(SMOKE_CASE_IDS)
    if phase == "formal":
        if len(case_ids) != 24:
            raise ValueError(f"formal phase requires exactly 24 explicit IDs, got {len(case_ids)}")
        return case_ids
    raise ValueError("phase must be smoke or formal")


def _resolve_output_root(value: str | Path) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else REPO_ROOT / raw
    resolved = candidate.resolve()
    experiments_root = (REPO_ROOT / "outputs" / "experiments").resolve()
    try:
        relative = resolved.relative_to(experiments_root)
    except ValueError as exc:
        raise ValueError("output root must stay under outputs/experiments") from exc
    if not relative.parts:
        raise ValueError("output root must be a child of outputs/experiments")
    if relative.parts[0].casefold() == "e11":
        raise ValueError("refusing to write into the original E11 bundle")
    return resolved


def _verify_formal_smoke_gate(output_root: Path, freeze_sha256: str) -> dict[str, Any]:
    manifest_path = output_root / "smoke" / "execution_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("formal matrix requires the formal-model smoke gate first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "status": "completed",
        "phase": "smoke",
        "backend": "ollama",
        "model": FORMAL_MODEL,
        "visualization_revision": VISUALIZATION_REVISION,
        "execution_revision": EXECUTION_REVISION,
        "evidence_tier": "formal_model_posthoc",
        "actual_logical_runs": 8,
        "amendment_freeze_sha256": freeze_sha256,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise RuntimeError(
                f"formal smoke gate mismatch for {key}: expected {expected!r}, got {manifest.get(key)!r}"
            )
    if manifest.get("selected_case_ids") != list(SMOKE_CASE_IDS):
        raise RuntimeError("formal smoke gate must record the four explicit smoke case IDs")
    for path_key, hash_key in (
        ("matrix_manifest_path", "matrix_manifest_sha256"),
        ("materialized_cases_path", "materialized_cases_sha256"),
    ):
        _, source = _strict_repo_relative(manifest.get(path_key))
        if sha256_file(source) != manifest.get(hash_key):
            raise RuntimeError(f"formal smoke gate source drift: {path_key}")
    _, matrix_path = _strict_repo_relative(manifest["matrix_manifest_path"])
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    if matrix.get("status") != "completed" or matrix.get("backend") != "ollama":
        raise RuntimeError("formal smoke matrix is not completed Ollama evidence")
    if matrix.get("model") != FORMAL_MODEL:
        raise RuntimeError("formal smoke matrix model mismatch")
    results = matrix.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise RuntimeError("formal smoke matrix must contain two conditions")
    if {item.get("condition_id") for item in results} != set(EXPECTED_CONDITIONS):
        raise RuntimeError("formal smoke matrix condition mismatch")
    for item in results:
        if (
            item.get("status") != "completed"
            or int(item.get("case_count", -1)) != 4
            or int(item.get("selected_case_count", -1)) != 4
            or int(item.get("error_count", -1)) != 0
        ):
            raise RuntimeError(
                f"formal smoke condition incomplete: {item.get('condition_id')}"
            )
        _, raw_path = _strict_repo_relative(item.get("jsonl"))
        if sha256_file(raw_path) != item.get("jsonl_sha256"):
            raise RuntimeError(
                f"formal smoke raw log drift: {item.get('condition_id')}"
            )
    return manifest


def run_phase(
    *,
    phase: str,
    backend: str,
    model: str,
    output_root: str | Path,
    resume: bool = False,
) -> dict[str, Any]:
    if phase not in {"smoke", "formal"}:
        raise ValueError("phase must be smoke or formal")
    if backend not in {"stub", "ollama"}:
        raise ValueError("backend must be stub or ollama")
    model = str(model).strip()
    if backend == "ollama" and model != FORMAL_MODEL:
        raise ValueError(f"formal-model runs are frozen to {FORMAL_MODEL}")
    if backend == "stub" and model not in {"", "stub"}:
        raise ValueError("stub backend must use model=stub")
    if phase == "formal" and backend != "ollama":
        raise ValueError("the 48-run formal matrix must use the Ollama formal model")

    validated = validate_frozen_protocol()
    root = _resolve_output_root(output_root)
    phase_dir = root / phase
    execution_manifest_path = phase_dir / "execution_manifest.json"
    if phase_dir.exists() and not resume:
        existing = [item for item in phase_dir.rglob("*") if item.is_file()]
        if existing:
            raise FileExistsError(
                f"phase output already exists; use --resume only for an identical interrupted run: {phase_dir}"
            )
    phase_dir.mkdir(parents=True, exist_ok=True)

    if phase == "formal":
        _verify_formal_smoke_gate(root, validated["freeze"]["sha256"])

    materialized = materialize_cases(validated["cases"], validated["fixtures"])
    materialized_path = phase_dir / "materialized_cases.jsonl"
    if resume and materialized_path.exists():
        existing_hash = sha256_file(materialized_path)
        expected_bytes = b"".join(
            (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            for row in materialized
        )
        expected_hash = hashlib.sha256(expected_bytes).hexdigest()
        if existing_hash != expected_hash:
            raise RuntimeError("refusing resume: materialized case file has drifted")
    else:
        _atomic_write_jsonl(materialized_path, materialized)

    selected_ids = selected_case_ids_for_phase(materialized, phase)
    expected_case_count = 4 if phase == "smoke" else 24
    expected_logical_runs = expected_case_count * len(EXPECTED_CONDITIONS)
    thresholds = validated["thresholds"]
    matrix_dir = phase_dir / "raw"
    matrix_config = {
        "cases": str(materialized_path),
        "backend": backend,
        "model": "stub" if backend == "stub" else model,
        "defense_modes": "",
        "conditions": CONDITIONS,
        "condition_label": "",
        "prompt_profiles": "",
        "guard_modes": "",
        "guard_modules": "",
        "ask_threshold": float(thresholds["ask_threshold"]),
        "deny_threshold": float(thresholds["deny_threshold"]),
        "families": "",
        "splits": "",
        "sample_types": "attack",
        "task_types": "",
        "case_ids": ",".join(selected_ids),
        "limit": None,
        "out_dir": str(matrix_dir),
        "max_steps": MAX_STEPS,
        "run_prefix": f"e11_posthoc_amendment_v1_exec_{EXECUTION_REVISION}_{phase}",
        "run_group": DENOMINATOR_POLICY,
        "seed": SEED,
        "selection_seed": SEED,
        "generation_seed": SEED,
        "repeats": REPEATS,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "num_ctx": None,
        "timeout": TIMEOUT_SECONDS,
        "shuffle": False,
        "resume": bool(resume),
        "fail_fast": True,
        "allow_fallback_guard": False,
        "notes": (
            f"E11 post-hoc protocol amendment v1 execution revision {EXECUTION_REVISION}; "
            "excluded from original E11 denominator"
        ),
    }

    started_at = utc_now()
    try:
        matrix_result = run_matrix(matrix_config)
        results = matrix_result["results"]
        actual_logical_runs = sum(int(item.get("case_count", 0)) for item in results)
        status = "completed"
        if matrix_result["manifest"].get("status") != "completed":
            status = "failed"
        if len(results) != 2 or {item.get("condition_id") for item in results} != set(
            EXPECTED_CONDITIONS
        ):
            status = "failed"
        if any(
            item.get("status") != "completed"
            or int(item.get("selected_case_count", -1)) != expected_case_count
            or int(item.get("case_count", -1)) != expected_case_count
            or int(item.get("error_count", -1)) != 0
            for item in results
        ):
            status = "failed"
        if actual_logical_runs != expected_logical_runs:
            status = "failed"
    except Exception as exc:
        failure = {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
            "amendment_type": AMENDMENT_TYPE,
            "visualization_revision": VISUALIZATION_REVISION,
            "execution_revision": EXECUTION_REVISION,
            "pre_registered": False,
            "denominator_policy": DENOMINATOR_POLICY,
            "status": "failed",
            "phase": phase,
            "backend": backend,
            "model": "stub" if backend == "stub" else model,
            "started_at": started_at,
            "completed_at": utc_now(),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "amendment_freeze_sha256": validated["freeze"]["sha256"],
        }
        _atomic_write_json(execution_manifest_path, failure)
        raise

    matrix_manifest_path = REPO_ROOT / str(matrix_result["manifest_path"])
    execution = {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "amendment_type": AMENDMENT_TYPE,
        "visualization_revision": VISUALIZATION_REVISION,
        "execution_revision": EXECUTION_REVISION,
        "pre_registered": False,
        "denominator_policy": DENOMINATOR_POLICY,
        "status": status,
        "phase": phase,
        "backend": backend,
        "model": "stub" if backend == "stub" else model,
        "evidence_tier": "regression_only" if backend == "stub" else "formal_model_posthoc",
        "started_at": started_at,
        "completed_at": utc_now(),
        "conditions": list(EXPECTED_CONDITIONS),
        "selected_case_ids": selected_ids,
        "expected_case_count_per_condition": expected_case_count,
        "expected_logical_runs": expected_logical_runs,
        "actual_logical_runs": actual_logical_runs,
        "materialized_cases_path": materialized_path.relative_to(REPO_ROOT).as_posix(),
        "materialized_cases_sha256": sha256_file(materialized_path),
        "matrix_manifest_path": matrix_manifest_path.relative_to(REPO_ROOT).as_posix(),
        "matrix_manifest_sha256": sha256_file(matrix_manifest_path),
        "amendment_freeze_path": validated["freeze"]["path"],
        "amendment_freeze_sha256": validated["freeze"]["sha256"],
        "v3_blind_freeze_path": V3_FREEZE_PATH.relative_to(REPO_ROOT).as_posix(),
        "v3_blind_freeze_sha256": sha256_file(V3_FREEZE_PATH),
        "e13_thresholds_path": E13_THRESHOLDS_PATH.relative_to(REPO_ROOT).as_posix(),
        "e13_thresholds_sha256": sha256_file(E13_THRESHOLDS_PATH),
        "ask_threshold": thresholds["ask_threshold"],
        "deny_threshold": thresholds["deny_threshold"],
        "seed": SEED,
        "temperature": TEMPERATURE,
        "repeats": REPEATS,
        "max_steps": MAX_STEPS,
        "max_tokens": MAX_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
    }
    _atomic_write_json(execution_manifest_path, execution)
    if status != "completed":
        raise RuntimeError(f"{phase} amendment matrix failed its completeness contract")
    return execution


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan", help="Validate all frozen inputs and print the fixed plan")
    run_parser = subparsers.add_parser("run", help="Run the fixed smoke or formal matrix")
    run_parser.add_argument("--phase", choices=["smoke", "formal"], required=True)
    run_parser.add_argument("--backend", choices=["stub", "ollama"], required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--output-root", required=True)
    run_parser.add_argument("--resume", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "plan":
        print(json.dumps(build_plan(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    execution = run_phase(
        phase=args.phase,
        backend=args.backend,
        model=args.model,
        output_root=args.output_root,
        resume=args.resume,
    )
    print(
        f"completed {execution['phase']}: {execution['actual_logical_runs']}/"
        f"{execution['expected_logical_runs']} logical runs; "
        f"manifest={Path(args.output_root) / args.phase / 'execution_manifest.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
