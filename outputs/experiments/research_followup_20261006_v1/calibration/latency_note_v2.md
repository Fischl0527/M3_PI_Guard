# 同期校准延迟统计修正

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Mode: existing-result measurement correction
- Date: 2026-10-06
- Status: analyzed; focused code tests verified, no new model experiment

原分析只接受标量，而runtime写入total/model/guard/tool对象，导致原表延迟列空。读取对象total并兼容旧标量；缺失、非法及各分项分别记数，绝不补零。

480/480条已有记录：总延迟可用476，缺失4，非法0。
原raw_records.jsonl、analysis.json、cells.csv及安全/完成推断均未改写；没有模型请求、bootstrap或配对检验重算。

|基准/类型|条件|可用/记录|缺失|非法|任务总p50（秒）|任务总p95（秒）|
|---|---|---:|---:|---:|---:|---:|
|agentdojo-v1/attack|m3_full_normal_prompt|30/30|0|0|1.192|2.214|
|agentdojo-v1/attack|m3_policy_only|30/30|0|0|1.360|4.744|
|agentdojo-v1/attack|no_defense|30/30|0|0|7.667|12.125|
|agentdojo-v1/attack|strongest_peer_reviewed_structural_baseline|28/30|2|0|10.350|20.995|
|agentdojo-v1/benign_tool|m3_full_normal_prompt|30/30|0|0|1.279|3.003|
|agentdojo-v1/benign_tool|m3_policy_only|30/30|0|0|1.209|3.029|
|agentdojo-v1/benign_tool|no_defense|30/30|0|0|5.083|11.575|
|agentdojo-v1/benign_tool|strongest_peer_reviewed_structural_baseline|28/30|2|0|8.145|20.291|
|m3-v2/attack|m3_full_normal_prompt|30/30|0|0|1.528|2.529|
|m3-v2/attack|m3_policy_only|30/30|0|0|1.438|2.471|
|m3-v2/attack|no_defense|30/30|0|0|1.500|2.564|
|m3-v2/attack|strongest_peer_reviewed_structural_baseline|30/30|0|0|4.091|5.889|
|m3-v2/benign_tool|m3_full_normal_prompt|30/30|0|0|2.613|4.201|
|m3-v2/benign_tool|m3_policy_only|30/30|0|0|2.472|3.953|
|m3-v2/benign_tool|no_defense|30/30|0|0|2.695|3.899|
|m3-v2/benign_tool|strongest_peer_reviewed_structural_baseline|30/30|0|0|5.153|6.226|

输出：latency_analysis_v2.json（分项、分母、格式），tables/latency_v2.csv（分层cell），latency_note_v2.md（本文）。原analysis.json是历史一次分析；延迟列请使用本v2派生表。

这是runtime报告的任务总延迟，不是单请求延迟。分项之和不保证等于total：还包括调度、约束生成或其他开销。各条件任务路径与调用次数不同，不能把差异都归因于Guard计算成本；缺失不能填成零延迟。

11类统计误区逐项检查：分层表避免混合方向误读；不作群体到个体推广；富集选择不作部署基率；不调整碰撞变量；不忽略基率；不从历史前后差推修复增益；全部480保留且4缺失明确；没有挑显著结果；只修事先识别的total读取而非事后变换；不同任务路径的相关延迟不称Guard成本因果；不作反向因果解释。原推断不重做；本表只有描述性分位数，无新显著性或领先结论。

可信度：9/10。依据：已有公开raw中的实际延迟字段与本次定向修复；当前服务吞吐和部署性能未验证。
