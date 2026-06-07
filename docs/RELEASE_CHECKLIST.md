# Release Checklist

## 1. 结构检查

- [ ] `README.md` 存在。
- [ ] `requirements-core.txt` 存在。
- [ ] `requirements-dashboard.txt` 存在。
- [ ] `m3_core/`、`m3_attacks/`、`m3_guard/`、`m3_eval/` 存在。
- [ ] `fixtures/`、`scripts/`、`docs/`、`outputs/metrics/`、`outputs/runs/` 存在。
- [ ] `release/Redteam_LLM_Security_v1.0/` 存在。

## 2. 文档检查

- [ ] `docs/DATASET_CARD.md` 存在。
- [ ] `docs/ETHICS_AND_SCOPE.md` 存在。
- [ ] `docs/SUBMISSION_EVIDENCE_INDEX.md` 存在。
- [ ] `docs/RUNBOOK.md` 存在。
- [ ] 三个 demo 案例卡存在且内容完整。
- [ ] 报告和演示材料不包含身份信息。

## 3. 样本检查

- [ ] `m3_attacks/cases/all_cases.jsonl` 存在。
- [ ] 样本总数为 69。
- [ ] 至少覆盖三类攻击场景。
- [ ] `duplicate_case_id` 为 0。
- [ ] `missing_required_fields` 为 0。
- [ ] 危险目标动作均在本地 mock 白名单内。

## 4. 安全边界检查

- [ ] 不包含真实恶意代码。
- [ ] 不包含真实邮箱。
- [ ] 不包含真实 API 地址。
- [ ] 不包含真实凭证。
- [ ] 不包含真实系统路径。
- [ ] `sandbox/secrets/` 不进入最终提交包。
- [ ] `sandbox/outbox/` 不进入最终提交包。

## 5. 运行检查

- [ ] 样本合并审计命令可运行。
- [ ] stub demo 可运行。
- [ ] 指标评估可生成 CSV。
- [ ] Dashboard 可读取现有指标和日志。

## 6. 打包检查

- [ ] release 包不包含 `.git/`。
- [ ] release 包不包含虚拟环境。
- [ ] release 包不包含 `__pycache__/` 或 `.pyc`。
- [ ] release 包不包含模型文件。
- [ ] release zip 可解压。
- [ ] SHA256 文件已生成。
