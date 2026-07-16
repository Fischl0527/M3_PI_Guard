# E12 benign_utility 证据分析

- 状态：`completed`。
- 分析问题：What normal-task utility and false-positive cost remain?
- 正式运行完整度：6480/6480。
- 证据边界：正式指标仅使用真实 Ollama 模型；Stub 仅允许作为回归证据，未进入本实验任何正式分母。
- 缺失、解析失败、拒答、超时与最大步数不会被补零或静默删除。

## 数据与粒度

案例级指标按 case-run 计算；调用级 Precision/Recall/FPR 按可判定工具调用计算；延迟按配对 case-run 计算。相同实验的模型、条件与维度切片保持独立分母。

- 正式模型：qwen3:4b-instruct, phi4-mini:3.8b, llama3.2:3b, gemma3:4b。
- Smoke 门禁模型：qwen3:4b-instruct, phi4-mini:3.8b, llama3.2:3b, gemma3:4b。
- 正式 JSONL：72 个；原始步骤行：12538。
- 逻辑案例运行：6480；未解决案例运行：563。
- 解析失败行：457；非终态运行：0；重复 run-step：0。
- 分母政策：解析失败、未解决及其他 warning 案例运行仍保留在预注册分母中；warning 不是丢弃条件。

## 指标结果

主图指标为 TCR。所有比例均同时保留原始计数、分母与 Wilson 95% 置信区间；CSV 中空单元格表示 NA，不表示 0。

| Scope | Model | Condition | Dimension | Value | Count | Wilson 95% CI |
|---|---|---|---|---:|---:|---:|
| utility_overall | gemma3:4b | `regular_none` | gemma3:4b | 59.3% | 48/81 | [48.4%, 69.3%] |
| utility_overall | gemma3:4b | `hardened_none` | gemma3:4b | 63.0% | 51/81 | [52.1%, 72.7%] |
| utility_overall | gemma3:4b | `regular_keyword` | gemma3:4b | 55.6% | 45/81 | [44.7%, 65.9%] |
| utility_overall | gemma3:4b | `regular_policy` | gemma3:4b | 51.9% | 42/81 | [41.1%, 62.4%] |
| utility_overall | gemma3:4b | `regular_full` | gemma3:4b | 51.9% | 42/81 | [41.1%, 62.4%] |
| utility_overall | gemma3:4b | `hardened_full` | gemma3:4b | 51.9% | 42/81 | [41.1%, 62.4%] |
| utility_overall | llama3.2:3b | `regular_none` | llama3.2:3b | 9.9% | 8/81 | [5.1%, 18.3%] |
| utility_overall | llama3.2:3b | `hardened_none` | llama3.2:3b | 27.2% | 22/81 | [18.7%, 37.7%] |
| utility_overall | llama3.2:3b | `regular_keyword` | llama3.2:3b | 6.2% | 5/81 | [2.7%, 13.6%] |
| utility_overall | llama3.2:3b | `regular_policy` | llama3.2:3b | 0.0% | 0/81 | [0.0%, 4.5%] |
| utility_overall | llama3.2:3b | `regular_full` | llama3.2:3b | 0.0% | 0/81 | [0.0%, 4.5%] |
| utility_overall | llama3.2:3b | `hardened_full` | llama3.2:3b | 4.9% | 4/81 | [1.9%, 12.0%] |
| utility_overall | phi4-mini:3.8b | `regular_none` | phi4-mini:3.8b | 71.6% | 58/81 | [61.0%, 80.3%] |
| utility_overall | phi4-mini:3.8b | `hardened_none` | phi4-mini:3.8b | 75.3% | 61/81 | [64.9%, 83.4%] |
| utility_overall | phi4-mini:3.8b | `regular_keyword` | phi4-mini:3.8b | 72.8% | 59/81 | [62.3%, 81.3%] |
| utility_overall | phi4-mini:3.8b | `regular_policy` | phi4-mini:3.8b | 66.7% | 54/81 | [55.9%, 76.0%] |
| utility_overall | phi4-mini:3.8b | `regular_full` | phi4-mini:3.8b | 66.7% | 54/81 | [55.9%, 76.0%] |
| utility_overall | phi4-mini:3.8b | `hardened_full` | phi4-mini:3.8b | 54.3% | 44/81 | [43.5%, 64.7%] |
| utility_overall | qwen3:4b-instruct | `regular_none` | qwen3:4b-instruct | 93.8% | 76/81 | [86.4%, 97.3%] |
| utility_overall | qwen3:4b-instruct | `hardened_none` | qwen3:4b-instruct | 90.1% | 73/81 | [81.7%, 94.9%] |
| utility_overall | qwen3:4b-instruct | `regular_keyword` | qwen3:4b-instruct | 93.8% | 76/81 | [86.4%, 97.3%] |
| utility_overall | qwen3:4b-instruct | `regular_policy` | qwen3:4b-instruct | 88.9% | 72/81 | [80.2%, 94.0%] |
| utility_overall | qwen3:4b-instruct | `regular_full` | qwen3:4b-instruct | 88.9% | 72/81 | [80.2%, 94.0%] |
| utility_overall | qwen3:4b-instruct | `hardened_full` | qwen3:4b-instruct | 86.4% | 70/81 | [77.3%, 92.2%] |

## 统计方法与解释边界

- 配对比较：8 组。
- 二元结果使用双侧精确 McNemar；ASR/DSR/TCR 差值使用按案例聚类的 10,000 次配对 bootstrap。
- 延迟使用配对 Wilcoxon 与 rank-biserial 效应量；同一实验内的可用假设统一做 Holm 校正。
- 不以单一 p 值判断效果；必须同时引用效应量、置信区间和原始分母。
- 不同实验矩阵（主矩阵、长上下文、多轮、稳定性）不互相混入分母。
- 主图可定义值范围：0.0000–0.9383；该范围只是证据概览，不替代逐条件统计。
- 主图 NA 单元：0；均未绘制为 0。

## 图表契约

```json
{
  "analytical_question": "What normal-task utility and false-positive cost remain?",
  "dimension": "model",
  "family": "comparison_and_uncertainty",
  "metric": "TCR",
  "na_policy": "undefined values are labelled NA and never rendered as zero",
  "palette_policy": "hard_two_root_plus_non_color_styles",
  "renderer": "matplotlib_static_png_svg",
  "uncertainty": "Wilson 95% confidence intervals",
  "variant": "grouped_bar_with_wilson_95ci"
}
```

## 可复现命令

```powershell
python -m experiments.analyze_program --experiments E12 --program-root 'outputs/experiments/program_final_v3' --out-root 'outputs/experiments'
```

本生成器不修改 `experiments/registry.json`；只有外部验收流程可以依据完整证据更新注册表状态。
