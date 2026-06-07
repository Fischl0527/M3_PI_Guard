# DAY7 B 最终检查清单

## 1. 样本合规性

- [x] `m3_attacks/cases/all_cases.jsonl` 存在。
- [x] 样本总数为 69。
- [x] 覆盖至少三类攻击场景。
- [x] 危险目标动作均限定在本地 mock 白名单内。
- [x] 未发现真实邮箱、真实 API、真实系统路径或真实凭证。
- [x] `benign_clean` 样本用于误报率校准。

## 2. 案例卡

- [x] `docs/case_cards/DEMO_001_RAG_INDIRECT.md` 已更新。
- [x] `docs/case_cards/DEMO_002_JSON_RPC.md` 已更新。
- [x] `docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md` 已更新。
- [x] 三张案例卡均包含攻击入口、攻击载体、正常任务、注入摘要、不安全目标动作、baseline 观察点、full_guard 阻断原因、证据路径和安全边界。

## 3. 证据索引

- [x] `docs/SUBMISSION_EVIDENCE_INDEX.md` 已生成。
- [x] 赛题要求与项目文件已逐项对应。
- [x] 覆盖风险分析报告、攻击样本、运行入口、行为监督、mock 工具、运行日志、阻断记录和安全边界声明。

## 4. 答辩材料

- [x] `docs/presentation/答辩问题准备_攻击侧.md` 已生成。
- [x] 问答覆盖真实攻击边界、本地模型价值、攻击类型、误报控制、样本公开安全性和后续扩展。

## 5. 扫描结果

- [x] 文档与攻击材料过程指令痕迹扫描为空。
- [x] 身份泄露关键词扫描为空。
- [x] `__pycache__` 和 `.pyc` 已从当前 B 侧工作区清理。

## 6. 仍需人工确认

- [ ] 最终 Word 报告目录页码需要用 Word/WPS 手动更新。
- [ ] 最终 release zip 是否包含 A/C 最新交付物，需要全队合并后再核对。
- [ ] 如果要提交 PDF，需要在本机 Word/WPS 中导出并人工打开确认。
