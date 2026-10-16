"""本次三篇参考译文的提取与定点纠错工具；路径和修改表为本次固定输入。"""

from pathlib import Path
from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
import re
import sys
import subprocess

import fitz
import numpy as np

from reference_translation_repairs_20261011 import BLOCK_REPAIRS, BLOCK_LAYOUT, LOCAL_REPAIRS, PANEL_CLEAR, PANEL_REPAIRS, TERMS

ROOT = Path(r"E:\M3_PI_Guard_test\docs\文档资料")
PREVIEWS = Path(r"E:\M3_PI_Guard_test\harness\tmp\translation_repair_20261011")
FONTFILES = {"repair": r"C:\Windows\Fonts\simhei.ttf", "symbols": r"C:\Windows\Fonts\seguisym.ttf", "mathrepair":r"C:\Windows\Fonts\cambria.ttc"}
FONTS = {name: fitz.Font(fontfile=file) for name, file in FONTFILES.items()}
OUTPUT_SUFFIX = "_校正版_2026-10-11.pdf"


def source(number, language="中文"):
    matches = [p for p in ROOT.glob(f"{number}_*.pdf") if f"[{language}]" in p.name and "校正版" not in p.name]
    assert len(matches) == 1, matches
    return matches[0]


def chinese_blocks(page):
    for index, block in enumerate(page.get_text("dict")["blocks"]):
        if "lines" not in block:
            continue
        text = "\n".join("".join(s["text"] for s in line["spans"]) for line in block["lines"])
        if re.search(r"[\u4e00-\u9fff]", text):
            yield index, text, block


def output(number):
    return source(number).with_name(source(number).stem + OUTPUT_SUFFIX)


def chars(block):
    return [dict(c, size=s["size"], color=s["color"], line=li, direction=line["dir"],
                 quad=fitz.recover_char_quad(line["dir"],s,c))
            for li, line in enumerate(block["lines"]) for s in line["spans"] for c in s["chars"]]


def normalized(text):
    return "".join(c for c in text if not c.isspace())


def rect_union(rects):
    result = fitz.Rect(rects[0])
    for r in rects[1:]:
        result |= fitz.Rect(r)
    return result


def pad(r, amount=2):
    return fitz.Rect(r.x0-amount, r.y0-amount, r.x1+amount, r.y1+amount)


@lru_cache(maxsize=None)
def font_for(character):
    for name, font in FONTS.items():
        if font.has_glyph(ord(character)):
            return name
    raise ValueError(f"缺少字体字形: {character!r} U+{ord(character):04X}")


@lru_cache(maxsize=None)
def unit_width(character):
    return FONTS[font_for(character)].text_length(character,fontsize=1)


def text_width(text, size):
    return sum(unit_width(c) for c in text)*size


def write_line(page, origin, text, size, xscale=1, color=(0, 0, 0), rotation=0):
    """分字体写入连续字形；数学字符由支持其字形的符号字体承担。"""
    x, y = origin
    dx,dy = math.cos(math.radians(rotation)), -math.sin(math.radians(rotation))
    runs = []
    for c in text:
        fontname = font_for(c)
        if runs and runs[-1][0] == fontname:
            runs[-1][1] += c
        else:
            runs.append([fontname, c])
    for fontname, value in runs:
        page.insert_text((x, y), value, fontsize=size, fontname=fontname,
                         fontfile=FONTFILES[fontname], color=color,
                         morph=(fitz.Point(x, y), fitz.Matrix(xscale, 1).prerotate(rotation)))
        advance=FONTS[fontname].text_length(value, fontsize=size)*xscale
        x+=advance*dx;y+=advance*dy


def remove_chars(page, items):
    # 小矩形只与待改字符相交，避免去掉相邻字符；不处理图像或矢量线。
    for c in items:
        r = fitz.Rect(c["bbox"])
        if r.is_empty or c["c"].isspace():
            continue
        if c['direction'] != (1.0,0.0):
            q=c['quad'];center=(q.ul+q.ur+q.ll+q.lr)*.25
            page.add_redact_annot(fitz.Rect(center.x-.2,center.y-.2,center.x+.2,center.y+.2),fill=None,cross_out=False)
            continue
        midpoint = (r.y0+r.y1)/2
        inset = min(0.75, r.width/4)
        page.add_redact_annot(fitz.Rect(r.x0+inset, midpoint-.35, r.x1-inset, midpoint+.35),
                             fill=None, cross_out=False)


