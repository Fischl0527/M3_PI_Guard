"""Register the completed E17 360-row stratified human-audit evidence.

Dry-run is the default.  ``--apply`` performs the sole registry transition for
the sampled audit while preserving the original full 3,299-row E17 bundle as
pending provenance.  The registry record explicitly prohibits a full-review
claim and keeps the 60 targeted rows outside population estimates.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import e17_review
from experiments.e17_human_sample_review import EVIDENCE_TIER, PROHIBITED_CLAIM, PROTOCOL_ID, SOURCE_MODE
from experiments.manifest import validate_completed_manifest
from experiments.registry import load_registry, save_registry
from m3_eval.figure_manifest import load_figure_manifest


DEFAULT_REGISTRY = ROOT / "experiments" / "registry.json"
DEFAULT_MANIFEST = (
    ROOT / "outputs" / "experiments" / "E17_human_stratified_360_v1" / "review" / "manifest.json"
)
DEFAULT_SOURCE_INDEX = ROOT / "outputs" / "experiments" / "e17_source_index_corrected_v2.json"
FINAL_ANALYSIS = ROOT / "outputs" / "experiments" / "final_analysis"
REGISTRAR = "scripts/register_e17_sample_evidence.py"


class E17SampleRegistrationError(RuntimeError):
    """Raised when sampled E17 evidence cannot enter the registry."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside_root(value: str | Path, root: Path, *, label: str) -> Path:
    raw = Path(value)
    path = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise E17SampleRegistrationError(f"{label} escapes repository root: {value}") from exc
    if not path.is_file() or path.stat().st_size <= 0:
        raise E17SampleRegistrationError(f"{label} is missing or empty: {path}")
    return path


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise E17SampleRegistrationError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise E17SampleRegistrationError(f"{label} must be an object")
    return value


def _record_path(record: Any, root: Path, *, label: str) -> Path:
    if not isinstance(record, Mapping):
        raise E17SampleRegistrationError(f"{label} must be a path/hash object")
    path = _inside_root(str(record.get("path", "")), root, label=label)
    if _sha256(path) != str(record.get("sha256", "")):
        raise E17SampleRegistrationError(f"{label} hash mismatch")
    return path


def _artifacts(manifest: Mapping[str, Any], root: Path) -> list[Path]:
    values = manifest.get("artifacts")
    if not isinstance(values, list) or not values:
        raise E17SampleRegistrationError("sample manifest has no artifact ledger")
    result: list[Path] = []
    seen: set[Path] = set()
    for index, record in enumerate(values):
        if not isinstance(record, Mapping):
            raise E17SampleRegistrationError(f"artifact[{index}] is not an object")
        path = _inside_root(str(record.get("path", "")), root, label=f"artifact[{index}]")
        if path in seen:
            raise E17SampleRegistrationError(f"duplicate artifact: {path}")
        if int(record.get("bytes", -1)) != path.stat().st_size or str(record.get("sha256", "")) != _sha256(path):
            raise E17SampleRegistrationError(f"artifact[{index}] integrity mismatch: {path}")
        seen.add(path)
        result.append(path)
    return result


