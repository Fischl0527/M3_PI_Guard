# M3-PI Guard 阶段性实验与工程验收报告

报告日期：2026-08-03  
报告范围：截至 Fresh Harness v4 自然结束的实验、证据链与工程状态  
当前决策：完成本次运行的核验与记录后暂停，不启动新的 API、公共矩阵、Adaptive 或盲测任务

## 1. 执行摘要

本阶段已经完成一个新的、直接观测操作系统退出码的全项目 Harness 验证。Fresh
Harness v4 于 2026-08-03 16:03:33（UTC+8）开始，于 20:38:25 自然结束，直接
退出码为 0。13 个聚合验证阶段全部通过，完整 pytest 结果为 1,485 passed、
1 skipped、3 warnings，最终唯一汇总标记为 `Verification failed=0`。

这次验证不授权网络或模型调用。启动器清除了 DeepSeek、Gemini 和 Google API
密钥环境变量，receipt 明确记录 `network_or_provider_call_authorized=false`。
因此，本次结论是“当前工程与冻结证据可重建且验证链为绿色”，不是新增模型效果、
跨模型泛化、Adaptive 成功或独立盲测结果。

按照项目所有者的最新指示，本报告交付后暂停后续执行。尚未生成 Fresh Harness
gate-v3，尚未生成新的 DeepSeek Flash recovery 或 Gemini continuation 执行准入，
也没有启动新的 provider 进程。F-PAPER-002 继续保持 `in_progress`，不能称为
21 天实验计划已经结项。

## 2. 本阶段完成的工作

### 2.1 Fresh Harness v4 全量验收

| 项目 | 结果 |
| --- | --- |
| 输出根 | `outputs/verification/experiment_closeout_fresh_harness_v4_20260803` |
| 开始时间 | 2026-08-03 16:03:33.3537245 +08:00 |
| 完成时间 | 2026-08-03 20:38:25.0139050 +08:00 |
| 总历时 | 约 4 小时 34 分 52 秒 |
| OS 退出码 | 0，直接观测 |
| 聚合阶段 | 13 PASS / 0 FAIL |
| pytest | 1,485 passed / 1 skipped / 3 warnings |
| Harness 终态 | `Verification failed=0` |
| Provider/网络授权 | false |
| 自动重启 | false |
| 新 API 调用 | 0 |

13 个通过的聚合阶段为：

1. Harness files；
2. Harness and project source boundary；
3. Project layout and naming conventions；
4. JSON contracts；
5. PowerShell syntax；
6. Shell syntax；
7. Python compile；
8. Unit and integration tests；
9. Experiment registry structure；
10. Paper-v2 source-audit evidence；
11. Paper-v2 frozen study assets；
12. Paper-v2 experiment closeout prospective evidence；
13. Historical evidence and current V2 freeze。

### 2.2 interim Harness v3 失败闭环

上一轮 interim Harness v3 的直接退出码为 1，pytest 为 1,456 passed、1 skipped、
3 warnings。唯一失败不是模型结果或核心运行时错误，而是旧静态测试只按
`pro_50` 字面量判断，未区分已废止的 adaptive v1 controller 与当前合法的 v2
controller。

本阶段没有改写旧运行，而是：

- 将 v3 失败、stdout、stderr 和源锁冻结为不可变失败审查；
- 把测试改为显式要求 adaptive v2，并显式禁止 v1 Pro/Flash admission；
- 完成 focused 20/20、扩展组合 38/38 和 conventions 12/12；
- 用全新的 v4 输出身份重跑完整 Harness，最终获得直接 exit 0。

这一处理保留了失败证据，也避免把局部测试通过冒充全项目验收。

### 2.3 独立盲测 Day-1 登记链

独立盲测保管人 Day-1 的公开登记闭包当前为精确 3/3 文件，冻结 acceptance
重放退出 0，定向测试 2/2 通过。项目只接收公钥、登记和独立验签公开回执，
没有接收私钥、标签、候选答案或身份声明明文。

这只证明保管人登记链可重放，并不证明以下工作已经完成：

- 600 条独立候选的第三方编写；
- 候选与标签的隔离保管；
- 3,600 条六条件盲测执行；
- 标签解封、独立评分和最终签名。

### 2.4 Gemini 失败感知对账与免费层计划

