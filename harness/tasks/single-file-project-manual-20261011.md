# 单篇中文项目手册整合

## 目标与范围

- 用户已选择改写现有 `docs/LLM的千层诱惑.md`，采用通俗主线加代码解读；不另建多个互相跳转的总览。
- 保存原文至 `docs/archive/entry_snapshots_20261010/LLM的千层诱惑.md`，不删其他专业文档。
- 更新 `docs/README.md` 和必要 Harness 状态。对应功能 F-DOC-003；科研功能 F-PAPER-002 不变。
- 禁止修改科研代码、实验输入/raw、论文正文/LaTeX、第三方、凭据及已有无关 dirty。不调用 API，不生成演示，不运行 Full Harness、历史统计重算，不自动 Git 提交/推送/PR。

## 分析与风险

- 旧长文混有已修复 exact_gold 待办、历史 E1–E8 和过多必读跳转，不能简单拼接。
- 当前证据应分开说明900授权执行、480同期校准、16合成控制、60任务事后复核；失败、未知不补零。
- 静态动作演示不是模型实验；M3V2-H-006-BT 是现有真实调用的正常任务，公开日志没有完整正文，不能伪造对话。
- 当前主仓库默认演示 HTML/JSON 是用户已有删除，保持删除；portable_verify 的完整输入和测试清单在解包交付包，主仓库不能照搬包内命令。
- 资料核对由两位只读子代理并行完成；主代理负责正文和公共状态，避免并发写入。

## 实施计划

1. 完整保留旧文，记录现有 dirty，建立当前手册任务。
2. 按12章重写：项目问题、术语、整条链路、详细演示、机制、真实调用案例、研究、统计、目录、跨环境运行、论文、问答与自测。
3. 主线内直接解释所有必要内容；仅内部目录锚点导航，外部文档/代码链接统一放可选附录。
4. README 将单篇手册设为第一入口；专业文档继续保留。
5. 对原文保存、路径/锚点/代码围栏、当前数字、状态边界做定向检查；新上下文读者回答8问，修复不清楚的内容。
6. 更新功能、进度、历史、决策和移交，只记录实际结果。

## 验收条件

- 原文完整保留，历史/当前/未完成明确区分。
- 读者不需要打开其他文档即可理解任务、权限、提案、决策、执行、评分、结果和运行步骤。
- 使用真实受控例子及公开模型案例；不把许可/执行/完成混成一项。
- 当前数字与来源一致，运行命令区分主仓库和完整包；无泄露秘密。
- 本地链接、内部锚点、代码围栏、feature JSON 和范围检查通过；新上下文8问检查完成。

## 核对来源

- 原交接文、当前综述/代码指南/演示指南/迁移报告和论文阅读说明。
- `claude_revision_v1/report.md`、`research_followup_20261006_v1/calibration/report.md`、`trusted_intent_review/report.md`。
- 当前 corrected 运行路径、portable_demo 源码和既有测试断言、M3V2-H-006-BT 公开计划/raw/复核。

## 验证记录

- 已验证。两位只读代理核对代码/正常案例与结果/命令；来源复核确认主数字、CI、状态、模型与运行命令。现有900/480/16/60和历史执行不重算。
- 旧文存档与实施前内容作文本比较（归一化换行及末尾空行）一致；只保留原文，不声称字节级或原相对链接都可用。
- 两当前文档71本地Markdown链接、13唯一显式锚点、0坏路径/锚点/围栏，主体0外部链接依赖；11实际代码/压缩包/输入/清单路径存在。根目录缺少包输入和用户删除HTML/JSON的状态仍不变。
- 新上下文代理仅依手册回答8问全部PASS；跨研究并集、ND、trace和Python已测范围补充后四处复读PASS。不是独立外部科研审核。
- feature JSON可解析，除新增F-DOC-003外全部原feature对象不变，论文F-PAPER-002不变；活动范围git diff --check通过。原文快照不为修空白或链接改写。

### 实际检查命令

从仓库根执行：

```powershell
Get-Content -LiteralPath 'docs\archive\entry_snapshots_20261010\LLM的千层诱惑.md' -Raw
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -c $manualCheck
git diff --check -- docs/LLM的千层诱惑.md docs/README.md harness/features/feature_list.json harness/state/current-task.md
git diff --numstat -- docs/LLM的千层诱惑.md docs/README.md harness/state/current-task.md harness/features/feature_list.json harness/state/failure-log.md
git diff --name-only
```

`$manualCheck` 是本次工具中定义的只读Python内联脚本，不是环境变量或新增仓库程序。它读取两MD，排除代码围栏后查本地链接与锚点，检查13章节锚点/主体外链、JSON/原feature保持、11实际依赖路径及5处已不存在路径。检查exit0，输出71/13/11及errors=[]。原文比较由工具内存中的起始原文与归档文本完成，不生成哈希或比较包。最终状态落盘后另做窄范围JSON/空白/状态检查，结果如实追加在本节。

最终落盘检查实际exit0：`& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -c $manualFinal`核对F-DOC-003唯一且verified、有检查证据、其他feature对象与HEAD一致、F-PAPER-002仍in_progress、旧文与起始HEAD归一化文本一致、任务围栏/空白通过；`git diff --check -- docs/LLM的千层诱惑.md docs/README.md harness/features/feature_list.json harness/state/current-task.md harness/state/progress.md harness/state/task-history.md harness/state/session-handoff.md harness/state/failure-log.md harness/docs/decision-log.md`exit0。`git status --short`核对原dirty仍在，`git diff --cached --stat`为空；没有暂存、提交或远端动作。该回执只追加一次，不递归记录自身。

### 范围与未运行检查

- 没有改动Python运行代码，因此没有执行pytest、Ruff、py_compile、Full Harness。没有新演示、API、统计推断、原始计数重建或论文构建。
- 119/276项测试属于此前记录，仅作手册引用；不能当本轮测试。
- 第一次校验工具有模板转义错误未执行；EOF空行第一次删后仍有一层，确认末尾后完全消除。旧归档空白与Git CRLF设置不修改。
- 现有无关dirty保留；没有Git暂存、提交、推送或PR变更。本轮功能F-DOC-003 verified，科研feature状态保持。
