## Material Passport

- Origin Skill: `academic-research-suite / experiment-agent`
- Mode: `plan -> run -> validate`
- Date: 2026-08-31
- Status: `FROZEN / OWNER AUTHORIZED / NOT STARTED`
- Study ID: `m3-q2-e6-cross-provider-calibration-v2`
- Execution block: `B1`

# E6-v2 B1 无人工延时结项计划

## 1. 目标与边界

本计划闭合独立诊断执行块 B1，不恢复 E6-v1 的跨日三窗口设计。B1 只投影
此前未执行的 source-W3 计划成员，但具有新的 study、run、execution、work-key、
output、trace、ledger 和 stop 身份。

- DeepSeek V4 Pro：60 个攻击任务 × 6 条件 = 360 条；
- Gemini 3.6 Flash：嵌套 30 个攻击任务 × 6 条件 = 180 条；
- 每个 provider 先执行 12 条 outcome-blind 正式前缀；
- 不设置 v1 W2 seal、18--30 小时、跨日或最长 12 小时时间门；
- 不运行真实邮件、支付、浏览器、代码执行、文件修改或生产 API effect；
- Gemini 只允许官方免费层、USD 0、无 Billing、无模型/项目/密钥池回退；
- response-bearing 行不重跑，失败和行政关闭均保留在 ITT；
- B1 不提供跨日期重复性、攻击饱和、部署流行率或正式跨厂商泛化证据。

## 2. 审计结论与待补接口

执行前只读审计确认：DeepSeek 360、Gemini 180 个 work key 均唯一；六条件
分别为 60/30 条；AgentDojo 与 M3-v2 各占一半；两家各有 12 条正式前缀；所有
计划行均为 `B1`、`replicate_index=1`、
`sample_role=risk_enriched_activity_diagnostic` 和
`temporal_replication_claim=false`。B1 输出根尚不存在，活动 E6 进程为 0，
Git 忽略的本地配置文件存在但未读取内容。

正式调用前必须补齐并验证两个最小接口：

1. `--seal-block`：技术门失败、provider 不可用或全部行终态后，给所有未触碰项
   写入显式行政终态并封存 B1，不制造 provider attempt 或模型响应；
2. B1 专用一次性分析器：禁止调用 E6-v1 时间重复性路径，只分析单块活性、
   条件差、2×2 因子、运行失败、负担、成本和嵌套跨 provider 方向。

## 3. 执行顺序

### A. 离线冻结门

- 完成 `--seal-block`、B1 分析器、Markdown 报告与定向测试；
- 运行 B1 runner/analysis、provider trace、身份、字段隔离、免费层和真实 effect
  负例；
- Ruff、`py_compile`、JSON 解析和 `git diff --check` 通过；
- 提交并推送离线设计检查点后才允许 provider 调用。

### B. DeepSeek 正式前缀与扩展

```powershell
F:\robot\Anaconda3\python.exe -B -m experiments.paper_v2.e6_cross_provider_calibration_runner_v2 --provider deepseek --block B1 --canary-only --config config/project.local.env
```

技术门通过后：

```powershell
F:\robot\Anaconda3\python.exe -B -m experiments.paper_v2.e6_cross_provider_calibration_runner_v2 --provider deepseek --block B1 --resume-pending-only --config config/project.local.env
```

### C. Gemini 正式前缀与扩展

```powershell
F:\robot\Anaconda3\python.exe -B -m experiments.paper_v2.e6_cross_provider_calibration_runner_v2 --provider gemini --block B1 --canary-only --config config/project.local.env
```

技术门通过后：

```powershell
F:\robot\Anaconda3\python.exe -B -m experiments.paper_v2.e6_cross_provider_calibration_runner_v2 --provider gemini --block B1 --resume-pending-only --config config/project.local.env
```

DeepSeek 与 Gemini 顺序执行，避免共享 GPU detector 和本地资源造成条件相关故障。

### D. 失败恢复与封存

- 获得官方响应的 refusal、parse failure、max-steps 或 provider failure：原行终态
  保留，不覆盖；