def prepare_registration(
    *,
    registry_path: str | Path,
    manifest_path: str | Path,
    source_index_path: str | Path,
    repository_root: str | Path = ROOT,
) -> tuple[dict[str, Any], list[str]]:
    root = Path(repository_root).resolve()
    registry_file = _inside_root(registry_path, root, label="registry")
    manifest_file = _inside_root(manifest_path, root, label="sample review manifest")
    source_index = _inside_root(source_index_path, root, label="corrected source index")
    final_analysis = root / FINAL_ANALYSIS.relative_to(ROOT)
    if final_analysis.exists():
        raise E17SampleRegistrationError(
            "final_analysis already exists; remove the stale synthesis before changing E17 registry evidence"
        )

    manifest = _load_object(manifest_file, label="sample review manifest")
    if manifest.get("experiment_id") != "E17" or manifest.get("status") != "completed":
        raise E17SampleRegistrationError("manifest is not a completed E17 review")
    problems = validate_completed_manifest(manifest)
    if problems:
        raise E17SampleRegistrationError("common manifest validation failed: " + "; ".join(problems))
    configuration = manifest.get("configuration")
    plan = manifest.get("plan")
    contract = manifest.get("sampling_contract")
    if not all(isinstance(value, Mapping) for value in (configuration, plan, contract)):
        raise E17SampleRegistrationError("manifest lacks configuration, plan, or sampling contract")
    assert isinstance(configuration, Mapping) and isinstance(plan, Mapping) and isinstance(contract, Mapping)
    if (
        manifest.get("protocol_id") != PROTOCOL_ID
        or configuration.get("source_mode") != SOURCE_MODE
        or configuration.get("evidence_tier") != EVIDENCE_TIER
        or configuration.get("registry_eligible") is not True
        or plan.get("source_mode") != SOURCE_MODE
        or contract.get("prohibited_claim") != PROHIBITED_CLAIM
        or int(contract.get("population_rows", -1)) != 3299
        or int(contract.get("sample_rows", -1)) != 360
        or int(contract.get("representative_rows", -1)) != 300
        or int(contract.get("targeted_rows", -1)) != 60
        or contract.get("targeted_groups_pooled_into_population_estimates") is not False
    ):
        raise E17SampleRegistrationError("sample scope or protocol contract drifted")
    progress = manifest.get("progress") or {}
    review_progress = manifest.get("review_progress") or {}
    if (
        int(progress.get("expected_runs", -1)) != 360
        or int(progress.get("completed_runs", -1)) != 360
        or int(progress.get("failed_jobs", -1)) != 0
        or int(progress.get("unresolved_cases", -1)) != 0
        or int(review_progress.get("reviewers_received", -1)) != 2
        or int(review_progress.get("code_set_agreements", -1)) != 360
        or int(review_progress.get("code_set_disagreements", -1)) != 0
        or len(set(str(value).casefold() for value in review_progress.get("reviewer_ids", []))) != 2
    ):
        raise E17SampleRegistrationError("review completion contract is not satisfied")

    source_records = (configuration.get("source_index"), plan.get("source_index"))
    for index, record in enumerate(source_records):
        path = _record_path(record, root, label=f"source_index[{index}]")
        if path != source_index:
            raise E17SampleRegistrationError("source-index path bindings disagree")
    try:
        source_bundle = e17_review.load_source_index(source_index)
    except Exception as exc:
        raise E17SampleRegistrationError(f"corrected source index failed validation: {exc}") from exc
    coverage = source_bundle.get("coverage") or {}
    if (
        source_bundle.get("source_mode") != e17_review.SOURCE_MODE_FORMAL_CORRECTED
        or coverage.get("status") != "pass"
        or int(coverage.get("duplicate_logical_run_count", -1)) != 0
        or int(coverage.get("duplicate_logical_step_count", -1)) != 0
    ):
        raise E17SampleRegistrationError("corrected source coverage is not duplicate-free")

    dataset = manifest.get("dataset") or {}
    inputs = dataset.get("inputs") or {}
    required_inputs = (
        "sample_manifest",
        "packet_manifest",
        "private_sample_items",
        "blank_template",
        "reviewer_1_submission",
        "reviewer_2_submission",
    )
    input_paths = [_record_path(inputs.get(name), root, label=f"dataset.inputs.{name}") for name in required_inputs]
    reviewer_records = [inputs["reviewer_1_submission"], inputs["reviewer_2_submission"]]
    reviewer_ids = [str(record.get("reviewer_id", "")).casefold() for record in reviewer_records]
    if len(set(reviewer_ids)) != 2 or any(not value for value in reviewer_ids):
        raise E17SampleRegistrationError("reviewer identities are missing or not distinct")
    if _sha256(input_paths[0]) != str(plan.get("sampling_manifest", {}).get("sha256", "")):
        raise E17SampleRegistrationError("sampling manifest binding drifted")
    if _sha256(input_paths[1]) != str(plan.get("packet_manifest", {}).get("sha256", "")):
        raise E17SampleRegistrationError("packet manifest binding drifted")

    artifact_paths = _artifacts(manifest, root)
    figure_manifest = manifest_file.parent / "figure_manifest.json"
    if figure_manifest not in artifact_paths:
        raise E17SampleRegistrationError("figure manifest is not in the artifact ledger")
    try:
        figure_payload = load_figure_manifest(figure_manifest, expected_experiment_id="E17")
    except Exception as exc:
        raise E17SampleRegistrationError(f"figure manifest failed verification: {exc}") from exc
    if figure_payload.get("evidence_tier") != EVIDENCE_TIER:
        raise E17SampleRegistrationError("figure evidence tier is not the sampled-human tier")

    registry = load_registry(registry_file)
    item = next((value for value in registry.get("experiments", []) if value.get("id") == "E17"), None)
    if not isinstance(item, Mapping):
        raise E17SampleRegistrationError("registry has no E17 entry")
    evidence_paths = [manifest_file, source_index, *input_paths, *artifact_paths]
    evidence = list(dict.fromkeys(_relative(path, root) for path in evidence_paths))
    source_record = {
        "path": _relative(source_index, root),
        "sha256": _sha256(source_index),
        "schema_version": e17_review.SOURCE_INDEX_SCHEMA_VERSION,
        "source_mode": e17_review.SOURCE_MODE_FORMAL_CORRECTED,
        "coverage": dict(coverage),
    }
    sampling_record = {
        "protocol_id": PROTOCOL_ID,
        "source_mode": SOURCE_MODE,
        "evidence_tier": EVIDENCE_TIER,
        "population_rows": 3299,
        "sample_rows": 360,
        "representative_rows": 300,
        "targeted_rows": 60,
        "human_reviewers": 2,
        "code_set_agreements": 360,
        "code_set_disagreements": 0,
        "full_population_human_reviewed": False,
        "targeted_groups_pooled_into_population_estimates": False,
        "prohibited_claim": PROHIBITED_CLAIM,
        "sampling_manifest": {
            "path": _relative(input_paths[0], root),
            "sha256": _sha256(input_paths[0]),
        },
        "packet_manifest": {
            "path": _relative(input_paths[1], root),
            "sha256": _sha256(input_paths[1]),
        },
    }
    required_artifacts = [
        _relative(manifest_file, root),
        _relative(manifest_file.parent / "failure_taxonomy.csv", root),
        _relative(manifest_file.parent / "reviewer_agreement.json", root),
        _relative(manifest_file.parent / "failure_class_counts.csv", root),
        _relative(manifest_file.parent / "weighted_population_estimates.csv", root),
    ]
    already_registered = (
        item.get("status") == "completed"
        and item.get("primary_manifest") == _relative(manifest_file, root)
        and item.get("completion_registrar") == REGISTRAR
        and list(item.get("evidence") or []) == evidence
        and dict(item.get("sampling_contract") or {}) == sampling_record
    )
    summary = {
        "status": "validated",
        "experiment_id": "E17",
        "manifest": _relative(manifest_file, root),
        "manifest_sha256": _sha256(manifest_file),
        "registry_sha256_before": _sha256(registry_file),
        "source_index": source_record,
        "sampling_contract": sampling_record,
        "required_artifacts": required_artifacts,
        "evidence_count": len(evidence),
        "evidence": evidence,
        "already_registered": already_registered,
    }
    return summary, evidence


