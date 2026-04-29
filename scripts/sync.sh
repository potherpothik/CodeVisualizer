#!/usr/bin/env bash
set -euo pipefail

# One-command AI context sync.
#
# Runs the full pipeline in the right order:
#   1. Regenerate all diagrams + ai_context_primer.md
#   2. Append a structured entry to CHANGELOG.md
#   3. Append a free-form note to AI_PROJECT_MEMORY.md
#
# Usage (from repo root):
#
#   Minimal — just refresh diagrams, no log entries:
#     ./CodeVisualizer/scripts/sync.sh
#
#   With a changelog entry:
#     ./CodeVisualizer/scripts/sync.sh \
#         --type fix \
#         --what "Fixed price rounding in invoice total" \
#         --why  "Per-line rounding accumulated cent errors"
#
#   With changelog + memory note + specific files listed:
#     ./CodeVisualizer/scripts/sync.sh \
#         --type fix \
#         --what "Fixed price rounding in invoice total" \
#         --why  "Per-line rounding accumulated cent errors" \
#         --files "src/invoice.py src/utils/currency.py" \
#         --note  "Also updated test_invoice.py; do not revert rounding order"
#
#   Analyze a single target instead of all targets:
#     ./CodeVisualizer/scripts/sync.sh --target "packages/core" --type chore --what "..." --why "..."
#
# Options:
#   --type   feat|fix|refactor|perf|chore|docs|test  (default: chore)
#   --what   What changed — required when --type is supplied
#   --why    Why it changed — required when --type is supplied
#   --files  Space-separated file list (optional; auto-detected from git if omitted)
#   --note   Extra free-form note appended to AI_PROJECT_MEMORY.md (optional)
#   --target Single target path to analyze (optional; otherwise uses .ai-map-targets)
#   --skip-regen  Skip diagram regeneration (only write log entries)

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(git -C "$TOOL_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$TOOL_DIR")"

# ── Parse arguments ────────────────────────────────────────────────────────────
TYPE=""
WHAT=""
WHY=""
FILES_ARG=""
NOTE=""
TARGET=""
SKIP_REGEN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)        TYPE="${2:-}";       shift 2 ;;
    --what)        WHAT="${2:-}";       shift 2 ;;
    --why)         WHY="${2:-}";        shift 2 ;;
    --files)       FILES_ARG="${2:-}";  shift 2 ;;
    --note)        NOTE="${2:-}";       shift 2 ;;
    --target)      TARGET="${2:-}";     shift 2 ;;
    --skip-regen)  SKIP_REGEN="true";  shift 1 ;;
    -h|--help)
      sed -n '3,40p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Run with --help for usage." >&2
      exit 2
      ;;
  esac
done

# Validate: if any of --type/--what/--why is given, all three are required
if [[ -n "$TYPE" || -n "$WHAT" || -n "$WHY" ]]; then
  if [[ -z "$TYPE" || -z "$WHAT" || -z "$WHY" ]]; then
    echo "Error: --type, --what, and --why must all be provided together." >&2
    echo "Run with --help for usage." >&2
    exit 2
  fi
fi

# ── Step 1: Regenerate diagrams + ai_context_primer.md ────────────────────────
if [[ "$SKIP_REGEN" != "true" ]]; then
  echo ""
  echo "╔══════════════════════════════════════════════════════════╗"
  echo "║  Step 1/3 — Regenerate diagrams + ai_context_primer.md  ║"
  echo "╚══════════════════════════════════════════════════════════╝"
  echo ""
  if [[ -n "$TARGET" ]]; then
    bash "$TOOL_DIR/scripts/regenerate_mermaid_output.sh" "$TARGET"
  else
    bash "$TOOL_DIR/scripts/regenerate_mermaid_output.sh"
  fi
else
  echo ""
  echo "[ Step 1/3 ] Skipped diagram regeneration (--skip-regen)."
fi

# ── Step 2: Structured changelog entry ────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Step 2/3 — Structured changelog entry (CHANGELOG.md)   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
if [[ -n "$TYPE" ]]; then
  changelog_args=(--type "$TYPE" --what "$WHAT" --why "$WHY")
  if [[ -n "$FILES_ARG" ]]; then
    changelog_args+=(--files "$FILES_ARG")
  fi
  bash "$TOOL_DIR/scripts/changelog.sh" "${changelog_args[@]}"
else
  echo "  Skipped — no --type/--what/--why provided."
  echo "  (Re-run with those flags to log a change entry.)"
fi

# ── Step 3: Free-form AI memory note ──────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Step 3/3 — AI memory note (AI_PROJECT_MEMORY.md)       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
if [[ -n "$NOTE" ]]; then
  bash "$TOOL_DIR/scripts/ai_note.sh" "$NOTE"
elif [[ -n "$WHAT" ]]; then
  # Auto-compose a memory note from the changelog fields if no --note was given
  auto_note="${TYPE}: ${WHAT} — ${WHY}"
  if [[ -n "$FILES_ARG" ]]; then
    auto_note="${auto_note} — files: ${FILES_ARG}"
  fi
  bash "$TOOL_DIR/scripts/ai_note.sh" "$auto_note"
else
  echo "  Skipped — no --note or --what provided."
  echo "  (Re-run with --note \"...\" to add a memory entry.)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Done.  AI context is fully up to date.                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Next: paste mermaid_output/<target>/ai_context_primer.md"
echo "        as the first message of your next AI chat."
echo ""
