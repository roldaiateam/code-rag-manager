# US-34 — Classification layer 2: `react-typescript` convention pack

**Tier:** Nivel 1 · **Depends on:** US-33
**Design reference:** none in `PLAN-MEJORA-CODE-RAG-MANAGER.md` — raised
during US-08's end-to-end verification against `mf-core-platform` (a real
React/TS frontend already in the benchmark bank), where every chunk fell
through to Layer 3's semantic guess for lack of any deterministic pack, the
same gap `spring-java` (US-07) closed for Java/Spring.

## Story

As an agent working in a React/TypeScript frontend, I want its common folder
conventions (`hooks/`, `pages/`, `components/`, `adapters/`or `services/`,
`models/`, `store/`or `state/`, `utils/`or `helpers/`) to produce a
deterministic structural role, the same way Spring annotations already do
for Java, so that a whole frontend doesn't rely entirely on Layer 3's
best-effort semantic guess just because it isn't Java.

## Context

`mf-core-platform` (real project, already registered and indexed for
benchmarking) has none of Layer 1's hexagonal path vocabulary and no Spring
annotations, so under today's US-08/US-32 behavior every chunk either gets a
Layer 3 semantic guess or abstains — even for files whose folder already
makes their role obvious to a human (`src/adapters/api/productsApi.ts`,
`src/utils/format/currency.ts`, `src/pages/Products/...`). This story adds
the missing Layer 2 pack using the generic engine from US-33 — pure data, no
new pipeline code.

`CodeChunk.language` only has four values today (`"python" | "javascript" |
"java" | "text"`, `domain/models.py`) — `TreeSitterJavaScriptParser` tags
both `.js` and `.ts`/`.tsx` chunks as `"javascript"`, so a single
`language == "javascript"` activation condition covers both.

## Acceptance criteria

- [ ] `domain/classification.py::REACT_TYPESCRIPT_PACK`, appended to
      `CLASSIFICATION_PACKS` after `SPRING_JAVA_PACK`, built with the US-33
      engine:
      ```python
      REACT_TYPESCRIPT_PACK = {
          "name": "react-typescript",
          "activates_when": {"language": "javascript"},
          "rules": [
              {"when": {"path_segment": "hooks", "symbol_prefix": "use"}, "role": "hook"},
              {"when": {"path_segment": "pages"}, "role": "page"},
              {"when": {"path_segment": "components"}, "role": "component"},
              {"when": {"path_segment_in": ["adapters", "services"]}, "role": "adapter"},
              {"when": {"path_segment": "models"}, "role": "entity"},
              {"when": {"path_segment_in": ["store", "state"]}, "role": "state"},
              {"when": {"path_segment_in": ["utils", "helpers"]}, "role": "utility"},
          ],
      }
      ```
      Rule order matters: `hooks` (more specific, requires both a path
      segment and a symbol prefix) is checked before the broader, path-only
      rules, so a helper function that happens to live under `hooks/` but
      isn't itself a `useXxx` hook falls through to a later/no rule instead
      of being misclassified.
- [ ] `role` values reuse existing vocabulary where the concept already
      exists (`adapter`, `entity`, `utility` — matching Layer 3's own
      prototype names, US-08) and introduce new ones only where nothing
      already fits (`hook`, `page`, `component`, `state`) — `role` is a free
      `str | None` field, no closed enum anywhere enforces this, but reusing
      names keeps a project's `role` vocabulary consistent regardless of
      which layer produced it.
- [ ] Unit tests (`tests/domain/test_classification.py`, hand-built
      `CodeChunk`s, no real parsing needed): one per rule, plus a rule-order
      test for the `hooks` case (a chunk under `hooks/` whose symbol does
      **not** start with `use` gets no role from this pack).
- [ ] Verified end-to-end against the real `mf-core-platform` project (same
      discipline as US-07/US-08): reindex and confirm chunks under the
      folders above get a deterministic role with `role_confidence is None`
      (never a Layer 3 margin) — spot-check `src/adapters/api/productsApi.ts`
      → `adapter`, `src/models/category.ts` → `entity`,
      `src/utils/format/currency.ts` → `utility`, a file under
      `src/pages/Products/` → `page`, a file under `src/components/Header/`
      → `component`. Also confirm this measurably shrinks how much Layer 3
      has to guess on that project (fewer chunks reach `nearest_role_prototype`
      than before this story).

## Out of scope

- Any Vue/Angular/Svelte pack.
- JSX-aware refinements to the `components` rule (e.g. requiring an actual
  JSX return) — starting path-only, same cheap/structural spirit as
  `spring-java`'s own activation check; revisit only if path alone proves
  too coarse on more real projects.
- Any Python framework pack — no real Python project in the benchmark bank
  yet to calibrate against (same reasoning that kept `spring-java` the only
  pack at US-07's launch, §12 point 4).

## Files likely touched

- `src/coderagmanager/domain/classification.py`
- `tests/domain/test_classification.py`
- `tests/application/test_index_project.py`
