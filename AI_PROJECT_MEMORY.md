# AI Project Memory

This file is a **curated, durable history** meant for future AI sessions.

It is intentionally short and practical:
- what changed
- why it changed
- where to look
- how to reproduce / logs if relevant

Add entries with:

```bash
codevis note "your note..."
```

For structured change tracking (recommended), also use:

```bash
codevis sync \
    --type fix \
    --what "One-sentence summary of what changed" \
    --why  "One-sentence reason / motivation" \
    --files "path/to/file1.py path/to/file2.py"
```

---

## Decision Registry

> Stable architectural decisions with unique IDs.  An AI agent **must not**
> suggest reversing these without referencing the entry and its consequences.
>
> Status values: `active` | `reverted` | `superseded`

| ID | Decision | Status | Chosen | Rejected | Consequences | Enforced in |
|----|----------|--------|--------|----------|--------------|-------------|
| DEC-001 | Single installable package `codevisualizer` | active | pip-installable package | monolithic script | Users install once; no copy-paste needed | `codevisualizer/`, `pyproject.toml` |
| DEC-002 | stdlib-only runtime dependencies | active | stdlib only | third-party libs | Runs on any Python 3.9+ without install friction | `pyproject.toml` `dependencies=[]` |
| DEC-003 | Mermaid output never committed to git | active | `.gitignore` exclusion | versioned output | Output is regenerated on demand; no stale artefacts | `.gitignore` |
| DEC-004 | AST-resolved callgraph edges (not name-heuristic) | active | symbol table per file | short-name match-all | Unresolved calls listed separately; fewer hallucinated edges | `_analyzer.py` |

---

## Known pitfalls — do not suggest

- **Do not remove the unresolved-call separation** — `FunctionInfo.unresolved_calls` is intentionally separate from `calls`. Merging them back breaks the callgraph accuracy guarantee.
- **Do not add non-stdlib runtime dependencies** — the package must stay zero-dependency (DEC-002). Use stdlib equivalents only.
- **Do not commit `mermaid_output/`** — it is gitignored by design (DEC-003).
- **Do not call `cmd_note` without an `impact_id`** when called from `cmd_sync` — the shared ID is what links changelog entries to memory notes.

---

## Architecture decisions

> Keep this section up to date whenever a significant architectural choice is made.
> An AI agent reading this will understand *why* the code is shaped the way it is,
> preventing it from suggesting changes that violate intentional constraints.

<!-- Example entries:

- **Monetary values stored as integers (cents)** — avoids float precision bugs in
  tax and invoice calculations.  All display formatting happens at the boundary
  (PDF renderer, API response serialiser).

- **No ORM lazy loading** — all queries use explicit `joinedload()` / `selectinload()`.
  Lazy loading caused N+1 issues in high-traffic endpoints.

- **Background jobs through Celery only** — never call task functions synchronously
  from request handlers.  Keeps API response times under 200 ms.

-->

## Known issues / gotchas

> Document non-obvious bugs, surprising edge-cases, or partial fixes so the AI
> does not repeatedly suggest the same wrong solutions.
> Always include a **How to reproduce** note — even one line.

<!-- Example entries:

- **Invoice rounding** (`src/invoice.py:calculate_total`) — rounding is done
  *after* summing all line items, not per-line.  Per-line rounding accumulates
  errors.  Do not change this without updating the test suite in `tests/test_invoice.py`.
  - *Reproduce*: `python -c "from src.invoice import calc; print(calc([0.1]*3))"` → 0.30, not 0.29.

- **Legacy payment adapter** (`legacy/payment_v1.py`) — vendor code, do not modify.
  The interface is wrapped in `src/payment_adapter.py`.
  - *Reproduce*: N/A (static vendor file; changes break signature verification).

-->

## Recent changes

> Entries added by `ai_note.sh` appear below in reverse-chronological order.
> For a full structured log see `CHANGELOG.md` at the repository root.


## 2026-04-29T16:58:47+00:00

- **Branch**: `cursor/ai-context-continuity-7043`
- **HEAD**: `bd40fc66d10c4751bacb1a34f891eb3f179392bd`
- **Note**: chore: Added sync.sh one-command AI context pipeline — Users needed a single command to regenerate diagrams, log changes, and update memory — files: scripts/sync.sh

### Diff (working tree)

```
 CHANGELOG.md                         | 19 +++++++++++++++++--
 Readme/AI_PROJECT_MEMORY.md          | 10 ++++++++++
 git-hooks/pre-commit                 |  2 +-
 scripts/install_git_hooks.sh         |  2 +-
 scripts/regenerate_mermaid_output.sh |  2 +-
 5 files changed, 30 insertions(+), 5 deletions(-)
```

### Recent commits

```
bd40fc6 feat: add AI context continuity tools (primer, changelog, cursorrules)
54ca000 Merge pull request :human-readable-erd-workflow-aa47
82d8cd2 Add human-readable workflow and ERD outputs
3cfa96b Modified codebase_visualizer.py and regenerate_mermaid_output.sh
5ceddb9 Initial commit: CodeVisualizer tooling
```

## 2026-04-29T17:13:17+00:00

- **Branch**: `cursor/ai-context-continuity-7043`
- **HEAD**: `e8543630fb2472431694aae98725d15e6b5b419c`
- **Note**: chore: Package restructure — Make installable via pip

### Diff (working tree)

```
CHANGELOG.md           |  17 +
 codebase_visualizer.py | 997 +------------------------------------------------
 2 files changed, 34 insertions(+), 980 deletions(-)
```

### Recent commits

```
e854363 feat: add sync.sh — one-command AI context pipeline
bd40fc6 feat: add AI context continuity tools (primer, changelog, cursorrules)
54ca000 Merge pull request :human-readable-erd-workflow-aa47
82d8cd2 Add human-readable workflow and ERD outputs
3cfa96b Modified codebase_visualizer.py and regenerate_mermaid_output.sh
```
