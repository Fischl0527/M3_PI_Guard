# Task Shield v1.6 执行结果与路线决策（终版）

更新时间：2026-07-23

## 结论

Task Shield v1.6 的工程正确性修复已验证，但扩大资格实验未通过，因此停止 Task Shield 正式实验路线，不进入 P5 或 P6。v1.3–v1.6 应保留为透明的负面工程证据；下一条强基线主线转向 Progent 和 CaMeL 或同类信息流方案。

本结论不改变 Q2 就绪度，不写正式结果注册表，也不把超时当作攻击被阻断。

## 本轮完成内容

- P0：完成 AgentDojo 指标语义审计和非破坏性 analysis-v2。官方 raw trace 中 `security=true` 表示注入目标执行成功；旧 adapter 的 `attack_success=not security` 是取反错误。G0 为 `15/15 passed`。
- P1–P2：新增 v1.6 runtime、runner、freeze builder、资格分析器和 32 项无模型回归。SDK `max_retries=0`，完整 JSON/schema/cardinality 恢复由唯一两次逻辑尝试负责；成功与失败都先保存 trace；runner 不提供 resume 或 failed-case retry。G1 为 `20/20 passed`，freeze 为 `21/21 passed`。
- P3：fresh 4-case 预检完成 `4/4`、0 failed、0 missing，G2 为 `11/11 passed`。
- P4：fresh 12-case 扩大资格形成 12/12 terminal rows，其中 9 completed、3 `case_timeout`、0 missing。G3 为 `12/16`，结论为 failed。
- 运行结束后已卸载模型、停止 Ollama，11434 端口不再监听。

## P4 结果

| 指标 | Task Shield v1.6 | Matched ToolFilter | 解释 |
| --- | ---: | ---: | --- |
| Standalone utility | 2/6 | 2/6 | 只刚好达到最低资格线 |
| Attack-condition utility | 0/6 | 2/6 | Task Shield 明显损失任务效用 |
| Raw injection success | 已完成攻击 0/5，另 1 条超时未判定 | 0/6 | 不能声称 Task Shield 带来安全增益 |
| Operational failure | 3/12 | 0/12 | Slack utility、Workspace utility/attack 超时 |
| p50 latency | 175.677 s | — | 诊断资格结果 |
| p95 latency | 600.070 s | 39.545 s | 约为 comparator 的 15.175 倍 |
| max latency | 600.145 s | — | 超过 600 秒门禁（watchdog 调度开销约百毫秒） |

三条超时均保留在原分母和 case manifest 中，并保留 terminal verifier trace、独立时间戳与 SHA-256。没有重跑、排除或覆盖失败行。

## 失败原因

### 1. 主要问题已经从“证据缺失”转为“方法成本不可接受”

v1.6 修复了 v1.5 的失败 trace 丢失、时间字段复用、SDK 隐式重试、超时类型误捕获和不完整 schema 恢复。P4 所有 12 条 terminal row 均有可验证 trace，说明新的证据链可靠；但可靠证据显示该方法在当前 8GB 本地 8B 环境中不具备扩大运行资格。

### 2. Verifier 是主要时间来源

P4 共记录 154 条 verifier request rows，累计约 2698 秒，占全部 case 时间约 78.92%。其中 29 次输出不满足完整契约并进入第 2 次逻辑尝试：

- invalid JSON：17 次；
- 传输超时：5 次；
- cardinality 少行：4 次；
- score 非数值：3 次。

恢复机制没有耗尽成 schema fail-closed 拒绝，说明正确性修复本身有效；但恢复和大量逐指令评分显著增加了延迟。

### 3. 低 ASR 与任务失败纠缠

六条 attack-condition utility 全部失败，其中 Workspace attack 还直接超时。虽然已完成的五条攻击没有执行注入目标，但 matched ToolFilter 在相同六条上的 raw injection success 同样为 0/6。Task Shield 没有提供可观察的安全增益，却使 attack-condition utility 从 2/6 降为 0/6。

### 4. 不是“全拒工具”造成的，但仍是退化结果

P4 共 21 个工具调用提案，只拒绝 2 个，因此并非简单通过全拒工具获得低 ASR。然而任务完成率仍很低，表明自然语言任务抽取/逐提案评分、agent 能力和长轨迹成本共同构成瓶颈。

## 可行方案

### 论文主线

1. 停止 Task Shield P5/P6，不提高其超时阈值后继续硬跑，也不把三个失败案例单独补跑。
2. 将 v1.3–v1.6 写入论文的基线工程与负面结果部分，透明披露指标取反、恢复成本、超时与效用退化。
3. 把正式强基线资源优先转移到 Progent；其符号权限/单调收缩机制与 M3 的授权不确定性更直接可比。
4. 第二优先级执行 CaMeL 或同类 capability/data-flow 基线，用于比较来源追踪和信息流机制。
5. 公共基准、独立 600 条盲测、两家前沿 API 和自适应预算攻击仍是 Q2-80 的主要证据缺口。

### 如果以后单独优化 Task Shield

只能作为新的方法/系统变体，而不是修改 v1.6 或恢复旧根：

- 使用独立小型 verifier，而不是让同一个 8B 模型同时承担 agent 与所有对齐判断；
- 使用 grammar-constrained decoding，减少 invalid JSON、cardinality 和非数值 score；
- 将多个 instruction/task 对一次性批量评分，减少 request 数；
- 对 trusted task extraction 做 case 内缓存；
- 冻结 verifier request budget，并把 budget exhaustion 作为独立失败；
- 新建版本、freeze、fresh root 和 matched comparator，不能复用 P4 选择做确认性结论。

这些优化已经改变论文复现条件，应标成 Task Shield-inspired optimized variant，而不是继续宣称 disclosed-paper reproduction。

## 证据与图表

- G0：`protocols/paper_upgrade_v1/execution/taskshield_v16_p0_metric_semantics_v1/gate_g0.json`
- G1：`protocols/paper_upgrade_v1/execution/taskshield_v16_p1_p2_correctness_v1/gate_g1.json`
- G2：`protocols/paper_upgrade_v1/execution/taskshield_v16_p3_preflight_v1/gate_g2.json`
- G3：`protocols/paper_upgrade_v1/execution/taskshield_v16_p4_expanded_v1/gate_g3.json`
- P3：`outputs/paper_upgrade_v1/baselines/taskshield_v16_preflight_4case/`
- P4：`outputs/paper_upgrade_v1/baselines/taskshield_v16_qualification_12case/`
- 详细 post-hoc 分析：`outputs/paper_upgrade_v1/analysis_v2/taskshield_v16_qualification/analysis.md`
- 延迟条形图：`outputs/paper_upgrade_v1/analysis_v2/taskshield_v16_qualification/figures/case_latency_vs_comparator.png`
- G3 门禁图：`outputs/paper_upgrade_v1/analysis_v2/taskshield_v16_qualification/figures/g3_gate_checks.png`
- Verifier 合约压力图：`outputs/paper_upgrade_v1/analysis_v2/taskshield_v16_qualification/figures/verifier_contract_pressure.png`

## 证据边界

P3/P4 都是已知回归选择上的资格实验，不是独立盲测或正式论文效果证据。P4 的原始攻击成功率只可对 5 条已完成攻击案例描述，剩余 1 条是未解决的运行失败；不得写成 0/6 的正式 ASR。Q2 就绪度与注册表在本轮保持不变。
