# 综合评估与研究收束计划

日期：2026-10-06。关联：F-PAPER-002。状态：规划文档已交付，文档检查通过；科研整体保持in_progress。

## 目标和范围

按用户要求完整阅读D:\下载\M3-PI Guard 后续研究与论文推进计划.md，结合Claude整改路线与本项目真实进展，输出Markdown到docs/research/paper_v2。

允许：新计划、本任务及必要Harness记录。禁止：API/服务/实验/权限/论文修改或构建/历史统计重算/Full Harness/目录迁移/其他dirty的提交。不改变既有持续目标状态，不停止任何进程。

验收：已完成与计划明确区分；900/16/480及四主表/20补充表不重复；主图/PDF和60意图审查是真正待办；条件性新增的先决条件、分母、安全与失败规则清楚；文档链接、围栏、格式及feature JSON有效。

## 分析与实施

- 完整读取1784行下载计划、Claude整改计划/修复报告，读取当前900+16/480报告和缓存摘要、延迟v2、AgentDyn控制、双语与生成器相关路径。
- 当前HEAD a44281c、分支codex/claude-review-repairs、origin RedTeam_LLM_Security；工作区现有表格集成和其他dirty未发布。只读匹配实验Python进程未列出活动项，不停止进程。
- 下载计划的exact修复及新增活性研究已完成；旧E6不能作为当前实际效果强证据。同期效用代价、稀疏安全区间和基线配置限制必须居主位。
- 新入口docs/research/paper_v2/M3_PI_Guard_研究收束与论文推进计划_2026-10-06.md保留所有历史计划，更新四主表/20补充已完成的真实状态；下一步60任务解释和主图/PDF，360/180/108有条件而非自动运行。
- 使用academic-research-suite实验规划技能，按用户限制不新增审批/哈希体系。核验AgentDojo正式NeurIPS2024及AgentDyn arXiv v3；JISA官网403、学校分区未知明确披露。

## 验证

本轮只做Markdown和状态检查；不运行pytest/Ruff/PDF，因为未修改可执行或论文代码。确切结果在检查后登记，不把既有32项检查说成本轮重跑。

- PowerShell `Get-Content -LiteralPath ... -Raw`及正则链接/围栏/空白检查：计划253行，6个本地链接，0断链，2个围栏成对，0尾空格和替换字符，exit0。
- 首次链接检查发生PowerShell参数集错误；改用`[IO.Path]::GetDirectoryName`解析父目录后通过。失败和修正记录在failure-log，不将未解析路径误报为真实断链。
- `Get-Content harness/features/feature_list.json -Raw | ConvertFrom-Json`通过；F-PAPER-002仍in_progress，新增本计划说明恰好一项。
- `git diff --check -- harness/state/current-task.md harness/state/progress.md harness/state/task-history.md harness/state/session-handoff.md harness/features/feature_list.json` exit0；仅既有LF/CRLF策略提示，不改Git配置。
- 只新增本计划/任务并追加必要状态及失败说明。已有表格/生成器/论文、旧计划、原始结果和其他dirty保持；未Git提交或推送，未启动下一实验。

## 后续

本任务交付不关闭F-PAPER-002；实施继续既有research-followup-execution-2026-10-06。当前用户请求仅规划，不开始下一实验、不提交其他未完成内容。
