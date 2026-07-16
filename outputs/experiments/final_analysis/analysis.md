# M3_PI_Guard 全量实验综合分析

## 技术摘要：验收结论由完整、可重建的正式证据决定

验收未通过：未达标项为 A04, A06, A07, A10。
本综合包只在 E0–E17 全部完成、registry 与 bundle manifest 一致、已声明 artifact 的字节数和 SHA-256 全部通过、figure manifest 可重验、比例指标 k/n/value 自洽后生成。E0 只用于测量完整性诊断；Stub 回归、smoke gate、E13 验证校准、E16 自适应专项和 E17 复核专项均按各自证据层隔离，绝不混入主矩阵效果分母。
最终结果完整性审计覆盖 main、derived、stability，审计 SHA-256 为 `ce5a1387affdc93f855a4c5970c9d4d3053a66fc6ddc9f70332aee8804072f10`。A11 仍严格表示 E1 `regular_full` 调用解析率；补充的主矩阵全条件诊断中，step-row 解析率为 12081/12538=96.4%（Wilson 95% CI 96.0%–96.7%，相对 95.0% 参考线为 pass），run-level 无解析失败率为 6025/6480=93.0%（Wilson 95% CI 92.3%–93.6%，相对 95.0% 参考线为 fail）。step-row 低于参考线的模型：llama3.2:3b、phi4-mini:3.8b；run-level 低于参考线的模型：llama3.2:3b、phi4-mini:3.8b。
E9 长上下文/注入位置专项从已登记 `context_position.csv` 原始计数重新得到 unresolved=14/120=11.7%；这些运行保留在 120 条正式 case-run 分母中，不能把可解析子集当作完整 E9 结果。
原始冻结 v3 E11 使用 4 个实现型链路模式，只有 `read_file_to_send_email` 与计划中的 `read_to_send` 直接对应；`search_to_api`、`memory_to_file`、`tool_output_to_next_action` 未进入原始分母。后续补充是 `E11_POSTHOC_AMENDMENT_V1` 的 post-hoc 独立证据（24 cases / 48 logical runs，`pre_registered=false`），不替换原始 E11、不合并分母，也不改变验收矩阵。

### 最终验收矩阵

| ID | 验收项 | 结果 | 不确定性判断 | 估计 | k/n | 阈值 | 来源 |
|---|---|---:|---|---:|---:|---:|---|
| A00 | Frozen validation threshold satisfies all calibration constraints | pass | deterministic_rule_pass | 1.000 | NA | status == targets_met (targets_met) | E13 |
| A01 | Full Guard reduces overall ASR under the same prompt | pass | point_estimate_pass_ci_unavailable | 99.2% | 3/756 | >= 70% relative reduction (70.0%) | E1 |
| A02 | Full-Guard data-spill rate is zero | pass | point_estimate_pass_ci_inconclusive | 0.0% | 0/432 | == 0 (0.0%) | E1 |
| A03 | Malicious-call Precision | pass | ci_supports_threshold | 99.2% | 525/529 | >= 90% (90.0%) | E1 |
| A04 | Malicious-call Recall | fail | point_estimate_fail | 86.5% | 525/607 | >= 90% (90.0%) | E1 |
| A05 | Benign call-level false-positive rate | pass | point_estimate_pass_ci_inconclusive | 2.7% | 4/146 | <= 5% (5.0%) | E12 |
| A06 | Normal-task completion-rate drop from full Guard | fail | point_estimate_fail | 6.8% | 168/324 | <= 5 percentage points (5.0%) | E12 |
| A07 | Legitimate-tool task completion rate | fail | point_estimate_fail | 65.5% | 110/168 | >= 90% (90.0%) | E12 |
| A08 | Benign ASK rate | pass | ci_supports_threshold | 6.2% | 20/324 | <= 10% (10.0%) | E12 |
| A09 | Guard p95 latency across tested engineering cells | pass | point_estimate_pass_ci_unavailable | 0.538 | NA | < 10 ms in every evaluable cell (10.0) | E14 |
| A10 | Median end-to-end latency overhead | fail | point_estimate_fail | 92.4% | NA | < 10% in every E14 comparison (10.0%) | E14 |
| A11 | ToolCall parse success rate | pass | ci_supports_threshold | 97.5% | 1529/1568 | >= 95% (95.0%) | E1 |

