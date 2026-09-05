# US-05 — Multi-field lexical scoring

**Tier:** Nivel 1 · **Depends on:** US-04
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §6.1`, §6.4

## Story

As an agent calling `search_code`, I want a chunk's methods, calls, and
(once classified) role/layer to also count toward its lexical score — not
just its name and path — so that natural-language and multi-word queries
recall the right chunk even when no single field matches on its own.

## Context

Adapted from `code-rag-mcp`'s `CodeSearcher.score()` (12 weighted signals).
`crm`'s `CodeChunk` is flatter than `code-rag-mcp`'s (no dedicated
`MethodSig`/`FieldSig` lists), so this story only wires the signals that
already exist or are introduced by sibling stories — it does not invent new
chunk structure.

## Acceptance criteria

- [x] New pure module `src/coderagmanager/domain/lexical_scoring.py`,
      separated from the storage adapter — same separation already used for
      `merge_and_rerank` vs. `VectorStore`/`LexicalIndex`.
- [x] Scoring uses `domain/tokenizer.py::expand_query()` (US-04) instead of
      raw substring splitting, so token-level (not just substring) matches
      count. Per US-04's "where and when": `expand_query()` runs once per
      query call; each chunk's `symbol`/`file_path`/`source_text` is
      tokenized via `tokenize()` **once, when the index is built/reloaded**,
      and the resulting token sets are cached in memory alongside the
      chunk — not re-tokenized on every search.
- [x] Signals scored, each via token-set overlap (not raw substring):
      `symbol` (highest weight, keep parity with US-01's 2.0/1.0/0.5 scale),
      `file_path`, `source_text`, plus **when available**: `role`/`layer`
      (once US-06/07/08 land — a chunk with `role=None` simply contributes
      nothing extra, no error).
- [x] `calls` are read from the graph (`DependencyEdge` with
      `edge_type=CALLS` originating at the chunk), **not** duplicated as a
      new list on `CodeChunk` — reuse what already exists.
- [x] `SubstringLexicalIndex` (or its successor) calls into this module
      instead of doing ad-hoc scoring inline.
- [x] Unit tests: a multi-word natural-language query (e.g. "email
      validation") matches a differently-named function via token overlap,
      without requiring a literal substring match.

## Verification notes (2026-09-05)

- **Code + tests**: `domain/lexical_scoring.py` (new: `ChunkTokens`,
  `tokenize_chunk()`, `score_chunk()`, `rank()`). `GraphStore` gained a raw
  `edges(project_id)` accessor (mirrors the existing `nodes()`), implemented
  in `JsonGraphStore` and `FakeGraphStore`; `dependency_chain()` now reuses
  it instead of duplicating the deserialization loop.
  `adapters/storage/substring_lexical_index.py` was rewritten as
  `MultiFieldLexicalIndex` (same file, renamed class — it no longer scores
  by substring): caches `ChunkTokens` per project, rebuilt eagerly on
  `index()` (called from `IndexProject.execute()`, previously a no-op) and
  lazily on first `search()` if a process never called `index()` (e.g. a
  bare `crm search` after a previous `crm index` run). Weights used:
  `symbol=2.0`, `file_path=1.0`, `source_text=0.5` (unchanged, parity with
  US-01), `calls=0.5`, `role=1.0`, `layer=1.0` (new, no AC fixed these
  three — documented and agreed during planning). `role`/`layer` are read
  via `getattr(chunk, "role", None)` in the adapter (the fields don't exist
  on `CodeChunk` yet — that's US-06) and passed into `tokenize_chunk()` as
  plain `str | None` parameters, so the domain module has no knowledge of
  that temporary gap. New/updated tests: `tests/domain/test_lexical_scoring.py`
  (new, 6 tests), `tests/adapters/test_multi_field_lexical_index.py`
  (renamed from `test_substring_lexical_index.py`, all previous US-01 tests
  kept green plus 4 new ones: token-overlap-without-substring, synonym
  expansion, calls-signal-from-graph, cache rebuild on reindex, lazy build
  on cold start), `tests/adapters/test_json_graph_store.py` (+1 test for
  `edges()`). Full suite: 115/115 passing, no regressions.
- **Deterministic check, with vs. without the fix** (direct calls to the
  lexical index, bypassing the LLM and the CLI's score rounding): on the
  real, already-indexed `mic-clients` project, querying `"validate"` against
  `handleConstraintViolation` (`GlobalExceptionHandler.java`) — a chunk
  whose `symbol`/`file_path` never contain "valid" and whose `source_text`
  only says `"Validation failed."` (not a substring of "validate":
  `v-a-l-i-d-a-t-e` vs. `v-a-l-i-d-a-t-i-o-n` diverge at the 8th
  character). **Before the fix**: `SubstringLexicalIndex.search(..., top_k=50)`
  returns 18 hits, this chunk absent — zero lexical signal, present in
  `search_code` output only via the semantic channel (`score=0.600, semantic`,
  rank #9 of 15, behind several unrelated generated-code setters that
  happen to contain the literal call `validate(...)`). **After the fix**:
  the same direct call returns this chunk with `score=0.5` (matches via
  `source_text`, stemmed `"validate"` ≡ `"validation"` → `"valid"`); in the
  merged `crm search` output it now shows as `match_reason=hybrid` once the
  internal lexical candidate window is wide enough to include it
  (`--top-k 40`; at the CLI's default `--top-k 10` it stays borderline
  `semantic` because the token `"valid"` is extremely common across this
  Bean-Validation-heavy codebase and many other chunks tie at the same
  0.5 floor — the expected, documented limitation of a heuristic,
  non-IDF-weighted scorer, explicitly deferred to US-11/BM25).
- **Regression check**: re-ran US-01's own verification case
  (`crm search "playwright" --project mf-core-platform`) — `README.md:51-110`
  still lands at rank #3, `score=0.600, hybrid`, identical to the value
  recorded in US-01's verification notes. No change in relative
  symbol/file_path/source_text ordering for existing cases.
- **Net**: the fix is verified correct at the index/scoring level
  (deterministic, reproducible evidence above, both "found nothing" →
  "found via the new signal" and "no regression on the prior fix"). No
  agentic/LLM benchmark re-run was performed for this story (not requested;
  the deterministic check above is equivalent in spirit to the evidence
  that actually carried US-01).

## Out of scope

- BM25-style statistical weighting (IDF, length normalization) — that's
  US-11. This story keeps the same "weighted heuristic" style as
  `code-rag-mcp`, just extended to more fields and token-aware.
- Role/layer scoring wiring beyond "use it if present" — the actual
  classification is US-06/07/08.

## Files touched

- `src/coderagmanager/domain/lexical_scoring.py` (new)
- `src/coderagmanager/ports/graph_store.py` (new `edges()` method)
- `src/coderagmanager/adapters/storage/json_graph_store.py` (implements
  `edges()`; `dependency_chain()` now reuses it)
- `src/coderagmanager/adapters/storage/substring_lexical_index.py`
  (rewritten as `MultiFieldLexicalIndex`, same file)
- `src/coderagmanager/composition_root.py` (wires `graph_store` into the
  lexical index)
- `tests/domain/test_lexical_scoring.py` (new)
- `tests/adapters/test_multi_field_lexical_index.py` (renamed from
  `test_substring_lexical_index.py`)
- `tests/adapters/test_json_graph_store.py` (`edges()` test)
- `tests/application/fakes.py` (`FakeGraphStore.edges()`)
