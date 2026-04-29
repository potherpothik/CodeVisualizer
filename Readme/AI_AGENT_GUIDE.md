# AI agent quick guide (CodeVisualizer)

This tool generates **Mermaid diagrams**, a **JSON index**, and a **paste-ready
context primer** under **`mermaid_output/<target>/`** so you never have to
re-explain the project when you start a new AI chat.

---

## Problem → Solution map

| Problem | Solution |
|---------|----------|
| Starting a new chat and having to explain the project again | Paste `ai_context_primer.md` as the first message |
| AI suggests changes that break architectural constraints | Keep `.cursorrules` (see §6) and `AI_PROJECT_MEMORY.md` § "Architecture decisions" up to date |
| AI goes down the wrong path because it missed a recent fix | Log every change with `changelog.sh` and `ai_note.sh` |
| AI reads wrong file or misses key relationship | Point it at the relevant `.mmd` diagram or `codebase_index.json` |

---

## 1) Configure targets

Put your targets list in **one** of these (first match wins):

1. `CodeVisualizer/Readme/.ai-map-targets`
2. `CodeVisualizer/.ai-map-targets`
3. `/.ai-map-targets` at the host repo root (legacy)

Copy from `CodeVisualizer/Readme/.ai-map-targets.example`. Paths are relative
to the **host repository root**. Prefer **small, meaningful** subtrees (your
apps, libraries) rather than entire dependency trees.

## 2) Excludes (when a target is `.`)

If one line in `.ai-map-targets` is **`.`** (whole repo), add
**`CodeVisualizer/Readme/.ai-map-excludes`** or **`CodeVisualizer/.ai-map-excludes`**
(see `Readme/.ai-map-excludes.example`). Each line is a **relative path prefix**
passed to `codebase_visualizer.py --exclude` (e.g. `node_modules`, `vendor`, `.venv`).

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

You get **`mermaid_output/services__api/`** (that service only) and
**`mermaid_output/__root__/`** (repo root minus excluded prefixes).

## 3) Regenerate

```bash
./CodeVisualizer/scripts/regenerate_mermaid_output.sh
./CodeVisualizer/scripts/regenerate_mermaid_output.sh "packages/core"   # one-off path
```

Hashes in **`mermaid_output/.inputs.<target>.sha1`** skip work when
**git-tracked** files under that target are unchanged.

Outputs per target:

| File | Purpose |
|------|---------|
| `architecture.mmd` | File dependency graph |
| `classes.mmd` | Class hierarchy |
| `callgraph.mmd` | Full function call graph |
| `workflow.mmd` | Execution flow from entry points |
| `erd.mmd` | Entity-relationship diagram |
| `summary.md` | LOC stats + parse errors |
| `codebase_index.json` | Machine-readable class/function index |
| **`ai_context_primer.md`** | **Compact paste-ready brief for new AI chats** |

## 4) Optional: regenerate on commit

```bash
./CodeVisualizer/scripts/install_git_hooks.sh
```

## 5) Starting a new AI chat — zero re-explanation workflow

Follow these steps every time you open a fresh chat (in Cursor, ChatGPT, Claude, etc.):

### Step A — Paste the primer (always)

```
[Paste the full contents of mermaid_output/<target>/ai_context_primer.md
as your very first message.]
```

The primer contains: file map, class catalogue, function list, cross-file call
relationships, and pointers to all diagrams.  The AI has an accurate mental model
of the project without reading a single source file.

### Step B — Add recent history (if there were changes since last run)

```
[Paste or attach CodeVisualizer/Readme/AI_PROJECT_MEMORY.md]
[Paste or attach CHANGELOG.md (or the last 20 lines of it)]
```

This tells the AI *what changed* and *why*, so it does not suggest changes that
were already tried and discarded, or that contradict a recent decision.

### Step C — Add a diagram for the specific area you are working on (optional)

```
[Attach mermaid_output/<target>/callgraph.mmd   — for tracing a bug through calls]
[Attach mermaid_output/<target>/erd.mmd         — for data model questions]
[Attach mermaid_output/<target>/workflow.mmd    — for execution flow questions]
```

### Step D — Describe your task

Now describe what you need.  The AI already knows the project, what changed
recently, and the relevant architecture — so it can give a precise, targeted answer.

### Step E — After the chat, record what changed

```bash
# Free-form memory note (always do this):
./CodeVisualizer/scripts/ai_note.sh \
  "Fixed calculate_total rounding; moved rounding to post-sum; see src/invoice.py:142"

# Structured changelog entry (recommended):
./CodeVisualizer/scripts/changelog.sh \
    --type fix \
    --what "Fixed float rounding in calculate_total" \
    --why  "Per-line rounding accumulated cent errors in multi-item invoices" \
    --files "src/invoice.py tests/test_invoice.py"
```

## 6) Optional: Cursor `.cursorrules` for persistent context

Copy the template and fill in the project-specific sections:

```bash
cp CodeVisualizer/Readme/.cursorrules.example .cursorrules
```

Cursor automatically prepends `.cursorrules` to every prompt in the workspace,
so the AI always knows the project identity, architecture constraints, and where
to look — even without manually pasting the primer.

**Combine both:** `.cursorrules` for persistent identity + paste `ai_context_primer.md`
at the start of each session for the live code map.

## 7) Logging changes — keeping the AI on the right track

Two complementary tools:

### `ai_note.sh` — free-form notes

```bash
./CodeVisualizer/scripts/ai_note.sh "Short note: what changed, why, where."
```

Appends to `CodeVisualizer/Readme/AI_PROJECT_MEMORY.md` with branch, HEAD,
diff stat, and recent commits.  Good for quick context notes during development.

### `changelog.sh` — structured entries

```bash
./CodeVisualizer/scripts/changelog.sh \
    --type  feat|fix|refactor|perf|chore|docs|test \
    --what  "One-sentence summary of the change" \
    --why   "One-sentence motivation / root cause" \
    --files "file1.py file2.py"   # optional; auto-detected from git if omitted
```

Prepends a structured entry (table + prose) to `CHANGELOG.md` at the **repo
root**.  Machine-parseable yet human-readable.  An AI agent can scan this file
to immediately understand the full history of modifications without reading git
log or diff output.

**Why log changes at all?**  When context is large or the chat is long, models
hallucinate or lose track of earlier decisions.  Starting a new chat with the
primer + `AI_PROJECT_MEMORY.md` + `CHANGELOG.md` restores the full picture in
seconds without you having to re-explain anything.

## Suggested workflow summary

**One command does everything (recommended):**

```bash
./CodeVisualizer/scripts/sync.sh \
    --type fix \
    --what "What you changed" \
    --why  "Why you changed it"
```

This runs all three steps in order: regenerate diagrams → write `CHANGELOG.md` → update `AI_PROJECT_MEMORY.md`.

Or step-by-step if you prefer:

1. After any code change → run `changelog.sh` and/or `ai_note.sh`.
2. After meaningful structural changes → run `regenerate_mermaid_output.sh`.
3. When starting a new AI chat → paste `ai_context_primer.md` + recent history.
4. Keep `.cursorrules` current for Cursor IDE persistent context.
5. Keep targets and excludes tight so diagrams stay focused.

For **Git ignore / untrack** (host repo), see **`Readme.md` → "Git: ignore or stop tracking outputs and the tool"**.
