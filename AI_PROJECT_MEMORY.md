# AI Project Memory

This file is a **curated, durable history** meant for future AI sessions.

It is intentionally short and practical:
- what changed
- why it changed
- where to look
- how to reproduce / logs if relevant

Add entries with:

```bash
./CodeVisualizer/scripts/ai_note.sh "your note..."
```

For structured change tracking (recommended), also use:

```bash
./CodeVisualizer/scripts/changelog.sh \
    --type fix \
    --what "One-sentence summary of what changed" \
    --why  "One-sentence reason / motivation" \
    --files "path/to/file1.py path/to/file2.py"
```

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

<!-- Example entries:

- **Invoice rounding** (`src/invoice.py:calculate_total`) — rounding is done
  *after* summing all line items, not per-line.  Per-line rounding accumulates
  errors.  Do not change this without updating the test suite in `tests/test_invoice.py`.

- **Legacy payment adapter** (`legacy/payment_v1.py`) — vendor code, do not modify.
  The interface is wrapped in `src/payment_adapter.py`.

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
