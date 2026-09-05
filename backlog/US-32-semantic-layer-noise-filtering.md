# US-32 — Layer 3 quality: exclude non-code chunks and abstain below confidence

**Tier:** Nivel 1 · **Depends on:** US-08
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §6.3` (Capa 3), §12 point 5

## Story

As an agent relying on `role`/`role_confidence` to understand a project's
architecture, I want the semantic layer (US-08) to leave `role=None` on
chunks it has no business classifying — non-code text and low-confidence
guesses — instead of always forcing one of the 7 categories, so that a
`role` value is a signal worth trusting rather than noise indistinguishable
from a real classification.

## Context

Verifying US-08 end-to-end against a real project (`mf-core-platform`, a
plain React/TS frontend with no recognizable folder convention and no Spring
annotations — exactly the kind of project this layer exists for) surfaced a
real quality problem: the layer classifies **every** chunk that layers 1/2
leave unclassified, with no eligibility check and no use of the confidence
signal it already computes.

Two concrete failure modes observed on real data:

- `pnpm-lock.yaml` (not code — a dependency lockfile) gets chunked into
  arbitrary ~60-line windows by the generic-text fallback parser
  (`adapters/parsers/generic_text.py::GenericTextParser`, `language="text"`,
  `kind="block"`), and each window still gets forced into one of the 7
  categories — e.g. `role="controller"` with a margin of `0.0002`, pure
  noise.
- Test-kind chunks (`kind="test"`, already detected by US-06's path
  convention) get a semantic role too, even though US-06's own design note
  already says test "doesn't need a fuzzy classifier at all" — nothing
  currently connects that signal to layer 3.

On top of that, `SEMANTIC_LOW_CONFIDENCE_MARGIN = 0.05`
(`domain/classification.py`, introduced by US-08) is defined but never
read anywhere — it documents a threshold without enforcing it. A chunk with
a margin of `0.03` (a near-tie between two prototypes) is persisted with the
same shape as one with a margin of `0.3` (a clear winner); nothing
downstream can tell them apart without recomputing similarities itself.

This matters most because **US-09** (`--role`/`--layer` filters, pending)
will expose these values directly to users. Shipping US-09 on top of
today's US-08 behavior means a `--role controller` filter would mix real
controllers with lockfile fragments and stray `catch` blocks, indistinguishable
from each other. This story should land before or together with US-09.

No existing story covers this — checked against the full backlog:
- **US-09** only wires already-produced `role`/`layer` into filters, or an
  all-or-nothing per-project kill switch; its own "Out of scope" excludes
  touching the classification logic.
- **US-20** (`.crm.yaml` include/exclude) excludes whole files from indexing
  entirely, manually, per project — no default for lockfiles, and it never
  looks at what happens to a chunk after it's already indexed.
- **US-30** (`CompositeLanguageParser` fallback) goes the other way: it
  makes the generic-text fallback fire *more* often, not less.
- **US-02**'s `is_low_confidence()` (`domain/ranking.py`) is the closest
  design precedent — a threshold over an already-computed confidence signal
  — but it exists only for search results, not for `role_confidence`.

## Acceptance criteria

- [ ] `domain/classification.py::is_eligible_for_semantic_role(chunk: CodeChunk) -> bool`:
      returns `False` when `chunk.kind == "test"` or `chunk.language == "text"`
      (the generic-text fallback's chunks are arbitrary line windows, not a
      real architectural unit, regardless of the underlying file type — this
      generalizes to any non-code file without hardcoding extensions), `True`
      otherwise.
- [ ] `domain/classification.py::classify_role_semantic(chunk_embedding, prototype_embeddings) -> tuple[str, float] | None`:
      wraps `nearest_role_prototype` (US-08, left unmodified) and returns
      `None` when the margin is below `SEMANTIC_LOW_CONFIDENCE_MARGIN`,
      otherwise returns its `(role, margin)` result unchanged. This is the
      first thing to actually read that constant.
- [ ] `application/index_project.py`: layer 3 only calls
      `classify_role_semantic` for chunks where `role is None` **and**
      `is_eligible_for_semantic_role(chunk)` is `True`. When
      `classify_role_semantic` returns `None` (ineligible, or low-confidence
      abstention), the chunk's `role`/`role_confidence` stay `None` — no
      third state, same shape as a chunk layers 1/2 already handled.
- [ ] Unit tests (`tests/domain/test_classification.py`): `is_eligible_for_semantic_role`
      is `False` for `kind="test"` and for `language="text"`, `True`
      otherwise; `classify_role_semantic` returns `None` below the margin
      threshold and the underlying `nearest_role_prototype` result at or
      above it.
- [ ] Integration tests (`tests/application/test_index_project.py`, `FakeEmbedder`):
      a test-kind chunk and a `language="text"` chunk both end `execute()`
      with `role=None`, even though before this story they would have
      received a semantic role.
- [ ] Verified end-to-end against a real project with no recognizable
      convention (e.g. `mf-core-platform`, already used for US-08's own
      verification): after reindexing, lockfile-derived and test-kind chunks
      no longer carry a role, and the overall distribution of assigned roles
      no longer includes near-zero-margin guesses.

## Out of scope

- Excluding whole files from indexing — that's US-20, and stays manual/
  per-project; this story only changes what happens to chunks that are
  already indexed and parsed.
- Retuning the exact `0.05` value — still the calibration follow-up from
  §12 point 5. This story makes the existing constant load-bearing; it does
  not change its value.
- New prototype categories or embedding-model changes.
- `--role`/`--layer` CLI/MCP filters (US-09) — unaffected and independent,
  though implementing this story first (or alongside) avoids exposing noisy
  `role` values through those filters on day one.

## Files likely touched

- `src/coderagmanager/domain/classification.py`
- `src/coderagmanager/application/index_project.py`
- `tests/domain/test_classification.py`
- `tests/application/test_index_project.py`
