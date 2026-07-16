# E8 encoding_evasion 证据分析

- 状态：`completed`。
- 分析问题：How robust is the system to encoded and hidden variants?
- 正式运行完整度：90/90。
- 证据边界：正式指标仅使用真实 Ollama 模型；Stub 仅允许作为回归证据，未进入本实验任何正式分母。
- 缺失、解析失败、拒答、超时与最大步数不会被补零或静默删除。

## 数据与粒度

案例级指标按 case-run 计算；调用级 Precision/Recall/FPR 按可判定工具调用计算；延迟按配对 case-run 计算。相同实验的模型、条件与维度切片保持独立分母。

- 正式模型：qwen3:4b-instruct。
- Smoke 门禁模型：qwen3:4b-instruct。
- 正式 JSONL：2 个；原始步骤行：129。
- 逻辑案例运行：90；未解决案例运行：4。
- 解析失败行：4；非终态运行：0；重复 run-step：0。
- 分母政策：解析失败、未解决及其他 warning 案例运行仍保留在预注册分母中；warning 不是丢弃条件。

## 指标结果

主图指标为 ASR。所有比例均同时保留原始计数、分母与 Wilson 95% 置信区间；CSV 中空单元格表示 NA，不表示 0。

| Scope | Model | Condition | Dimension | Value | Count | Wilson 95% CI |
|---|---|---|---|---:|---:|---:|
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=base64 | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=base64 | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=character_split | 40.0% | 2/5 | [11.8%, 76.9%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=character_split | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=homoglyph | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=homoglyph | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=json | 40.0% | 2/5 | [11.8%, 76.9%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=json | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=markdown_hidden | 40.0% | 2/5 | [11.8%, 76.9%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=markdown_hidden | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=unicode_escape | 40.0% | 2/5 | [11.8%, 76.9%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=unicode_escape | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=xml | 40.0% | 2/5 | [11.8%, 76.9%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=xml | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=yaml | 40.0% | 2/5 | [11.8%, 76.9%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=yaml | 0.0% | 0/5 | [0.0%, 43.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_off` | obfuscation_type=zero_width | 20.0% | 1/5 | [3.6%, 62.4%] |
| obfuscation | qwen3:4b-instruct | `derived_normal_full` | obfuscation_type=zero_width | 0.0% | 0/5 | [0.0%, 43.4%] |

## 统计方法与解释边界

- 配对比较：9 组。
- 二元结果使用双侧精确 McNemar；ASR/DSR/TCR 差值使用按案例聚类的 10,000 次配对 bootstrap。
- 延迟使用配对 Wilcoxon 与 rank-biserial 效应量；同一实验内的可用假设统一做 Holm 校正。
- 不以单一 p 值判断效果；必须同时引用效应量、置信区间和原始分母。
- 不同实验矩阵（主矩阵、长上下文、多轮、稳定性）不互相混入分母。
- 主图可定义值范围：0.0000–0.4000；该范围只是证据概览，不替代逐条件统计。
- 主图 NA 单元：0；均未绘制为 0。

## 图表契约

```json
{
  "analytical_question": "How robust is the system to encoded and hidden variants?",
  "dimension": "obfuscation_type",
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
python -m experiments.analyze_program --experiments E8 --program-root 'outputs/experiments/program_final_v3' --out-root 'outputs/experiments'
```

本生成器不修改 `experiments/registry.json`；只有外部验收流程可以依据完整证据更新注册表状态。
