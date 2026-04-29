# CodeVisualizer

**AI context toolkit for Python projects.**  
Generate Mermaid diagrams, a JSON index, and a paste-ready `ai_context_primer.md`
from any Python codebase — so your IDE AI always has a true picture of the system
without reading every file.

---

## Install

```bash
pip install codevisualizer
```

No dependencies beyond the Python standard library.  Works on Python 3.9+.

---

## Quick start (3 steps)

### 1. Initialize your project (once)

```bash
cd /path/to/your-project
codevis init
```

Creates (if absent):

| File | Purpose |
|------|---------|
| `.codevis-targets` | Paths to analyze (one per line) |
| `.codevis-excludes` | Path prefixes to skip (e.g. `node_modules`, `.venv`) |
| `.cursorrules` | Cursor IDE persistent context — fill in your project details |
| `AI_PROJECT_MEMORY.md` | Curated change log for AI sessions |

### 2. Run sync after every meaningful change

```bash
codevis sync \
    --type fix \
    --what "Fixed price rounding in invoice total" \
    --why  "Per-line rounding accumulated cent errors"
```

This runs all three pipeline steps in order:

| Step | What it does | Output |
|------|-------------|--------|
| 1 | Analyze Python source | `mermaid_output/<target>/` (diagrams + primer + index) |
| 2 | Structured changelog entry | `CHANGELOG.md` |
| 3 | AI memory note | `AI_PROJECT_MEMORY.md` |

### 3. Start a new AI chat — zero re-explanation

Paste `mermaid_output/<target>/ai_context_primer.md` as the **first message**.
The agent instantly has the full project picture: file map, classes, functions,
cross-file call relationships, and pointers to all diagrams.

---

## All commands

```
codevis init        # Scaffold config files (run once per project)
codevis analyze     # Regenerate diagrams + ai_context_primer.md
codevis changelog   # Append structured entry to CHANGELOG.md
codevis note        # Append free-form note to AI_PROJECT_MEMORY.md
codevis sync        # All three in one command (recommended)
```

### `codevis sync` — full option reference

```bash
codevis sync [PATH] \
    --type   feat|fix|refactor|perf|chore|docs|test \
    --what   "What changed (one sentence)" \
    --why    "Why it changed (one sentence)" \
    --files  "file1.py file2.py"    # optional; auto-detected from git
    --note   "Extra memory note"    # optional; auto-composed from --what/--why
    --target packages/core          # analyze one folder instead of all targets
    --skip-regen                    # skip diagram regeneration
    --force                         # re-analyze even if git hash unchanged
```

All flags after `PATH` are optional — bare `codevis sync` just refreshes diagrams.

### `codevis analyze`

```bash
codevis analyze [PATH] [--out DIR] [--exclude PREFIX] [--target PATH] [--force]
```

### `codevis changelog`

```bash
codevis changelog --type fix --what "..." --why "..." [--files "..."]
```

### `codevis note`

```bash
codevis note "Short note: what changed, why, where to look."
```

---

## Outputs (per analyzed target)

| File | Purpose |
|------|---------|
| `architecture.mmd` | File dependency graph |
| `classes.mmd` | Class hierarchy |
| `callgraph.mmd` | Full function call graph |
| `workflow.mmd` | Execution flow from entry points |
| `erd.mmd` | Entity-relationship diagram |
| `summary.md` | LOC stats + parse errors |
| `codebase_index.json` | Machine-readable class/function index |
| **`ai_context_primer.md`** | **Paste-ready brief for new AI chats** |

All files go to `mermaid_output/<sanitized-target>/` in the repo root.

---

## Python API

```python
from codevisualizer import ProjectVisualizer

viz = ProjectVisualizer("/path/to/project", exclude_prefixes=["node_modules", ".venv"])
viz.analyze()
viz.write_all("/path/to/output")
```

---

## Configuration files

### `.codevis-targets`

```text
# One path per line, relative to the repo root.
src/my_app
packages/api
```

### `.codevis-excludes`

```text
# Path prefixes to skip.
node_modules
.venv
dist
```

### `.cursorrules` (Cursor IDE)

Copy from the installed template and fill in your project details:

```bash
codevis init   # creates .cursorrules automatically
```

Or copy manually:

```bash
python -c "import codevisualizer, shutil, pathlib; \
  shutil.copy(str(pathlib.Path(codevisualizer.__file__).parent / 'templates/.cursorrules.example'), '.cursorrules')"
```

---

## How the four goals are served

| Goal | How |
|------|-----|
| **Persistent project memory** | `.cursorrules` (always-on in Cursor) + `AI_PROJECT_MEMORY.md` + `ai_context_primer.md` |
| **Auto-generated project graph** | `codevis analyze` → architecture, classes, callgraph, workflow, ERD, JSON index |
| **Change log with intent** | `codevis changelog --what "..." --why "..."` → `CHANGELOG.md` |
| **Guided retrieval layer** | `ai_context_primer.md` pre-computes cross-file relationships; `.cursorrules` tells the AI exactly which file to read first |

---

## Why no third-party dependencies?

The analyzer uses only `ast`, `json`, `pathlib`, `subprocess`, and `hashlib` from
the standard library.  `pip install codevisualizer` works in any environment,
including locked corporate environments and CI containers, without dependency
conflicts.

---

## Migrating from the bash scripts

| Old command | New command |
|-------------|-------------|
| `./CodeVisualizer/scripts/sync.sh --type fix --what ... --why ...` | `codevis sync --type fix --what ... --why ...` |
| `./CodeVisualizer/scripts/regenerate_mermaid_output.sh` | `codevis analyze` |
| `./CodeVisualizer/scripts/changelog.sh --type fix --what ... --why ...` | `codevis changelog --type fix --what ... --why ...` |
| `./CodeVisualizer/scripts/ai_note.sh "note"` | `codevis note "note"` |
| `python codebase_visualizer.py /path` | `codevis analyze /path` or `python codebase_visualizer.py /path` (still works) |

---

See `Readme.md` for the full documentation including git hooks, multi-target
setups, and embedding CodeVisualizer inside a host repository.
