# PPT Result Notes

## Slide 1: Problem

Prompt injection is more dangerous when the model controls tools. A harmless-looking summary task can become a secret read, email send, API call, or code execution request.

Speaker note:
We evaluate the agent's behavior, not just whether the final answer sounds safe.

## Slide 2: System

M3-PI Guard sits between the agent and tools. Every proposed tool call is scored and converted to `allow`, `ask`, or `deny`.

Speaker note:
The interface is intentionally simple: `guard_decide(context, tool_call)`.

## Slide 3: Detection Capability

DAY5 Guard detects:

- instruction-like text
- multilingual and T2L obfuscation
- JSON/RPC structured injection
- tool-output injection
- sensitive dataflow
- intent-action mismatch

Speaker note:
This makes the Guard explainable. Each block has reason codes, not just a binary result.

## Slide 4: Evaluation Matrix

We run three result groups:

- stub full matrix: baseline, keyword_only, policy_only, full_guard
- Qwen2.5 representative subset: baseline vs full_guard
- demo cases: short presentation replay

Speaker note:
Stub is deterministic and broad. Qwen representative runs show model-facing behavior.

## Slide 5: Stub Results

Key numbers:

- baseline ASR 0.5507 and DSR 0.5507
- full_guard ASR 0.0000 and DSR 0.0000
- keyword_only reduces risk but leaves ASR 0.1304
- policy_only and full_guard reach WRS 0.9826

Speaker note:
Policy constraints at the tool boundary are the largest contributor.

## Slide 6: Qwen2.5 Results

Key numbers:

- baseline ASR 0.0833, UTR 0.0833, DSR 0.0417
- full_guard ASR 0.0000, UTR 0.0000, DSR 0.0000
- full_guard BSR 0.4583 and WRS 0.9187

Speaker note:
Even when the model is not always vulnerable, the Guard removes the observed unsafe tool behavior.

## Slide 7: Figures

Use these figures:

- `outputs/figures/day5_asr_by_defense_mode.png`
- `outputs/figures/day5_dsr_by_defense_mode.png`
- `outputs/figures/day5_wrs_by_defense_mode.png`
- `outputs/figures/day5_guard_reasons_top10.png`

Speaker note:
Show both risk reduction and explainability.

## Slide 8: Dashboard Demo

Command:

```powershell
streamlit run m3_eval/dashboard.py -- --logs outputs/runs/day5_qwen25_matrix --metrics outputs/metrics/day5_qwen25_summary.csv
```

Demo flow:

1. Overview metrics.
2. Baseline vs guarded table.
3. Attack family grouping.
4. Block records.
5. Single-case replay.
6. Raw log view.

## Slide 9: Limitations

- Qwen representative set has no clean cases under the current fixture labeling, so FPR is not informative.
- Rules can miss unseen semantic paraphrases.
- Metrics depend on correct attack-case labels.

Speaker note:
The honest limitation is also a future-work path: better clean controls and learned/semantic detectors.

## Slide 10: Final Message

M3-PI Guard turns prompt-injection defense into measurable behavior control for tool-using agents.

Speaker note:
The key outcome is reducing unauthorized tool calls and data spill while retaining a transparent reason trail.