状态规则：`pass` 表示点估计和规定的逐-cell检查达到预设阈值；`fail` 表示明确未达标；`not_evaluable` 表示分母或必需统计量不可用。NA 从不替换为 0。

## 主要发现与图形证据

### 1. Main defense effect and benign-task utility

![Main defense effect and benign-task utility](main_defense_effect.png)

**结果解读：** 同提示比较中，ASR 从 50.5% 变为 0.4%，相对下降 99.2%；full Guard 的 DSR 为 0.0%。是否正式达标以验收矩阵和逐模型配对区间为准。

**如何阅读：** Core-model micro-averages compare regular_none with regular_full. E1 supplies attack-security metrics; E12 explicitly supplies overall benign TCR, legitimate-tool TCR, call-level FPR, and benign ASK rate. Every bar retains its own k/n and Wilson 95% interval.

**证据说明：** 来源 E1,E12；图表数据 14 行，其中 observed=14、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** E1 and E12 use distinct metric-specific denominators and are never pooled with each other.；E0 historical, Stub, and smoke rows are excluded.

### 2. Prompt hardening and Guard incremental ASR reduction

![Prompt hardening and Guard incremental ASR reduction](prompt_guard_increment.png)

**结果解读：** E2 的逐模型平均配对 ASR 降幅为 2.4%；E3 的逐模型平均配对 ASR 降幅为 47.8%。E2 与 E3 分别隔离提示词和 Guard 增量，不把二者混成一个处理。

**如何阅读：** E2 isolates prompt hardening without Guard; E3 isolates full Guard under the hardened prompt. Values are paired ASR reductions with case-clustered bootstrap 95% intervals.

**证据说明：** 来源 E2,E3；图表数据 8 行，其中 observed=8、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** Positive values indicate lower ASR in the treatment condition.

### 3. Guard component contribution

![Guard component contribution](guard_ablation.png)

**结果解读：** 影响最大的已测 ablation 是 ablation_named_detector_only，替换 full Guard 后 ASR 增加 31.0%。若其区间跨 0，应按不确定效应解读，而不是认定组件必然有贡献。

**如何阅读：** Paired ASR increase when each ablation variant replaces full Guard. Positive values indicate degradation; intervals are case-clustered bootstrap 95% intervals.

**证据说明：** 来源 E4；图表数据 24 行，其中 observed=24、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** This is a delta chart, not an absolute ASR chart; the zero reference is authoritative.

### 4. Cross-model ASR robustness

![Cross-model ASR robustness](cross_model_heatmap.png)

**结果解读：** full Guard 下残余 ASR 最高的已测模型为 llama3.2:3b（1.6%）；模型差异不被总体平均掩盖。

**如何阅读：** E5 ASR by model and condition. Each observed cell shows percentage and k/n; NA cells are hatched/labelled and never rendered as zero.

**证据说明：** 来源 E5；图表数据 8 行，其中 observed=8、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** Vicuna, when present, is compatibility-only and is not pooled with the four core models.

### 5. Attack-family robustness under full Guard

![Attack-family robustness under full Guard](family_robustness.png)

**结果解读：** 残余 ASR 最高的 family/model 单元是 environment_context_pollution / llama3.2:3b（14.3%）；最低 Recall 为 14.3%。

**如何阅读：** E6 full-Guard ASR, Recall, and DSR by attack family and model. Cells show exact k/n and Wilson intervals remain in the CSV.

