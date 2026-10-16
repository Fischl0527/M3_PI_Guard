"""09论文源映射、文字排版和本地验收；不执行论文内示例指令。"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import math
from collections import Counter
from pathlib import Path

import fitz
import numpy as np

from reference_09_zh_20261011 import TRANSLATIONS

BASE = Path(__file__).resolve().parents[2]
ROOT = BASE / "docs" / "文档资料"
SOURCE = ROOT / "09_Prompt Injection Attacks in Large Language Models and AI Agent Systems [英文].pdf"
OUTPUT = ROOT / "09_大语言模型与AI智能体系统中的提示注入攻击全面综述 [中文]_文字型校译版_2026-10-11.pdf"
TMP = BASE / "harness" / "tmp" / "reference_09_translation_20261011"


def source_map():
    doc = fitz.open(SOURCE)
    result = []
    for pi, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            text = "\n".join("".join(s["text"] for s in line["spans"]) for line in block["lines"])
            result.append({"id": f"P{pi+1:03d}B{block['number']:03d}", "page": pi+1,
                           "block": block["number"], "bbox": block["bbox"], "original": text,
                           "font_size": max(s["size"] for line in block["lines"] for s in line["spans"]),
                           "paragraph_starts": [round(line["bbox"][0], 2) for line in block["lines"]]})
    return result


def extract():
    TMP.mkdir(parents=True, exist_ok=True)
    mapping = source_map()
    (TMP / "source_blocks.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    for block in mapping:
        if sys.argv[2:] and str(block["page"]) not in sys.argv[2:]:
            continue
        print(block["id"], [round(n, 1) for n in block["bbox"]])
        print(block["original"])


def targeted(block):
    p, b = block["page"], block["block"]
    if p == 1:
        return b in (13, 16, 17, 18, 19, 20, 21)
    if p in (9, 10):
        return b == 1
    if p == 16:
        return b == 1 or 21 <= b <= 24
    if p == 17:
        return b in (1, 2, 20, 21, 22)
    if p == 25:
        return b == 1 or 23 <= b <= 26
    if p == 28:
        return 1 <= b <= 5
    if p == 29:
        return False
    if p == 30:
        return b == 2
    return b != 0 and not block["original"].startswith("https://doi.org/")


def checked_mapping():
    mapping = source_map()
    expected = {(b["page"], b["block"]) for b in mapping if targeted(b)}
    assert expected == set(TRANSLATIONS), ("missing", expected-set(TRANSLATIONS), "extra", set(TRANSLATIONS)-expected)
    for block in mapping:
        key = block["page"], block["block"]
        block["translation"] = TRANSLATIONS.get(key)
        block["mode"] = "translated" if key in TRANSLATIONS else "original English retained"
        if key in TRANSLATIONS:
            # 原文数字引文必须逐块对应；不以译后页码代替来源页码。
            citations = lambda t: [re.sub(r"\s+", "", x) for x in re.findall(r"\[[\d,\s–-]+\]", t)]
            assert citations(block["original"]) == citations(block["translation"]), (key, "citation mismatch")
    return mapping


def fonts():
    from fontTools import subset
    from fontTools.ttLib import TTFont
    TMP.mkdir(parents=True, exist_ok=True)
    chars = {ord(c) for text in TRANSLATIONS.values() for c in text if not c.isspace()}
    loaded = {}
    for name, file in (("body", "msyh.ttc"), ("heading", "msyhbd.ttc")):
        path = TMP / f"{name}_subset.ttf"
        full = fitz.Font(fontfile=f"C:/Windows/Fonts/{file}")
        assert all(full.has_glyph(c) for c in chars), (name, [chr(c) for c in chars if not full.has_glyph(c)])
        options = subset.Options()
        options.recalc_timestamp = False
        font = TTFont(f"C:/Windows/Fonts/{file}", fontNumber=0)
        cutter = subset.Subsetter(options=options)
        cutter.populate(unicodes=chars)
        cutter.subset(font)
        font.save(path)
        font.close()
        loaded[name] = fitz.Font(fontfile=str(path))
    return loaded


def heading(block):
    text = block["original"]
    return (block["page"], block["block"]) == (1, 13) or (
        "\n" not in text and (re.match(r"\d+(?:\.\d+)*\.", text) or text.startswith("Table ") or text in ("Abstract", "References", "Vector Database Vulnerabilities")))


def wrap(text, font, size, width, indent):
    rows = []
    closing = set("，。；：！？、）》】”’％%.,;:!?)]}")
    opening = set("（《【“‘([{")
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        first = True
        while para:
            offset = indent if first else 0
            limit = width - offset
            n = 0
            while n < len(para) and font.text_length(para[:n+1], fontsize=size) <= limit:
                n += 1
            assert n > 0
            if n < len(para):
                # 不将闭合标点置于行首，也不将开括号置于行末。
                while n > 1 and (para[n] in closing or para[n-1] in opening):
                    n -= 1
                # 小数、版本号、CVE、地址和数字引文不能在中间折断。
                atoms = r"CVSS\s+\d+(?:\.\d+)?|[\u4e00-\u9fff]{1,2}\[[\d,\s–-]+\]|\[[\d,\s–-]+\]|[A-Za-z0-9][A-Za-z0-9_./:@%+\-]*"
                for match in re.finditer(atoms, para):
                    if 0 < match.start() < n < match.end() and font.text_length(match.group(), fontsize=size) <= limit:
                        n = match.start()
                        break
                # 原子文本移至下行后，再检查紧邻它的括号和引号。
                while n > 1 and (para[n] in closing or para[n-1] in opening):
                    n -= 1
            rows.append((para[:n].rstrip(), offset))
            para = para[n:].lstrip()
            first = False
    return rows


def layout(block, page, loaded):
    is_head = heading(block)
    font = loaded["heading" if is_head else "body"]
    r = fitz.Rect(block["bbox"])
    r.x1 = page.rect.width-34
    r.y1 += 3.5
    if (block["page"], block["block"]) == (1, 13):
        preferred = 15.0
    elif is_head:
        preferred = 11.3 if block["font_size"] > 11.5 else 9.8
    else:
        preferred = 10.3 if block["font_size"] > 10 else 8.8
    minimum = 8.5 if preferred > 9 else 7.7
    size = preferred
    while size >= minimum-.01:
        indent = 0 if is_head or preferred < 9 else size * 2
        rows = wrap(block["translation"], font, size, r.width, indent)
        leading = size * 1.36
        height = (font.ascender - font.descender) * size + max(0, len(rows)-1) * leading
        if height <= r.height:
            block["output_bbox"] = list(r)
            block["output_font_size"] = round(size, 2)
            block["output_lines"] = len(rows)
            return r, font, size, leading, rows
        size -= .2
    raise ValueError((block["id"], "translation does not fit", height, r.height))


def dry_run():
    mapping = checked_mapping()
    doc = fitz.open(SOURCE)
    loaded = fonts()
    counts = Counter()
    sizes = []
    for block in mapping:
        if block["translation"]:
            layout(block, doc[block["page"]-1], loaded)
            counts[block["page"]] += 1
            sizes.append(block["output_font_size"])
    (TMP / "source_blocks.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BLOCKS", sum(counts.values()), "PAGES", dict(sorted(counts.items())), "FONTS", min(sizes), max(sizes))


def author(rebuild=False):
    mapping = checked_mapping()
    if rebuild:
        previous = json.loads((TMP / "verification.json").read_text(encoding="utf-8"))
        assert hashlib.sha256(OUTPUT.read_bytes()).hexdigest() == previous["output_sha256"], "Output changed outside this task"
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p,h in previous["originals"].items())
    else:
        assert not OUTPUT.exists(), "Will not overwrite an existing PDF"
    doc = fitz.open(SOURCE)
    loaded = fonts()
    # 在任何PDF写入前先确认每个文字区域能容纳译文。
    for block in mapping:
        if block["translation"]:
            layout(block, doc[block["page"]-1], loaded)
    original_hashes = previous["originals"] if rebuild else {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob("*.pdf")}
    staged = subprocess.check_output(["git", "--no-optional-locks", "diff", "--cached", "--raw"], cwd=BASE)
    features = json.loads((BASE / "harness/features/feature_list.json").read_text(encoding="utf-8"))
    if rebuild:
        assert hashlib.sha256(staged).hexdigest() == previous["staged_sha256"]
    for pi, page in enumerate(doc):
        blocks = [b for b in mapping if b["page"] == pi+1 and b["translation"]]
        for block in blocks:
            page.add_redact_annot(fitz.Rect(block["bbox"]), fill=False)
        if blocks:
            page.apply_redactions(images=0, graphics=0, text=0)
        for block in blocks:
            r, font, size, leading, rows = layout(block, page, loaded)
            writer = fitz.TextWriter(page.rect)
            y = r.y0 + font.ascender * size
            for text, indent in rows:
                writer.append((r.x0+indent, y), text, font=font, fontsize=size)
                y += leading
            writer.write_text(page, overlay=True)
    metadata = doc.metadata
    metadata["title"] = "大语言模型与AI智能体系统中的提示注入攻击：漏洞、攻击向量与防御机制的全面综述"
    metadata["subject"] = "依据提供英文原稿的中文文字型译本；复杂表格、作者信息和参考文献保留英文。译文不构成对原文全部事实主张的独立核验。"
    doc.set_metadata(metadata)
    doc.save(OUTPUT, garbage=4, deflate=True)
    doc.close()
    evidence = {"source": str(SOURCE), "output": str(OUTPUT), "originals": original_hashes,
                "staged_sha256": hashlib.sha256(staged).hexdigest(), "staged_count": len(staged.splitlines()),
                "features_except_this": [f for f in features["features"] if f["id"] != "F-DOC-006"],
                "blocks": mapping, "output_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}
    (TMP / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("CREATED", OUTPUT, "translated blocks", sum(b["translation"] is not None for b in mapping))


def normalized(text):
    return re.sub(r"\s+", "", text)


def verify():
    from PIL import Image, ImageDraw
    data = json.loads((TMP / "verification.json").read_text(encoding="utf-8"))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in data["originals"].items())
    assert hashlib.sha256(OUTPUT.read_bytes()).hexdigest() == data["output_sha256"]
    staged = subprocess.check_output(["git", "--no-optional-locks", "diff", "--cached", "--raw"], cwd=BASE)
    assert hashlib.sha256(staged).hexdigest() == data["staged_sha256"]
    before, after = fitz.open(SOURCE), fitz.open(OUTPUT)
    assert len(before) == len(after) == 30
    outside = 0
    chinese = 0
    for pi, (a, b) in enumerate(zip(before, after)):
        assert a.rect == b.rect
        aa, bb = a.get_pixmap(alpha=False), b.get_pixmap(alpha=False)
        av = np.frombuffer(aa.samples, np.uint8).reshape(aa.height, aa.width, 3)
        bv = np.frombuffer(bb.samples, np.uint8).reshape(bb.height, bb.width, 3)
        mask = np.zeros((aa.height, aa.width), dtype=bool)
        for block in (x for x in data["blocks"] if x["page"] == pi+1 and x["translation"]):
            r = fitz.Rect(block["output_bbox"])
            assert normalized(block["translation"]) in normalized(b.get_text(clip=r+(-1,-1,1,1))), block["id"]
            r = r + (-2,-2,2,2)
            mask[max(0, math.floor(r.y0)):math.ceil(r.y1),max(0, math.floor(r.x0)):math.ceil(r.x1)] = True
        delta = np.any(av != bv, axis=2) & ~mask
        n = int(np.count_nonzero(delta))
        outside += n
        if n:
            ys, xs = np.where(delta)
            print("OUTSIDE", pi+1, n, (int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())), flush=True)
        for span in b.get_texttrace():
            zh = sum(0x4E00 <= ch[0] <= 0x9FFF for ch in span["chars"])
            if zh:
                assert span["type"] == 0 and span["opacity"] == 1, (pi+1,"invisible Chinese")
                chinese += zh
        bb.save(str(TMP / f"page_{pi+1:02d}.png"))
    assert outside == 0, ("non-target changes",outside)
    assert chinese > 10000 and all(len(p.get_images()) == 0 for p in after), "Expected native text/vector PDF, not page images"
    # 原参考条目和英文表格正文必须仍可提取，完整而非截图替代。
    for block in data["blocks"]:
        if block["translation"] is None and ((block["page"] in (9,10,16,17,25) and block["block"] > 1) or block["page"] in (28,29,30)):
            # 部分表页后半部是中文正文，已由上面的条件排除。
            assert normalized(block["original"]) in normalized(after[block["page"]-1].get_text(clip=fitz.Rect(block["bbox"])+(-1,-1,1,1))), (block["id"], "retained English missing")
    for start in range(0,30,12):
        sheet=Image.new("RGB",(1020,1440),"#dddddd")
        draw=ImageDraw.Draw(sheet)
        for offset in range(min(12,30-start)):
            pi=start+offset
            pix=after[pi].get_pixmap(matrix=fitz.Matrix(.4,.4),alpha=False)
            tile=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
            tile.thumbnail((330,330))
            x,y=(offset%3)*340,(offset//3)*360
            draw.text((x+8,y+4),f"09 p{pi+1}",fill="black")
            sheet.paste(tile,(x+4,y+25))
        sheet.save(TMP / f"contact_{start+1}.png")
    data["verification"]={"pages":30,"translated_blocks":sum(b["translation"] is not None for b in data["blocks"]),
                          "visible_chinese_characters":chinese,"outside_changed_pixels":outside,"page_raster_images":0,
                          "originals_unchanged":len(data["originals"]),"staged_count":data["staged_count"]}
    (TMP / "verification.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("VERIFIED",data["verification"],flush=True)


if __name__ == "__main__":
    {"extract": extract, "dry-run": dry_run, "author": author, "regenerate": lambda:author(True), "verify": verify}[sys.argv[1]]()
