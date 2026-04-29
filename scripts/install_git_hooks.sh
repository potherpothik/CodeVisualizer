#!/usr/bin/env bash
set -euo pipefail

# Installs CodeVisualizer git hooks into .git/hooks (no git config changes).
#
# Usage (from repo root):
#   ./CodeVisualizer/scripts/install_git_hooks.sh

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(git -C "$TOOL_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$TOOL_DIR")"
SRC_DIR="$TOOL_DIR/git-hooks"
DST_DIR="$ROOT_DIR/.git/hooks"

if [[ ! -d "$ROOT_DIR/.git" ]]; then
  echo "Not a git repo: $ROOT_DIR" >&2
  exit 2
fi

mkdir -p "$DST_DIR"

for hook in pre-commit; do
  if [[ -f "$SRC_DIR/$hook" ]]; then
    install -m 0755 "$SRC_DIR/$hook" "$DST_DIR/$hook"
    echo "Installed: .git/hooks/$hook"
  fi
done

echo "Done."

