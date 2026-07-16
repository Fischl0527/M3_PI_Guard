# Rubric Ledger (Inferred From Competition Brief)

## Rubric Item C1
### Source
`文档资料/比赛与规范/比赛要求/附件1：命题挑战赛赛题.pdf`
### Criterion
从红队视角覆盖提示注入、越狱、工具调用劫持、记忆中毒、环境污染等典型攻击面。
### Weight Or Importance
Critical
### Expected Evidence
9类攻击数据、攻击链、E6-E11结果和代表案例。
### Draft Location
数据集卡、E6-E11 bundles、最终分析图表和 Dashboard。
### Status
pass
### Evidence
M3-PI-300 已覆盖 9 类攻击；E6-E11 已完成并通过 bundle/hash 审计。
### Repair Action
No repair required; keep E11 post-hoc supplement separate from the frozen denominator.
### Notes
Benign不计作攻击族。

## Rubric Item C2
### Source
Competition brief
### Criterion
至少3类攻击场景，每类包含对抗样本、越狱测试用例集和智能体攻击脚本。
### Weight Or Importance
Critical
### Expected Evidence
每类canonical cases、生成器/派生脚本、manifest与运行日志。
### Draft Location
`m3_attacks`, `experiments` and frozen experiment bundles.
### Status
pass
### Evidence
Canonical/derived generators、9 类案例、manifest 和原始 RunLog 均已完成并可追溯。
### Repair Action
No repair required for case/script coverage; E17 remains a separate review gate.
### Notes
必须区分样本生成器和真实工具攻击执行。

## Rubric Item C3
### Source
Competition brief
### Criterion
行为监督原型能拦截智能体与外部工具交互，并支持allow/ask/deny或异常检测。
### Weight Or Importance
Critical
### Expected Evidence
Guard接口、工具沙箱、决策日志、E1-E4及Dashboard回放。
### Draft Location
Source code, system architecture, E1-E4 bundles and Dashboard replay.
### Status
pass
### Evidence
Prompt 与 Guard 已正交；six core conditions、detector/policy/dataflow 及 named ablations 已执行和验证。
### Repair Action
No repair required.
### Notes
效果结论只能来自无泄漏实验。

## Rubric Item C4
### Source
Competition brief
### Criterion
提供模拟邮件、文件、API等业务工具与本地安全边界。
### Weight Or Importance
High
### Expected Evidence
工具实现、mock边界测试、合法/恶意工具任务。
### Draft Location
`m3_core/tool_sandbox.py`, E11/E12, safety docs.
### Status
pass
### Evidence
Mock file/email/API/code boundaries、authorized_actions、E11/E12 和独立临时 sandbox 均已实现并测试。
### Repair Action
No repair required; real services remain forbidden.
### Notes
不允许真实副作用。

## Rubric Item C5
### Source
Competition brief
### Criterion
模型调用链安全监控、基座模型检测/过滤原型、监督端实时展示告警和阻断记录。
### Weight Or Importance
Critical
### Expected Evidence
RunLog/manifest、Guard、模型矩阵、Dashboard筛选和攻击链回放。
### Draft Location
Runtime, frozen evidence and Dashboard.
### Status
pass
### Evidence
RunLog/manifest 新字段、五模型 smoke、四模型盲测、Guard trace 和 Dashboard 筛选/回放均已完成。
### Repair Action
No repair required; keep the frozen Dashboard source separate from the enhanced evidence UI.
### Notes
需明确项目自有Agent靶场与可嵌入Guard接口的关系。

## Rubric Item C6
### Source
User-approved experiment plan
### Criterion
实验设计可信：显式标签、无标签泄漏、盲测冻结、配对对照、统计置信区间。
### Weight Or Importance
Critical
### Expected Evidence
E0、数据审计、prompt测试、manifest hash、E13和统计输出。
### Draft Location
E0/E13 evidence, dataset audit, prompt tests, freeze and statistics outputs.
### Status
pass
### Evidence
E0 corrected historical denominators and passed 600/600 prompt leakage checks; validation-only thresholds and paired statistics are frozen.
### Repair Action
No repair required; old FPR=0 remains labelled prototype-only.
### Notes
旧FPR=0不能继续作为正式证据。

## Rubric Item C7
### Source
User-approved experiment plan
### Criterion
跨模型、跨语言、规避、多轮、长上下文、工具链、性能和稳定性覆盖充分。
### Weight Or Importance
High
### Expected Evidence
E5-E16全部completed。
### Draft Location
E5-E16 bundles, figures and Dashboard.
### Status
pass
### Evidence
E5-E16 coverage is complete. Corrected E9/E14 execution-r3 replaces the invalid old context claims with 120/120 E9 formal runs and 432/432 E14 formal runs plus 48/48 excluded warmups; E11 execution-r2 provides current-runtime cross-tool evidence. Old v3 and failed r2 bundles remain diagnostic only.
### Repair Action
No completion repair remains; keep small-cell uncertainty and historical invalidation visible.
### Notes
分族小样本需标记探索性。

## Rubric Item C8
### Source
Harness and user completion condition
### Criterion
所有结果可复现、可恢复、可从 manifest 定位，最终分析/图表/Dashboard 与冻结证据一致。
### Weight Or Importance
Critical
### Expected Evidence
Registry complete、one-command rebuild、final audit、Dashboard/figure checks、local commit。
### Draft Location
Harness, outputs, delivery files.
### Status
pass
### Evidence
Registry is 18 completed / 0 running / 0 failed. Two distinct humans completed the frozen sampled E17 protocol; final analysis has 13 charts and 63 manifest artifacts; independent statistics and Dashboard evidence gates pass; all 50 test files pass. The final local commit is the authorized handoff action.
### Repair Action
No evidence-completion repair remains. Product work should prioritize the four failed acceptance targets without rewriting current results.
### Notes
不得远程推送；PPT、DOCX 报告和提交 ZIP 不适用当前范围。
