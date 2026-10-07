# 当前四主图与稿件接入完成记录

开始：2026-10-07；完成本切片检查：2026-10-08。这是实施报告，不是新实验计划。

## 实际完成

从已有分析缓存生成四张当前主图，每张包含PDF、SVG、PNG，共12个文件。英文、中文Markdown与当前LaTeX入口均已接入。此前五图保留为历史补充图S1–S5；原图和旧实验原始记录没有覆盖。

|主图|文件前缀|回答的问题|解释边界|
|---|---|---|---|
|1|current_01_boundaries|授权、提案、防护判定、模拟执行和离线评价如何分开|边界说明，不是有效性证明；精确目标是离线目标派生的理想对照|
|2|current_02_authorization|改变授权对象后正常任务完成率如何变化|左侧为Wilson观察区间，右侧为Newcombe任务配对差区间；不能混用|
|3|current_03_calibration|同期无防护、policy、full与配置VIGIL的安全和效用如何比较|基准端点分开；未知不填零，ITT识别范围不是置信区间；VIGIL不是完整官方默认实现|
|4|current_04_restrictions|正常任务首次限制与流程终态有何分布|描述性事件分类，不是已判定根因；ASK/DENY事件负担见主表2|

policy是仅权限检查；full是完整运行时模块；ASK表示等待确认，DENY表示拒绝；ITT表示所有计划项留在分析分母。图件与稿件同时保留这些指标之间的区别。

## 来源与目录

所有路径相对于主项目E:\M3_PI_Guard_test：

- 绘图源码：scripts/current_evidence_figures.py。
- 本目录：当前四图的三个格式和本说明，主文使用这里的图。
- 授权缓存：outputs/experiments/claude_revision_v1/analysis.json，900条授权分配及16条合成控制。
- 同期缓存：outputs/experiments/research_followup_20261006_v1/calibration/analysis.json，480条分配。
- 原因类别缓存：outputs/experiments/research_followup_20261006_v1/diagnosis/analysis.json，300条去重诊断记录；图4只用240条主良性工具分配。
- 英文、中文与补充Markdown：docs/research/paper_v2/manuscript/。
- 当前模板入口：LaTeX通用模板/数模通用模板.tex；对应PDF为同名文件。
- 正式LaTeX与补充入口：LaTeX通用模板/M3_PI_Guard_JISA/。
- 本次排版预览：outputs/manuscript/previews/current_evidence_20261007/。日期表示切片开始日；这里只是派生预览，不是研究原始结果，不上传这些检查图片。
- 历史五图来源：outputs/experiments/incremental_empirical_v1/figures/。LaTeX独立包内的必要图副本保留。

没有新增统计推断，没有重跑模型或原始实验，没有调用API。图的数字和区间直接读取现有缓存；未调用历史分析器、Full Harness或递归证据验证。

## 修复的实际排版问题

1. 图3分数文字越界、图2/4图例碰撞：调整画布和留白，未缩小字体或改变数字。
2. LaTeX补充入口原只引用S1–S12：补齐S13–S20及历史五图，避免“文件已生成但PDF没收录”。
3. 旋转宽表：拆为竖版续表，各部分重复前两列和原始行编号，保留全部数据列及数值。表格不使用旋转、缩放盒或scriptsize。
4. 续表的链接目的地重复：为各部分设独立链接，保持同一个表号和一个主标签。
5. 长条件名溢出：为英文词表斜线增加可换行位置，为长词增加排版断词；数字分数不拆开。
6. 当前图不应漂移到历史结果段：增加浮动图边界，四图在当前结果范围内闭合。
7. 页码检查误报：用实际基线而不是字体字框上边判断页脚；新增负例仍拒绝左侧、旋转和正文数字。没有隐藏真正的页码问题。

## 实际验证

- 五组定向pytest：43 passed。范围为新绘图、英中图表接入、补充保留、LaTeX生成和页码检查。
- 上述修改的五份脚本和五份测试：Ruff通过。
- 四个源PDF：最小字形9pt，文字碰撞0 fail / 0 warn；实际逐图查看。静态绘图检查器的四个代码模式识别失败仍记录，不冒称该工具通过；最终字体、格式和轴区由可执行检查验证。
- 当前三个PDF编译exit 0；114页结构检查未见空页、旋转、越页文字、页码错位、缺字、未定义引用或Overfull。逐页联系图及当前图表、补充宽表的放大页已查看。
- 模板审阅PDF：51页，69条导航，最低可见文字8.229pt。
- elsarticle正式稿PDF：39页，68条导航，最低可见文字8.229pt。
- 补充PDF：24页，最低可见文字8.635pt；20表、5历史图。补充表不是章节，因此不把零章节书签误报为正文结构丢失。
- 三PDF作者元数据为空。普通文字为Times New Roman；CMSY只用于数学符号。
- 缓存分析与原始结果的范围Git差异为零；没有用这次版式修改改变科研结果。

现有PDF技能的打包运行时入口在本机不可用，未制造成功回执；使用项目已安装的XeLaTeX和既有PyMuPDF检查，缺失工具不作为已通过项。

## 可复用命令

在E:\M3_PI_Guard_test运行；Python为F:\robot\Anaconda3\python.exe，不设置永久环境变量：

    F:\robot\Anaconda3\python.exe -X utf8 -B -m scripts.current_evidence_figures
    F:\robot\Anaconda3\python.exe -X utf8 -B -m scripts.build_lean_paper_manuscript --sync-chinese-figures
    F:\robot\Anaconda3\python.exe -X utf8 -B -m scripts.build_lean_paper_supplement --markdown-only
    F:\robot\Anaconda3\python.exe -X utf8 -B -m scripts.build_jisa_latex
    F:\robot\Anaconda3\python.exe -X utf8 -B -m pytest tests/unit/test_current_evidence_figures.py tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_build_lean_paper_supplement.py tests/unit/test_build_jisa_latex.py tests/unit/test_check_jisa_pdf_layout.py -q

PDF编译使用已安装的D:\TeXLive\texlive\2026\bin\windows\latexmk.exe，参数为-xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error -cd，依次指向三个入口。只在该命令进程中补充TeX可执行目录，不改永久PATH。

## 尚未完成

这次实际完成图件、接入、宽表与当前PDF版式，不等于研究或投稿结项。随后60个正常任务的受信意图解释已完成，见[逐任务报告](../trusted_intent_review/report.md)和同目录review.csv；新增9项定向测试/Ruff通过。最终科学方法与主张审查仍待。旧研究保留原定义，不能事后当作实际越权效果证据。未完成新模型、原生动态基准或跨厂商研究，不能宣称领先、首次、唯一或普遍泛化。全文历史叙事仍较长，当前PDF可读不等于已完成最终正文压缩。四图/PDF阶段提交d71b1f9已推送并核对远端同名分支一致。

可信度：9/10。依据为缓存、定向测试、实际编译和渲染；剩余科研解释不列为已完成。
