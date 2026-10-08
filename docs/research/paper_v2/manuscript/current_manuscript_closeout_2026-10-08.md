# 当前稿科学口径与正文收束执行报告

日期：2026-10-08。状态：本轮实际执行完成；科研整体和投稿仍为in_progress。

后续同日实际核对已完成：24活动引用，补10个arXiv DOI、1项分类与DRIFT作者姓名，
保护书目缩写；按已有分析明确四项/三项Holm家族，作者审阅改为待投稿前确认。
当前英中稿和两PDF已同步；最新英文正文8,256词，模板35页/正式27页，
45定向测试、Ruff、实际编译及受影响页检查通过。详见
[当前引用与内部方法复核](citation_compliance_active_v1.md)。
**以下1–6节保留前一稿件节点的回执和计数，不是后续修订后的最新页数/词数。**

这不是新计划。已修改源文件、生成独立精简英中稿、实际编译PDF并查看页面，没有新增模型实验。

## 1. 本轮做完了什么

1. 将固定60任务受信意图审查纳入方法、结果、讨论和结论，明确事后解释、非盲审、无独立评审一致性。
2. 修正“失败就不能完成”的方法矛盾，保留先完成后流程失败；未知效果和缺失时延不填零。
3. 区分历史配置的安全提示和当前普通提示，区分历史服务时间与后续修正版执行时间。
4. 将历史1/400风险标签、当前490攻击条件分配全零、同期3/30对0/30分别解释；不从旧矩阵恢复当前防护有效性的强主张。
5. 新增显式current正文配置，保留完整工作稿和全部历史源文件；主要文章只展开当前证据，历史详细结果由完整工作稿及S1–S20承载。
6. 生成精简中英文稿，更新LaTeX实际正文，修复短主表表注跨页。

没有覆盖任何raw、冻结计划或原统计；没有新授权版本、扩权、模型API、历史统计推断重算、Full Harness或递归哈希包。

## 2. 现在应读哪一份

|用途|文件|
|---|---|
|精简英文主稿|[manuscript_current_v2.md](manuscript_current_v2.md)|
|精简中文内容对照|[manuscript_current_zh_v2.md](manuscript_current_zh_v2.md)|
|保留全部历史细节的英文工作稿|[manuscript_deepseek_v1.md](manuscript_deepseek_v1.md)|
|完整中文工作稿|[manuscript_zh_v1.md](manuscript_zh_v1.md)|
|历史20表和5图|[supplementary_tables_v1.md](supplementary_tables_v1.md)|
|60任务逐项解释|[report.md](../../../../outputs/experiments/research_followup_20261006_v1/trusted_intent_review/report.md)|
|当前完整研究报告|[阶段报告](../../../../outputs/experiments/research_followup_20261006_v1/report.md)|

英文精简正文为8,148词，完整工作稿正文为15,838词，减少约48.6%。计数限第1–6章，排除摘要、标题、表格行、图和参考文献条目，也排除引用键；使用仓库既有英文token正则。精简文件全文件10,116词，不能把这个数与正文目标混用。中文是内容对照，不宣称逐句等长翻译。

完整工作稿仍为六章，历史细节没有被删除或改数。current配置只选择明确标题，标题缺失或重复会报错，不能静默省略当前证据。

## 3. 聚焦科学审查与实际修正

本次是同一执行者的内部聚焦方法/主张审查，不是独立同行评审或真实期刊意见；没有ARS全流程机械门禁、盲评或期刊接受概率。

|问题|已执行修正|仍保留的边界|
|---|---|---|
|方法称流程失败不能算完成，与两条先完成后失败记录矛盾|分别记录完成和运行失败；完成须有基准证据|不能把故障自动改成成功，也不抹去已有完成|
|旧bundled条件与当前普通提示混淆|注明历史policy-normal/full-safe；当前900/480均普通提示|历史因子研究不证明每个内部模块的独立收益|
|历史1/400和当前490全零混作同一个新实验|按版本、队列、端点分别解释|当前授权研究无无防护对照，安全有效性仍未建立|
|用较大旧矩阵弥补当前稀少安全事件|删除这种推论，保留历史风险标签名称|旧端点不能变成修正版执行证据|
|60任务审查仍被列为未来工作|英中方法、结果、讨论、结论实际接入|七声明保留、十三直接目标、十待确认不是误阻断裁决|
|有执行却未完成被轻率归因评分器|明确三个mock API案例的脱敏参数缺口|不知道具体不匹配原因，不宣称评分器错误|
|正文堆叠研究演进、重复方法|独立8,148词current主稿；完整版本保留|不因删减叙述提高研究证据强度|
|短主表的最后一句解释跨页|四个短主表改为整体竖版浮动表，保留全部数值和表注|历史长表仍为带行号的非旋转续表|

