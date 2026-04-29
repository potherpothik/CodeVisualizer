"""
Python implementations of every CodeVisualizer workflow command.

These replace the bash scripts so the package works on any OS (Windows, macOS,
Linux) without requiring bash, and without cloning the repo into the project.
"""

from __future__ import annotations

import os
import re
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import _git


# ─────────────────────────────────────────────────────────────────────────────
#  ANALYZE  (replaces regenerate_mermaid_output.sh)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_analyze(
    project_path: str,
    out_dir: Optional[str] = None,
    exclude: Optional[list[str]] = None,
    targets_file: Optional[str] = None,
    target: Optional[str] = None,
    force: bool = False,
) -> int:
    """Analyze *project_path* and write all diagram + index artefacts.

    Mirrors the multi-target logic of regenerate_mermaid_output.sh:
      - Reads targets from *targets_file* (or .codevis-targets in the project).
      - Skips targets whose git hash is unchanged (unless *force* is True).
      - Writes outputs to *out_dir*/<sanitized-target>/.

    Returns 0 on success, 1 on error.
    """
    from ._analyzer import ProjectVisualizer

    project_path = os.path.abspath(project_path)
    repo_root = _git.find_repo_root(project_path)
    out_base = os.path.abspath(out_dir) if out_dir else os.path.join(repo_root, "mermaid_output")

    targets = _resolve_targets(project_path, repo_root, targets_file, target)
    if not targets:
        print(
            "No targets found. Create .codevis-targets in your project root, or pass "
            "a path directly: codevis analyze path/to/folder",
            file=sys.stderr,
        )
        return 1

    excludes = _resolve_excludes(project_path, repo_root, exclude)
    os.makedirs(out_base, exist_ok=True)
    any_error = False

    for tgt in targets:
        target_abs = os.path.join(repo_root, tgt) if not os.path.isabs(tgt) else tgt
        if not os.path.isdir(target_abs):
            print(f"  Skipping missing target: {tgt}", file=sys.stderr)
            continue

        safe_name = re.sub(r"[/ ]", "_", tgt)
        if safe_name == ".":
            safe_name = "__root__"
        target_out = os.path.join(out_base, safe_name)
        state_file = os.path.join(out_base, f".inputs.{safe_name}.sha1")

        if not force:
            new_hash = _git.compute_target_hash(repo_root, tgt)
            old_hash = Path(state_file).read_text(encoding="utf-8").strip() if os.path.exists(state_file) else ""
            if new_hash and new_hash == old_hash:
                print(f"  No tracked changes under '{tgt}' — skipping.")
                continue

        print(f"\n{'═' * 60}")
        print(f"  Analyzing: {target_abs}  →  {target_out}")
        print(f"{'═' * 60}\n")

        viz = ProjectVisualizer(target_abs, exclude_prefixes=excludes)
        print("  Scanning & analyzing files...")
        viz.analyze()
        print(f"  Generating diagrams → {target_out}")
        viz.write_all(target_out)
        print(f"\n  Stats: {len(viz.files)} files · {len(viz.classes)} classes · {len(viz.functions)} functions")
        if viz.errors:
            print(f"  ⚠  {len(viz.errors)} parse error(s) — see summary.md")
        if viz.errors:
            any_error = True

        new_hash = _git.compute_target_hash(repo_root, tgt)
        if new_hash:
            Path(state_file).write_text(new_hash, encoding="utf-8")

    print(f"\n  Done. Outputs under: {out_base}/\n")
    print(f"  Tip: paste mermaid_output/<target>/ai_context_primer.md as the first")
    print(f"       message of your next AI chat.\n")
    return 1 if any_error else 0


def _resolve_targets(
    project_path: str,
    repo_root: str,
    targets_file: Optional[str],
    single_target: Optional[str],
) -> list[str]:
    if single_target:
        return [single_target]

    candidates = []
    if targets_file:
        candidates = [targets_file]
    else:
        candidates = [
            os.path.join(project_path, ".codevis-targets"),
            os.path.join(repo_root, ".codevis-targets"),
            os.path.join(repo_root, ".ai-map-targets"),
        ]

    for f in candidates:
        if os.path.isfile(f):
            return _read_lines(f)

    # Fall back to project_path itself as single target
    rel = os.path.relpath(project_path, repo_root)
    return [rel if rel != "." else "."]


