# Glossary

- **ASK:** A runtime Guard decision that withholds the proposed effect until an
  independent confirmation decision is supplied.
- **Authorization regime:** The procedure and information used to construct the
  policy visible to the online Guard.
- **`auto_compiled`:** A non-oracle authorization regime compiled from trusted
  task context without evaluator or gold-answer fields.
- **`broad`:** A stress regime that deliberately grants a wider action space
  than the task-specific non-oracle policy.
- **`conflicting`:** A stress regime containing mutually inconsistent
  authorization constraints.
- **DENY:** A runtime Guard decision that prevents the proposed effect.
- **`exact_gold`:** An oracle-sensitivity regime reconstructed from
  evaluator-side expected-action information; it is not the deployment-realistic
  primary authorization regime.
- **Intention-to-treat (ITT):** Analysis that keeps every frozen work item in its
  prespecified denominator, including operational failures and timeouts.
- **M3-full:** The evaluated Guard variant combining policy enforcement with
  provenance, temporal/data-flow and confirmation logic.
- **Operational failure:** A terminal provider, transport, parsing, refusal or
  maximum-step outcome that prevents ordinary task completion and remains in
  ITT analysis.
- **Policy-only:** The ablation that applies the same policy interface without
  the additional provenance, temporal/data-flow and confirmation modules.
- **Provenance:** Recorded evidence about the source and propagation of values
  used in a proposed tool action.
- **Task completion rate (TCR):** The proportion of frozen benign tasks whose
  intended benchmark objective is completed.
- **`underspecified`:** A stress regime that intentionally omits constraints
  needed to authorize all task-relevant actions.
- **Unsafe effect:** A benchmark-scored unauthorized state change that crosses
  the isolated runtime enforcement boundary.
