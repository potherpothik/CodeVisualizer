#!/usr/bin/env bash
set -euo pipefail

# Regenerate Mermaid + index artifacts for AI navigation/debugging.
#
# Usage (from repo root):
#   ./CodeVisualizer/scripts/regenerate_mermaid_output.sh "packages/core"
#   ./CodeVisualizer/scripts/regenerate_mermaid_output.sh --targets-file "CodeVisualizer/.ai-map-targets"
#
# Tip: scanning the whole repo root ("." in .ai-map-targets) can be slow; use
# .ai-map-excludes for vendor trees, virtualenvs, and build output.

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(git -C "$TOOL_DIR/.." rev-parse --show-toplevel 2>/dev/null || (cd "$TOOL_DIR/.." && pwd))"

OUT_DIR="$ROOT_DIR/mermaid_output"

resolve_default_targets_file() {
  # Prefer tool-local files over repo root (legacy).
  local candidates=(
    "$TOOL_DIR/Readme/.ai-map-targets"
    "$TOOL_DIR/.ai-map-targets"
    "$ROOT_DIR/.ai-map-targets"
  )
  for f in "${candidates[@]}"; do
    if [[ -f "$f" ]]; then
      printf '%s' "$f"
      return 0
    fi
  done
  return 1
}

TARGETS_FILE="$(resolve_default_targets_file || true)"

if [[ "${1:-}" == "--targets-file" ]]; then
  tf="${2:-}"
  if [[ -z "$tf" ]]; then
    echo "Usage: $0 --targets-file <path>" >&2
    exit 2
  fi
  if [[ "$tf" = /* ]]; then
    TARGETS_FILE="$tf"
  else
    TARGETS_FILE="$ROOT_DIR/${tf}"
  fi
  shift 2
fi

TARGET_REL="${1:-}"

if [[ -z "$TARGET_REL" && ! -f "${TARGETS_FILE:-}" ]]; then
  echo "No target provided and no targets file found." >&2
  echo "Create one of (paths relative to repo root unless absolute):" >&2
  echo "  CodeVisualizer/Readme/.ai-map-targets" >&2
  echo "  CodeVisualizer/.ai-map-targets" >&2
  echo "  .ai-map-targets (legacy, repo root)" >&2
  echo "Or run: $0 \"Facade V3\"" >&2
  exit 2
fi

mkdir -p "$OUT_DIR"

resolve_excludes_file() {
  local candidates=(
    "$TOOL_DIR/Readme/.ai-map-excludes"
    "$TOOL_DIR/.ai-map-excludes"
    "$ROOT_DIR/.ai-map-excludes"
  )
  for f in "${candidates[@]}"; do
    if [[ -f "$f" ]]; then
      printf '%s' "$f"
      return 0
    fi
  done
  return 1
}

EXCLUDE_ARGS=()
EXCLUDES_FILE="$(resolve_excludes_file || true)"
if [[ -n "${EXCLUDES_FILE}" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "${line// }" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    EXCLUDE_ARGS+=(--exclude "$line")
  done < "$EXCLUDES_FILE"
fi

read_targets() {
  if [[ -n "$TARGET_REL" ]]; then
    printf '%s\n' "$TARGET_REL"
    return 0
  fi
  # shellcheck disable=SC2002
  cat "${TARGETS_FILE}" | while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    printf '%s\n' "$line"
  done
}

compute_inputs_hash_for_target() {
  local target_rel="$1"
  (cd "$ROOT_DIR" && \
    git ls-files -z -- "$target_rel" | \
      xargs -0 sha1sum | \
      sha1sum | \
      awk '{print $1}'
  )
}

while IFS= read -r target; do
  target_dir="$(cd "$ROOT_DIR/$target" 2>/dev/null && pwd || true)"
  if [[ -z "${target_dir}" || ! -d "${target_dir}" ]]; then
    echo "Skipping missing target: $target" >&2
    continue
  fi

  # Separate state per target to avoid collisions.
  safe_name="$(printf '%s' "$target" | tr '/ ' '__')"
  [[ "$safe_name" == "." ]] && safe_name="__root__"
  state_file="$OUT_DIR/.inputs.${safe_name}.sha1"
  target_out="$OUT_DIR/${safe_name}"

  new_hash="$(compute_inputs_hash_for_target "$target" || true)"
  old_hash=""
  if [[ -f "$state_file" ]]; then
    old_hash="$(cat "$state_file" 2>/dev/null || true)"
  fi

  if [[ -n "$new_hash" && "$new_hash" == "$old_hash" ]]; then
    echo "No tracked file changes under '$target'. Skipping."
    continue
  fi

  echo "Regenerating mermaid_output from target: $target_dir → $target_out"
  mkdir -p "$target_out"
  python3 "$TOOL_DIR/codebase_visualizer.py" "$target_dir" --out "$target_out" "${EXCLUDE_ARGS[@]}"

  if [[ -n "$new_hash" ]]; then
    printf '%s' "$new_hash" > "$state_file"
  fi
done < <(read_targets)

echo "Done. Outputs under: $OUT_DIR/<target>/"

