# Unified local configuration

M3 PI Guard uses one configuration schema but never shares real credentials.

## Files

- `project.env.example` is tracked. It defines the shared field names, frozen
  model revision and default development-machine paths.
- `project.local.env` is ignored. Each team member edits this one local file
  with personal tokens and machine-specific paths.

Do not rename the local file to a tracked filename and do not attach it to
issues, chat messages, reports, experiment manifests or delivery folders.

## First-time setup

If the local file is absent, copy the template:

```powershell
Copy-Item config\project.env.example config\project.local.env
```

Edit `config/project.local.env` and replace only the required local values.
For PromptGuard, the first required secret is `HF_TOKEN`. Every team member
must use a personal read-only token from the Hugging Face account that has
accepted the gated model terms.

Validate without exposing credentials:

```powershell
python scripts\check_project_config.py --require-promptguard-token
```

The output may say `set_redacted`; it must never contain the credential value.

## Frontier API Q2 slots

Frontier API models are optional but required before the Q2 readiness audit can
pass its two-vendor model-coverage gate. Keep all credentials in
`config/project.local.env`; never copy them into protocols, reports, manifests
or chat.

To prepare the slots, edit only the local file and set two distinct vendors:

```text
OPENAI_API_KEY=<your personal key>
FRONTIER_OPENAI_MODEL_ID=<exact model id approved for the paper>
ANTHROPIC_API_KEY=<your personal key>
FRONTIER_ANTHROPIC_MODEL_ID=<exact model id approved for the paper>
```

Leave the base-url fields as placeholders unless the team intentionally uses a
non-default compatible endpoint. Before any network smoke, also set the explicit
consent value:

```text
M3_FRONTIER_API_CONSENT=yes_for_network_smoke
```

The paper-v2 runtime also supports official DeepSeek and Gemini endpoints. Keep
their credentials in the same ignored local file:

```text
# Official DeepSeek API (OpenAI-compatible)
DEEPSEEK_API_KEY=<your personal DeepSeek key>
FRONTIER_DEEPSEEK_MODEL_ID=deepseek-v4-pro
FRONTIER_DEEPSEEK_BASE_URL=https://api.deepseek.com

# Official Gemini API (OpenAI-compatible)
GEMINI_API_KEY=<your personal Gemini API key>
FRONTIER_GEMINI_MODEL_ID=gemini-3.6-flash
FRONTIER_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

M3_FRONTIER_API_CONSENT=yes_for_network_smoke
```

Model names are rechecked against the official provider model endpoint during
the identity smoke; a configured name is never treated as proof of the returned
model. DeepSeek/Gemini inference is restricted by
`protocols/paper_upgrade_v2/provider_safety_policy_v1.json`: outbound traffic is
model inference only, model-proposed tool calls are untrusted data, and effects
may run only in M3 sandbox fixtures or copied AgentDojo in-memory environments.
Real email, payment, production API, arbitrary command, credential, and host
filesystem operations are forbidden.

Then run the gates in order:

```powershell
python -m experiments.paper_v1.benchmarks.audit_frontier_api_model_slots
python -m experiments.paper_v1.benchmarks.smoke_frontier_api_models
python -m experiments.paper_v1.benchmarks.smoke_frontier_api_models --execute
python -m experiments.paper_v1.benchmarks.admit_frontier_api_model_slots
python -m experiments.paper_v1.benchmarks.audit_frontier_api_model_slots
python -m experiments.paper_v1.benchmarks.audit_q2_readiness
```

The first smoke command is plan-only and performs no network calls. The
`--execute` command sends only a fixed synthetic smoke prompt, not unpublished
M3 cases, tool outputs, private notes or experiment results. The admission step
uses the redacted smoke manifest to write a new registry candidate; it does not
promote smoke runs into formal paper tables.

## PromptGuard bootstrap

The following command validates the configuration without network access:

```powershell
& "E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe" `
  scripts\promptguard_setup_from_config.py --check-only
```

After that check passes, omit `--check-only` to download the exact frozen
revision and write a SHA-256 snapshot. The download remains a qualification
step, not a formal experiment result.

After a successful download, run the real local-only smoke with the frozen
snapshot path recorded in
`E:\M3_PI_Guard_runtime\promptguard\evidence\promptguard_download_snapshot.json`:

```powershell
& "E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe" `
  -m experiments.paper_v1.benchmarks.promptguard_real_smoke `
  --snapshot-path "E:\AI_Cache\huggingface\hub\models--meta-llama--Llama-Prompt-Guard-2-86M\snapshots\a8ded8e697ce7c355e395a0df51f94adb4a2fd27" `
  --download-snapshot "E:\M3_PI_Guard_runtime\promptguard\evidence\promptguard_download_snapshot.json" `
  --revision a8ded8e697ce7c355e395a0df51f94adb4a2fd27
```

This fixed 12-case run is real-model qualification evidence only. It must not
be inserted into the formal paper tables.

## Migration contract

Move the repository with `project.env.example`, not `project.local.env`.
On the destination machine, create a new local file, update local paths and use
that member's own credentials. Large datasets and model weights remain outside
the repository; the config stores their paths, revisions and evidence paths.
