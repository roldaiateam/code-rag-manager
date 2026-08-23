# US-01 — Lexical search also over `source_text`

**Tier:** Nivel 0 (close the measured gap) · **Depends on:** —
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §5.1`, §12 point 1

## Story

As an agent calling `search_code`, I want a chunk to be findable even when the
query term only appears inside its body (not its name or file path), so that
I stop missing answers that live in a chunk's implementation rather than its
identifier.

## Context

Confirmed by reading `adapters/storage/substring_lexical_index.py:22-41`:
`SubstringLexicalIndex.search()` only scores matches against `chunk.symbol`
(+2.0 per term) and `chunk.file_path` (+1.0 per term) — never against
`chunk.source_text`, even though that field is already persisted in full.
This is the confirmed root cause of the benchmark's "trampa" category
regression (67% vs 89% without MCP) — see `§3` of the design doc for the
Playwright/Cypress case that exposed it.

## Acceptance criteria

- [ ] `SubstringLexicalIndex.search()` (or its direct successor) also scores
      `+0.5` per query term found as a case-insensitive substring in
      `chunk.source_text`, counted once per distinct term (presence, not
      occurrence count — same rule already used for `symbol`/`file_path`).
- [ ] Relative weights stay `symbol=2.0 > file_path=1.0 > source_text=0.5`.
- [ ] A unit test proves a chunk with a term only in `source_text` (absent
      from `symbol` and `file_path`) is now returned with score `> 0`.
- [ ] A unit test proves the existing `symbol`/`file_path` scoring is
      unchanged for chunks that don't need the new signal (no regression).
- [ ] `benchmarks/runner.py` re-run on the affected project shows `tra-02` (or
      an equivalent case) improve, or a note explaining why it didn't.

## Out of scope

- Term-frequency counting or length normalization inside `source_text` — that
  is Nivel 2's job (US-11, real BM25). This story intentionally accepts the
  known edge case where a long chunk containing several query terms by
  chance could out-score a precise `symbol` match elsewhere.
- Any change to the semantic (embedding) side of `search_code`.

## Files likely touched

- `src/coderagmanager/adapters/storage/substring_lexical_index.py`
- `tests/adapters/` (new/updated test for the lexical index)
