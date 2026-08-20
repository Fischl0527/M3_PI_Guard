# Cover letter draft

Status: provisional; update only if the prespecified Gemini stopping rule adds
a defensible cross-provider result. Corresponding-author details and the
submission date remain author-owned fields.

Dear Editors of the *Journal of Information Security and Applications*,

Please consider our original research article, “Evaluating Runtime
Authorization Under Context and Provenance Uncertainty for Tool-Using LLM
Agents,” for publication in the *Journal of Information Security and
Applications*.

Tool-using language-model agents can convert untrusted content into externally
meaningful actions, yet prompt-injection evaluations often treat authorization
as fixed infrastructure. Our study instead evaluates runtime authorization as
an experimental treatment. Raw evaluator, scoring, and gold-answer fields
remain offline, while a derived exact-authorization object is tested only as a
sensitivity condition. The study jointly measures executed unsafe effects,
benign-tool completion, confirmation and blocking burden, operational failures,
latency, and adaptive attack budget.

Across completed public experiments with DeepSeek V4 Pro and V4 Flash, the
full provenance-aware runtime reduced unsafe effects relative to a structural
baseline but did not outperform a policy-only ablation. A prospectively frozen
900-work-item authorization study further showed that evaluator-derived exact
authorization could leave attack outcomes near the observed floor while
reducing benign-tool completion by 21.67 percentage points under policy-only
and 15.00 points under the full runtime. Exact authorization also replaced
confirmation with frequent denial and increased operational failure and
latency. In a separate defense-aware panel, first unsafe effects increased from
4/40 tasks by query 50 to 18/40 by query 200, demonstrating why a single low
attack budget is an incomplete evaluation.

The manuscript fits the journal’s focus on access control, security policy,
and practical information-security systems. Its contribution is an empirical
evaluation method and a bounded account of security–utility trade-offs, not a
claim of a universally leading defense. We believe the negative module result,
paired authorization analysis, two public benchmarks, and explicit accounting
of failures and operator burden will be useful to researchers and practitioners
evaluating security controls for tool-using agents.

Thank you for considering the manuscript.

Sincerely,

The authors
