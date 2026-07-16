# E0 指标、标签与历史结果审计

> 结论限定：**diagnostic only（仅诊断）**。历史运行存在 prompt/Guard coupling （提示词与 Guard 耦合）和 evaluator-label leakage（评估答案字段泄漏），不得用于正式因果效果声明。

## 验收结论

- 当前测量链路：`pass_with_historical_findings`。显式 `sample_type`、数据集配额、模板隔离和运行时输入投影检查均通过。
- 历史结果：六组日志已原样索引并重新计算；解析失败、拒答、超时或未完成状态仍保留在原分母。
- Stub：只作为确定性回归证据。旧 Stub 直接读取 `case_id` 和 `attack_family`，不能代表真实模型安全效果。
- 空分母：统一写作 `NA`，图中不绘制为 0。

## 数据与粒度

| 数据 | 行/案例 | SHA-256 |
|---|---:|---|
| `m3_attacks/cases/all_cases.jsonl` | 300 / 300 | `31327e383343ba71591e34637b0b10468d248a34dd5942174329c5ee42655462` |
| `release/Redteam_LLM_Security_v1.0/m3_attacks/cases/all_cases.jsonl` | 69 / 69 | `7ae24f3a06773925750322303d08e85acdb3c2d065b296f9e1c08e09c4f32877` |
| `fixtures/day5_representative_cases.jsonl` | 24 / 24 | `2b42e02407ab5c70a5f29c59e0714adc25b3a4df8a2afc6a6bf0588f309cd95e` |
| `outputs/runs/day5_stub_matrix/day5_stub_all_baseline.jsonl` | 163 / 69 | `30113a70f3805574a1d9a02ea6fc0dd07a553194a03e65f8513c3f30086ce1ac` |
| `outputs/runs/day5_stub_matrix/day5_stub_all_keyword_only.jsonl` | 91 / 69 | `1525af0e18e05cc9fdc531a13dec75320890a97e06bcf96ee2fd2b7a92828b7a` |
| `outputs/runs/day5_stub_matrix/day5_stub_all_policy_only.jsonl` | 69 / 69 | `a42cb271711135081c40b01a0b4258e04cfb121e98487755f36dddc02a6dc31e` |
| `outputs/runs/day5_stub_matrix/day5_stub_all_full_guard.jsonl` | 69 / 69 | `a3d4d6bbc28e11f0891065d73928816fe8bf2bc66836c129fd3d1fae6ee2fe55` |
| `outputs/runs/day5_qwen25_matrix/day5_qwen25_rep_baseline.jsonl` | 38 / 24 | `f6db74e273dd2c228b3a4a8c79ce27daa6ec7958cc262d8c9f9adb2865149fb4` |
| `outputs/runs/day5_qwen25_matrix/day5_qwen25_rep_full_guard.jsonl` | 24 / 24 | `4f6ff9f085a86264b0e88f72395b3696c07f531d7dcdfa47b5bbb9f3ba5a4b58` |

主比例指标按案例运行（case-run）计算；Precision/Recall/FPR 按可判定工具调用计算；ParseSuccessRate 按解析尝试计算。
历史 pre-schema 数据仅在内存副本中按 `benign_clean → benign，其余 → attack` 写入显式 `sample_type`，原文件未修改。

## 300 条规范数据集审计

- 文件哈希：`31327e383343ba71591e34637b0b10468d248a34dd5942174329c5ee42655462`；语义哈希：`4d397967b4dc1cfbaa147969b68b1e339c8e0caadb7e3aa3369946c1138f10ee`。
- 共 300 条：attack=210，benign=90。
- 切分：dev=150，validation=60，blind=90。
- 正常任务：无工具=45，合法工具=45。
- 九类攻击共 210 条；69 条遗留样本全部位于 dev。
- 数据审计：`pass`，hard_fail=0，跨集合模板=0。
- 运行时泄漏变形测试：600 组消息对，状态 `pass`。

## 历史指标重算

| 运行 | attack/benign | ASR | UTR | DSR | BSR | TCR | 正常干预 | 解析成功 | 未解决案例 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Stub baseline | 61/8 | 57.4% | 32.8% | 52.9% | 0.0% | 75.0% | 0.0% | 100.0% | 0 |
| Stub keyword | 61/8 | 13.1% | 9.8% | 11.8% | 60.0% | 75.0% | 0.0% | 100.0% | 0 |
| Stub policy | 61/8 | 0.0% | 0.0% | 0.0% | 100.0% | 75.0% | 0.0% | 100.0% | 0 |
| Stub full Guard | 61/8 | 0.0% | 0.0% | 0.0% | 100.0% | 75.0% | 0.0% | 100.0% | 0 |
| Qwen2.5 baseline | 19/5 | 15.8% | 15.8% | 0.0% | 0.0% | 60.0% | 0.0% | 94.7% | 3 |
| Qwen2.5 full Guard | 19/5 | 0.0% | 0.0% | 0.0% | 100.0% | 60.0% | 40.0% | 91.7% | 2 |

关键分母修正：69 条 Stub 快照统一使用 attack=61、benign=8；24 条 Qwen 快照使用 attack=19、benign=5。8 条 `benign_clean` 不再进入 Stub ASR/UTR/DSR 的攻击分母。
Qwen baseline/full 的解析成功率分别为 36/38 与 22/24；未解决案例分别为 3 与 2，均未被静默删除。
FPR 只有存在可判定的合法工具调用分母时才定义；Qwen full 的两条合法文件调用虽使用历史 `file_path` 别名，仍应计入分母，且两条均被拒绝，因此 FPR=2/2=100%、正常案例干预率=2/5。四组 Stub 快照没有可判定的合法工具调用，FPR 才是 NA。

## 历史缺陷与解释边界

1. **Prompt/Guard coupling**：旧 `_build_initial_messages` 直接从 `defense_mode` 选择普通或强化提示。keyword、policy、full Guard 与 baseline 的差异同时包含提示词变化。
2. **Label leakage**：旧模型输入包含 `case_id`、`attack_family` 和 `<ExpectedSafeBehavior>`。这相当于向模型暴露样本标签和期望答案。
3. **Stub oracle dependency**：旧 Stub 根据 `case_id`/`attack_family` 直接选择工具调用路径，只适合回归测试。
4. 因此，`statistics.json` 的 McNemar、10,000 次配对 bootstrap 和 Holm 校正仅验证重算链路；即使 p 值很小，也不能支持 Guard 的正式因果结论。

## 可复现入口

```powershell
python -m experiments.e0_audit --out-dir outputs/experiments/E0
```

统计比较数：4；历史运行数：6。
