# CodeVisualizer

Generate **Mermaid diagrams** and a **JSON index** from a Python codebase so IDEs and AI assistants can navigate structure, classes, call patterns, and workflows faster.

Outputs are written to **`mermaid_output/`** at the **host repository root** (by design), not inside this folder.

---

## Requirements

| Requirement | Notes |
|-------------|--------|
| **Python 3** | Uses the standard library only (`codebase_visualizer.py` has no third-party pip dependencies). |
| **Bash** | Shell scripts use `bash`. |
| **Git** (optional but recommended) | Used to detect the host repo root, for `pre-commit` hooks, and for “skip regeneration if tracked files unchanged”. |

---

## Repository layout (this tool)

```
CodeVisualizer/
  Readme.md                 ← this file
  codebase_visualizer.py    ← main analyzer + CLI
  scripts/
    regenerate_mermaid_output.sh
    install_git_hooks.sh
    ai_note.sh
  git-hooks/
    pre-commit
  Readme/
    .ai-map-targets.example
    AI_AGENT_GUIDE.md       ← short Odoo-oriented quick reference
    AI_PROJECT_MEMORY.md    ← curated “what changed” log (optional)
  .ai-map-targets           ← optional; you can keep config here (not committed in your main repo if you gitignore the folder)
```

---

## Using CodeVisualizer inside another project (recommended workflow)

### 1) Add the tool to the host repository

Pick **one** of these patterns:

**A. Copy or clone into the host repo (typical)**

```text
your-host-repo/
  .git/
  CodeVisualizer/          ← this entire folder (from your separate CodeVisualizer GitHub repo)
  src/   (or apps/, packages/, etc.)
```

**B. Symlink (same paths, tool lives elsewhere)**

```bash
cd /path/to/your-host-repo
ln -s /path/to/your/CodeVisualizer-checkout CodeVisualizer
```

**C. Nested path (allowed)**  
You may place the folder deeper (e.g. `tools/CodeVisualizer/`). Scripts resolve the **git top-level** of the host repo, so `.ai-map-targets` paths stay relative to the **host repo root**, not relative to the `CodeVisualizer` folder.

> **Folder name:** Scripts locate themselves via `TOOL_DIR`; they do **not** require the directory to be named `CodeVisualizer` for execution. Some **error messages** still mention `CodeVisualizer/...`; use `--targets-file` with your real path if you rename the folder.

### 2) Configure what to analyze (required)

The analyzer should **not** be pointed at huge trees unless you intend to (e.g. full Odoo `community/` + `enterprise/`). List **only** the subtrees you care about.

Create **one** of these files (first existing file wins):

1. `CodeVisualizer/Readme/.ai-map-targets`
2. `CodeVisualizer/.ai-map-targets`
3. `/.ai-map-targets` at the **host repo root** (legacy)

Start from the example:

```bash
cp CodeVisualizer/Readme/.ai-map-targets.example CodeVisualizer/.ai-map-targets
```

Edit the file: **one path per line**, relative to the **host repository root**. Example:

```text
# comments start with #
src/my_app
packages/api
```

Paths may contain spaces (e.g. `My Client App`); quote if your shell needs it when passing a single folder on the CLI.

### 3) (Optional) Ignore the tool and generated output in the host repo

If the host project should **not** publish CodeVisualizer to its GitHub (separate tool repo), add to the host **`.gitignore`**:

```gitignore
CodeVisualizer/
mermaid_output/
```

Then each developer clones or copies CodeVisualizer locally.

### 4) Regenerate diagrams

From the **host repository root**:

```bash
./CodeVisualizer/scripts/regenerate_mermaid_output.sh
```

One-off analysis of a single folder (still from host root; quote paths with spaces):

```bash
./CodeVisualizer/scripts/regenerate_mermaid_output.sh "path/to/subproject"
```

Explicit targets file:

```bash
./CodeVisualizer/scripts/regenerate_mermaid_output.sh --targets-file "CodeVisualizer/.ai-map-targets"
```

**Output directory:** `mermaid_output/` at the host repo root, typically:

- `architecture.mmd`
- `classes.mmd`
- `callgraph.mmd`
- `workflow.mmd`
- `summary.md`
- `codebase_index.json`

