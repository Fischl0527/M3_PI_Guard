# docs 文档更新与合并

日期：2026-10-09。状态：文档整理verified；范围提交、推送及PR交付接续执行。

## 目标与范围

读者能区分当前运行指南、当前修复后证据、论文工作稿和历史材料；不再被七月的 test1、旧74,760矩阵、盲测或旧80分门槛误导。合并重复说明，保留原文归档和原入口兼容。

允许修改 docs 内的索引、说明、检查清单、历史位置补充，以及必要的 Harness 状态。科研源文件、冻结/原始记录、论文正文、BibTeX、LaTeX、Word和PDF均不改。已有 dirty 的80-percent-v2、full_citation_refresh、legacy_evidence_impact不触碰。

## 检查发现

- 初始 docs 为117 Markdown、15 Word、14 PNG、1 BibTeX。全部Markdown先巡检标题、状态和路径，逐段核对活跃入口及其依据；不声称重新审查15个历史Word正文或全部论文。
- 根目录综述、移交、架构、证据索引和清单仍使用七月状态；研究稿README的26页/8,148词被后续27页/8,256词替代。当前状态以10月报告/结果为依据。
- 运行手册仍以旧比赛回放为默认，还称Python3.12为最低版本；已完成限定包实测支持3.10.12。不能把限定包资格推广到所有历史入口。
- 全目录第一次链接巡检的45个报警含Windows绝对路径行号误判；需修正检查后再报告真实缺口，不把报警数冒称真实断链数。

## 执行计划与验收

1. 原入口历史全文归档，当前综述合并架构/交接状态；旧架构/交接/运行文件改短入口，不删历史。
2. 更新README、数据说明、证据索引与投稿检查清单，当前修复后900/480/16/60与历史E1–E6分开；不重新推断统计。
3. 增加research/paper_v2单一导航，历史计划只分类，保留内容；维护输出目录说明及已安装环境入口。
4. 检查本地Markdown链接、文档目录类型、变更范围和JSON；用独立读者问题检验可理解性。无代码行为变更，不重跑pytest/Full Harness/API/论文构建。
5. 只提交本轮文档与状态，保留用户dirty；正常推送自身研究分支，不再次覆盖历史。用户追加确认Git+PR，目标Alysia163/RedTeam_LLM_Security:new-test；只建PR，不直接改目标或自动合并。

## 实施与实际验证

- 七份旧根入口Move-Item整份保留在docs/archive/entry_snapshots_202607；先确认原文件未修改、目标不存在且在指定归档内。当前架构/交接/运行改兼容导航，综述合并当前解释。原文与整理前Git版本逐份文本比较7/7一致，不生成hash。
- 重写docs/README、research/README、新增paper-v2导航；更新证据、数据、伦理、清单、论文索引/旧图表说明、outputs结构及历史迁移状态。不修改稿件正文或原统计，当前F-PAPER-002仍in_progress。
- 临时PowerShell只读检查：逐行剔除代码块，解析Markdown本地目标、Windows绝对路径行号与标题锚点，再用Test-Path核对。422本地链接0缺失、0坏锚点、0未闭合代码块；7原样快照排除新位置链接要求，1仓库外绝对路径不核验。最后新增直接tex入口确认Test-Path=True。检查范围包含已有未提交文档的链接，不改变其内容。
- 七快照比较命令为git show HEAD:docs/文件名，与ReadAllText归档原文规范化换行后进行区分大小写文本比较；首次Replace重载错误改正后7/7一致。未读取私密配置、签名或trace。
- 当前docs为127 Markdown/15 Word/14 PNG/1 BibTeX，仍无脚本、JSON、CSV；feature_list.json经ConvertFrom-Json有效。活动改动空白检查通过；暂存后的完整检查提示两份原样快照5处继承的Markdown硬换行双空格，保留原文并明确披露，排除这两份快照后的检查exit0。Git的LF→CRLF提示保留，不批量换行。
- 新上下文Reader Testing回答八个接手问题，唯一缺口是未明示主文tex；修正直接链接后PASS。此为模型读者检查，非独立同行评审。
- 本轮仅文档及必要Harness状态，无程序行为变化；因此不运行pytest/Ruff/编译/Full Harness/API/历史统计重算。只做与修改直接相关的检查。

## Git与剩余边界

沿用codex/claude-review-repairs，origin指向Fischl0527/RedTeam_LLM_Security。PR目标new-test已由用户确认；远端基线e81ac385与本轮前HEAD相同，可形成仅本轮的审阅差异。先提交推送，再创建PR，回执另记；不把原16行用户current-task、80-percent-v2、full_citation_refresh、legacy_endpoint以及模板/子模块等dirty一并提交。

报告docs/文档整理报告_2026-10-09.md。历史Word正文未重审、期刊/JCR未重新外部核验、论文未重编译；文档整理完成不代表投稿完成。
