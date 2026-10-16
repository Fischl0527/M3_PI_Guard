"""Record the verified Word revision without changing scientific feature status."""

from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/teacher-brief-20261014"


def prepend(relative, title, content):
    p = ROOT / relative
    s = p.read_bytes().decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in s else "\n"
    if title in s:
        return
    first = s.index(nl) + len(nl)
    addition = title + nl + nl + content.replace("\n", nl) + nl + nl
    p.write_bytes((s[:first] + nl + addition + s[first:].lstrip("\r\n")).encode("utf-8"))


def finish():
    check = json.loads((WORK / "verification.json").read_text(encoding="utf-8"))
    change = json.loads((WORK / "detailed_changes.json").read_text(encoding="utf-8"))
    assert not check["problems"]
    assert check["render"]["brief"]["pages"] == 2
    assert check["preservation"]["original_spacing_changes"] == 0
    assert all(v for k, v in check["preservation"].items() if k != "original_spacing_changes")
    for source, qa in [
        ("docs/M3_PI_Guard_研究介绍_教师交流两页版_2026-10-14.docx", "teacher_brief.docx"),
        ("docs/M3_PI_Guard_研究介绍_2026-10-14.docx", "detailed_report.docx"),
    ]:
        assert sha256((ROOT / source).read_bytes()).digest() == sha256((WORK / qa).read_bytes()).digest()
    title = "## 2026-10-14 — 两页教师简版与详细报告补充（已验证）"
    note = (
        "- 教师简版实际渲染2页A4：纯黑文字、无填充/表格/图片/显式分页；完整概括早期E1—E17，当前仅corrected-v1。\n"
        f"- 原名详细版实际渲染{check['render']['detailed']['pages']}页：新增{change['added_characters']}字符、共{len(change['added_paragraphs'])}个段落/标题，补充早期17项、增量研究与图解；移除50处强制分页。\n"
        "- 原有段落、151嵌图、42表及图像尺寸保持，段落/图片间距变更0；原暂存diff保持。docs/picture不变，无API、新实验或产品/权限逻辑改动。\n"
        "- 两份Word均已渲染并完成视觉核对；XML/PDF颜色、分页、分母/版本与内容完整性检查通过，三个辅助脚本Ruff/内存编译通过。\n"
        "- 简版docs/M3_PI_Guard_研究介绍_教师交流两页版_2026-10-14.docx；详细版docs/M3_PI_Guard_研究介绍_2026-10-14.docx。\n"
        "- 任务harness/tasks/teacher-brief-20261014.md；复核harness/workspaces/teacher-brief-20261014/verification.json与visual_review.md；原详细版备份在同工作目录。F-DOC-009 verified，其他研究feature状态不变。"
    )
    for file in ("current-task.md", "progress.md", "task-history.md", "session-handoff.md"):
        prepend("harness/state/" + file, title, note)
    task_path = ROOT / "harness/tasks/teacher-brief-20261014.md"
    task = task_path.read_text(encoding="utf-8").replace("状态：in_progress。", "状态：verified。", 1)
    if "## 最终验证与命令" not in task:
        task += "\n\n## 最终验证与命令\n\n" + note + "\n\n"
        task += (
            "实际核对来源：experiments/registry.json；outputs/experiments/E1至E16/analysis.md；E9/E14主来源为context_correction_v2_r3；E17_human_stratified_360_v1/review/analysis.md；docs/research/paper_v2/incremental_empirical_v1/phase_report_v1.md；manuscript_current_zh_v2.md的corrected-v1章节。\n\n"
            "```powershell\n"
            "& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 harness/scripts/build_teacher_documents_20261014.py\n"
            "$env:PATH = 'C:/Users/gaohang/.cache/codex-tools/libreoffice-26.2.4/portable/program;' + $env:PATH\n"
            "& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'C:/Users/gaohang/.codex/plugins/cache/openai-primary-runtime/documents/26.1013.11914/skills/documents/render_docx.py' 'E:/M3_PI_Guard_test/harness/workspaces/teacher-brief-20261014/teacher_brief.docx' --output_dir 'E:/M3_PI_Guard_test/harness/workspaces/teacher-brief-20261014/rendered-brief-final-v2' --emit_pdf --width 1200 --height 1600\n"
            "& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'C:/Users/gaohang/.codex/plugins/cache/openai-primary-runtime/documents/26.1013.11914/skills/documents/render_docx.py' 'E:/M3_PI_Guard_test/harness/workspaces/teacher-brief-20261014/detailed_report.docx' --output_dir 'E:/M3_PI_Guard_test/harness/workspaces/teacher-brief-20261014/rendered-detailed-final-v2' --emit_pdf --width 1000 --height 1400\n"
            "python -X utf8 harness/scripts/verify_teacher_documents_20261014.py\n"
            "python -X utf8 -m ruff check harness/scripts/build_teacher_documents_20261014.py harness/scripts/verify_teacher_documents_20261014.py harness/scripts/finish_teacher_documents_20261014.py\n"
            "```\n\n"
            "文档任务不运行产品单元/集成测试、Full Harness或科研统计；DOCX构建、实际渲染、全部页面视觉、原文/图像/间距/暂存保持和脚本检查覆盖本次变更。一次只读XPath探查转义错误已改用stdin脚本；一次Ruff未使用导入已移除，最终均通过。未改架构或科研结论，不新增架构决策。\n"
        )
    task_path.write_text(task, encoding="utf-8")
    feature_path = ROOT / "harness/features/feature_list.json"
    s = feature_path.read_bytes().decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in s else "\n"
    feature = next(x for x in json.loads(s)["features"] if x["id"] == "F-DOC-009")
    revised = dict(feature)
    revised.update({
        "name": "研究介绍两页简版与详细报告及实验图集",
        "description": "两页纯黑无填充教师简版概括早期E1—E17、当前仅v1；详细版补充解释、无强制分页，完整版本与图集保留。",
        "status": "verified",
        "acceptanceCriteria": [
            "教师简版实际2页、纯黑文字、无填充，历史E1—E17覆盖且当前仅v1",
            "原名详细版增加解释、无显式分页，原文/图表/间距保持",
            "两份均实际渲染和视觉核对，原暂存及实验数据保持",
        ],
        "verification": [
            "简版2页A4；详细版40页A4；全Word/PDF文字纯黑；两份显式分页0，简版填充/表格/图片0",
            "详细版新增5001字符/39段落及标题，早期17项与后续增量编号分别说明；原151嵌图/42表/文字/尺寸及间距保持",
            "原15新图及157组317历史图文件不变；当前暂存diff保持；无模型或科研执行",
            "限定三辅助脚本Ruff及内存编译通过；最终核对在teacher-brief-20261014工作目录",
        ],
    })
    def block(obj):
        return nl.join("    " + line for line in json.dumps(obj, ensure_ascii=False, indent=2).splitlines())
    assert block(feature) in s
    feature_path.write_bytes(s.replace(block(feature), block(revised), 1).encode("utf-8"))
    print("F-DOC-009 verified; two Word deliverables and task state recorded")


if __name__ == "__main__":
    finish()
