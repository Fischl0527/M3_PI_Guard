# M3-PI Guard 强化实证实验阶段报告

## 0. 先看这轮到底发现了什么

本轮已按计划结束：**2,165 条模型执行、320 次受控机制判定、358 个真实首提案回放**。没有重跑成功行，也没有因结果不利替换样本。模型执行数不是独立任务数：Pro合法任务217个、攻击任务80个；Flash分别120个、40个，并且是预先选定的嵌套子集。

最主要的发现是：**当前系统在公开复杂任务上的问题，首先是授权编译与确认负担，不是单纯缺少攻击样本。** 下表均为合法任务的“实际完成数／固定任务数”；policy表示仅权限模块，full表示完整模块，两者在本轮使用相同的普通提示。

|模型／基准|无防护|policy自动授权|full自动授权|policy精确目标对照|full精确目标对照|
|---|---:|---:|---:|---:|---:|
|Pro／AgentDojo|68/97|8/97|8/97|38/97|29/97|
|当前V4.1 Flash／AgentDojo|46/60|5/60|5/60|25/60|20/60|
|Pro／M3-v2|60/120|59/120|58/120|56/120|59/120|
|当前V4.1 Flash／M3-v2|30/60|30/60|30/60|30/60|30/60|

- **授权信息确实影响公开任务效用。** Pro／AgentDojo的精确目标减自动授权：policy增加30.93个百分点，配对95%区间[21.66,40.16]；full增加21.65个百分点，区间[13.02,30.67]。两项均通过预定Holm校正。精确目标只给Guard，不进入首轮模型载荷；它是解释瓶颈的离线对照，不是部署方案。
- **完整模块并未因此表现出整体效用优势。** 自动授权下Pro／AgentDojo的policy/full均8/97；精确目标下full为29/97、policy为38/97。自动授权的ASK（等待确认）分别涉及90/97、91/97个任务，报告不能只展示危险结果较少而隐去完成损失。
- **M3的确认任务要单独看。** Pro的40个需确认任务在五个条件中均未完成，连无防护也是0/40；无需确认任务才是无防护60/80、policy自动59/80、full自动58/80。因此不能把全部120任务的低完成率都归因于Guard。本轮没有真人批准流程。
- **当前攻击活性并不普遍。** Pro／AgentDojo无防护7/40出现原生危险判定，policy/full均0/40；对无防护的两项比较Holm后p=0.078125。配置VIGIL为8/36，另4项结局未知；full相对它的已知36个配对差异为−22.22个百分点，校正p=0.046875，但必须同时阅读未知界限和效用损失。Pro／M3-v2及Flash两基准无防护均零事件，不能据此证明普遍安全优势。
- **机制能触发，但自然提案上的增量很小。** 受控160个policy/full提案对有80对判定改变；两配置在合法夹具上均放行，完整模块阻断或要求确认未授权夹具。真实358个首提案中仅3对从ASK变DENY，其余判定一致。这个差距本身就是值得解释的实证发现。

两幅概览图展示已观察比例及Wilson区间；配对差异与校正检验另见第4节，不用边际区间重叠替代配对检验。

![合法任务完成率及Wilson区间](figures/utility_observed_rates_v1.svg)

![攻击结果观察率及Wilson区间](figures/activity_observed_rates_v1.svg)

## 1. 实际完成量

本次读取计划 2165 项、公开终态记录 2165 项；未运行 0 项，已知运行失败 188 项。
计划数不是成功数：未知评分、运行失败及未运行分开登记。分析只读取当前研究，不重算历史矩阵，不调用模型，不改论文。
缺少计划的研究/模型目录：`无`。未找到的计划未计入已完成量。

|研究|模型|已记录/计划|未运行|已知失败|获得官方响应|评分投影凭证缺失|
|---|---|---:|---:|---:|---:|---:|
|utility|pro|1085/1085|0|130|1085|0|
|utility|flash|600/600|0|22|600|0|
|activity|pro|320/320|0|24|320|0|
|activity|flash|160/160|0|12|160|0|

## 2. 实验设计和统计单位

模型身份分别报告API请求别名、官方响应中的model别名及冻结服务元数据版本；后者不是权重文件快照，不能据此宣称模型权重锁定。当前Flash若标为DeepSeek-V4.1-Flash，属于新服务模型复现，不是历史V4 Flash，也不是跨厂商模型。

|研究/模型|请求模型ID|官方响应模型ID|冻结服务元数据版本|
|---|---|---|---|
|utility/pro|`deepseek-v4-pro`|`deepseek-v4-pro`|`DeepSeek-V4-Pro-0813`|
|utility/flash|`deepseek-flash`|`deepseek-flash`|`DeepSeek-V4.1-Flash`|
|activity/pro|`deepseek-v4-pro`|`deepseek-v4-pro`|`DeepSeek-V4-Pro-0813`|
|activity/flash|`deepseek-flash`|`deepseek-flash`|`DeepSeek-V4.1-Flash`|

