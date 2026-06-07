# M3_PI_Guard Runbook

## Purpose

This runbook explains how to reproduce the final local demo from the release package. All commands run locally and use mock tools only.

## Requirements

- Python 3.10 or newer
- PowerShell on Windows
- Optional: local Ollama service for model smoke tests

Install the core Python dependency if needed:

```powershell
pip install -r requirements-core.txt
```

Dashboard dependencies are optional:

```powershell
pip install -r requirements-dashboard.txt
```

## Smoke Test

From the release package root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day7_smoke_test.ps1
```

Expected outputs:

```text
outputs/runs/day7_smoke_stub/
outputs/metrics/day7_smoke_summary.csv
outputs/quality/day7_smoke_test_result.md
```

The smoke test uses the deterministic `stub` backend and validates the baseline and `full_guard` paths on `fixtures/demo_cases.jsonl`.

## Manual Demo

Run the demo matrix:

```powershell
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/day7_smoke_stub --run-prefix day7_smoke --max-steps 5
```

Evaluate the generated logs:

```powershell
python -m m3_eval.evaluate --log-dir outputs/runs/day7_smoke_stub --cases fixtures/demo_cases.jsonl --out outputs/metrics/day7_smoke_summary.csv
```

Optional dashboard:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day5_dashboard.ps1
```

## Local Model Demo

If local Ollama and `m3-target-qwen25-7b` are available:

```powershell
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day7_smoke_qwen --run-prefix day7_smoke_qwen --max-steps 5
```

This step is optional. The final reproducible path is the stub smoke test.

## Safety Notes

- No real email is sent.
- No public business API is called.
- Model-generated code is not executed.
- Sandbox canaries are local fake values.
- Release packages exclude local model files, secrets, runtime mailboxes, and private notes.
