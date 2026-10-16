# 参考论文编号与校译工作量评估

## 目标和范围

- 用户指定 `docs/文档资料`，要求修正 Google 翻译错误并给未编号论文补齐编号；若全文校译耗费过大，允许放弃。
- 实测顶层39份PDF、20篇论文；19份中文PDF共363页，其中15份没有可提取文字层。英文PDF共378页；部分英文PDF也不能提取文字。本次按用户条件跳过全文校译，不声称正文纠错完成。
- 仅将三组中英文PDF接续编号为18–20，沿用 `编号_题名 [中文/英文].pdf`；已有01–17、17份原始备份、阅读笔记保持原状。
- 对应F-DOC-004仅验收编号整理；必要状态追加、Obsidian最近文件列表中六个旧路径同步。科研代码、论文投稿稿、实验、Git暂存/提交/推送不在范围。

## 分析与计划

1. 已读取目录和PDF页数/文字提取统计，对照三个英文首页确认完整题名。
2. 批量执行前验证六个源文件、目标路径和无同名冲突；只做同目录非覆盖改名。
3. 直接比较改名前后文件字节摘要、页数、论文对照编号；既有PDF及备份不变，原Git暂存不变。
4. 定点更新Obsidian六条路径和Harness状态；验证JSON和范围空白。

## 改名映射

| 原文件 | 新文件 |
| --- | --- |
| AgentDojo A Dynamic Environment to Evaluate.pdf | 18_AgentDojo - A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents [英文].pdf |
| 中文翻译AgentDojo A Dynamic Environment to Evaluate.pdf | 18_AgentDojo：评估大语言模型智能体提示注入攻击与防御的动态环境 [中文].pdf |
| Not what you’ve signed up for Compromising Real-World.pdf | 19_Not what you've signed up for - Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection [英文].pdf |
| 中文翻译Not what you've signed up for - Indirect Prompt Injection.pdf | 19_非你所愿：通过间接提示注入攻陷现实世界的大语言模型集成应用 [中文].pdf |
| Progent Securing AI Agents with Privilege Control.pdf | 20_Progent - Securing AI Agents with Privilege Control [英文].pdf |
| 中文翻译Progent_ Securing AI Agents with Privilege Control - Progent Securing AI Agents with Privilege Control.pdf | 20_Progent：通过权限控制保护AI智能体 [中文].pdf |

## 验证

- 已完成并核验；F-DOC-004仅指编号整理。
- 六份PDF改名成功；顶层39份PDF覆盖01–20，19个中英文对照组；17仅有英文原版，未伪造中文版本。
- 全目录56份PDF（顶层39份及17份原始备份）在改名前后逐文件SHA256相同；摘要仅在内存比较，不新建摘要清单。新18/19/20各组页数仍为26/33/17。
- Obsidian最近文件列表仅替换六条路径，均指向实际文件；JSON解析通过，其余历史路径/用户界面状态不改。
- 原17条Git暂存记录在改名前后逐字相同；其他feature对象与起始HEAD语义相同，F-PAPER-002保持in_progress。
- 首次改名命令在解析阶段失败：PowerShell将题名中的弯单引号视作字符串定界符；该命令未执行任何改名。改用双引号包围明确文件名后重试，不更改PDF内容。
- 不运行pytest、构建或模型API：本任务不涉及可执行行为，PDF正文不改。

实际执行采用 `python -X utf8 -c` 内联PyMuPDF统计页数/文字和复验编号、页数、JSON、路径；同目录移动采用 `Move-Item -LiteralPath $sourcePath -Destination $targetPath` 对上述六组明确路径执行，无Force。PDF内容比较采用 `Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256`；暂存比较采用 `git -c core.quotepath=false diff --cached --name-status`。最后运行下列范围空白和JSON检查。

```powershell
git diff --check -- harness/tasks/reference-paper-numbering-20261011.md harness/state/current-task.md harness/state/progress.md harness/state/task-history.md harness/state/session-handoff.md harness/state/failure-log.md harness/features/feature_list.json
python -X utf8 -c "import json,pathlib; [json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['harness/features/feature_list.json','docs/.obsidian/workspace.json']]; print('JSON PASS')"
```

## 结束状态

- 正文改动0；仅六个文件名和必要路径/任务状态更新，无Git提交或推送。
- 全文校译按用户成本条件跳过，后续仅在用户明确选择单篇或提供可编辑文字版时另行开展。
