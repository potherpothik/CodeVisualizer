"""
Pure-Python git helpers used by the command implementations.
All functions are best-effort: they return sensible defaults when git is
unavailable or the directory is not a git repository.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


def _run(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout, or '' on failure."""
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def find_repo_root(start: str) -> str:
    """Return the git repository root containing *start*, or *start* itself."""
    root = _run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    return root if root else start


def current_branch(repo_root: str) -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root) or "unknown"


def current_commit(repo_root: str) -> str:
    return _run(["git", "rev-parse", "HEAD"], cwd=repo_root) or "unknown"


def diff_stat(repo_root: str) -> str:
    """Return a diff --stat summary.

    Prefers staged changes (--cached) when any exist; falls back to the full
    working-tree diff so that the snapshot is always non-empty if there is
    anything to show.
    """
    staged = _run(["git", "diff", "--cached", "--stat"], cwd=repo_root)
    if staged:
        return staged
    return _run(["git", "diff", "--stat"], cwd=repo_root) or "(no diff)"


def recent_commits(repo_root: str, n: int = 5) -> str:
    return _run(["git", "log", f"-{n}", "--oneline"], cwd=repo_root) or "(no commits)"


def changed_files(repo_root: str) -> list[str]:
    """Return files changed vs HEAD (staged + unstaged), with rename detection.

    Order of preference:
    1. Staged files (--cached), which are the most intentional.
    2. Working-tree changes vs HEAD.
    Rename detection (-M) is enabled so moved files appear as the new name.
    """
    staged = _run(["git", "diff", "--cached", "--name-only", "-M"], cwd=repo_root)
    if staged:
        return [f for f in staged.splitlines() if f]
    out = _run(["git", "diff", "--name-only", "-M", "HEAD"], cwd=repo_root)
    return [f for f in out.splitlines() if f] if out else []


def ls_files(repo_root: str, target: str) -> list[str]:
    """Return git-tracked files under *target* (relative to repo root)."""
    out = _run(["git", "ls-files", "--", target], cwd=repo_root)
    return [f for f in out.splitlines() if f] if out else []


def compute_target_hash(repo_root: str, target: str) -> str:
    """SHA1 hash of all git-tracked files under *target*, for cache invalidation."""
    import hashlib
    files = ls_files(repo_root, target)
    if not files:
        return ""
    h = hashlib.sha1()
    for rel in sorted(files):
        abs_path = os.path.join(repo_root, rel)
        try:
            h.update(Path(abs_path).read_bytes())
        except OSError:
            pass
    return h.hexdigest()


def is_git_repo(path: str) -> bool:
    return bool(_run(["git", "rev-parse", "--git-dir"], cwd=path))
