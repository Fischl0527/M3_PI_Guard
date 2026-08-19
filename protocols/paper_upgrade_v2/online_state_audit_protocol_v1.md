# paper-v2 Online-State 源码审计协议 v1

状态：`active`  
版本：`m3-paper-v2-online-state-audit-1.0`  
登记表：`online_state_audit_registry_v1.json`

## 目的

判断一个公开防御或基准在**在线执行阶段**实际向 Agent、Guard、policy generator、validator 或 judge 暴露了哪些字段。审计目标不是从论文描述推测是否 “oracle”，而是形成可复核的源码级证据。

## 审计单位

一个审计单位是固定源码版本中的一个可执行组件，例如：

- benchmark case loader；
- runtime projection；
- defense/guard entry point；
- policy generator；
- tool/action validator；
- success/attack evaluator；
- metric denominator builder。

同一仓库的 loader、Guard 和 evaluator 必须分别跟踪，不能因为共享仓库而合并结论。

## 禁止在线可见字段

以下字段或其语义等价物只能存在于离线 evaluator：

- gold/expected answer；
- attack success label；
- task success label；
- expected malicious tool/action；
- per-case exact allow/deny key；
- evaluator-only reference trajectory；
- 直接由最终标签生成的授权范围；
- 任何可反推出上述信息的派生字段。

字段名命中只能作为检索线索，不能单独证明泄漏；没有命中也不能证明安全。

## 固定步骤

1. **来源固定**
   - 记录官方论文页、官方源码 URL、默认分支、40 位 commit SHA、许可证和获取时间。
   - 只有固定 commit 后才能进入 `source_pinned`。
2. **入口定位**
   - 标出 case 读取、在线 Agent/Guard、工具执行和 evaluator 的入口文件与行号。
3. **数据流追踪**
   - 从原始 case 对象逐字段追踪到 prompt、policy、GuardDecision 和工具执行参数。
   - 区分 initialization、online execution、post-hoc evaluation。
4. **负向投影测试**
   - 为禁止字段写入唯一 sentinel；
   - 捕获所有在线序列化对象和模型请求；
   - sentinel 或等价派生值不得出现。
5. **差分测试**
   - 只改变 evaluator/gold 字段，保持在线输入不变；
   - 在线 proposal/decision/tool trace 必须保持不变。
6. **授权来源判定**
   - `user_or_manifest`：来自独立用户/任务策略；
   - `auto_compiled_non_gold`：只由非标签上下文生成；
   - `broad_default`：统一宽策略；
   - `gold_derived`：由答案/标签/参考轨迹生成；
   - `mixed_or_unclear`：无法排除 gold 派生。
7. **双人复核**
   - 首审和复核不得使用同一份私有笔记；
   - 冲突保留为 `disputed`，不以多数意见覆盖证据。

## 结论枚举

- `no_online_gold_observed`：固定版本和已覆盖路径中未发现禁止字段；不是全局安全证明。
- `online_gold_observed`：有可复现数据流或动态 sentinel 证据。
- `mixed_or_path_dependent`：仅部分模式/路径泄漏。
- `inconclusive`：入口不完整、代码不可运行或证据不足。
- `not_a_runtime_guard`：只做离线检测/评估，不应与运行时执行防御混为一类。

## 准入规则

- 源码审计与基线准入相互独立。发现性能差、延迟高或效用低不能排除基线。
- `online_gold_observed` 不自动否定该论文；正式比较必须增加无 oracle 配置或明确标为不可比。
- 未完成源码审计前，正文只能写“待审计”或描述作者公开方法，不能写“该领域普遍使用 oracle”。
- 任何动态运行均先使用 stub/公开无敏感样本；不得把 API 凭据写入日志或审计产物。

## 每项审计的最小证据包

```text
audits/<audit_id>/
  source_lock.json
  entrypoints.md
  field_flow.json
  static_hits.json
  projection_test.py
  projection_test_result.json
  differential_test_result.json
  finding.md
  evidence_manifest.json
```

`evidence_manifest.json` 必须含每个文件的 SHA-256、执行命令、退出码和审计者。

