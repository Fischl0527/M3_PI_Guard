"""OOXML, figure inventory and source-preservation checks for the requested report."""

from __future__ import annotations
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from docx import Document
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/research-introduction-20261014"
DOC = ROOT / "docs/M3_PI_Guard_研究介绍_2026-10-14.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def blacken():
    """Make every stored text color explicit black, including unused built-in styles."""
    with zipfile.ZipFile(DOC) as z:
        members = [(i, z.read(i.filename)) for i in z.infolist()]
    result = []
    changed = 0
    for info, blob in members:
        if info.filename.startswith("word/") and info.filename.endswith(".xml"):
            node = ET.fromstring(blob)
            dirty = False
            for c in node.iter(W + "color"):
                if c.get(W + "val") != "000000" or any(
                    W + k in c.attrib for k in ["themeColor", "themeTint", "themeShade"]
                ):
                    c.set(W + "val", "000000")
                    for k in ["themeColor", "themeTint", "themeShade"]:
                        c.attrib.pop(W + k, None)
                    dirty = True
                    changed += 1
            if dirty:
                # Preserve existing namespace prefixes used by Word compatibility attributes.
                for _, binding in ET.iterparse(
                    __import__("io").BytesIO(blob), events=["start-ns"]
                ):
                    prefix, uri = binding
                    if prefix not in ["xml"] and not prefix.startswith("ns"):
                        try:
                            ET.register_namespace(prefix, uri)
                        except ValueError:
                            pass
                blob = ET.tostring(node, encoding="utf-8", xml_declaration=True)
        result.append((info, blob))
    if changed:
        tmp = DOC.with_suffix(".normalized.docx")
        with zipfile.ZipFile(tmp, "w") as z:
            for info, blob in result:
                z.writestr(info, blob)
        tmp.replace(DOC)
    return changed


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify():
    patched = blacken()
    data = json.loads((WORK / "research_data.json").read_text(encoding="utf-8"))
    snapshot = json.loads((WORK / "source_snapshot.json").read_text(encoding="utf-8"))
    problems = []
    for rel, digest in snapshot["sources"].items():
        if sha(ROOT / rel) != digest:
            problems.append(f"Changed scientific source: {rel}")
    staged = subprocess.run(
        ["git", "diff", "--cached", "--binary"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    staged_same = hashlib.sha256(staged).hexdigest() == snapshot["staged_diff_sha256"]
    for h in data["history"]:
        for rel, digest in h["original_hashes"].items():
            original = ROOT / rel
            target = (
                ROOT / "docs/picture/历史实验图表" / Path(rel).relative_to("outputs")
            )
            if sha(original) != digest or sha(target) != digest:
                problems.append(f"History copy/source mismatch: {rel}")
    doc = Document(DOC)
    all_text = (
        "\n".join(p.text for p in doc.paragraphs)
        + "\n"
        + "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    )
    for needle in [
        "v1",
        "v2",
        "v3",
        "v4",
        "2165",
        "5/32",
        "0/32",
        "68/97",
        "38/97",
        "29/97",
        "457",
        "358",
    ]:
        # 457 appears in the figure caption, not every prose version.
        if needle not in all_text:
            problems.append(f"Missing expected content: {needle}")
    colors = []
    fonts = []
    media = []
    embedded = 0
    with zipfile.ZipFile(DOC) as z:
        for n in z.namelist():
            if n.startswith("word/") and n.endswith(".xml"):
                node = ET.fromstring(z.read(n))
                colors.extend(c.get(W + "val") for c in node.iter(W + "color"))
                fonts.extend(
                    c.get(W + "eastAsia")
                    for c in node.iter(W + "rFonts")
                    if c.get(W + "eastAsia")
                )
                embedded += sum(
                    1
                    for c in node.iter(
                        "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
                    )
                    if c.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                    )
                )
            if n.startswith("word/media/") and not n.endswith("/"):
                media.append(n)
                with Image.open(__import__("io").BytesIO(z.read(n))) as im:
                    im.verify()
    if set(colors) != {"000000"}:
        problems.append(f"Text colors not pure black: {set(colors)}")
    expected = 15 + data["history_unique_count"]
    if embedded != expected:
        problems.append(f"Embedded image count {embedded}, expected {expected}")
    new_png = list((ROOT / "docs/picture").glob("M3_*.png"))
    if len(new_png) != 15:
        problems.append("Expected 15 new PNGs")
    for f in new_png:
        with Image.open(f) as im:
            if im.width < 2000:
                problems.append(f"Low resolution new plot: {f.name}")
    report = {
        "docx": DOC.relative_to(ROOT).as_posix(),
        "bytes": DOC.stat().st_size,
        "text_colors": sorted(set(colors)),
        "color_elements": len(colors),
        "normalized_color_elements": patched,
        "east_asian_fonts": sorted(set(fonts)),
        "embedded_images": embedded,
        "media_files": len(media),
        "new_figures": len(new_png),
        "history_groups": len(data["history"]),
        "history_original_files": sum(len(x["files"]) for x in data["history"]),
        "history_unique_images": data["history_unique_count"],
        "protected_sources_unchanged": len(snapshot["sources"]),
        "staged_diff_unchanged": staged_same,
        "paragraphs": len(doc.paragraphs),
        "tables": len(doc.tables),
        "problems": problems,
    }
    (WORK / "document_structural_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    verify()
