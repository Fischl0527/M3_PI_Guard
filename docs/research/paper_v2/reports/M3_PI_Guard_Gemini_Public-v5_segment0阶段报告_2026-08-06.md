# M3-PI Guard Gemini Public-v5 Segment 0 阶段技术报告

日期：2026-08-06（Asia/Shanghai）  
执行范围：fresh Harness v6 非授权门禁、Gemini Public-v5 recovery 单日段包装器、
一个最小官方免费层 segment 及其 outcome-blind 技术审查。  
结论：本阶段工作已完成并停止；21 天实验结项总任务尚未完成。

## 1. 执行结论

本阶段成功把 2026-08-05/06 已通过的 fresh Harness v6 转换为可独立重放的
non-authorizing closeout gate v4，并建立了真正绑定
`gemini_public_controller_v5` 与 v5 recovery candidate 的 single-use 包装器。

在全部前置门禁通过后，项目于 America/Los_Angeles 配额日 `2026-08-05`
执行 Gemini Public-v5 recovery segment 0：

- 计划记录：1；实际记录：1；
- provider call attempts：1；transport completions：1；
- 返回模型：`gemini-3.6-flash`；官方 response ID 存在；
- 记录状态：`formal_candidate`，`operational_status=completed`，保留在 ITT；
- 技术门：全部检查通过，`matrix_continuation_eligible=true`；
- 计费层：free；`charged_usd=0.0`，`paid_ceiling_usd=0.0`；
- 自动重试：0；provider tools：关闭；external effects：关闭；
- runner failure：0；日志 secret-format 命中：0；
- scientific outcome access：false；result admission：false。

包装器最终 exit 0，所有相关正式进程已归零。本阶段没有扩展到下一 segment。

## 2. 为什么需要新门禁和新包装器

历史文件 `run_gemini_public_v5_segment_guarded.ps1` 虽然名称含 v5，但实际绑定
的是 `gemini_public_controller_v4`、旧 v4 candidate 和旧 admission 路径。
直接复用会造成执行身份与证据合同错配。因此本阶段没有修改历史包装器，而是
新增独立版本：

- `experiments/paper_v2/experiment_closeout_harness_gate_v4.py`；
- `outputs/verification/run_gemini_public_v5_recovery_segment_guarded_v2.ps1`；
- 两组独立定向测试；
- 新 gate artifact、prospective admission、运行 receipt 和技术 review。

这一处理保留了历史证据不可变性，也使本次运行身份、candidate、admission、
quota day、work-key 和输出根形成一条前瞻闭合链。

## 3. 新工程准入检查（第4版）

gate v4 绑定 fresh Harness v6 的 launch、running、stdout、stderr、receipt、helper
和 launcher，同时重放以下前置证据：

1. fresh Harness v5 失败审计；
2. process-scoped Git safe.directory 资格化；
3. Adaptive v2 执行顺序；
4. 独立盲测 Day-1 登记 acceptance；
5. DeepSeek Flash second-role 1,791 条证据 merge；
6. Gemini Public-v5 recovery candidate。

门禁观测结果：

- Harness stage：13/13 PASS；
- pytest：1,538 passed、1 skipped、3 warnings；
- 终态：唯一 `Verification failed=0`；
- RuntimeAuditor 预期删除阻断：183；
- Traceback：0；疑似密钥格式命中：0；
- v6 child exit：0，evidence gate：true；
- verifier/helper 运行前后 hash 稳定；
- AgentDojo commit 精确匹配；global/repository Git config 未修改。

gate manifest：
`d79faf97795a3cc1ac67104e767d6f85f77ff5f00f02e3ee5eaf2592916e1e9a`。

gate 文件 SHA-256：
`4ffa9d247fa746b7ccb7a2105e823f66b578fd3c87d94d8ccdc6e83193796cbc`。

该 gate 明确保持：provider execution=false、result access=false。它只是工程和
证据前置条件，不单独授权 API。

## 4. 当日精确 admission

执行前检查结果：

- 当前 provider quota day：`2026-08-05`；
- 已占用日仅为 `2026-08-02`、`2026-08-03`；当前日未占用；
- segment 0 记录数：1；最大 provider requests：8；
- 输出根不存在，文件数为 0；
- 其他 Gemini Public-v5 正式执行进程：0；
- admission 文件此前不存在。

由此生成只针对 segment 0 和该配额日的 prospective admission：

`protocols/paper_upgrade_v2/admissions/
gemini_public_canary_recovery_v5_s0_2026-08-05_admission.json`

- admission manifest：
  `99abc6a8b7302a793cda38d0ee96b400466f3dee0f6933dabdbdfbe722727de4`；
- admission 文件 SHA-256：
  `4a7c8a5939fc601c027c8d9ccffe4153f55c8fddd9aed819bf0b7e98f9806190`；
- free tier、USD 0、automatic retries 0；
- provider tools/external effects/result admission 均为 false；
- 同日其他正式 Gemini 工作未获授权。

## 5. 单次执行与证据链

single-use wrapper 依次执行四个捕获步骤，全部 exit 0：

