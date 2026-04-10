# AI agent quick guide (CodeVisualizer)

This tool generates **Mermaid diagrams** and **`codebase_index.json`** under **`mermaid_output/<target>/`** (one subdirectory per line in `.ai-map-targets`) for faster navigation and AI-assisted debugging.

## 1) Configure targets

Put your targets list in **one** of these (first match wins):

1. `CodeVisualizer/Readme/.ai-map-targets`
2. `CodeVisualizer/.ai-map-targets`
3. `/.ai-map-targets` at the host repo root (legacy)

Copy from `CodeVisualizer/Readme/.ai-map-targets.example`. Paths are relative to the **host repository root**. Prefer **small, meaningful** subtrees (your apps, libraries) rather than entire dependency trees.

## 2) Excludes (when a target is `.`)

If one line in `.ai-map-targets` is **`.`** (whole repo), add **`CodeVisualizer/Readme/.ai-map-excludes`** or **`CodeVisualizer/.ai-map-excludes`** (see `Readme/.ai-map-excludes.example`). Each line is a **relative path prefix** passed to `codebase_visualizer.py --exclude` (e.g. `node_modules`, `vendor`, `.venv`).

### Example: two outputs without scanning vendor trees

**`.ai-map-targets`:**

```text
services/api
.
```

**`.ai-map-excludes`** (for the `.` run; adjust to your repo):

```text
CodeVisualizer
node_modules
vendor
.venv
dist
services/api
```

You get **`mermaid_output/services__api/`** (that service only) and **`mermaid_output/__root__/`** (repo root minus excluded prefixes). Listing `services/api` twice is intentional only if you want a **dedicated** folder for that subtree **and** want it **omitted** from the root map via excludes.

## 3) Regenerate

```bash
./CodeVisualizer/scripts/regenerate_mermaid_output.sh
./CodeVisualizer/scripts/regenerate_mermaid_output.sh "packages/core"   # one-off path (quote if spaces)
```

Hashes in **`mermaid_output/.inputs.<target>.sha1`** skip work when **git-tracked** files under that target are unchanged.

## 4) Optional: regenerate on commit

```bash
./CodeVisualizer/scripts/install_git_hooks.sh
```

## 5) Optional: curated “project memory”

```bash
./CodeVisualizer/scripts/ai_note.sh "Short note: what changed, why, where."
```

Appends to `CodeVisualizer/Readme/AI_PROJECT_MEMORY.md` (with a fallback path documented in the main Readme).

## Suggested workflow

- Keep targets and excludes tight.
- Regenerate after meaningful code changes (or rely on the hook).
- When asking an AI for help, attach logs/tracebacks, the relevant path, and files under **`mermaid_output/<target>/`** (e.g. `codebase_index.json`, `callgraph.mmd`).

For **Git ignore / untrack** (host repo), see **`Readme.md` → “Git: ignore or stop tracking outputs and the tool”**.
