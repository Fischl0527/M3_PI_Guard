# M3-PI Guard Gemini v2/v5 离线收尾报告

日期：2026-08-04  
范围：Gemini 前瞻证据合同、Public canary 恢复候选、Flash 第二模型证据链与 Harness 集成  
结论状态：**离线实现与定向验证完成；完整 Harness 未取得可用终态，因此项目仍为 `in_progress`**

## 1. 本轮结论

本轮完成了手头的离线工程工作，并按要求停止在新的 API 执行之前：

1. 完成 Gemini 本地预提交证据合同 v2.1，解决“官方响应存在，但 Google 未返回 provider request ID”时的诚实证据表达问题。
2. 完成 Gemini Public-v5 canary 恢复控制器，只选择 10 个从未启动的任务；历史 1 条终态记录和 1 条中止记录保持不可变并继续留在 ITT。
3. 完成 v5 候选写入与独立重放，候选本身不授权执行、付费、重试、工具或真实外部 effect。
4. 将 Gemini v2/v5 和 Flash recovery-v4/evidence-merge-v1 纳入统一 Harness 入口。
5. 完成定向单元测试、注入式端到端回归、编译、Ruff 和项目约定检查。
6. 启动一次完整 Harness。外层在 3,604 秒达到时限并返回 exit 124；原验证子进程继续高 CPU 运行，随后又运行 441.6 秒并自然结束。由于外层收集器已经关闭，无法恢复原始 Harness 的最终退出码和完整日志，故本轮**不得宣称完整 Harness 通过**。
7. 最终确认相关 Harness、pytest、Gemini 和 Flash verifier 进程数量为 0。本轮没有启动任何新的 DeepSeek/Gemini API 请求。

因此，本轮形成了可审计的前瞻实现和候选证据，但还没有满足“新 provider 执行前必须有一轮直接、可留档的完整 Harness exit 0”这一门槛。

## 2. Gemini 前瞻证据合同 v2.1

### 2.1 问题边界

历史 Gemini Public-v4 segment 1 已获得官方 HTTP 200、精确模型身份和官方 response ID，但响应头没有 provider request ID。旧 runtime v1 将通用 receipt 的 `diagnostic_only` 与完整 trace bundle 机械取低，导致响应后的正式记录合同拒绝。历史记录、trace、ledger 和 abort review 均未修改。

### 2.2 新合同的允许路径

v2.1 只对一个非常窄的场景允许从通用 diagnostic 提升到 `formal_candidate`：

- provider 必须是官方 Google Gemini；
- 返回模型必须精确等于冻结的 `gemini-3.6-flash`；
- 官方 response ID 必须存在并在 receipt、trace 和 bundle 间一致；
- provider request ID 必须诚实记录为不可用，不得用本地 ID 冒充；
- 调用前本地 client request ID 和 canonical payload hash 必须已经持久化；
- trace bundle 必须完成，且 open/failure 均为 0；
- append、flush、fsync 三项必须成立；
- billing tier 必须为 free、实际收费 USD 0、paid ceiling USD 0；
- automatic retry、provider tools、外部连接、真实 effect 和敏感内容持久化必须全部为 0/false。

任一 provider、模型、response ID、payload、提示改写声明、bundle 完整性、费用或身份字段漂移都会 fail closed。旧的 `request_id` 字段不会被伪造；v2 另外记录 `client_request_id`、`request_identity_mode` 和 `provider_request_id_available`。

### 2.3 验证结果

- runtime v2 单元测试：20/20 通过；
- 覆盖双 ID、缺 provider ID、post-response runner failure、模型/响应/payload 漂移、非零收费、不完整 bundle、qualification/stub 路径、tamper 和 secret/prompt 不落盘等正负例；
- 合同 v2.1 候选独立重放：exit 0；
- manifest：`accc5941608fd1194c8e8cdbcce4a858ca84142dfaab3d293443871042c93bb8`；
- `network_calls_made=0`，`provider_execution_authorized=false`。

## 3. Gemini Public-v5 canary 恢复设计

### 3.1 历史边界

控制器直接验证历史工件的 canonical manifest、source lock、授权边界和内容无关计数，不递归重建同一 1,791 行计划多次：

