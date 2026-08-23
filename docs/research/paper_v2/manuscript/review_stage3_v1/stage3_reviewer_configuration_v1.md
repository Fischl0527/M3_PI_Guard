# Stage 3 Reviewer Configuration

## Frozen review baseline

- Repository commit: `119b1b1c0d158c41de485b969830c370ca951b1a`
- Branch: `codex/q2-empirical-study`
- Review target: English manuscript `manuscript_deepseek_v1.md`
- Intended journal: *Journal of Information Security and Applications* (JISA)
- Article type: original empirical research article
- Review mode: internal author-side scientific review before submission
- Review date: 2026-08-23

This review does not represent an Elsevier or JISA editorial review. The current
JISA Guide for Authors prohibits generative-AI use by journal reviewers and
editors. The present panel is instead an internal manuscript-quality exercise
conducted by the authors before any submission.

## Journal and field fit

The manuscript sits at the intersection of information security, access control,
security policy, tool-using LLM agents, prompt injection, and empirical systems
evaluation. JISA is a plausible scope match because its official aims include
practice-driven information-security research and its listed topics include
authentication and access control and security management and policies. The
review therefore emphasizes security-effect validity, authorization semantics,
runtime isolation, task utility, operational failure, and reproducibility rather
than NLP benchmark score alone.

## Frozen sprint contract

- Contract: `reviewer/reviewer_full/v1`
- Panel size: 5
- Mandatory dimensions: D1 methodology rigor, D2 domain accuracy, D3
  argumentative coherence
- High-priority dimension: D4 cross-disciplinary relevance
- Normal-priority dimension: D5 writing and structure
- Allowed dimension outcomes: `block`, `warn`, `pass`

Mechanical decision rules:

1. If any reviewer assigns `block` to a mandatory dimension, the outcome is at
   least reject-or-major-revision.
2. If at least four of five reviewers identify warn-or-worse on two or more
   mandatory dimensions, the outcome is major revision.
3. If any reviewer assigns `block` to D4, the outcome is at least major revision.
4. Acceptance requires all five reviewers to assign `pass` to every mandatory
   dimension.

## Independent reviewer roles

1. **Editor-in-Chief reviewer.** Assesses JISA fit, contribution visibility,
   editorial readiness, claim calibration, and whether the work offers a
   coherent information-security contribution.
2. **Methodology reviewer.** Assesses design validity, estimands, sampling,
   paired comparisons, failure handling, multiplicity, uncertainty, and the
   relationship between confirmatory and descriptive evidence.
3. **Domain reviewer.** Assesses correctness and novelty relative to LLM-agent
   prompt-injection defenses, authorization/provenance mechanisms, and current
   benchmark practice.
4. **Cross-disciplinary perspective reviewer.** Assesses whether `ASK`, `DENY`,
   task completion, and operational burden are interpretable as usable-security
   outcomes, including implications for human confirmation.
5. **Devil's Advocate reviewer.** Constructs the strongest rejection case,
   searches for alternative explanations and hidden assumptions, and tests
   whether the conclusions survive the least favorable reasonable reading.

## Review boundaries

- Reviewers may recommend new offline analyses or textual clarification.
- Reviewers may not rewrite or edit the manuscript during Stage 3.
- New provider calls, new experiment conditions, full Harness runs, historical
  evidence replay, blind-study work, and hash-package generation are out of
  scope.
- Existing successful experiment rows are immutable.
- Every finding must identify a manuscript section or evidence artifact and
  state whether it is critical, major, or minor.
- Stage 4 manuscript revision does not begin until the consolidated editorial
  decision is available at the author checkpoint.

## Primary-source venue basis

- JISA, “Guide for authors,” ScienceDirect, accessed 2026-08-23:
  https://www.sciencedirect.com/journal/journal-of-information-security-and-applications/publish/guide-for-authors
- JISA, “About the journal,” ScienceDirect, accessed 2026-08-23:
  https://www.sciencedirect.com/journal/journal-of-information-security-and-applications

