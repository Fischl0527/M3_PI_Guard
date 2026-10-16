"""Inspect every rendered report page and create paginated visual review sheets."""

from pathlib import Path
import json
import re
import fitz
from PIL import Image, ImageOps, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/research-introduction-20261014"
RENDER = WORK / "rendered-release"
pdf = next(RENDER.glob("*.pdf"))
doc = fitz.open(pdf)
pages = []
outside = []
nonblack = []
sparse = []
for i, page in enumerate(doc):
    spans = [
        s
        for b in page.get_text("dict")["blocks"]
        if "lines" in b
        for line in b["lines"]
        for s in line["spans"]
    ]
    for s in spans:
        if s["text"].strip() and s["color"] != 0:
            nonblack.append((i + 1, s["text"], s["color"]))
        x0, y0, x1, y1 = s["bbox"]
        if s["text"].strip() and (
            x0 < 25
            or y0 < 12
            or x1 > page.rect.width - 25
            or y1 > page.rect.height - 10
        ):
            outside.append((i + 1, s["text"], list(s["bbox"])))
    text = page.get_text()
    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
        and x.strip() != "M3 PI Guard 研究介绍"
        and not re.fullmatch(r"第\s*\d+\s*页\s*共\s*\d+\s*页", x.strip())
    ]
    images = page.get_image_info()
    chars = len("".join(lines))
    if chars < 50 and not images:
        sparse.append(i + 1)
    pages.append(
        {
            "page": i + 1,
            "head": " / ".join(lines[:2]),
            "chars": chars,
            "images": len(images),
            "fonts": sorted({s["font"] for s in spans}),
        }
    )
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
for start in range(0, len(pages), 4):
    sheet = Image.new("RGB", (1440, 2100), "#E8E8E8")
    draw = ImageDraw.Draw(sheet)
    for j in range(4):
        num = start + j + 1
        if num > len(pages):
            break
        p = RENDER / f"page-{num}.png"
        with Image.open(p) as im:
            tile = ImageOps.contain(im.convert("RGB"), (700, 1010))
            x = (j % 2) * 720 + (720 - tile.width) // 2
            y = (j // 2) * 1050 + 32
            sheet.paste(tile, (x, y))
            draw.text(
                ((j % 2) * 720 + 14, (j // 2) * 1050 + 5),
                f"第 {num} 页",
                font=font,
                fill="black",
            )
    sheet.save(WORK / f"document_pages_{start // 4 + 1:02d}.png")
report = {
    "pdf": pdf.relative_to(ROOT).as_posix(),
    "pages": len(doc),
    "page_pngs": len(list(RENDER.glob("page-*.png"))),
    "a4_upright": all(
        abs(p.rect.width - 595.28) < 1 and abs(p.rect.height - 841.89) < 1 for p in doc
    ),
    "outside_text": outside,
    "nonblack_text": nonblack,
    "sparse_no_image_pages": sparse,
    "page_details": pages,
}
(WORK / "document_render_check.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {k: v for k, v in report.items() if k != "page_details"}, ensure_ascii=False
    )
)
print(
    "\n".join(
        f"{p['page']:02d}: {p['chars']}字 / {p['images']}图 / {p['head']}"
        for p in pages
    )
)
