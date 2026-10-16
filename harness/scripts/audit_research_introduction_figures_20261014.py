"""Run the figure skill checks and create local visual review sheets."""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/research-introduction-20261014"
QA = WORK / "figure_qa"
SKILL = Path("C:/Users/gaohang/.agents/skills/nature-figure/scripts")
data = json.loads((WORK / "research_data.json").read_text(encoding="utf-8"))
source = subprocess.run(
    [
        sys.executable,
        "-X",
        "utf8",
        str(SKILL / "validate_figure.py"),
        str(ROOT / "harness/scripts/plot_research_introduction_20261014.py"),
        "--json",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
)
(QA / "source_validation.json").write_text(source.stdout, encoding="utf-8")
source_obj = json.loads(source.stdout)
summaries = []
for f in data["new_figures"]:
    p = ROOT / f["pdf"]
    tag = f["id"]
    glyph = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(SKILL / "audit_pdf_text.py"),
            str(p),
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    (QA / f"{tag}.text_audit.json").write_text(glyph.stdout, encoding="utf-8")
    collision = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(SKILL / "audit_figure_collisions.py"),
            str(p),
            "--json-out",
            str(QA / f"{tag}.collision.json"),
            "--overlay-pdf",
            str(QA / f"{tag}.collision.pdf"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    (QA / f"{tag}.collision.log").write_text(
        collision.stdout + "\n" + collision.stderr, encoding="utf-8"
    )
    co = json.loads((QA / f"{tag}.collision.json").read_text(encoding="utf-8"))
    summaries.append(
        {
            "id": tag,
            "glyph_exit": glyph.returncode,
            "collision_exit": collision.returncode,
            "collision_summary": co.get("summary", co.get("status")),
            "keys": list(co),
        }
    )
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
for start in range(0, len(data["new_figures"]), 4):
    sheet = Image.new("RGB", (1600, 1180), "white")
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(data["new_figures"][start : start + 4]):
        x = (i % 2) * 800
        y = (i // 2) * 590
        draw.text((x + 18, y + 6), f"{f['id']}  {f['title']}", font=font, fill="black")
        with Image.open(ROOT / f["png"]) as im:
            tile = ImageOps.contain(im.convert("RGB"), (780, 540))
            sheet.paste(
                tile, (x + (800 - tile.width) // 2, y + 43 + (540 - tile.height) // 2)
            )
    sheet.save(QA / f"new_figures_sheet_{start // 4 + 1}.png")
report = {
    "source_exit": source.returncode,
    "source_summary": source_obj.get("summary"),
    "figures": summaries,
}
(QA / "summary.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False))
