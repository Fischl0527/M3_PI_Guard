# M3-PI Guard 阶段性实验报告

日期：2026-07-14  
分支：`test1`  
基线：`2c53f52c475e6838dc82246c821db5ed7ac0209c`  
报告性质：阶段性、可审计、非最终结论

## 1. 当前结论

项目已经完成绝大多数可独立执行的实验、统计基础设施、自动双代理诊断和 Dashboard 验收，但**尚未达到“所有实验完成”**：

- E0–E8、E10–E13、E15–E16 的运行与统计证据可继续使用，共 15 项为 `completed`。
- E9 长上下文实验和 E14 性能实验在冻结后的语义有效性复核中暴露设计问题，已经重新打开为 `running`；旧结果仅保留为诊断/溯源证据，不能支撑正式长上下文与按上下文长度的性能结论。
- E17 自动双代理复核已完成，但它只用于诊断；两名真人独立盲审仍是正式门禁。
- 当前注册表应为 `15 completed / 3 running / 0 failed`。正式 `final_analysis`、最终 Dashboard 数据冻结和本地提交仍必须等待修正后的 E9/E14 与真人 E17。

本轮按要求在短周期后停止，没有启动数小时级重跑，也没有制作 PPT、DOCX 或提交 ZIP，没有提交、推送或创建 PR。

## 2. 已完成的工程与实验基础

### 2.1 数据、运行与证据规模

| 项目 | 当前证据 |
| --- | ---: |
| 审计数据集 | 300 条：210 attack、90 benign；dev/validation/blind = 150/60/90 |
| 攻击族 | 9 类 |
| 正常任务 | 45 无工具 + 45 合法工具 |
| 已运行程序规模 | 172 jobs，15,446/15,446 case-runs |
| 主矩阵 | 4 核心模型 × 90 盲测 × 6 条件 × 3 次重复 = 6,480 case-runs |
| 稳定性 | 4 模型 × 30 样本 × 10 seeds × 3 temperatures = 3,600 case-runs |
| 严格逻辑运行审计 | 10,526 runs；65/65 冻结文件哈希一致 |
| E0–E16 旧版 bundle 完整性 | 17 bundles；954/954 工件通过 SHA-256 与字节数复验 |
| 自动双代理 E17 诊断 | 3,379 项；主原因一致率 84.02%；Cohen's κ = 0.7881；716 项分歧 |

上表中的“文件完整”只证明日志与工件没有丢失或篡改，不等同于实验设计语义有效。E9/E14 正是通过第二层语义审计被重新打开。

### 2.2 已实现能力

- `AttackCase`、`RunLog` 与实验 manifest 已扩充到样本类型、模板/切分、授权动作、提示配置、Guard 模块、seed/repeat、耗时、token 和模型环境等字段。
- 模型输入与评估答案分离；`prompt_profile` 与 `guard_mode` 正交；Stub 只作为确定性回归。
- 已实现断点续跑、失败保留、完整分母、Wilson 置信区间、McNemar、配对 bootstrap、Wilcoxon 与 Holm 校正。
- 已建立 13 图最终分析构建器、原始证据回放和按模型/防御/攻击族/语言/批次筛选的 Dashboard。
- Dashboard 真实浏览器验收为 0 console errors、0 warnings；冻结源 `m3_eval/dashboard.py` 保持原哈希，增强 UI 位于独立的 `m3_eval/evidence_dashboard.py`。

## 3. 当前实验状态