Gemini Public-v4 segment 0 的一条 VIGIL 后处理 runner failure 保留在 ITT，
没有重写 ledger。v5 技术审查对一条 provider transport completion 与该 runner
failure 完成精确对账，14/14 检查通过，结果准入仍为 false。缺失的 wrapper OS
receipt 没有伪造，同 segment 禁止重跑。

Gemini continuation-v2 保留 1,779 个 pending work item 和 1,186 个免费层配额
日段。当前冻结边界为官方免费层、USD 0、每项目每日 18 次本地上限。在不启用
Billing、不改变模型和不压缩证据预算的前提下，完整 Gemini 公共矩阵在 21 天内
不可完成；已记录的安全日历下界是 canary 之后至少 1,186 个配额日。

### 2.5 DeepSeek Flash 公共矩阵状态

DeepSeek Flash 的 12 条 canary 已完成，包含 18 次官方调用，记录成本
CNY 0.01232192；无 diagnostic、自动重试、provider tool 或真实外部 effect。

历史 continuation-v2 两个分片自然结束时合计保留 473 条记录、2 条 diagnostic、
1,463 次调用和 CNY 0.77555336。旧 wrapper receipt 缺失，不补造，也不恢复旧
身份。recovery-v3 候选仅覆盖 1,306 个从未触碰的 work key，当前只有离线候选，
没有新的 execution admission，未启动 recovery API。

## 3. Fresh Harness v4 证据完整性

| 文件 | SHA-256 |
| --- | --- |
| `receipt.json` | `a9fddc0fc5b8658b8375cc00ed2fcfa09359aa326eb0045809b704ca74c02c1b` |
| `stdout.log` | `1b1a530511dc6c465d53c29cd60166fa7d2917c6d3659a16f92fbaa5e7353d75` |
| `stderr.log` | `777e65d1c120c3aea21e3f59902548cd1341817b48bc6dbb5c081b582842cb26` |
| `harness/scripts/verify.ps1`（receipt 绑定） | `33390d65db42cca49c266620ad5460d21d9b662ee59e71ca850837d5ba97c6e4` |
| detached helper（receipt 绑定） | `3f3135bd7928a2665f0a00655dd6c605bc14f3cd484b6e580782b31d7f2ecdfd` |
| `running.json`（receipt 绑定） | `d37a2438ceffef313a000cdad6be428e9a7da3232f8305bbfc70e4e90e1273dd` |

receipt 同时记录：

- 操作系统退出码是直接观测值，不是从日志推断；
- stdout 为 1,122,157 bytes，stderr 为 6,405 bytes；
- DeepSeek、Gemini 和 Google API 环境变量已 scrub；
- 不授权 network/provider call。

stderr 的 126 行中，123 行是测试预期的
`[RuntimeAuditor] Blocked tool call: delete_record`，它证明删除型动作被审计器拒绝，
不是未处理异常。其余为 WSL 本地化/编码提示和一个空行。最终 13/13 阶段、pytest
和 OS exit 0 已独立确认，日志中没有 `FAIL:` 聚合阶段。

## 4. 当前科学证据状态

| 工作流 | 当前证据 | 是否完成正式目标 |
| --- | --- | --- |
| DeepSeek Pro 中型 480 条 | v8/v9 合并 480 条已准入并独立复算；机制门失败，转入授权泄漏/安全—效用经验研究叙事 | 已完成该主模型中型阶段，但不支持机制领先 |
| Public primary | 5,082 条、847 cases、76 个 ITT diagnostics；独立复算完成 | 主模型公共结果已完成，仍不是跨模型结论 |
| DeepSeek Flash Public | 12 条 canary + 历史 473 条 continuation 记录；1,306 个未触碰项待 recovery | 未完成 1,791 条正式矩阵 |
| Gemini Public | segment 0 一条 ITT runner failure；其余 canary/continuation 未完成 | 未完成；免费层产生长期外部约束 |
| Pro Adaptive | 8-task exploratory：374 terminal queries、562 calls、CNY 0.552805、unsafe-effect 0/8 | 不是冻结的 40-task 多预算正式面板 |
| Flash/Gemini Adaptive | 离线计划与调度存在 | 未执行正式 50/200 面板 |
| 独立盲测 | Day-1 保管人登记通过 | 600 条 authoring/custody、3,600 条运行和评分未完成 |