def write_term(page, items, replacement):
    lines = []
    for c in items:
        if lines and lines[-1][0] == c["line"]:
            lines[-1][1].append(c)
        else:
            lines.append([c["line"], [c]])
    remaining = replacement
    for i, (_, line_chars) in enumerate(lines):
        if i == len(lines)-1:
            part = remaining
        else:
            share = max(1, round(len(replacement)*len(line_chars)/len(items)))
            part, remaining = remaining[:share], remaining[share:]
        r = rect_union([c["bbox"] for c in line_chars])
        size = max(c["size"] for c in line_chars)
        direction=line_chars[0]['direction']
        rotation=math.degrees(math.atan2(-direction[1],direction[0]))
        if direction == (1.0,0.0):
            width=r.width
        else:
            first,last=fitz.Point(line_chars[0]['origin']),fitz.Point(line_chars[-1]['origin'])
            q=line_chars[-1]['quad']
            width=abs(last-first)+abs(q.ur-q.ul)
        scale = min(1, width/max(.01, text_width(part, size)))
        assert scale >= .53, (replacement, scale, r)
        rgb = fitz.sRGB_to_pdf(line_chars[0]["color"])
        origin=fitz.Point(line_chars[0]['origin'])
        if replacement == '摘要':
            advance=(width-text_width(part,size)*scale)/2
            origin+=fitz.Point(direction[0]*advance,direction[1]*advance)
        write_line(page, origin, part, size, scale, rgb,rotation)


def wrapped(text, size, width):
    tokens = re.findall(r"[A-Za-z0-9_]+(?:[.-][A-Za-z0-9_]+)*|[^A-Za-z0-9_]", text)
    result, line = [], ""
    for token in tokens:
        if token == "\n":
            result.append(line)
            line = ""
        elif line and text_width(line+token, size) > width:
            result.append(line.rstrip())
            line = token.lstrip()
        else:
            line += token
    if line:
        result.append(line.rstrip())
    return result


def write_block(page, block, replacement):
    r = fitz.Rect(block["bbox"])
    old_sizes = [s["size"] for l in block["lines"] for s in l["spans"]]
    size = Counter(round(s, 2) for s in old_sizes).most_common(1)[0][0]
    if r.height < size*1.8:
        scale = min(1, r.width/text_width(replacement,size))
        assert scale >= .53, (replacement,scale)
        write_line(page,(r.x0,r.y0+size*.9),replacement,size,scale)
        return size,1
    # 不放大字体，最长的一小段可最多缩小15%，防止挤出原段落范围。
    initial = size
    while size >= initial*.85:
        lines = wrapped(replacement, size, r.width)
        advance = size*1.24
        if size+(len(lines)-1)*advance <= r.height+.6:
            break
        size -= .1
    else:
        raise ValueError(f"段落超出原框: {replacement[:60]} ({len(lines)}行)")
    y = r.y0+size*.9
    for line in lines:
        write_line(page, (r.x0, y), line, size)
        y += advance
    return size, len(lines)


