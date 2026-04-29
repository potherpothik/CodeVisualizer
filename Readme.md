# CodeVisualizer

Generate **Mermaid diagrams** and a **JSON index** from a Python codebase so IDEs and AI assistants can navigate structure, classes, call patterns, and workflows faster.

**Outputs** live under the **host repository root** in `mermaid_output/`, organized like this:

- **`mermaid_output/<sanitized-target>/`** — diagrams and `codebase_index.json` for **one** line from `.ai-map-targets` (multiple targets **do not** overwrite each other).
- **`mermaid_output/.inputs.<sanitized-target>.sha1`** — small cache files at the **parent** of those folders; used to skip regeneration when **git-tracked** files under that target are unchanged.

**`<sanitized-target>`** is derived from each target path: `/` and spaces become `_`, and the special target **`.`** (repo root) becomes **`__root__`** (e.g. `packages/my app` → `packages__my_app`).

Optional **`.ai-map-excludes`** supplies path prefixes for **`codebase_visualizer.py --exclude`** so wide targets (especially **`.`**) can skip dependencies and other large trees (e.g. `node_modules`, `vendor`, virtualenvs, this tool’s folder if embedded in the same repo).

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
  codebase_visualizer.py    ← main analyzer + CLI (--out, --exclude, --single, …)
  scripts/
    regenerate_mermaid_output.sh   ← reads .ai-map-targets + .ai-map-excludes, per-target --out
    install_git_hooks.sh
    ai_note.sh                     ← append a free-form note to AI_PROJECT_MEMORY.md
    changelog.sh                   ← append a structured entry to CHANGELOG.md (repo root)
  git-hooks/
    pre-commit
  Readme/
    .ai-map-targets.example
    .ai-map-excludes.example
    .cursorrules.example    ← Cursor IDE persistent context template (copy to repo root)
    AI_AGENT_GUIDE.md       ← short quick reference for agents and daily use
    AI_PROJECT_MEMORY.md    ← curated “what changed” log (optional)
  .ai-map-targets           ← optional (same semantics as Readme/.ai-map-targets; see below)
  .ai-map-excludes          ← optional prefix list for --exclude
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

The analyzer should **not** be pointed at huge trees unless you intend to (e.g. all of `node_modules/`, a full platform checkout). List **only** the subtrees you care about, or use target **`.`** together with a strict **`.ai-map-excludes`** file.

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

**Multiple targets:** each non-comment line produces its **own** subdirectory under `mermaid_output/`. Example for a **monorepo**: one focused package plus “everything at repo root” with vendor trees excluded:

```text
packages/core
.
```

With **`.ai-map-excludes`** (see §4), list prefixes such as `node_modules`, `vendor`, `.venv`, `CodeVisualizer`, and—if you want that package **only** in its own folder—`packages/core` so the **`.`** run does not duplicate it under **`__root__`**.

### 3) Git: ignore or stop tracking outputs and the tool (host repo)

Use this when generated diagrams should stay **local**, or when the tool is **vendored/copied** per developer and must not be part of the host project’s remote.

#### Never commit these paths (recommended)

Add to the host repository **`.gitignore`** (adjust names if your tool folder or output directory differs):

```gitignore
# Optional: embed tool only locally / from a separate repo
CodeVisualizer/

# Generated AI / diagram artifacts
mermaid_output/
```

New clones will not show these as untracked noise, and `git add` will not pick them up by default.

#### Paths were already committed: stop tracking but keep files on disk

If `CodeVisualizer/` or `mermaid_output/` was committed before you added `.gitignore`, remove them from the **index** only (files remain locally):

```bash
git rm -r --cached CodeVisualizer
git rm -r --cached mermaid_output
git commit -m "Stop tracking CodeVisualizer and mermaid_output (local tooling and generated output)"
```

After that, ensure the same paths are listed in **`.gitignore`** so they are not re-added.

#### Stop tracking a single file

```bash
git rm --cached path/to/file
```

#### Repository-wide ignore without editing `.gitignore` (one machine only)

You can add patterns to **`.git/info/exclude`** in the host repo (not shared with collaborators). Same syntax as `.gitignore`.

> **Note:** Incremental regeneration uses **git-tracked** file lists for hashing. If you rely on that optimization, keep your source code **tracked**; ignoring only `mermaid_output/` and the tool folder is the usual setup.

### 4) Optional: exclude subtrees (usually with target `.`)

When a target is the **repo root** (`.`), you usually skip vendor/core trees. Create **one** excludes file; the regenerate script uses the **first path that exists**:

1. `CodeVisualizer/Readme/.ai-map-excludes`
2. `CodeVisualizer/.ai-map-excludes`
3. `/.ai-map-excludes` at the **host repo root** (legacy)

Copy from `Readme/.ai-map-excludes.example`. Each non-comment line is a **relative path prefix** from the **analyzed directory** (for target `.`, that is the host repo root): e.g. `node_modules`, `vendor`, `.venv`, `dist`, `CodeVisualizer`.

The script passes every prefix as **`codebase_visualizer.py --exclude`** on **each** target run. For a **narrow** target (single addon folder), excludes that do not match any file under that folder have **no effect**.

### 5) Regenerate diagrams

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

**Output directory:** for each target line, **`mermaid_output/<sanitized-target>/`**, typically containing:

- `architecture.mmd`
- `classes.mmd`
- `callgraph.mmd`
- `workflow.mmd`
- `erd.mmd`
- `summary.md`
- `codebase_index.json`
- **`ai_context_primer.md`** — compact paste-ready project brief for new AI chats

