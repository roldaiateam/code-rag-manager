# US-12 — Additional embedding provider (Voyage AI)

**Tier:** Nivel 2 · **Depends on:** —
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §7.2`, `docs_en/06-embeddings-vector-store.md §1`

## Story

As a user who wants higher-quality semantic search and is fine with a paid
API, I want to switch `crm`'s embedding provider to Voyage AI, so that I get
better conceptual-query recall without `crm` changing its architecture.

## Context

Lowest-risk story in this whole backlog: the `EmbeddingProvider` port
already exists, and `docs_en/06-embeddings-vector-store.md` already contains
a working sketch of `VoyageEmbeddingProvider`. Because `crm` always does a
full drop-and-rebuild index (never incremental — see design doc §8/§9),
switching providers never requires a vector-dimension migration: just
re-run `crm index`.

## Acceptance criteria

- [ ] `adapters/embeddings/voyage_provider.py`: `VoyageEmbeddingProvider`
      implementing `EmbeddingProvider` (`embed_batch`, `dimensions`), per the
      sketch in `docs_en/06`.
- [ ] API key read from `VOYAGE_API_KEY` environment variable at runtime —
      **never** stored in `~/.crm/projects.yaml` or anywhere in the registry.
- [ ] `crm config set embedding.provider voyage` (and per-project override in
      the registry, as already documented in `docs_en/04`) selects this
      adapter in `composition_root.py`. **Default stays `local`** — this
      story never changes the default; Voyage is strictly opt-in, both
      globally and per project.
- [ ] **Fail fast and clearly when the key is missing.** The provider
      factory in `composition_root.py` (the single place that builds
      whichever `EmbeddingProvider` is configured) checks for
      `VOYAGE_API_KEY` when `embedding.provider == "voyage"` and, if absent,
      raises before any HTTP call is attempted — never a raw
      `voyageai`/network exception. Message, surfaced via the CLI's existing
      `_fail()` pattern (same as other `ValueError` handling in
      `adapters/cli/main.py`): *"The 'voyage' embedding provider requires the
      VOYAGE_API_KEY environment variable. Export it and retry, or run `crm
      config set embedding.provider local` to use the free local model
      instead."* Triggers on any command that actually embeds text
      (`crm index`, `crm search`, `crm mcp serve`) — centralized in the
      factory, not duplicated per command.
- [ ] `crm config show` surfaces, for the active embedding provider, whether
      its required environment variable is present — e.g.
      `embedding.provider: voyage (⚠ VOYAGE_API_KEY not set)` — so the gap is
      visible on inspection, not only when a command fails.
- [ ] Switching **back** to `local` (`crm config set embedding.provider
      local`) works symmetrically, and the docs/README note explicitly that
      it requires the same full `crm index` re-run as switching to Voyage
      did — the vector dimension changes in both directions (1024 → 384),
      not just one.
- [ ] `pyproject.toml`: `voyageai` added as an **optional** dependency (extra
      group, e.g. `crm[voyage]`), not a hard default dependency — keeps the
      zero-cost local default (`sentence-transformers`) install-light.
- [ ] README/docs updated with the config switch, the env var requirement,
      the default value, and the fail-fast error behavior.
- [ ] Integration test (skipped/mocked if no API key present in CI)
      confirming `embed_batch` returns vectors of the documented dimension.
- [ ] Unit test: building the provider with `embedding.provider == "voyage"`
      and no `VOYAGE_API_KEY` set raises the clear error above, not a
      network/library exception.

## Out of scope

- Qwen3-Embedding or any other provider — separate story if/when needed,
  same pattern.
- Automatic re-indexing on provider change — user re-runs `crm index`
  manually, consistent with the "always full" indexing model.

## Files likely touched

- `src/coderagmanager/adapters/embeddings/voyage_provider.py` (new)
- `src/coderagmanager/composition_root.py`
- `pyproject.toml`
- `README.md`, `docs_en/06-embeddings-vector-store.md` (mark as implemented)
- `tests/adapters/test_voyage_provider.py` (new)
