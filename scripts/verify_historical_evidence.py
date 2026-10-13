"""并排验证历史不可变实验证据与当前 V2 固化版本的一致性。

防止历史基准实验数据在后续演进中发生意外篡改或漂移。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DECLARATION = ROOT / "protocols" / "historical_evidence_compatibility_v1.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class HistoricalEvidenceError(RuntimeError):
    """当不可变数据包或声明的漂移不再匹配时抛出。"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_file(value: Any) -> tuple[str, Path]:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise HistoricalEvidenceError(f"invalid repository path: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise HistoricalEvidenceError(f"path must be canonical and repository-relative: {value!r}")
    path = ROOT.joinpath(*pure.parts).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise HistoricalEvidenceError(f"path escapes repository: {value}") from exc
    if not path.is_file() or path.is_symlink():
        raise HistoricalEvidenceError(f"evidence file missing or linked: {value}")
    return value, path


def verified_record(
    record: Mapping[str, Any], *, base_dir: Path | None = None
) -> dict[str, Any]:
    value = record.get("path")
    expected = record.get("sha256")
    if not isinstance(value, str) or not value or "\x00" in value:
        raise HistoricalEvidenceError(f"invalid evidence path: {value!r}")
    if not isinstance(expected, str) or SHA256_RE.fullmatch(expected) is None:
        raise HistoricalEvidenceError(f"invalid SHA-256 for {value}")
    expected_bytes = record.get("bytes")
    raw = Path(value)
    candidates = [raw] if raw.is_absolute() else [ROOT / raw]
    if not raw.is_absolute() and base_dir is not None:
        candidates.append(base_dir / raw)
    checked: list[str] = []
    for candidate in candidates:
        path = candidate.resolve()
        try:
            relative = path.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            continue
        if not path.is_file() or path.is_symlink():
            continue
        actual = sha256_file(path)
        checked.append(f"{relative}={actual}")
        if actual != expected:
            continue
        if expected_bytes is not None and expected_bytes != path.stat().st_size:
            continue
        return {"path": relative, "sha256": actual, "bytes": path.stat().st_size}
    raise HistoricalEvidenceError(
        f"evidence record did not resolve to its declared bytes: {value}; checked {checked}"
    )


def reference_records(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            yield value
        for nested in value.values():
            yield from reference_records(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from reference_records(nested)


def verify_current_freeze(record: Mapping[str, Any]) -> dict[str, Any]:
    freeze_record = verified_record(record)
    freeze = json.loads((ROOT / freeze_record["path"]).read_text(encoding="utf-8"))
    source_records = freeze.get("source_records")
    if not isinstance(source_records, list) or not source_records:
        raise HistoricalEvidenceError("current evidence freeze has no source_records")
    verified = [verified_record(item) for item in source_records]
    return {"freeze": freeze_record, "source_records": len(verified)}


def verify_historical_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    bundle_id = bundle.get("id")
    freeze_spec = bundle.get("freeze")
    if not isinstance(bundle_id, str) or not isinstance(freeze_spec, Mapping):
        raise HistoricalEvidenceError("invalid historical bundle declaration")
    freeze_record = verified_record(freeze_spec)
    freeze = json.loads((ROOT / freeze_record["path"]).read_text(encoding="utf-8"))
    entries_key = freeze_spec.get("entries_key")
    entries = freeze.get(entries_key) if isinstance(entries_key, str) else None
    if not isinstance(entries, list) or not entries:
        raise HistoricalEvidenceError(f"{bundle_id}: freeze has no {entries_key!r} entries")

    actual_drifts: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise HistoricalEvidenceError(f"{bundle_id}: invalid freeze entry")
        relative, path = repo_file(entry.get("path"))
        expected = entry.get("sha256")
        if not isinstance(expected, str) or SHA256_RE.fullmatch(expected) is None:
            raise HistoricalEvidenceError(f"{bundle_id}: invalid frozen SHA for {relative}")
        actual = sha256_file(path)
        if actual != expected:
            actual_drifts.append(
                {"path": relative, "frozen_sha256": expected, "current_sha256": actual}
            )

    declared = bundle.get("declared_current_source_drifts")
    if not isinstance(declared, list):
        raise HistoricalEvidenceError(f"{bundle_id}: drift declaration must be a list")
    normalized_declared = sorted(
        (
            {
                "path": str(item.get("path")),
                "frozen_sha256": str(item.get("frozen_sha256")),
                "current_sha256": str(item.get("current_sha256")),
            }
            for item in declared
            if isinstance(item, Mapping)
        ),
        key=lambda item: item["path"],
    )
    normalized_actual = sorted(actual_drifts, key=lambda item: item["path"])
    if normalized_actual != normalized_declared:
        raise HistoricalEvidenceError(
            f"{bundle_id}: current-source drift set differs from the exact declaration"
        )

    roots = bundle.get("evidence_roots")
    if not isinstance(roots, list) or not roots:
        raise HistoricalEvidenceError(f"{bundle_id}: evidence_roots must be non-empty")
    root_records = [verified_record(item) for item in roots]
    nested_count = 0
    for root_record in root_records:
        root_path = ROOT / root_record["path"]
        payload = json.loads(root_path.read_text(encoding="utf-8"))
        for reference in reference_records(payload):
            verified_record(reference, base_dir=root_path.parent)
            nested_count += 1

    return {
        "id": bundle_id,
        "freeze": freeze_record,
        "freeze_entries": len(entries),
        "declared_current_source_drifts": len(actual_drifts),
        "evidence_roots": len(root_records),
        "nested_evidence_records": nested_count,
    }


def verify_historical_evidence() -> dict[str, Any]:
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    if declaration.get("schema_version") != "1.0":
        raise HistoricalEvidenceError("unsupported compatibility declaration schema")
    current = declaration.get("current_evidence")
    bundles = declaration.get("historical_bundles")
    if not isinstance(current, Mapping) or not isinstance(bundles, list) or not bundles:
        raise HistoricalEvidenceError("compatibility declaration is incomplete")
    current_freeze = current.get("freeze")
    if not isinstance(current_freeze, Mapping):
        raise HistoricalEvidenceError("current evidence freeze declaration is missing")
    result = {
        "status": "pass",
        "policy": declaration.get("policy"),
        "current_evidence": verify_current_freeze(current_freeze),
        "historical_bundles": [verify_historical_bundle(bundle) for bundle in bundles],
    }
    return result


def main() -> int:
    print(json.dumps(verify_historical_evidence(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
