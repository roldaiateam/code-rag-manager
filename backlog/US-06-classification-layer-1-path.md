# US-06 — Classification layer 1: path vocabulary

**Tier:** Nivel 1 · **Depends on:** —
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §6.3` (Capa 1), §6.4

## Story

As an agent filtering chunks by architectural layer, I want a chunk's
`layer` inferred from common hexagonal/clean-architecture path vocabulary —
without `crm` knowing anything about the project's language or framework —
so that projects following a recognizable folder convention get this signal
for free, and projects that don't simply get `layer=None` instead of a wrong
guess.

## Context

This is the "always-on, framework-agnostic" base classifier — no ports, no
new dependencies, pure string matching, generalizes across languages by
design (unlike `code-rag-mcp`'s `Classifiers.java`, which is hardcoded to one
project's Java/Spring conventions).

## Acceptance criteria

- [ ] New fields on `CodeChunk` (domain, optional, default `None`):
      `layer: str | None`, `role: str | None`, `role_confidence: float | None`.
- [ ] `domain/classification.py::classify_layer_by_path(file_path: str) -> str | None`:
      recognizes segments `domain/`, `application/`, `infrastructure/`,
      `ports/`, `adapters/`, `controllers/`, `services/`, `repositories/`
      (case-insensitive, any position in the path) and maps to a
      corresponding `layer` value; returns `None` if no segment matches —
      never guesses.
- [ ] Also in this story (cheap, path-based, same spirit): `kind="test"`
      detection via path/name convention (`tests/`, `test/`, or filename
      matching `*test*`/`*spec*`) — this was explicitly carved out of the
      semantic classifier (US-08) in the design doc §12 point 5 because it
      doesn't need a fuzzy classifier at all.
- [ ] `application/index_project.py` calls this after parsing, before
      embedding — same pattern as the existing
      `chunks = [replace(c, embedding=e) for c, e in zip(chunks, embeddings)]`
      line, extended to also set `layer`.
- [ ] Unit tests: a path with a recognized segment gets the right `layer`; a
      flat path (e.g. `tests/fixtures/sample_repo/src/pedidos.py`) gets
      `layer=None`.
- [ ] `--no-role-classification` flag (see US-09) also disables this layer,
      not just layers 2/3.

## Out of scope

- Annotation/decorator-based role detection — US-07.
- Semantic fallback — US-08.

## Files likely touched

- `src/coderagmanager/domain/models.py` (new `CodeChunk` fields)
- `src/coderagmanager/domain/classification.py` (new)
- `src/coderagmanager/application/index_project.py`
- `tests/domain/test_classification.py` (new)
