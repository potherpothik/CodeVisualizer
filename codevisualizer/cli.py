"""
codevis — command-line interface

Subcommands:
  init        Scaffold config files in a project (run once per project)
  analyze     Regenerate all diagrams + ai_context_primer.md
  changelog   Append a structured entry to CHANGELOG.md
  note        Append a free-form note to AI_PROJECT_MEMORY.md
  sync        Run analyze + changelog + note in one command (recommended)
"""

from __future__ import annotations

import argparse
import sys

from ._commands import (
    cmd_analyze,
    cmd_changelog,
    cmd_init,
    cmd_note,
    cmd_sync,
)


def _add_path_arg(p: argparse.ArgumentParser):
    p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        metavar="PATH",
        help="Project root to operate on (default: current directory).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codevis",
        description="CodeVisualizer — AI context toolkit for Python projects.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First time setup in a project:
  codevis init

  # After code changes — one command does everything:
  codevis sync --type fix --what "Fixed price rounding" --why "Cent errors in invoices"

  # Regenerate diagrams only:
  codevis analyze

  # Log a change without regenerating:
  codevis changelog --type feat --what "Added PDF export" --why "User request"

  # Add a quick memory note:
  codevis note "Reverted lazy-load change — caused N+1 on orders endpoint"
""",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── init ──────────────────────────────────────────────────────────────────
    p_init = sub.add_parser(
        "init",
        help="Scaffold .codevis-targets, .cursorrules, AI_PROJECT_MEMORY.md (run once).",
        description=(
            "Create CodeVisualizer config files in the project root.\n"
            "Safe to re-run — existing files are never overwritten."
        ),
    )
    _add_path_arg(p_init)

    # ── analyze ───────────────────────────────────────────────────────────────
    p_analyze = sub.add_parser(
        "analyze",
        help="Regenerate all diagrams + ai_context_primer.md.",
        description="Analyze Python source and write Mermaid diagrams, JSON index, and ai_context_primer.md.",
    )
    _add_path_arg(p_analyze)
    p_analyze.add_argument("--out", "-o", metavar="DIR", help="Output directory (default: <repo-root>/mermaid_output).")
    p_analyze.add_argument("--exclude", "-x", action="append", metavar="PREFIX", help="Skip files under this prefix. Repeatable.")
    p_analyze.add_argument("--targets-file", metavar="FILE", help="Path to a targets file (overrides .codevis-targets).")
    p_analyze.add_argument("--target", "-t", metavar="PATH", help="Analyze a single target path instead of reading targets file.")
    p_analyze.add_argument("--force", "-f", action="store_true", help="Re-analyze even if git hash is unchanged.")

    # ── changelog ─────────────────────────────────────────────────────────────
    p_cl = sub.add_parser(
        "changelog",
        help="Append a structured entry to CHANGELOG.md.",
        description="Write a type/what/why entry to CHANGELOG.md at the repo root.",
    )
    _add_path_arg(p_cl)
    p_cl.add_argument("--type", dest="change_type", default="chore", metavar="TYPE",
                      help="feat|fix|refactor|perf|chore|docs|test (default: chore).")
    p_cl.add_argument("--what", required=True, metavar="TEXT", help="One sentence: what changed.")
    p_cl.add_argument("--why",  required=True, metavar="TEXT", help="One sentence: why it changed.")
    p_cl.add_argument("--files", metavar="FILES", help="Space-separated file list (auto-detected from git if omitted).")

    # ── note ──────────────────────────────────────────────────────────────────
    p_note = sub.add_parser(
        "note",
        help="Append a free-form note to AI_PROJECT_MEMORY.md.",
        description="Stamp a note with branch, commit, diff stat, and recent commits.",
    )
    _add_path_arg(p_note)
    p_note.add_argument("text", metavar="NOTE", help="The note text to append.")

    # ── sync ──────────────────────────────────────────────────────────────────
    p_sync = sub.add_parser(
        "sync",
        help="Run analyze + changelog + note in one command (recommended daily driver).",
        description=(
            "Full AI context pipeline:\n"
            "  1. Regenerate diagrams + ai_context_primer.md\n"
            "  2. Append structured entry to CHANGELOG.md\n"
            "  3. Append note to AI_PROJECT_MEMORY.md\n\n"
            "All log flags are optional — bare `codevis sync` just refreshes diagrams."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_path_arg(p_sync)
    p_sync.add_argument("--type", dest="change_type", default=None, metavar="TYPE",
                        help="feat|fix|refactor|perf|chore|docs|test.")
    p_sync.add_argument("--what", metavar="TEXT", help="One sentence: what changed.")
    p_sync.add_argument("--why",  metavar="TEXT", help="One sentence: why it changed.")
    p_sync.add_argument("--files", metavar="FILES", help="Files touched (auto-detected if omitted).")
    p_sync.add_argument("--note", metavar="TEXT", help="Extra memory note (auto-composed from --what/--why if omitted).")
    p_sync.add_argument("--target", "-t", metavar="PATH", help="Analyze a single target path.")
    p_sync.add_argument("--skip-regen", action="store_true", help="Skip diagram regeneration.")
    p_sync.add_argument("--force", "-f", action="store_true", help="Re-analyze even if git hash is unchanged.")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        sys.exit(cmd_init(args.project_path))

    elif args.command == "analyze":
        sys.exit(cmd_analyze(
            args.project_path,
            out_dir=args.out,
            exclude=args.exclude,
            targets_file=args.targets_file,
            target=args.target,
            force=args.force,
        ))

    elif args.command == "changelog":
        sys.exit(cmd_changelog(
            args.project_path,
            change_type=args.change_type,
            what=args.what,
            why=args.why,
            files=args.files,
        ))

    elif args.command == "note":
        sys.exit(cmd_note(args.project_path, args.text))

    elif args.command == "sync":
        sys.exit(cmd_sync(
            args.project_path,
            change_type=args.change_type,
            what=args.what,
            why=args.why,
            files=args.files,
            note=args.note,
            target=args.target,
            skip_regen=args.skip_regen,
            force=args.force,
        ))


if __name__ == "__main__":
    main()
