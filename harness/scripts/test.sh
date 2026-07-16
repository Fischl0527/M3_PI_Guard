#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"

if [ -z "$PYTHON_BIN" ]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v where.exe >/dev/null 2>&1 && command -v wslpath >/dev/null 2>&1; then
    windows_python="$(where.exe python 2>/dev/null | sed -n '1{s/\r$//;p;}')"
    [ -n "$windows_python" ] || { printf '%s\n' "FAIL: unable to resolve Python" >&2; exit 1; }
    PYTHON_BIN="$(wslpath -u "$windows_python")"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    printf '%s\n' "FAIL: unable to resolve Python" >&2
    exit 1
  fi
fi

if [ ! -d tests ]; then
  printf '%s\n' "FAIL: local tests directory is missing"
  exit 1
fi

"$PYTHON_BIN" -m unittest discover -s tests -t . -v
