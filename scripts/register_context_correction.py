"""Atomically register passing Context Correction V2 evidence for E9 and E14.

This is the only supported completion path for the corrected context
experiments.  It never calls the generic experiment registrar.  A stored pass
audit is required, the entire audit is re-run, and both registry entries are
updated in one atomic payload replacement.  Any admission failure occurs
before that replacement, leaving the registry byte-for-byte unchanged.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.context_correction_runtime import EXPECTED_FREEZE_PATHS  # noqa: E402
from experiments.registry import load_registry, save_registry  # noqa: E402
from scripts.audit_context_correction_v2 import (  # noqa: E402
    AUDIT_TYPE,
    DEFAULT_E14_MANIFEST,
    DEFAULT_E9_MANIFEST,
    DEFAULT_FREEZE,
    DEFAULT_JSON,
    PROTOCOL_ID,
    audit_context_correction_v2,
)


DEFAULT_REGISTRY = ROOT / "experiments" / "registry.json"


class ContextCorrectionRegistrationError(RuntimeError):
    """Raised before the atomic registry write when admission is invalid."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside_root(
    value: str | Path,
    root: Path,
    *,
    label: str,
    require_file: bool = True,
    allow_empty: bool = False,
) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ContextCorrectionRegistrationError(
            f"{label} escapes repository root: {value}"
        ) from exc
    if require_file:
        if not resolved.is_file():
            raise ContextCorrectionRegistrationError(f"{label} is missing: {resolved}")
        if not allow_empty and resolved.stat().st_size <= 0:
            raise ContextCorrectionRegistrationError(f"{label} is empty: {resolved}")
    return resolved


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContextCorrectionRegistrationError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContextCorrectionRegistrationError(f"{label} must be a JSON object")
    return value


