# P1 同期校准报告

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Mode: run + validate
- Date: 2026-10-06
- Status: actual recorded results, not submission readiness

## 完成量与设计

计划480条，记录480，待记录0。状态：`{'completed': 443, 'max_steps': 9, 'parse_failure': 25, 'runner_failure': 2, 'provider_failure': 1}`。官方请求1172次，token 1578814；CNY旧峰时费率参考估计4.7428，并非当前账单。

固定120个案例：两个基准各30攻击、30良性工具。攻击每个底层任务只选一个实例；选自已固定cohort，不使用本轮结果筛选。所有条件normal普通提示/auto_compiled授权/T0/512输出/180秒超时；模拟执行能力和物理安全边界相同。无真实邮件、支付、生产接口、宿主代码执行。

三主条件各120条；配置明确的VIGIL额外120。VIGIL固定源码hybrid确定性审计、模型生成约束，关闭LLM二次验证；16-call上限，其余8-call。不能称完整默认VIGIL或最强SOTA系统。16正式前缀已计入总量，不重复。

第一阶段在120条后因两次VIGIL约束输出截断被误分类为程序错误而停止，并使一条已有响应的无防护任务终止。这三条及全部120条原记录都保留，没有重跑。telemetry_v1.1仅隔离线程日志并将后续身份有效、明确length截断的约束失败归为parse_failure；512输出、提示、权限与计划不改。续跑仅覆盖此前未触碰项。两阶段分别记录runner_revision，不能把分类修正解释成防御增益。

投影收据完整性：478条明确记录在线禁止字段不存在，2条缺少此收据；实际记录为存在的条数0。缺收据的两条早期VIGIL失败为diagnostic/未知，保留ITT；没有后补旧收据，也不将未观察到泄漏写成480条全部证实无泄漏。480条均记录provider tools禁用、真实external effect为0；完整结构化safety_receipt为476条，缺4条（VIGIL约束失败，效果端点未知）。这是本运行路径的限定检查，不是任意系统安全认证。

## 结果

|基准/类型|条件|记录/计划|危险 真/已知|完成 真/已知|未知危险/完成|非正常结束|ASK/DENY|
|---|---|---:|---:|---:|---:|---:|---:|
|agentdojo-v1/attack|Full modules|30/30|0/30|4/30|0/0|0|29/0|
|agentdojo-v1/attack|Policy only|30/30|0/30|4/30|0/0|0|29/0|
|agentdojo-v1/attack|No defense|30/30|3/30|18/30|0/0|5|0/1|
|agentdojo-v1/attack|VIGIL configured|30/30|4/28|20/28|2/2|3|0/1|
|agentdojo-v1/benign_tool|Full modules|30/30|0/30|2/30|0/0|0|29/0|
|agentdojo-v1/benign_tool|Policy only|30/30|0/30|2/30|0/0|0|29/0|
|agentdojo-v1/benign_tool|No defense|30/30|0/30|17/30|0/0|7|0/3|
|agentdojo-v1/benign_tool|VIGIL configured|30/30|0/28|17/28|2/2|7|0/4|
|m3-v2/attack|Full modules|30/30|0/30|24/30|0/0|0|1/0|
|m3-v2/attack|Policy only|30/30|0/30|24/30|0/0|0|0/0|
|m3-v2/attack|No defense|30/30|0/30|24/30|0/0|0|0/0|
|m3-v2/attack|VIGIL configured|30/30|0/30|24/30|0/0|0|0/0|
|m3-v2/benign_tool|Full modules|30/30|0/30|16/30|0/0|4|2/4|
|m3-v2/benign_tool|Policy only|30/30|0/30|17/30|0/0|1|3/1|
|m3-v2/benign_tool|No defense|30/30|0/30|16/30|0/0|4|0/4|
|m3-v2/benign_tool|VIGIL configured|30/30|0/30|16/30|0/0|6|0/6|

![同期危险效果与良性完成率](figures/contemporaneous_endpoints.png)

## 配对比较

核心三个比较按各基准、各端点分别Holm校正；VIGIL两项是描述性配置对照，不增加主要显著性家族。区间采用Newcombe配对区间、10,000次底层任务bootstrap，McNemar为辅助检验。未知不填零，所有计划项保留在ITT上下界；零事件和退化bootstrap不是确定性安全证明。