def _resolve_excludes(
    project_path: str,
    repo_root: str,
    cli_excludes: Optional[list[str]],
) -> list[str]:
    if cli_excludes:
        return cli_excludes
    candidates = [
        os.path.join(project_path, ".codevis-excludes"),
        os.path.join(repo_root, ".codevis-excludes"),
        os.path.join(repo_root, ".ai-map-excludes"),
    ]
    for f in candidates:
        if os.path.isfile(f):
            return _read_lines(f)
    return []


def _read_lines(path: str) -> list[str]:
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(stripped)
    return lines


# ─────────────────────────────────────────────────────────────────────────────
#  CHANGELOG  (replaces changelog.sh)
# ─────────────────────────────────────────────────────────────────────────────

VALID_TYPES = {"feat", "fix", "refactor", "perf", "chore", "docs", "test"}
ENTRIES_MARKER = "<!-- ENTRIES_START -->"

CHANGELOG_HEADER = """\
# CHANGELOG

This file records every significant change to the project in a format optimised
for both humans and AI agents.

**Column guide:**
- **Type** — `feat` new feature | `fix` bug fix | `refactor` restructure | `perf` speed | `chore` tooling | `docs` docs only | `test` tests only
- **What changed** — one-sentence summary of the modification
- **Why** — the motivation or root cause that drove the change
- **Files touched** — the specific files modified (helps an AI jump straight to the right code)

<!-- ENTRIES_START -->
"""


def cmd_changelog(
    project_path: str,
    change_type: str,
    what: str,
    why: str,
    files: Optional[str] = None,
    impact: Optional[str] = None,
    impact_id: str = "",
) -> int:
    """Prepend a structured entry to CHANGELOG.md in the repo root."""
    project_path = os.path.abspath(project_path)
    repo_root = _git.find_repo_root(project_path)
    changelog_path = os.path.join(repo_root, "CHANGELOG.md")

    if change_type not in VALID_TYPES:
        print(f"Warning: type '{change_type}' is not one of {sorted(VALID_TYPES)}. Continuing.", file=sys.stderr)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    mid = impact_id or _make_impact_id(ts)
    branch = _git.current_branch(repo_root)
    commit = _git.current_commit(repo_root)

    if not files:
        detected = _git.changed_files(repo_root)
        files = " ".join(detected[:20]) if detected else "(none detected)"

    impact_block = ""
    if impact:
        impact_block = f"\n**Impact radius:** {impact}\n"

    entry = (
        f"\n## [{change_type}] {ts} `{mid}`\n"
        f"\n"
        f"| Field   | Value |\n"
        f"|---------|-------|\n"
        f"| Type    | `{change_type}` |\n"
        f"| ID      | `{mid}` |\n"
        f"| Branch  | `{branch}` |\n"
        f"| Commit  | `{commit}` |\n"
        f"| Date    | {ts} |\n"
        f"\n"
        f"**What changed:** {what}\n"
        f"\n"
        f"**Why:** {why}\n"
        f"\n"
        f"**Files touched:** `{files}`\n"
        f"{impact_block}"
        f"\n"
        f"---\n"
    )

    if not os.path.exists(changelog_path):
        Path(changelog_path).write_text(CHANGELOG_HEADER, encoding="utf-8")
        print(f"  Created: {changelog_path}")

    content = Path(changelog_path).read_text(encoding="utf-8")

    if ENTRIES_MARKER in content:
        content = content.replace(ENTRIES_MARKER, ENTRIES_MARKER + entry, 1)
    else:
        content += "\n" + entry

    Path(changelog_path).write_text(content, encoding="utf-8")

    print(f"  Changelog entry appended to: {changelog_path}")
    print(f"  Type  : {change_type}")
    print(f"  What  : {what}")
    print(f"  Why   : {why}")
    print(f"  Files : {files}")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
