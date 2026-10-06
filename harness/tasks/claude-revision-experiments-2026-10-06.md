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

## 本轮实际完成

- 12正式前缀门passed，12可解析；10completed/2max_steps，后续只执行888pending行。
- 授权矩阵900/900：795completed、60max_steps、45parse_failure；合成16/16全部completed。两个runner均exit0，无自动/人工重试，无成功重复执行。
- 单次分析exit0：916唯一终态、1796官方请求、1,712,733tokens；已知峰时费用估计CNY4.35603144（不是账单），本轮usage完整。模型身份、请求ID/digest/responseID、请求次数上限和安全边界检查通过。
- 合成Pro/Flash同向：policy私有受限/缺分类发送unsafe；full分别DENY/ASK；公开/归档任务完成。主矩阵攻击0/490，不作防护增益结论；AgentDojo良性auto2/30、exact policy13/30/full11/30，M3-v2auto policy16/30/full17/30、exact14/30/16/30。
- 统计保留Wilson/配对Newcombe/10k底层任务聚类bootstrap/按基准端点Holm；经验bootstrap退化不报告[0,0]。原始危险效果与unsafe-or-failure分别报告。
- 后续定向验证55passed；最终统计9passed，Ruff与4源内存编译通过，图目视检查；均非Full Harness，测试批次有重叠不相加。
- 报告outputs/experiments/claude_revision_v1/report.md，表CSV、图PNG、analysis.json及两份raw同目录。临时M3沙箱在每任务结束清理；AgentDojo内存副本/合成邮箱均无真实connector。
- 本地11434服务不可达，240开放模型项未执行；Gemini继续暂缓。没有论文改写、盲测、历史重放或新大型研究。没有活动实验进程。本实验子阶段完成，F-PAPER-002整体in_progress。
