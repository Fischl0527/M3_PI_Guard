# Cover letter draft

Status: scientific wording closed without a cross-provider claim;
corresponding-author details and the submission date remain author-owned fields.

Dear Editors of the *Journal of Information Security and Applications*,

Please consider our original research article, “Evaluating Authorization
Regimes and Runtime Guardrail Configurations for Tool-Using LLM Agents,” for
publication in the *Journal of Information Security and
Applications*.

Tool-using language-model agents can convert untrusted content into externally
meaningful actions, yet prompt-injection evaluations often treat authorization
as fixed infrastructure. Our study instead evaluates runtime authorization as
an experimental treatment. Raw evaluator, scoring, and gold-answer fields
remain offline, while a derived exact-authorization object is tested only as a
sensitivity condition. The study jointly measures executed unsafe effects,
benign-tool completion, system confirmation-request and blocking incidence, operational failures,
latency, and adaptive attack budget.

Across completed public experiments with DeepSeek V4 Pro and V4 Flash, the
full configuration package reduced unsafe effects relative to a structural
baseline but did not outperform the policy package. A contemporaneous 2×2
experiment subsequently separated the prompt profile from the runtime module
bundle and found no clear positive module, prompt, or interaction contribution.
A prospectively frozen 900-work-item authorization study further showed that
pooled utility effects reversed by benchmark: exact authorization improved
AgentDojo completion but reduced both M3-v2 configuration cells to 0/30. The
pessimistic unsafe-or-failure bound also increased from 7% to 25% under the
policy package and from 8% to 26% under the full package. A controlled
source-authority experiment showed provenance-sensitive full-Guard decisions,
but all end-to-end actions remained blocked or pending confirmation. In a separate
defense-aware panel, first unsafe effects increased from
4/40 tasks by query 50 to 18/40 by query 200, demonstrating why a single low
attack budget is an incomplete evaluation. None of 12 prespecified B200
survivors first succeeded by query 500, but the Wilson upper limit remained
24.25%. A separately executed, historically risk-enriched single block observed
17/60 no-defense unsafe effects, while policy/normal and full/safe produced 2/60
and 0/60; 47/60 tasks overlapped the E3 challenge sample. This conditional result
is not a deployment-rate, utility, temporal-repeatability, independent-sample,
or isolated-module claim. Two incomplete Gemini attempts leave cross-provider
effects not estimable.

The manuscript fits the journal’s focus on access control, security policy,
and practical information-security systems. Its contribution is an empirical
evaluation method and a bounded account of security–utility trade-offs, not a
claim of a universally leading defense. We believe the bounded configuration
comparison, factorial analysis, source-only counterfactual, two public
benchmarks, and explicit accounting of failures and system confirmation
requests will be useful to researchers and practitioners
evaluating security controls for tool-using agents.

Thank you for considering the manuscript.

Sincerely,

The authors