目前能够支持的结论是：主模型上存在明确的安全—效用权衡，M3-full 相对结构化
基线降低 unsafe effect，但相对 policy-only 没有独立安全增益，且良性工具任务
完成率下降。因此应维持经验研究 fallback，不应宣称 first、only、SOTA、机制
领先或跨模型泛化。

## 5. 未完成项与结项差距

21 天实验计划仍有以下硬缺口：

1. DeepSeek Flash 的 1,306 个未触碰公共 work item 未运行和准入；
2. Gemini 1,791 条公共矩阵未完成；
3. Pro 40 任务 50/200/500、hardest-20 × 2,000 未完成；
4. Flash 20 任务 50/200 与 Gemini 20 任务 50/200 未完成；
5. 600 条第三方独立盲测尚未 author、seal、执行、解封和评分；
6. 三模型正式统计、最终 evidence manifest、成本清单和结项哈希包未形成；
7. Fresh Harness gate-v3 尚未生成，故当前没有新的 provider execution gate。

其中 Gemini 免费层是结构性的日历阻塞：按当前冻结的 18 RPD 和一日一正式段设计，
仅 Public continuation 就需要至少 1,186 个配额日。这个事实不能用并发账号、
自动重试、429 重放或未执行记录冒充完成来规避。

## 6. 风险与审查意见

### 6.1 科学风险

- 主模型结果已经否定“full 必然优于 policy-only”的机制主张；后续应以经验研究
  叙事为主，而不是为了改善结果修改冻结条件。
- 第二模型和独立盲测为空，因此不能把单模型方向一致性扩大为普遍结论。
- 8-task Adaptive 的 0/8 点估计区间很宽，只能作为探索性证据。

### 6.2 工程与证据风险

- Flash 历史 wrapper 缺 receipt，必须保留为已披露证据缺口；禁止补造。
- Gemini segment 0 是 transport 完成后的 runner failure，必须继续留在 ITT；
  禁止同段重试。
- 盲测只能由第三方保管人推进，开发者不能代填候选、提前看标签或代签。
- 当前绿色 Harness 证明当前代码与冻结证据可重建，但不会自动授权 provider。

### 6.3 进度风险

- 在 Gemini free-only 边界不变时，原 21 天目标不具备日历可行性。
- 如果未来仍要求 21 天内完成，需要项目所有者另行决定是否更换具有可用免费
  配额的正式第二模型，或明确授权新的计费方案；这属于范围与预算变更，不能由
  当前执行者自行假设。

## 7. 暂停点与恢复条件

本次暂停点是安全且可恢复的：

- Fresh Harness v4 已终态 exit 0，相关 helper/child 和旧 Flash wrapper PID 均已
  自然消失；
- 没有开放的当前 Harness 进程；
- 没有启动新的 DeepSeek/Gemini provider 任务；
- Flash/Gemini recovery 仍是未授权候选；
- 历史终态与 diagnostics 未重试、未删除、未改写。

如项目所有者以后恢复实验，建议严格按以下顺序：

1. 只读重放 Fresh Harness v4 receipt、v3 failure review 和 Day-1 acceptance；
2. 生成并验证非自授权的 Harness gate-v3；
3. 为 DeepSeek Flash recovery-v3 创建新的 exact-command admission；
4. 仅运行 1,306 个未触碰 work key，完成技术审查与独立结果准入；
5. 对 Gemini 的免费层工期或替代方案做新的所有者决策后，再生成逐日 admission；
6. 第三方完成 600 条 custody 后，开发者才导入无标签执行集；
7. Adaptive 与盲测全部终态后，重建统计、完整 Harness 和最终哈希包。

## 8. 阶段结论

本阶段的工程验收是成功的：Fresh Harness v4 直接 exit 0，13/13 聚合阶段通过，
1,485 个测试通过，证据链和历史冻结可重建，且没有 provider/network 调用。

本项目的完整实验结项尚未完成。当前最准确的状态是：工程验证绿色、主模型中型与
primary public 已形成可审计经验结果、Day-1 保管人登记完成；第二模型正式矩阵、
三模型 Adaptive、600 条独立盲测及最终结项包仍待完成。报告交付后按所有者指示
暂停，不把阶段成功表述为项目最终结项。
