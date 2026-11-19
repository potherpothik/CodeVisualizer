#!/usr/bin/env bash
# Shortcut: regenerate Mermaid + JSON reports for every path in CodeVisualizer/.ai-map-targets
# Run from anywhere; resolves host repo root via git.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(git -C "$TOOL_DIR/.." rev-parse --show-toplevel 2>/dev/null || (cd "$TOOL_DIR/.." && pwd))"

cd "$ROOT_DIR"
# Pass-through e.g. --force: ./regenerate_maps_quick.sh --force
exec "$TOOL_DIR/scripts/regenerate_mermaid_output.sh" "$@" --targets-file "$TOOL_DIR/.ai-map-targets"