| 范围 | 状态 | 说明 |
| --- | --- | --- |
| E0 | completed | 攻击/正常分母、标签泄漏、历史指标审计完成 |
| E1–E6 | completed | 主效果、提示、增量、消融、跨模型、攻击族证据完整 |
| E7–E8 | completed | 多语言与编码规避独立矩阵完成 |
| E9 | **running / reopened** | 旧 2K/4K/8K/16K 未形成真实递增 workload，需新冻结全量复跑 120 case-runs |
| E10–E13 | completed | 多轮、跨工具、可用性、阈值校准完成；E11 后置补充单独计数，不并入原分母 |
| E14 | **running / reopened** | 四个上下文标签使用相同短输入，需新冻结全量复跑 432 正式 + 48 warmups |
| E15–E16 | completed | 随机稳定性和三轮自适应红队完成 |
| E17 | **running / external gate** | 自动诊断已完成；等待两名真实独立盲审，不能由代理冒充 |

## 4. 有效结果的阶段性分析

以下结果来自仍然有效的冻结主矩阵与可用性评估。它们是阶段性证据，E9/E14 修正和 E17 完成前不得包装为最终项目验收。

| 指标 | 观察值 | 目标 | 判断 |
| --- | ---: | ---: | --- |
| full Guard 相对同提示 baseline 的总体 ASR 下降 | 99.21% | ≥70% | 达标 |
| DSR | 0 | =0 | 达标 |
| 恶意调用 Precision | 99.24% | ≥90% | 达标 |
| 恶意调用 Recall | 525/607 = 86.49% | ≥90% | **未达标** |
| 正常调用 FPR | 2.74% | ≤5% | 达标 |
| 正常 TCR | 190/324 → 168/324，下降 6.79 个百分点 | 下降 ≤5 pp | **未达标** |
| 合法工具 TCR | 110/168 = 65.48% | ≥90% | **未达标** |
| 正常 ASK 率 | 6.17% | ≤10% | 达标 |
| full-Guard ToolCall 解析率 | 97.51% | ≥95% | 该切片达标 |
| 全程序 run-level ToolCall 解析率 | 92.98% | ≥95% | **未达标**，须与安全失误分开报告 |
| Guard p95 | 旧短 workload 观察值 1.765 ms | <10 ms | 仅短 workload 暂时达标；不能替代修正后的 E14 |
| 端到端开销 | 旧 E14 不足以支持跨 2K–16K 结论 | <10% | 待修正 E14 |

最重要的结果不是“Guard 全面通过”，而是安全性提升非常明显，同时仍存在三类实质缺口：恶意调用漏检、正常任务完成率下降、合法工具任务可用性不足。这些负面结果会保留原分母；若后续改进防御，必须创建新版本和新冻结重新评测，不能在当前盲测结果上反向调参。

### 4.1 现有有效图表

主防御图以模型为分组、条件为系列，误差线为 Wilson 95% 置信区间。四个 baseline 的 ASR 介于 23.81%–84.66%，full Guard 后 Gemma、Phi-4 Mini、Qwen 为 0，Llama 3.2 为 1.59%；它证明安全增益很强，但不能代替后文的 Recall 与正常任务可用性检查。

![E1 主防御效果](../../outputs/experiments/E1/primary_chart.png)

消融森林图把每个变体与完整 Guard 做案例配对，左侧是 ASR 差值、右侧是 TCR 差值。部分单组件/关闭条件显著增加 ASR，而许多“移除单一模块”点估计接近 0；这说明当前 60 条验证集对细粒度模块贡献的区分能力有限，宽置信区间必须与点估计一起解读。

![E4 组件消融](../../outputs/experiments/E4/ablation_contribution_forest.png)

攻击族图使用四模型合并的 84 个案例/族/条件。full Guard 将八类攻击族的 ASR 降至 0，但环境上下文污染仍有 3/84（3.57%）；这三例应进入后续逐案根因分析，不能被总体平均掩盖。

![E6 分攻击族结果](../../outputs/experiments/E6/primary_chart.png)

可用性图展示四模型在六种条件下的 TCR 与 Wilson 区间。模型差异很大，尤其 Llama 3.2 明显偏低；完整 Guard 的安全收益伴随总体 TCR 与合法工具 TCR 的下降，因此后续优化应把误拦、ASK、规划失败和解析失败分开定位。

