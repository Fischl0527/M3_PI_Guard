# E11 Post-hoc Protocol Amendment Analysis

> This is a post-hoc protocol amendment (`pre_registered=false`). Its 48 formal runs are supplementary and are excluded from the original E11 denominator.

## Pattern-level results

| Pattern | Guard off ASR | Full Guard ASR | Full−off difference (95% paired bootstrap CI) | McNemar p | Holm p |
|---|---:|---:|---:|---:|---:|
| read → send | 3/6 (50.0%) | 0/6 (0.0%) | -50.0% [-83.3%, -16.7%] | 0.25 | 0.5 |
| search → API | 5/6 (83.3%) | 0/6 (0.0%) | -83.3% [-100.0%, -50.0%] | 0.0625 | 0.25 |
| memory → file | 1/6 (16.7%) | 0/6 (0.0%) | -16.7% [-50.0%, +0.0%] | 1 | 1 |
| tool output →
next action | 5/6 (83.3%) | 0/6 (0.0%) | -83.3% [-100.0%, -50.0%] | 0.0625 | 0.25 |

## Interpretation boundary

Each row is independently denominated at six paired cases. McNemar tests are exact; bootstrap intervals use 10,000 case-paired resamples; Holm correction covers the four pattern-level ASR tests. Effect sizes and intervals, not a single p-value, govern the description.

Across the condition-by-pattern cells, parse success was 78/80 step outputs and unresolved case-runs totaled 2. These operational failures remain in the original per-pattern denominators and are available in the raw index and case replay files.

The amendment does not estimate benign-task FPR or TCR, does not replace the original E11 result, and must not be described as pre-registered or pooled with the original blind matrix.
