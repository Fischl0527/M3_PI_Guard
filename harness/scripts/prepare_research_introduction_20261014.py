"""Prepare a scoped introduction and source-preserving research figure catalog."""

from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/research-introduction-20261014"
PIC = ROOT / "docs/picture"
FEATURE_ID = "F-DOC-009"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepend(rel, title, content):
    p = ROOT / rel
    raw = p.read_bytes()
    s = raw.decode("utf-8-sig")
    if title in s:
        return
    nl = "\r\n" if "\r\n" in s else "\n"
    i = s.find(nl)
    s = (
        s[: i + len(nl)]
        + nl
        + title
        + nl
        + nl
        + content.replace("\n", nl)
        + nl
        + nl
        + s[i + len(nl) :].lstrip("\r\n")
    )
    p.write_bytes(s.encode("utf-8"))


def prepare():
    WORK.mkdir(parents=True, exist_ok=True)
    PIC.mkdir(parents=True, exist_ok=True)
    snapshot = WORK / "source_snapshot.json"
    if not snapshot.exists():
        protected = [
            "outputs/experiments/empirical_reinforcement_v1/analysis_v1.json",
            "outputs/experiments/task_contract_compiler_v4_development_v1/analysis_v1.json",
            "docs/research/paper_v2/manuscript/manuscript_current_zh_v2.md",
        ]
        for p in (ROOT / "outputs/experiments/empirical_reinforcement_v1").rglob(
            "raw_records_v1.jsonl"
        ):
            protected.append(p.relative_to(ROOT).as_posix())
        staged = subprocess.run(
            ["git", "diff", "--cached", "--binary"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        obj = {
            "sources": {p: sha(ROOT / p) for p in protected},
            "staged_diff_sha256": hashlib.sha256(staged).hexdigest(),
        }
        snapshot.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    title = "## 2026-10-14 — 研究介绍 Word 与完整图集（制作中）"
    content = "- 用户要求 docs 下纯黑字体研究介绍 Word，docs/picture 下配套图，并追加覆盖 corrected_v1—v4 与历史实验图表。\n- 任务 harness/tasks/research-introduction-word-20261014.md，F-DOC-009。只新增说明、图表副本及必要 Harness；不改代码、raw、论文或原图，不调用模型，不 Git 交付。\n- 以最新论文、强化实证和 v3/v4 开发报告为准；生成后实际渲染与数据/字体检查，完成前保持 in_progress。"
    prepend("harness/state/current-task.md", title, content)
    prepend("harness/state/progress.md", title, content)
    f = ROOT / "harness/features/feature_list.json"
    s = f.read_bytes().decode("utf-8-sig")
    features = json.loads(s)["features"]
    if not any(x["id"] == FEATURE_ID for x in features):
        feature = {
            "id": FEATURE_ID,
            "name": "研究介绍 Word 与版本及完整实验图集",
            "description": "黑色文字中文研究介绍，覆盖 corrected_v1—v4、当前证据与历史实验图表。",
            "status": "in_progress",
            "priority": "high",
            "acceptanceCriteria": [
                "DOCX及完整图片位于指定目录",
                "Word文字纯黑，数字有来源，版本清楚",
                "实际渲染全部页面并检查，源数据与暂存保持",
            ],
            "verification": [],
        }
        nl = "\r\n" if "\r\n" in s else "\n"
        block = json.dumps(feature, ensure_ascii=False, indent=2).replace("\n", nl)
        block = nl.join("    " + line for line in block.split(nl))
        s = s.replace('"features": [', '"features": [' + nl + block + ",", 1)
        f.write_bytes(s.encode("utf-8"))
    roots = [
        "outputs/experiments",
        "outputs/paper_upgrade_v1",
        "outputs/paper_upgrade_v2",
        "outputs/reports/paper_v2",
    ]
    grouped = {}
    excluded = []
    for rel in roots:
        for p in sorted((ROOT / rel).rglob("*")):
            if not p.is_file() or p.suffix.lower() not in {".png", ".svg", ".pdf"}:
                continue
            low = p.as_posix().lower()
            if any(
                x in low
                for x in [
                    "collision",
                    "alignment",
                    "overlay",
                    "/report_qa/",
                    "/previews/",
                    "/rendered/",
                    "report_preview",
                    "/figures_demo/",
                    "visual_qa",
                    "/pytest",
                    "/test-",
                ]
            ):
                excluded.append(p.relative_to(ROOT).as_posix())
                continue
            if (
                p.suffix == ".pdf"
                and not any(p.with_suffix(x).exists() for x in [".png", ".svg"])
                and not any(x in p.parts for x in ["figures", "charts"])
            ):
                continue
            key = p.relative_to(ROOT).with_suffix("").as_posix()
            grouped.setdefault(key, []).append(p)
    catalog = []
    for key, paths in grouped.items():
        low = key.lower()
        if "/_invalid/" in low:
            status = "停用记录"
        elif any(
            x in low
            for x in [
                "diagnostic",
                "cold_start",
                "stub",
                "smoke",
                "preflight",
                "policy_regime_smoke",
            ]
        ):
            status = "诊断与预检"
        elif any(
            x in low
            for x in [
                "claude_revision",
                "research_followup_20261006",
                "empirical_reinforcement",
                "task_contract_compiler_v4",
            ]
        ):
            status = "当前研究"
        else:
            status = "历史研究"
        dests = []
        for p in paths:
            target = PIC / "历史实验图表" / p.relative_to(ROOT / "outputs")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and sha(target) != sha(p):
                raise RuntimeError(f"Existing different destination: {target}")
            if not target.exists():
                shutil.copy2(p, target)
            dests.append(target.relative_to(ROOT).as_posix())
        source_png = next((p for p in paths if p.suffix == ".png"), None)
        representative = source_png or next(
            (p for p in paths if p.suffix == ".pdf"), paths[0]
        )
        catalog.append(
            {
                "id": f"H{len(catalog) + 1:03d}",
                "source_stem": key,
                "status": status,
                "files": dests,
                "original_hashes": {
                    p.relative_to(ROOT).as_posix(): sha(p) for p in paths
                },
                "representative_source": representative.relative_to(ROOT).as_posix(),
            }
        )
    data = {
        "empirical": load(
            "outputs/experiments/empirical_reinforcement_v1/analysis_v1.json"
        ),
        "v4": load(
            "outputs/experiments/task_contract_compiler_v4_development_v1/analysis_v1.json"
        ),
        "history": catalog,
        "excluded_qa": excluded,
    }
    (WORK / "research_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "historical_chart_groups": len(catalog),
        "source_files": sum(len(x["files"]) for x in catalog),
        "by_stage": dict(Counter(x["status"] for x in catalog)),
        "excluded_generated_qa": len(excluded),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    prepare()
