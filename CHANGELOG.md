# CHANGELOG

This file records every significant change to the project in a format optimised
for both humans and AI agents.

**Column guide:**
- **Type** — `feat` new feature | `fix` bug fix | `refactor` restructure | `perf` speed | `chore` tooling | `docs` docs only | `test` tests only
- **What changed** — one-sentence summary of the modification
- **Why** — the motivation or root cause that drove the change
- **Files touched** — the specific files modified (helps an AI jump straight to the right code)

<!-- ENTRIES_START -->
## [chore] 2026-04-29T17:13:17+00:00

| Field   | Value |
|---------|-------|
| Type    | `chore` |
| Branch  | `cursor/ai-context-continuity-7043` |
| Commit  | `e8543630fb2472431694aae98725d15e6b5b419c` |
| Date    | 2026-04-29T17:13:17+00:00 |

**What changed:** Package restructure

**Why:** Make installable via pip

**Files touched:** `codebase_visualizer.py`

---

## [chore] 2026-04-29T16:58:47+00:00

| Field   | Value |
|---------|-------|
| Type    | `chore` |
| Branch  | `cursor/ai-context-continuity-7043` |
| Commit  | `bd40fc66d10c4751bacb1a34f891eb3f179392bd` |
| Date    | 2026-04-29T16:58:47+00:00 |

**What changed:** Added sync.sh one-command AI context pipeline

**Why:** Users needed a single command to regenerate diagrams, log changes, and update memory

**Files touched:** `scripts/sync.sh`

---## [feat] 2026-04-29T16:35:52+00:00

| Field   | Value |
|---------|-------|
| Type    | `feat` |
| Branch  | `cursor/ai-context-continuity-7043` |
| Commit  | `54ca0002069e12dee6615e2c4f5afc1758768b58` |
| Date    | 2026-04-29T16:35:52+00:00 |

**What changed:** Added ai_context_primer.md generation and changelog.sh script

**Why:** Users needed a way to avoid re-explaining the project in every new AI chat and to track modification history for AI agents

**Files touched:** `codebase_visualizer.py scripts/changelog.sh Readme/AI_AGENT_GUIDE.md Readme/AI_PROJECT_MEMORY.md Readme/.cursorrules.example Readme.md`

---