- 无响应且具有 attempt-1 payload commitment 的唯一 unresolved key：只允许显式
  `--retry-failed-work-key <KEY>` 一次；attempt 2 终态；
- HTTP 429：该 work key 为 ITT diagnostic terminal，不走 generic recovery；
- fatal identity/payload/safety/usage/ledger 错误：写 provider stop 并立即停止；
- 前缀满 12 条但技术门失败：不扩展，使用 `--seal-block` 将未触碰项登记为
  `technical_gate_not_extended`；
- provider 在前缀完成前不可用或 fatal-stopped：使用 `--seal-block` 将未触碰项登记
  为 `provider_block_unavailable`；
- 技术门通过后的 response-less 中断先按唯一 key 恢复；仍无法终态时封存并透明
  报告，绝不重跑成功行或降低技术门。

## 4. 技术门

每个 provider 的 12 条正式前缀必须同时满足：

- 返回模型与冻结模型完全一致；
- request ID、payload digest、官方 response ID 和 returned model 完整；
- 至少 9/12 为 `completed`；
- evaluator/gold 原始字段在线可见数为 0；
- provider tools 和真实 external effect 为 0；
- 不存在重复的系统性 runner/contract 错误；
- Gemini 每行均有免费层、USD 0、`paid_fallback_enabled=false` 证明。

技术门不读取 `unsafe_effect`，安全结果不决定是否扩展。

## 5. 一次性分析

以计划 360/180 为 ITT 分母，分别报告：

- planned、observed、terminal、response-bearing 和 operational status；
- 每条件 unsafe effect、unsafe-or-failure、ASK、DENY、provider calls、延迟、token
  与成本；
- no-defense B1 活性：DeepSeek `x/60`、Gemini `x/30` 及 Wilson 95% CI，按两个
  benchmark 分层；
- 四个配对比较：VIGIL−no-defense、policy-normal−no-defense、
  full-safe−no-defense、full-safe−VIGIL；
- M3 四条件的 module、prompt 和 module×prompt 作用；
- Gemini 30 个嵌套任务上的 provider 内效应与 DeepSeek 对应方向，仅作 diagnostic；
- 实际执行开始、结束和跨度，不把跨度用作准入或重复性检验。

配对比较使用 Newcombe 区间；任务聚类、benchmark 分层 bootstrap 10,000 次；
四项主比较做 Holm 校正。全零时不得把退化 bootstrap `[0,0]` 写成确定性结论，
同时给出 cell-level Wilson 上界。B1 不计算窗口 agreement、Fleiss κ、跨窗口复现率
或三窗口 pooled estimate。

## 6. 最小产物

```text
outputs/experiments/e6_cross_provider_calibration_v2/
├── deepseek_pro/
│   ├── raw_records_v2.jsonl
│   ├── window_gate_B1_v2.json
│   └── block_seal_B1_v2.json
├── gemini_flash/
│   ├── raw_records_v2.jsonl
│   ├── window_gate_B1_v2.json
│   └── block_seal_B1_v2.json
├── analysis_v2.json
├── tables/
├── figures/
└── report_v2.md
```

`internal/` 继续 Git 忽略。公开产物不保存密钥、完整 prompt、完整 response、header
或 provider trace。不得生成递归哈希包、历史重放或 Full Harness 工件。

## 7. 完成定义

B1 只有在以下条件全部成立时结项：

- 540 个计划 work key 均有模型终态或显式行政 ITT 终态；
- 两个 provider 均有 gate 和 block seal；
- 所有 response-bearing 行身份链完整，字段泄漏、provider tools、真实 effect 为 0；
- Gemini 成本为 USD 0 且无回退；
- B1 专用分析、表、图和 Markdown 报告可由两份 raw JSONL 一次重建；
- 报告明确区分完整矩阵、技术门未扩展和 provider 不可用；
- 定向测试、Ruff、`py_compile`、JSON、差异和独立结果复审通过；
- Harness 状态、失败台账、任务历史和会话移交更新；
- 公开最小证据提交并推送 `origin/codex/q2-empirical-study`；
- 正面、负面、全零、429 或 provider 不可用均按原样保留，不以结果方向定义成功。