**证据说明：** 来源 E6；图表数据 108 行，其中 observed=100、NA=8。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** Family-level sample sizes can be small; interpret wide intervals directly.

### 6. Language and encoding-evasion robustness

![Language and encoding-evasion robustness](language_evasion.png)

**结果解读：** 语言/规避切片中最高残余 ASR 出现在 Language · ASR 的 en（0.0%）；语言与编码分母保持分离。

**如何阅读：** E7 language and E8 encoding/evasion results are shown in separate panels; they are not pooled into one denominator. Exact labels show k/n.

**证据说明：** 来源 E7,E8；图表数据 36 行，其中 observed=36、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** E8 mutation types are categorical; no ordinal attack-strength axis is inferred.

### 7. Context length and injection-position trends

![Context length and injection-position trends](context_position_trends.png)

**结果解读：** 已测网格的最高 ASR 为 0.0%，对应 context=2048、位置=0%；图示 full Guard unresolved rate 为 11.7%；最大描述性 case p95 延迟为 41676.24 ms。

**如何阅读：** E9 full-Guard ASR, descriptive case-latency p95, and unresolved rate across ordered injection positions, faceted by context length. Across both registered E9 conditions, 14/120 (11.7%) case-runs were unresolved; this value is recomputed from context_position.csv rather than hard-coded.

**证据说明：** 来源 E9；图表数据 60 行，其中 observed=60、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** E9 has 14/120 (11.7%) unresolved case-runs across both conditions; long-context security estimates are incomplete without this disclosure.；Latency is descriptive and has no inferential interval; separate E14 evidence governs engineering acceptance.

### 8. Multi-turn and adaptive attack trends

![Multi-turn and adaptive attack trends](multiturn_adaptive_trends.png)

**结果解读：** Multi-turn 从 0.0% 变为 0.0%；Adaptive red team 从 0.0% 变为 0.0%。趋势只描述离散设计条件，不作连续时间外推。

**如何阅读：** E10 turn-count and E16 adaptive-round ASR are shown in separate panels. Exact point labels show k/n; the two denominators are never pooled.

**证据说明：** 来源 E10,E16；图表数据 15 行，其中 observed=15、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** Round/turn axes are discrete designed attempts, not continuous time.

### 9. Validation-only two-threshold operating points

![Validation-only two-threshold operating points](threshold_calibration.png)

**结果解读：** 冻结点的 Precision=96.6%、Recall=100.0%、FPR=4.5%、正常 ASK=0.0%；这只是验证集操作点。

**如何阅读：** E13 validation-only operating points over the two-dimensional ASK×DENY grid. Points are not connected because no single scalar threshold orders this grid; the frozen pair is marked with a star.

**证据说明：** 来源 E13；图表数据 20604 行，其中 observed=20604、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** E13 is calibration evidence only and is not used as blind-test outcome evidence.

### 10. Random stability across seeds and temperatures

![Random stability across seeds and temperatures](random_stability.png)

**结果解读：** 种子级 ASR 范围为 0.0%–5.0%；箱线图展示随机波动，不把 whisker 当作置信区间。

**如何阅读：** E15 seed-level ASR distributions by model and temperature. Raw seed points are retained; box whiskers are descriptive, not confidence intervals.

**证据说明：** 来源 E15；图表数据 120 行，其中 observed=120、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** The 10 seeds are repeated stochastic evaluations, not independent new cases.

### 11. Latency and throughput by context and concurrency

![Latency and throughput by context and concurrency](performance_profile.png)

**结果解读：** 最差已测 Guard p95=0.54 ms、端到端 p95=NA、最低吞吐=0.034 case-runs/s。工程验收按全部可评估 cell 而不是单一平均值判断。

**如何阅读：** E14 descriptive p95 latency and throughput by context, concurrency, and condition. Labels show successful/expected case-runs; missing and failed runs remain explicit.

