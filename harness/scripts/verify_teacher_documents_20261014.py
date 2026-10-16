"""Verify delivered Word structure, original content, and actual PDF pagination."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from lxml import etree as ET
import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/teacher-brief-20261014"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"
FILES = {
    "brief": ROOT / "docs/M3_PI_Guard_研究介绍_教师交流两页版_2026-10-14.docx",
    "detailed": ROOT / "docs/M3_PI_Guard_研究介绍_2026-10-14.docx",
}


def digest(data):
    return sha256(data).hexdigest()


def inspect_docx(path):
    errors, colors, pages, fills = [], 0, 0, 0
    with ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        for name in z.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            xml = ET.fromstring(z.read(name))
            for e in xml.findall(".//w:color", NS):
                colors += 1
                if e.attrib != {W + "val": "000000"}:
                    errors.append(f"nonblack Word text color in {name}")
            pages += len(xml.findall(".//w:pageBreakBefore", NS))
            pages += sum(e.get(W + "type") == "page" for e in xml.findall(".//w:br", NS))
            fills += sum(len(xml.findall(".//w:" + name, NS))
                         for name in ("shd", "highlight", "background"))
        if pages:
            errors.append("forced page breaks present")
        media = {n: digest(z.read(n)) for n in z.namelist()
                 if n.startswith("word/media/") and not n.endswith("/")}
        return {
            "errors": errors,
            "text_color_elements": colors,
            "forced_page_breaks": pages,
            "fill_elements": fills,
            "media": media,
            "tables": len(root.findall(".//w:tbl", NS)),
            "drawings": len(root.findall(".//w:drawing", NS)),
            "root": root,
        }


def inspect_pdf(kind, render_dir, expected=None):
    pdf = next(render_dir.glob("*.pdf"))
    pages, errors = [], []
    with fitz.open(pdf) as doc:
        if expected is not None and len(doc) != expected:
            errors.append(f"expected {expected} pages, got {len(doc)}")
        for i, page in enumerate(doc):
            spans = [s for b in page.get_text("dict")["blocks"] if "lines" in b
                     for line in b["lines"] for s in line["spans"] if s["text"].strip()]
            if any(s["color"] != 0 for s in spans):
                errors.append(f"page {i + 1}: nonblack text")
            if any(s["bbox"][0] < 18 or s["bbox"][1] < 10
                   or s["bbox"][2] > page.rect.width - 18
                   or s["bbox"][3] > page.rect.height - 10 for s in spans):
                errors.append(f"page {i + 1}: text outside page")
            images = page.get_image_info()
            if not spans and not images:
                errors.append(f"page {i + 1}: blank")
            if abs(page.rect.width - 595.28) > 1 or abs(page.rect.height - 841.89) > 1:
                errors.append(f"page {i + 1}: not A4 portrait")
            pages.append({"page": i + 1, "characters": len(page.get_text()),
                          "images": len(images),
                          "heading": page.get_text()[:100].replace("\n", " / ")})
    pngs = list(render_dir.glob("page-*.png"))
    if len(pngs) != len(pages):
        errors.append("PDF and PNG page counts differ")
    return {"kind": kind, "pdf": str(pdf), "pages": len(pages),
            "errors": errors, "page_details": pages}


def compare_original(old_root, new_root):
    old = list(old_root.findall(".//w:p", NS))
    new = list(new_root.findall(".//w:p", NS))
    position, spacing_changed = 0, 0
    for p in old:
        text = "".join(p.xpath(".//w:t/text()", namespaces=NS))
        while position < len(new) and "".join(new[position].xpath(".//w:t/text()", namespaces=NS)) != text:
            position += 1
        if position == len(new):
            return False, spacing_changed
        for tag in ("spacing", "ind", "contextualSpacing"):
            a, b = p.find("w:pPr/w:" + tag, NS), new[position].find("w:pPr/w:" + tag, NS)
            left, right = (dict(a.attrib) if a is not None else None,
                           dict(b.attrib) if b is not None else None)
            if left != right:
                spacing_changed += 1
        position += 1
    return True, spacing_changed


def review_pairs(render_dir):
    review = WORK / "detailed_review"
    review.mkdir(exist_ok=True)
    paths = sorted(render_dir.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
    for start in range(0, len(paths), 2):
        pair = paths[start:start + 2]
        tiles = [Image.open(p).convert("RGB") for p in pair]
        width = sum(im.width for im in tiles) + 18 * (len(tiles) - 1)
        height = max(im.height for im in tiles) + 30
        canvas = Image.new("RGB", (width, height), "#dddddd")
        draw = ImageDraw.Draw(canvas)
        offset = 0
        for index, im in enumerate(tiles):
            draw.text((offset + 10, 3), f"Page {start + index + 1}", font=font, fill="black")
            canvas.paste(im, (offset, 30))
            offset += im.width + 18
        canvas.save(review / f"pages_{start + 1:02d}_{start + len(pair):02d}.png")


def main():
    report = {"structure": {}, "render": {}, "preservation": {}, "problems": []}
    for kind, path in FILES.items():
        obj = inspect_docx(path)
        if kind == "brief" and (obj["fill_elements"] or obj["tables"] or obj["drawings"]):
            obj["errors"].append("brief contains fill, table or drawing")
        root = obj.pop("root")
        if kind == "brief":
            text = "".join(root.xpath(".//w:t/text()", namespaces=NS))
            if any(x in text for x in ("v2 区分", "v3", "v4", "2,165", "2165", "68/97")):
                obj["errors"].append("brief exceeds historical plus current-v1 scope")
            if not all(x in text for x in (*("E" + str(i) for i in range(1, 18)), "v1")):
                obj["errors"].append("brief lacks requested historical or current-v1 coverage")
        report["structure"][kind] = obj
        report["problems"].extend(obj["errors"])
        if kind == "detailed":
            with ZipFile(WORK / "original_detailed_report.docx") as z:
                old = ET.fromstring(z.read("word/document.xml"))
                same, spaces = compare_original(old, root)
                report["preservation"]["all_original_paragraphs_in_order"] = same
                report["preservation"]["original_spacing_changes"] = spaces
                before = json.loads((WORK / "before.json").read_text(encoding="utf-8"))
                report["preservation"]["embedded_media_unchanged"] = obj["media"] == before["media"]
                report["preservation"]["table_count_unchanged"] = obj["tables"] == len(old.findall(".//w:tbl", NS))
                old_extents = [dict(e.attrib) for e in old.iter()
                               if ET.QName(e).localname == "extent"]
                new_extents = [dict(e.attrib) for e in root.iter()
                               if ET.QName(e).localname == "extent"]
                report["preservation"]["image_dimensions_unchanged"] = old_extents == new_extents
                if not same or spaces or not report["preservation"]["embedded_media_unchanged"]:
                    report["problems"].append("detailed original content or spacing changed")
        qa_name = "teacher_brief.docx" if kind == "brief" else "detailed_report.docx"
        if digest(path.read_bytes()) != digest((WORK / qa_name).read_bytes()):
            report["problems"].append(kind + " differs from rendered copy")
    before = json.loads((WORK / "before.json").read_text(encoding="utf-8"))
    staged = subprocess.run(["git", "diff", "--cached", "--binary"], cwd=ROOT,
                            capture_output=True, check=True).stdout
    report["preservation"]["staged_diff_unchanged"] = digest(staged) == before["staged_diff_sha256"]
    if not report["preservation"]["staged_diff_unchanged"]:
        report["problems"].append("staged diff changed")
    for kind, dirname, pages in (("brief", "rendered-brief-final-v2", 2),
                                 ("detailed", "rendered-detailed-final-v2", None)):
        obj = inspect_pdf(kind, WORK / dirname, pages)
        report["render"][kind] = obj
        report["problems"].extend(obj["errors"])
    review_pairs(WORK / "rendered-detailed-final-v2")
    (WORK / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pages": {k: v["pages"] for k, v in report["render"].items()},
                      "preservation": report["preservation"],
                      "problems": report["problems"]}, ensure_ascii=False))
    if report["problems"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