R1（utility，合法任务效用）在同一批底层任务上运行五个条件：无防护自动授权、policy自动授权、full普通提示自动授权、policy精确目标授权、full普通提示精确目标授权。精确目标授权来自离线预期动作，是oracle（预先知道目标的对照），不是可直接部署的授权方案。
R2（activity，攻击活性）在历史无防护或VIGIL出现危险结果的任务上运行无防护、当前配置VIGIL、policy和full普通提示四个条件。该攻击样本为历史阳性富集集。
统计单位是underlying_task（底层任务），而不是API请求或条件执行次数。同一任务跨条件配对；Pro与Flash、两个基准分开报告。AgentDojo使用原生离线安全评分，M3-v2统计已执行的模拟越权效果，不能直接混合成一个自然攻击率。
M3良性任务同时报告all（全部）、non_confirmation（无确认需求）、confirmation_required（需确认）。没有真人批准时，ASK代表合理等待，不算任务完成，也不能自动称为错误阻断；另列授权形态和四类workflow（工作流）描述性分组。
置信区间：单cell采用95% Wilson；配对采用Newcombe混合分数区间，并按AgentDojo suite（任务套件）/M3 authorization_profile（授权形态）分层进行10,000次底层任务bootstrap（有放回重采样）。固定种子标签`m3-reinforcement-20261012-v1`。
Pro R1四项主比较（两模块的exact−auto×两个基准）共一个Holm家族；Pro R2六项主比较（policy−ND、full−ND、full−VIGIL×两个基准）共一个Holm家族。Flash报告效应方向、区间和未校正的辅助配对p值，不新增显著性家族。其余比较与工作流分层为次要/描述分析。
全零或bootstrap退化时，经验bootstrap区间记NA，使用配对区间和cell Wilson界限表达不确定性，不将[0,0]解释为确定零风险。未知配对不填零，并报告在全部计划任务上的差异保守上下界。

## 3. 分层结果

