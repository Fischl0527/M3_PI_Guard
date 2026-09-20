# 正确性修复与三模型开发试跑

状态：verified_development_substage。本批已结束；用户于2026-09-20批准执行；F-PAPER-002整体仍in_progress。

## 2026-09-20 用户范围调整与最终交付

- 用户要求先忽略Gemini，完成其他部分；本次按原开发批范围收尾，不解释为扩展论文研究授权。
- 原计划非Gemini均已交付：正确性修复、离线检查、Pro288/Flash288、分层统计与MD报告。
- 独立只读复核确认同动作配对已在runtime的READ/SEND/FINAL测试和policy规则同提案测试实现。
  在原报告补验收映射，避免“后续建议”造成未实施的误解；不新建回放脚本/数据包。
- Gemini恢复记为deferred_by_user（暂缓，不是完成），原5响应/3纯503/280not_run及新503诊断不动。
- 本次仅文档与状态修改；不模型调用、不统计重算、不重复已通过测试、不Full Harness、不改论文。
- 验收只查新增文档链接、数值与既存analysis一致及Git范围；提交推送origin/codex/q2-empirical-study。

本轮文档验收（未重新运行模型、单元测试或统计）：

- `Get-Content outputs/experiments/correctness_repair_v1/analysis.json -Raw | ConvertFrom-Json`：
  直接读取既存汇总，Pro/Flash各288项，与报告状态数一致；不是统计重建。
- `Get-Content harness/features/feature_list.json -Raw | ConvertFrom-Json`：有效JSON。
- 对两份report.md的本地Markdown目标逐项`Test-Path -LiteralPath`：17个链接、0缺失。
- `git diff --check`：退出0。`git diff --numstat -- experiments tests m3_core m3_guard m3_eval protocols outputs/experiments/correctness_repair_v1/analysis.json outputs/experiments/correctness_repair_v1/deepseek_pro/raw_records.jsonl outputs/experiments/correctness_repair_v1/deepseek_flash/raw_records.jsonl`：无变更。
- `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'"`后仅筛选correctness_runner_v1/gemini_correctness_recovery_v1：无活动匹配进程。
- `git remote get-url origin`与`git branch --show-current`：目标为RedTeam_LLM_Security、codex/q2-empirical-study。

## 范围和验收

- 显式 corrected_v1；旧默认路径、计划、原raw及论文不修改。
- 修复动作—资源绑定、同工具完整规则匹配、可信标签传播与匹配方向、确认历史保留。
- 区分越权提案、错误放行、隔离拒绝、实际模拟效果、任务完成和未知/失败。
- 公共四接口保持兼容；结果必须保存新评价细节；保留ITT和失败，不伪造零。
- 先跑定向pytest/Ruff/编译，证明正常任务完成、隔离拒绝与可观测模拟危险效果可区分。
- 48任务：AgentDojo攻击12/工具8；M3攻击12/工具8/无工具8。攻击从E6取历史富集样本；合法从180固定集取。
- 六条件：无防护normal/safe、policy normal/safe、full normal/safe；提示内容一致。
- Pro/Flash各288条；Gemini最多288条免费层，首429停新请求，不等待配额日。
- 各模型先5个分层任务×6=30条计入总数；Pro/Flash各并发2，Gemini并发1且15秒间隔。
- max_tokens512、temperature0、每条最多8调用、请求180秒；无自动重试，无fallback。
- 无响应工程失败修复后对应key最多补一次；已有响应终态不覆盖。
- 输出仅任务表、raw、分析/图表、report.md与内部忽略trace；不新建审计链/哈希包。
- 不触碰外部工具/真实副作用、第三方代码、模板资产、历史实验、E8或论文正文。

## 实施分工

1. 权限代理：版本化编译、规则匹配和确认状态修复及定向测试。
2. 来源代理：版本化可信标签/来源传播及定向测试。
3. 评价代理：版本化分离效果评价和未知语义及定向测试。
4. 根代理：显式注入、选样、并行runner、结果保存、统计报告、Harness与Git。

## 交付与验证记录

根目录：outputs/experiments/correctness_repair_v1/。
Git目标：origin/codex/q2-empirical-study。三个节点：修复测试、试跑结果、分析报告。
### 2026-09-20 启动前检查

