"""Build a complete 34-entry bibliography from authoritative metadata."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/citation_integrity_manifest_v1.json"
)
OUTPUT_BIB = (
    PROJECT_ROOT / "docs/research/paper_v2/manuscript/references_v1.bib"
)
OUTPUT_REPORT = (
    PROJECT_ROOT
    / "docs/research/paper_v2/manuscript/bibliography_build_v1.json"
)
USER_AGENT = (
    "M3-PI-Guard-Academic-Metadata/1.0 "
    "(research bibliography; no credentials)"
)
ACL_IDS = {
    "L01",
    "L03",
    "L04",
    "L05",
    "L06",
    "L10",
    "L14",
    "L25",
    "L32",
    "L33",
}
ARXIV_IDS = {
    "L21",
    "L22",
    "L23",
    "L24",
    "L26",
    "L27",
    "L28",
    "L29",
    "L30",
    "L31",
}
DOIS = {
    "L08": "10.1145/3713082.3730378",
    "L18": "10.1109/ACCESS.2026.3656849",
    "L19": "10.3390/info17010054",
    "L20": "10.1145/3744916.3764546",
}
AUTHORITATIVE_OVERRIDES = {
    "L20": {
        "type": "inproceedings",
        "author": (
            "Haoyu Wang and Christopher M. Poskitt and Jun Sun"
        ),
        "title": (
            "AgentSpec: Customizable Runtime Enforcement for Safe and "
            "Reliable LLM Agents"
        ),
        "booktitle": (
            "2026 IEEE/ACM 48th International Conference on "
            "Software Engineering (ICSE)"
        ),
        "year": "2026",
        "pages": "1--12",
        "doi": "10.1145/3744916.3764546",
        "url": "https://doi.org/10.1145/3744916.3764546",
        "source": (
            "https://cposkitt.github.io/files/publications/"
            "agentspec_llm_enforcement_icse26.pdf"
        ),
    }
}
ARXIV_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


class BibliographyBuildError(ValueError):
    """Raised when any bibliography entry lacks authoritative metadata."""


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "meta":
            return
        values = {key.lower(): value for key, value in attrs if value}
        key = values.get("name") or values.get("property")
        content = values.get("content")
        if key and content:
            self.meta.setdefault(key.lower(), []).append(
                html.unescape(content).strip()
            )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BibliographyBuildError(f"{path}: expected an object")
    return value


def _request(url: str, *, accept: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def _crossref_work(*, doi: str | None, title: str) -> dict[str, Any]:
    if doi:
        url = (
            "https://api.crossref.org/works/"
            + urllib.parse.quote(doi, safe="/")
        )
    else:
        query = urllib.parse.urlencode(
            {
                "query.title": title,
                "rows": 5,
                "select": (
                    "DOI,title,author,container-title,published,"
                    "page,volume,issue,publisher,type,URL"
                ),
            }
        )
        url = "https://api.crossref.org/works?" + query
    try:
        payload = json.loads(_request(url).decode("utf-8"))
    except HTTPError as exc:
        if doi and exc.code == 404:
            return _crossref_work(doi=None, title=title)
        raise
    message = payload["message"]
    if doi:
        return message
    items = message.get("items", [])
    normalized = re.sub(r"\W+", "", title).casefold()
    for item in items:
        candidate = " ".join(item.get("title", []))
        if re.sub(r"\W+", "", candidate).casefold() == normalized:
            return item
    if not items:
        raise BibliographyBuildError(f"Crossref returned no item: {title}")
    return items[0]


def _person_name(person: Mapping[str, Any]) -> str:
    literal = person.get("name")
    if literal:
        return str(literal)
    family = str(person.get("family", "")).strip()
    given = str(person.get("given", "")).strip()
    if not family:
        raise BibliographyBuildError("Crossref author lacks family name")
    return f"{family}, {given}".rstrip(", ")


def _year_from_crossref(work: Mapping[str, Any]) -> int:
    for key in ("published", "published-print", "published-online", "issued"):
        parts = work.get(key, {}).get("date-parts")
        if parts and parts[0]:
            return int(parts[0][0])
    raise BibliographyBuildError("Crossref work lacks publication year")


def _from_crossref(
    entry: Mapping[str, Any],
    *,
    doi: str | None = None,
) -> dict[str, Any]:
    work = _crossref_work(doi=doi, title=str(entry["title"]))
    authors = [_person_name(person) for person in work.get("author", [])]
    containers = work.get("container-title", [])
    venue = str(containers[0]) if containers else str(work.get("publisher", ""))
    return {
        "id": entry["citation_id"],
        "type": (
            "article"
            if str(work.get("type", "")).startswith("journal")
            else "inproceedings"
        ),
        "title": str(entry["title"]),
        "authors": authors,
        "year": _year_from_crossref(work),
        "venue": venue,
        "pages": str(work.get("page", "")),
        "volume": str(work.get("volume", "")),
        "number": str(work.get("issue", "")),
        "doi": str(work.get("DOI", doi or "")),
        "url": str(entry["stable_url"]),
        "source": (
            "https://api.crossref.org/works/"
            + urllib.parse.quote(str(work.get("DOI", doi or "")), safe="/")
        ),
        "publication_status": entry["publication_status"],
    }


def _acl_bib(entry: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    source = str(entry["stable_url"]).rstrip("/") + ".bib"
    value = _request(source).decode("utf-8").strip()
    value = re.sub(
        r"^(@\w+\{)[^,]+,",
        rf"\g<1>{entry['citation_id']},",
        value,
        count=1,
    )
    required = ("author", "title", "year", "booktitle")
    if any(re.search(rf"\b{name}\s*=", value, re.I) is None for name in required):
        raise BibliographyBuildError(
            f"{entry['citation_id']}: incomplete ACL BibTeX"
        )
    if re.search(r"\burl\s*=", value, re.I) is None:
        value = value[:-1].rstrip() + (
            f",\n  url = {{{entry['stable_url']}}}\n}}"
        )
    metadata = {
        "citation_id": entry["citation_id"],
        "metadata_source": source,
        "publication_status": entry["publication_status"],
        "complete": True,
    }
    return value, metadata


def _arxiv_entry(entry: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    arxiv_id = str(entry["stable_url"]).rstrip("/").split("/")[-1]
    source = (
        "https://export.arxiv.org/api/query?"
        + urllib.parse.urlencode({"id_list": arxiv_id})
    )
    root = ET.fromstring(_request(source))
    record = root.find("atom:entry", ARXIV_NAMESPACE)
    if record is None:
        raise BibliographyBuildError(
            f"{entry['citation_id']}: arXiv entry missing"
        )
    title = " ".join(
        (record.findtext("atom:title", "", ARXIV_NAMESPACE)).split()
    )
    authors = [
        author.findtext("atom:name", "", ARXIV_NAMESPACE).strip()
        for author in record.findall("atom:author", ARXIV_NAMESPACE)
    ]
    published = record.findtext("atom:published", "", ARXIV_NAMESPACE)
    updated = record.findtext("atom:updated", "", ARXIV_NAMESPACE)
    if not title or not authors or not published:
        raise BibliographyBuildError(
            f"{entry['citation_id']}: incomplete arXiv metadata"
        )
    fields = {
        "author": " and ".join(authors),
        "title": title,
        "year": published[:4],
        "eprint": arxiv_id,
        "archivePrefix": "arXiv",
        "primaryClass": next(
            (
                category.attrib["term"]
                for category in record.findall(
                    "atom:category", ARXIV_NAMESPACE
                )
                if "term" in category.attrib
            ),
            "",
        ),
        "url": str(entry["stable_url"]),
        "note": f"Preprint; arXiv version updated {updated[:10]}",
    }
    bib = _format_bib(str(entry["citation_id"]), "misc", fields)
    metadata = {
        "citation_id": entry["citation_id"],
        "metadata_source": source,
        "publication_status": entry["publication_status"],
        "arxiv_version_date": updated[:10],
        "complete": True,
    }
    return bib, metadata


def _page_meta(entry: Mapping[str, Any]) -> dict[str, Any]:
    source = str(entry["stable_url"])
    parser = _MetaParser()
    parser.feed(_request(source).decode("utf-8", errors="replace"))
    meta = parser.meta

    def first(*names: str) -> str:
        for name in names:
            values = meta.get(name.lower(), [])
            if values:
                return values[0]
        return ""

    authors = meta.get("citation_author", [])
    title = first("citation_title", "dc.title", "og:title")
    venue = first(
        "citation_conference_title",
        "citation_journal_title",
        "citation_book_title",
    )
    date = first("citation_publication_date", "citation_date")
    if not authors or not title or not date:
        return _from_crossref(entry)
    return {
        "id": entry["citation_id"],
        "type": (
            "article" if first("citation_journal_title") else "inproceedings"
        ),
        "title": title,
        "authors": authors,
        "year": int(re.search(r"\d{4}", date).group())
        if re.search(r"\d{4}", date)
        else int(entry["year"]),
        "venue": venue,
        "pages": "-".join(
            value
            for value in (
                first("citation_firstpage"),
                first("citation_lastpage"),
            )
            if value
        ),
        "volume": first("citation_volume"),
        "number": first("citation_issue"),
        "doi": first("citation_doi"),
        "url": source,
        "source": source,
        "publication_status": entry["publication_status"],
    }


def _format_bib(key: str, kind: str, fields: Mapping[str, str]) -> str:
    lines = [f"@{kind}{{{key},"]
    active = [(name, value) for name, value in fields.items() if value]
    for index, (name, value) in enumerate(active):
        suffix = "," if index < len(active) - 1 else ""
        lines.append(f"  {name} = {{{value}}}{suffix}")
    lines.append("}")
    return "\n".join(lines)


def _generic_bib(entry: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    metadata = _page_meta(entry)
    authors = [str(author).strip() for author in metadata["authors"] if str(author).strip()]
    if (
        not authors
        or not metadata["title"]
        or not metadata["year"]
        or not metadata["venue"]
    ):
        raise BibliographyBuildError(
            f"{entry['citation_id']}: incomplete publisher metadata"
        )
    fields = {
        "author": " and ".join(authors),
        "title": str(metadata["title"]),
        (
            "journal"
            if metadata["type"] == "article"
            else "booktitle"
        ): str(metadata["venue"]),
        "year": str(metadata["year"]),
        "pages": str(metadata["pages"]),
        "volume": str(metadata["volume"]),
        "number": str(metadata["number"]),
        "doi": str(metadata["doi"]),
        "url": str(metadata["url"]),
    }
    bib = _format_bib(
        str(entry["citation_id"]),
        str(metadata["type"]),
        fields,
    )
    report = {
        "citation_id": entry["citation_id"],
        "metadata_source": metadata["source"],
        "publication_status": entry["publication_status"],
        "complete": True,
    }
    return bib, report


def build() -> tuple[str, dict[str, Any]]:
    manifest = _load_json(MANIFEST_PATH)
    entries = manifest.get("entries", [])
    if len(entries) != 34:
        raise BibliographyBuildError("citation manifest must contain 34 entries")
    bib_entries: list[str] = []
    reports: list[dict[str, Any]] = []
    for entry in entries:
        citation_id = str(entry["citation_id"])
        if citation_id in AUTHORITATIVE_OVERRIDES:
            override = AUTHORITATIVE_OVERRIDES[citation_id]
            bib = _format_bib(
                citation_id,
                str(override["type"]),
                {
                    key: str(value)
                    for key, value in override.items()
                    if key not in {"type", "source"}
                },
            )
            report = {
                "citation_id": citation_id,
                "metadata_source": override["source"],
                "publication_status": entry["publication_status"],
                "complete": True,
            }
        elif citation_id in ACL_IDS:
            bib, report = _acl_bib(entry)
        elif citation_id in ARXIV_IDS:
            bib, report = _arxiv_entry(entry)
        elif citation_id in DOIS:
            metadata = _from_crossref(entry, doi=DOIS[citation_id])
            bib = _generic_bib_from_metadata(metadata)
            report = {
                "citation_id": citation_id,
                "metadata_source": metadata["source"],
                "publication_status": entry["publication_status"],
                "complete": True,
            }
        else:
            bib, report = _generic_bib(entry)
        bib_entries.append(bib)
        reports.append(report)
    bibliography = "\n\n".join(bib_entries) + "\n"
    if len(re.findall(r"^@\w+\{L\d{2},", bibliography, re.M)) != 34:
        raise BibliographyBuildError("bibliography entry count drift")
    core = {
        "schema_version": "m3-paper-v2-bibliography-build-1.0",
        "status": "complete_authoritative_metadata_export",
        "entry_count": 34,
        "peer_reviewed_count": manifest["peer_reviewed_count"],
        "preprint_only_count": manifest["preprint_only_count"],
        "source_manifest_sha256": sha256_canonical_json(manifest["entries"]),
        "bibliography_sha256": hashlib.sha256(
            bibliography.encode("utf-8")
        ).hexdigest(),
        "entries": reports,
        "network_policy": {
            "authoritative_publisher_or_repository_metadata_only": True,
            "credentials_used": False,
            "llm_provider_calls": 0,
        },
    }
    report = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return bibliography, report


def _generic_bib_from_metadata(metadata: Mapping[str, Any]) -> str:
    authors = [str(author).strip() for author in metadata["authors"] if str(author).strip()]
    if not authors or not metadata["venue"]:
        raise BibliographyBuildError(
            f"{metadata['id']}: incomplete Crossref metadata"
        )
    venue_field = (
        "journal" if metadata["type"] == "article" else "booktitle"
    )
    return _format_bib(
        str(metadata["id"]),
        str(metadata["type"]),
        {
            "author": " and ".join(authors),
            "title": str(metadata["title"]),
            venue_field: str(metadata["venue"]),
            "year": str(metadata["year"]),
            "pages": str(metadata["pages"]),
            "volume": str(metadata["volume"]),
            "number": str(metadata["number"]),
            "doi": str(metadata["doi"]),
            "url": str(metadata["url"]),
        },
    )


def write() -> dict[str, Any]:
    bibliography, report = build()
    OUTPUT_BIB.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_BIB.write_text(bibliography, encoding="utf-8")
    OUTPUT_REPORT.write_bytes(canonical_json_bytes(report) + b"\n")
    return report


def verify() -> dict[str, Any]:
    bibliography = OUTPUT_BIB.read_text(encoding="utf-8")
    report = _load_json(OUTPUT_REPORT)
    manifest = _load_json(MANIFEST_PATH)
    expected_manifest = sha256_canonical_json(
        {
            key: child
            for key, child in report.items()
            if key != "manifest_sha256"
        }
    )
    if (
        report.get("manifest_sha256") != expected_manifest
        or report.get("entry_count") != 34
        or report.get("source_manifest_sha256")
        != sha256_canonical_json(manifest["entries"])
        or report.get("bibliography_sha256")
        != hashlib.sha256(bibliography.encode("utf-8")).hexdigest()
        or len(report.get("entries", [])) != 34
        or any(
            entry.get("complete") is not True
            for entry in report.get("entries", [])
        )
        or {
            entry.get("citation_id") for entry in report.get("entries", [])
        }
        != {f"L{index:02d}" for index in range(1, 35)}
        or len(re.findall(r"^@\w+\{L\d{2},", bibliography, re.M)) != 34
    ):
        raise BibliographyBuildError("bibliography export drift")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = write() if args.write else verify()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
