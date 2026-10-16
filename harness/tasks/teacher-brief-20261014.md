# 两页教师交流版研究介绍

状态：verified。关联：F-DOC-009。

## 需求与范围

用户要求教师交流 Word 恰好两页，纯黑文字，无任何填充，优先历史内容；后续明确原文件是详细报告，要求它保留完整内容、禁止分页符，增加文字解释并保留段落与图片原间距。因此分别交付两页简版与原名详细版。简版最新范围为完整概括早期E1—E17，五项后续增量研究仅概述并与早期编号区分；目前研究仅介绍corrected_v1，移除简版v2/v3/v4与近期强化实验。详细版补充E1—E17逐项解释，并继续覆盖完整版本与实验图集。

允许修改 docs/M3_PI_Guard_研究介绍_2026-10-14.docx，新增 docs/M3_PI_Guard_研究介绍_教师交流两页版_2026-10-14.docx、此任务的 harness/scripts 与 workspaces、必要 Harness 状态。原详细版先备份到任务工作目录。既有 docs/picture 图集、论文、产品代码、权限逻辑、实验及原暂存均保持；不调用模型或重跑统计。

## 分析与计划

1. 已读 AGENTS、current-task、architecture、progress、F-DOC-009，沿用文档技能及现有 bundled Python/docx 和便携 LibreOffice。
2. 已核对历史 E1—E5 阶段报告、当前中文论文 corrected-v1/v2 证据及 v3/v4 开发报告。历史旧风险标签仅按旧含义介绍；任务与条件执行分母区分。
3. 保存原详细版，重新组织两页纯文字稿并另存。历史研究占主要篇幅，保留机制、早期研究动因、代表数字与后续问题。两份均不使用显式分页。
4. 按用户最新要求：详细版移除手动分页及段前分页，保留段落与图片原间距，新增研究机制、历史实验动机与图表解读段落；保持全部既有文字、表格、图片与关系。
5. 用 bundled renderer 分别实际渲染；简版核对恰好两页 A4、纯黑、无底纹/填充/图片/表格；详细版核对无分页符、正文与图像保持、页数/留白改善。逐页视觉检查，记录来源与原文件保持。

## 验收

- 教师简版 Word 位于用户指定 docs 目录，可打开，实际渲染恰好两页；历史为主，目前工作仅介绍v1。
- 原名详细 Word 内容完整、无分页符及段前分页，排版比修改前紧凑。
- 纯黑文字，XML 不含底纹、高亮、背景或图形填充；无图片和表格。
- 简版完整提到早期E1—E17，历史为主，目前仅v1；详细版v1—v4保留，补充早期17项。数字有明确本地来源。
- 图片目录与既有科研数据保持；原暂存差异不消费。
- 更新相关 feature、progress、history 与 session-handoff，记录实际验证结果。


## 最终验证与命令

- 教师简版实际渲染2页A4：纯黑文字、无填充/表格/图片/显式分页；完整概括早期E1—E17，当前仅corrected-v1。
- 原名详细版实际渲染40页：新增5001字符、共39个段落/标题，补充早期17项、增量研究与图解；移除50处强制分页。
- 原有段落、151嵌图、42表及图像尺寸保持，段落/图片间距变更0；原暂存diff保持。docs/picture不变，无API、新实验或产品/权限逻辑改动。
- 两份Word均已渲染并完成视觉核对；XML/PDF颜色、分页、分母/版本与内容完整性检查通过，三个辅助脚本Ruff/内存编译通过。
- 简版docs/M3_PI_Guard_研究介绍_教师交流两页版_2026-10-14.docx；详细版docs/M3_PI_Guard_研究介绍_2026-10-14.docx。
- 任务harness/tasks/teacher-brief-20261014.md；复核harness/workspaces/teacher-brief-20261014/verification.json与visual_review.md；原详细版备份在同工作目录。F-DOC-009 verified，其他研究feature状态不变。

实际核对来源：experiments/registry.json；outputs/experiments/E1至E16/analysis.md；E9/E14主来源为context_correction_v2_r3；E17_human_stratified_360_v1/review/analysis.md；docs/research/paper_v2/incremental_empirical_v1/phase_report_v1.md；manuscript_current_zh_v2.md的corrected-v1章节。

```powershell
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 harness/scripts/build_teacher_documents_20261014.py
$env:PATH = 'C:/Users/gaohang/.cache/codex-tools/libreoffice-26.2.4/portable/program;' + $env:PATH
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'C:/Users/gaohang/.codex/plugins/cache/openai-primary-runtime/documents/26.1013.11914/skills/documents/render_docx.py' 'E:/M3_PI_Guard_test/harness/workspaces/teacher-brief-20261014/teacher_brief.docx' --output_dir 'E:/M3_PI_Guard_test/harness/workspaces/teacher-brief-20261014/rendered-brief-final-v2' --emit_pdf --width 1200 --height 1600
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'C:/Users/gaohang/.codex/plugins/cache/openai-primary-runtime/documents/26.1013.11914/skills/documents/render_docx.py' 'E:/M3_PI_Guard_test/harness/workspaces/teacher-brief-20261014/detailed_report.docx' --output_dir 'E:/M3_PI_Guard_test/harness/workspaces/teacher-brief-20261014/rendered-detailed-final-v2' --emit_pdf --width 1000 --height 1400
python -X utf8 harness/scripts/verify_teacher_documents_20261014.py
python -X utf8 -m ruff check harness/scripts/build_teacher_documents_20261014.py harness/scripts/verify_teacher_documents_20261014.py harness/scripts/finish_teacher_documents_20261014.py
```

文档任务不运行产品单元/集成测试、Full Harness或科研统计；DOCX构建、实际渲染、全部页面视觉、原文/图像/间距/暂存保持和脚本检查覆盖本次变更。一次只读XPath探查转义错误已改用stdin脚本；一次Ruff未使用导入已移除，最终均通过。未改架构或科研结论，不新增架构决策。
