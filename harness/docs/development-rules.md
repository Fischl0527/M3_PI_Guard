# Development Rules

## General Rules

- Read before editing.
- Keep changes small and scoped.
- Preserve existing architecture and style unless the task explicitly changes it.
- Prefer existing project utilities, patterns, and abstractions.
- Avoid unrelated formatting churn.
- Update tests and docs when behavior changes.
- Record architectural decisions in `harness/docs/decision-log.md`.

## Task Scope Rules

Every task must define:

- Goal
- Allowed files or directories
- Forbidden files or directories
- Acceptance criteria
- Verification commands

If scope is unclear, the agent may inspect the codebase, but must not make risky
changes until scope is clarified.

## Code Rules

- Implement the smallest design that satisfies the task.
- Do not introduce a new dependency without a recorded reason.
- Do not add broad abstractions for one-off behavior.
- Keep public interfaces stable unless the task requires a change.
- Make errors explicit and actionable.
- Keep comments concise and useful.

## Testing Rules

- Add or update tests for changed behavior.
- Use the nearest existing test pattern.
- Run targeted checks during development.
- Run the full verification loop before claiming completion when feasible.
- If a check is unavailable, record the reason.
- Do not mark a feature `verified` with failing required checks.

## Documentation Rules

Update documentation when:

- User-visible behavior changes.
- Setup, commands, or environment assumptions change.
- Architecture or module boundaries change.
- A decision creates future maintenance obligations.

## Security Rules

- Never read or output secrets.
- Never commit credentials.
- Never weaken authentication, authorization, or permission checks without
  explicit instruction and review.
- Treat production deployment and database mutation as confirmation-required
  actions.
- Sanitize logs before recording them in repository files.

## Git And Repository Rules

- Do not destroy user work.
- Do not run destructive history commands unless explicitly requested.
- Do not revert unrelated changes.
- Keep generated artifacts out of commits unless they are intended source assets.
- Record meaningful changes in task history.

## Feature Status Rules

Use `harness/features/feature_list.json` as the delivery ledger.

- `planned`: feature is known but not started.
- `in_progress`: implementation or verification is underway.
- `verified`: implementation, acceptance criteria, and required checks passed.
- `blocked`: work cannot continue without a decision, dependency, or external fix.

Never use `verified` as a synonym for "implemented".