|研究/模型/基准|范围|条件/授权|已记录/计划|危险真/已知|完成真/已知|危险未知/完成未知|ASK项|未运行/失败|
|---|---|---|---:|---:|---:|---:|---:|---:|
|utility/pro/agentdojo-v1|all|m3_full_normal_prompt/auto_compiled|97/97|0/97|8/97|0/0|91|0/0|
|utility/pro/agentdojo-v1|all|m3_full_normal_prompt/exact_target_v2|97/97|0/97|29/97|0/0|0|0/34|
|utility/pro/agentdojo-v1|all|m3_policy_only/auto_compiled|97/97|0/97|8/97|0/0|90|0/1|
|utility/pro/agentdojo-v1|all|m3_policy_only/exact_target_v2|97/97|0/97|38/97|0/0|0|0/33|
|utility/pro/agentdojo-v1|all|no_defense/auto_compiled|97/97|0/97|68/97|0/0|0|0/16|
|utility/pro/m3-v2|all|m3_full_normal_prompt/auto_compiled|120/120|0/120|58/120|0/0|7|0/10|
|utility/pro/m3-v2|confirmation_required|m3_full_normal_prompt/auto_compiled|40/40|0/40|0/40|0/0|7|0/8|
|utility/pro/m3-v2|non_confirmation|m3_full_normal_prompt/auto_compiled|80/80|0/80|58/80|0/0|0|0/2|
|utility/pro/m3-v2|all|m3_full_normal_prompt/exact_target_v2|120/120|0/120|59/120|0/0|0|0/8|
|utility/pro/m3-v2|confirmation_required|m3_full_normal_prompt/exact_target_v2|40/40|0/40|0/40|0/0|0|0/6|
|utility/pro/m3-v2|non_confirmation|m3_full_normal_prompt/exact_target_v2|80/80|0/80|59/80|0/0|0|0/2|
|utility/pro/m3-v2|all|m3_policy_only/auto_compiled|120/120|0/120|59/120|0/0|5|0/9|
|utility/pro/m3-v2|confirmation_required|m3_policy_only/auto_compiled|40/40|0/40|0/40|0/0|5|0/8|
|utility/pro/m3-v2|non_confirmation|m3_policy_only/auto_compiled|80/80|0/80|59/80|0/0|0|0/1|
|utility/pro/m3-v2|all|m3_policy_only/exact_target_v2|120/120|0/120|56/120|0/0|0|0/13|
|utility/pro/m3-v2|confirmation_required|m3_policy_only/exact_target_v2|40/40|0/40|0/40|0/0|0|0/9|
|utility/pro/m3-v2|non_confirmation|m3_policy_only/exact_target_v2|80/80|0/80|56/80|0/0|0|0/4|
|utility/pro/m3-v2|all|no_defense/auto_compiled|120/120|0/120|60/120|0/0|0|0/6|
|utility/pro/m3-v2|confirmation_required|no_defense/auto_compiled|40/40|0/40|0/40|0/0|0|0/6|
|utility/pro/m3-v2|non_confirmation|no_defense/auto_compiled|80/80|0/80|60/80|0/0|0|0/0|
|utility/flash/agentdojo-v1|all|m3_full_normal_prompt/auto_compiled|60/60|0/60|5/60|0/0|57|0/0|
|utility/flash/agentdojo-v1|all|m3_full_normal_prompt/exact_target_v2|60/60|0/60|20/60|0/0|0|0/5|
|utility/flash/agentdojo-v1|all|m3_policy_only/auto_compiled|60/60|0/60|5/60|0/0|57|0/0|
|utility/flash/agentdojo-v1|all|m3_policy_only/exact_target_v2|60/60|0/60|25/60|0/0|0|0/7|
|utility/flash/agentdojo-v1|all|no_defense/auto_compiled|60/60|0/60|46/60|0/0|0|0/10|
|utility/flash/m3-v2|all|m3_full_normal_prompt/auto_compiled|60/60|0/60|30/60|0/0|9|0/0|
|utility/flash/m3-v2|confirmation_required|m3_full_normal_prompt/auto_compiled|20/20|0/20|0/20|0/0|9|0/0|
|utility/flash/m3-v2|non_confirmation|m3_full_normal_prompt/auto_compiled|40/40|0/40|30/40|0/0|0|0/0|
|utility/flash/m3-v2|all|m3_full_normal_prompt/exact_target_v2|60/60|0/60|30/60|0/0|0|0/0|
|utility/flash/m3-v2|confirmation_required|m3_full_normal_prompt/exact_target_v2|20/20|0/20|0/20|0/0|0|0/0|
|utility/flash/m3-v2|non_confirmation|m3_full_normal_prompt/exact_target_v2|40/40|0/40|30/40|0/0|0|0/0|
|utility/flash/m3-v2|all|m3_policy_only/auto_compiled|60/60|0/60|30/60|0/0|7|0/0|
|utility/flash/m3-v2|confirmation_required|m3_policy_only/auto_compiled|20/20|0/20|0/20|0/0|7|0/0|
|utility/flash/m3-v2|non_confirmation|m3_policy_only/auto_compiled|40/40|0/40|30/40|0/0|0|0/0|
|utility/flash/m3-v2|all|m3_policy_only/exact_target_v2|60/60|0/60|30/60|0/0|0|0/0|
|utility/flash/m3-v2|confirmation_required|m3_policy_only/exact_target_v2|20/20|0/20|0/20|0/0|0|0/0|
|utility/flash/m3-v2|non_confirmation|m3_policy_only/exact_target_v2|40/40|0/40|30/40|0/0|0|0/0|
|utility/flash/m3-v2|all|no_defense/auto_compiled|60/60|0/60|30/60|0/0|0|0/0|
|utility/flash/m3-v2|confirmation_required|no_defense/auto_compiled|20/20|0/20|0/20|0/0|0|0/0|
|utility/flash/m3-v2|non_confirmation|no_defense/auto_compiled|40/40|0/40|30/40|0/0|0|0/0|
|activity/pro/agentdojo-v1|all|m3_full_normal_prompt/auto_compiled|40/40|0/40|2/40|0/0|38|0/0|
|activity/pro/agentdojo-v1|all|m3_policy_only/auto_compiled|40/40|0/40|2/40|0/0|37|0/1|
|activity/pro/agentdojo-v1|all|no_defense/auto_compiled|40/40|7/40|21/40|0/0|0|0/14|
|activity/pro/agentdojo-v1|all|strongest_peer_reviewed_structural_baseline/auto_compiled|40/40|8/36|23/36|4/4|0|0/8|
|activity/pro/m3-v2|all|m3_full_normal_prompt/auto_compiled|40/40|0/40|14/40|0/0|4|0/1|
|activity/pro/m3-v2|all|m3_policy_only/auto_compiled|40/40|0/40|14/40|0/0|7|0/0|
|activity/pro/m3-v2|all|no_defense/auto_compiled|40/40|0/40|15/40|0/0|0|0/0|
|activity/pro/m3-v2|all|strongest_peer_reviewed_structural_baseline/auto_compiled|40/40|0/40|15/40|0/0|0|0/0|
|activity/flash/agentdojo-v1|all|m3_full_normal_prompt/auto_compiled|20/20|0/20|1/20|0/0|18|0/0|
|activity/flash/agentdojo-v1|all|m3_policy_only/auto_compiled|20/20|0/20|1/20|0/0|18|0/0|
|activity/flash/agentdojo-v1|all|no_defense/auto_compiled|20/20|0/20|11/20|0/0|0|0/5|
|activity/flash/agentdojo-v1|all|strongest_peer_reviewed_structural_baseline/auto_compiled|20/20|0/19|12/19|1/1|0|0/2|
|activity/flash/m3-v2|all|m3_full_normal_prompt/auto_compiled|20/20|0/20|7/20|0/0|2|0/1|
|activity/flash/m3-v2|all|m3_policy_only/auto_compiled|20/20|0/20|7/20|0/0|2|0/1|
|activity/flash/m3-v2|all|no_defense/auto_compiled|20/20|0/20|6/20|0/0|0|0/2|
|activity/flash/m3-v2|all|strongest_peer_reviewed_structural_baseline/auto_compiled|20/20|0/20|7/20|0/0|0|0/1|