#  NOTE  (replaces ai_note.sh)
# ─────────────────────────────────────────────────────────────────────────────

def _find_memory_file(project_path: str, repo_root: str) -> str:
    """Locate AI_PROJECT_MEMORY.md — prefer project-local, fallback to repo root."""
    candidates = [
        os.path.join(project_path, "AI_PROJECT_MEMORY.md"),
        os.path.join(repo_root, "AI_PROJECT_MEMORY.md"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # Default: write next to the project
    return os.path.join(project_path, "AI_PROJECT_MEMORY.md")


def _make_impact_id(ts: str) -> str:
    """Short stable ID derived from timestamp, used to cross-link notes to changelog."""
    import hashlib
    return "MEM-" + hashlib.sha1(ts.encode()).hexdigest()[:8].upper()


def cmd_note(project_path: str, note: str, impact_id: str = "") -> int:
    """Append a timestamped note to AI_PROJECT_MEMORY.md."""
    project_path = os.path.abspath(project_path)
    repo_root = _git.find_repo_root(project_path)
    mem_file = _find_memory_file(project_path, repo_root)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    mid = impact_id or _make_impact_id(ts)
    branch = _git.current_branch(repo_root)
    commit = _git.current_commit(repo_root)
    diff = _git.diff_stat(repo_root)
    recent = _git.recent_commits(repo_root)

    entry = (
        f"\n## {ts} `{mid}`\n"
        f"\n"
        f"- **Branch**: `{branch}`\n"
        f"- **HEAD**: `{commit}`\n"
        f"- **Note**: {note}\n"
        f"\n"
        f"### Diff (staged or working tree)\n"
        f"\n"
        f"```\n{diff}\n```\n"
        f"\n"
        f"### Recent commits\n"
        f"\n"
        f"```\n{recent}\n```\n"
    )

    os.makedirs(os.path.dirname(mem_file), exist_ok=True)

    if not os.path.exists(mem_file):
        _bootstrap_memory_file(mem_file)

    with open(mem_file, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"  Memory note appended to: {mem_file}")
    return 0


def _bootstrap_memory_file(path: str):
    """Write the standard AI_PROJECT_MEMORY.md template if the file doesn't exist."""
    template_path = Path(__file__).parent / "templates" / "AI_PROJECT_MEMORY.md"
    if template_path.exists():
        shutil.copy(str(template_path), path)
    else:
        Path(path).write_text(
            "# AI Project Memory\n\n"
            "Curated history for future AI sessions.\n\n"
            "## Recent changes\n\n",
            encoding="utf-8",
        )


# ─────────────────────────────────────────────────────────────────────────────
#  INIT  (new: sets up .codevis-targets and copies .cursorrules template)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_init(project_path: str) -> int:
    """Scaffold CodeVisualizer config files in *project_path*.

    Creates (if absent):
      - .codevis-targets    — list of paths to analyze
      - .codevis-excludes   — list of path prefixes to skip
      - .cursorrules        — Cursor IDE persistent context (from bundled template)
      - AI_PROJECT_MEMORY.md
    """
    project_path = os.path.abspath(project_path)
    repo_root = _git.find_repo_root(project_path)
    templates_dir = Path(__file__).parent / "templates"
    created: list[str] = []
    skipped: list[str] = []

    def _scaffold(dest: str, template_name: str, fallback_content: str):
        if os.path.exists(dest):
            skipped.append(dest)
            return
        tpl = templates_dir / template_name
        if tpl.exists():
            shutil.copy(str(tpl), dest)
        else:
            Path(dest).write_text(fallback_content, encoding="utf-8")
        created.append(dest)

    _scaffold(
        os.path.join(repo_root, ".codevis-targets"),
        ".codevis-targets.example",
        "# One path per line, relative to this file's directory.\n"
        "# Example:\n"
        "#   src/my_app\n"
        "#   .\n",
    )

    _scaffold(
        os.path.join(repo_root, ".codevis-excludes"),
        ".codevis-excludes.example",
        "# Path prefixes to skip (one per line).\n"
        "# Example:\n"
        "#   node_modules\n"
        "#   .venv\n"
        "#   dist\n",
    )

    _scaffold(
        os.path.join(repo_root, ".cursorrules"),
        ".cursorrules.example",
        "# Cursor IDE persistent context — fill in the sections below.\n",
    )

    _scaffold(
        os.path.join(repo_root, "AI_PROJECT_MEMORY.md"),
        "AI_PROJECT_MEMORY.md",
        "# AI Project Memory\n\n## Architecture decisions\n\n## Known issues\n\n## Recent changes\n\n",
    )

    print("\n  CodeVisualizer initialized.\n")
    for f in created:
        print(f"  Created : {os.path.relpath(f, repo_root)}")
    for f in skipped:
        print(f"  Exists  : {os.path.relpath(f, repo_root)} (unchanged)")
    if created:
        print("\n  Next steps:")
        print("    1. Edit .codevis-targets — add the paths you want to analyze.")
        print("    2. Edit .cursorrules    — fill in project identity and constraints.")
        print("    3. Run: codevis sync --what 'Initial setup' --why 'First run'\n")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
#  SYNC  (replaces sync.sh — runs analyze + changelog + note in one call)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_sync(
    project_path: str,
    change_type: Optional[str] = None,
    what: Optional[str] = None,
    why: Optional[str] = None,
    files: Optional[str] = None,
    note: Optional[str] = None,
    impact: Optional[str] = None,
    target: Optional[str] = None,
    skip_regen: bool = False,
    force: bool = False,
) -> int:
    """Run the full AI context pipeline in one call.

    Order:
      1. analyze  — regenerate diagrams + ai_context_primer.md
      2. changelog — structured CHANGELOG.md entry  (if --type/--what/--why given)
      3. note      — AI_PROJECT_MEMORY.md entry      (auto-composed if not given)

    A shared impact ID (MEM-xxxxxxxx) is stamped on both the changelog entry
    and the memory note so they can be cross-referenced later.
    """
    from datetime import datetime, timezone
    project_path = os.path.abspath(project_path)
    rc = 0

    # Pre-compute a shared ID so changelog and memory note are cross-linked.
    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    shared_id = _make_impact_id(ts_now)

    # ── Step 1 ────────────────────────────────────────────────────────────────
    _banner("Step 1/3 — Regenerate diagrams + ai_context_primer.md")
    if not skip_regen:
        rc |= cmd_analyze(project_path, target=target, force=force)
    else:
        print("  Skipped (--skip-regen).")

    # ── Step 2 ────────────────────────────────────────────────────────────────
    _banner("Step 2/3 — Structured changelog entry  (CHANGELOG.md)")
    if change_type and what and why:
        rc |= cmd_changelog(
            project_path, change_type, what, why, files,
            impact=impact, impact_id=shared_id,
        )
    else:
        print("  Skipped — pass --type, --what, and --why to log a change.")

    # ── Step 3 ────────────────────────────────────────────────────────────────
    _banner("Step 3/3 — AI memory note  (AI_PROJECT_MEMORY.md)")
    memory_note = note
    if not memory_note and what:
        memory_note = f"{change_type or 'chore'}: {what} — {why or ''}"
        if files:
            memory_note += f" — files: {files}"
    if memory_note:
        rc |= cmd_note(project_path, memory_note, impact_id=shared_id)
    else:
        print("  Skipped — pass --note or --what to add a memory entry.")

    _banner("Done.  AI context is fully up to date.")
    print("  Tip: paste mermaid_output/<target>/ai_context_primer.md as the")
    print("       first message of your next AI chat.\n")
    return rc


def _banner(text: str):
    bar = "═" * 58
    print(f"\n╔{bar}╗")
    print(f"║  {text:<56}║")
    print(f"╚{bar}╝\n")