def operations(number, page_number, raw):
    panel_ops = [dict(kind="panel", clip=fitz.Rect(clip), rect=fitz.Rect(*(v*1.5 for v in clip)), reason=reason)
                 for n, p, clip, reason in PANEL_REPAIRS if n == number and p == page_number]
    for op in panel_ops:
        clear=PANEL_CLEAR.get((number,page_number,op['reason']))
        op['clear_rect']=fitz.Rect(*(v*1.5 for v in clear)) if clear else op['rect']
    block_ops, used = [], set()
    for n, p, indices, new, reason in BLOCK_REPAIRS:
        if n != number or p != page_number:
            continue
        indices = (indices,) if isinstance(indices, int) else indices
        bs = [raw["blocks"][i] for i in indices]
        r = rect_union([b["bbox"] for b in bs])
        layout = fitz.Rect(BLOCK_LAYOUT.get((n,p,indices[0]),r))
        items = [c for b in bs for c in chars(b)]
        block_ops.append(dict(kind="block", rect=r|layout, items=items, new=new, reason=reason,
                              block=dict(bbox=tuple(layout), lines=[l for b in bs for l in b["lines"]])))
        used.update(indices)
    term_ops = []
    rules = TERMS["all"]+TERMS[number]+[(old, new) for n,p,old,new in LOCAL_REPAIRS if n==number and p==page_number]
    rules += [("抽象的", "摘要")]
    rules = sorted(rules, key=lambda pair: len(normalized(pair[0])), reverse=True)
    for bi, b in enumerate(raw["blocks"]):
        if bi in used or "lines" not in b:
            continue
        cs = chars(b)
        value = "".join(c["c"] for c in cs)
        if not re.search(r"[\u4e00-\u9fff]", value):
            continue
        positions = [i for i,c in enumerate(cs) if not c["c"].isspace()]
        compact = "".join(cs[i]["c"] for i in positions)
        occupied = set()
        for old,new in rules:
            key = normalized(old)
            if old == "抽象的" and compact != key:
                continue
            for match in re.finditer(re.escape(key), compact):
                indices = list(range(positions[match.start()], positions[match.end()-1]+1))
                if occupied.intersection(indices):
                    continue
                items = [cs[i] for i in indices]
                r = rect_union([c["bbox"] for c in items])
                if any(op["rect"].contains(r) for op in panel_ops):
                    continue
                term_ops.append(dict(kind="term", rect=r, items=items, old=old, new=new,
                                     reason=f"{old} → {new}"))
                occupied.update(indices)
    return panel_ops+block_ops+term_ops


def prepare_fonts():
    # 只子集化本次新增字体，不对子集化能力未知的原PDF字体进行改动。
    from fontTools import subset
    from fontTools.ttLib import TTFont
    PREVIEWS.mkdir(parents=True,exist_ok=True)
    text='摘要'+''.join(new for rules in TERMS.values() for _,new in rules)+''.join(r[3] for r in BLOCK_REPAIRS)+''.join(r[3] for r in LOCAL_REPAIRS)
    for name,file in list(FONTFILES.items()):
        font=TTFont(file,fontNumber=0)
        subsetter=subset.Subsetter();subsetter.populate(text=text);subsetter.subset(font)
        path=PREVIEWS/f'{name}_subset.ttf';font.save(path);font.close()
        FONTFILES[name]=str(path)


