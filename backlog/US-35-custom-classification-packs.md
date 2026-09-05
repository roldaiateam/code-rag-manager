# US-35 — Project-local custom classification packs

**Tier:** Nivel 1 (pack extensibility) · **Depends on:** US-33, US-20
**Design reference:** none in `PLAN-MEJORA-CODE-RAG-MANAGER.md` — raised
alongside US-33/US-34 while designing how a project whose conventions match
neither `spring-java` nor `react-typescript` could get accurate role
classification without forking `crm` or waiting for a maintainer to ship a
new built-in pack.

## Story

As a `crm` user whose project's architecture doesn't match any built-in
pack, I want to declare my own role-classification rules in my project's own
committed config, using the exact same small rule vocabulary the built-in
packs use, so that I get accurate classification for my own conventions
without writing Python or forking `crm`.

## Context

US-33 makes a pack a plain, documented `dict` — the only remaining gap is
loading *extra* packs from outside `crm`'s own source tree. `.crm.yaml`
(US-20) is already meant to be the project's committed, teammate/CI-shared
config surface — a `classification_packs:` key there, using literally the
same schema US-33 documents for built-in packs, avoids inventing a second
config file and keeps custom packs versioned and shared exactly like
`include`/`exclude` already will be.

Since packs are plain data (US-33's deliberate choice — no dataclass, no
Python callable), YAML parses directly into the same shape the engine
already consumes: no new (de)serialization code, no new trust boundary
(no code execution from project config, only declarative conditions from
the closed vocabulary US-33 documents).

## Acceptance criteria

- [ ] `.crm.yaml` (US-20) gains an optional `classification_packs:` key: a
      list of pack dicts in exactly US-33's schema (`name`, `activates_when`,
      `rules: [{when, role}]`), e.g.:
      ```yaml
      classification_packs:
        - name: my-vue-conventions
          activates_when: {language: javascript}
          rules:
            - when: {path_segment: stores}
              role: state
            - when: {symbol_suffix: "Composable"}
              role: hook
      ```
- [ ] Project-declared packs are appended to that project's
      `CLASSIFICATION_PACKS` **after** the built-in ones (`SPRING_JAVA_PACK`,
      `REACT_TYPESCRIPT_PACK`), scoped to that `IndexProject` instance only —
      never mutating the shared built-in registry, never touching a chunk a
      built-in pack already classified. Same non-clobbering rule US-33
      already established between packs.
- [ ] A malformed pack entry (unknown condition key inside `when`/
      `activates_when`, or a missing `name`/`rules`/`role`) fails indexing
      with a clear message naming the offending pack and the exact problem —
      never silently ignored, never a raw stack trace pointing into `crm`
      internals.
- [ ] `crm project config --project <id>` (US-20's inspection command) also
      lists each custom pack declared for the project and whether it
      activated on the last indexing run.
- [ ] Documentation: a short "Writing a custom classification pack" section
      (README, or `docs_en`/`docs_es`) with US-33's full condition-key table
      plus one complete worked example — pointing at `SPRING_JAVA_PACK` or
      `REACT_TYPESCRIPT_PACK` as real, working references to copy from,
      rather than an example invented for the docs alone.
- [ ] Integration test: a project with a `classification_packs:` entry in
      `.crm.yaml` gets chunks matching its rules classified accordingly, and
      chunks already classified by a built-in pack are left untouched even
      when a custom rule would also have matched them.

## Out of scope

- Arbitrary Python/code-based packs — declarative-only, by design: no
  sandboxing question, no new trust boundary, and it keeps a custom pack
  exactly as easy to write as a built-in one.
- Any interactive/CLI pack-authoring helper — hand-written YAML only.
- Changing or retiring any built-in pack.

## Files likely touched

- Wherever US-20 lands `.crm.yaml` parsing (`src/coderagmanager/adapters/config/`)
- `src/coderagmanager/domain/classification.py` (pack-shape validation,
  kept pure — reports problems, doesn't raise directly if that's better
  suited to the application layer)
- `src/coderagmanager/application/index_project.py` (accept extra packs)
- `src/coderagmanager/composition_root.py` (load + merge project packs)
- `README.md` or `docs_en/`, `docs_es/`
- `tests/application/`, `tests/adapters/`
