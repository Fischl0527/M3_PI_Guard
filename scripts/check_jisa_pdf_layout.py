"""渲染并检查论文 PDF 排版质量（仅执行静态页面与版式 QA，绝不运行实验代码）。

借助 PyMuPDF (fitz) 自动检查页面尺寸、页码居中基线、文本越界及字体完整性。
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "LaTeX通用模板"
OUTPUT = ROOT / "outputs/document_qa/correctness_paper_update_v1"
DOCUMENTS = {
    "review": TEMPLATE / "数模通用模板.pdf",
    "official": TEMPLATE / "M3_PI_Guard_JISA/M3_PI_Guard_JISA.pdf",
}


def centered_footer(page_rect, box, direction, baseline: float) -> bool:
    """依据渲染基线与水平中心距严格判定页脚页码是否正确居中（容差 4 像素以内）。"""
    return (
        baseline > page_rect.height - 100
        and abs((box.x0 + box.x1) / 2 - page_rect.width / 2) < 4
        and abs(direction[0] - 1) < 0.01
    )


def inspect(name: str, path: Path) -> dict:
    doc = fitz.open(path)
    result = {
        "pages": len(doc), "outline_entries": len(doc.get_toc()),
        "author": doc.metadata.get("author", ""), "errors": [],
        "fonts": [], "key_pages": [], "page_sizes": [],
    }
    fonts, sizes = set(), set()
    thumbnails = []
    for index, page in enumerate(doc):
        number = index + 1
        sizes.add((round(page.rect.width, 2), round(page.rect.height, 2)))
        text = page.get_text()
        if not text.strip() or page.rotation:
            result["errors"].append(f"page {number}: empty or rotated")
        blocks = page.get_text("dict")["blocks"]
        lines = [line for block in blocks if "lines" in block for line in block["lines"]]
        footer = []
        for line in lines:
            for span in line["spans"]:
                fonts.add(span["font"])
                box = fitz.Rect(span["bbox"])
                if not page.rect.contains(box):
                    result["errors"].append(f"page {number}: text outside page")
                if span["text"].strip().isdigit():
                    footer.append((box, line["dir"], span["origin"][1]))
        # cumcm hides the title-page number; elsarticle uses its frontmatter
        # footer instead. Subsequent pages must have centered upright numbers.
        if index != 0:
            centered = [box for box, direction, baseline in footer
                        if centered_footer(page.rect, box, direction, baseline)]
            if not centered:
                result["errors"].append(f"page {number}: centered upright footer missing")
        pix = page.get_pixmap(matrix=fitz.Matrix(0.55, 0.55), alpha=False)
        thumb = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        thumbnails.append(thumb)
        if any(phrase in text for phrase in (
            "Authorization and confirmation diagnostics",
            "Authorization diagnostics and execution permits",
            "E7a execution-permit diagnostic",
            "Native dynamic-environment validation",
            "Corrected development study",
            "Synthetic follow-up",
        )):
            result["key_pages"].append(number)
            page.get_pixmap(matrix=fitz.Matrix(1.65, 1.65), alpha=False).save(
                OUTPUT / f"{name}_page_{number:02d}.png"
            )
    for start in range(0, len(thumbnails), 20):
        subset = thumbnails[start:start + 20]
        tile_width, tile_height = 346, 490
        sheet = Image.new("RGB", (tile_width * 4, tile_height * math.ceil(len(subset) / 4)), "#d9dce1")
        draw = ImageDraw.Draw(sheet)
        for offset, thumb in enumerate(subset):
            x, y = offset % 4 * tile_width, offset // 4 * tile_height
            sheet.paste(thumb, (x + 6, y + 22))
            draw.text((x + 8, y + 4), f"{name} PDF page {start + offset + 1}", fill="black")
        sheet.save(OUTPUT / f"{name}_contact_{start // 20 + 1}.png")
    result["fonts"] = sorted(fonts)
    result["page_sizes"] = sorted(sizes)
    if result["author"]:
        result["errors"].append("author metadata must remain blank")
    if name == "review":
        if any("TimesNewRoman" not in font and not font.startswith("CMSY") for font in fonts):
            result["errors"].append("review has unexpected text font")
        if any(abs(width - 595.28) > 1 or abs(height - 841.89) > 1 for width, height in sizes):
            result["errors"].append("review is not portrait A4")
    log = path.with_suffix(".log").read_text(encoding="utf-8", errors="replace")
    result["layout_log_issues"] = re.findall(r"^.*(?:Overfull|undefined|Missing character|^!).*$", log, re.M)
    result["underfull_count"] = log.count("Underfull")
    if result["layout_log_issues"]:
        result["errors"].append("unresolved LaTeX issue")
    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = {name: inspect(name, path) for name, path in DOCUMENTS.items()}
    (OUTPUT / "layout_check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    if any(item["errors"] for item in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