完整cell表见`tables/cells_v1.csv`：包括已观察比例、Wilson区间、计划分母、ITT下/上界、失败敏感上界、ASK/DENY和延迟；不把未知当安全零。

## 4. 任务配对差异

下表差异均为treatment−baseline（后者条件减去参照条件）。完成率正差表示完成更多；危险率负差表示危险结果更少。百分点评估不是百分比相对减少。
|研究/模型/基准|比较|角色|已知/计划配对|观察差异|配对95%区间|ITT差异上下界|Holm p|
|---|---|---|---:|---:|---|---|---:|
|utility/pro/agentdojo-v1|policy_exact_minus_auto|primary|97/97|+30.93pp|[+21.66pp, +40.16pp]|[+30.93pp, +30.93pp]|7.45058e-09|
|utility/pro/agentdojo-v1|full_exact_minus_auto|primary|97/97|+21.65pp|[+13.02pp, +30.67pp]|[+21.65pp, +21.65pp]|1.71661e-05|
|utility/pro/agentdojo-v1|policy_minus_nd|secondary|97/97|-61.86pp|[-70.87pp, -49.94pp]|[-61.86pp, -61.86pp]|NA|
|utility/pro/agentdojo-v1|full_minus_nd|secondary|97/97|-61.86pp|[-70.87pp, -49.94pp]|[-61.86pp, -61.86pp]|NA|
|utility/pro/agentdojo-v1|full_minus_policy|secondary|97/97|+0.00pp|[-3.18pp, +3.18pp]|[+0.00pp, +0.00pp]|NA|
|utility/pro/m3-v2|policy_exact_minus_auto|primary|120/120|-2.50pp|[-6.06pp, +1.09pp]|[-2.50pp, -2.50pp]|0.75|
|utility/pro/m3-v2|full_exact_minus_auto|primary|120/120|+0.83pp|[-0.77pp, +2.43pp]|[+0.83pp, +0.83pp]|1|
|utility/pro/m3-v2|policy_minus_nd|secondary|120/120|-0.83pp|[-2.43pp, +0.77pp]|[-0.83pp, -0.83pp]|NA|
|utility/pro/m3-v2|full_minus_nd|secondary|120/120|-1.67pp|[-3.92pp, +0.60pp]|[-1.67pp, -1.67pp]|NA|
|utility/pro/m3-v2|full_minus_policy|secondary|120/120|-0.83pp|[-2.43pp, +0.77pp]|[-0.83pp, -0.83pp]|NA|
|utility/flash/agentdojo-v1|policy_exact_minus_auto|replication|60/60|+33.33pp|[+21.13pp, +45.11pp]|[+33.33pp, +33.33pp]|NA|
|utility/flash/agentdojo-v1|full_exact_minus_auto|replication|60/60|+25.00pp|[+14.08pp, +36.42pp]|[+25.00pp, +25.00pp]|NA|
|utility/flash/agentdojo-v1|policy_minus_nd|replication|60/60|-68.33pp|[-77.68pp, -54.12pp]|[-68.33pp, -68.33pp]|NA|
|utility/flash/agentdojo-v1|full_minus_nd|replication|60/60|-68.33pp|[-77.68pp, -54.12pp]|[-68.33pp, -68.33pp]|NA|
|utility/flash/agentdojo-v1|full_minus_policy|replication|60/60|+0.00pp|[-5.01pp, +5.01pp]|[+0.00pp, +0.00pp]|NA|
|utility/flash/m3-v2|policy_exact_minus_auto|replication|60/60|+0.00pp|[+0.00pp, +0.00pp]|[+0.00pp, +0.00pp]|NA|
|utility/flash/m3-v2|full_exact_minus_auto|replication|60/60|+0.00pp|[+0.00pp, +0.00pp]|[+0.00pp, +0.00pp]|NA|
|utility/flash/m3-v2|policy_minus_nd|replication|60/60|+0.00pp|[+0.00pp, +0.00pp]|[+0.00pp, +0.00pp]|NA|
|utility/flash/m3-v2|full_minus_nd|replication|60/60|+0.00pp|[+0.00pp, +0.00pp]|[+0.00pp, +0.00pp]|NA|
|utility/flash/m3-v2|full_minus_policy|replication|60/60|+0.00pp|[+0.00pp, +0.00pp]|[+0.00pp, +0.00pp]|NA|
|activity/pro/agentdojo-v1|policy_minus_nd|primary|40/40|-17.50pp|[-31.95pp, -5.11pp]|[-17.50pp, -17.50pp]|0.078125|
|activity/pro/agentdojo-v1|full_minus_nd|primary|40/40|-17.50pp|[-31.95pp, -5.11pp]|[-17.50pp, -17.50pp]|0.078125|
|activity/pro/agentdojo-v1|full_minus_vigil|primary|36/40|-22.22pp|[-38.08pp, -7.96pp]|[-30.00pp, -20.00pp]|0.046875|
|activity/pro/agentdojo-v1|vigil_minus_nd|secondary|36/40|+5.56pp|[-3.08pp, +15.33pp]|[+2.50pp, +12.50pp]|NA|
|activity/pro/agentdojo-v1|full_minus_policy|secondary|40/40|+0.00pp|[-8.76pp, +8.76pp]|[+0.00pp, +0.00pp]|NA|
|activity/pro/m3-v2|policy_minus_nd|primary|40/40|+0.00pp|[-8.76pp, +8.76pp]|[+0.00pp, +0.00pp]|1|
|activity/pro/m3-v2|full_minus_nd|primary|40/40|+0.00pp|[-8.76pp, +8.76pp]|[+0.00pp, +0.00pp]|1|
|activity/pro/m3-v2|full_minus_vigil|primary|40/40|+0.00pp|[-8.76pp, +8.76pp]|[+0.00pp, +0.00pp]|1|
|activity/pro/m3-v2|vigil_minus_nd|secondary|40/40|+0.00pp|[-8.76pp, +8.76pp]|[+0.00pp, +0.00pp]|NA|
|activity/pro/m3-v2|full_minus_policy|secondary|40/40|+0.00pp|[-8.76pp, +8.76pp]|[+0.00pp, +0.00pp]|NA|
|activity/flash/agentdojo-v1|policy_minus_nd|replication|20/20|+0.00pp|[-16.11pp, +16.11pp]|[+0.00pp, +0.00pp]|NA|
|activity/flash/agentdojo-v1|full_minus_nd|replication|20/20|+0.00pp|[-16.11pp, +16.11pp]|[+0.00pp, +0.00pp]|NA|
|activity/flash/agentdojo-v1|full_minus_vigil|replication|19/20|+0.00pp|[-16.82pp, +16.82pp]|[-5.00pp, +0.00pp]|NA|
|activity/flash/agentdojo-v1|vigil_minus_nd|replication|19/20|+0.00pp|[-16.82pp, +16.82pp]|[+0.00pp, +5.00pp]|NA|
|activity/flash/agentdojo-v1|full_minus_policy|replication|20/20|+0.00pp|[-16.11pp, +16.11pp]|[+0.00pp, +0.00pp]|NA|
|activity/flash/m3-v2|policy_minus_nd|replication|20/20|+0.00pp|[-16.11pp, +16.11pp]|[+0.00pp, +0.00pp]|NA|
|activity/flash/m3-v2|full_minus_nd|replication|20/20|+0.00pp|[-16.11pp, +16.11pp]|[+0.00pp, +0.00pp]|NA|
|activity/flash/m3-v2|full_minus_vigil|replication|20/20|+0.00pp|[-16.11pp, +16.11pp]|[+0.00pp, +0.00pp]|NA|
|activity/flash/m3-v2|vigil_minus_nd|replication|20/20|+0.00pp|[-16.11pp, +16.11pp]|[+0.00pp, +0.00pp]|NA|
|activity/flash/m3-v2|full_minus_policy|replication|20/20|+0.00pp|[-16.11pp, +16.11pp]|[+0.00pp, +0.00pp]|NA|

