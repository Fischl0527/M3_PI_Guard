# E5 second execution-cost amendment

## Material Passport

- Study: `m3-q2-incremental-empirical-v1`
- Component: E5 B200-survivor adaptive tail
- Date: 2026-08-28
- Status: owner-authorized operational amendment
- Scientific design changed: no

## Reason

The first cost amendment raised the adaptive/global fuses to CNY 20/CNY 30
after 898 query work items. The owner later stopped the active process and
subsequently issued a new explicit instruction to continue the project.

At the resumed checkpoint, E5 contains 2,379 unique query keys and has spent
CNY 17.9303736. Seven of twelve tasks reached query 500, one stopped at query
474, one retains only its query-201--205 formal prefix, and three are
untouched. The remaining maximum path contains 1,222 unique queries. Using the
observed cumulative average gives a projected additional cost of about CNY
9.2 and a projected E5 total near CNY 27.2. The CNY 20 adaptive fuse and CNY 30
global fuse therefore cannot close the frozen cohort even when execution is
healthy.

The owner then explicitly directed that cost must not limit the project. The
adaptive and incremental global fuses are therefore set to a deliberately
non-blocking CNY 1,000 each. These values remain machine-readable safety
ceilings rather than experimental budgets. Pro and Flash regular-study fuses
remain CNY 8 and CNY 3 because those studies are already terminal. This is a
cost-policy-only correction made while no E5 process is running; all actual
usage and cost continue to be recorded for disclosure.

## Invariants

This amendment does not change:

- the twelve selected B200 survivors or their A1/A2/A3 balance;
- query indices 201--500;
- the attacker, model, prompt, runtime modules, authorization regime, or seed;
- first-unsafe-effect stopping;
- append-only attempts, explicit response-less-only recovery, or ITT handling;
- provider-tools-disabled and real-effects-disabled controls;
- the conditional estimand or the prohibition on a complete-panel B500 or
  saturation claim.

The only eligible recovery at resume is the existing response-less
`adaptive-cost-v1__M3V2-D-077-A2__q00474` work key. Previously successful or
response-bearing queries remain ineligible for replay.