**Incremental runs:** For each target, a hash is stored under `mermaid_output/.inputs.<sanitized_target>.sha1`. If **tracked** git files under that target did not change, regeneration is skipped.

> **Untracked files** are not included in that hash. After large local edits that are not yet committed, run with a **single explicit path** argument to force analysis, or commit/stage as appropriate.

### 5) (Optional) Auto-regenerate on `git commit`

Install the hook once per clone (from host repo root):

```bash
./CodeVisualizer/scripts/install_git_hooks.sh
```

This copies `CodeVisualizer/git-hooks/pre-commit` to `.git/hooks/pre-commit`. On commit, if staged files match common source extensions (`.py`, `.xml`, `.js`, `.ts`, …), it runs `regenerate_mermaid_output.sh`.

### 6) (Optional) Curated “project memory” for AI sessions

Chat transcripts are not in git. To keep a short, durable log (branch, HEAD, note, diff stat, recent commits):

```bash
./CodeVisualizer/scripts/ai_note.sh "What changed, why, where; include repro/logs if useful."
```

Default append path: `CodeVisualizer/Readme/AI_PROJECT_MEMORY.md` (fallback: host `Readme/AI_PROJECT_MEMORY.md` if the first is missing).

---

## Direct CLI (without shell helpers)

From anywhere:

```bash
python3 /path/to/CodeVisualizer/codebase_visualizer.py /path/to/project/to/analyze --out /path/to/mermaid_output
```

Options:

- `--out`, `-o` — output directory (default `./mermaid_output` relative to the current working directory)
- `--single`, `-s` — single combined diagram mode (if enabled in your copy of the script)

---

## Configuration / code changes in *other* projects

**No changes are required inside your application code.** This tool is **offline analysis** only:

- It **does not** import your runtime package.
- It **does not** patch your project.

You only configure:

1. **Where the tool lives** in the tree (see above).
2. **`.ai-map-targets`** — which directories to scan (relative to host git root).
3. **Host `.gitignore`** — if you want `CodeVisualizer/` and `mermaid_output/` excluded from that repo.

If you **rename** the tool directory, update:

- Your own docs/commands (e.g. `./tools/MyVisualizer/scripts/...`).
- Optional: paths passed to `--targets-file`.

No edits to `codebase_visualizer.py` are needed for normal use.

---

## Publishing this folder as its **own** GitHub repository

1. Create a new empty repository (e.g. `yourname/code-visualizer`).
2. Push **only** the contents of `CodeVisualizer/` as that repo’s root (so `codebase_visualizer.py` and `scripts/` sit at the top level of the new repo).
3. On GitHub, the default readme file is **`README.md`**. This project ships **`Readme.md`**; either rename it to `README.md` in that standalone repo or add a one-line `README.md` that points to `Readme.md`.

In consumer projects, add the tool by cloning into `CodeVisualizer/` or any path you prefer.

### Developing or testing the tool repo alone

The shell helpers (`regenerate_mermaid_output.sh`, hooks) assume the tool folder lives **inside a larger host repository** so `ROOT_DIR` is that host’s git top-level. If this repository **is only** CodeVisualizer at the root, use the Python CLI directly:

```bash
python3 codebase_visualizer.py . --out ./mermaid_output
```

Or embed the folder into a host project and use the scripts from the host root as documented above.

---

## Troubleshooting

| Issue | What to check |
|--------|----------------|
| `No target provided and no targets file found` | Create `.ai-map-targets` in one of the locations listed in section 2. |
| `unrecognized arguments` / path split wrong | Quote paths that contain **spaces**. |
| Regeneration **never** runs | Hash skip: compare `mermaid_output/.inputs.*.sha1`; run with an explicit folder argument to force. |
| **Slow** runs | You pointed at too large a tree; narrow `.ai-map-targets` to app/custom folders only. |
| Hook does nothing | Ensure `install_git_hooks.sh` ran in a **git** repo; check staged file extensions match the hook. |

---

## See also

- `Readme/AI_AGENT_GUIDE.md` — condensed workflow (written with Odoo-sized repos in mind).
- `Readme/.ai-map-targets.example` — template for target paths.
