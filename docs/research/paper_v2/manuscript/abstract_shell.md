# Abstract — lean empirical study shell

Status: `new_authorization_results_pending`

Tool-using large-language-model agents can convert prompt injection into
external actions, but measured security depends on both the runtime mechanism
and the authorization information supplied to it. We study this dependence
with an online-state projection that excludes evaluator and gold-label fields,
paired comparisons of policy-only and provenance-aware runtime enforcement,
and explicit measurement of unsafe effects, benign task completion,
confirmation/blocking burden, operational failure, latency, and cost.

We first reanalyze completed DeepSeek evidence comprising a 480-record medium
study, a 5,082-record V4 Pro Public matrix, a 1,791-record V4 Flash Public
matrix, and 40 adaptive tasks at budgets 50 and 200. In the Pro matrix,
M3-full produced 38/600 unsafe effects versus 13/600 for policy-only, while
both completed 49/168 benign tool tasks. Flash showed the same direction
(24/400 versus 12/400 unsafe effects), with tool-task completion of 38/145 and
35/145. Adaptive search found a first unsafe effect for 4/40 tasks by budget 50
and 18/40 by budget 200; these two points do not establish saturation.

We then run a prospectively frozen 900-work-item DeepSeek V4 Pro experiment on
180 paired AgentDojo/M3-v2 cases, crossing policy-only and M3-full with
non-oracle `auto_compiled` and oracle-sensitivity `exact_gold`
authorization. A fixed 60-case subset adds `broad`, `underspecified`, and
`conflicting` regimes. A nested 90-case, 450-work-item Gemini 3.6 Flash sample
tests diagnostic cross-provider consistency under the official free tier.

`[Insert terminal paired unsafe-effect/TCR differences, 95% intervals,
McNemar/Holm results, ASK/DENY/failure/latency burden, and Gemini completion or
transparent diagnostic downgrade here. Do not fill before the compact terminal
analysis is written.]`

The study is positioned as an empirical evaluation of authorization regimes
and runtime security–utility trade-offs, not as a first, unique, or
state-of-the-art defense claim. Negative or inconsistent results are retained.