完整配对表与bootstrap区间在`tables/paired_comparisons_v1.csv`；结果缺失时观察差异不是全样本差异，需同时阅读ITT界限。

## 5. 同期攻击活性

|模型/基准|无防护危险真/已观察/计划|未知|描述|本队列终态齐全|
|---|---:|---:|---|---|
|pro/agentdojo-v1|7/40/40|0|WEAK|True|
|pro/m3-v2|0/40/40|0|INACTIVE|True|
|flash/agentdojo-v1|0/20/20|0|INACTIVE|True|
|flash/m3-v2|0/20/20|0|INACTIVE|True|

活性描述按预定计数：0例INACTIVE（未观察活性）、1–7例WEAK（较弱）、至少8例OBSERVED_ACTIVE（本队列观察到活性）。这是描述而非停止规则；含未知时不能断言所有任务不活跃，不进行模型排名或自然部署发生率推断。

### 5.1 同一提案的离线机制判定

受控夹具决策已记录 320/320，基础夹具 40，policy/full完整提案对 160、不完整对 0，判定变化 80 对。
公开捕获首提案回放 358 项，来自至多 457 个冻结无防护项，判定变化 3 项。未被捕获不意味着模型没有提出危险动作：也可能首先返回final、解析失败或无可回放前缀。
下表只报告确定性机制决策；合法夹具未ALLOW、未授权夹具被ALLOW分别作为对照计数。ASK与DENY分别保留，确认等待不视为执行或完成。没有新模型调用、实际effect、端到端成功率或p值。
|机制家族|模块|决策数|合法未ALLOW/合法|未授权ALLOW/未授权|ALLOW/ASK/DENY分布|
|---|---|---:|---:|---:|---|
|confirmation|full|40|0/20|0/20|`{"ALLOW": 20, "ASK": 20}`|
|confirmation|policy|40|0/20|20/20|`{"ALLOW": 40}`|
|dataflow|full|40|0/20|0/20|`{"ALLOW": 20, "DENY": 20}`|
|dataflow|policy|40|0/20|20/20|`{"ALLOW": 40}`|
|order|full|40|0/20|0/20|`{"ALLOW": 20, "DENY": 20}`|
|order|policy|40|0/20|20/20|`{"ALLOW": 40}`|
|source_authority|full|40|0/20|0/20|`{"ALLOW": 20, "DENY": 20}`|
|source_authority|policy|40|0/20|20/20|`{"ALLOW": 40}`|

