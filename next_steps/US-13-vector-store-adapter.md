# US-13 — Additional vector store adapter

**Tier:** Nivel 2 · **Depends on:** —
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §7.2`, `docs_en/06-embeddings-vector-store.md §2`

## Story

As a user with different operational constraints than the default (e.g.
already running Chroma or Qdrant elsewhere), I want to plug in an
alternative vector store, so that `crm` doesn't force LanceDB as the only
option when the port already supports swapping it.

## Context

Same risk profile as US-12: the `VectorStore` port already exists
(`drop`, `upsert`, `search`), and `docs_en/06` already discusses ChromaDB and
Qdrant as documented alternatives with clear trade-offs. Pick **one** to
implement first (ChromaDB recommended — simplest API, embedded mode
available, matches `crm`'s "no server process to manage" default) unless a
concrete need points to Qdrant instead.

## Acceptance criteria

- [ ] `adapters/storage/chroma_vector_store.py`: `ChromaVectorStore`
      implementing `VectorStore` (`drop`, `upsert`, `search`), one collection
      per `project_id` — same isolation pattern as `LanceDbVectorStore`'s
      one-table-per-project.
- [ ] `crm config set vector_store.provider chroma` selects this adapter in
      `composition_root.py`.
- [ ] `chromadb` added as an optional dependency (extra group), not a hard
      default — same reasoning as US-12.
- [ ] README/docs updated with the config switch.
- [ ] Integration test against a real (embedded-mode) Chroma instance,
      mirroring the existing `LanceDbVectorStore` test structure.

## Out of scope

- Qdrant adapter — separate story, same pattern, only if a concrete need
  arises (design doc explicitly deprioritizes trying to cover every option
  up front).
- Any change to `EmbeddingProvider` or the domain model.

## Files likely touched

- `src/coderagmanager/adapters/storage/chroma_vector_store.py` (new)
- `src/coderagmanager/composition_root.py`
- `pyproject.toml`
- `README.md`, `docs_en/06-embeddings-vector-store.md` (mark as implemented)
- `tests/adapters/test_chroma_vector_store.py` (new)