- 历史 segment 0：保留 1 条终态 runner-failure 记录；
- 历史 segment 1：保留 1 个 open attempt 对应的永久中止 ITT 槽位；
- 两个历史 work key 均不可重试、修复、改写或迁移；
- 科研结果访问和结果准入仍为 false。

### 3.2 新候选分区

原 canary 共 12 个槽位。v5 只选择其余 10 个未触碰 work key，并形成 7 个独立免费层日段：

| 日段 | 新记录数 | 最大 provider 请求数 |
|---:|---:|---:|
| 0 | 1 | 8 |
| 1 | 1 | 16 |
| 2 | 2 | 16 |
| 3 | 1 | 16 |
| 4 | 2 | 16 |
| 5 | 1 | 16 |
| 6 | 2 | 16 |

每段都满足本地 18 RPD 上限，要求独立 quota day、独立 run ID、execution identity、output root、ledger 和 admission。候选状态是 `candidate_pending_fresh_harness_and_daily_admissions`，不包含任何已激活 admission。

### 3.3 候选证据

- 候选 manifest：`f00fe60135f57c4f1951bb7fb19947a6a2aac2d971470b599d7612b41d49a472`；
- 候选文件 SHA-256：`c0a6448c993e0ae5a5b82c0dfbf03c3fc1c14fb41444d4930613ba8aee1fd455`；
- write：exit 0；独立 verify：exit 0；
- candidate-only，segment execution=false，historical retry=false，matrix continuation=false，result admission=false；
- free tier，paid ceiling USD 0，automatic retries=0；
- provider tools=false，external effects=false。

## 4. 定向验证证据

| 检查 | 结果 | 说明 |
|---|---:|---|
| v5 候选/准入三项测试 | 3/3 PASS | 10 个未触碰任务、精确免费层准入、错误 owner digest 拒绝 |
| v5 缺 request ID 注入式 E2E | 1/1 PASS | 本地假响应；官方 response ID 存在，provider request ID 缺失 |
| runtime v2 测试 | 20/20 PASS | 正负路径、持久化与不泄密边界 |
| Python 编译 | PASS | 5 个实现模块和 5 个对应测试文件 |
| Ruff | PASS | 同上 |
| 项目约定审计 | 12/12 PASS | Harness 集成后执行 |
| 合同 v2.1 独立重放 | exit 0 | 不授权网络/provider |
| v5 候选 write/verify | exit 0 / exit 0 | 相同 manifest 重建 |
| Flash merge | 已有 write/verify exit 0 | 1,791 记录、16 diagnostic 全保留 |
| 完整 Harness | **无可用结论** | 外层 3,604 秒 exit 124；子进程随后自然结束但退出码不可恢复 |

注：VIGIL 依赖在部分测试中产生 Pydantic v2 deprecation warning；这是已知上游警告，不是本轮测试失败。

## 5. 完整 Harness 超时分析

### 5.1 观测事实

- 完整命令在清除 `DEEPSEEK_API_KEY`、`GEMINI_API_KEY` 和 `M3_FRONTIER_API_CONSENT` 后启动；
- 外层 60 分钟时限返回 exit 124，且没有交付阶段输出；
- 外层结束时，原 PowerShell Harness 和 pytest 子进程仍存在；pytest CPU 时间约 3,197 秒，说明是持续计算，不是网络等待或静态死锁；
- 未终止子进程；继续只读监测 441.6 秒后，原 Harness 进程自然消失；
- 最终相关进程计数为 0；
- stdout/exit-code 收集通道已在外层超时关闭，子进程自然结束不等于已证明 exit 0。

### 5.2 原因判断

新增测试和 verifier 会多次重建 1,791 行计划、VIGIL 依赖状态、历史 append-only 链和 Flash 1,791-record merge。定向测试表明一次候选重建约需 140 秒，完整 pytest 对多个用例重复执行这些路径，叠加 Harness 后续逐工件重放，使总时长超过原 60 分钟窗口。

### 5.3 工程处理

