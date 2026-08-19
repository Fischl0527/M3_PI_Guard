# PromptGuard detector adapter preflight v1

Generated: 2026-07-22T08:15:23.646848+00:00

## Result

- Status: `real_detector_smoke_completed_formal_run_pending`
- Real detector ready: `True`
- Real detector smoke completed: `True`
- Stub smoke completed: `True`
- Formal result eligible: `False`

## Dependency probe

- `python_executable`: E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe
- `python_version`: 3.13.5
- `model_id`: meta-llama/Llama-Prompt-Guard-2-86M
- `expected_revision`: a8ded8e697ce7c355e395a0df51f94adb4a2fd27
- `expected_revision_complete`: True
- `hub_cache_root`: E:\ai_cache\huggingface\hub
- `model_cache_path`: E:\ai_cache\huggingface\hub\models--meta-llama--Llama-Prompt-Guard-2-86M
- `model_cache_exists`: True
- `snapshot_count`: 1
- `snapshots`: [{'revision': 'a8ded8e697ce7c355e395a0df51f94adb4a2fd27', 'path': 'E:\\ai_cache\\huggingface\\hub\\models--meta-llama--Llama-Prompt-Guard-2-86M\\snapshots\\a8ded8e697ce7c355e395a0df51f94adb4a2fd27', 'file_count': 10, 'has_config': True, 'has_weights': True, 'has_tokenizer': True, 'complete': True}]
- `complete_snapshot_revisions`: ['a8ded8e697ce7c355e395a0df51f94adb4a2fd27']
- `model_cache_complete`: True
- `transformers_installed`: True
- `torch_installed`: True
- `huggingface_hub_installed`: True
- `local_files_only`: True

## Real detector qualification smoke

- Manifest: `outputs/paper_upgrade_v1/baselines/promptguard_real_smoke_v1/promptguard_real_smoke_manifest.json`
- SHA-256: `847d8d77f0890cb40bc8c8d1fc253d70e416175153d66bf91f719973ecc52282`
- Status: `completed_real_model_smoke`
- Cases: `12`
- Diagnostic exact match: `0.75`
- Formal table eligible: `False`

## Stub smoke

| Case | Decision | Score | Forbidden-key clean |
|---|---|---:|---|
| `promptguard:stub:attack:0001` | `malicious` | 0.910 | `True` |
| `promptguard:stub:benign:0001` | `benign` | 0.060 | `True` |

## Boundary

The 12-case real-model smoke is qualification evidence, while the stub smoke validates online-only record construction. Neither is a formal PromptGuard effect result. Formal use still requires tokenizer-aware windowing, a frozen benchmark manifest and complete detector logs.
