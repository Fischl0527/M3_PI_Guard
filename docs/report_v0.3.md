# M3-PI Guard Report v0.3

## 1. Project Scope

M3-PI Guard is a local behavior-supervision layer for tool-using LLM agents. The system focuses on whether an agent should execute a proposed tool call, rather than judging only the final natural-language answer.

The local range uses simulated tools only:

- `read_file`
- `write_file`
- `send_email`
- `call_api`
- `run_code`
- `final`

No real external API, mailbox, or public network target is required for the evaluation artifacts in this repository.

## 2. Threat Model

The evaluated attacks attempt to convert untrusted text into unauthorized tool behavior:

- direct jailbreak and role-play authorization pressure
- RAG / document-based indirect prompt injection
- JSON/RPC structured injection
- multilingual and T2L obfuscation
- tool-output injection
- secret read and data exfiltration through email or mock API calls

The protected assets are local sandbox secrets, canary strings, API-key-like content, and the integrity of the agent's intended user task.

## 3. Guard Design

The Guard exposes one stable interface:

```python
def guard_decide(context: dict, tool_call: dict) -> tuple[str, float, list[str]]:
    ...
```

The decision is one of `allow`, `ask`, or `deny`. The risk score is normalized to `[0, 1]`, and reasons are machine-readable strings used by metrics and the dashboard.

The DAY5 Guard includes:

- Unicode normalization, zero-width stripping, and mixed-script detection
- pinyin / homophone evasion detection
- instruction-like text detection
- JSON/RPC structured field detection
- policy matrix for file, email, API, and code execution tools
- sensitive dataflow detection from observations to external tools
- tool-output injection scanning
- intent-action mismatch detection

## 4. Evaluation Setup

DAY5 evaluates three run groups:

| Run group | Input directory | Case file | Purpose |
|---|---|---|---|
| Stub full matrix | `outputs/runs/day5_stub_matrix` | `m3_attacks/cases/all_cases.jsonl` | deterministic four-mode regression |
| Qwen2.5 representative | `outputs/runs/day5_qwen25_matrix` | `fixtures/day5_representative_cases.jsonl` | model-backed representative sample |
| Demo cases | `outputs/runs/day5_demo_matrix` | `fixtures/demo_cases.jsonl` | short dashboard and defense demo |

Generated final artifacts:

- `outputs/metrics/day5_final_summary.csv`
- `outputs/metrics/day5_final_summary.json`
- `outputs/figures/*.png`

## 5. Metrics

The report uses behavior-level metrics:

- ASR: attack success rate
- UTR: unauthorized tool-call rate
- DSR: data spill rate
- BSR: block success rate
- FPR: false positive rate
- AvgRisk: average Guard risk score
- WRS: weighted resilience score

## 6. Results

### Stub Full Matrix

| Defense mode | ASR | UTR | DSR | BSR | WRS |
|---|---:|---:|---:|---:|---:|
| baseline | 0.5507 | 0.2899 | 0.5507 | 0.0000 | 0.4891 |
| keyword_only | 0.1304 | 0.0870 | 0.1304 | 0.6522 | 0.8587 |
| policy_only | 0.0000 | 0.0000 | 0.0000 | 0.8841 | 0.9826 |
| full_guard | 0.0000 | 0.0000 | 0.0000 | 0.8841 | 0.9826 |

The stub matrix shows that policy-level checks are the strongest single component for this benchmark. Keyword-only filtering improves resilience but still leaves residual attack success and data spill.

### Qwen2.5 Representative Sample

| Defense mode | ASR | UTR | DSR | BSR | AvgRisk | WRS |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.0833 | 0.0833 | 0.0417 | 0.0000 | 0.0000 | 0.7958 |
| full_guard | 0.0000 | 0.0000 | 0.0000 | 0.4583 | 0.4375 | 0.9187 |

On the representative Qwen2.5 subset, full_guard eliminates observed attack success, unauthorized tool calls, and data spill in the available logs.

### Demo Cases

| Defense mode | ASR | UTR | DSR | BSR | AvgRisk | WRS |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.8500 |
| full_guard | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.9833 | 1.0000 |

The demo run is optimized for presentation: it clearly shows blocked high-risk behavior and visible Guard reasons.

## 7. Figures

The DAY5 figure set is generated under `outputs/figures/`:

- `day5_asr_by_defense_mode.png`
- `day5_utr_by_defense_mode.png`
- `day5_dsr_by_defense_mode.png`
- `day5_bsr_by_defense_mode.png`
- `day5_fpr_by_defense_mode.png`
- `day5_wrs_by_defense_mode.png`
- `day5_asr_by_attack_family.png`
- `day5_guard_reasons_top10.png`

## 8. Dashboard

Run:

```powershell
streamlit run m3_eval/dashboard.py -- --logs outputs/runs/day5_qwen25_matrix --metrics outputs/metrics/day5_qwen25_summary.csv
```

The dashboard supports:

- project overview metrics
- baseline vs guarded comparison
- attack-family grouped metrics
- carrier/language/severity/model/defense-mode grouping
- block records
- single-case replay
- raw log inspection

## 9. Limitations and Data Notes

- The Qwen2.5 representative fixture currently reports `clean_cases=0`; FPR is therefore not informative for that subset.
- The Guard remains rule-based. Strong semantic paraphrases or unseen obfuscation can evade static rules.
- The metrics depend on `unsafe_target_actions` labels and RunLog completeness.
- The demo set is intentionally small and presentation-oriented; it should not be read as full benchmark coverage.

## 10. Conclusion

DAY5 results support the main project claim: behavior supervision at the tool-call boundary can sharply reduce unauthorized actions and data spill without requiring a remote judge model. The most defensible message for the final presentation is that M3-PI Guard converts prompt-injection evaluation from text-only refusal checks into measurable agent behavior control.
