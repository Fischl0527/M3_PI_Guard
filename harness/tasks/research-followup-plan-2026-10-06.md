# 综合评估与后续研究计划

日期：2026-10-06。关联F-PAPER-002。状态：规划交付及本轮链接/格式检查完成；新增实现、实验和论文同步未执行。

## 需求与范围

- 用户要求阅读D:\下载\M3-PI Guard 后续研究与论文推进计划.md，结合项目和此前Claude计划，输出新的Markdown计划到对应文档目录。
- 只修改新计划及必要Harness记录。保留原文、已完成实验、论文、源码和所有既存dirty改动。
- 不调用模型API、不启动服务/实验、不运行Full Harness或历史统计、不编译论文、不Git提交/推送。

## 分析记录

- 当前codex/claude-review-repairs，HEAD44ea311；不是下载文档的旧分支快照。
- exact_target_v2、模糊权限、缺分类及效果记录修复已有验证；900授权+16模型控制完成。不能重复执行新文档的先修复/再360exact流程。
- 新900无同期no-defense，攻击0/490不是490独立任务或有效性证明；AgentDojoauto良性2/30，exact13/30/11/30；M3auto16/30/17/30，exact14/30/16/30。105非正常结束仍保留。
- 原固定攻击100案例的底层任务数只读计数：AgentDojo35、M3-v2 46，可按suite/族覆盖各取30；AgentDojo身份含suite。
- E8现有qualification_v2为0provider calls、8参考轨迹成功、0noop成功、0异常；18任务的10个评分false不能当模型失败或上游缺陷证据。
- 当前英文稿仍含旧17/30→0/30/旧exact与E6叙事；没有更新其内容。
- 核验AgentDojo正式NeurIPS2024页及AgentDyn arXiv v3/官方仓库。AgentDyn新题名/六作者与旧检索快照不同，以当前一手记录为准；不声称正式会议状态。JISA官网403，分区/范围最新核验不冒称通过。

## 计划与风险

- 新计划：docs/research/paper_v2/M3_PI_Guard_综合评估与后续研究计划_2026-10-06.md。
- P0先读本研究公开事件解释低效用及失败，只修可复现违约；保留未知，压力授权预期限制不自动修成放行。
- P1核心120任务×no-defense/policy/full=360新同期执行；可选VIGIL120在调用前确定。P2嵌套60×3本地180；P3 E8端点可解释后最多108。
- 最大建议768研究项，主线必选360；非全量强制结项。无Gemini、盲测、日期等待、旧900重跑、递归哈希。
- 新研究均待用户实施指令。新旧运行时期/版本不能用于无混杂修复归因；本地模型和E8不可相互替代外部有效性。
- 后续双语/LaTeX先纠正已明确旧解释，再整合新证据；作者信息仍空。F-PAPER-002保持in_progress。

## 本轮验证

- Get-Content/rg：完整阅读用户1784行文件和Claude501行计划，读取最新报告、E8结果、有关运行接口、状态及英文稿；未执行实验分析器。
- PowerShell只读JSON解析与固定cohort分组：确认180结构及35/46攻击底层任务数；检查E8和feature状态。
- git status --short、git log -1、git branch --show-current、git remote get-url origin：确认真实checkout和既存dirty，不修改索引。
- 本轮只改文档/状态，不运行pytest/Ruff/模型/LaTeX；验证范围是新计划链接、结构、JSON和scoped diff。
- 实际交付检查：计划417行、8个本地链接0断链、2个代码围栏成对、0尾部空格；feature JSON解析成功且F-PAPER-002仍in_progress。`git diff --check -- harness/state/current-task.md harness/state/progress.md harness/state/task-history.md harness/state/session-handoff.md harness/features/feature_list.json` exit0；LF/CRLF提示保留，不进行全仓库换行重写。current-task中原16行未提交新增保留，不混为本轮工作。

## 下一步

用户确认执行后先做P0原因分类；不得直接恢复旧runner或重跑已成功916项。正式模型配置、输入和统计比较应在新调用前记录。
