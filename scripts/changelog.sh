#!/usr/bin/env bash
set -euo pipefail

# Record a structured entry in CHANGELOG.md (repo root).
#
# Usage (from repo root):
#   ./CodeVisualizer/scripts/changelog.sh \
#       --type fix \
#       --what "Corrected price rounding in invoice total" \
#       --why  "Float precision caused cent-level discrepancies in PDF exports" \
#       --files "src/invoice.py src/utils/currency.py"
#
# --type   : feat | fix | refactor | perf | chore | docs | test  (default: chore)
# --what   : one-sentence description of what changed (required)
# --why    : one-sentence reason / motivation (required)
# --files  : space-separated list of changed files (optional; auto-detected from git if omitted)
#
# The entry is prepended to CHANGELOG.md so newest changes are always at the top.
# Each entry is machine-readable (YAML front-matter style) AND human-readable prose,
# so AI agents can parse it reliably without ambiguity.

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# When the tool lives inside a host repo (the normal case), ROOT_DIR is that
# host repo's top-level.  When this repo IS the tool repo (standalone dev),
# git rev-parse returns TOOL_DIR itself — so fall back to TOOL_DIR in that case.
ROOT_DIR="$(git -C "$TOOL_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$TOOL_DIR")"
CHANGELOG="$ROOT_DIR/CHANGELOG.md"

# ── Parse arguments ────────────────────────────────────────────────────────────
TYPE="chore"
WHAT=""
WHY=""
FILES_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)   TYPE="${2:-chore}";  shift 2 ;;
    --what)   WHAT="${2:-}";       shift 2 ;;
    --why)    WHY="${2:-}";        shift 2 ;;
    --files)  FILES_ARG="${2:-}";  shift 2 ;;
    -h|--help)
      sed -n '3,20p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Run with --help for usage." >&2
      exit 2
      ;;
  esac
done

if [[ -z "$WHAT" || -z "$WHY" ]]; then
  echo "Error: --what and --why are required." >&2
  echo "" >&2
  echo "Example:" >&2
  echo "  $0 --type fix --what \"Fixed X\" --why \"Because Y\" --files \"a.py b.py\"" >&2
  exit 2
fi

VALID_TYPES="feat fix refactor perf chore docs test"
if ! echo "$VALID_TYPES" | grep -qw "$TYPE"; then
  echo "Warning: --type '$TYPE' is not one of: $VALID_TYPES" >&2
  echo "Continuing anyway." >&2
fi

# ── Collect metadata ───────────────────────────────────────────────────────────
ts="$(date -Is 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S%z')"
branch="$(cd "$ROOT_DIR" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
commit="$(cd "$ROOT_DIR" && git rev-parse HEAD 2>/dev/null || echo "unknown")"

# Auto-detect changed files from staged + unstaged if not provided
if [[ -z "$FILES_ARG" ]]; then
  FILES_ARG="$(cd "$ROOT_DIR" && git diff --name-only HEAD 2>/dev/null | head -20 | tr '\n' ' ' || true)"
  FILES_ARG="${FILES_ARG%% }"  # trim trailing space
  if [[ -z "$FILES_ARG" ]]; then
    FILES_ARG="(none detected)"
  fi
fi

# ── Build the entry ────────────────────────────────────────────────────────────
read -r -d '' ENTRY <<ENTRY_EOF || true
## [${TYPE}] ${ts}

| Field   | Value |
|---------|-------|
| Type    | \`${TYPE}\` |
| Branch  | \`${branch}\` |
| Commit  | \`${commit}\` |
| Date    | ${ts} |

**What changed:** ${WHAT}

**Why:** ${WHY}

**Files touched:** \`${FILES_ARG}\`

---

ENTRY_EOF

# ── Bootstrap CHANGELOG.md if absent ─────────────────────────────────────────
if [[ ! -f "$CHANGELOG" ]]; then
  cat > "$CHANGELOG" <<'HEADER'
# CHANGELOG

This file records every significant change to the project in a format optimised
for both humans and AI agents.

**Column guide:**
- **Type** — `feat` new feature | `fix` bug fix | `refactor` restructure | `perf` speed | `chore` tooling | `docs` docs only | `test` tests only
- **What changed** — one-sentence summary of the modification
- **Why** — the motivation or root cause that drove the change
- **Files touched** — the specific files modified (helps an AI jump straight to the right code)

<!-- ENTRIES_START -->
HEADER
  echo "Created: $CHANGELOG"
fi

# ── Prepend entry after the header marker ─────────────────────────────────────
MARKER="<!-- ENTRIES_START -->"
if grep -q "$MARKER" "$CHANGELOG"; then
  # Insert new entry immediately after the marker line
  TMP="$(mktemp)"
  awk -v entry="$ENTRY" -v marker="$MARKER" '
    { print }
    $0 == marker { printf "%s", entry }
  ' "$CHANGELOG" > "$TMP"
  mv "$TMP" "$CHANGELOG"
else
  # Fallback: append to end
  printf '\n%s' "$ENTRY" >> "$CHANGELOG"
fi

echo "Changelog entry appended to: $CHANGELOG"
echo ""
echo "  Type   : $TYPE"
echo "  What   : $WHAT"
echo "  Why    : $WHY"
echo "  Files  : $FILES_ARG"