| 步骤 | 作用 | Exit |
|---|---|---:|
| 01 | 重放 Harness gate v4 | 0 |
| 02 | 重放精确 admission | 0 |
| 03 | 执行 segment 0 | 0 |
| 04 | 生成 outcome-blind 技术 review | 0 |

请求证据采用：调用前本地预提交 request identity/payload hash，加官方 response ID、
精确返回模型和 append-only terminal binding。Gemini 本次响应没有暴露 provider
request ID，因此 `provider_request_id_available=false`；但本项目已冻结的
`gemini_local_precommit_plus_official_response_v2` 合同允许在本地预提交链、官方
response ID、模型与 payload 绑定、fsync 和零未闭合调用全部成立时形成
`formal_candidate`，且不会伪造 provider request ID。

内容无关 usage evidence：

- requests：1；
- prompt tokens：593；
- completion tokens：17；
- provider total tokens：844；
- billing tier：free；charged USD：0.0。

报告不读取或披露 `unsafe_effect`、`task_completion` 等科研 outcome 字段；本次
技术通过不能解释为安全效果、效用或模型优劣结论。

## 6. 终态工件

运行根：

`outputs/verification/gemini_public_v5_recovery_s0_2026-08-05_guarded_v2`

- `receipt.json` SHA-256：
  `a881799ffd1e3f012fb11da0cb41bc5839e62d73760e1e547199c00c5b51b3de`；
- receipt status：`completed_technical_gate_pass`；
- final exit code：0；
- secret scan：pass，命中 0。

实验输出根：

`outputs/paper_upgrade_v2/formal_public/gemini/
public-v5-canary-recovery-s0-885cf3a88684ca7427a29a5c0b65e0a6f97746133279fb59341bae557c4b48b2`

| 文件 | SHA-256 |
|---|---|
| `attempt_events_v1.jsonl` | `076f281da0c580178133e1ef9a3fe4fe8852c7931b5422b1435687c68a5be121` |
| `provider_call_events_v1.jsonl` | `06cf23e51443aff528ac47717f51444f7e5e08baa8a7a81091161ab43bb44569` |
| `experiment_records_v2_contract.jsonl` | `1c342e3874274dd70499a558bd177a9b43e8a794563d5cedae36a02a6930e2a6` |
| provider trace JSONL | `56f1801f46d1ccb78952678b22184c6781b865d9f8f206bd537af9bc79c58f1f` |
| `technical_segment_review_v6.json` | `a77e206cb90354f3dfb5a031cbbd59d77699bd43427a2ddfb6dc9231441e08d7` |

技术 review manifest：
`86e48d12fb1e9aad993acaa8c51e70c5922297e46313f23937fa3523b44560c2`。

quota ledger 已追加第三个合法事件，当前 SHA-256：
`858b66b05e9dcb834914eb2ab869a0faccc776f2c61d72907517baa958bfa532`。

## 7. 验证结果

本阶段完成以下验证：

- gate/wrapper/quota/controller 定向回归：20 passed，1 个已知 VIGIL Pydantic
  deprecation warning；
- 新门禁负例与包装器静态检查：12 passed；
- Ruff：pass；py_compile：pass；
- 新 wrapper 与统一 `verify.ps1` PowerShell parse：pass；
- project conventions：12/12 pass；
- wrapper 内 gate/admission/execute/review 四步：全部 exit 0；
- 相关正式进程终态：0。

本阶段没有在新增 gate/wrapper 并接入 `verify.ps1` 后再运行一次完整 Harness。
最新完整 Harness 仍是 v6 的 1,538/1/3 与直接 exit 0；因此不能把本阶段描述为
“最终完整 Harness 已重新通过”。这一缺口必须在后续更大规模正式扩展前关闭。

## 8. 发现并修复的问题

新 wrapper 初次静态解析时，在有序哈希表值中直接使用 `if/else`，不兼容当前
Windows PowerShell parser。修复方式是先计算 quota-ledger hash 与 receipt status，
再写入哈希表。该失败发生于纯静态解析阶段，没有创建运行根、quota reservation、
API 调用或实验记录。

此外，只读进程检查最初把检查命令自身计入匹配；排除当前 PID 后正式进程为 0。
正式 wrapper 本身从一开始就包含该 PID 排除，因此没有执行安全缺陷。

## 9. 当前项目状态与后续边界

本阶段只证明：Gemini Public-v5 recovery 的新证据合同和单日段执行路径在 1 条
最小样本上技术闭合。它没有完成以下 21 天结项目标：

- Gemini 1,791 条完整正式公共矩阵；
- DeepSeek Pro/Flash 与 Gemini 的正式 adaptive 面板；
- hardest-20 × 2,000；
- 600 条独立盲测 authoring、执行、解封和评分；
- 三模型统计重建、异质性分析和最终哈希结项包；
- 新增源之后的最终完整 Harness。

因此 F-PAPER-002 应继续保持 `in_progress`，不能标为结项。技术 review 给出
`matrix_continuation_eligible=true`，只代表后续可以在新的配额日、新 admission、
未触碰工作键和完整 Harness 门禁下继续；它不自动授权 segment 1，也不授权读取
科研结果。本报告生成后，本轮按项目所有者要求停止。
