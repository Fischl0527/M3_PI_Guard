# E5 execution-cost amendment

## Material Passport

- Study: `m3-q2-incremental-empirical-v1`
- Component: E5 B200-survivor adaptive tail
- Date: 2026-08-26
- Status: approved operational amendment
- Scientific design changed: no

## Reason

The original plan estimated CNY 1--3 for at most 3,600 incremental adaptive
queries and set an adaptive fuse of CNY 5. After 898 latest query work items,
the cumulative provider ledger was CNY 4.2561534. The observed average implies
approximately CNY 17 for the maximum no-success path, so the original fuse
would stop the registered cohort for an engineering cost-estimation error.

The owner had already authorized normal DeepSeek use without letting the
initial estimate block completion. The adaptive fuse is therefore raised from
CNY 5 to CNY 20 and the incremental global fuse from CNY 16 to CNY 30. Pro and
Flash regular-study fuses remain CNY 8 and CNY 3.

## Invariants

This amendment changes only the maximum permitted spend. It does not change:

- the twelve selected B200 survivors or their A1/A2/A3 balance;
- query indices 201--500;
- the attacker, model, prompt, runtime modules, authorization regime, or seed;
- first-unsafe-effect stopping;
- append-only attempts, response-less-only recovery, or ITT handling;
- provider-tools-disabled and real-effects-disabled controls;
- the conditional estimand or the prohibition on a complete-panel B500 or
  saturation claim.

The amendment was recorded while no E5 process was running. Previously
successful queries are not replayed.
