# Gemini恢复：原48任务六条件开发试跑

当前处置：2026-09-20用户要求先忽略Gemini，故为deferred_by_user（用户暂缓），不再推进在线恢复。
本地修复已验证；历史在线状态仍为paused/diagnostics_not_passed，恢复整体未完成。关联F-PAPER-002。
以下批准计划与验证记录保留备查；没有新的用户指令时不得启动诊断、前缀或续跑。

## 已批准范围

- 原plan/raw只读，DeepSeek不运行，不修改论文。原Gemini288项：5已有响应永不重跑；280未调用attempt1；3纯503恢复attempt2。
- 新配置gemini_recovery_v1：max_tokens2048/reasoning_effort low；temperature0/JSON/180秒不变。
- 原默认512及DeepSeek保持兼容；本地2048校验只改恢复内存policy副本。
- 503不计重复程序错误；连续503等待60/120/240/300秒，第5次暂停；成功HTTP响应重置。429立即停止新请求。
- 无响应才可追加一次attempt；每原key累计最多8调用，旧失败调用必须扣除。HTTP库自动重试0。
- 身份、字段泄漏、真实effect、provider tools异常立即停；开放trace不自动重发。
- 独立Gemini入口，不依赖DeepSeek结束状态；并发1/请求起始间隔15秒。

## 实施与验证顺序

1. 参数/恢复/记录边界的定向pytest，Ruff和编译；先失败测试后修复。
2. 提交推送修复测试里程碑。
3. 六条read/write/final合成诊断（各2）；均正确身份、未截断、可解析才进入实验。
4. 原30前缀中只补25项，技术检查不依赖攻击结果；再执行其余pending项。
5. 新旧参数分别统计；配对只用同配置。未知/失败/未执行不填零。
6. Markdown报告、目录入口与Harness更新，提交推送结果里程碑。

## 所有权与风险

- 参数代理：gemini_json_client_v1、correctness_provider_v1及provider测试。
- 根代理：恢复入口、累计调用上限、定向测试、运行和Harness/Git。
- 分析代理：恢复分析器及其测试，旧结果不改。
- Google服务与low参数实际支持待六条诊断；失败就暂停，禁止盲目参数搜索。
- 输出：outputs/experiments/correctness_repair_v1/gemini_recovery_v1/；internal忽略。
- 不Full Harness、不历史递归验证、不追加研究/模型/日期重复。

## 验证与运行记录

代码0ac8631推送后，六条诊断的首条收到HTTP503且没有模型响应，立即停止。
剩余5条诊断及283项实验未调用。旧结果不变。不自动重试诊断、不盲目改参数。

- provider新旧兼容：`python -m pytest tests/unit/test_correctness_provider_v1.py tests/unit/test_paper_v2_gemini_json_client_v1.py -q`，72 passed。
- 恢复与原runner/runtime回归：`python -m pytest tests/unit/test_gemini_correctness_recovery_v1.py tests/unit/test_correctness_runner_v1.py tests/unit/test_correctness_runtime_v1.py -q`，42 passed；未调用模型。
- 独立复核确认283候选/25前缀和原5保护；新增open-trace/bool-attempt/累计cap测试后，恢复专项9 passed。
- Ruff与py_compile通过；不运行Full Harness。配置为官方固定Gemini，不静默删除low或切模型。
- 启动命令依次为同一模块 `experiments.paper_v2.gemini_correctness_recovery_v1` 的 `--diagnostics`、`--prefix-only`、`--resume-pending-only`。诊断不通过禁止后两步。
- 首条诊断命令当时exit0、passed=false；随后仅修复CLI为失败/暂停返回1并定向验证，未重发API。
- 恢复专项最终10 passed；实际发送2048/low确认，但实际模型支持尚未确认（无成功响应）。
- 分析相关39 passed，修正default path后最终恢复+分析联合33 passed；Ruff/编译通过。
- 正确嵌套目录生成报告/4CSV/2PNG/analysis；已目视图件，效果图无点表示无观测，不是零风险。
- 初版分析器误产出同级目录，修复并留回归测试；旧raw无修改。清理移动被工具策略拒绝，
  同级草稿未删除也不提交Git；有效报告只在correctness_repair_v1/gemini_recovery_v1。
