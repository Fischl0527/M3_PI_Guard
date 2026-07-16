# Agent Policies

## Repository As Source Of Truth

All durable task state must be written into repository files. Private chat memory
is not enough for long-running work.

Required state files:

- `harness/state/progress.md`
- `harness/state/current-task.md`
- `harness/state/session-handoff.md`
- `harness/state/task-history.md`
- `harness/features/feature_list.json`
- `harness/docs/decision-log.md`

## Verification Policy

The agent may not claim that code works based only on reasoning.

A valid completion claim requires:

- Commands run.
- Results observed.
- Failing or skipped checks explained.
- Acceptance criteria mapped to evidence.

Use:

```bash
bash harness/scripts/verify.sh
```

## Safety Policy

Read `harness/config/permissions.yaml` before risky actions.

The agent must ask for confirmation before:

- File deletion outside safe generated paths.
- Database changes.
- Production deployment.
- Permission system changes.
- Git history rewriting.

The agent must never:

- Access or output secrets.
- Bypass security rules.
- Disable tests to hide failures.
- Mark unverified work complete.

## Failure Policy

Failures are normal engineering events. Repeated blind retries are not.

For each meaningful failure, update `harness/state/failure-log.md` with:

- Error.
- Cause analysis.
- Attempts.
- Final resolution.
- Follow-up.

Before retrying, change the hypothesis or gather new evidence.

## Documentation Policy

Update documentation when a change affects:

- User behavior.
- Developer setup.
- Commands.
- Architecture.
- Security posture.
- Acceptance criteria.

## Handoff Policy

Every session must end with a usable handoff.

`harness/state/session-handoff.md` must include:

- Current task.
- Files changed.
- Commands run.
- Verification result.
- Open risks.
- Next recommended action.