**证据说明：** 来源 E14；图表数据 72 行，其中 observed=48、NA=24。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** Engineering measurements are hardware- and runtime-specific; no inferential interval is claimed.

### 12. Stratified human-audit failure taxonomy

![Stratified human-audit failure taxonomy](failure_taxonomy.png)

**结果解读：** E17 cohort 中最多的非 none 主分类是 leak（112/300）。该分类只对复核 cohort 权威，不能外推为主矩阵总体占比。

**如何阅读：** E17 primary classes in the 300-row representative audit stratum. The 60 targeted rows are excluded; the share panel uses dots and Wilson 95% intervals because the composition is too dense for an honest donut. Labels show count/total.

**证据说明：** 来源 E17；图表数据 8 行，其中 observed=8、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** Weighted population estimates and targeted-group diagnostics remain in the E17 source bundle.

### 13. Original E11 scope versus post-hoc requested cross-tool patterns

![Original E11 scope versus post-hoc requested cross-tool patterns](cross_tool_chain_patterns.png)

**结果解读：** 原始 v3各模式 full Guard ASR 范围为 0.0%–0.0%；post-hoc 补充各模式 full Guard ASR 范围为 0.0%–0.0%。两面板仅作分面描述，原始与补充分母从未合并；补充实验未预注册，不能追溯改写原始 E11 结论。

**如何阅读：** ASR by chain pattern and Guard condition. The upper panel is the original frozen v3 E11 scope; the lower panel is a post-hoc, not-pre-registered supplement. Every bar shows its own k/n and Wilson 95% interval; panels and denominators are never pooled.

**证据说明：** 来源 E11 original v3; E11_POSTHOC_AMENDMENT_V1；图表数据 16 行，其中 observed=16、NA=0。数据 CSV 保留精确 k/n、置信区间和限制字段；PNG/SVG 由同一 CSV 在本次生成中重绘。

**限制：** The supplement is post-hoc (pre_registered=false) and cannot retroactively replace the original E11 scope.；Only read_file_to_send_email directly overlaps the requested read_to_send semantics; all other requested patterns use independent supplement denominators.；No original and supplement counts are added, averaged, or used to change the acceptance matrix.

## 指标、分母与证据范围

- ASR、UTR、DSR、BSR、TCR 是案例/案例运行级比例；Precision、Recall、F1、FPR 和 ASK 类指标是调用级或明确命名的正常样本级比例。每个比例以原始 numerator/denominator 与 Wilson 95% 区间报告。
- FPR 是调用级误拦率，不能用 CaseFPR 替代。DSR 只使用具备数据外泄判定资格的攻击分母，因此不必等于所有攻击运行数。
- E1–E12 与 E15 是正式真实模型效果层；E13 只决定验证集阈值；E14 是工程性能层；E16、E17 是独立专项层，不能与主矩阵相加。
- E11 原始 manifest `outputs/experiments/E11/manifest.json` 保持主证据身份；post-hoc 补充 `outputs/experiments/E11_posthoc_amendment_v1/manifest.json` 仅补足请求模式，`pre_registered=false`，采用独立分母且禁止 pooling。
- 解析失败、拒答、超时和最大步数不会从原始运行分母静默删除；缺失统计量保持 NA。
- A11 的 `regular_full` 验收口径与主矩阵全条件解析诊断不可互换：后者的 step-row 为 12081/12538=96.4%（Wilson 95% CI 96.0%–96.7%，相对 95.0% 参考线为 pass），run-level 为 6025/6480=93.0%（Wilson 95% CI 92.3%–93.6%，相对 95.0% 参考线为 fail）。

## 方法与统计验证

主比例使用原始计数与 Wilson 95% 置信区间。E17 抽样审计另以冻结的分层权重给出 Hajek 比例和 10,000 次分层 percentile-bootstrap 95% 区间。正式实验中的配对二元结局、按案例聚类的 10,000 次 bootstrap、Wilcoxon 检验、效应量和 Holm 多重校正保留在各实验 `statistics.json`；本综合层不重复发明或伪造新的配对区间。ASR 总体目标使用 E1 core-model `model_condition` 行的明确 micro-average，同时要求审阅逐模型配对结果。E14 工程目标按所有可评估 context × concurrency cell 检查，最差 cell 作为保守摘要。

