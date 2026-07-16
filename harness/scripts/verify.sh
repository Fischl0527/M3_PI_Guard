#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
REQUIRE_EXPERIMENTS_COMPLETE="${REQUIRE_EXPERIMENTS_COMPLETE:-0}"
FAILED=0

resolve_python() {
  if [ -n "$PYTHON_BIN" ]; then
    if command -v "$PYTHON_BIN" >/dev/null 2>&1 || [ -x "$PYTHON_BIN" ]; then
      return 0
    fi
    printf 'configured PYTHON_BIN is unavailable: %s\n' "$PYTHON_BIN" >&2
    return 1
  fi

  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v where.exe >/dev/null 2>&1 && command -v wslpath >/dev/null 2>&1; then
    windows_python="$(where.exe python 2>/dev/null | sed -n '1{s/\r$//;p;}')"
    [ -n "$windows_python" ] || return 1
    PYTHON_BIN="$(wslpath -u "$windows_python")"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    return 1
  fi

  [ -x "$PYTHON_BIN" ] || command -v "$PYTHON_BIN" >/dev/null 2>&1
}

if ! resolve_python; then
  printf '%s\n' "FAIL: unable to resolve a Python interpreter" >&2
  exit 1
fi
export PYTHON_BIN

run_check() {
  name="$1"
  shift
  printf '\n== %s ==\n' "$name"
  if "$@"; then
    printf 'PASS: %s\n' "$name"
  else
    printf 'FAIL: %s\n' "$name"
    FAILED=1
  fi
}

check_files() {
  for required in \
    AGENTS.md harness/README.md \
    harness/docs/architecture.md harness/docs/development-rules.md \
    harness/docs/decision-log.md harness/docs/agent-guide.md \
    harness/state/progress.md harness/state/memory.md harness/state/current-task.md \
    harness/state/session-handoff.md harness/state/task-history.md harness/state/failure-log.md \
    harness/specs/product-spec.md harness/specs/technical-spec.md \
    harness/specs/acceptance-criteria.md harness/features/feature_list.json \
    experiments/registry.json harness/workspaces/runpro/10_analysis/approval-gate.md \
    harness/workspaces/runpro/10_analysis/requirement-ledger.md \
    harness/scripts/init.sh harness/scripts/verify.sh harness/scripts/test.sh \
    harness/scripts/cleanup.sh harness/scripts/verify.ps1 harness/scripts/test.ps1 \
    harness/config/permissions.yaml harness/config/policies.md harness/config/workflow.md
  do
    [ -f "$required" ] || { printf 'missing %s\n' "$required"; return 1; }
  done
}

check_boundary() {
  for legacy in \
    README_AGENT.md .agent features specs tasks runpro_workspace \
    agent/current-task.md agent/failure-log.md agent/memory.md agent/progress.md \
    agent/session-handoff.md agent/task-history.md
  do
    [ ! -e "$legacy" ] || { printf 'legacy Harness path remains: %s\n' "$legacy"; return 1; }
  done
  for project_dir in \
    m3_core m3_guard m3_eval m3_attacks experiments protocols schemas fixtures tests scripts
  do
    [ -d "$project_dir" ] || { printf 'missing project source directory: %s\n' "$project_dir"; return 1; }
  done
}

validate_json() {
  "$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

for path in [
    Path("harness/features/feature_list.json"),
    Path("experiments/registry.json"),
    Path("schemas/attack_case.schema.json"),
    Path("schemas/run_log.schema.json"),
    Path("schemas/tool_call.schema.json"),
]:
    json.loads(path.read_text(encoding="utf-8"))
    print(f"parsed {path}")
PY
}

run_check "Harness files" check_files
run_check "Harness and project source boundary" check_boundary
run_check "JSON contracts" validate_json
run_check "Shell syntax" bash -n harness/scripts/init.sh harness/scripts/verify.sh harness/scripts/test.sh harness/scripts/cleanup.sh
run_check "Python compile" "$PYTHON_BIN" -m compileall -q m3_core m3_guard m3_attacks m3_eval experiments tests
run_check "Unit and integration tests" bash harness/scripts/test.sh
run_check "Experiment registry structure" "$PYTHON_BIN" -m experiments.validate_registry

if [ -f scripts/build_e17_source_index.py ] && [ -f outputs/experiments/e17_source_index_corrected_v2.json ]; then
  run_check "Corrected E17 source index" "$PYTHON_BIN" scripts/build_e17_source_index.py --check
fi

if [ "$REQUIRE_EXPERIMENTS_COMPLETE" = "1" ]; then
  run_check "Experiment registry complete" "$PYTHON_BIN" -m experiments.validate_registry --require-complete
fi

printf '\nVerification failed=%s\n' "$FAILED"
[ "$FAILED" -eq 0 ]
