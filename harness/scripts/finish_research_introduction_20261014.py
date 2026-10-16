"""Record completion of the reviewed document task without touching research state."""

from __future__ import annotations
import hashlib
import json
from prepare_research_introduction_20261014 import ROOT, WORK, prepend


def load(name):
    return json.loads((WORK / name).read_text(encoding="utf-8"))


def finish():
    structural = load("document_structural_check.json")
    render = load("document_render_check.json")
    figures = load("figure_qa/summary.json")
    assert not structural["problems"]
    assert structural["staged_diff_unchanged"]
    assert not render["outside_text"] and not render["nonblack_text"]
    assert not render["sparse_no_image_pages"]
    assert render["a4_upright"] and render["pages"] == render["page_pngs"]
    assert (
        sum(p["images"] for p in render["page_details"])
        == structural["embedded_images"]
    )
    assert all(
        f["glyph_exit"] == 0 and f["collision_exit"] == 0 for f in figures["figures"]
    )
    doc = ROOT / structural["docx"]
    assert (
        hashlib.sha256(doc.read_bytes()).digest()
        == hashlib.sha256(
            (WORK / "research_introduction_render.docx").read_bytes()
        ).digest()
    )
    pages = render["pages"]
    summary = (
        f"- 研究介绍 Word 已生成并实际渲染为{pages}页A4；前15页研究正文，随后来源/导航及完整索引、历史图集。覆盖corrected_v1—v4、900/480/16主证据、2165强化执行、320受控判定、358首提案与最新v3/v4开发。\n"
        "- 新绘15幅300dpi PNG及SVG/PDF；157组既有图317源文件原样复制，136幅不同图像入册。7张报告页面预览移出本任务图集，源文件保留。\n"
        "- Word894处文字颜色均为000000；实际PDF全部文字纯黑、无文字越界、无空白页，151幅嵌图可读。全部页面联系图及重点正文原尺寸检查通过。\n"
        "- 15图字号检查通过、碰撞0 FAIL；6个环图内孔文字WARN已逐图复核。源码19 PASS/0 FAIL，PNG与300dpi两个格式提示符合本任务；限定辅助脚本Ruff/编译通过。\n"
        "- 7个选定科研来源及317原图/副本哈希保持，原Git暂存diff不变。0模型API/新实验/统计重跑/产品代码/权限/论文/Git交付。F-DOC-009 verified仅限文档图集，其他科研feature状态不变。\n"
        "- Word：docs/M3_PI_Guard_研究介绍_2026-10-14.docx；完整图片与目录：docs/picture/。任务：harness/tasks/research-introduction-word-20261014.md。"
    )
    heading = "## 2026-10-14 — 研究介绍 Word 与完整图集（已验证）"
    for rel in [
        "harness/state/current-task.md",
        "harness/state/progress.md",
        "harness/state/task-history.md",
    ]:
        prepend(rel, heading, summary)
    handoff = summary + (
        "\n- 修改范围：新DOCX、docs/picture新图和历史副本/目录；本任务七个辅助脚本、任务记录及必要Harness状态/失败记录。当前无本任务未完成步骤。\n"
        "- 命令：python -X utf8 harness/scripts/prepare_research_introduction_20261014.py；plot_research_introduction_20261014.py；bundled Node执行build_research_introduction_20261014.mjs；bundled Python执行verify_research_introduction_20261014.py；audit_research_introduction_figures_20261014.py；bundled render_docx.py --output_dir harness/workspaces/research-introduction-20261014/rendered-release --emit_pdf --width 1200 --height 1600；review_research_introduction_pdf_20261014.py。精确执行路径及参数另见任务。\n"
        "- 验证材料：harness/workspaces/research-introduction-20261014内structural/render检查JSON、figure_qa、原尺寸页图和联系图。内部PDF/预览用于QA，不作为额外交付。\n"
        "- 下一步：阅读Word正文及图表目录；若修订介绍，只更新本任务文档与图，保持原始科研记录及其他用户改动。"
    )
    prepend("harness/state/session-handoff.md", heading, handoff)
    path = ROOT / "harness/features/feature_list.json"
    text = path.read_bytes().decode("utf-8-sig")
    pos = text.index('"id": "F-DOC-009"')
    start = text.rfind("{", 0, pos)
    feature, length = json.JSONDecoder().raw_decode(text[start:])
    assert feature["id"] == "F-DOC-009"
    feature["status"] = "verified"
    feature["verification"] = [
        f"Word实际渲染{pages}页A4；151嵌图；全部文字000000；无越界/空白页",
        "15新绘图字号通过/碰撞0FAIL；6个内孔WARN人工复核；157组历史图317文件来源哈希保持",
        "正文覆盖corrected_v1至v4、当前主证据及强化研究；7个科研来源及暂存diff保持；无API或研究执行",
    ]
    nl = "\r\n" if "\r\n" in text else "\n"
    block = json.dumps(feature, ensure_ascii=False, indent=2).replace("\n", nl + "    ")
    path.write_bytes((text[:start] + block + text[start + length :]).encode("utf-8"))
    task = ROOT / "harness/tasks/research-introduction-word-20261014.md"
    content = task.read_text(encoding="utf-8").replace(
        "状态：in_progress", "状态：verified", 1
    )
    content = content.replace("进行中。现有便携", "环境：现有便携", 1)
    if "## 最终验证与交付" not in content:
        content += (
            "\n\n## 最终验证与交付\n\n"
            + summary
            + "\n\n### 实际命令\n\n```powershell\n"
        )
        content += "python -X utf8 harness/scripts/prepare_research_introduction_20261014.py\npython -X utf8 harness/scripts/plot_research_introduction_20261014.py\n"
        content += "& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' harness/scripts/build_research_introduction_20261014.mjs\n"
        content += "& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 harness/scripts/verify_research_introduction_20261014.py\n"
        content += "python -X utf8 harness/scripts/audit_research_introduction_figures_20261014.py\n"
        content += "$env:PATH = 'C:/Users/gaohang/.cache/codex-tools/libreoffice-26.2.4/portable/program;' + $env:PATH\n"
        content += "& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'C:/Users/gaohang/.codex/plugins/cache/openai-primary-runtime/documents/26.1013.11914/skills/documents/render_docx.py' 'E:/M3_PI_Guard_test/harness/workspaces/research-introduction-20261014/research_introduction_render.docx' --output_dir 'E:/M3_PI_Guard_test/harness/workspaces/research-introduction-20261014/rendered-release' --emit_pdf --width 1200 --height 1600\n"
        content += "python -X utf8 harness/scripts/review_research_introduction_pdf_20261014.py\n```\n\n产品单元/集成测试、Full Harness与论文构建不运行：本轮仅文档与配图，以上构建/渲染/源码/颜色/数据/来源检查是相关验证。一般架构未改变，不新增架构决策。\n"
    task.write_text(content, encoding="utf-8")
    print(
        json.dumps(
            {
                "feature": "F-DOC-009",
                "status": "verified",
                "pages": pages,
                "new_figures": 15,
                "historical_groups": 157,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    finish()
