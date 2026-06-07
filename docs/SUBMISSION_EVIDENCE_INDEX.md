# Submission Evidence Index

This index maps the final submission requirements to files in the release package.

## 1. Safety Risk Analysis

- Main report: `docs/report/作品报告_终稿.docx`
- Scope and boundaries: `docs/ETHICS_AND_SCOPE.md`
- System overview: `docs/SYSTEM_ARCHITECTURE.md`

## 2. Attack Scenarios

- Attack chapter source: `docs/report_sections/03_attack_scenarios.md`
- Case cards: `docs/case_cards/`
- Attack matrix: `m3_attacks/ATTACK_MATRIX.md`

## 3. Test Case Set

- Full dataset: `m3_attacks/cases/all_cases.jsonl`
- Dataset card: `docs/DATASET_CARD.md`
- Representative set: `fixtures/day5_representative_cases.jsonl`
- Demo set: `fixtures/demo_cases.jsonl`

## 4. Agent Attack Execution

- Agent runner: `m3_core/agent_runner.py`
- Batch runner: `m3_core/run_batch.py`
- Matrix runner: `m3_core/run_matrix.py`
- Local model client: `m3_core/llm_client.py`

## 5. Behavior Supervision Prototype

- Guard entry point: `m3_guard/guard_engine.py`
- Detector: `m3_guard/detector.py`
- Policy engine: `m3_guard/policy_engine.py`
- Data-flow tracker: `m3_guard/dataflow.py`

## 6. Simulated Business Tools

- Tool sandbox: `m3_core/tool_sandbox.py`
- Sandbox public files: `sandbox/public/`

## 7. Monitoring and Logs

- DAY5 demo logs: `outputs/runs/day5_demo_matrix/`
- DAY5 local-model representative logs: `outputs/runs/day5_qwen25_matrix/`
- DAY6 release demo logs: `outputs/runs/day6_demo_stub_matrix/`
- Metrics summaries: `outputs/metrics/`

## 8. Alert or Blocking Evidence

- Guarded/full-guard logs: `outputs/runs/day5_demo_matrix/day5_demo_full_guard.jsonl`
- Summary metrics: `outputs/metrics/day5_demo_summary.csv`
- Log audit: `outputs/metrics/day5_log_audit.json`

## 9. Reproducibility

- Runbook: `docs/RUNBOOK.md`
- Smoke test script: `scripts/run_day7_smoke_test.ps1`
- Core requirements: `requirements-core.txt`
- Dashboard requirements: `requirements-dashboard.txt`

## 10. Presentation Materials

- Slide deck: `docs/presentation/Redteam_LLM_Security_答辩PPT.pptx`
- Demo notes: `docs/presentation/演示讲稿.md`
- Question preparation: `docs/presentation/答辩问题准备_综合.md`
- Screenshot list: `docs/presentation/截图清单.md`
