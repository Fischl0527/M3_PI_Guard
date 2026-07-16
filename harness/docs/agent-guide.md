# Agent Guide

This guide explains how an AI coding agent should operate inside this repository.

## Start Of Session

Read these files first:

1. `AGENTS.md`
2. `harness/state/current-task.md`
3. `harness/docs/architecture.md`
4. `harness/state/progress.md`

Then load relevant support files:

- `harness/features/feature_list.json`
- `harness/specs/product-spec.md`
- `harness/specs/technical-spec.md`
- `harness/specs/acceptance-criteria.md`
- `harness/docs/development-rules.md`
- `harness/docs/decision-log.md`
- `harness/state/memory.md`
- `harness/state/session-handoff.md`

## Creating A Task

Use `harness/tasks/task.md` as the task record template.

A task must include:

- Goal
- Scope
- Plan
- Implementation record
- Verification record
- Final report

Update `harness/state/current-task.md` with the active task summary.

## During Implementation

- Inspect relevant code before edits.
- Keep changes small.
- Update task notes after meaningful steps.
- Record architectural decisions immediately.
- Record failures in `harness/state/failure-log.md`.
- Update feature status as work progresses.

## Verification

Use the strongest available command on the primary Windows runtime:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1
```

The equivalent WSL/Git Bash wrapper is:

```bash
bash harness/scripts/verify.sh
```

For local iteration, use narrower commands such as:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/test.ps1
```

Always record:

- Command
- Result
- Important output
- Skipped checks and reason

## Completing A Task

Before claiming completion:

1. Confirm acceptance criteria are met.
2. Confirm required verification passed.
3. Update `harness/features/feature_list.json`.
4. Update `harness/state/progress.md`.
5. Update `harness/state/task-history.md`.
6. Update `harness/state/session-handoff.md`.
7. Write a final report with evidence.

## Handling Failure

When a failure occurs:

1. Record the error.
2. Explain the likely cause.
3. Record attempted fixes.
4. Try a changed hypothesis.
5. Stop if the next step needs confirmation.

Do not repeat an identical failed attempt.

## Handoff

At the end of a session, make sure `harness/state/session-handoff.md` answers:

- What is the current task?
- What changed?
- What remains?
- What commands were run?
- What is the next best action?
- Are there blockers or risks?