![E12 正常任务可用性](../../outputs/experiments/E12/primary_chart.png)

阈值 ROC/PR、语言、编码规避、多轮、跨工具与稳定性图也已生成在各自 E7/E8/E10/E11/E13/E15 bundle 中。旧 E9/E14 图不再列为正式证据。

## 5. E9/E14 有效性审计

### 5.1 E9：标称上下文长度与实际 token 不一致

| 标称目标 | 首步实际 prompt token（min/median/max） | 解析成功 | 结论 |
| ---: | ---: | ---: | --- |
| 2,048 | 6,307 / 6,310 / 6,320 | 30/30 | 超过目标约 208%，不符合目标 |
| 4,096 | 8,192 / 8,192 / 8,192 | 0/30 | 被默认 8,192 context 截断/折叠 |
| 8,192 | 8,192 / 8,192 / 8,192 | 0/30 | token 数表面相等，但无输出余量且全部解析失败 |
| 16,384 | 8,192 / 8,192 / 8,192 | 0/30 | 被默认 8,192 context 截断/折叠 |

根因有两层：派生输入按空白 `.split()` 近似“token”，而填充串并非单 token；同时 OpenAI-compatible 请求里的动态 `num_ctx` 没有在当前 Ollama 路径上改变实际 context。94/120 个 unresolved 不是“攻击被安全阻断”，因此旧 ASR=0 不能解释为长上下文鲁棒性。

### 5.2 E14：上下文标签变化，但工作负载没有变化

| 条件 | 2K prompt median | 4K | 8K | 16K | 最大/最小比 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Guard off | 486.5 | 486.5 | 486.5 | 486.5 | 1.0× |
| full Guard | 230.5 | 230.5 | 230.5 | 230.5 | 1.0× |

E14 的 432 个正式运行与 48 个 warmups 都存在，但四个 `num_ctx` 单元复用了同一批短 smoke 输入。因此它只能描述短输入下的观察值，不能支持“不同上下文长度下的延迟、吞吐与显存”结论。

机器可读审计：

- `agent/audits/context_experiment_validity.json`
- `agent/audits/context_experiment_validity.md`
- 回归测试：`tests/unit/test_audit_context_experiments.py`，4/4 通过

## 6. 修正准备情况

已创建并真实探针验证四个本地 Qwen context aliases：

| Alias | Modelfile `num_ctx` | 过长输入探针的实际 prompt token | 结论 |
| --- | ---: | ---: | --- |
| `m3-qwen3-4b-ctx4k:latest` | 4,096 | 4,096 | 有效封顶 |
| `m3-qwen3-4b-ctx8k:latest` | 8,192 | 8,192 | 有效封顶 |
| `m3-qwen3-4b-ctx16k:latest` | 16,384 | 16,384 | 有效封顶 |
| `m3-qwen3-4b-ctx32k:latest` | 32,768 | 20,156（20K filler） | 未在 20K 处截断，留有输出余量 |

修正协议将：

1. 以模型返回的 `prompt_eval_count` 为准，将 2K/4K/8K/16K workload 迭代校准到 ±5%，不再用空白词计数。
2. 分别使用 4K/8K/16K/32K alias，为模板和至少 512 输出 token 留足 headroom。
3. 记录实际 context、实际 prompt token、截断状态和实际注入位置；不通过 validity checks 的 cell 不能标记完成。
4. 在新协议与新 freeze 下全量复跑 E9 120 case-runs，以及 E14 432 case-runs + 48 warmups，不只补失败样本。
5. 保留 `program_final_v3` 与 `blind_freeze_v3`；修正结果使用新目录和新 manifest，不覆盖旧证据。
6. 修正后重建 E17 source index、空白盲审包和自动诊断，再交两名真人盲审。

