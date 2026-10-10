# M3-PI Guard：Flash 第二模型证据复核与暂停报告

**报告日期：** 2026-08-04  
**报告范围：** DeepSeek V4 Flash 公共矩阵的离线证据复核与合并  
**停止状态：** 已停止；无 Public、Gemini、Adaptive、盲测或 Harness 进程运行  
**科研结果状态：** 未准入，unsafe-effect、TCR 和条件优劣仍保持封存

## 1. 本轮结论

本轮完成了当前已经开始的离线证据复核工作，并在复核、定向测试、状态更新和
报告完成后停止。没有启动新的 API 调用，也没有恢复任何历史失败执行。

主要结论如下：

1. DeepSeek V4 Flash 第二模型角色的 1,791 个冻结工作键已形成完整、唯一、可重放
   的物理证据闭包：12 条 canary、473 条历史闭合前缀和 1,306 条 recovery。
2. 1,791 条记录中 16 条为 diagnostic，全部保留在 ITT；累计 4,193 次 provider
   calls，成本 CNY 1.87793024，自动重试为 0，provider tools 和外部 effect 均未启用。
3. 新版 recovery evidence review v4 修正了旧 v3 对否定边界布尔值的解释，但没有
   改写旧工件，也没有豁免原冻结质量门。shard 0 的证据完整性通过，质量门仍失败；
   shard 1 的证据完整性和原质量门均通过。
4. 新版 second-role evidence merge v1 精确重建 1,791 条覆盖，并通过独立重放。
   它只证明证据完整，不能自行授权科研结果访问。
5. 全角色 diagnostic 比例为 16/1,791，即 0.8934%，虽然低于 1%，但没有用于
   追溯豁免 shard 0 的分片失败。因此 clean-mechanism claim 仍不合格，只允许未来
   在独立结果准入后进入经验性的安全—效用分析路线。

## 2. 本轮工作边界

本轮仅执行本地、内容无关的证据读取、哈希重放、计数核对和单元测试。严格保持：

- API/provider/network 调用：0；
- 凭据读取：0；
- 科研 outcome 访问：0；
- 历史终态记录重试：0；
- 历史 ledger 行改写：0；
- diagnostic 排除：0；
- provider tools：false；
- external effects：false；
- Gemini、Adaptive、600 条盲测和完整 Harness：未启动。

本轮没有实现前瞻性的 Gemini contract v2。现有 Gemini segment 1 仍按历史 abort
review 永久封存；下一次工作必须使用新版本、新 segment、新 run identity 和新的
完整 Harness，不得复用旧响应或旧 work item。

## 3. 新增的版本化复核组件

### 3.1 恢复证据复核（第4版）

新增 `public_second_recovery_evidence_review_v4.py`，目标是把两个概念彻底分开：

- **证据完整性：** 记录、attempt、trace、预算、哈希、终态和 ITT 是否完整；
- **机制质量声明：** 冻结的每分片 1% diagnostic 门是否通过。

旧 v3 中 `source_terminal_records_retried=false` 本来表示“没有重试”，却被直接送入
`all(checks.values())`，使 false 被误作失败。v4 将其重述为正向检查
`zero_terminal_retries=true`，并把 `scientific_outcomes_aggregated=false` 等否定边界
独立保存。这样可以证明证据完整，但不会把 shard 0 的真实质量失败改成通过。

| 分片 | 记录 | diagnostic | 冻结上限 | 证据完整性 | 分片质量门 | 结果访问 |
|---|---:|---:|---:|---|---|---|
| shard 0 | 652 | 10 | 6 | PASS | FAIL | 未授权 |
| shard 1 | 654 | 4 | 6 | PASS | PASS | 未授权 |

v4 工件 manifest：

- shard 0：`1faf69b8606cb85d2adf5defad0697ed4b69cc33b31506b90408ea1b0e31292c`
- shard 1：`cac90f24257734ee5b7c286dee2cf1efe94ea5e3ce241b73b8efd847335fcc36`

### 3.2 第二模型证据合并（第1版）

新增 `public_second_evidence_merge_v1.py`。它只读取已封存技术证据，执行以下检查：

- canary 12 条技术门通过；
- 两个历史 prefix 不可变闭合；
- 两个 recovery evidence-integrity gate 通过；
- 原 1,779 条 continuation 的分片顺序保持不变；
- prefix 与 recovery 拼接后覆盖精确；
- 1,791 个 work key 全部唯一；
- attempt 全部终态，预算均未暂停；
- record/attempt/trace/budget 交叉绑定完整；
- 16 条 diagnostic 全部保留在 ITT；
- 科研 outcome 边界未被打开。

合并工件状态为：

`second_evidence_merge_pass_result_access_still_sealed`

manifest SHA-256：

`7fba09cc0f348b6fbb13545dbf7971ffea4d3f92e59badc5711f3c03d948432b`

文件 SHA-256：

`6334514e944976cebf4850297fb8d0db76a19daa7847784d64c275ebf8a8ef4e`

## 4. 第二模型物理闭包对账

| 证据组成 | 记录数 | diagnostic | provider calls | 成本（CNY） |
|---|---:|---:|---:|---:|
| canary | 12 | 0 | 18 | 0.01232192 |
| 历史闭合前缀 | 473 | 2 | 1,463 | 0.77555336 |
| recovery shard 0 | 652 | 10 | 1,329 | 0.59580836 |
| recovery shard 1 | 654 | 4 | 1,383 | 0.49424660 |
| **合计** | **1,791** | **16** | **4,193** | **1.87793024** |

