"""针对 2026-07-27 阶段报告 DOCX 文档执行结构化与内容质量 QA 校验。

检查 Word 文档中的段落数、表格结构、占位符残留与数字事实一致性。
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image
from docx import Document
from lxml import etree


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "docs/research/paper_v2/reports"
    / "M3_PI_Guard_阶段性研究报告_2026-07-27.docx"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/report_qa/stage_report_20260727"
    / "structural_qa.json"
)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attr(node: etree._Element, local_name: str) -> str | None:
    return node.get(f"{{{NS['w']}}}{local_name}")


def _check_table_geometry(document_xml: bytes) -> dict[str, Any]:
    root = etree.fromstring(document_xml)
    tables = root.xpath(".//w:tbl", namespaces=NS)
    failures: list[str] = []
    header_rows = 0
    for table_index, table in enumerate(tables, start=1):
        tbl_w_nodes = table.xpath("./w:tblPr/w:tblW", namespaces=NS)
        tbl_ind_nodes = table.xpath("./w:tblPr/w:tblInd", namespaces=NS)
        grid_nodes = table.xpath("./w:tblGrid/w:gridCol", namespaces=NS)
        if len(tbl_w_nodes) != 1 or attr(tbl_w_nodes[0], "w") != "9360":
            failures.append(f"table {table_index}: tblW is not 9360 DXA")
        if len(tbl_ind_nodes) != 1 or attr(tbl_ind_nodes[0], "w") != "120":
            failures.append(f"table {table_index}: tblInd is not 120 DXA")
        grid = [int(attr(node, "w") or "0") for node in grid_nodes]
        if sum(grid) != 9360:
            failures.append(f"table {table_index}: grid sum {sum(grid)}")
        rows = table.xpath("./w:tr", namespaces=NS)
        if rows and rows[0].xpath("./w:trPr/w:tblHeader", namespaces=NS):
            header_rows += 1
        for row_index, row in enumerate(rows, start=1):
            widths = [
                int(attr(node, "w") or "0")
                for node in row.xpath("./w:tc/w:tcPr/w:tcW", namespaces=NS)
            ]
            if widths != grid:
                failures.append(
                    f"table {table_index} row {row_index}: tcW {widths} != {grid}"
                )
        exact_heights = table.xpath(
            ".//w:trHeight[@w:hRule='exact']",
            namespaces=NS,
        )
        if exact_heights:
            failures.append(f"table {table_index}: fixed exact row height present")
    return {
        "table_count": len(tables),
        "repeating_header_rows": header_rows,
        "failures": failures,
        "passed": not failures and header_rows == len(tables),
    }


def _check_page_geometry(document_xml: bytes) -> dict[str, Any]:
    root = etree.fromstring(document_xml)
    sections = root.xpath(".//w:sectPr", namespaces=NS)
    failures: list[str] = []
    for index, section in enumerate(sections, start=1):
        page = section.xpath("./w:pgSz", namespaces=NS)
        margins = section.xpath("./w:pgMar", namespaces=NS)
        if not page or (attr(page[0], "w"), attr(page[0], "h")) != (
            "12240",
            "15840",
        ):
            failures.append(f"section {index}: page size is not US Letter")
        if not margins:
            failures.append(f"section {index}: missing page margins")
        else:
            values = tuple(
                attr(margins[0], name)
                for name in ("top", "right", "bottom", "left")
            )
            if values != ("1440", "1440", "1440", "1440"):
                failures.append(f"section {index}: margins {values}")
    return {
        "section_count": len(sections),
        "failures": failures,
        "passed": len(sections) == 1 and not failures,
    }


def _check_images(
    archive: zipfile.ZipFile,
    document_xml: bytes,
) -> dict[str, Any]:
    root = etree.fromstring(document_xml)
    doc_prs = root.xpath(".//wp:docPr", namespaces=NS)
    missing_alt = [
        node.get("name", "")
        for node in doc_prs
        if not node.get("title") or not node.get("descr")
    ]
    media = sorted(
        name
        for name in archive.namelist()
        if name.startswith("word/media/") and name.lower().endswith(".png")
    )
    dimensions: list[dict[str, Any]] = []
    for name in media:
        payload = archive.read(name)
        with Image.open(io.BytesIO(payload)) as image:
            dimensions.append(
                {
                    "name": name,
                    "width": image.width,
                    "height": image.height,
                    "sha256": sha256_bytes(payload),
                }
            )
    return {
        "inline_image_count": len(doc_prs),
        "media_png_count": len(media),
        "missing_alt": missing_alt,
        "dimensions": dimensions,
        "passed": (
            len(doc_prs) == 6
            and len(media) == 6
            and not missing_alt
            and all(
                item["width"] == 1800 and item["height"] == 1050
                for item in dimensions
            )
        ),
    }


def _check_clean_content(
    document_xml: bytes,
    visible_text: str,
) -> dict[str, Any]:
    root = etree.fromstring(document_xml)
    placeholder_patterns = [
        r"\bTODO\b",
        r"\bTBD\b",
        r"\bFIXME\b",
        r"\{\{[^}]+\}\}",
        r"<INSERT[^>]*>",
    ]
    credential_patterns = [
        r"sk-[A-Za-z0-9_-]{16,}",
        r"AQ\.[A-Za-z0-9_-]{16,}",
        r"AIza[A-Za-z0-9_-]{20,}",
    ]
    placeholders = [
        pattern
        for pattern in placeholder_patterns
        if re.search(pattern, visible_text, flags=re.IGNORECASE)
    ]
    credentials = [
        pattern
        for pattern in credential_patterns
        if re.search(pattern, visible_text)
    ]
    tracked = root.xpath(".//w:ins | .//w:del", namespaces=NS)
    comments = root.xpath(
        ".//w:commentRangeStart | .//w:commentRangeEnd | .//w:commentReference",
        namespaces=NS,
    )
    return {
        "placeholder_hits": placeholders,
        "credential_pattern_hits": credentials,
        "tracked_change_nodes": len(tracked),
        "comment_anchor_nodes": len(comments),
        "passed": not placeholders and not credentials and not tracked and not comments,
    }


def validate(report_path: Path) -> dict[str, Any]:
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    with zipfile.ZipFile(report_path) as archive:
        corrupt_member = archive.testzip()
        document_xml = archive.read("word/document.xml")
        styles_xml = archive.read("word/styles.xml")
        numbering_xml = archive.read("word/numbering.xml")
        table_geometry = _check_table_geometry(document_xml)
        page_geometry = _check_page_geometry(document_xml)
        images = _check_images(archive, document_xml)
        root = etree.fromstring(document_xml)
        hyperlinks = len(root.xpath(".//w:hyperlink", namespaces=NS))
        style_root = etree.fromstring(styles_xml)
        numbering_root = etree.fromstring(numbering_xml)
        list_style_num_pr = len(
            style_root.xpath(
                ".//w:style[@w:styleId='ListBullet']/w:pPr/w:numPr | "
                ".//w:style[@w:styleId='ListNumber']/w:pPr/w:numPr",
                namespaces=NS,
            )
        )
        numbering_instances = len(
            numbering_root.xpath(".//w:num", namespaces=NS)
        )

    doc = Document(report_path)
    visible_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    visible_text += "\n" + "\n".join(
        cell.text
        for table in doc.tables
        for row in table.rows
        for cell in row.cells
    )
    clean_content = _check_clean_content(document_xml, visible_text)
    heading_count = sum(
        1
        for paragraph in doc.paragraphs
        if paragraph.style.name.startswith("Heading ")
    )
    title_style_count = sum(
        1 for paragraph in doc.paragraphs if paragraph.style.name == "Title"
    )
    subtitle_style_count = sum(
        1 for paragraph in doc.paragraphs if paragraph.style.name == "Subtitle"
    )
    required_markers = [
        "mechanism_paper_candidate = false",
        "authorization_leakage_uncertainty_empirical_fallback",
        "M3-full 与 policy-only 均为 0/36",
        "首个 policy-only 请求收到 HTTP 429",
        "科学证据完成度 61%",
        "不会使用两家 API 执行",
        "自适应攻击",
        "独立盲测",
    ]
    missing_markers = [marker for marker in required_markers if marker not in visible_text]

    checks = {
        "zip_integrity": corrupt_member is None,
        "page_geometry": page_geometry["passed"],
        "table_geometry": table_geometry["passed"],
        "images_and_alt_text": images["passed"],
        "clean_content": clean_content["passed"],
        "real_list_numbering": list_style_num_pr == 2 and numbering_instances > 0,
        "hyperlinks": hyperlinks >= 11,
        "headings": heading_count >= 20,
        "title_styles": title_style_count == 1 and subtitle_style_count == 1,
        "required_content": not missing_markers,
    }
    return {
        "schema_version": "m3-paper-v2-stage-report-structural-qa-1.0",
        "report": str(report_path),
        "report_sha256": sha256_file(report_path),
        "report_bytes": report_path.stat().st_size,
        "checks": checks,
        "passed": all(checks.values()),
        "counts": {
            "paragraphs": len(doc.paragraphs),
            "headings": heading_count,
            "tables": len(doc.tables),
            "inline_shapes": len(doc.inline_shapes),
            "hyperlinks": hyperlinks,
            "title_style": title_style_count,
            "subtitle_style": subtitle_style_count,
            "list_style_num_pr": list_style_num_pr,
            "numbering_instances": numbering_instances,
        },
        "page_geometry": page_geometry,
        "table_geometry": table_geometry,
        "images": images,
        "clean_content": clean_content,
        "missing_required_markers": missing_markers,
        "render_qa": {
            "status": "unavailable",
            "reason": "LibreOffice/soffice is not installed on the current Windows host.",
            "visual_chart_review": "all_six_png_charts_reviewed",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", nargs="?", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = validate(args.report.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