def _restore_bytes_atomic(path: Path, content: bytes) -> None:
    """Restore the pre-transaction registry bytes after an unexpected save error."""

    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.restore.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _validate_stored_audit(
    *,
    root: Path,
    audit_path: Path,
    expected_freeze_paths: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    stored = _load_object(audit_path, label="context correction audit")
    if (
        stored.get("audit_type") != AUDIT_TYPE
        or stored.get("protocol_id") != PROTOCOL_ID
        or stored.get("workload_revision") != "r2"
    ):
        raise ContextCorrectionRegistrationError("stored audit is not Context Correction V2")
    if stored.get("status") != "pass" or stored.get("failures") != []:
        raise ContextCorrectionRegistrationError("stored context correction audit is not a clean pass")
    if stored.get("old_v3_policy") != "preserved_invalid_diagnostic_provenance_excluded_from_v2_denominators":
        raise ContextCorrectionRegistrationError("stored audit does not exclude old V3 evidence")
    if Path(str(stored.get("repository_root", ""))).resolve() != root:
        raise ContextCorrectionRegistrationError("stored audit repository root differs")
    integrity = stored.get("integrity_summary") or {}
    if integrity.get("status") != "pass" or int(integrity.get("files_hashed", 0)) < 1:
        raise ContextCorrectionRegistrationError("stored audit has no passing integrity ledger")
    for experiment_id, expected, warmup in (("E9", 120, 0), ("E14", 432, 48)):
        item = (stored.get("experiments") or {}).get(experiment_id) or {}
        if (
            item.get("status") != "pass"
            or item.get("expected_case_runs") != expected
            or item.get("observed_case_runs") != expected
            or item.get("warmup_case_runs") != warmup
            or item.get("warmup_excluded") is not True
        ):
            raise ContextCorrectionRegistrationError(
                f"stored audit {experiment_id} denominator gate is invalid"
            )

    markdown_record = stored.get("markdown_report")
    if not isinstance(markdown_record, Mapping):
        raise ContextCorrectionRegistrationError("stored audit has no Markdown companion record")
    markdown = _inside_root(
        str(markdown_record.get("path", "")), root, label="audit Markdown"
    )
    if (
        markdown_record.get("sha256") != _sha256(markdown)
        or int(markdown_record.get("bytes", -1)) != markdown.stat().st_size
    ):
        raise ContextCorrectionRegistrationError("audit Markdown hash/bytes mismatch")

    inputs = stored.get("inputs") or {}
    freeze_record = inputs.get("freeze") or {}
    freeze = _inside_root(freeze_record.get("path", DEFAULT_FREEZE), root, label="freeze")
    manifests = inputs.get("formal_manifests") or {}
    e9_record = manifests.get("E9") or {}
    e14_record = manifests.get("E14") or {}
    e9_manifest = _inside_root(e9_record.get("path", DEFAULT_E9_MANIFEST), root, label="E9 manifest")
    e14_manifest = _inside_root(e14_record.get("path", DEFAULT_E14_MANIFEST), root, label="E14 manifest")

    fresh = audit_context_correction_v2(
        repository_root=root,
        freeze_path=freeze,
        e9_manifest_path=e9_manifest,
        e14_manifest_path=e14_manifest,
        output_json=None,
        output_markdown=None,
        expected_freeze_paths=expected_freeze_paths,
    )
    if fresh.get("status") != "pass" or fresh.get("failures"):
        raise ContextCorrectionRegistrationError(
            "fresh context correction audit failed: "
            + "; ".join(
                f"{item.get('code')}={item.get('detail')}"
                for item in fresh.get("failures") or []
            )
        )
    if fresh.get("evidence_fingerprint") != stored.get("evidence_fingerprint"):
        raise ContextCorrectionRegistrationError(
            "stored audit fingerprint is stale or does not match fresh evidence"
        )
    # These sections carry the admission semantics.  Requiring exact equality
    # prevents a hand-edited pass report from changing counts or provenance
    # while retaining the same underlying file fingerprint.
    for key in (
        "old_v3_policy",
        "inputs",
        "freeze",
        "prompt_proof",
        "experiments",
        "integrity_summary",
        "integrity_ledger",
        "failures",
    ):
        if stored.get(key) != fresh.get(key):
            raise ContextCorrectionRegistrationError(
                f"stored audit section differs from fresh audit: {key}"
            )
    return stored, fresh, markdown


def _active_evidence(
    *,
    root: Path,
    stored_audit: Mapping[str, Any],
    experiment_id: str,
    audit_path: Path,
    markdown_path: Path,
) -> list[str]:
    item = (stored_audit.get("experiments") or {}).get(experiment_id) or {}
    manifest = item.get("manifest") or {}
    values = [
        str(manifest.get("path", "")),
        *(str(value) for value in item.get("active_artifacts") or []),
        str((stored_audit.get("inputs") or {}).get("freeze", {}).get("path", "")),
        str((stored_audit.get("inputs") or {}).get("prompt_verification", {}).get("path", "")),
        _relative(audit_path, root),
        _relative(markdown_path, root),
    ]
    evidence: list[str] = []
    for index, value in enumerate(values):
        if not value:
            raise ContextCorrectionRegistrationError(
                f"{experiment_id} active evidence contains an empty path"
            )
        path = _inside_root(value, root, label=f"{experiment_id} active_evidence[{index}]", allow_empty=True)
        relative = _relative(path, root)
        if relative not in evidence:
            evidence.append(relative)
    return evidence


def _superseded_snapshot(item: Mapping[str, Any], *, at: str) -> dict[str, Any]:
    return {
        "captured_at": at,
        "status": "invalid_diagnostic_provenance",
        "previous_status": item.get("status"),
        "reason": item.get("error")
        or "Old V3 context evidence is invalid and excluded from corrected denominators.",
        "required_artifacts": list(item.get("required_artifacts") or []),
        "evidence": list(item.get("evidence") or []),
        "primary_manifest": copy.deepcopy(item.get("primary_manifest")),
        "primary_manifest_record": copy.deepcopy(
            item.get("primary_manifest_record")
        ),
        "excluded_from_active_denominators": True,
        "pooling_prohibited": True,
    }


def _existing_superseded(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = item.get("superseded_evidence")
    if isinstance(value, list):
        return [copy.deepcopy(entry) for entry in value if isinstance(entry, Mapping)]
    if isinstance(value, Mapping):
        return [copy.deepcopy(dict(value))]
    return []


def prepare_registration(
    *,
    registry_path: str | Path,
    repository_root: str | Path,
    audit_path: str | Path,
    expected_freeze_paths: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a fully validated candidate registry without writing it."""

    root = Path(repository_root).resolve()
    registry_file = _inside_root(registry_path, root, label="registry")
    audit_file = _inside_root(audit_path, root, label="context correction audit")
    stored_audit, fresh_audit, markdown = _validate_stored_audit(
        root=root,
        audit_path=audit_file,
        expected_freeze_paths=tuple(expected_freeze_paths or EXPECTED_FREEZE_PATHS),
    )
    registry = load_registry(registry_file)
    candidate = copy.deepcopy(registry)
    entries = {str(item.get("id")): item for item in candidate.get("experiments") or []}
    if set(("E9", "E14")) - set(entries):
        raise ContextCorrectionRegistrationError("registry is missing E9 or E14")
    at = _utc_now()
    audit_record = {
        "path": _relative(audit_file, root),
        "sha256": _sha256(audit_file),
        "bytes": audit_file.stat().st_size,
        "evidence_fingerprint": stored_audit["evidence_fingerprint"],
    }
    primary_paths: dict[str, str] = {}
    primary_records: dict[str, dict[str, Any]] = {}
    active_by_experiment: dict[str, list[str]] = {}
    required_by_experiment: dict[str, list[str]] = {}
    for experiment_id in ("E9", "E14"):
        audited = (stored_audit.get("experiments") or {})[experiment_id]
        manifest_record = audited.get("manifest") or {}
        primary = {
            "path": str(manifest_record.get("path", "")),
            "sha256": str(manifest_record.get("sha256", "")),
            "bytes": int(manifest_record.get("bytes", -1)),
            "protocol_id": PROTOCOL_ID,
            "evidence_tier": "formal_context_correction_v2",
            "workload_revision": "r2",
        }
        manifest_path = _inside_root(primary["path"], root, label=f"{experiment_id} primary manifest")
        if primary["sha256"] != _sha256(manifest_path) or primary["bytes"] != manifest_path.stat().st_size:
            raise ContextCorrectionRegistrationError(
                f"{experiment_id} primary manifest hash/bytes mismatch"
            )
        primary_paths[experiment_id] = primary["path"]
        primary_records[experiment_id] = primary
        active_by_experiment[experiment_id] = _active_evidence(
            root=root,
            stored_audit=stored_audit,
            experiment_id=experiment_id,
            audit_path=audit_file,
            markdown_path=markdown,
        )
        # Final-analysis validation requires every required path other than the
        # manifest itself to appear in that manifest's artifact ledger.  The
        # wider evidence list may additionally retain the freeze and audit.
        required_by_experiment[experiment_id] = list(
            dict.fromkeys(
                [
                    primary_paths[experiment_id],
                    *(str(value) for value in audited.get("active_artifacts") or []),
                ]
            )
        )

    already_registered = all(
        entries[experiment_id].get("status") == "completed"
        and entries[experiment_id].get("primary_manifest")
        == primary_paths[experiment_id]
        and entries[experiment_id].get("primary_manifest_record")
        == primary_records[experiment_id]
        and entries[experiment_id].get("active_evidence")
        == active_by_experiment[experiment_id]
        and entries[experiment_id].get("required_artifacts")
        == required_by_experiment[experiment_id]
        and (entries[experiment_id].get("completion_gate") or {}).get("audit")
        == audit_record
        for experiment_id in ("E9", "E14")
    )

    if not already_registered:
        for experiment_id, expected, warmup in (("E9", 120, 0), ("E14", 432, 48)):
            item = entries[experiment_id]
            superseded = _existing_superseded(item)
            # Capture the pre-correction evidence once.  A rerun of the same
            # registrar must not recursively supersede the corrected bundle.
            if not superseded and not item.get("completion_gate"):
                superseded.append(_superseded_snapshot(item, at=at))
            item.update(
                {
                    "status": "completed",
                    "primary_manifest": primary_paths[experiment_id],
                    "primary_manifest_record": primary_records[experiment_id],
                    "active_evidence": active_by_experiment[experiment_id],
                    "required_artifacts": required_by_experiment[experiment_id],
                    "evidence": active_by_experiment[experiment_id],
                    "completion_gate": {
                        "schema_version": "2.0",
                        "registrar": "scripts/register_context_correction.py",
                        "protocol_id": PROTOCOL_ID,
                        "workload_revision": "r2",
                        "all_or_nothing_pair": ["E9", "E14"],
                        "formal_expected_case_runs": expected,
                        "warmup_case_runs": warmup,
                        "warmup_excluded_from_formal_denominator": experiment_id != "E14"
                        or warmup == 48,
                        "old_v3_excluded": True,
                        "audit": audit_record,
                        "registered_at": at,
                    },
                    "superseded_evidence": superseded,
                    "error": "",
                    "updated_at": at,
                    "completed_at": at,
                }
            )

    summary = {
        "schema_version": "2.0",
        "status": "validated",
        "protocol_id": PROTOCOL_ID,
        "experiments": ["E9", "E14"],
        "audit": audit_record,
        "fresh_audit_pass": fresh_audit.get("status") == "pass",
        "all_or_nothing": True,
        "already_registered": already_registered,
        "active_evidence_counts": {
            key: len(value) for key, value in active_by_experiment.items()
        },
    }
    return summary, candidate


def register_context_correction(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY,
    repository_root: str | Path = ROOT,
    audit_path: str | Path | None = None,
    apply: bool = False,
    expected_freeze_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    registry_file = _inside_root(registry_path, root, label="registry")
    audit_file = Path(audit_path or root / DEFAULT_JSON.relative_to(ROOT))
    before = registry_file.read_bytes()
    try:
        summary, candidate = prepare_registration(
            registry_path=registry_file,
            repository_root=root,
            audit_path=audit_file,
            expected_freeze_paths=expected_freeze_paths,
        )
        if not apply:
            return {**summary, "mode": "dry_run", "registry_written": False}
        if summary["already_registered"]:
            return {
                **summary,
                "mode": "apply",
                "registry_written": False,
                "no_op": True,
                "registry_sha256": hashlib.sha256(before).hexdigest(),
            }
    except Exception:
        if registry_file.is_file() and registry_file.read_bytes() != before:
            _restore_bytes_atomic(registry_file, before)
        raise

    # Exactly one atomic payload save updates E9 and E14 together.  Should an
    # unexpected filesystem error occur after replacement, restore the exact
    # pre-transaction bytes before propagating it.
    try:
        save_registry(candidate, registry_file)
    except Exception:
        if not registry_file.is_file() or registry_file.read_bytes() != before:
            _restore_bytes_atomic(registry_file, before)
        raise
    try:
        registry_sha256 = _sha256(registry_file)
    except Exception:
        _restore_bytes_atomic(registry_file, before)
        raise
    return {
        **summary,
        "mode": "apply",
        "registry_written": True,
        "no_op": False,
        "registry_sha256": registry_sha256,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--audit", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = register_context_correction(
        registry_path=args.registry,
        repository_root=ROOT,
        audit_path=args.audit,
        apply=args.apply,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