关键派生量：

- 完整覆盖：1,791/1,791（100%）；
- diagnostic：16/1,791（0.8934%）；
- 预算使用：CNY 1.87793024 / 5（37.56%）；
- 预算余量：CNY 3.12206976；
- 自动重试：0；
- 终态记录重试：0；
- 外部 effect：0。

这里的 100% 只表示冻结工作键的物理执行证据齐全，不表示安全效果通过，也不表示
论文可使用该第二模型结果。

## 5. 质量门与结果门的准确解释

本轮把三层状态明确分开：

| 层级 | 当前状态 | 含义 |
|---|---|---|
| 物理执行闭包 | PASS | 1,791 个 work key 均有唯一终态证据 |
| 证据完整性 | PASS | 哈希、顺序、账本、trace、预算和 ITT 一致 |
| clean-mechanism 质量声明 | FAIL | shard 0 仍超过冻结的每分片 1% 门 |
| 独立科研结果准入 | 未执行 | 仍需独立 admission，不得由 merge 自授权 |
| 科研 outcome 访问 | 未授权 | unsafe-effect/TCR/条件差异未读取 |

因此目前可以公开的工程结论是“第二模型证据闭包和完整性通过”；不能公开的结论包括
“质量门通过”“第二模型验证了防御有效”“跨模型泛化成立”或“SOTA”。

## 6. 验证记录

### 6.1 真实工件生成与重放

- recovery v4 shard 0 write/verify：通过；
- recovery v4 shard 1 write/verify：通过；
- second-role merge v1 write：exit 0，约 206.1 秒；
- second-role merge v1 独立 verify：exit 0，约 207.9 秒；
- write 与 verify 返回相同 manifest、记录数和 diagnostic 数。

首次独立重放把外层等待误设为约 1 秒，返回 exit 124，没有形成验证结论，也没有
改写工件。该失败已记入 failure log；随后按真实构建耗时增加余量并完整重放通过。

### 6.2 定向代码检查

- 定向 pytest：8 passed；
- Ruff：通过；
- Python 编译检查：通过；
- 相关正式进程数：0。

本轮没有运行新的完整 Harness。因此 Fresh Harness v4 仍只是本轮变更前的绿色基线，
不能用来宣称这四个新源码/测试已经获得完整 Harness 覆盖。功能状态必须保持
`in_progress`。

## 7. 工件哈希

| 工件 | SHA-256 |
|---|---|
| recovery review v4 源码 | `771fbb31cfaa0e2f9714831a015fc1e3c70d12e9bae74dad7196c003442d3340` |
| recovery review v4 测试 | `d0b3b3789e9081eeef4d7b125c243f8ee77b4f5b8de2a9477cbd3b14e22332b6` |
| evidence merge v1 源码 | `7b9161f11d1d58376df73256c1f3a746c76777e2e7185a1a4a2d5a7b171c077e` |
| evidence merge v1 测试 | `293fb3c0979a947fe81ca2938edbb007da07b5e8bcb8cc1226d668b57adc937f` |
| merge JSON 文件 | `6334514e944976cebf4850297fb8d0db76a19daa7847784d64c275ebf8a8ef4e` |
| shard 0 review JSON 文件 | `727947117c5e1b5e0531f70a7fda38fedb3b8b26864e2039d8069c6d0e3db831` |
| shard 1 review JSON 文件 | `9b33a7375d2bbff1134ef4fc3e38def9cbf4991ee7e6fbfc593929100a07d402` |

## 8. 尚未完成的结项工作

本轮停止后，21 天计划仍有以下主要缺口：

1. 前瞻性 Gemini local-precommit + official response ID 合同升级、全新资格化和正式矩阵；
2. DeepSeek Pro 40、Flash 20、Gemini 20 的正式 adaptive 面板以及 hardest-20 × 2,000；
3. 第三方 600 条盲测的 authoring/custody、3,600 条六条件执行、解封和评分；
4. 独立科研结果准入、统计复算和异质性分析；
5. 将新复核组件纳入当前 Harness 后运行新的 single-use full Harness；
6. 最终 evidence manifest、成本/调用台账、失败台账和 SHA-256 结项包。

## 9. 下次恢复顺序

建议下次严格按以下顺序恢复：

1. 审查并实现前瞻性 Gemini trace-attaching runtime 新版本；
2. 补齐缺失 provider request ID、响应 ID 不匹配、payload 漂移、断链等负例；
3. 把 recovery v4、merge v1 和 Gemini 新合同纳入 Harness；
4. 运行 fresh full Harness，只有直接 exit 0 才生成新的非授权 gate；
5. 使用全新 Gemini segment/work identity 进行一条资格化，再做独立 canary；
6. 通过 outcome-blind 技术门后再决定是否扩展公共矩阵；
7. 最后依次进入 Adaptive、盲测、结果准入、统计和结项包。

## 10. 最终状态

当前最准确的项目表述为：

> DeepSeek V4 Flash 第二模型的 1,791 条公共矩阵已经完成物理证据闭包，并通过
> 版本化的证据完整性复核与独立重放；16 条 diagnostic 全部保留，未发生重试、
> 工具调用或外部 effect。shard 0 的冻结质量门仍失败，科研结果访问与独立准入
> 仍关闭。当前无相关进程运行，项目安全暂停，F-PAPER-002 保持 in_progress。
