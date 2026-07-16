# E17 真人分层抽样盲审包

这是 `E17_HUMAN_STRATIFIED_360_V1` 的项目管理员入口。该包从 3299 条 E17 待审记录中，以种子 `20260716` 生成两份内容和顺序完全相同的 360 行盲审模板。

本包属于 M3 PI Guard 的实验输出，不属于 AI Agent Harness 源码。抽样/盲审实现位于 `experiments/e17_human_sample.py`，模板源位于 `experiments/review_templates/`，命令入口位于 `scripts/build_e17_human_sample.py`；`harness/` 只记录任务状态、验证和阶段工作区。

## 当前状态

- 需要两名真人分别独立完成同一批 360 行。
- 代表性样本：300 行。
- 自动分歧定向样本：40 行。
- 稀有/复杂定向样本：20 行。
- 两份模板尚未填写时，本包只表示“已准备好评审”，不表示 E17 真人复核已完成。
- 允许的覆盖声明：两名真人独立复核共享的 360 条分层样本。
- 禁止的覆盖声明：全部 E17 记录均由真人复核。

## 目录说明

```text
E17_human_stratified_360_v1/
├─ README.md                         管理员入口与文件索引
├─ REVIEW_INSTRUCTIONS.md            发给两名评审员的完整判定手册
├─ manifest.json                     抽样协议、来源哈希、输出哈希和分析边界
├─ packet_manifest.json              模板行数、ID、证据和字节一致性校验
├─ sampling_strata.csv               管理员使用的抽样分层/权重规则
├─ packets/
│  ├─ README.md                      评审包快速说明
│  ├─ reviewer_1_blinded_template.csv Reviewer 1 唯一工作模板
│  └─ reviewer_2_blinded_template.csv Reviewer 2 唯一工作模板
├─ submissions/
│  └─ README.md                      完成文件命名和交回规则
└─ private/
   ├─ README.md                      私有目录访问边界
   └─ review_items_360.jsonl         盲 ID 与来源/分层映射，仅管理员可见
```

## 分发方式

给 Reviewer 1：

- `REVIEW_INSTRUCTIONS.md`
- `packets/reviewer_1_blinded_template.csv`

给 Reviewer 2：

- `REVIEW_INSTRUCTIONS.md`
- `packets/reviewer_2_blinded_template.csv`

不要向任一评审员分发 `private/`、`sampling_strata.csv`、自动评审结果或另一人的文件。根目录 manifest 可以用于项目审计，但不属于评审员完成判定所需材料。

## 收回方式

将冻结的完成文件放入：

- `submissions/reviewer_1_completed.csv`
- `submissions/reviewer_2_completed.csv`

在两份文件都收到前，不运行相互比较，不把任何一方的判定反馈给另一方。收到后先做结构和证据完整性校验，再计算一致性并生成分歧清单。

## 重建命令

从仓库根目录运行：

```powershell
python scripts/build_e17_human_sample.py
```

详细手册和本目录说明由 `experiments/review_templates/` 下的源模板生成。需要修改说明时应修改源模板后重建，避免下次生成覆盖人工编辑。

重建不得改变相同输入、相同种子下的两份 CSV 内容；manifest 中记录的哈希用于验证这一点。
