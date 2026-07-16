#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

log() {
  printf '%s\n' "$*"
}

ensure_dir() {
  if [ ! -d "$1" ]; then
    mkdir -p "$1"
    log "created directory: $1"
  fi
}

ensure_file() {
  if [ ! -f "$1" ]; then
    printf '%s\n' "$2" > "$1"
    log "created file: $1"
  fi
}

log "AI Agent Harness initializer"
log "root: $ROOT_DIR"

log ""
log "Checking environment..."

if command -v git >/dev/null 2>&1; then
  log "git: $(git --version)"
else
  log "git: not found"
fi

if command -v node >/dev/null 2>&1; then
  log "node: $(node --version)"
else
  log "node: not found"
fi

if command -v python >/dev/null 2>&1; then
  log "python: $(python --version 2>&1)"
elif command -v python3 >/dev/null 2>&1; then
  log "python3: $(python3 --version 2>&1)"
else
  log "python: not found"
fi

log ""
log "Checking harness directories..."

ensure_dir "harness/docs"
ensure_dir "harness/state"
ensure_dir "harness/specs"
ensure_dir "harness/features"
ensure_dir "harness/tasks"
ensure_dir "harness/scripts"
ensure_dir "harness/config"
ensure_dir "harness/tmp"

ensure_file "harness/state/current-task.md" "# Current Task

## Task ID

None.

## Goal

No active task.
"

ensure_file "harness/state/progress.md" "# Progress

## Current Status

Initialized.

## Completed

-

## In Progress

-

## Blocked

-

## Next Actions

-

## Verification Status

Tests:

Lint:

Build:
"

log ""
log "Project structure:"
if command -v find >/dev/null 2>&1; then
  find . -maxdepth 3 \
    -not -path './.git/*' \
    -not -path './node_modules/*' \
    -not -path './harness/tmp/*' \
    -print | sort
else
  ls -la
fi

log ""
log "Initialization complete."
log "Next: read AGENTS.md, update harness/specs, then run bash harness/scripts/verify.sh"
