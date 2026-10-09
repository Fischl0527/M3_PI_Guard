# paper-v2：当前研究和历史证据

更新：2026-10-09。路线是实证研究，不是继续证明“完整防护一定更强”。

## 先看已经完成的修复版研究

| 材料 | 数量与作用 | 入口 |
|---|---|---|
| 修复版授权制度实验 | 180 个案例对应 900 条执行；不同制度和配置是重复执行，不是 900 个独立任务 | [实际结果报告](../../../outputs/experiments/claude_revision_v1/report.md) |
| 合成组件控制 | 16 条模型执行；与离线 Guard 单元测试分开 | 同上报告及 [synthetic_regression_raw.jsonl](../../../outputs/experiments/claude_revision_v1/synthetic_regression_raw.jsonl) |
| 同期攻击活性与效用校准 | 120 个任务、四条件，共 480 条；含无防护同期对照 | [后续研究总报告](../../../outputs/experiments/research_followup_20261006_v1/report.md) |
| 良性任务解释性复核 | 复核 60 个既有任务及其 240 条四条件记录；不是新增 240 条模型执行 | 同上报告的 trusted-intent review 部分 |
| 当前论文主图 | 基于上述当前证据生成；历史补充图与其分开 | [manuscript_figures](../../../outputs/experiments/research_followup_20261006_v1/manuscript_figures/) |

关键限制：

- AgentDojo 中，无防护的良性工具任务完成为 17/30，policy/full 为 2/30；这反映当前编译授权与任务要求的不匹配，不能把大量阻断当成净安全收益。
- 同期 AgentDojo 攻击结果为 3/30 对 0/30，但差异区间跨零，不能据此宣称已证明防御优越。
- M3-v2 对照中的低事件数限制安全效应估计。
- `exact_target_v2` 使用离线预期目标形成权限，属于带答案信息的对照；“未直接发送原始 gold 字段”不代表完全没有答案依赖。
- 解释性复核是在看到结果之后进行，不能伪称预注册的因果实验。

## 看论文与审查

- [论文工作区入口](manuscript/README.md)：当前英文、中文、LaTeX 和补充材料。
- [证据索引](../../证据索引.md)：结果与主张的对应关系。
- [Claude 修复报告（2026-10-06）](Claude审核修复报告_2026-10-06.md)：当时的实现修复记录；后续执行状态以本页上方报告为准。
- [审核整改计划（2026-10-05）](Claude审核整改计划_2026-10-05.md)与[80% 证据执行计划 v2](M3_PI_Guard_80_percent_evidence_execution_plan_v2.md)：历史决策材料，不是今天自动恢复的任务清单。
- 当前工程状态：[Harness 进度](../../../harness/state/progress.md)。论文功能 F-PAPER-002 仍是 `in_progress`。

## 旧研究仍保留，但不要拼成修复版证据

历史 Public Pro 5,082 条、Flash 1,791 条、中型研究以及 E1–E6 的实现、样本、模型身份和端点各有自己的冻结语义。它们可以用于历史或敏感性说明，不能直接证明修复后的来源／数据流模块已经改善实际越权效果。

E5 是 12 个 B200 未成功任务的条件性尾部扩展，不是完整 B500 队列，也不证明攻击饱和。历史 E6 最终改为 DeepSeek 360 条单执行区块；不能继续称“三日期重复性研究”。Gemini 的不完整记录仅为诊断，不能用于跨厂商效应结论。

相关历史产物仍在 `outputs/experiments/lean_empirical/`、`incremental_empirical_v1/` 及各自协议目录；不覆盖、不合并原始行，也不重新跑旧实验。

## 不再作为当前门槛的项目

盲测、600 条独立封存、完整 Gemini 矩阵、80 分内部评分、hardest-20×2,000、Full Harness 与历史递归证据重放均不属于当前任务。旧文件保留这些内容只用于追溯。

作者信息继续留空；正式投稿前仍需作者完成声明、数据／代码发布安排，以及投稿当天的期刊分区核验。
