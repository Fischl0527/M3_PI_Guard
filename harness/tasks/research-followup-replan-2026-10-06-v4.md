# 当前成果后的综合评估与后续计划 v4

日期：2026-10-06。关联：F-PAPER-002。状态：规划文档已交付且检查通过；科研整体仍 in_progress。

## 目标、范围与验收

用户要求阅读 `D:\下载\M3-PI Guard 后续研究与论文推进计划.md`，综合当前项目、参考此前Claude计划，输出新Markdown到对应文档目录。

只允许本轮新计划、此任务及必要Harness记录；保留旧计划、下载原文件、raw、统计、用户dirty和模板资产。不运行API/服务/实验/统计重算/Full Harness，不修科研代码或授权逻辑，不改论文或编译PDF，不移动删除，不Git提交推送。

验收：区分已完成900/16/480、延迟修复及已更新英中核心与尚待主表图/PDF；必要研究解释与可选新批次有明确条件、样本、变量、失败和输出范围；不继承下载计划中的旧快照或预设有利结论；Markdown链接/围栏/格式、feature JSON与范围diff检查通过。

## 本轮读取和判断

- 已读AGENTS、架构、权限、开发规则及最新current-task/progress/handoff；本地HEAD a44281c，分支codex/claude-review-repairs，origin RedTeam_LLM_Security。相关实验Python进程的只读筛选未列出活动进程，不停止任何进程。
- 使用academic-research-suite实验规划技能，完整读取根技能、实验WORKFLOW及代码计划模板；用户要求综合提出新计划，沿用已有三个RQ，不引入额外审批、签名或跨模型审核。
- 完整读取下载文档及Claude整改计划/修复报告，核对900+16与480报告、JSON摘要、300诊断、延迟说明、AgentDyn原参考/离线控制及最新论文入口。
- generic-v2源码有未解析必填安全范围即删除整条许可的分支；该行为不能直接判定为60任务均有编译bug。exact_target_v2及current正文已明确目标/内容角色与oracle边界。
- 当前英文主要叙事/当前Results优先与中文核心已修订；现存英中仍八张历史主表，主图/PDF未同步，避免把v3的旧待办照搬。
- 官网核验AgentDojo为NeurIPS2024正式论文；AgentDyn v3按预印本记录使用。JISA官方范围读取403，学校分区未查，不认证当前SCIE/JCR。
- 一次文件定位用了不存在的abstract.md；改用目录实际存在的abstract_shell.md进行入口确认，没有修改文件或重复执行实验。

## 实施与验证安排

1. 新建独立v4，保留v1/v2/v3；以已完成和真实缺口重排优先级。
2. 必要线为当前主表图/PDF与60受信意图核对；360新修复验证、180独立模型、108动态环境均为条件性建议，不在本轮开跑。
3. 只做文档检查与必要状态记录；科研整体状态不改成verified，当前持续实施任务保留。

## 实际验证

- PowerShell读取新计划并检查Markdown：297行、10个本地链接、0断链；2个代码围栏成对；0尾空格、0替换字符。计划文件存在。
- `Get-Content harness/features/feature_list.json -Raw | ConvertFrom-Json`通过，F-PAPER-002仍为in_progress。
- `git diff --check -- harness/state/current-task.md harness/state/progress.md harness/state/task-history.md harness/state/session-handoff.md harness/features/feature_list.json` exit0。Git仅提示已有换行策略将LF转CRLF，没有为此改设置。
- 范围status核对：新增计划/任务与必要状态；其他dirty仍在，原16行current-task修改保留。没有改产品、实验、论文、原始数据或统计。
- 没有运行pytest/Ruff/构建：本轮没有可执行代码或实验语义变化，文档检查不冒充科研复现。没有API、服务、模型、历史统计或Git提交推送。
- 下一次实施优先缓存主表图/最新PDF与60任务意图解释，继续既有执行任务；本规划完成不关闭科研整体或擅改持续目标状态。
