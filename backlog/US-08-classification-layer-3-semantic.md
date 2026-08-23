# US-08 — Classification layer 3: semantic prototypes

**Tier:** Nivel 1 · **Depends on:** US-06, US-07 (runs only when both return `None`)
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §6.3` (Capa 3), §12 point 5

## Story

As an agent working in a project with no recognizable folder or framework
convention (e.g. a plain JS/React frontend), I want chunks to still get a
best-effort role classification from what they semantically resemble, so
that role filtering isn't limited to Java/Spring-shaped projects only.

## Context

This is the layer `code-rag-mcp` structurally cannot have (no embeddings).
It reuses the **existing** `EmbeddingProvider` port — no new port. Combination
rule: layers 1 (US-06) and 2 (US-07) run first; this layer only assigns a
role when both returned `None`.

## Acceptance criteria

- [ ] Fixed set of 7 English prototype phrases (embedded once, cached):
  - `entity` — "a domain entity or data model representing a core business concept, without external I/O"
  - `controller` — "a handler that receives an external request (HTTP, CLI, or event) and delegates it to application logic"
  - `adapter` — "an adapter that reads or writes to an external system such as a database, message queue, or API"
  - `use_case` — "an application service that orchestrates business logic by coordinating several components"
  - `mapper` — "a converter that transforms data between two representations, such as a DTO and a domain object"
  - `config` — "configuration or setup code that wires dependencies, with no business logic"
  - `utility` — "a generic helper function with no specific architectural role"
- [ ] `domain/classification.py::nearest_role_prototype(chunk_embedding, prototype_embeddings) -> tuple[str, float]`:
      pure cosine-similarity argmax over the 7 prototypes (always assigns one
      — closed set, no "none" option at this stage).
- [ ] Confidence is the **margin** between the top-1 and top-2 cosine
      similarities (not an absolute cosine cutoff — see design doc for why
      an absolute threshold is unreliable for code-vs-text comparisons).
- [ ] Starting low-confidence margin: `< 0.05` — flagged in code with a
      comment pointing to `PLAN-MEJORA-CODE-RAG-MANAGER.md §12 point 5` as
      "value to calibrate against the 3 real benchmark projects once this
      lands."
- [ ] Prototype embeddings are computed once via the existing
      `EmbeddingProvider.embed_batch()`, at composition-root/startup time,
      not per chunk.
- [ ] Unit tests with a fake `EmbeddingProvider` (deterministic fixed
      vectors) proving argmax selection and margin computation — no real
      model needed for the domain-level test.

## Out of scope

- Adding more than 7 categories, or tuning the exact margin threshold beyond
  the starting value — explicitly left as a follow-up calibration task, not
  part of this story's definition of done.

## Files likely touched

- `src/coderagmanager/domain/classification.py`
- `src/coderagmanager/composition_root.py` (prototype embedding wiring)
- `tests/domain/test_classification.py`