def author(regenerate=False):
    targets = [output(n) for n in ("18", "19", "20")]
    if regenerate:
        previous=json.loads((PREVIEWS/'verification_data.json').read_text(encoding='utf-8'))
        originals=previous['originals']
        assert {str(p) for p in targets} == {o['path'] for o in previous['outputs']}
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in originals.items())
        assert all(hashlib.sha256(Path(o['path']).read_bytes()).hexdigest()==o['output_sha256'] for o in previous['outputs'])
        assert all(str(p) not in originals for p in targets)
    else:
        assert not any(p.exists() for p in targets), "已有校正版，禁止覆盖"
        originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob("*.pdf")}
    prepare_fonts()
    staged=subprocess.check_output(['git','--no-optional-locks','diff','--cached','--raw'])
    numbers=sys.argv[2:] if regenerate and len(sys.argv)>2 else ('18','19','20')
    assert set(numbers) <= {'18','19','20'}
    ledger = {"originals": originals, "staged_sha256":hashlib.sha256(staged).hexdigest(),
              "staged_count":len(staged.splitlines()), "outputs": []}
    if regenerate:
        assert ledger['staged_sha256']==previous['staged_sha256']
        ledger['outputs']=[o for o in previous['outputs'] if o['number'] not in numbers]
    for number in numbers:
        doc, english = fitz.open(source(number)), fitz.open(source(number, "英文"))
        all_ops = []
        for pi, page in enumerate(doc):
            ops = operations(number, pi+1, page.get_text("rawdict"))
            for op in ops:
                if op["kind"] == "panel":
                    # 清除原译文字，白底仅限明确需要恢复原文的技术区域。
                    r = op["clear_rect"]
                    page.add_redact_annot(fitz.Rect(r.x0+.2,r.y0+.2,r.x1-.2,r.y1-.2), fill=(1,1,1), cross_out=False)
                else:
                    remove_chars(page, op["items"])
            if ops:
                page.apply_redactions(images=0, graphics=0)
            for op in ops:
                if op["kind"] == "panel":
                    page.show_pdf_page(op["rect"], english, pi, clip=op["clip"], keep_proportion=False)
                    # show_pdf_page不复制链接注释，额外保留原英文参考文献中的外链。
                    for link in english[pi].get_links():
                        if link.get("uri") and op["clip"].contains(link["from"]):
                            rect = fitz.Rect(*(v*1.5 for v in link["from"]))
                            page.insert_link({"kind":fitz.LINK_URI,"from":rect,"uri":link["uri"]})
                elif op["kind"] == "block":
                    size, lines = write_block(page, op["block"], op["new"])
                    op["size"], op["lines"] = size, lines
                else:
                    write_term(page, op["items"], op["new"])
                all_ops.append(dict(page=pi+1, kind=op["kind"], rect=list(op.get("clear_rect",op["rect"])),
                                    old=op.get("old"), new=op.get("new"), reason=op["reason"]))
        doc.save(output(number), garbage=4, deflate=True)
        ledger["outputs"].append(dict(number=number,path=str(output(number)),pages=len(doc),operations=all_ops,
                                      output_sha256=hashlib.sha256(output(number).read_bytes()).hexdigest()))
        print(number, len(doc), 'pages', Counter(op['kind'] for op in all_ops), flush=True)
    # 这是工具生成的验证数据，不是人工文档；保存在本次临时目录，便于核验。
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    (PREVIEWS/"verification_data.json").write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding="utf-8")


def verify():
    ledger = json.loads((PREVIEWS/"verification_data.json").read_text(encoding="utf-8"))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in ledger["originals"].items())
    staged=subprocess.check_output(['git','--no-optional-locks','diff','--cached','--raw'])
    assert hashlib.sha256(staged).hexdigest()==ledger['staged_sha256']
    for out in ledger["outputs"]:
        before, after = fitz.open(source(out["number"])), fitz.open(out["path"])
        assert len(before) == len(after) == out["pages"]
        outside_total, edited_pages = 0, 0
        for pi, (p1,p2) in enumerate(zip(before, after)):
            assert p1.rect == p2.rect
            ops = [op for op in out["operations"] if op["page"]==pi+1]
            a, b = p1.get_pixmap(alpha=False), p2.get_pixmap(alpha=False)
            aa = np.frombuffer(a.samples,dtype=np.uint8).reshape(a.height,a.width,3)
            bb = np.frombuffer(b.samples,dtype=np.uint8).reshape(b.height,b.width,3)
            changed = np.any(aa != bb,axis=2)
            mask = np.zeros(changed.shape,dtype=bool)
            for op in ops:
                r = pad(fitz.Rect(op["rect"]),3)
                mask[max(0,math.floor(r.y0)):math.ceil(r.y1),max(0,math.floor(r.x0)):math.ceil(r.x1)] = True
                if op["new"]:
                    visible = normalized(p2.get_text(clip=pad(fitz.Rect(op["rect"]),3)))
                    # 隐藏的原英文层可能插入其他文本；使用相对顺序而非整段连续字符串。
                    target = normalized(op["new"])
                    it = iter(visible)
                    assert all(any(c==want for c in it) for want in target), (out["number"],pi+1,op["reason"],target,visible)
            outside = int(np.count_nonzero(changed & ~mask))
            outside_total += outside
            if outside:
                ys,xs = np.where(changed & ~mask)
                print('OUTSIDE',out['number'],pi+1,outside,(int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())),flush=True)
            if ops:
                edited_pages += 1
                b.save(str(PREVIEWS/f"{out['number']}_{pi+1}_after.png"))
                # 拼接修改前后的小区域，供逐处目视复核。
                crops=[]
                for i,op in enumerate(ops):
                    r=pad(fitz.Rect(op['rect']),3)&p1.rect
                    crops.append((p1.get_pixmap(matrix=fitz.Matrix(1.6,1.6),clip=r),p2.get_pixmap(matrix=fitz.Matrix(1.6,1.6),clip=r),op['reason']))
                from PIL import Image, ImageDraw
                w=max(max(x.width,y.width) for x,y,_ in crops)
                total=sum(max(x.height,y.height)+30 for x,y,_ in crops)
                sheet=Image.new('RGB',(w*2+20,total),'#dddddd');draw=ImageDraw.Draw(sheet)
                yy=0
                for i,(x,y,reason) in enumerate(crops):
                    draw.text((4,yy),f"{out['number']} p{pi+1} edit{i+1}: BEFORE / AFTER",fill='black')
                    yy+=22
                    sheet.paste(Image.frombytes('RGB',(x.width,x.height),x.samples),(0,yy))
                    sheet.paste(Image.frombytes('RGB',(y.width,y.height),y.samples),(w+20,yy))
                    yy+=max(x.height,y.height)+8
                sheet.save(PREVIEWS/f"{out['number']}_{pi+1}_changes.png")
        assert outside_total == 0, (out['number'], 'non-target rendering changed', outside_total)
        out['verification']={'originals_unchanged':True,'pages_and_dimensions_unchanged':True,'edited_pages':edited_pages,'outside_changed_pixels':outside_total}
        out['output_sha256']=hashlib.sha256(Path(out['path']).read_bytes()).hexdigest()
        print('VERIFIED',out['number'],out['verification'],flush=True)
    (PREVIEWS/'verification_data.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')


