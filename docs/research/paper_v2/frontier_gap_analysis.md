# paper-v2 前沿差异与主张边界

版本：`2026-07-23.v1`

## 可保留的研究问题

- `RQ1 — Authorization leakage`：逐样本 gold/evaluator 授权信息进入在线 Guard 时，会把 unsafe-effect 与任务完成率高估多少？
- `RQ2 — Runtime mechanism`：在不读取 gold/evaluator 字段的条件下，权限单调、参数来源、时序/数据流与独立确认是否优于 policy-only？
- `RQ3 — Security–utility trade-off`：`ALLOW/ASK/DENY` 能否在 unsafe effect、TCR 和确认负担之间取得非退化优势？
- `RQ4 — Robustness`：在防御感知的自适应攻击和不同授权 regime 下，结论是否保持？

## 当前可以写与不可以写的主张

| 主张 | 当前状态 | 升级为论文主张所需证据 |
|---|---|---|
| paper-v1 在线路径未直接读取 evaluator/gold 字段 | 仅限当前仓库与已覆盖路径；paper-v2 投影契约已实现 | 在真实 paper-v2 运行中保留字段摘要、冻结记录和独立复核 |
| 外部基线普遍存在 oracle authorization | **不得声明**；20 个审计单元未支持该强结论 | 独立第二复核与更强动态边界证据；不能把已达数量门槛等同于领域结论 |
| M3-full 优于 policy-only | 未证实 | 配对中型证伪实验，再由正式公共基准复核 |
| M3-full 优于最强结构化基线 | 未证实 | 对 VIGIL/DRIFT 的忠实适配、相同模型/任务/攻击和配对统计 |
| M3 的参数来源追踪是首创 | 已被 ARGUS/AuthGraph 等前沿工作否定 | 删除 first/only 叙事，改为联合评估与执行约束 |
| ASK 机制具有实际价值 | 未证实 | 确认率、确认后完成率、用户负担和 deny-all 退化检查 |
| 自适应攻击下仍鲁棒 | 未证实 | 按预算阶梯运行防御感知攻击，失败与超时留在分母 |
| 适合 JISA | 范围匹配已初核 | 投稿前由学校/Clarivate 核验当期 SCIE/JCR Q2，并复核专题/常规栏目 |

## 机制论文的止损门槛

只有同时满足以下四点，才保留“防御机制具有优势”的论文主线：

1. M3-full 相对最强结构化基线的 unsafe-effect 点估计相对降低至少 20%，或绝对降低至少 10 个百分点。
2. 合法任务 TCR 的单侧非劣界限不差于 `-5pp`。
3. M3-full 相对 policy-only 呈方向一致且可解释的模块增益。
4. `ASK + DENY` 不构成近似 deny-all，且 operational failure 不解释主要效果。

任一前三项失败，默认切换到授权泄漏、授权不确定性和安全—效用权衡的实证论文，不隐去负面结果。

## 需要正面比较的五组工作

1. `VIGIL`：提交前验证和 SIREN，是同行评审首要结构化基线。
2. `DRIFT`：动态规则、控制/数据流和记忆隔离，是完整机制边界。
3. `Task Shield / PlanGuard`：任务或计划一致性，是 policy-only 的主要比较。
4. `Progent / CaMeL / IPIGuard`：最小权限、能力和工具依赖图，是 privilege/dataflow 组。
5. `ARGUS / AuthGraph`：上下文决策审计和来源—授权图，是新颖性威胁；无代码时也必须进入 Related Work。

## 论文叙事

当前候选标题：

> Beyond Answer-Key Authorization: Evaluating and Enforcing Provenance-Aware Runtime Authorization for Tool-Using LLM Agents

20 个 online-state 审计单元没有建立系统性 `Answer-Key Authorization`
证据，因此上述标题当前暂停，默认使用：

> Evaluating Runtime Authorization Under Context and Provenance Uncertainty for Tool-Using LLM Agents

贡献顺序固定为：

1. 一个禁止 evaluator/gold 字段进入在线状态、可用摘要证明的评估方法；
2. 一个非 oracle、权限单调、来源/时序感知且带独立确认的运行时机制；
3. 在公共基准、配对消融和自适应攻击下联合报告 unsafe effect、TCR、确认负担与 operational failure；
4. 可由 manifest、哈希、日志和统计脚本重建的证据链。
