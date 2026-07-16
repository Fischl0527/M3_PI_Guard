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

- Do not run Python unittest discovery against a missing local tests directory; it can resolve an unrelated installed `tests` package.
- Runpro's interim ledger validator rejects `pending`; use `in progress` until final statuses are available.
- Runpro final ledger validation accepts only `satisfied`, `blocked` or `not applicable`; do not leave stale execution statuses at handoff.
- Never update a blind-freeze hash to excuse post-freeze presentation changes; isolate presentation code under a new path and preserve the frozen source byte-for-byte.
- A registry status of completed is distinct from target attainment: the final program is execution-complete even though four A00-A11 engineering targets failed and remain visible.

## Do Not Store

- API keys
- Passwords
- Private tokens
- Full secret-bearing logs
- Personal data that is not required for engineering work
