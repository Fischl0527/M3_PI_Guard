# IPIGuard TDG adapter preflight v1

Generated: 2026-07-22T08:22:54.397412+00:00

## Result

- Status: `ready_for_official_source_smoke`
- Source checkout ready: `True`
- Stub smoke completed: `True`
- Formal result eligible: `False`

## Source probe

- `python_executable`: F:\robot\Anaconda3\python.exe
- `python_version`: 3.13.5
- `expected_repository`: https://github.com/Greysahy/ipiguard
- `expected_commit`: 4e686ed2f62c135cb12564a4466daa95f3ace878
- `checkout_path`: external/baselines/ipiguard
- `checkout_exists`: True
- `checkout_git_head`: 4e686ed2f62c135cb12564a4466daa95f3ace878
- `checkout_git_available`: True
- `checkout_matches_expected_commit`: True

## Stub smoke

| Case | Decision | Risk edges | Forbidden-key clean |
|---|---|---:|---|
| `ipiguard:stub:attack:0001` | `deny_stub_untrusted_side_effect` | 1 | `True` |
| `ipiguard:stub:benign:0001` | `allow_stub_compatible` | 0 | `True` |

## Boundary

Adapter preflight only. Stub smoke validates online-only TDG input construction and trusted/untrusted source separation; it is not an IPIGuard algorithm result. Formal use requires the exact official source commit, graph rules, dependencies, adapters and complete logs.
