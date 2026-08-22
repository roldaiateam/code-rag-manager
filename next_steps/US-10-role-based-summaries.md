# US-10 — Role-based chunk summaries

**Tier:** Nivel 1, second wave (lower priority — does not block Nivel 2/3)
**Depends on:** US-06, US-07, US-08
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §6.1`

## Story

As an agent reading search results, I want a chunk's summary text to reflect
what kind of thing it is (entity vs. controller vs. use-case...), so that I
get a denser, more useful preview without always needing a follow-up
`get_source` call.

## Context

Adapted from `code-rag-mcp`'s `SummaryGenerator.java`, which produces a
different summary shape per `role` (e.g. a `use-case` summary lists its
method signatures and the ports it depends on; an `entity` summary lists its
fields). This is explicitly the most expensive item of Nivel 1 to port
faithfully — `code-rag-mcp`'s model has dedicated `MethodSig`/`FieldSig`
structures that `crm`'s flatter `CodeChunk` doesn't. Scope this story to what
today's chunk data actually supports; don't block on adding new structured
fields to `CodeChunk` beyond what's already planned in sibling stories.

## Acceptance criteria

- [ ] New pure module `domain/summary.py::generate_summary(chunk) -> str`,
      dispatching on `chunk.role` (falls back to a generic summary when
      `role is None`).
- [ ] At minimum, distinct summary shapes for: `entity`, `controller`,
      `use-case`, `adapter`, `repository`, `mapper`, generic fallback —
      mirroring `code-rag-mcp`'s categories that map cleanly onto what's
      already extractable (US-07's Java metadata, `DependencyEdge` calls).
- [ ] Summary is stored/returned as part of the formatted search result, not
      as a new persisted `CodeChunk` field (avoid re-indexing just to change
      wording — compute on read).
- [ ] Unit tests for each role branch and the fallback.

## Out of scope

- Any new structured extraction beyond what US-06/07/08 already produce
  (e.g. do not add a full `MethodSig` model to `CodeChunk` just for this).

## Files likely touched

- `src/coderagmanager/domain/summary.py` (new)
- `src/coderagmanager/adapters/formatting.py`
- `tests/domain/test_summary.py` (new)
