# US-04 — Shared tokenizer (split + stemming + synonyms)

**Tier:** Nivel 1 · **Depends on:** —
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §6.1`, §2.3, §12 point 3

## Story

As a future consumer of both the ad-hoc multi-field scorer (US-05) and real
BM25 (US-11), I want a single, dependency-free tokenizer shared by both, so
that query terms and indexed terms are normalized identically everywhere and
this work is done exactly once.

## Context

Ported in spirit (not literally) from `code-rag-mcp`'s `Tokenizer.java`. Its
camelCase/snake_case splitting and conservative English stemmer are generic
and reusable; its synonym table is **not** — it is one project's business
vocabulary (inventory-management terms) and would not generalize across
`crm`'s multi-project, multi-domain use case. See design doc §6.1 for the
full reasoning.

## Where and when this runs

Two distinct moments, not one — consumers (US-05, US-11) must respect both:

1. **Query side, on every single call.** `expand_query()` runs once per
   `search_code`/`crm search` invocation, on the incoming query text only.
   Cheap (one short string per call).
2. **Chunk side, once per index build / process startup — never per query.**
   `tokenize()` (no synonym expansion, see below) runs once over each
   chunk's `symbol`/`file_path`/`source_text` when the index is built or the
   MCP server/CLI process starts, and the resulting token sets are cached in
   memory alongside the chunk data. For BM25 (US-11) this is mandatory
   (IDF needs corpus-wide term statistics before anything can be scored);
   for the simpler scorer (US-05) it isn't strictly required but avoids
   re-tokenizing every chunk's `source_text` on every single query. **Not
   persisted as a new artifact on disk** — same "rebuildable cache"
   philosophy as the rest of `.crm/`: it's a cheap, deterministic derivation
   from data (`source_text` etc.) that's already persisted.

**Deliberate asymmetry: synonym expansion applies only to the query side,
never to the chunk side** (`tokenize()` is called on both, `expand_query()`
only on the query). Reason: if synonyms were baked into each chunk's cached
tokens, adding a new project-specific `extra_synonyms` entry to
`~/.crm/projects.yaml` would require a full reindex before it had any
effect. Expanding only the query means a new synonym takes effect on the
**next search**, with no reindex needed.

## Acceptance criteria

- [ ] New pure module `src/coderagmanager/domain/tokenizer.py`, no new
      dependency (no NLTK or similar).
- [ ] `tokenize(text: str) -> set[str]`: splits camelCase (`ProductBarcodeType`
      → `product`, `barcode`, `type`), snake_case, and kebab-case; lowercases;
      drops tokens shorter than 2 chars and stopwords (reuse a small
      EN+ES stopword list, same idea as `code-rag-mcp`'s).
- [ ] Conservative stemmer (`stem(token) -> str`): plural `-s` (len > 3,
      excluding `-ss`/`-us`/`-is` endings), `-ies` → `-y` (len > 4), gerund
      `-ing` stripped (len > 5) — ported near-literally from
      `code-rag-mcp`'s `Tokenizer.stem()`.
- [ ] Additional light Spanish plural rule: strip trailing `-es`/`-s` on
      words longer than 4 characters.
- [ ] Generic, domain-agnostic synonym base (always active), exactly this
      starting set: `create↔add,new,insert` · `remove↔delete` ·
      `update↔edit,modify` · `get↔fetch,retrieve` · `list↔search,query,find` ·
      `endpoint↔api,route,handler` · `config↔configuration,settings` ·
      `error↔exception,failure` · `validate↔check,verify`.
- [ ] `expand_query(query: str, extra_synonyms: dict[str, list[str]] | None = None) -> set[str]`:
      tokenizes and expands with the base synonyms plus any project-specific
      `extra_synonyms` passed in (see US-15 sibling concern: the field itself
      is `Project.extra_synonyms`, read and passed in by the caller —
      `domain/tokenizer.py` stays a pure function, no registry access).
- [ ] Unit tests covering: camelCase split, stemming edge cases, base synonym
      expansion, and extra-synonym injection.

## Out of scope

- Reading `~/.crm/projects.yaml` from this module — that's the caller's job
  (keeps this module free of I/O, matching `domain/` conventions).
- Any business-domain synonym pairs (e.g. `inventario↔stock`) — those belong
  only in a specific project's `extra_synonyms`, never in the shared base.

## Files likely touched

- `src/coderagmanager/domain/tokenizer.py` (new)
- `tests/domain/test_tokenizer.py` (new)
