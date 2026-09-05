# 授权诊断与E7a论文整合

日期：2026-09-05；关联F-PAPER-002；状态verified_manuscript_substage，整体in_progress。
Origin Skill: academic-research-suite / academic-paper (revision, fidelity).

## 范围与预定主张

1. 已有P0分区是观察性未完成状态，不追溯伪造旧Guard reason。
2. 512个新确定性探针只说明受控组件边界，不代表旧API输出或部署ASR。
3. E7a是96次官方模型提案、384个配对确认单元；只有许可，未调用effect backend。
4. 0/12至12/12的差异来自刻意过度约束对照，不证明通用效用、安全或full优势。
5. E2为合成场景、非原生AgentDojo；E8无模型结果。旧E6 Gemini仍diagnostic/NE。

## 实施与验证计划

- 修改规范Markdown章节、中文对照、BibTeX；生成器直接从已存analysis导出窄表。
- 不改老实验raw/统计；不改历史模板资产或dirty子模块；不产生Word。
- 补充Methods/Results和必要Discussion/Conclusion；保持章节大纲与旧数值。
- 定向pytest、Ruff、py_compile；重生成LaTeX并编译正式稿、审阅稿及兼容入口。
- 实际检查PDF字体、页面尺寸/旋转、底部页码、书签、缺字/溢出、全页缩略与关键页。
- 记录MD修订报告和outputs中QA目录；完成后Git提交并推送origin工作分支。

## 研究与工程边界

无API、新实验、Full Harness、历史递归重放、哈希包、外部效应或作者信息推断。
论文整体不因文稿更新而标为投稿就绪。新文献只核验新增3项的原始元数据与摘要。

## 完成与验收

- 英文Methods3.17/Results4.13/Table7及解释边界完成，中文MD同步；24个实际引用。
- E7表从已有analysis直接导出，强制permission-only声明；无后端调用不能报告TCR。
- 17个定向测试、Ruff、py_compile通过；三个受影响LaTeX入口完成构建。
- 审阅52页、正式59页、兼容52页、补充12页；两主稿QA errors=[]，111页缩略
  和新增关键页已视觉检查；母版/兼容稿逐页文本及书签一致。
- 表7表注拆页局部修复，原有字体/边距/页码/TeXstudio input保持；无新API或实验。
- 精确命令、原始结果边界与outputs结构详见
  `docs/research/paper_v2/manuscript/usability_manuscript_update_v1.md`。
- 本阶段Git范围为相关源码、公开文稿和Harness，目标origin工作分支；不纳入
  内部trace、无关dirty子模块、用户未跟踪模板资产或本地QA PNG缓存。