**Incremental runs:** For each target, a hash is stored in **`mermaid_output/.inputs.<sanitized_target>.sha1`** (next to the per-target folders, not inside them). The hash is based on **git-tracked** files under that target. If nothing changed, that target’s diagrams are skipped.

> **Untracked files** are not included in that hash. After large local edits that are not yet committed, run with a **single explicit path** argument to force analysis, or commit/stage as appropriate.

### 6) (Optional) Auto-regenerate on `git commit`

Install the hook once per clone (from host repo root):

```bash
./CodeVisualizer/scripts/install_git_hooks.sh
```

This copies `CodeVisualizer/git-hooks/pre-commit` to `.git/hooks/pre-commit`. On commit, if staged files match common source extensions (`.py`, `.xml`, `.js`, `.ts`, …), it runs `regenerate_mermaid_output.sh`.

### 7) (Optional) Curated “project memory” for AI sessions

Chat transcripts are not in git. To keep a short, durable log (branch, HEAD, note, diff stat, recent commits):

```bash
./CodeVisualizer/scripts/ai_note.sh "What changed, why, where; include repro/logs if useful."
```

Default append path: `CodeVisualizer/Readme/AI_PROJECT_MEMORY.md` (fallback: host `Readme/AI_PROJECT_MEMORY.md` if the first is missing).

### 8) (Optional) Structured change log

Record every meaningful modification in a machine-readable yet human-readable format so an AI agent can understand the full history without parsing raw git log:

```bash
./CodeVisualizer/scripts/changelog.sh \
    --type  feat          `# feat | fix | refactor | perf | chore | docs | test` \
    --what  "Added PDF export to invoice emails" \
    --why   "Customers requested downloadable invoices" \
    --files "src/invoice.py src/email_sender.py"
```

Prepends a structured entry (table + prose) to **`CHANGELOG.md`** at the host repo root.
If `CHANGELOG.md` does not exist it is created with a header and column guide.
Omit `--files` to auto-detect changed files from `git diff HEAD`.

### 9) (Optional) Cursor IDE persistent context (`.cursorrules`)

Copy the template to your host repo root and fill in the project-specific sections:

```bash
cp CodeVisualizer/Readme/.cursorrules.example .cursorrules
```

Cursor automatically prepends `.cursorrules` to every prompt in the workspace, so the AI
always knows the project identity, stack, architecture constraints, and where to look —
even without manually pasting the context primer.

**Recommended combination:** `.cursorrules` for persistent identity + paste
`mermaid_output/<target>/ai_context_primer.md` at the start of each chat session
for the live, regenerated code map.

---

## Direct CLI (without shell helpers)

From anywhere:

```bash
python3 /path/to/CodeVisualizer/codebase_visualizer.py /path/to/project/to/analyze --out /path/to/mermaid_output
```

Skip subtrees (prefixes relative to `project_path`):

```bash
python3 /path/to/CodeVisualizer/codebase_visualizer.py /path/to/repo/root \
  --out /path/to/mermaid_output \
  --exclude node_modules --exclude vendor --exclude .venv --exclude CodeVisualizer
```

Options:

- `--out`, `-o` — output directory (default `./mermaid_output` relative to the current working directory)
- `--exclude`, `-x` — skip `.py` files whose path (relative to `project_path`) equals or starts with this prefix; repeatable
- `--single`, `-s` — single combined diagram mode (if enabled in your copy of the script)

---

## Configuration / code changes in *other* projects

**No changes are required inside your application code.** This tool is **offline analysis** only:

- It **does not** import your runtime package.
- It **does not** patch your project.

You only configure:

1. **Where the tool lives** in the tree (see above).
2. **`.ai-map-targets`** — which directories to scan (relative to host git root); each line → `mermaid_output/<sanitized-target>/`.
3. **`.ai-map-excludes`** (optional) — path prefixes for `--exclude` when scanning wide trees (especially target `.`).
4. **Host `.gitignore`** — if you want `CodeVisualizer/` and `mermaid_output/` excluded from that repo.

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
| Regeneration **never** runs | Hash skip: inspect `mermaid_output/.inputs.*.sha1`; run with an explicit folder argument to force one target. |
| **Slow** runs | Narrow `.ai-map-targets`, or use target `.` with a thorough **`.ai-map-excludes`** (dependencies, build output, virtualenvs). |
| Wrong or missing diagrams after multi-target setup | Each target writes to **`mermaid_output/<sanitized-target>/`**; open the folder that matches your target line (not the old flat `mermaid_output/*.mmd` layout). |
| Hook does nothing | Ensure `install_git_hooks.sh` ran in a **git** repo; check staged file extensions match the hook. |

---

## See also

- `Readme/AI_AGENT_GUIDE.md` — condensed workflow for day-to-day use, including the "zero re-explanation" new-chat protocol.
- `Readme/AI_PROJECT_MEMORY.md` — curated change history with architecture decisions and known issues.
- `Readme/.cursorrules.example` — Cursor IDE persistent context template.
- `Readme/.ai-map-targets.example` — template for target paths.
- `Readme/.ai-map-excludes.example` — template for `--exclude` prefixes.
- `scripts/changelog.sh` — structured change-log tool (`--type`, `--what`, `--why`, `--files`).
- `scripts/ai_note.sh` — free-form project memory note tool.
