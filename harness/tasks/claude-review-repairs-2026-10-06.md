# Claude审核问题：实现修复与定向验证

- 日期2026-10-06；用户已要求修复Claude指出的问题，包含相关授权逻辑修正。
- 关联F-PAPER-002，状态in_progress；分支codex/claude-review-repairs。
- 依据docs/research/paper_v2/Claude审核整改计划_2026-10-05.md及两份原审核。
- 本子阶段修复P0-A精确目标对照、P0-B模糊权限、P0-C缺分类受限动作、P0-D事件保存。旧授权代码/实验raw/历史统计只读。科研结论与后续实验不足不伪称已补齐。
- 仅授权/来源/运行配置与保存相关Python、对应定向测试、普通MD报告和现有Harness；不改第三方、字体、冻结计划、LaTeX、密钥，不API/Full Harness/递归审计。Gemini继续暂缓。
- 现有未提交generic-v2、correctness_runtime和followup工作先复核再集成，保留无关稿件/模板/第三方改动；不覆盖原文件。

## 小步计划与验收

1. 公共接口复现三个缺口，保存实际失败结果；新对照保留旧exact_gold语义。
2. 精确目标版本使用明确工具字段角色和完整接口校验；目标/额外安全字段/类型/必填/顺序不得被子集比较绕过。
3. unresolved授权在policy/full中都不能自动执行；明确受信动作和正文合法生成不被一律拒绝。
4. 数据流保护适用且可信分类缺失时新修复配置ASK；公开数据/内部归档不误阻，旧配置仍可复现历史负面结果。
5. 新配置显式注入已有运行器，逐步分类、Guard/执行/未知和评价摘要保存，不复制运行器。
6. 仅受影响pytest/Ruff/内存编译与离线模拟集成；报告哪些问题修复、哪些科学证据仍缺失，更新状态并范围化Git推送。

## 已知风险

- 从旧聚合结果无法重建真实历史拒绝原因；新测试不是历史模型TCR修正。
- 模糊目标与可自由生成的正文应区分，不能靠关闭确认模块扩大权限。
- exact_target_v2是显式oracle对照，不可作为非oracle系统部署权限或隐藏读取gold。
- 无新模型结果，不宣称修复后安全/效用增益或跨模型有效。

## 执行记录

### 分析与修复

- 公共接口复现：原generic-v2对未明确频道在policy-only下ALLOW；旧full合成探针missing_classification发送后unsafe=True。初始4回归失败后按原因收口编译权限。
- 新ExactTargetMonitorV2使用受信实现字段角色/接口完整性/精确安全参数，保留重复调用序列及判定—执行绑定；没有修改旧exact_gold。原全局时间/来源/数据流限制可显式附加，派生oracle只给Guard。
- RuntimeMonitorCorrectedV2接入run-local可信分类tracker，受限动作missing_input返回ASK；即使原动作要求确认，也不能批准绕过缺分类。四类真实模拟邮箱状态与Guard相符。
- 同一共享运行器增加明确factory注入，不复制整套实现；事件保存隔离/执行/未知/请求摘要，评价细节读写保留。计划和编译/runtime/版本/授权制度必须一致，避免新配置套旧任务。
- 整合既有未提交generic-v2和合成followup源码/测试供回归使用，已复核和测试；不调用其模型批次。无关旧endpoint恢复、稿件、模板及第三方dirty不提交。

### 验证命令及结果

位置E:\M3_PI_Guard_test；环境F:\robot\Anaconda3\python.exe3.13.5。

```powershell
& 'F:\robot\Anaconda3\python.exe' -B -X utf8 -m pytest -q --basetemp=harness/tmp/pytest-claude-review tests/unit/test_claude_review_repairs.py tests/unit/test_claude_runtime_integration.py tests/unit/test_generic_policy_corrected_v2.py tests/unit/test_correctness_runtime_v1.py tests/unit/test_correctness_followup_v1.py tests/unit/test_paper_v2_live_condition_runtime.py tests/unit/test_provenance_corrected_v1.py tests/unit/test_correctness_effects_v1.py -k 'not all_48 and not frozen_qualification and not qualification_artifact and not pinned_promptguard_live'
& 'F:\robot\Anaconda3\python.exe' -B -X utf8 -m ruff check m3_core/policy_compiler_corrected_v2.py m3_guard/tool_contracts_v2.py m3_guard/runtime_monitor_corrected_v2.py experiments/paper_v2/exact_target_ablation_v2.py experiments/paper_v2/correctness_runtime_v1.py experiments/paper_v2/live_condition_runtime.py experiments/paper_v2/correctness_followup_v1.py tests/unit/test_claude_review_repairs.py tests/unit/test_claude_runtime_integration.py tests/unit/test_generic_policy_corrected_v2.py tests/unit/test_correctness_followup_v1.py
```

- 最终151passed/4deselected/1warning，0fail，10.93秒。四项是旧48×6烟测和三历史资格/缓存产物核对，不属于本轮修复必要验证；warning为第三方Pydantic旧config弃用，保留不修。
-11指定Python源在内存compile(...,'exec')通过；Ruff全部通过。没有新依赖、环境变量或生成历史审计包。
- 固定30个M3良性案例同目标、补齐接口的提案：旧3/30全ALLOW，新30/30。是离线permission-only，不是模型TCR或旧0/30原因重建。
- 失败优先负例与修正记录见failure-log；补充捕获枚举/非法schema、异常未知、后加限制与版本不一致；测试夹具identity不合旧格式时改夹具不放宽校验。

### 完成边界与交付

- 实现子阶段验收满足；F-PAPER-002整体in_progress。新授权矩阵、16新模型控制、本地/独立任务证据和后续双语/LaTeX同步没有执行。
-0官方API/Full Harness/历史递归回放/科研统计重算/论文构建；现有结果和作者字段不动。Gemini继续暂缓。
- 报告docs/research/paper_v2/Claude审核修复报告_2026-10-06.md；测试临时产物仅harness/tmp，不新增正式outputs结果目录。
- 新分支codex/claude-review-repairs，起点397a879a16f986d2db20defb73da95d0488a4161；origin=RedTeam_LLM_Security。待范围化暂存检查、提交并推送，再补实际回执。