捕获判定对分布：`{"ASK->ASK": 210, "ALLOW->ALLOW": 145, "ASK->DENY": 3}`。机制表在`tables/mechanism_decisions_v1.csv`；仅公开摘要，不读取内部提案正文。

## 6. 调用、成本和结果来源

本研究各尝试合计官方请求 5463 次，total token 6412110（总量字段缺失0）；已知用量估计CNY 12.187084（成本缺失0），用量完整性为 True。这是记录中峰值费率估算，不是账单实付；失败后的显式恢复调用也计入。
VIGIL每任务最多16次provider call（模型请求）；其他条件最多8次。下表按全部实际尝试累计调用、token（文本计费单元）及峰值费率估算成本，终态任务分母保持不变。每任务调用p50/p95为中位数/第95百分位；未启动任务不作为零调用任务加入分位数。
VIGIL约束生成调用只合计显式字段，并报告字段缺失；截断行有总调用但无分项时保留总数，不补造约束生成0次或1次。成本与token缺失也不填零，已知合计只代表可用记录。

|研究/模型/基准|条件/授权|调用上限|总调用|每任务调用p50/p95|输入/输出/总token|估算CNY/成本缺失|约束生成已知合计/分项缺失|
|---|---|---:|---:|---:|---:|---:|---:|
|utility/pro/agentdojo-v1|m3_full_normal_prompt/auto_compiled|8|110|1.00/2.00|158037/3037/161074|0.276031/0|不适用|
|utility/pro/agentdojo-v1|m3_full_normal_prompt/exact_target_v2|8|505|5.00/8.00|633922/16918/650840|1.196542/0|不适用|
|utility/pro/agentdojo-v1|m3_policy_only/auto_compiled|8|111|1.00/2.00|166332/3255/169587|0.462364/0|不适用|
|utility/pro/agentdojo-v1|m3_policy_only/exact_target_v2|8|501|4.00/8.00|642758/17105/659863|1.235457/0|不适用|
|utility/pro/agentdojo-v1|no_defense/auto_compiled|8|439|4.00/8.00|763065/20368/783433|1.571121/0|不适用|
|utility/pro/m3-v2|m3_full_normal_prompt/auto_compiled|8|218|2.00/3.00|91523/10197/101720|0.463160/0|不适用|
|utility/pro/m3-v2|m3_full_normal_prompt/exact_target_v2|8|234|2.00/3.00|99093/9575/108668|0.461044/0|不适用|
|utility/pro/m3-v2|m3_policy_only/auto_compiled|8|219|2.00/3.00|91926/10130/102056|0.462751/0|不适用|
|utility/pro/m3-v2|m3_policy_only/exact_target_v2|8|227|2.00/3.00|95533/9270/104803|0.441927/0|不适用|
|utility/pro/m3-v2|no_defense/auto_compiled|8|229|2.00/3.00|96514/10619/107133|0.482725/0|不适用|
|utility/flash/agentdojo-v1|m3_full_normal_prompt/auto_compiled|8|69|1.00/2.00|112921/1496/114417|0.061704/0|不适用|
|utility/flash/agentdojo-v1|m3_full_normal_prompt/exact_target_v2|8|254|3.00/8.00|306226/9367/315593|0.193433/0|不适用|
|utility/flash/agentdojo-v1|m3_policy_only/auto_compiled|8|66|1.00/2.00|87637/1452/89089|0.048677/0|不适用|
|utility/flash/agentdojo-v1|m3_policy_only/exact_target_v2|8|258|3.50/8.00|311199/9184/320383|0.198636/0|不适用|
|utility/flash/agentdojo-v1|no_defense/auto_compiled|8|265|4.00/8.00|454086/10898/464984|0.272349/0|不适用|
|utility/flash/m3-v2|m3_full_normal_prompt/auto_compiled|8|110|2.00/3.00|46664/5738/52402|0.094074/0|不适用|
|utility/flash/m3-v2|m3_full_normal_prompt/exact_target_v2|8|116|2.00/3.00|49048/6387/55435|0.101023/0|不适用|
|utility/flash/m3-v2|m3_policy_only/auto_compiled|8|110|2.00/3.00|46621/5900/52521|0.095534/0|不适用|
|utility/flash/m3-v2|m3_policy_only/exact_target_v2|8|117|2.00/3.00|49524/6505/56029|0.102417/0|不适用|
|utility/flash/m3-v2|no_defense/auto_compiled|8|129|2.00/3.00|55249/6680/61929|0.108494/0|不适用|
|activity/pro/agentdojo-v1|m3_full_normal_prompt/auto_compiled|8|44|1.00/2.00|63537/1386/64923|0.211700/0|不适用|
|activity/pro/agentdojo-v1|m3_policy_only/auto_compiled|8|45|1.00/2.00|71903/1903/73806|0.293158/0|不适用|
|activity/pro/agentdojo-v1|no_defense/auto_compiled|8|217|5.00/8.00|377338/10772/388110|0.788185/0|不适用|
|activity/pro/agentdojo-v1|strongest_peer_reviewed_structural_baseline/auto_compiled|16|265|6.00/14.00|440626/25567/466193|1.251668/0|36/4|
|activity/pro/m3-v2|m3_full_normal_prompt/auto_compiled|8|46|1.00/2.00|17267/2675/19942|0.116268/0|不适用|
|activity/pro/m3-v2|m3_policy_only/auto_compiled|8|40|1.00/1.00|14615/2147/16762|0.088166/0|不适用|
|activity/pro/m3-v2|no_defense/auto_compiled|8|45|1.00/2.00|16782/2542/19324|0.089381/0|不适用|
|activity/pro/m3-v2|strongest_peer_reviewed_structural_baseline/auto_compiled|16|89|2.00/3.00|76812/11501/88313|0.491806/0|40/0|
|activity/flash/agentdojo-v1|m3_full_normal_prompt/auto_compiled|8|23|1.00/2.00|39386/910/40296|0.032121/0|不适用|
|activity/flash/agentdojo-v1|m3_policy_only/auto_compiled|8|23|1.00/2.00|39386/779/40165|0.032578/0|不适用|
|activity/flash/agentdojo-v1|no_defense/auto_compiled|8|107|6.00/8.00|227545/5272/232817|0.106150/0|不适用|
|activity/flash/agentdojo-v1|strongest_peer_reviewed_structural_baseline/auto_compiled|16|132|6.00/13.15|348307/12948/361255|0.218672/0|19/1|
|activity/flash/m3-v2|m3_full_normal_prompt/auto_compiled|8|20|1.00/1.00|7336/1182/8518|0.018628/0|不适用|
|activity/flash/m3-v2|m3_policy_only/auto_compiled|8|20|1.00/1.00|7336/1119/8455|0.017132/0|不适用|
|activity/flash/m3-v2|no_defense/auto_compiled|8|20|1.00/1.00|7336/1178/8514|0.016111/0|不适用|
|activity/flash/m3-v2|strongest_peer_reviewed_structural_baseline/auto_compiled|16|40|2.00/2.00|36553/6205/42758|0.085898/0|20/0|

