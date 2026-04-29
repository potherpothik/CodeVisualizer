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

<!-- Template — copy-paste and fill in:

| ID | Decision | Status | Chosen | Rejected | Consequences | Enforced in |
|----|----------|--------|--------|----------|--------------|-------------|
| DEC-001 | Monetary values stored as integers (cents) | active | int cents | float/Decimal | All display formatting at boundary (PDF, API) | src/invoice.py, src/payment.py |
| DEC-002 | No ORM lazy loading | active | explicit joinedload() | lazy default | Prevents N+1 in high-traffic endpoints | src/db.py |

Context (one line per entry explaining *why* the decision was made):
- DEC-001: float precision causes rounding drift in tax calculations.
- DEC-002: lazy loading caused 300 ms+ response times on /orders endpoint (2024-11 profiling).

-->

---

## Known pitfalls — do not suggest

> Short, non-negotiable constraints. The AI **must not** propose any of these.

<!-- Template:

- **Do not change rounding order** (`src/invoice.py:calculate_total`) — rounding after sum, not per-line.
- **Do not touch `vendor/` folder** — third-party code frozen at pinned version; wrap, never edit.
- **No enterprise code copy** — proprietary logic from Client X must stay in `src/x_adapter.py` only.
- **Do not add `SELECT *` queries** — all ORM queries must list explicit columns for performance.

-->

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

---

## Known issues / gotchas

> Document non-obvious bugs, surprising edge-cases, or partial fixes so the AI
> does not repeatedly suggest the same wrong solutions.
>
> Include a short "How to reproduce" block for every bug. This prevents agents
> from proposing fixes without evidence.

<!-- Example entries:

- **Invoice rounding** (`src/invoice.py:calculate_total`) — rounding is done
  *after* summing all line items, not per-line.  Per-line rounding accumulates
  errors.  Do not change this without updating the test suite in `tests/test_invoice.py`.
  - *Reproduce*: `python -c "from src.invoice import calc; calc([0.1]*3)"` → total is 0.30, not 0.29.

- **Legacy payment adapter** (`legacy/payment_v1.py`) — vendor code, do not modify.
  The interface is wrapped in `src/payment_adapter.py`.
  - *Reproduce*: N/A (static vendor file; changes break signature verification).

-->

---

## Recent changes

> Entries added by `codevis note` appear below in reverse-chronological order.
> For a full structured log see `CHANGELOG.md` at the repository root.
