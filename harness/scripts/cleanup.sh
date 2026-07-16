#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

safe_remove_dir() {
  target="$1"
  case "$target" in
    harness/tmp|./harness/tmp|coverage|./coverage|.pytest_cache|./.pytest_cache)
      if [ -d "$target" ]; then
        rm -rf "$target"
        printf 'removed: %s\n' "$target"
      fi
      ;;
    *)
      printf 'refusing to remove unsafe path: %s\n' "$target"
      return 1
      ;;
  esac
}

printf '%s\n' "Safe cleanup started."
safe_remove_dir "harness/tmp"
safe_remove_dir "coverage"
safe_remove_dir ".pytest_cache"
mkdir -p "harness/tmp"
printf '%s\n' "Safe cleanup complete."
