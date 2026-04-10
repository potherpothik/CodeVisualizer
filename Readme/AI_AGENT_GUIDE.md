# AI Agent Automation Guide (Odoo workspace)

This repo generates **AI navigation artifacts** (Mermaid diagrams + an index) under `mermaid_output/` to speed up debugging and code understanding.

## 1) Auto-regenerate diagrams when code changes (local)

### Configure targets (important)

Put your targets list in **one** of these (first match wins):

1. `CodeVisualizer/Readme/.ai-map-targets` — keeps config next to the AI docs  
2. `CodeVisualizer/.ai-map-targets` — single file at the tool root (good when reusing the folder elsewhere)  
3. `/.ai-map-targets` at the repo root — legacy only  

Copy from `CodeVisualizer/Readme/.ai-map-targets.example`. Paths inside the file are relative to the **repository root**. This avoids scanning huge Odoo sources like `community/` and `enterprise/`.

### Regenerate on demand

```bash
cp CodeVisualizer/Readme/.ai-map-targets.example CodeVisualizer/.ai-map-targets
# or: ... CodeVisualizer/Readme/.ai-map-targets
./CodeVisualizer/scripts/regenerate_mermaid_output.sh
./CodeVisualizer/scripts/regenerate_mermaid_output.sh "Facade V3"     # one-off run for a specific folder
```

The script caches a hash per target under `mermaid_output/.inputs.<target>.sha1` and **skips regeneration** if tracked files under that target path did not change.

### Regenerate automatically on every commit (recommended)

Install the provided git hook:

```bash
./CodeVisualizer/scripts/install_git_hooks.sh
```

This installs `.git/hooks/pre-commit` which regenerates `mermaid_output/` when staged changes include typical source files (`.py`, `.xml`, `.js`, `.ts`, etc.).

> Note: `mermaid_output/` is currently gitignored in this repo, so the hook regenerates files **for local AI use** only.

## 2) Track “project memory” so future AI sessions understand what changed

Cursor chat transcripts are not tracked in git. Instead, keep a **small curated log** tied to commits/branches.

Append a note after meaningful work:

```bash
./CodeVisualizer/scripts/ai_note.sh "What changed, why, and where. Include error context if relevant."
```

This appends to `CodeVisualizer/Readme/AI_PROJECT_MEMORY.md`:
- branch + HEAD SHA
- your note
- `git diff --stat`
- last 5 commits

## Suggested workflow

- Run your work (debug/fix/feature)
- Commit normally
- Add an AI memory note (1–3 sentences) with the intent and context
- When debugging later, give the AI:
  - the error traceback/logs
  - the affected module path
  - `CodeVisualizer/Readme/AI_PROJECT_MEMORY.md`
  - `mermaid_output/codebase_index.json` + `mermaid_output/callgraph.mmd` (if available)