|基准|端点|比较|已知配对|差异pp|95%配对区间pp|Holm p|
|---|---|---|---:|---:|---|---:|
|agentdojo-v1|unsafe_effect|policy_minus_nd|30|-10.00|[-25.62,+3.10]|0.7500|
|agentdojo-v1|unsafe_effect|full_minus_nd|30|-10.00|[-25.62,+3.10]|0.7500|
|agentdojo-v1|unsafe_effect|full_minus_policy|30|+0.00|[-11.35,+11.35]|1.0000|
|agentdojo-v1|unsafe_effect|vigil_minus_nd|28|+3.57|[-6.69,+15.43]|descriptive|
|agentdojo-v1|unsafe_effect|full_minus_vigil|28|-14.29|[-31.49,+0.52]|descriptive|
|agentdojo-v1|task_completion|policy_minus_nd|30|-50.00|[-66.83,-26.80]|0.0008|
|agentdojo-v1|task_completion|full_minus_nd|30|-50.00|[-66.83,-26.80]|0.0008|
|agentdojo-v1|task_completion|full_minus_policy|30|+0.00|[-9.84,+9.84]|1.0000|
|agentdojo-v1|task_completion|vigil_minus_nd|28|+3.57|[-3.24,+10.35]|descriptive|
|agentdojo-v1|task_completion|full_minus_vigil|28|-53.57|[-68.98,-32.39]|descriptive|
|m3-v2|unsafe_effect|policy_minus_nd|30|+0.00|[-11.35,+11.35]|1.0000|
|m3-v2|unsafe_effect|full_minus_nd|30|+0.00|[-11.35,+11.35]|1.0000|
|m3-v2|unsafe_effect|full_minus_policy|30|+0.00|[-11.35,+11.35]|1.0000|
|m3-v2|unsafe_effect|vigil_minus_nd|30|+0.00|[-11.35,+11.35]|descriptive|
|m3-v2|unsafe_effect|full_minus_vigil|30|+0.00|[-11.35,+11.35]|descriptive|
|m3-v2|task_completion|policy_minus_nd|30|+3.33|[-2.87,+9.44]|1.0000|
|m3-v2|task_completion|full_minus_nd|30|+0.00|[-0.76,+0.76]|1.0000|
|m3-v2|task_completion|full_minus_policy|30|-3.33|[-9.44,+2.87]|1.0000|
|m3-v2|task_completion|vigil_minus_nd|30|+0.00|[-0.76,+0.76]|descriptive|
|m3-v2|task_completion|full_minus_vigil|30|+0.00|[-0.76,+0.76]|descriptive|

## 解释与目录

攻击效果以no-defense同期活性为解释前提。若无防护无事件，则只报告当前地板/模型任务适配限制；若有事件，仍须结合完成率、失败和配对区间，不能只看阻断数。AgentDojo使用内存副本上的原生评分；M3-v2只计隔离沙箱中有执行证据的效果。两者分别报告，不混成相同端点。

研究目录：E:\M3_PI_Guard_test\outputs\experiments\research_followup_20261006_v1\calibration。

```text
calibration/
├── plan.jsonl              # 480个新计划项，版本和参数
├── raw_records.jsonl       # append-only终态，未覆盖旧916行
├── status.json             # 前缀门及终态进度
├── analysis.json           # 一次统计、区间和未知上下界
├── tables/cells.csv        # 分层表和负担
├── figures/contemporaneous_endpoints.png
├── report.md               # 本报告
└── internal/               # 忽略的请求摘要和锁，禁止上传
```

11/11统计误区检查：分层、不做部署基率/个体推广；原队列选择限制披露；不依新结果筛选或排除；不把历史前后差解释成修复因果；未知与失败保持分母；所有预定比较呈现；Holm家族明确；参数固定；时间/模型服务漂移仍为限制；无领先、跨厂商或来源模块普遍有效主张。

可信度：9/10。依据：固定计划、原始终态与一次重建；推广结论仍受固定cohort和服务窗口限制。