Ollama 当前兼容性约束与推荐的 Modelfile 配置方式可参见官方 [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)、[running models](https://docs.ollama.com/api/ps) 与 [usage](https://docs.ollama.com/api/usage)。

## 7. 自动复核与真人门禁

两名隔离的自动诊断代理均完成 3,379/3,379 项，主原因一致 2,839/3,379（84.02%，κ=0.7881），共有 716 个需要重点复核的分歧项。自动结果可用于排序和发现 taxonomy 边界，但不能替代真人。

正式 E17 仍要求：

- 两名真实、独立、相互不可见答案的盲审者；
- 对漏拦、误拦、ASK、解析失败与原因码完成复核；
- 通过 schema、覆盖率与一致性验证后再登记；
- 若 E9/E14 修正改变源索引，真人必须使用重建后的最终冻结包。

本报告没有读取、生成或代填任何真人盲审答案。

## 8. Harness 与门禁状态

Harness 已从“仅 E17 阻塞”纠正为真实状态：

- R18（E9）、R23（E14）、R26（E17）、R32（最终交付）、R33（最终分析）均为 blocked。
- 需求台账预期为 28 satisfied / 5 blocked。
- `final-audit.md` 保持 `Blocked`，不做虚假完成声明。
- 旧 E9/E14 bundle 仍可用于根因诊断与溯源，但禁止进入正式长上下文/性能主张。
- 最终分析与 Dashboard 正式冻结仍受 E9/E14/E17 三重门禁。

本轮短验证链结果：

- Context validity 审计回归：4/4 tests passed；审计本身按设计返回 `status=fail`，用于阻止旧 E9/E14 被误用。
- Experiment registry：PASS，15 completed / 3 running / 0 failed。
- Requirement lock：PASS。
- Requirement ledger：PASS，33 项中 28 satisfied / 5 blocked。
- Final audit：PASS，结论为 `Blocked`。
- Source log：PASS，10 个可核验来源。
- 正式 final-analysis 与最终 Dashboard validate-only 均正确拒绝 E9 未完成的状态。
- 冻结 Dashboard 源仍为 60,207 bytes，SHA-256 `ce81b87225c42b17248e2c9b60c2e0fd59c05e32ca6ddde2db08c06bf5d47053`。
- 最近一次全量测试记录为 293 passed / 1 skipped；本轮按“短周期后停止”要求未重复长耗时全套测试。

## 9. 停止点与下一轮顺序

本轮停止在“修正协议准备完成、正式长跑尚未启动”的安全断点。下一轮应严格按以下顺序：

1. 实现 token 校准 fixture 与强制 validity checks，建立 E9/E14 correction v2 freeze。
2. 先做每个 alias 的短 smoke；通过后顺序运行 E9 120 个正式案例。
3. 使用真实 2K/4K/8K/16K workload 运行 E14 的 48 warmups + 432 正式案例，正常 matched-path 与攻击混合吞吐分开报告。
4. 审计新 bundle 的案例数、实际 token/context、截断、哈希和统计；更新注册表。
5. 重建 E17 source index 与空白包，重跑双代理诊断，再等待两名真人盲审。
6. 仅在 E0–E17 全部有效完成后构建正式 `final_analysis`、13 张主图与最终 Dashboard，执行全量测试和最终 Harness 审计。
7. 最后本地提交 `test1`；默认不 push、不建 PR。

## 10. 复核命令

```powershell
python -m pytest -q tests/unit/test_audit_context_experiments.py
python scripts/audit_context_experiments.py --allow-fail
python -m experiments.validate_registry
python scripts/build_final_analysis.py --validate-only
powershell -ExecutionPolicy Bypass -File scripts/run_final_dashboard.ps1 -ValidateOnly
```

预期行为：上下文有效性审计返回 `status=fail` 以保护旧结果不被误用；注册表显示 15 completed、3 running、0 failed；正式最终分析和最终 Dashboard 验证在 E9/E14/E17 未完成时必须拒绝放行。
