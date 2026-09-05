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

- [x] New pure module `src/coderagmanager/domain/tokenizer.py`. **Amended
      after initial implementation:** the AC's "no new dependency (no NLTK
      or similar)" was revisited as a deliberate, evaluated follow-up — see
      "Stemmer library swap" below. It still holds in spirit (no NLTK, no
      spaCy, no heavy NLP/ML dependency); `snowballstemmer` was added
      instead, a tiny pure-Python package with no models/corpora.
- [x] `tokenize(text: str) -> set[str]`: splits camelCase (`ProductBarcodeType`
      → `product`, `barcode`, `type`), snake_case, and kebab-case; lowercases;
      drops tokens shorter than 2 chars and stopwords (reuse a small
      EN+ES stopword list, same idea as `code-rag-mcp`'s). Unchanged by the
      stemmer swap below — the split regex itself was never in question.
- [x] Conservative stemmer (`stem(token) -> str`). **Superseded by a
      follow-up improvement, not left as originally implemented.** The
      first pass ported `Tokenizer.stem()`'s 3-rule cascade near-literally
      (plural `-s`, `-ies`→`-y`, gerund `-ing`) plus a light Spanish
      plural rule, with the `-es` (2-char) branch deliberately *not*
      prioritized to avoid breaking English `type`/`types`-style pairs (full
      original reasoning kept below for context). That hand-rolled stemmer
      was then replaced with **`snowballstemmer`** (the official Snowball
      project — real linguistic algorithms for English and Spanish, not
      hand-guessed suffix rules), after explicitly comparing both on 28
      concrete cases before adopting it (not assumed to be strictly better):
      - **Fixed:** `papel`/`papeles` now share a stem (`papel`/`papel`) —
        this was the documented limitation of the hand-rolled version.
      - **New trade-off, accepted and tested:** short accented Spanish words
        like `año`/`años` no longer unify (`año`/`años`, Snowball's Spanish
        algorithm doesn't act below a certain word length) — the hand-rolled
        rule used to get this one right. Net assessment: not a strict
        improvement on Spanish specifically, but a real one overall — ties
        or improves on every English case tested (the dominant language in
        this corpus), and replaces 3 guessed lines with a maintained,
        real algorithm. See `stem()`'s docstring for the full comparison.
      - Language selection is a simple heuristic: a token containing any
        Spanish accented vowel or `ñ` goes through the Spanish Snowball
        stemmer; everything else through the English one.
      - Original reasoning kept for context (no longer the active
        implementation): giving `-es` priority over plain `-s` is
        structurally indistinguishable from, and would break, the extremely
        common English "consonant + silent e + s" pattern (`type`/`types`,
        `create`/`creates`, `role`/`roles`...); the dominant Spanish plural
        pattern (vowel + `s`: `producto`/`productos`) was already covered by
        the plain `-s` rule with zero extra code.
- [x] Generic, domain-agnostic synonym base (always active), exactly this
      starting set: `create↔add,new,insert` · `remove↔delete` ·
      `update↔edit,modify` · `get↔fetch,retrieve` · `list↔search,query,find` ·
      `endpoint↔api,route,handler` · `config↔configuration,settings` ·
      `error↔exception,failure` · `validate↔check,verify`.
- [x] `expand_query(query: str, extra_synonyms: dict[str, list[str]] | None = None) -> set[str]`:
      tokenizes and expands with the base synonyms plus any project-specific
      `extra_synonyms` passed in (see US-15 sibling concern: the field itself
      is `Project.extra_synonyms`, read and passed in by the caller —
      `domain/tokenizer.py` stays a pure function, no registry access).
      **Note:** `Project.extra_synonyms` does not exist yet in
      `domain/models.py`/`YamlProjectRegistry` in this backlog — no story
      currently adds it (US-15 is about the unrelated `group` field). Not a
      blocker: `expand_query` already accepts the parameter with the right
      shape for whenever that field lands.
- [x] Unit tests covering: camelCase split, stemming edge cases, base synonym
      expansion, and extra-synonym injection. Also added (found while
      validating against a real, already-indexed project — see below): a
      regression test for accented Spanish words (`código`, `año`,
      `validación`, `dónde`), which a naive ASCII-only `[^A-Za-z0-9]+` split
      (the literal regex in `code-rag-mcp`'s `Tokenizer.java`) mangled
      (`código` → `digo`, `año` → empty set).

**Verification beyond unit tests:** run against the real, already-indexed
`mic-inventory` project (2730 real chunks) — zero exceptions tokenizing the
full corpus, and real symbols like `getProductBarcodeTypes` tokenize exactly
as the AC's worked example implies. Real Spanish benchmark queries
(`benchmarks/bank/mic-inventory.yaml`) confirmed the accent fix (no more
`nde`/`mo`/`digo`-style garbage tokens) — and also confirmed, as expected and
scoped in the story's own context, that raw lexical token-overlap alone
still cannot bridge a Spanish query to English-only identifiers (e.g.
"producto" → `ProductsControllerApi`): that gap is intentionally left to the
semantic/embedding channel, not this tokenizer (no ES↔EN translation pairs
in the base synonym table — see "Out of scope").

## Out of scope

- Reading `~/.crm/projects.yaml` from this module — that's the caller's job
  (keeps this module free of I/O, matching `domain/` conventions).
- Any business-domain synonym pairs (e.g. `inventario↔stock`) — those belong
  only in a specific project's `extra_synonyms`, never in the shared base.

## Files likely touched

- `src/coderagmanager/domain/tokenizer.py` (new)
- `tests/domain/test_tokenizer.py` (new)
- `pyproject.toml` (added later, follow-up: `snowballstemmer` dependency for
  the stemmer swap described above)
