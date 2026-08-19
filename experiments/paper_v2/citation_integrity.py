"""Verify the paper-v2 literature matrix and freeze citation-admission metadata.

This is a local structural check, not a substitute for opening every publisher
record immediately before submission.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = PROJECT_ROOT / "docs/research/paper_v2/literature_matrix.md"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/citation_integrity_manifest_v1.json"
)
EXPECTED_IDS = tuple(f"L{index:02d}" for index in range(1, 35))
CRITICAL_FRONTIER_IDS = (
    "L01",
    "L02",
    "L03",
    "L21",
    "L22",
    "L23",
    "L24",
    "L25",
    "L26",
    "L27",
)
PRIMARY_SOURCE_HOSTS = frozenset(
    {
        "aclanthology.org",
        "arxiv.org",
        "doi.org",
        "proceedings.iclr.cc",
        "proceedings.neurips.cc",
        "research.google",
        "www.usenix.org",
    }
)
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https://[^)]+)\)")


class CitationIntegrityError(ValueError):
    """Raised when the literature registry is incomplete or inconsistent."""


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_rows(matrix_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        matrix_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not re.match(r"^\| L\d{2} \|", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            raise CitationIntegrityError(
                f"literature row {line_number} has {len(cells)} cells"
            )
        citation_id, year_status, work, relation, use = (
            cells[0],
            cells[1],
            cells[2],
            cells[4],
            cells[5],
        )
        link = LINK_PATTERN.fullmatch(work)
        if link is None:
            raise CitationIntegrityError(
                f"{citation_id}: work cell must contain one HTTPS Markdown link"
            )
        year_match = re.match(r"^(\d{4})\s*/\s*(.+)$", year_status)
        if year_match is None:
            raise CitationIntegrityError(
                f"{citation_id}: invalid year/status cell"
            )
        url = link.group(2)
        host = urlparse(url).netloc.casefold()
        if host not in PRIMARY_SOURCE_HOSTS:
            raise CitationIntegrityError(
                f"{citation_id}: non-primary citation host {host}"
            )
        status = year_match.group(2)
        if "PR" not in status and "PP" not in status:
            raise CitationIntegrityError(
                f"{citation_id}: publication status lacks PR or PP"
            )
        rows.append(
            {
                "citation_id": citation_id,
                "year": int(year_match.group(1)),
                "publication_status": status,
                "peer_reviewed": "PR" in status,
                "preprint": "PP" in status and "PR" not in status,
                "title": link.group(1),
                "stable_url": url,
                "source_host": host,
                "relation_to_m3": relation,
                "paper_v2_use": use,
                "matrix_line": line_number,
            }
        )
    return rows


def build_citation_manifest(
    matrix_path: Path = DEFAULT_MATRIX,
) -> dict[str, Any]:
    rows = _parse_rows(matrix_path)
    ids = tuple(row["citation_id"] for row in rows)
    if ids != EXPECTED_IDS:
        raise CitationIntegrityError(
            f"citation IDs must be exactly {list(EXPECTED_IDS)}"
        )
    critical = [row for row in rows if row["citation_id"] in CRITICAL_FRONTIER_IDS]
    if len(critical) != len(CRITICAL_FRONTIER_IDS):
        raise CitationIntegrityError("critical frontier citation is missing")
    status_by_id = {
        row["citation_id"]: (
            "peer_reviewed" if row["peer_reviewed"] else "preprint"
        )
        for row in critical
    }
    expected_status = {
        "L01": "peer_reviewed",
        "L02": "peer_reviewed",
        "L03": "peer_reviewed",
        "L21": "preprint",
        "L22": "preprint",
        "L23": "preprint",
        "L24": "preprint",
        "L25": "peer_reviewed",
        "L26": "preprint",
        "L27": "preprint",
    }
    if status_by_id != expected_status:
        raise CitationIntegrityError(
            "frontier publication-status classification drift"
        )
    entries_digest = sha256_canonical_json(rows)
    return {
        "schema_version": "m3-paper-v2-citation-integrity-manifest-1.0",
        "status": "matrix_metadata_refreshed_final_context_audit_pending",
        "generated_at": "2026-07-28T05:00:00+08:00",
        "network_calls_made_by_this_module": 0,
        "authoritative_metadata_audit": {
            "path": (
                "docs/research/paper_v2/manuscript/"
                "full_citation_refresh_v1.md"
            ),
            "checked_count": len(rows),
            "checked_at": "2026-07-28",
            "status": "all_matrix_records_checked",
        },
        "matrix": {
            "path": matrix_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": _sha256_file(matrix_path),
        },
        "citation_count": len(rows),
        "peer_reviewed_count": sum(row["peer_reviewed"] for row in rows),
        "preprint_only_count": sum(row["preprint"] for row in rows),
        "critical_frontier_ids": list(CRITICAL_FRONTIER_IDS),
        "critical_status_by_id": status_by_id,
        "primary_source_hosts": sorted({row["source_host"] for row in rows}),
        "entries_sha256": entries_digest,
        "entries": rows,
        "claim_controls": {
            "preprint_treated_as_peer_reviewed": False,
            "first_only_sota_claims_default": "forbidden",
            "metric_values_require_original_source_semantic_match": True,
            "submission_date_refresh_required": True,
            "doi_and_bibliography_field_completion": "pending_full_manuscript",
            "inline_citation_context_audit": "pending_full_manuscript",
        },
    }


def verify_citation_manifest(
    *,
    matrix_path: Path = DEFAULT_MATRIX,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    expected = build_citation_manifest(matrix_path)
    observed = json.loads(output_path.read_text(encoding="utf-8"))
    if observed != expected:
        raise CitationIntegrityError(
            "frozen citation integrity manifest does not reproduce"
        )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    matrix = resolve(args.matrix)
    output = resolve(args.output)
    if args.verify_only:
        manifest = verify_citation_manifest(
            matrix_path=matrix, output_path=output
        )
    else:
        manifest = build_citation_manifest(matrix)
        output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
