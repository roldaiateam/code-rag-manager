# US-02 — Confidence threshold in `search_code`

**Tier:** Nivel 0 (close the measured gap) · **Depends on:** US-01
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §5.2`, §12 point 2

## Story

As an agent calling `search_code`, I want to be told explicitly when no
result is a strong match, so that I don't present a mediocre result as if it
were a confident answer (the failure mode behind the "trampa" benchmark
category).

## Context

`domain/ranking.py::_normalize()` performs min-max normalization *within the
current result batch*, which means the top result of any non-empty batch is
always stretched toward `1.0` regardless of absolute quality. A threshold
applied **after** that normalization would essentially never fire. The
threshold must be applied to the **raw, pre-normalization** scores instead.

## Acceptance criteria

- [x] Before `merge_and_rerank` normalizes scores, capture the best raw
      semantic score (cosine similarity from `VectorStore.search()`) and the
      best raw lexical score (from the lexical index, post US-01).
- [x] Low-confidence condition: best raw semantic score `< 0.35` **AND** best
      raw lexical score `== 0`. Both must fail — if either channel found real
      signal, do not flag.
- [x] When the condition is true, `search_code`'s formatted output still
      returns the top 1-3 candidates (never an empty response) but is
      prefixed with an explicit low-confidence notice, e.g.: `"⚠ No result
      clears the confidence threshold for this query; closest matches below,
      treat with caution:"`.
- [x] Unit test: a query with no lexical hits and low cosine similarity
      across all candidates triggers the notice.
- [x] Unit test: a query with a strong lexical hit but weak semantic score
      does **not** trigger the notice (hybrid — either channel is enough).
- [x] `0.35` / `0` are the starting values from the design doc; if
      `benchmarks/runner.py` calibration suggests different values, update
      both the code and `PLAN-MEJORA-CODE-RAG-MANAGER.md §5.2` together.

## Verification notes (2026-09-05)

- **Code + tests**: `domain/ranking.py` gains `is_low_confidence()` (pure,
  evaluated on raw pre-normalization scores) plus
  `SEMANTIC_CONFIDENCE_THRESHOLD`/`LEXICAL_CONFIDENCE_THRESHOLD`.
  `domain/models.py` gains `SearchOutcome(results, low_confidence)` so
  `SearchCode.execute()` can carry the flag to its callers.
  `application/search_code.py` computes the flag from the raw
  `semantic`/`lexical` lists *before* calling `merge_and_rerank`, and caps
  the returned results to 3 when the flag is set. `adapters/formatting.py`
  prefixes `format_search_results()` with `LOW_CONFIDENCE_NOTICE` (in
  Spanish, consistent with the rest of that module — the string in this
  acceptance criteria is illustrative, not literal; see US-19). Both call
  sites (`adapters/cli/main.py`, `adapters/mcp/server.py`) updated for the
  new `SearchOutcome` return type. 6 new tests added across
  `tests/domain/test_ranking.py`, `tests/application/test_search_code.py`,
  `tests/adapters/test_formatting.py`. Full suite: 79/79 passing, no
  regressions.
- **Deterministic check** (`crm search --project <id> "<term>"`, no LLM
  cost): against `mf-core-platform`, a nonsense query ("xyzqwertunicornflavor
  nonexistent term zzzz") returns the `⚠` notice with exactly 3 candidates,
  all below the 0.35 cosine threshold and no lexical hits; a real symbol
  query ("isCorrectCreateCategoryInput") returns the notice-free, full
  top-5 list with `match_reason=hybrid` on the top result — confirming the
  low-confidence path only fires when both channels genuinely fail.

## Out of scope

- Any change to `get_source` / `get_dependency_chain` / `list_chunks`.
- A configurable threshold (CLI flag / config) — not requested; hardcode the
  starting values and revisit only if real usage shows they need tuning.

## Files likely touched

- `src/coderagmanager/application/search_code.py`
- `src/coderagmanager/domain/ranking.py` (or a small addition alongside it to
  expose pre-normalization best scores)
- `src/coderagmanager/adapters/formatting.py` (low-confidence notice format)
- `tests/application/`, `tests/domain/`
