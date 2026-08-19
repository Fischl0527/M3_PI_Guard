# IPIGuard source-backed formal freeze v1

- Status: `completed_frozen_formal_protocol`
- Condition: `ipiguard_source_backed`
- Model: `m3-paper-qwen3-8b-v1:latest`
- Cases: 726 (97 utility + 629 security)
- Attack: `direct`
- IPIGuard commit: `4e686ed2f62c135cb12564a4466daa95f3ace878`
- Checks: 9/9
- Result eligible: `False` until complete execution and analysis are admitted.

## Disclosed compatibility boundary

- The construct, traverse and DAG executor classes are loaded from the pinned IPIGuard source without editing that checkout.
- The unused Vertex provider package initializer is isolated; the exact upstream empty-function sentinel is pinned and reproduced.
- The agent model is the frozen local Qwen3 8B paper alias through Ollama's OpenAI-compatible endpoint.
- The direct AgentDojo attack is used so this cell matches the other frozen official-baseline cells; the IPIGuard repository's native default is recorded separately.
- All 726 cases must have unique manifests and complete raw traces; qualification and partial runs remain diagnostic.

## Evidence boundary

This freeze declares a source-backed IPIGuard adapter over the frozen 726-case AgentDojo universe. It is not the upstream CLI byte-for-byte because the unused Vertex provider import is isolated and Ollama supplies the OpenAI-compatible model. The local runner/analyzer/protocol are hash-bound and the runner records raw DAG JSON before delegating to the unchanged upstream parser. No result is formal until a complete explicitly admitted run has zero unexplained failures.
