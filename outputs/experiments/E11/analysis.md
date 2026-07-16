# E11 cross_tool_chain 证据分析

- 状态：`completed`。
- 分析问题：Can attacks propagate across authorized tool chains?
- 正式运行完整度：44/44。
- 证据边界：正式指标仅使用真实 Ollama 模型；Stub 仅允许作为回归证据，未进入本实验任何正式分母。
- 缺失、解析失败、拒答、超时与最大步数不会被补零或静默删除。

## 数据与粒度

案例级指标按 case-run 计算；调用级 Precision/Recall/FPR 按可判定工具调用计算；延迟按配对 case-run 计算。相同实验的模型、条件与维度切片保持独立分母。

- 正式模型：qwen3:4b-instruct。
- Smoke 门禁模型：qwen3:4b-instruct。
- 正式 JSONL：2 个；原始步骤行：80。
- 逻辑案例运行：44；未解决案例运行：2。
- 解析失败行：2；非终态运行：0；重复 run-step：0。
- 分母政策：解析失败、未解决及其他 warning 案例运行仍保留在预注册分母中；warning 不是丢弃条件。

## 指标结果

主图指标为 ASR。所有比例均同时保留原始计数、分母与 Wilson 95% 置信区间；CSV 中空单元格表示 NA，不表示 0。

| Scope | Model | Condition | Dimension | Value | Count | Wilson 95% CI |
|---|---|---|---|---:|---:|---:|
| chain_pattern | qwen3:4b-instruct | `derived_normal_off` | chain_pattern=read_file_to_call_api | 66.7% | 4/6 | [30.0%, 90.3%] |
| chain_pattern | qwen3:4b-instruct | `derived_normal_full` | chain_pattern=read_file_to_call_api | 0.0% | 0/6 | [0.0%, 39.0%] |
| chain_pattern | qwen3:4b-instruct | `derived_normal_off` | chain_pattern=read_file_to_send_email | 50.0% | 3/6 | [18.8%, 81.2%] |
| chain_pattern | qwen3:4b-instruct | `derived_normal_full` | chain_pattern=read_file_to_send_email | 0.0% | 0/6 | [0.0%, 39.0%] |
| chain_pattern | qwen3:4b-instruct | `derived_normal_off` | chain_pattern=run_code_to_write_file | 33.3% | 2/6 | [9.7%, 70.0%] |
| chain_pattern | qwen3:4b-instruct | `derived_normal_full` | chain_pattern=run_code_to_write_file | 0.0% | 0/6 | [0.0%, 39.0%] |
| chain_pattern | qwen3:4b-instruct | `derived_normal_off` | chain_pattern=write_file_to_call_api | 25.0% | 1/4 | [4.6%, 69.9%] |
| chain_pattern | qwen3:4b-instruct | `derived_normal_full` | chain_pattern=write_file_to_call_api | 0.0% | 0/4 | [0.0%, 49.0%] |

## 统计方法与解释边界

- 配对比较：4 组。
- 二元结果使用双侧精确 McNemar；ASR/DSR/TCR 差值使用按案例聚类的 10,000 次配对 bootstrap。
- 延迟使用配对 Wilcoxon 与 rank-biserial 效应量；同一实验内的可用假设统一做 Holm 校正。
- 不以单一 p 值判断效果；必须同时引用效应量、置信区间和原始分母。
- 不同实验矩阵（主矩阵、长上下文、多轮、稳定性）不互相混入分母。
- 主图可定义值范围：0.0000–0.6667；该范围只是证据概览，不替代逐条件统计。
- 主图 NA 单元：0；均未绘制为 0。

## 图表契约

```json
{
  "analytical_question": "Can attacks propagate across authorized tool chains?",
  "dimension": "chain_pattern",
  "family": "matrix_and_cohort",
  "metric": "ASR",
  "na_policy": "undefined values are labelled NA and never rendered as zero",
  "palette_policy": "single_root",
  "renderer": "matplotlib_static_png_svg",
  "uncertainty": "numerators, denominators and Wilson intervals remain in chart CSV",
  "variant": "annotated_heatmap"
}
```

## 可复现命令

```powershell
python -m experiments.analyze_program --experiments E11 --program-root 'outputs/experiments/program_final_v3' --out-root 'outputs/experiments'
```

本生成器不修改 `experiments/registry.json`；只有外部验收流程可以依据完整证据更新注册表状态。
