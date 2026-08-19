# AgentDojo transformers PI detector resource-isolation protocol v1

The first exact official CPU-detector root is retained as invalid diagnostic evidence after a 27,697-character tool output caused a 2,185,056,432-byte CPU attention allocation failure while other model-loading tests were active. It must not be resumed into or pooled with this protocol.

This recovery keeps AgentDojo's pinned `TransformersBasedPIDetector`, complete message-mode tool output, ProtectAI revision `90c9989b1a342275dd0d1a95aad283c04e075671`, `SAFE` label and threshold 0.5 unchanged. Before every CPU detector call, the wrapper asks the local Ollama service to unload the Qwen3 8B target with `keep_alive=0`. The next LLM request reloads the same frozen alias. The wrapper records unload counts and fails the case if unloading fails.

The policy changes only resource residency. It does not truncate, window, summarize, filter or otherwise transform detector input, and it does not change the detector output. A fresh output root is mandatory. Formal admission still requires all 97 utility and 629 security cases, unique exact coverage, complete official traces and zero failures. The old partial root and the one-case diagnostic reproduction remain excluded.
