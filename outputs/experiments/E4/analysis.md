# E4 component_ablation 证据分析

- 状态：`completed`。
- 分析问题：Which Guard components contribute protection and utility cost?
- 正式运行完整度：1500/1500。
- 证据边界：正式指标仅使用真实 Ollama 模型；Stub 仅允许作为回归证据，未进入本实验任何正式分母。
- 缺失、解析失败、拒答、超时与最大步数不会被补零或静默删除。

## 数据与粒度

案例级指标按 case-run 计算；调用级 Precision/Recall/FPR 按可判定工具调用计算；延迟按配对 case-run 计算。相同实验的模型、条件与维度切片保持独立分母。

- 正式模型：qwen3:4b-instruct。
- Smoke 门禁模型：qwen3:4b-instruct。
- 正式 JSONL：25 个；原始步骤行：2485。
- 逻辑案例运行：1500；未解决案例运行：47。
- 解析失败行：47；非终态运行：0；重复 run-step：0。
- 分母政策：解析失败、未解决及其他 warning 案例运行仍保留在预注册分母中；warning 不是丢弃条件。

## 指标结果

主图指标为 ASR。所有比例均同时保留原始计数、分母与 Wilson 95% 置信区间；CSV 中空单元格表示 NA，不表示 0。

| Scope | Model | Condition | Dimension | Value | Count | Wilson 95% CI |
|---|---|---|---|---:|---:|---:|
| ablation_condition | qwen3:4b-instruct | `ablation_named_detector_only` | ablation_named_detector_only | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_named_full_guard` | ablation_named_full_guard | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_named_keyword_only` | ablation_named_keyword_only | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_named_no_dataflow` | ablation_named_no_dataflow | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_named_no_intent_action` | ablation_named_no_intent_action | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_named_no_multilingual_detector` | ablation_named_no_multilingual_detector | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_named_no_structured_detector` | ablation_named_no_structured_detector | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_named_off` | ablation_named_off | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_named_policy_only` | ablation_named_policy_only | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_remove_dataflow` | ablation_remove_dataflow | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_remove_instruction_detector` | ablation_remove_instruction_detector | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_remove_intent_action` | ablation_remove_intent_action | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_remove_multilingual_detector` | ablation_remove_multilingual_detector | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_remove_output_dlp` | ablation_remove_output_dlp | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_remove_policy` | ablation_remove_policy | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_remove_structured_detector` | ablation_remove_structured_detector | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_remove_tool_lure_detector` | ablation_remove_tool_lure_detector | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_solo_dataflow` | ablation_solo_dataflow | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_solo_instruction_detector` | ablation_solo_instruction_detector | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_solo_intent_action` | ablation_solo_intent_action | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_solo_multilingual_detector` | ablation_solo_multilingual_detector | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_solo_output_dlp` | ablation_solo_output_dlp | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_solo_policy` | ablation_solo_policy | 0.0% | 0/42 | [0.0%, 8.4%] |
| ablation_condition | qwen3:4b-instruct | `ablation_solo_structured_detector` | ablation_solo_structured_detector | 31.0% | 13/42 | [19.1%, 46.0%] |
| ablation_condition | qwen3:4b-instruct | `ablation_solo_tool_lure_detector` | ablation_solo_tool_lure_detector | 31.0% | 13/42 | [19.1%, 46.0%] |

## 统计方法与解释边界

- 配对比较：24 组。
- 二元结果使用双侧精确 McNemar；ASR/DSR/TCR 差值使用按案例聚类的 10,000 次配对 bootstrap。
- 延迟使用配对 Wilcoxon 与 rank-biserial 效应量；同一实验内的可用假设统一做 Holm 校正。
- 不以单一 p 值判断效果；必须同时引用效应量、置信区间和原始分母。
- 不同实验矩阵（主矩阵、长上下文、多轮、稳定性）不互相混入分母。
- 主图可定义值范围：0.0000–0.3095；该范围只是证据概览，不替代逐条件统计。
- 主图 NA 单元：0；均未绘制为 0。

## 图表契约

```json
{
  "analytical_question": "Which Guard components contribute protection and utility cost?",
  "dimension": "condition",
  "family": "paired_effect_and_uncertainty",
  "metric": "ASR",
  "na_policy": "undefined values are labelled NA and never rendered as zero",
  "palette_policy": "single_root",
  "renderer": "matplotlib_static_png_svg",
  "uncertainty": "case-clustered paired bootstrap 95% confidence intervals",
  "variant": "paired_ASR_TCR_contribution_forest_with_bootstrap_95ci"
}
```

## 可复现命令

```powershell
python -m experiments.analyze_program --experiments E4 --program-root 'outputs/experiments/program_final_v3' --out-root 'outputs/experiments'
```

本生成器不修改 `experiments/registry.json`；只有外部验收流程可以依据完整证据更新注册表状态。
