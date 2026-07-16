# E9 V2 calibrated context/position analysis

- Semantic validity: **pass**; 120/120 formal first-step case-runs.
- No Guard ASR: 36/60 (60.00%).
- Full Guard ASR: 0/60 (0.00%).
- Parse failures retained: 14 first-step runs.
- Every exact first-turn prompt has frozen native Ollama token proof; a formal raw counter is preferred and the one-token preflight is used only when Ollama returns an explicitly non-final response.
- Provider-incomplete outcomes retained as non-executable errors: 6 case-runs.
- V3 E9 is preserved only as invalid diagnostic provenance and is not pooled with this denominator.

Interpret position and context trends from `context_position.csv` and the paired tests in `statistics.json`; each cell contains only three attacks, so Wilson intervals are intentionally wide.