- 官方模型/价格页 https://api-docs.deepseek.com/zh-cn/quick_start/pricing/ 已核对。
  旧V4 Flash已退役并转到V4.1；用户明确批准改用`deepseek-flash`，登记为
  DeepSeek-V4.1-Flash新模型复现，不改旧结果、本地凭据配置或Billing。
- 新模块六份定向测试131 passed，含48案例×6条件的288条离线全路径检查。
  全路径响应是测试替身，不是API或效用结果。
- 旧确认/runtime/边界回归71 passed、2 deselected；排除不涉及的PromptGuard测试，
  因本机既有模型缓存缺失，不恢复缓存或历史验证。
- 共享运行器只加可选factory注入；新配置绕过旧结果bool强制转换。
- 标签输入来自可信backend；本批private读取覆盖可能不足，不能据此称dataflow实证有效。
- 定向命令：`F:/robot/Anaconda3/python.exe -X utf8 -m pytest tests/unit/test_corrected_v1_policy.py tests/unit/test_correctness_effects_v1.py tests/unit/test_correctness_runtime_v1.py tests/unit/test_provenance_corrected_v1.py tests/unit/test_correctness_provider_v1.py tests/unit/test_correctness_analysis_v1.py -q`。
- 回归命令：`python -m pytest tests/test_confirmation_session_v1.py tests/unit/test_paper_v1_runtime.py tests/unit/test_paper_v2_runtime_invariants.py tests/unit/test_paper_v2_boundary_rejection_runtime_v3.py tests/unit/test_paper_v2_live_condition_runtime.py -q -k 'not promptguard'`。
- 并发runner专项检查进行中；本记录时尚未调用模型。

### 收尾结果

- 运行命令：`F:/robot/Anaconda3/python.exe -X utf8 -m experiments.paper_v2.correctness_runner_v1 --run-all`，退出0。
- Pro288与新V4.1Flash288完成尝试；Gemini8尝试、5条有模型响应，重复HTTP503后280未运行。
- 无重试；864唯一工作项，1119请求/1116HTTP200+3HTTP503，身份/在线字段/真实效果检查通过。
- 分析命令：`python -m experiments.paper_v2.correctness_analysis_v1`；一次分析生成3CSV/2PNG/JSON/MD。
- 两张图已目视检查；报告额外人工加入实测结论、修复说明与证据数字。重新生成通用报告会
  替换该人工前言，故最终版本以Git记录的report.md为准。
- 代码/计划000338f、原始结果b27b6d1已推送；最后报告/状态另作节点提交。
- 没有扩大实验或修改论文。低TCR、敏感标签未触发、Gemini不完整依旧是后续研究缺口。

### 2026-09-20 完成标准复核与局部补丁

- 独立只读复核发现后置条件/否定漏洞：`Write public/a.txt if needed`自动授予
  写权限；`Write public/a.txt, not public/b.txt`还授予b。先新增负例观察失败，
  再仅修正corrected编译器；条件与否定识别屏蔽资源名内的词。
- 沿用同工具混合肯定/否定时保守收缩的规则，显式应用声明不得绕过用户否定。
  不宣称通用NL理解；旧默认编译器、四公共接口、原计划/raw均不改。
- 补充重叠规则反向排列断言和真实执行/评分→append_row→read_jsonl完整保留测试；
  后者只替换HTTP边界，没有模型调用。
- 独立Verifier从`git show 7ec9345:m3_core/policy_compiler_corrected_v1.py`加载旧代码
  到内存，复用冻结plan的48个在线投影和FROZEN_GENERATED_AT，与当前完整manifest
  直接比较：AgentDojo20/20、M3-v2 28/28一致，0差异。无受影响API行，不重跑。
- 最终命令：`F:/robot/Anaconda3/python.exe -X utf8 -m pytest tests/unit/test_corrected_v1_policy.py tests/unit/test_correctness_runtime_v1.py::test_runtime_evaluation_details_survive_execute_save_and_read tests/test_confirmation_session_v1.py -q`，49 passed，0.54s。
- `python -m ruff check m3_core/policy_compiler_corrected_v1.py tests/unit/test_corrected_v1_policy.py tests/unit/test_correctness_runtime_v1.py`：通过；同三文件`python -m py_compile`：通过。
- 仅更新本报告与现有Harness状态并提交推送；不复算分析、重跑48×6旧smoke、Full Harness或扩展研究。
