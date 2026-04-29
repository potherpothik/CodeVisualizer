#!/usr/bin/env bash
set -euo pipefail

# Append a short, durable “AI memory” note into CodeVisualizer/Readme/AI_PROJECT_MEMORY.md
# (falls back to repo Readme/AI_PROJECT_MEMORY.md if the tool Readme file is missing).
#
# Usage (from repo root):
#   ./CodeVisualizer/scripts/ai_note.sh "Fixed X; why; where; repro/logs..."

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(git -C "$TOOL_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$TOOL_DIR")"

MEM_FILE="$TOOL_DIR/Readme/AI_PROJECT_MEMORY.md"
if [[ ! -f "$MEM_FILE" ]]; then
  MEM_FILE="$ROOT_DIR/Readme/AI_PROJECT_MEMORY.md"
fi
NOTE="${1:-}"

if [[ -z "$NOTE" ]]; then
  echo "Usage: $0 \"your note...\"" >&2
  exit 2
fi

mkdir -p "$(dirname "$MEM_FILE")"

ts="$(date -Is)"
branch="$(cd "$ROOT_DIR" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
head="$(cd "$ROOT_DIR" && git rev-parse HEAD 2>/dev/null || echo "unknown")"

{
  echo ""
  echo "## ${ts}"
  echo ""
  echo "- **Branch**: \`${branch}\`"
  echo "- **HEAD**: \`${head}\`"
  echo "- **Note**: ${NOTE}"
  echo ""
  echo "### Diff (working tree)"
  echo ""
  echo '```'
  (cd "$ROOT_DIR" && git diff --stat || true)
  echo '```'
  echo ""
  echo "### Recent commits"
  echo ""
  echo '```'
  (cd "$ROOT_DIR" && git log -5 --oneline || true)
  echo '```'
} >> "$MEM_FILE"

echo "Appended memory note to: $MEM_FILE"

