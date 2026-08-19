"""Import and replay the public Day-1 blind-custodian registration bundle.

The importer reads exactly three developer-safe files.  It never searches for
or opens the custodian's private identity attestation, private key, candidate
rows, or labels.  The resulting project-side receipt stores only identity
digests and content-free cryptographic/integrity evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.independent_blind_closeout_v2 import (
    _registration_verifier_receipt_checks,
    verify_custodian_registration,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INBOX = (
    PROJECT_ROOT
    / "external/independent_blind/day1_registration_inbox"
)
ACCEPTANCE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/independent_blind_day1_registration_acceptance_v1.json"
)
ACCEPTED_AT = "2026-08-02T23:20:00+08:00"
SCHEMA_VERSION = "m3-paper-v2-independent-blind-day1-acceptance-1.0"

EXPECTED_FILENAMES = frozenset(
    {
        "custodian_public_key.pem",
        "custodian_registration_v2.json",
        "custodian_registration_verifier_receipt_v2.json",
    }
)


class IndependentBlindDay1AcceptanceV1Error(ValueError):
    """Raised when the developer-safe Day-1 handoff fails closed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentBlindDay1AcceptanceV1Error(
            f"invalid Day-1 JSON: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise IndependentBlindDay1AcceptanceV1Error(
            f"Day-1 JSON must be an object: {path}"
        )
    return value


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise IndependentBlindDay1AcceptanceV1Error(
            "Day-1 inbox path escapes the project"
        ) from exc


def _paths(inbox: Path) -> dict[str, Path]:
    return {
        "public_key": inbox / "custodian_public_key.pem",
        "registration": inbox / "custodian_registration_v2.json",
        "verifier_receipt": (
            inbox / "custodian_registration_verifier_receipt_v2.json"
        ),
    }


def _validate_inbox(inbox: Path) -> dict[str, Path]:
    if not inbox.is_dir() or inbox.is_symlink():
        raise IndependentBlindDay1AcceptanceV1Error(
            "Day-1 inbox must be a real directory"
        )
    children = list(inbox.iterdir())
    names = {child.name for child in children}
    if names != EXPECTED_FILENAMES:
        raise IndependentBlindDay1AcceptanceV1Error(
            "Day-1 inbox must contain exactly the three public registration files"
        )
    for child in children:
        if child.is_symlink() or not child.is_file():
            raise IndependentBlindDay1AcceptanceV1Error(
                "Day-1 inbox entries must be regular files"
            )
        try:
            child.resolve().relative_to(inbox.resolve())
        except ValueError as exc:
            raise IndependentBlindDay1AcceptanceV1Error(
                "Day-1 file escapes the inbox"
            ) from exc
    return _paths(inbox)


def _file_lock(path: Path) -> dict[str, Any]:
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def build_acceptance(
    *, inbox: Path = DEFAULT_INBOX, accepted_at: str = ACCEPTED_AT
) -> dict[str, Any]:
    paths = _validate_inbox(inbox)
    registration = _read_json(paths["registration"])
    receipt = _read_json(paths["verifier_receipt"])

    verifier_id = str(receipt.get("verifier_id", ""))
    custodian_id = str(receipt.get("custodian_id", ""))
    replayed = verify_custodian_registration(
        registration_path=paths["registration"],
        public_key_path=paths["public_key"],
        verifier_id=verifier_id,
        verified_at=str(receipt.get("verified_at", "")),
    )
    chain_checks = _registration_verifier_receipt_checks(
        registration=registration,
        registration_path=paths["registration"],
        receipt=receipt,
        public_key_path=paths["public_key"],
    )
    checks = {
        "exact_three_file_handoff": True,
        "registration_receipt_exact_replay": replayed == receipt,
        "registration_chain_checks_all_pass": bool(chain_checks)
        and all(chain_checks.values()),
        "recorded_registration_checks_all_pass": bool(receipt.get("checks"))
        and all(value is True for value in receipt["checks"].values()),
        "clock_start_status_verified": receipt.get("status")
        == "custodian_registration_verified_clock_may_start",
        "receipt_verified_true": receipt.get("verified") is True,
        "custodian_and_verifier_distinct": bool(custodian_id)
        and bool(verifier_id)
        and custodian_id != verifier_id,
        "registration_has_zero_labels": registration.get("label_rows_present")
        == 0,
        "execution_remains_unauthorized": registration.get(
            "execution_authorized"
        )
        is False
        and receipt.get("evidence_boundary", {}).get("execution_authorized")
        is False,
        "private_identity_content_not_required": receipt.get(
            "evidence_boundary", {}
        ).get("offline_identity_evidence_content_opened")
        is False,
    }
    if not all(checks.values()):
        failed = sorted(key for key, value in checks.items() if not value)
        raise IndependentBlindDay1AcceptanceV1Error(
            f"Day-1 registration handoff rejected: {failed}"
        )

    source_files = [
        _file_lock(paths[key])
        for key in ("public_key", "registration", "verifier_receipt")
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "developer_side_day1_registration_acceptance",
        "status": "independent_custodian_day1_registration_accepted",
        "accepted_at": accepted_at,
        "source_files": source_files,
        "registration": {
            "registration_manifest_sha256": registration["manifest_sha256"],
            "verifier_receipt_manifest_sha256": receipt["manifest_sha256"],
            "public_key_spki_sha256": receipt["public_key_spki_sha256"],
            "signature_key_id": receipt["signature_key_id"],
            "custodian_id_sha256": hashlib.sha256(
                custodian_id.encode("utf-8")
            ).hexdigest(),
            "verifier_id_sha256": hashlib.sha256(
                verifier_id.encode("utf-8")
            ).hexdigest(),
            "confirmed_at": registration["confirmed_at"],
            "verified_at": receipt["verified_at"],
            "recorded_check_count": len(receipt["checks"]),
        },
        "checks": checks,
        "evidence_boundary": {
            "offline_identity_attestation_content_opened": False,
            "private_key_opened": False,
            "candidate_or_label_files_received": 0,
            "label_rows_read": 0,
            "network_calls_made": 0,
            "provider_calls_made": 0,
            "execution_authorized": False,
            "clock_start_technical_gate_satisfied": True,
            "real_person_identity_remains_offline_attestation": True,
            "blind_dataset_authoring_completed": False,
        },
        "implementation_lock": _file_lock(Path(__file__)),
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_acceptance(
    *, inbox: Path = DEFAULT_INBOX, accepted_at: str = ACCEPTED_AT
) -> dict[str, Any]:
    value = build_acceptance(inbox=inbox, accepted_at=accepted_at)
    ACCEPTANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_acceptance(*, inbox: Path = DEFAULT_INBOX) -> dict[str, Any]:
    observed = _read_json(ACCEPTANCE_PATH)
    expected = build_acceptance(
        inbox=inbox, accepted_at=str(observed.get("accepted_at", ""))
    )
    if observed != expected or observed.get("manifest_sha256") != _manifest_sha(
        observed
    ):
        raise IndependentBlindDay1AcceptanceV1Error(
            "Day-1 acceptance artifact drift"
        )
    return copy.deepcopy(observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-acceptance", action="store_true")
    action.add_argument("--verify-acceptance", action="store_true")
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    args = parser.parse_args()
    value = (
        write_acceptance(inbox=args.inbox)
        if args.write_acceptance
        else verify_acceptance(inbox=args.inbox)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
