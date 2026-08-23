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

- [ ] New pure module `src/coderagmanager/domain/lexical_scoring.py`,
      separated from the storage adapter — same separation already used for
      `merge_and_rerank` vs. `VectorStore`/`LexicalIndex`.
- [ ] Scoring uses `domain/tokenizer.py::expand_query()` (US-04) instead of
      raw substring splitting, so token-level (not just substring) matches
      count. Per US-04's "where and when": `expand_query()` runs once per
      query call; each chunk's `symbol`/`file_path`/`source_text` is
      tokenized via `tokenize()` **once, when the index is built/reloaded**,
      and the resulting token sets are cached in memory alongside the
      chunk — not re-tokenized on every search.
- [ ] Signals scored, each via token-set overlap (not raw substring):
      `symbol` (highest weight, keep parity with US-01's 2.0/1.0/0.5 scale),
      `file_path`, `source_text`, plus **when available**: `role`/`layer`
      (once US-06/07/08 land — a chunk with `role=None` simply contributes
      nothing extra, no error).
- [ ] `calls` are read from the graph (`DependencyEdge` with
      `edge_type=CALLS` originating at the chunk), **not** duplicated as a
      new list on `CodeChunk` — reuse what already exists.
- [ ] `SubstringLexicalIndex` (or its successor) calls into this module
      instead of doing ad-hoc scoring inline.
- [ ] Unit tests: a multi-word natural-language query (e.g. "email
      validation") matches a differently-named function via token overlap,
      without requiring a literal substring match.

## Out of scope

- BM25-style statistical weighting (IDF, length normalization) — that's
  US-11. This story keeps the same "weighted heuristic" style as
  `code-rag-mcp`, just extended to more fields and token-aware.
- Role/layer scoring wiring beyond "use it if present" — the actual
  classification is US-06/07/08.

## Files likely touched

- `src/coderagmanager/domain/lexical_scoring.py` (new)
- `src/coderagmanager/adapters/storage/substring_lexical_index.py`
- `tests/domain/test_lexical_scoring.py` (new)