- 不把这次运行标记为 PASS；
- 不自动重跑；
- 不据此创建 Gemini admission；
- 不修改或排除历史失败；
- 后续应使用 single-use launcher、独立 stdout/stderr/receipt 和至少 90 分钟的外层窗口，或者在不降低覆盖率的前提下共享不可变候选 fixture，随后必须取得直接 exit 0。

## 6. Flash 第二模型现状

- 1,791/1,791 唯一 work key；
- 16 条 diagnostic 全部留在 ITT；
- 4,193 次 provider calls，累计 CNY 1.87793024；
- retry=0、provider tools=false、external effects=false；
- recovery-v4 的 evidence-integrity 对两个 shard 均为 PASS；
- shard 0 的冻结质量门仍为 10 diagnostic > 6，不能用整体 0.8934% 覆盖该预注册失败；
- merge manifest：`7fba09cc0f348b6fbb13545dbf7971ffea4d3f92e59badc5711f3c03d948432b`；
- merge 文件 SHA-256：`6334514e944976cebf4850297fb8d0db76a19daa7847784d64c275ebf8a8ef4e`。

这证明证据完整性，不等于科学结果已经准入，也不支持 SOTA、跨 provider 或无条件机制质量主张。

## 7. 文件与哈希

| 文件 | SHA-256 |
|---|---|
| `experiments/paper_v2/gemini_trace_attaching_runtime_v2.py` | `7d3989fdcea59a08577ce1cc770f5bc6a20c2c99ddb44aafdfe230ba267003ca` |
| `experiments/paper_v2/gemini_local_precommit_contract_v2_candidate.py` | `4aa2c994a90607eaeff2cf2bbead060ee60c51728cad76b65fda8253aa2ab5ba` |
| `experiments/paper_v2/gemini_public_controller_v5.py` | `b6fcc8340a2c3936b27fe736cbe2c7e57c520d976cbd151e5a042e4a7403d339` |
| `protocols/paper_upgrade_v2/gemini_local_precommit_contract_v2_1_candidate.json` | `31e3fadf31d251c28e7fd84dc39fc9166cfdf32b9b06ab0a031010251e45407c` |
| `protocols/paper_upgrade_v2/gemini_public_canary_recovery_candidate_v5.json` | `c0a6448c993e0ae5a5b82c0dfbf03c3fc1c14fb41444d4930613ba8aee1fd455` |
| `protocols/paper_upgrade_v2/public_second_evidence_merge_v1.json` | `6334514e944976cebf4850297fb8d0db76a19daa7847784d64c275ebf8a8ef4e` |
| `harness/scripts/verify.ps1` | `5aa9908a176d95fc755588bfae66ce63baf884f5c27121533e7b30cab0ea394f` |

## 8. API、安全与费用声明

本轮没有读取、打印或复制 API key；没有新的 DeepSeek 或 Gemini 请求；没有配额预约；没有 API 成本；没有 provider tool、真实邮件、支付、浏览器、生产 API 或其他外部 effect。注入式端到端测试使用本地构造的 HTTP 200 响应，不访问互联网。

## 9. 未完成项与恢复入口

项目整体仍未结项，`F-PAPER-002` 必须保持 `in_progress`。下一次恢复的唯一合理入口是：

1. 为当前 `verify.ps1` 创建 single-use、可持久化 stdout/stderr/receipt 的 fresh Harness；
2. 使用足够的外层运行窗口，取得直接 exit 0 和 `Verification failed=0`；
3. 只有该门通过后，才可为 v5 segment 0 创建当日、单次、精确命令 admission；
4. 后续 Gemini 仍受免费层 18 RPD、本地零重试和 USD 0 约束；
5. 正式 Gemini 公共矩阵、三模型 adaptive、600 条盲测执行/解封/评分、统计复算和最终哈希结项包仍未完成。

## 10. 最终判定

本轮“手头工作”的实现部分已完成并形成可重放候选；运行部分已经自然停止，后台相关进程为 0。由于完整 Harness 的直接终态证据缺失，当前只能判定为：

> **Gemini v2/v5 前瞻离线工程就绪，定向验证通过；新 API 执行仍未准入，21 天实验结项目标尚未完成。**
