# 迁移错误复核和新分支修复

- 目标：修复迁移引入的问题，检查确认后提交并推送新分支。
- 分支：codex/directory-migration-fixes；起点3c32923；保留已有科研、论文生成器、模板和第三方dirty内容。
- 关联F-DOC-001；状态in_progress。必要验证：路径读写、成稿图链接、文档构建、归档位置与目录边界；不API、不Full Harness、不历史重算。
- 用户补充授权“迁移、环境和论文检查都修”：修复CaMeL基础Python缺失、当前BIB检查及生成器/主稿不同步；这些既存问题仍与迁移引入的问题分别记录。
- 不修改科研运行语义、历史原始记录或冻结导出；同步论文只使用已有结果并保留研究边界。

## 复现与分析

- 扩展定向检查（补充材料、英/中文Word、投稿材料、Lean分析）：31 passed/2 failed。
- 迁移遗漏：中文稿检查直接禁止全文中的 outputs/，五个有效图片链接误触发；应验证正文不夹带工程说明、并独立验证图片路径存在。
- 另一失败为引用数21的旧断言，而迁移前和当前英/中文稿实际均用24个引用；应保持科学内容不变，先分离既存问题与迁移问题。
- 三类可验证假设：图片URL误分类（已复现）；活动消费者路径漏改（继续测试实际构建）；未提交生成器与已保存稿件不同步（核对起点提交，不把dirty工作混入新分支）。

## 计划与验收

1. 对中文图链接遗漏做最小修复和真实路径回归。
2. 查活动读写路径、临时英/中文文档构建，以及已提交代码的独立验证。
3. 检查迁移的368个内容相同文件和归档目录，明确未执行迁移不是已修复。
4. 新报告及Harness状态，范围化暂存，推送新分支并核对远端。

## 验证

- 2026-10-06完成本轮软件/环境/构建验证；D盘归档单独未完成，不以旧保存成稿代替实际构建。
- 主检查：F:\robot\Anaconda3\python.exe -B -X utf8 -m pytest -q --basetemp=harness/tmp/pytest-migration-final，加报告第5节列出的15个测试模块，73 passed/18.50s。AgentSpec页码补入后文献+英中文DOCX三个模块17 passed。
- Ruff检查本次10个Python源/测试文件：全部通过；源文件内存编译、不产生额外证据包。
- 实际运行scripts.build_lean_paper_manuscript、英/中文DOCX构建器、experiments.paper_v2.incremental_figures_v1、scripts.build_jisa_latex，均exit0；图仅从已有analysis生成，未重新分析raw。
- 既有latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error -cd，主稿、原模板、兼容入口均exit0；补充材料入口无需BibTeX，编译exit0。检查器scripts.check_jisa_pdf_layout无错误：审阅55页67书签、正式61页66书签，空作者。
- 临时仅class/BST及当前审阅稿的包，0私有字体资产，实际编译55页67书签通过；已查看联系页和表8续表。Word结构/XML通过，本轮未额外WPS渲染。
- CaMeL旧联接下python -B导入camel.interpreter.interpreter、camel.pipeline_elements.agentdojo_function、agentdojo.agent_pipeline、agentdojo.benchmark成功；uv显式E盘cache-dir pip check报告120包兼容。
- 历史368迁移仍R100；冻结BIB导出及manifest、旧raw/protocols/release归档本轮diff为空；D两源存在、E两目标不存在。
- 本轮未API、未Full Harness、未递归历史验证，理由是用户限定范围与修改只涉及路径/环境/构建。
- 提交前从Git暂存区/已跟踪依赖导出80个必要文件至空临时目录，仅运行论文、LaTeX、文献三个模块：23 passed/0.53s；暂存源码逐字重现待提交英文稿。没有复制未提交科研源码、字体或原始矩阵。
- 10个改动Python文件内存编译通过；入口三文档3个本地链接有效；feature JSON、git diff --cached --check和范围排除通过。current-task仅本轮新段落暂存，既有16行未提交内容保留。

## 实施与失败修复

- 中文图片URL只作为资源路径验证，不再误判为正文工程描述；双语引用集为24个。
- 当前BIB含39条，旧34条构建记录保持只读。当前检查校验唯一键、必需字段及引用覆盖；保留显式历史校验入口，不把本地完整性检查冒充39条在线权威核验。
- AgentSpec DOI经ICSE官方页面与作者accepted PDF核验后补入。当前测试对缺字段、缺键和重复键均拒绝；历史写入入口拒绝覆盖新增文献的当前库。
- 论文已有生成器新增表8，却未同步4.14正文及7→8表数量约束，已补方法、结果与中英同步；corrected-v1与历史混合标签分开，不更改历史raw或统计数值。
- 实际Word含方法条件表1张+编号结果表8张，共9张，保存版本重建后检查，不把总表数当作编号结果表数。
- CaMeL缺失的3.10.12基础解释器已用现有uv下载到归档runtime/python，pyvenv.cfg明确改用新路径；旧runtime联接下启动及依赖导入通过，无永久环境变量。
- 模板class/BST原在本机但未被Git跟踪，补为必要源码依赖；class对可选私有字体文件提供系统字体回退，原字体文件不上传、不删除。审阅入口仍统一Times New Roman。
- 未修科研权限逻辑、未调用模型、未重新分析历史大文件。D盘迁移仍因先前工具策略拒绝未执行，已向用户请求资源管理器迁移，绝不绕过。