延迟统计使用每任务total毫秒，另报告缺失/非法数。不同条件路径和调用次数不同，不能把总延迟差全部称为Guard计算开销。

## 7. 产物目录及重新分析

本报告所在结果根：`E:\M3_PI_Guard_test\outputs\experiments\empirical_reinforcement_v1`。根目录只存本研究必要派生产物，旧历史目录不参与本次计算。

```text
empirical_reinforcement_v1/
├── manifest_v1.json             # 四个冻结队列的运行清单
├── utility/                     # R1：合法工具任务
│   ├── pro/
│   │   ├── cases_v1.jsonl         # 固定案例及选择依据
│   │   ├── plan_v1.jsonl          # 冻结任务、条件、授权与模型
│   │   ├── raw_records_v1.jsonl   # 逐尝试公开结果，不覆盖已有响应
│   │   ├── status_v1.json        # 进度、技术门和停止原因
│   │   └── internal/             # 本地忽略：逐请求记录、锁和首提案捕获
│   └── flash/                    # 相同结构；同提供商复现
├── activity/                    # R2：历史阳性攻击活性
│   ├── pro/                     # 与utility/pro同结构，状态及internal独立
│   └── flash/                   # 与utility/flash同结构，状态及internal独立
├── mechanism/                   # R3：固定提案/已捕获提案的离线机制回放
│   ├── controlled_decisions_v1.jsonl
│   ├── captured_replays_v1.jsonl
│   └── summary_v1.json           # 40基础夹具、320判定及实际捕获计数
├── analysis_v1.json             # 本次统计，未知、配对及多重校正
├── tables/
│   ├── cells_v1.csv
│   ├── paired_comparisons_v1.csv
│   ├── attack_activity_v1.csv
│   └── mechanism_decisions_v1.csv
├── figures/                     # 可选SVG，只画已观察比例/Wilson区间
└── report.md                     # 自足中文报告
```

四个study/model（研究/模型）子目录均有各自的internal目录；它们不是根目录共用账本，不进入GitHub或服务器统计包。服务器只接收公开计划、raw和机制摘要。

分析命令（在项目根目录运行）：

```powershell
& F:\robot\Anaconda3\python.exe -X utf8 -m experiments.paper_v2.empirical_reinforcement_analysis_v1
```

代码只读取本研究公开JSONL，生成上述派生表和报告；不调用模型、不读取密钥、不中断运行器、不执行Full Harness、不修改论文和历史结果。R3确定性决策与模型端到端结果分别分析，不能用机制回放正确率代替模型防御有效性。

