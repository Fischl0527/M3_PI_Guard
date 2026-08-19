# Task Shield disclosed reproduction formal protocol v1.2

## Scope

This condition is a disclosed reproduction of the Task Shield paper and is
never labelled as an official-source implementation. It uses the frozen local
Qwen3 8B alias for both the AgentDojo agent and the alignment verifier, with
temperature 0 and contribution threshold 0.

## Frozen universe and evidence

- Execute all 97 AgentDojo utility tasks and all 629 direct-injection security
  cases exactly once.
- Preserve the official AgentDojo trace, every verifier request/response,
  parsed contribution scores, final tool effects, failures and timing.
- Invalid verifier JSON, timeout and parser failure remain in the original
  denominator. No failed case is silently retried.
- Qualification uses two fixed utility/security cases and is diagnostic only.
  A formal result requires 726 unique completed cases, zero unexplained
  failures, exact freeze coverage and explicit admission.

## Trusted-input boundary

Only the initial user request may define or extend the user task set. Tool
outputs, external documents, memory and generated assistant text remain
untrusted. The verifier never receives attack labels, target actions, expected
tool answers or evaluator-only fields.

## Resume and source identity

The v1.2 freeze hash-binds the reproduction runtime, import preflight, runner,
analyzer, this protocol and the shared resume-identity helper. Before any
Ollama probe, the runner rejects an existing output root whose freeze hash,
runner version, model, condition or selected-case hash differs. A changed
freeze therefore requires a new output directory; old rows cannot be silently
resumed.

## Analysis boundary

The analyzer must verify the admitted run manifest, exact case coverage,
outcome and trace hashes before computing utility, attack success, Wilson
intervals and figures. Diagnostic, partial, failed or unadmitted rows cannot be
promoted by the analyzer.
