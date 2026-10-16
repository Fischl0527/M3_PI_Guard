# Abstract — lean empirical study

Status: `corrected_v2_sources_updated_bilingual_layout_pending`

Authorization scope materially changed benign task completion in our evaluation
of runtime guardrails for tool-using language-model agents. After correcting a
target matcher, we compared compiled and exact-target authorization across 900
DeepSeek Pro assignments over 180 fixed cases. Ordinary prompts were held fixed
across policy and full-module conditions. AgentDojo benign-tool completion rose
from 2/30 with compiled authorization to 13/30 with exact-target policy and
11/30 with exact-target full modules. M3-v2 completion differences were small
and uncertain.

A separately executed, 480-assignment contemporaneous calibration compared
guarded conditions with an unguarded control on an overlapping cohort. On
AgentDojo, policy and full modules reduced benign completion from 17/30 to
2/30, a paired difference of −50 percentage points (95% CI −66.83 to −26.80).
Sparse security events left the corresponding security difference uncertain.
Sixteen synthetic Pro/Flash runs verified private-data restrictions and
missing-classification handling within the tested component scenarios.

Together, these findings identify authorization burden as a measurable part of
the security–utility trade-off. Separating authorization, simulated execution,
task completion, failures, and unknown outcomes makes that burden visible and
provides a basis for evaluating runtime guardrails beyond module activation.

Keywords: prompt injection; LLM agents; runtime authorization; provenance;
security–utility trade-off
