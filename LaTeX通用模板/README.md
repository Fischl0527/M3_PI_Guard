# M3-PI Guard LaTeX 稿件

2026-09-05 更新：授权诊断及 E7a 许可实验已纳入第 3.17、4.13 节与表 7。
当前审阅稿 52 页、65 个 PDF 书签；elsarticle 主稿 59 页；补充材料维持 12 页。
主稿为 5 图、7 表、24 篇实际引用。表 7 使用不旋转的窄表，表题、表体与
表注保持同页。详细内容/版式复核见
`../docs/research/paper_v2/manuscript/usability_manuscript_update_v1.md`。
E7a 仅为提案获许可，不计为任务完成或已提交效应；本次没有启动新实验。

本目录现在包含两种用途明确分离的 LaTeX 入口。作者审阅时优先打开用户原模板
直接生成的 `数模通用模板.pdf`，其编辑入口就是 `数模通用模板.tex`，而不是 Word
转换版或另造的页面样式：

- `M3_PI_Guard_JISA/M3_PI_Guard_JISA.tex`：正式英文投稿主稿，使用
  Elsevier `elsarticle` 类和 `elsarticle-num` 参考文献样式。
- `M3_PI_Guard_JISA/M3_PI_Guard_JISA_supplement.tex`：独立补充材料，含
  Supplementary Tables S1--S12。
- `数模通用模板.tex`：模板审阅母版，直接使用本目录原有的
  `cumcmthesis`、字体和 `gbt7714-numerical.bst`。页面严格继承模板的 A4、
  四边 25 mm 和底部居中页码；拉丁正文、标题、行内标识和图表文字统一使用
  Times New Roman。它不是 JISA 官方模板，也不应冒充正式投稿类。
- `M3_PI_Guard_template_review.tex`：仅为兼容旧路径的薄包装，实际加载上述
  `数模通用模板.tex`，不再维护第二份审阅版正文。

作者、单位和通信作者字段均有意留空，待作者本人在投稿前填写。正文、表格、
图件和参考文献由当前 Markdown 论文源确定性生成；构建过程不会调用模型 API，
不会修改实验原始结果。

`数模通用模板.tex` 对摘要、六章正文和声明使用字面 `\input` 路径，而不是把
路径藏在 `\ProjectRoot` 宏中。TeXstudio 因而可以递归读取各章，并在左侧“结构”
面板显示完整的 section、subsection 和 subsubsection。若文件已在修改前打开，
请重新打开主文件或执行 Idefix 的“刷新结构”。

六列及以上的宽表只旋转表格内容，PDF 纸张、模板页边距与页码均保持纵向；不要
把这些表改回 `pdflscape/landscape`，否则阅读器会把页码旋到页面左侧。

## 重新生成源文件

在仓库根目录执行：

```powershell
& 'F:\robot\Anaconda3\python.exe' -B .\scripts\build_jisa_latex.py
```

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