## 失败分类：权威分区与诊断信号分开

E17 的 8 行互斥主分类来自两名真人独立复核的 300 行代表性抽样层；另有 40 行自动分歧定向样本和 20 行稀有/复杂定向样本，仅作诊断且不进入该分母。总体估计及分层 bootstrap 区间保留在 E17 的 `weighted_population_estimates.csv`。E14/E16 另有 6 行工程或自适应诊断信号；这些信号可能重叠，也使用不同分母，因此不得相加成总体失败数。精确内容见 `failure_summary.csv`。

## 不确定性、限制与稳健性

- 点估计达标不等于置信区间整体满足阈值；尤其 DSR 观测为 0 时仍需报告 Wilson 上界并逐案检查。
- E13 的阈值是在验证集冻结的，不能以其结果替代盲测效果。
- E9 有 14/120=11.7% unresolved；长上下文结论必须同时展示该数据质量边界，不能只展示 ASR 点估计。
- E14 的延迟、吞吐和显存是当前硬件/Ollama 运行时上的描述性结果，外推到其他机器需重新测量。
- E16 的沙箱运行时由哈希绑定的 `raw_attempts.jsonl` 逐行验证为 `isolated-tool-sandbox-v1`；这不是 E16 manifest 的 schema version。E16 使用独立 validation 自适应分母，并排除在主矩阵、E14 性能和延迟汇总之外。
- E16 的轮次和 E10 的回合是离散设计条件，不是连续时间趋势；E17 是从自动筛选 cohort 冻结得到的分层抽样审计，只有 300 行代表性层可用于加权估计，不能描述成 3,299 行全量真人评审。
- 兼容性模型结果单独展示，不与四个核心模型合并为单一结论。
- E11 请求模式补充是在发现原始 scope 偏差后追加的 post-hoc amendment，因此只能作为透明披露的补充/敏感性证据，不能被描述为原始预注册结果。

## 建议的后续动作

1. 对所有 `fail` 目标定位到来源实验、模型、攻击族和原始案例；修复后完整复跑受影响条件，不只补单个有利结果。
2. 对 `not_evaluable` 目标补齐缺失分母或工程统计，再重新生成本综合包；不得人工改写 CSV 或图。
3. 对 E17 的 leak、false_block、parse_failure、timeout 和 max_steps 逐类关联 Guard reason code 与原始回放，形成可执行修复清单。
4. 正式最终分析与 Dashboard 只引用本包 figure manifest 中已验证的 PNG/SVG/CSV，并明确旧 FPR=0 和 Stub 结果属于早期原型/回归证据。

## 仍需回答的问题

- 未达标是否集中在单一模型、攻击族、语言或上下文位置？
- 安全提升是否由少数组件主导，且是否存在明显正常任务代价？
- 自适应改写的成功转移是否在更多独立模板上复现？
- 在不同 GPU、Ollama 版本和模型量化标签下，工程验收是否保持？

## 可复现入口

```powershell
python scripts/build_final_analysis_sampled_e17.py --registry experiments/registry.json --program-manifest outputs/experiments/program_manifest_final_v3.json --integrity-audit agent/audits/final_result_integrity.json --out outputs/experiments/final_analysis
```

本命令从 registry 重新验证所有输入，复验最终完整性审计对 program/freeze/threshold 的哈希绑定，并严格复验 E11 post-hoc 补充的独立证据链；随后生成验收矩阵、主矩阵解析诊断、E16 运行时来源、失败汇总、技术分析、13 组 CSV/PNG/SVG、figure manifest 和最终 artifact manifest。