按本轮实际检查范围，方法描述一致性、主张—证据边界和正文长度问题已处理。新颖性、全部文献全文支撑及投稿适配没有重新做外部核验，记为未评估，而不是自动通过。仍不支持first/only/SOTA、完整模块领先、普遍来源防护、跨厂商泛化或攻击饱和。

## 4. 验证结果

实际使用Python 3.13.5：F:\robot\Anaconda3\python.exe。

~~~powershell
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m pytest tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_build_jisa_latex.py tests/unit/test_trusted_intent_review_v1.py -q
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m ruff check scripts/build_lean_paper_manuscript.py scripts/build_jisa_latex.py tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_build_jisa_latex.py
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_lean_paper_manuscript --profile full
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_lean_paper_manuscript --profile current
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_jisa_latex --main-markdown manuscript_current_v2.md
~~~

最终定向pytest：46 passed；Ruff通过。覆盖版本区别、失败/完成并存、未知、60审查范围、精简篇幅、完整稿保留、六章/四图/四表、标题缺失或重复拒绝、显式LaTeX入口和所有短主表数据/表注完整。不是全项目测试通过。

两个当前PDF实际使用latexmk的-xelatex、-bibtex、-interaction=nonstopmode、-halt-on-error、-file-line-error、-cd选项编译，均exit0：

|产物|页数|PDF导航条目|自动布局错误|作者元数据|
|---|---:|---:|---:|---|
|数模通用模板.pdf|35|40|0|空|
|M3_PI_Guard_JISA.pdf|26|39|0|空|

两份共61页均为A4竖版、无页旋转、底部居中页码、正文Times New Roman（数学符号可为CMSY）、无越界/空白页/缺字/未定义引用/Overfull。联系图与表3放大页已查看。最终表3及完整表注在模板PDF第18页、正式PDF第13页同页。正式稿仍有3处Underfull排版警告，目视未见裁切或重叠，未隐藏警告或降低阈值。

24页补充PDF本轮无内容变化，保留前一阶段的编译/检查结果，不冒称本轮重新编译。PDF技能附带运行时接口和操作标记脚本在本机不可用，改用既有TeXLive/PyMuPDF；不声称该附带工具检查通过。

首次定向测试的几项失败是跨换行的字符串断言和旧longtable/目录路径断言，已按实际生成契约修正并保留数据与表注检查；PDF同页检查最初误把图3相同标题当成表3，改为完整“Table 3”标题识别，没有放宽同页要求。PowerShell花括号语法及工具字符串构造失败均发生在实际执行前，没有改数据。

## 5. outputs结构

~~~text
outputs/
├── experiments/
│   ├── claude_revision_v1/                  # 900授权、16组件的既有原始/分析
│   └── research_followup_20261006_v1/
│       ├── report.md                       # 研究总入口
│       ├── calibration/                    # 480同期原始、既有统计及延迟修正
│       ├── diagnosis/                      # 去重300条公开事件解释
│       ├── trusted_intent_review/
│       │   ├── review.csv                  # 固定60任务逐项解释
│       │   └── report.md
│       └── manuscript_figures/             # 当前四图PDF/SVG/PNG与说明
└── manuscript/previews/current_article_20261008/
    └── *.png                               # 当前PDF联系图/重点页，本地预览不进Git
~~~

正文和报告在docs；当前LaTeX与最终PDF仍在LaTeX通用模板，不挪入实验原始数据。没有新增结果JSON、签名、审计包或哈希树。内部provider traces不上传。

## 6. 尚未完成的事项

当前文稿和局部科学口径并不等于投稿就绪。作者/单位/资助/利益冲突/贡献须由作者填写确认；最终期刊范围和分区须投稿时确认。独立模型服务、原生动态环境模型研究和具体脱敏参数原因仍没有合格结果，不以计划数补齐，也不为了好看扩权或重跑成功行。完整参考文献内容支撑与外部独立方法审阅若要宣称完成，仍须对应真实核验。

科研整体保持in_progress。本轮成果按范围提交到codex/claude-review-repairs并推送当前origin；确切提交回执见对话及下一阶段交接，不为自引用hash循环提交。

可信度：9/10。代码、当前文件、定向测试、实际编译和页面可复核；未知原因、外部审阅和投稿条件未冒称完成。