def dry_run():
    numbers=sys.argv[2:] or ('18','19','20')
    for number in numbers:
        doc=fitz.open(source(number));count=Counter();short=Counter()
        for pi,page in enumerate(doc):
            ops=operations(number,pi+1,page.get_text('rawdict'))
            for op in ops:
                if op['kind']=='block':
                    # 内存中的副本用于拟合，不输出PDF。
                    write_block(page,op['block'],op['new'])
                elif op['kind']=='term':
                    write_term(page,op['items'],op['new'])
                count[op['kind']]+=1;short[op['reason']]+=1
        print(number,count)
        for reason,n in short.items():print(n,reason)


def contacts():
    from PIL import Image,ImageDraw
    ledger=json.loads((PREVIEWS/'verification_data.json').read_text(encoding='utf-8'))
    for out in ledger['outputs']:
        doc=fitz.open(out['path'])
        for start in range(0,len(doc),12):
            sheet=Image.new('RGB',(1020,1440),'#dddddd');draw=ImageDraw.Draw(sheet)
            for offset in range(min(12,len(doc)-start)):
                pi=start+offset;pix=doc[pi].get_pixmap(matrix=fitz.Matrix(.35,.35),alpha=False)
                tile=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                x=(offset%3)*340;y=(offset//3)*360
                draw.text((x+8,y+4),f"{out['number']} p{pi+1}",fill='black')
                tile.thumbnail((330,330));sheet.paste(tile,(x+4,y+25))
            path=PREVIEWS/f"{out['number']}_contact_{start+1}.png";sheet.save(path);print(path)


if __name__ == "__main__":
    if sys.argv[1] in {"author", "verify", "dry-run", "regenerate", "contacts"}:
        {"author":author,"verify":verify,"dry-run":dry_run,"regenerate":lambda:author(True),"contacts":contacts}[sys.argv[1]]()
        raise SystemExit
    number = sys.argv[1]
    start, end = int(sys.argv[2]), int(sys.argv[3])
    with fitz.open(source(number)) as document:
        for page_number in range(start - 1, min(end, len(document))):
            print(f"\n===== {number} PAGE {page_number + 1} =====")
            for index, text, _ in chinese_blocks(document[page_number]):
                print(f"[b{index}] {text}")
