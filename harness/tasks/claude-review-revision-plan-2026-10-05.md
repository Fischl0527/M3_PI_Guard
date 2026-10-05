# Claude 审核核对与整改计划

日期：2026-10-05。关联 F-PAPER-002。状态：规划交付完成，修复/实验/论文仍未完成。

## 范围和验收

- 阅读docs内两份Claude报告，区分审核个人判断、已复现缺陷、历史证据和未提交补丁。
- 交付普通Markdown整改计划，包含优先级、对应路径、有限实验、统计、论文/LaTeX、排期和验收。
- 只修改计划、文档入口和最小Harness状态；不修运行代码、不调用API、不改raw、不编译论文。
- 保留已有dirty源码、文稿、第三方和模板资产；Git仅包含本轮文件/状态新增段落。

## 分析与计划

- 2026-09-21缺陷报告修正了2026-09-20乐观评价的授权结论。
- 本机直接调用实际_exact_authorization和ExactGoldAblationMonitor，不使用第三方重建授权：30个M3良性任务只给答案参数时30全允许，补齐必填正文等字段后仅3全允许。
- 模糊请求经未提交generic-v2编译后requires_confirmation=true，但同提案corrected监视器在policy-only为ALLOW、full为ASK，故修补尚不能接正式试跑。
- 已有followup记录20离线+16模型任务，包括missing_classification下full仍有模拟危险效果；本次只读，不新增运行。
- 历史Public汇总6873条，direct旧阳性323、失败未知569、复合ITT阳性892。不能称修正版实际效果。
- E6为单块诊断，Gemini未准入；论文摘要/结论仍有受缺陷影响的解释。引用键实际24、Bib39，不沿用旧18快照。
- 本地模型清单存在；RTX4060 Laptop显存8188MiB、物理内存15.63GiB。没有推理资格或吞吐测量，计划仅建议补充。
- 实施建议详见docs/research/paper_v2/Claude审核整改计划_2026-10-05.md；主线900新同期执行+最多16有界开发回归，本地240条可选。没有生成新runner命令或宣称已执行。

## 本次实际验证

- `F:\robot\Anaconda3\python.exe -B -X utf8 -`：stdin内联读取固定30案例，通过项目原构造函数和监视器计算上述30/3/27，exit0，无网络/文件写入。
- 同解释器另一个内联诊断：构造send_message模糊规则和synthetic额外目标，打印policy ALLOW/full ASK，exit0，不执行工具。
- 同解释器只读现有JSON/Markdown：核对followup、历史汇总、活跃引用键和feature状态；未重算历史研究。
- `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader`及Win32_ComputerSystem只读查询：检查本地可选复现资源。
- 交付检查：计划501行、9个链接目标均存在且在Git跟踪，5个仅本地未发布来源明示路径；Harness JSON有效且F-PAPER-002仍in_progress，scoped git diff --check通过。
- 未运行pytest/Ruff/Full Harness：没有修改实现，本次不是修复完成验收。未运行LaTeX、API、历史重放或哈希包。
- Git暂存current-task只加入本轮规划段落；最初手写管道补丁上下文检查失败，改按实际索引文本生成UTF-8差异后check/apply均为0，未暂存此前未提交状态段落。见既存failure-log。

## 下一步与边界

用户确认实施后，优先以失败测试修三项P0。后续正式实验、稿件重建另按计划执行；作者信息留空，Gemini仍暂缓。

本任务的完成只代表审核核对与计划交付，不把F-PAPER-002设为verified。
