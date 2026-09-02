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

- [x] `SubstringLexicalIndex.search()` (or its direct successor) also scores
      `+0.5` per query term found as a case-insensitive substring in
      `chunk.source_text`, counted once per distinct term (presence, not
      occurrence count — same rule already used for `symbol`/`file_path`).
- [x] Relative weights stay `symbol=2.0 > file_path=1.0 > source_text=0.5`.
- [x] A unit test proves a chunk with a term only in `source_text` (absent
      from `symbol` and `file_path`) is now returned with score `> 0`.
- [x] A unit test proves the existing `symbol`/`file_path` scoring is
      unchanged for chunks that don't need the new signal (no regression).
- [x] `benchmarks/runner.py` re-run on the affected project shows `tra-02` (or
      an equivalent case) improve, or a note explaining why it didn't.
      Satisfied via the second branch — see "Verification notes" below.

## Verification notes (2026-09-02)

- **Code + tests**: implemented in
  `adapters/storage/substring_lexical_index.py`; two new tests added to
  `tests/adapters/test_substring_lexical_index.py`
  (`test_term_only_in_source_text_is_still_found`,
  `test_source_text_match_does_not_change_symbol_or_path_scoring`). Full
  suite: 73/73 passing, no regressions.
- **Deterministic check** (`crm search --project <id> "<term>"`, bypasses the
  agent, no LLM cost): confirms the mechanism works exactly as designed —
  chunks whose matching term lives only in `source_text` now score via the
  lexical layer and rank higher. E.g. in `mf-core-platform`, the
  `README.md:51-110` block (mentions "playwright" only in its body, not in
  `symbol`/`file_path`) went from `0.481 semantic` to `0.600 hybrid`, moving
  from rank #5 to #3. Equivalent jumps observed in `mic-inventory` (a doc
  chunk mentioning "Kafka") and `mic-clients` (a `README.md` block).
- **Agentic re-run of `benchmarks/runner.py`** (`mcp` arm only, scoped to the
  3 `trampa` questions + 1 control question per project across the 3-project
  bank, rep=1 baseline pre-fix vs. rep=2 post-fix, 24 `claude -p` calls
  total, results not committed — `benchmarks/` is gitignored): did **not**
  show a correctness flip attributable to this fix on the target case
  (`mf-core-platform|tra-02`). That cell was already answered correctly in
  both baseline and post-fix, because the project's Playwright test files
  now live under paths containing "playwright" (e.g. `tests/playwright/...`)
  — a signal the pre-existing `file_path` scoring already covers. The repo
  has drifted since the original benchmark run (2026-08-01) that diagnosed
  this gap (see `PLAN-MEJORA-CODE-RAG-MANAGER.md §3`). The only marker flip
  observed (`mf-core-platform|tra-01`) was due to LLM answer-phrasing
  variance between the two independent samples, not this fix. No
  regressions across the 12 replayed questions.
- **Net**: the fix is verified correct and working as intended at the
  index/scoring level (deterministic evidence above); this particular
  benchmark resample (single rep, one project's case already covered by a
  pre-existing signal) lacked the right case to also show it moving the
  needle at the full-agent level.

## Out of scope

- Term-frequency counting or length normalization inside `source_text` — that
  is Nivel 2's job (US-11, real BM25). This story intentionally accepts the
  known edge case where a long chunk containing several query terms by
  chance could out-score a precise `symbol` match elsewhere.
- Any change to the semantic (embedding) side of `search_code`.

## Files likely touched

- `src/coderagmanager/adapters/storage/substring_lexical_index.py`
- `tests/adapters/` (new/updated test for the lexical index)
