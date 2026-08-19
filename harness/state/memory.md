# Agent Memory

This file stores durable project knowledge that should survive across sessions.
Do not store secrets, personal data, or large transient logs here.

## Stable Project Facts

- The repository uses an AI Agent Harness to manage context, task state,
  verification, and session continuity.
- `AGENTS.md` is the top-level agent working agreement.
- `harness/features/feature_list.json` is the feature status source of truth.
- The product baseline is `origin/team-a/m3-core-day7@2c53f52`; active development is local branch `test1`.
- M3-PI Guard is a local-only Agent tool-call safety range using mock file, email, API, and code tools.
- `experiments/registry.json` is the E0-E17 execution status source of truth.
- Stub runs are regression evidence only; formal effectiveness claims require local model runs.
- `outputs/experiments/program_manifest_final_v3.json` and `blind_freeze_v3.json` are the controlling formal program/freeze; invalidated or post-hoc roots must not be pooled silently.
- `m3_eval/dashboard.py` is a frozen provenance file; post-freeze UI work belongs in `m3_eval/evidence_dashboard.py`.

## Conventions

- Load context progressively instead of reading every file by default.
- Record decisions in `harness/docs/decision-log.md`.
- Record failures in `harness/state/failure-log.md`.
- Update `harness/state/session-handoff.md` before ending a session.
- Keep model-visible fields and evaluator-only labels separate.
- Compare defense conditions using the same case, model, prompt profile, generation settings, seed and replicate.
- Keep failed, timed-out, refused and parse-error runs in the denominator and evidence set.
- E17 requires two independent real human blind reviews; automated-agent reviews are diagnostic only. The accepted final protocol is a frozen 360-row two-human stratified audit: only its 300 representative rows support design-weighted population estimates, while 60 targeted rows remain diagnostic.
- Current scope excludes PPT, DOCX report and submission ZIP; final Git action is local commit only unless separately authorized.

## Lessons Learned

- Adaptive query work keys that are reused as trace filenames must be
  cross-platform path-safe at the identity layer. Do not silently rewrite only
  the path; use one Windows-safe identity (for example `__` separators) in the
  query, trace, budget and evaluator bindings.
- For adaptive official execution, fsync a content-free query `started` event
  before any provider request, keep each provider call in its independent
  request/response and cost chain, then append a query `terminal` that binds
  the complete call sequence. MCTS checkpoints alone are not call-level
  evidence.
- Do not run Python unittest discovery against a missing local tests directory; it can resolve an unrelated installed `tests` package.
- Runpro's interim ledger validator rejects `pending`; use `in progress` until final statuses are available.
- Runpro final ledger validation accepts only `satisfied`, `blocked` or `not applicable`; do not leave stale execution statuses at handoff.
- Never update a blind-freeze hash to excuse post-freeze presentation changes; isolate presentation code under a new path and preserve the frozen source byte-for-byte.
- A registry status of completed is distinct from target attainment: the final program is execution-complete even though four A00-A11 engineering targets failed and remain visible.
- A multi-step provider work item cannot be evidenced by only its last response.
  Current paper-v2 experiment-record 2.2 binds the ordered, content-free trace
  of every call plus the provider safety receipt; any open or unactivated call
  caps the whole record at diagnostic and is retained as an ITT failure.

## Do Not Store

- API keys
- Passwords
- Private tokens
- Full secret-bearing logs
- Personal data that is not required for engineering work
## 2026-07-24 — paper-v2 pilot admission ordering

- Do not call the official-provider pilot through a lower-level runtime. Use
  `formal_execution_controller_v2.py` so admission and single-use checks happen
  before credential access.
- `deepseek_pilot_admission_candidate_v2.json` is deliberately non-executable.
  Never edit it into an active admission or treat budget consent as pilot
  approval.
- The active path is single-use and bound to work key
  `fd89c79707414a035a9d4309c3c3125bde14f7260c0e4c9cd66088164076fbe7`;
  it remains unavailable until the project owner explicitly clears the
  academic pilot checkpoint.
- Even after a live pilot, its record is a candidate/diagnostic artifact pending
  review; it does not authorize the medium matrix or unlock an effect claim.

## 2026-07-24 — paper-v2 DeepSeek usage/cost evidence

- Every completed DeepSeek call in provider trace bundle 2.1 must include
  content-free cache-hit/cache-miss/output accounting, a provider receipt
  digest, exact request/cumulative CNY cost and the budget state.
- Validate usage identity and arithmetic against the terminal request trace
  before allowing `formal_candidate`; missing cache fields remain fail-closed.
- Offline fixture costs prove the contract only. Never describe them as
  empirical API pricing, cache performance or paper effect evidence.

## 2026-07-24 — paper-v2 post-pilot evidence review

- Experiment-record 2.2 persists `provider_safety_receipt`; do not accept a
  live record that only validated the receipt transiently.
- The official post-pilot reviewer must compare the independent trace file with
  the bundle and bind the active admission file digest, cost rows, safety
  action digest and record ledger tail.
- `offline_injected_qualification` can pass structural checks only. It must
  never set the official gate, owner-review readiness, matrix authorization or
  result admission.
# 2026-07-28 — Manuscript tables must be executable evidence views

- A manuscript status shell can become stale even when the claim ledger and
  scorecard are current. Every admitted numerical table should bind the source
  analysis hash/admission and have a focused test that rebuilds displayed
  numerators, denominators, intervals and operational prefixes.
- Legacy field names inside a frozen analysis must not be rewritten in place.
  Interpret them through their enclosing semantic key and disclose the naming
  limitation in the manuscript.
