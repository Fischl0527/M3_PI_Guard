# E4 DeepSeek V4 Flash 因子复现实验结果

状态：`complete`

## 执行与质量

- 冻结计划：360 个工作项，90 个案例 × 4 个因子单元。
- 终态有效工作项：360/360；均取得官方响应。
- 原始物理记录：361 行。其中 1 行为无响应的瞬时
  `ProviderTransportError`，仅对该 work key 执行第 2 次尝试并成功；其余成功行
  未重跑。
- 运行状态：347 `completed`、8 `parse_failure`、4 `provider_failure`、
  1 `max_steps`，全部按预定 ITT 规则保留。
- 在线 forbidden field、provider tool、真实外部 effect：均为 0。
- Flash 增量成本：CNY 0.5410834。

## 四个因子单元

| 单元 | 攻击 unsafe effect | 攻击 unsafe-or-failure | 良性工具 TCR | ASK | DENY |
|---|---:|---:|---:|---:|---:|
| policy + normal | 0/50 | 0/50 | 10/30 | 28/90 | 2/90 |
| policy + safe | 0/50 | 0/50 | 8/30 | 28/90 | 4/90 |
| full + normal | 0/50 | 2/50 | 10/30 | 27/90 | 3/90 |
| full + safe | 0/50 | 1/50 | 10/30 | 26/90 | 3/90 |

## 因子效应

Flash 的 50 个攻击案例在四个单元中均未产生 unsafe effect，因此 module、
prompt 和 interaction 的 unsafe-effect 点估计均为 0。该结果仍受地板效应约束，
不能解释为等价性证据。

良性工具任务中，module 平均主效应为 +3.33 个百分点（95% cluster-bootstrap
CI：0 至 +8.33），prompt 主效应为 -3.33 个百分点（-11.67 至 +3.33），交互
为 +6.67 个百分点（0 至 +16.67）。E4 是复现分析，不建立新的显著性家族。

攻击的 unsafe-or-failure 中，module 主效应为 +3.00 个百分点（0 至 +7.00），
prompt 主效应为 -1.00 个百分点（-5.00 至 +2.00），交互为 -2.00 个百分点
（-10.00 至 +4.00）。因此，Flash 没有显示 full 模块包的直接安全收益；观察到
的差异主要体现在失败敏感界限和良性任务效用。

## 解释边界

E4 只支持同一 API 服务商内部的 V4 Pro/V4 Flash 方向比较，不支持跨厂商泛化。
安全端点为全零时，主要信息来自 TCR、失败敏感界限、ASK/DENY、时延与成本，
不得把零 unsafe effect 表述为已经证明防御稳健。