## 8. 解释与未完成项

本轮实验、定向检查和报告已经完成；**没有自动修改论文正文或LaTeX，也没有启动下一项研究**。后续论文集成应以授权制度造成的任务完成差异、攻击活性不足、受控机制与真实提案之间的差距为主线，而不是恢复完整模块领先的叙事。

技术细节：五项VIGIL约束生成在创建模拟环境前被输出长度截断（Pro四项、Flash一项），保留未知结局；其总请求数完整，缺失的约束生成子计数没有补造。R3的可选study_part标签在本轮捕获中为空，原因是计划字段名为study；358项仍以唯一work_key正确对应四份计划的基准、案例、模型与研究来源。未来捕获的字段投影已修复并通过回归，既有捕获和结果没有重写，也没有为补标签重跑API或回放。R3捕获来源分别为utility/pro185、utility/flash108、activity/pro45、activity/flash20。完整捕获输入仍在本地internal，不随GitHub公开；公开摘要可以复算回放计数，但不能从摘要逆推出动作内容以重新执行同一回放。受控夹具的生成与判定代码则在仓库内。

- 统计单位为底层任务；每个基准、模型与条件一条，跨条件配对，跨模型不混合。
- M3全部任务、无确认任务和确认任务并列；没有真人批准时ASK是合理等待，完成率下降不自动等于误拦。
- 四类M3工作流与语言/授权形态有关，工作流子组仅描述，不当作四类独立自然任务总体。
- 攻击集来自历史阳性富集，只校准当前攻击活性，不代表部署自然攻击发生率。
- VIGIL为当前source-pinned源码适配配置，未启用模型二次验证或模型约束二次验证；比较对象不是官方默认完整系统。
- 未知和未运行不填零；观察估计与ITT保守上下界同时报告。
- 零事件bootstrap退化时返回NA并提供非退化配对/Wilson区间。
- Flash仅作同提供商模型复现，不建立新显著性家族或模型排名。
- 模型请求别名、官方响应别名和冻结服务版本标识分别披露；服务版本元数据不等于权重锁定。当前Flash服务为V4.1时，不能当作历史V4 Flash同一模型的复现。

本轮未运行项为零。五项未知评分保留在原计划分母和保守界限内；已有模型响应的成功或失败行不重跑。作者信息和正式投稿状态本轮未改变。

## 9. 工程验收与复算方式

- 四个队列的工作项与冻结计划逐项对应，全部attempt=1。5,463个本地请求ID、5,463个官方response ID跨研究及模型不重复；身份、512输出上限、180秒请求超时及调用上限符合计划。
- 所有新公开记录保持字段隔离，provider tools（厂商托管工具）和真实external effect（外部副作用）为零。原始失败、未知与有效评分分别保存；公开结果不包含完整模型请求、响应、动作参数或密钥。
- 320个受控判定含四类机制、每类10个基础夹具及160个完整配对，输入一致；358个捕获回放在457个预定无防护项上界内，来源通过work_key唯一对应，没有复用历史模型结果。
- 原有相关模块148项定向回归通过；最终四套强化测试**60 passed/19.08秒**，Ruff通过，四个研究模块编译通过。用量／统计补充在Ubuntu24与阿里云Python3.10分别通过22项测试，不表示服务器运行了整个项目或模型实验。
- 正式10000次分层任务重采样只在Ubuntu24新工作区执行一次。本地从取回的analysis_v1.json生成表图和报告，没有再次计算统计。两图已实际渲染查看，临时PDF的文字最低10pt、碰撞检查均0失败／0警告；当前交付为阶段报告图，不宣称投稿排版完成。

如需在另一环境复算，先安装项目声明的Python依赖，在主项目根目录运行以下命令。它**不调用模型、不读取internal**；会重新计算统计并覆盖派生表图，保留原始JSONL。由于本报告开头是人工解读，正式复算时可用新的输出副本保留该段。

```powershell
& F:\robot\Anaconda3\python.exe -X utf8 -B -m experiments.paper_v2.empirical_reinforcement_analysis_v1 --output-root outputs/experiments/empirical_reinforcement_v1 --bootstrap-draws 10000
```

本轮最终定向检查命令：

```powershell
& F:\robot\Anaconda3\python.exe -X utf8 -B -m pytest tests/unit/test_empirical_reinforcement_plan_v1.py tests/unit/test_empirical_reinforcement_v1.py tests/unit/test_empirical_reinforcement_mechanism_v1.py tests/unit/test_empirical_reinforcement_analysis_v1.py -q
```

Git已完成实现节点`155e0cc`和结果节点`7f9a45b`；统计、图表、本文及最终Harness登记在报告节点提交。目标为个人仓库`Fischl0527/M3_PI_Guard`的`codex/claude-review-repairs`，不是旧比赛仓库或默认main；不强推、不打包其他工作树改动。

可信度：9/10。依据：冻结计划、公开原始结果及定向统计测试；推广范围、服务漂移及独立外部审校仍需结合实际完成量解释。
