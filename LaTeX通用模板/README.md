# M3-PI Guard LaTeX 稿件

2026-10-08 更新：当前精简英文正文8,148词，纳入900授权、480同期、
16组件控制及60正常任务的事后解释性审查。完整工作稿另存，不删除历史结果。
当前审阅稿35页、40个PDF导航条目；elsarticle主稿26页、39个导航条目。
主稿为4图、4张结果表；独立补充包含20张历史表与5张历史图，24页PDF
保留上一阶段检查结果，本轮未重新编译。作者信息仍留空。
四个短主表的标题、数据与表注作为整体竖版浮动表，不旋转、不缩小数字。
详细实际执行、测试和限制见
[正文收束报告](../docs/research/paper_v2/manuscript/current_manuscript_closeout_2026-10-08.md)。
历史E7a仅为提案许可，不计为完成或实际效果。本次没有启动新模型实验。

本目录现在包含两种用途明确分离的 LaTeX 入口。作者审阅时优先打开用户原模板
直接生成的 `数模通用模板.pdf`，其编辑入口就是 `数模通用模板.tex`，而不是 Word
转换版或另造的页面样式：

- `M3_PI_Guard_JISA/M3_PI_Guard_JISA.tex`：正式英文投稿主稿，使用
  Elsevier `elsarticle` 类和 `elsarticle-num` 参考文献样式。
- `M3_PI_Guard_JISA/M3_PI_Guard_JISA_supplement.tex`：独立补充材料，含
  Supplementary Tables S1--S20 和 Figures S1--S5。
- `数模通用模板.tex`：模板审阅母版，直接使用本目录原有的
  `cumcmthesis`、字体和 `gbt7714-numerical.bst`。页面严格继承模板的 A4、
  四边 25 mm 和底部居中页码；拉丁正文、标题、行内标识和图表文字统一使用
  Times New Roman。它不是 JISA 官方模板，也不应冒充正式投稿类。
- `M3_PI_Guard_template_review.tex`：仅为兼容旧路径的薄包装，实际加载上述
  `数模通用模板.tex`，不再维护第二份审阅版正文。

作者、单位和通信作者字段均有意留空，待作者本人在投稿前填写。正文、表格、
图件和参考文献由当前 Markdown 论文源确定性生成；构建过程不会调用模型 API，
不会修改实验原始结果。

审阅包所需 `cumcmthesis.cls` 和 `gbt7714-numerical.bst` 已纳入版本控制。
类文件不再强制依赖未共享的本地代码字体、思源字体；缺少这些可选字体文件时
使用系统 Times New Roman/SimSun 回退，不上传或删除原字体素材。本机无字体
素材副本的临时源码包已独立编译通过。Windows系统仍须具备所声明的系统字体。

`数模通用模板.tex` 对摘要、六章正文和声明使用字面 `\input` 路径，而不是把
路径藏在 `\ProjectRoot` 宏中。TeXstudio 因而可以递归读取各章，并在左侧“结构”
面板显示完整的 section、subsection 和 subsubsection。若文件已在修改前打开，
请重新打开主文件或执行 Idefix 的“刷新结构”。

历史宽表按原始行号和身份列拆成竖版续表，全部列、行和值保留；
不使用旋转表格、`pdflscape/landscape`、缩放盒或微小字体。

## 重新生成源文件

在仓库根目录执行：

```powershell
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_lean_paper_manuscript --profile current
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_jisa_latex --main-markdown manuscript_current_v2.md
```

这两个显式选项选择当前精简稿。默认生成器仍保留完整工作稿行为；
不要用省略选项的默认构建误覆盖当前精简正文。

## 编译正式主稿和补充材料

Elsevier Editorial Manager 不处理 LaTeX 子目录，因此正式包中的入口、章节、
表格、图件和 `.bib` 均放在 `M3_PI_Guard_JISA/` 同一级。无需设置永久环境变量：

```powershell
$latexmk = 'D:\TeXLive\texlive\2026\bin\windows\latexmk.exe'
$texBin = Split-Path -Parent $latexmk
$env:Path = "$texBin;$env:Path"

Set-Location -LiteralPath 'E:\M3_PI_Guard_test\LaTeX通用模板\M3_PI_Guard_JISA'
& $latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error `
  '.\M3_PI_Guard_JISA.tex'
& $latexmk -xelatex -interaction=nonstopmode -halt-on-error -file-line-error `
  '.\M3_PI_Guard_JISA_supplement.tex'
```

## 编译本地模板对照稿

该入口依赖本目录原有 `cumcmthesis.cls`、字体和 BST，因此必须从本目录编译：

```powershell
Set-Location -LiteralPath 'E:\M3_PI_Guard_test\LaTeX通用模板'
& $latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error `
  '.\数模通用模板.tex'
```

正式投稿时以 `M3_PI_Guard_JISA/` 中的英文主稿和补充材料为准；Word 文件只保留
为历史审阅件，不再作为排版源。
