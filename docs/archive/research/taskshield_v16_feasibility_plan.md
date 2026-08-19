# Task Shield v1.6 可行性与恢复方案

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-22
- Verification Status: UNVERIFIED
- Version Label: taskshield_v16_feasibility_plan_v1
- Authorization Status: superseded_by_approved_staged_execution_plan

> 2026-07-22 更新：用户已经批准进入 v1.6。本文保留为批准前的可行性分析；
> 当前授权边界和可执行门禁以
> `taskshield_v16_execution_plan.md` 及
> `protocols/paper_upgrade_v1/execution/taskshield_v16_preparation_v1/` 为准。

## 1. 推荐决策

不要直接运行 v1.6 模型实验。先完成 AgentDojo 指标桥 P0 修正，再决定 Task
Shield 是否值得继续。推荐顺序是：

1. 非破坏性修正 ASR 语义和受影响分析；
2. 新建 v1.6 correctness-only runtime，修 timeout、trace 和完整 schema；
3. 先 4-case 定点预检，再 fresh 12-case qualification；
4. 只有效用、运行可靠性和延迟同时过门槛，才运行 30-case pilot；
5. 726-case 仅在服务器上、经新的显式授权后运行。

如果 v1.6 的 12-case 仍低于 2/6 utility、合法动作仍被 schema error 拒绝，
或 p95 仍高于 matched same-model comparator 的 5 倍，应停止 Task Shield
正式化，把它保留为 disclosed negative diagnostic，并转向 Progent/CaMeL。

## 2. Objective and hypothesis

- Objective：证明指标语义、失败证据和运行时契约均正确后，判断 Task Shield
  是否能在不显著破坏 utility 的前提下阻断注入。
- H1 correctness：raw AgentDojo injection result 与统一 `attack_success` 逐行
  100% 一致。
- H2 reliability：已知 invalid JSON、wrong cardinality 和 timeout 不再产生
  未记录或契约外失败。
- H3 utility：fresh 12-case utility 至少达到同模型 comparator 的 2/6，且
  没有合法工具调用因 verifier schema failure 被拒绝。
- H4 cost：12-case p95 不超过 matched comparator 的 5×，单 case 硬上限
  不超过 600 秒。

## 3. 阶段 P0：指标语义隔离与纠正

### 修改原则

- 不修改任何旧 freeze、outcomes、official trace、analysis 或 registry 历史。
- 新 schema 使用无歧义字段：
  - `official_injection_success`：直接读取 AgentDojo attack checker；
  - `attack_success`：等于 `official_injection_success`；
  - `security_preserved`：等于 `not official_injection_success`；
  - 旧 `security_success` 标为 deprecated，不再进入新表。
- utility case 的 AgentDojo `security=true` 只是无攻击路径默认值，不得计入
  ASR 或 `security_preserved`。

### 交付物

1. 一个只读 semantics audit，逐行核对 outcomes 与 raw official trace。
2. ToolFilter analysis-v2：从 629 份 raw trace 重建 7/629 Targeted ASR、CI、
   图表和 manifest，不覆盖 v1。
3. Task Shield v1.5 corrected-diagnostic analysis：0/6 ASR、1/6 utility。
4. IPIGuard、CaMeL、Progent、Transformers detector 的影响清单。
5. Q2 readiness 和双 registry 的重新审计；在审计完成前不增加分数。

### Gate G0

- 所有 security case 的 `attack_success == official_trace.security`；
- utility case 不进入攻击分母；
- raw trace 缺失数为 0，或逐案列为 blocker；
- complement/inversion fixture 测试通过；
- 旧文件 hash 全部不变。

## 4. 阶段 P1：v1.6 correctness-only 新实现

v1.6 必须新建 runtime、runner、freeze 和 output root，不在 v1.5 上修改。

### 4.1 timeout 语义

- `_request` 保留精确 timeout 类型和所有 attempt metadata。
- untrusted `assistant`/`tool_output` timeout 耗尽后进入明确的 fail-closed
  suppression row；trusted-user 初始化 timeout 仍使 case 失败。
- 不捕获所有异常，只捕获冻结列出的 transport timeout 类型。

### 4.2 单一重试所有者

- OpenAI client 显式 `max_retries=0`。
- v1.6 自己管理最多 2 次 logical attempt，backoff 1 秒。
- 建议 verifier read timeout 初值 120 秒；单个逻辑 verifier 调用最多约
  241 秒，不再出现 SDK×runtime 乘法重试。
- case 级硬超时 600 秒。硬超时保留失败行，不自动重跑。

### 4.3 完整 schema recovery

恢复循环必须覆盖完整契约，而不只是 `json.loads()`：

- 顶层必须是 array；
- extraction 元素必须是非空字符串；
- scoring 每项必须是 object；
- score 必须可解析且在 [0,1]；
- row 数必须与 trusted task 数严格相等；
- retry row 必须保留原始输出、错误类型和 expected/observed cardinality。

第一次 schema 失败后允许一次带 expected schema/count 的纠正请求。该纠正
提示属于方法变化，必须写入 freeze，不能称为原论文官方实现。

### 4.4 失败证据和计时

- case 开始时保存独立 trace handle；
- success/failure 两个分支都先 snapshot，再写 case manifest；
- progress 使用独立 `started_at`、`finished_at`、`duration_ms`；
- 保存 verifier logical attempt、SDK retry policy、timeout、raw output、parse
  结果、schema 结果和最终 fail-closed decision。

