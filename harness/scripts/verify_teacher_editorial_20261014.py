"""Check paper-only references, preserved figures and actual report pagination."""

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from zipfile import ZipFile

from lxml import etree as E

import verify_teacher_documents_20261014 as qa
from revise_teacher_documents_editorial_20261014 import REFERENCES

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/teacher-documents-editorial-20261014"
NS = qa.NS
LOCAL = re.compile(r"(?:[A-Z]:[\\/]|(?:outputs|experiments|harness|docs|paper_upgrade_v\d+)[\\/]|\.(?:md|json|jsonl|py)\b)")


def root(path):
    with ZipFile(path) as z:
        return E.fromstring(z.read("word/document.xml"))


def image_spacing(xml):
    return [dict(e.attrib) if e is not None else None
            for p in xml.findall(".//w:p", NS) if p.findall(".//w:drawing", NS)
            for e in [p.find("w:pPr/w:spacing", NS)]]


def run():
    result = {"problems": [], "documents": {}}
    for kind, filename, qa_name in [
        ("brief", "M3_PI_Guard_研究介绍_教师交流两页版_2026-10-14.docx", "teacher_brief.docx"),
        ("detailed", "M3_PI_Guard_研究介绍_2026-10-14.docx", "detailed_report.docx"),
    ]:
        path = ROOT / "docs" / filename
        obj = qa.inspect_docx(path)
        xml = obj.pop("root")
        paragraphs = ["".join(p.xpath(".//w:t/text()", namespaces=NS)) for p in xml.findall(".//w:p", NS)]
        body = ["".join(p.xpath(".//w:t/text()", namespaces=NS)) for p in xml.findall("w:body/w:p", NS)]
        local = [t for t in paragraphs if LOCAL.search(t)]
        nonpaper = [t for t in paragraphs if re.match(r"^(资料依据|本节来源|上述历史过程依据|来源\s*\[)", t)]
        refs = [t for t in body if re.match(r"^\[\d+\]", t)]
        cited = set(re.findall(r"\[(\d+)\]", "".join(t for t in body if not t.startswith("["))))
        limits = [t for t in body if "局限性" in t and len(t) > 45]
        obj.update({"local_path_citations": local, "nonpaper_source_paragraphs": nonpaper,
                    "paper_references": refs, "citation_ids": sorted(cited),
                    "limitations_paragraphs": len(limits)})
        if local or nonpaper or refs != REFERENCES or cited != {"1", "2", "3"} or len(limits) != 1:
            obj["errors"].append("reference or limitation contract violated")
        with ZipFile(path) as z:
            ext = []
            for name in z.namelist():
                if name.endswith(".rels"):
                    for e in E.fromstring(z.read(name)):
                        if e.get("TargetMode") == "External" and not e.get("Target", "").startswith("https://"):
                            ext.append(e.get("Target"))
            if ext:
                obj["errors"].append("local external links remain")
        if kind == "brief":
            if obj["fill_elements"] or obj["tables"] or obj["drawings"]:
                obj["errors"].append("brief has fill or graphics")
            s = "".join(body)
            if not all("E" + str(i) in s for i in range(1, 18)):
                obj["errors"].append("early experiment coverage incomplete")
        if kind == "detailed":
            before = qa.inspect_docx(WORK / "before_detailed.docx")
            old = before.pop("root")
            obj["media_unchanged"] = obj["media"] == before["media"]
            obj["tables_unchanged"] = obj["tables"] == before["tables"]
            obj["picture_spacing_unchanged"] = image_spacing(xml) == image_spacing(old)
            obj["dimensions_unchanged"] = [dict(e.attrib) for e in xml.iter() if E.QName(e).localname == "extent"] == [dict(e.attrib) for e in old.iter() if E.QName(e).localname == "extent"]
            if not all(obj[k] for k in ("media_unchanged", "tables_unchanged", "picture_spacing_unchanged", "dimensions_unchanged")):
                obj["errors"].append("figure or table preservation failed")
        if sha256(path.read_bytes()).digest() != sha256((WORK / qa_name).read_bytes()).digest():
            obj["errors"].append("delivery differs from rendered copy")
        render = qa.inspect_pdf(kind, WORK / ("rendered-brief-v1" if kind == "brief" else "rendered-detailed-v1"), 2 if kind == "brief" else None)
        obj["render"] = render
        result["problems"].extend(obj["errors"] + render["errors"])
        result["documents"][kind] = obj
    before = json.loads((WORK / "before.json").read_text(encoding="utf-8"))
    staged = subprocess.run(["git", "diff", "--cached", "--binary"], cwd=ROOT, capture_output=True, check=True).stdout
    result["staged_diff_unchanged"] = sha256(staged).hexdigest() == before["staged_diff_sha256"]
    if not result["staged_diff_unchanged"]:
        result["problems"].append("staged diff changed")
    qa.WORK = WORK
    qa.review_pairs(WORK / "rendered-detailed-v1")
    (WORK / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pages": {k:v["render"]["pages"] for k,v in result["documents"].items()},
                      "references": {k:len(v["paper_references"]) for k,v in result["documents"].items()},
                      "limitations": {k:v["limitations_paragraphs"] for k,v in result["documents"].items()},
                      "problems":result["problems"]}, ensure_ascii=False))
    if result["problems"]:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
