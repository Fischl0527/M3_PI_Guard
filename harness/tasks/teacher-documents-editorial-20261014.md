# 教师研究介绍引文与表述修订

状态：verified，2026-10-16续接验收完成。关联F-DOC-009。

用户要求：两份Word删除本地路径及对论文以外文件的引用；论文引文有明确出处；减少防御性措辞，各文档的局限性集中为一个段落。沿用此前两页简版、纯黑无填充、历史E1—E17完整概述且当前仅v1；详细版保留全部图表、段落/图片间距与自然分页并补充解释。

计划：备份当前两份文档；以已核对实验数据重写解释、删除报告及注册表引文，将图集路径换为中文研究名和图意；仅在相关工作处引用正式核实的论文，使用编号和完整书目/官方链接；各自保留一个局限性段落。实际渲染两份，检查简版2页、文字颜色、填充、分页、图表保持、无路径和非论文引文、编号对应及逐页版面。仅改Word及必要Harness；不改科研数据、图片源或产品，不调用模型，不Git交付。

已核对论文：AgentDojo（NeurIPS 2024官方论文页）；Progent 2025 arXiv v1；Defeating Prompt Injections by Design 2025 arXiv v1。使用明确版本以保持题名与作者对应。

## 实施与验收

- 两份原名Word已原位更新；修订前备份为本任务工作目录的before_detailed.docx与before_brief.docx。详细版重写58处正文，移除37处内部来源或重复说明；136处图集路径改为中文研究名与图意。
- 引文仅为上述三篇论文，正文[1]—[3]与完整书目一一对应。项目自己的结果按实验编号、模型与条件直接说明；局限性各集中一段。
- 简版实际2页，覆盖历史E1—E17、当前仅v1，纯黑且填充/表格/图片均0；详细版实际40页，保留151幅嵌图和42表，媒体哈希、图像尺寸与图片段落间距和修订前一致，两份显式分页均0。
- 两份均已实际渲染；简版两页及详细版全部40页已逐页视觉检查，标题、正文、引文、表格及图集无新增裁切/遮挡。自然留白与原图保留；未重绘历史图或重算统计。
- 最终XML/PDF检查problems=[]，本地路径/非论文来源段落均0，所有正文引文有对应书目，每份局限性段落1；交付文件与渲染副本逐字节一致。原暂存diff哈希保持。
- 2026-10-16新增路径规则检查5项0问题；两份编辑辅助脚本Ruff与内存编译通过。此前5条E702已拆为单行语句后复测通过，记录于failure-log。
- 附加Git空白检查提示failure-log既有EOF空行，未改无关尾部；此次顶部新增记录单独检查。此项不影响Word验收，不能声称整文件Git空白检查通过。
- 验证证据：harness/workspaces/teacher-documents-editorial-20261014/verification.json及visual_review.md。未运行产品单测/完整Harness：此次只改说明文档与辅助排版脚本，已完成针对DOCX结构、内容、实际分页及视觉结果的验证；未改产品行为。

## 执行命令

```powershell
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 harness/scripts/revise_teacher_documents_editorial_20261014.py
$env:PATH = 'C:/Users/gaohang/.cache/codex-tools/libreoffice-26.2.4/portable/program;' + $env:PATH
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'C:/Users/gaohang/.codex/plugins/cache/openai-primary-runtime/documents/26.1013.11914/skills/documents/render_docx.py' 'E:/M3_PI_Guard_test/harness/workspaces/teacher-documents-editorial-20261014/teacher_brief.docx' --output_dir 'E:/M3_PI_Guard_test/harness/workspaces/teacher-documents-editorial-20261014/rendered-brief-v1' --emit_pdf --width 1200 --height 1600
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'C:/Users/gaohang/.codex/plugins/cache/openai-primary-runtime/documents/26.1013.11914/skills/documents/render_docx.py' 'E:/M3_PI_Guard_test/harness/workspaces/teacher-documents-editorial-20261014/detailed_report.docx' --output_dir 'E:/M3_PI_Guard_test/harness/workspaces/teacher-documents-editorial-20261014/rendered-detailed-v1' --emit_pdf --width 1000 --height 1400
python -X utf8 -B harness/scripts/check_paths.py harness/scripts/revise_teacher_documents_editorial_20261014.py harness/scripts/verify_teacher_editorial_20261014.py harness/tasks/teacher-documents-editorial-20261014.md harness/workspaces/teacher-documents-editorial-20261014/visual_review.md harness/workspaces/teacher-documents-editorial-20261014/verification.json
python -X utf8 -B harness/scripts/verify_teacher_editorial_20261014.py
python -X utf8 -B -m ruff check harness/scripts/revise_teacher_documents_editorial_20261014.py harness/scripts/verify_teacher_editorial_20261014.py
@'
from pathlib import Path
paths = [Path('harness/scripts/revise_teacher_documents_editorial_20261014.py'), Path('harness/scripts/verify_teacher_editorial_20261014.py')]
for p in paths:
    compile(p.read_text(encoding='utf-8'), str(p), 'exec')
print('Two editorial helper scripts compile in memory: PASS')
'@ | python -X utf8 -B -
```

本任务不调用模型、不执行实验、不改科研原始结果或docs/picture，不改权限逻辑、不暂存/提交/推送。F-DOC-009验收仅指本次文档交付；其他研究功能状态保持。下一步无本次必需工作，可直接使用两份原名Word。
