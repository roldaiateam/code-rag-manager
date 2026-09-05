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

- [x] Fixed set of 7 English prototype phrases (embedded once, cached):
  - `entity` — "a domain entity or data model representing a core business concept, without external I/O"
  - `controller` — "a handler that receives an external request (HTTP, CLI, or event) and delegates it to application logic"
  - `adapter` — "an adapter that reads or writes to an external system such as a database, message queue, or API"
  - `use_case` — "an application service that orchestrates business logic by coordinating several components"
  - `mapper` — "a converter that transforms data between two representations, such as a DTO and a domain object"
  - `config` — "configuration or setup code that wires dependencies, with no business logic"
  - `utility` — "a generic helper function with no specific architectural role"
- [x] `domain/classification.py::nearest_role_prototype(chunk_embedding, prototype_embeddings) -> tuple[str, float]`:
      pure cosine-similarity argmax over the 7 prototypes (always assigns one
      — closed set, no "none" option at this stage).
- [x] Confidence is the **margin** between the top-1 and top-2 cosine
      similarities (not an absolute cosine cutoff — see design doc for why
      an absolute threshold is unreliable for code-vs-text comparisons).
- [x] Starting low-confidence margin: `< 0.05` — flagged in code with a
      comment pointing to `PLAN-MEJORA-CODE-RAG-MANAGER.md §12 point 5` as
      "value to calibrate against the 3 real benchmark projects once this
      lands."
- [x] Prototype embeddings are computed once via the existing
      `EmbeddingProvider.embed_batch()`, at composition-root/startup time,
      not per chunk. **Implemented as once per `IndexProject` instance
      instead** (cached lazily on first `execute()`, in
      `IndexProject._semantic_prototypes()`), not literally inside
      `composition_root.py`: `adapters/embeddings/local_provider.py` loads
      its ~90MB model lazily on purpose ("para no penalizar los comandos de
      CLI que no embeben nada"), and `composition_root.build_use_cases()`
      runs on *every* CLI/MCP command, including ones that never index
      (`crm chunks`, `crm stats`...). Computing the prototype embeddings
      there would force-load the model on those commands too. Doing it
      inside `IndexProject` means the cost is only ever paid when indexing
      actually runs — the same run that already loads the model for the
      real per-chunk embeddings — and the MCP server's long-lived `reindex`
      tool (which reuses one `IndexProject` instance for the life of the
      process, see `adapters/mcp/server.py::build_server`) still only pays
      it once.
- [x] Unit tests with a fake `EmbeddingProvider` (deterministic fixed
      vectors) proving argmax selection and margin computation — no real
      model needed for the domain-level test.

## Out of scope

- Adding more than 7 categories, or tuning the exact margin threshold beyond
  the starting value — explicitly left as a follow-up calibration task, not
  part of this story's definition of done.

## Verification

- Unit tests: `tests/domain/test_classification.py` (argmax, margin, zero
  vector, tie-breaking, closed-set) and `tests/application/test_index_project.py`
  (semantic role assigned only when layers 1/2 return `None`; a role from
  layer 2 is never overridden). `test_java_project_without_spring_annotations_has_no_roles`
  was renamed to `..._falls_back_to_semantic_roles` and its assertion
  updated — its old `role is None` premise is no longer true once this layer
  is always on.
- Manual end-to-end verification against real projects (same approach as
  US-07 — not committed as a test, this repo has no test that loads the real
  embedding model):
  - `tests/fixtures/sample_repo/src/pedidos.py` (the design doc's own anchor
    example): reindexed with the real model. `Pedido`/`PedidoUrgente` get
    `layer=None` (confirmed, as before) and a semantic role — but the
    concrete category (`mapper`/`utility`, margins 0.015/0.067) differs from
    the design doc's informal guess (`entity`, confidence 0.4-0.5). This is
    not a bug: the full 7-way similarity ranking for both chunks sits in a
    narrow 0.0–0.16 cosine band, which is exactly the "code vs. English
    prose lives in a narrow band" behavior §12 point 5 already anticipated
    as the reason to use a margin instead of an absolute cosine cutoff, and
    the reason that margin is flagged as needing calibration rather than
    trusted as-is.
  - `mf-core-platform` (real React/TS project, no hexagonal folders, no
    Spring annotations, registered in `~/.crm/projects.yaml`): **before**
    this story, its existing index (built 2026-09-02) had `role=None` on
    all 263 chunks — confirmed by reading that index as-is, without
    reindexing. **After** reindexing with this story's code, all 263 chunks
    got a role and a confidence (distribution: utility 99, controller 77,
    config 41, use_case 30, mapper 9, adapter 6, entity 1). Spot-checked
    `src/utils/format/currency.ts::formatPrice` → `role=mapper` (margin
    0.082) — a defensible call, since the function's whole job is
    converting a number into a formatted currency string. `.crm/` in that
    repo is git-ignored and reconstructible; no tracked file was touched.

## Files touched

- `src/coderagmanager/domain/classification.py`
- `src/coderagmanager/application/index_project.py` (not in the original
  "files likely touched" list — needed to actually invoke the new layer in
  the pipeline; same kind of gap already noted in US-07's own file)
- `tests/domain/test_classification.py`
- `tests/application/test_index_project.py`, `tests/application/fakes.py`
  (also not originally listed, needed for the integration tests above)
- `src/coderagmanager/composition_root.py` — **deliberately not touched**,
  see the note on the "computed once" criterion above.
