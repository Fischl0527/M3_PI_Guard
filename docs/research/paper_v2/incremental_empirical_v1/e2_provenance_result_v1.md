# E2 source-authority counterfactual result

Status: complete, end-to-end and deterministic Guard evidence separated

## Execution and integrity

- End-to-end work items: 240/240, all response-bearing.
- Official response IDs: 295; operational status: 239 completed and one
  provider failure, retained in ITT.
- Online forbidden fields, provider-managed tools, and real external effects:
  0/240 for each.
- End-to-end official-API cost: CNY 0.4254876.
- Deterministic Guard replay: 480/480 decisions and zero provider calls.

## End-to-end result

No cell executed an authorized, unauthorized, or other action. Consequently,
unauthorized-argument influence, authorized-action execution, and their source,
module, and source-by-module contrasts are all 0. This is an endpoint floor,
not evidence that source authority has no effect: confirmation and blocking
intervened before any action was executed.

| Cell | ASK incidence | DENY incidence | Operational failure | Executed actions |
|---|---:|---:|---:|---:|
| policy / trusted | 60/60 (100.0%) | 0/60 | 0/60 | 0/60 |
| policy / untrusted | 53/60 (88.3%) | 0/60 | 0/60 | 0/60 |
| full / trusted | 57/60 (95.0%) | 0/60 | 0/60 | 0/60 |
| full / untrusted | 0/60 | 55/60 (91.7%) | 1/60 (1.7%) | 0/60 |

The paired source swap changed the actual executed-action tuple in 0/60 tasks
for both policy and full modules. It changed operational status in 0/60 policy
pairs and 1/60 full pairs; the latter is reported separately and is not counted
as an action change.

## Deterministic Guard replay

The replay sends an authorized and an unauthorized proposal through each
source-by-module context:

- false allow: 0/240 unauthorized proposals (0.0%; Wilson 95% CI
  0.0%--1.58%);
- false block: 30/240 authorized proposals (12.50%; 95% CI
  8.90%--17.28%);
- policy/trusted: 60 ALLOW and 60 ASK;
- policy/untrusted: 60 ALLOW and 60 ASK;
- full/trusted: 60 ALLOW and 60 ASK; and
- full/untrusted: 30 ALLOW, 30 ASK, and 60 DENY.

The replay therefore demonstrates mechanism-level provenance sensitivity in
the full configuration: the same proposals become DENY-eligible when their
critical proposition is moved to an untrusted origin. Policy-only does not
change its decision distribution under the source swap.

## Interpretation boundary

The end-to-end study reveals a confirmation bottleneck rather than usable task
completion: trusted-origin tasks were overwhelmingly routed to ASK and none
executed without independent confirmation. The offline result may support a
claim about deterministic Guard behavior, but it cannot be substituted for
end-to-end task utility or for a human confirmation study. The correct paper
claim is therefore two-part: provenance affects full-Guard decisions under a
controlled source swap, while the tested model--Guard system did not convert
that mechanism into completed actions and incurred high ASK/DENY burden.