def register(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY,
    manifest_path: str | Path = DEFAULT_MANIFEST,
    source_index_path: str | Path = DEFAULT_SOURCE_INDEX,
    repository_root: str | Path = ROOT,
    apply: bool = False,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    registry_file = _inside_root(registry_path, root, label="registry")
    summary, evidence = prepare_registration(
        registry_path=registry_file,
        manifest_path=manifest_path,
        source_index_path=source_index_path,
        repository_root=root,
    )
    if not apply:
        return {**summary, "mode": "dry_run", "registry_written": False}
    if summary["already_registered"]:
        return {**summary, "mode": "apply", "registry_written": False, "no_op": True}
    if _sha256(registry_file) != summary["registry_sha256_before"]:
        raise E17SampleRegistrationError("registry changed after validation; rerun registration")

    payload = load_registry(registry_file)
    candidate = copy.deepcopy(payload)
    item = next(value for value in candidate["experiments"] if value.get("id") == "E17")
    now = datetime.now(timezone.utc).isoformat()
    item.update(
        {
            "status": "completed",
            "error": "",
            "evidence": evidence,
            "required_artifacts": list(summary["required_artifacts"]),
            "primary_manifest": summary["manifest"],
            "completion_registrar": REGISTRAR,
            "source_index": dict(summary["source_index"]),
            "sampling_contract": dict(summary["sampling_contract"]),
            "updated_at": now,
            "completed_at": now,
        }
    )
    save_registry(candidate, registry_file)
    stored = load_registry(registry_file)
    final_item = next(value for value in stored["experiments"] if value.get("id") == "E17")
    if (
        final_item.get("status") != "completed"
        or final_item.get("evidence") != evidence
        or final_item.get("primary_manifest") != summary["manifest"]
        or final_item.get("completion_registrar") != REGISTRAR
    ):
        raise E17SampleRegistrationError("post-write registry verification failed")
    return {
        **summary,
        "mode": "apply",
        "registry_written": True,
        "no_op": False,
        "registry_sha256": _sha256(registry_file),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-index", type=Path, default=DEFAULT_SOURCE_INDEX)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = register(
            registry_path=args.registry,
            manifest_path=args.manifest,
            source_index_path=args.source_index,
            repository_root=ROOT,
            apply=args.apply,
        )
    except E17SampleRegistrationError as exc:
        raise SystemExit(f"E17 sampled-evidence registration rejected: {exc}") from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