### 4.5 不在 correctness 版本中混入的优化

以下优化会改变复现条件，应作为单独的 v1.6-lite/v1.7 消融，不混入主版本：

- 更换更小 verifier 模型；
- 跨 case 缓存 trusted task extraction；
- 批量合并 instruction extraction 与 contribution scoring；
- 以 PromptGuard 或关键词代替 Task Shield verifier。

## 5. 阶段 P2：无模型单元测试

必须先通过以下 deterministic fixtures：

1. AgentDojo `security=true` 映射为 attack success；
2. `security=false` 映射为 security preserved；
3. utility case 不进入攻击分母；
4. assistant timeout 两次耗尽后 suppress；
5. tool-output timeout 两次耗尽后 suppress；
6. trusted-user timeout 仍失败；
7. wrong cardinality 第一次失败、第二次恢复；
8. wrong cardinality 两次失败后零分 fail-closed；
9. failed outcome 保留完整 trace；
10. terminal timestamps 和 duration 正确；
11. OpenAI client `max_retries=0`；
12. `retry_failed=false`、无 case retry、无 failed-row exclusion。

### Gate G1

- 全部新测试通过；
- 现有 Task Shield/Q2/layout 回归通过；
- hash-bound identity 和历史证据验证通过；
- v1.3/v1.4/v1.5 文件零漂移。

## 6. 阶段 P3：4-case 定点预检

在新的显式授权后，只选择已知失效点：

- banking user_task_6 utility/security：invalid JSON + cardinality；
- slack user_task_18 utility/security：timeout + 多步工具链。

### Gate G2

- 4/4 terminal outcomes，0 operational failure，0 missing；
- 四条 outcome 均保存 trace；
- 所有 timeout/contract retry 次数与 freeze 一致；
- raw official metric 与新字段 100% 一致；
- 没有自动 case retry；
- 每条 case ≤600 秒。

失败时立即停止，不扩到 12 条。

## 7. 阶段 P4：fresh 12-case qualification

可以复用 v1.5 的 12 条作为已知回归集，因为它们只用于 qualification，不能
作为新 confirmatory blind。必须新建 root，不 resume v1.5。

### Gate G3

- 12/12 completed，0 failed，0 missing；
- utility ≥2/6；
- 攻击条件下的 utility 单独报告，不允许用低 utility 换取低 ASR；
- 没有合法工具动作因 parser/schema/cardinality error 被拒绝；
- corrected Targeted ASR 与 raw official trace 逐行一致；
- p95 ≤ matched same-model comparator 的 5×；
- max case ≤600 秒；
- Q2 score change 仍为 0，qualification 仍不可进入正式表。

## 8. 阶段 P5：30-case 成本和效用 pilot

仅在 G3 全部通过后，冻结 15 条 utility 与各自一条 security pair，覆盖四个
AgentDojo suite、单步/多步工具链和不同 trusted-task 数。

### Gate G4

- 30/30，0 operational failure；
- paired utility 相比同模型 comparator 下降不超过 1/15；
- parser/schema failure 不导致合法工具误拒；
- 报告 raw count、Wilson CI、paired difference 和 latency；
- 根据实测吞吐重新估算 726-case wall time；
- 预计本机运行超过 24 小时时，正式矩阵必须迁移服务器。

## 9. 阶段 P6：726-case formal

只有用户再次明确授权且 G0–G4 全部通过后才能冻结并运行。

- 使用服务器或独占 GPU 顺序运行；
- fresh root、零 case retry、失败保留原分母；
- 任意 operational failure 都阻断 admission；
- raw official Targeted ASR、utility、timeout、schema recovery、合法动作误拒和
  latency 同时进入分析；
- 完成后再生成 Pareto、CI、失败类型图和论文表格。

## 10. 停止和转向条件

满足任一条件即停止 Task Shield formal 路线：

- 12-case utility <2/6；
- 仍有合法动作因 verifier schema failure 被拒；
- 仍有失败行缺 trace；
- p95 超过 comparator 5×，或 30-case 推算 726-case 不可承受；
- corrected ASR 只能通过全部拒绝/任务失败获得；
- 修复需要改变方法到无法合理称为 Task Shield disclosed reproduction。

停止后保留 v1.3–v1.6 为完整 negative-result 工程证据，论文强基线槽转向
Progent 和 CaMeL。这样比无上限迭代 Task Shield 更有利于推进 Q2 80%。

## 11. 资源与预计工作量

| 阶段 | 模型调用 | 适合资源 | 预计性质 |
| --- | ---: | --- | --- |
| P0 semantics correction | 0 | CPU | 从现有 raw trace 重建 |
| P1/P2 implementation/tests | 0 | CPU | 新代码和 fixtures |
| P3 4-case preflight | 4 cases | 本机 8GB GPU | 失败模式定点验证 |
| P4 12-case qualification | 12 cases | 本机或服务器 | 预计数小时，设硬上限 |
| P5 30-case pilot | 30 cases | 优先服务器 | 估算正式成本 |
| P6 726-case formal | 726 cases | 服务器/独占 GPU | 仅最终授权后 |

## 12. 本方案不授权的动作

- 不启动 Ollama、API 或模型实验；
- 不修改 v1.3/v1.4/v1.5；
- 不重跑单个失败 case；
- 不排除失败行；
- 不修改现有 Q2 分数或 formal registry；
- 不创建 v1.6 freeze，直到 P0 审计完成且用户明确同意继续。
