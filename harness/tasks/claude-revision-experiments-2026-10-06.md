# Claude整改后的新实验

- 用户授权：2026-10-06“那你也把实验也做做”。关联F-PAPER-002，in_progress。
- 当前分支codex/claude-review-repairs；保留历史raw、旧默认、用户未提交稿件/模板及第三方工作。
- 执行范围：固定180案例的四个normal-prompt授权条件720行；既有60嵌套案例三个stress regime180行；四类合成场景×policy/full×Pro/已批准Flash16行。Gemini暂缓。本地模型仅可先做可用性检查，不阻塞主线。
- 官方端点仅推理公开AgentDojo/合成M3任务，Git忽略配置由程序在当前进程读取；禁止正文公开、真实工具和external effects。
- 新计划、新work key、新输出outputs/experiments/claude_revision_v1；失败与未知不填零，已有响应不重试，未响应仅显式单项恢复一次。

## 实施步骤及验收

1. 新实验计划/最小runner复用CorrectnessRuntime和execute_one；显式corrected_v2和exact_target_v2，旧默认不改。
2. 接通三个stress regime，仅改变Guard授权；四个主条件提示一致normal。修复后合成控制走同一Live循环和run-local tracker。
3. 定向测试计数、参数、隔离、版本、前缀、断点不重跑；12正式前缀通过outcome-blind门后扩展900行。
4. 每任务最多8请求（合成最多3），timeout180秒、temperature0、max_tokens512；DeepSeek最多两个工作项并发；HTTP自动重试零。身份/字段/安全异常立即停止。
5. 一次性分基准统计、原始分子分母、未知上下界、配对比较与表图；报告目录、实际进度、故障及边界。更新Harness并范围提交推送。

## 现场确认

- 起点f5edcafd6fe201c614341f92caadfd7d8e0e9627；修复代码已提交。没有活动Python实验进程（仅元数据检查）。
- 官方最新updates确认V4 Pro继续服务；Flash为V4.1，旧别名不作为新模型。实测精确返回身份仍须前缀确认。
- 不运行Full Harness、历史递归验证、旧统计重算、论文编译、盲测或大型新研究。

## 实际执行记录

新增runner与916行新计划已生成；normal提示固定，三个stress regime仅改变Guard授权，合成控制显式corrected_v2。

- 初次5项失败是混合计划基准标记问题，已修正并记录failure-log。最终69passed/1deselected（旧48×6宽烟测），23.60秒；Ruff通过。
- 命令：`F:\robot\Anaconda3\python.exe -B -X utf8 -m pytest -q tests/unit/test_claude_revision_v1.py tests/unit/test_correctness_runtime_v1.py tests/unit/test_correctness_followup_v1.py tests/unit/test_claude_runtime_integration.py -k 'not all_48' --basetemp=harness/tmp/pytest-claude-revision-fixed`。
- 定向pytest使用mock传输，0模型调用；下一步12正式前缀与16合成模型行。本文件尚不构成主矩阵已完成的证明。
