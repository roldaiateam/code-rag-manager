# US-33 — Classification layer 2: declarative convention-pack engine (migrate `spring-java` onto it)

**Tier:** Nivel 1 · **Depends on:** US-07
**Design reference:** none in `PLAN-MEJORA-CODE-RAG-MANAGER.md` — raised while
scoping a second Layer-2 pack (US-34) and finding that today's `spring-java`
is bespoke Python wired into `index_project.py` by name, not something a new
ecosystem's rules could reuse without copying that pattern function-by-function.

## Story

As someone adding a new architectural-convention pack to `crm` (a
maintainer, or a project owner extending `crm` for their own codebase in
US-35), I want a pack to be a small, declarative rule table instead of a
bespoke Python function wired into the indexing pipeline by name, so that
adding one never requires touching `index_project.py`, and the whole
mechanism is small enough to document in one page.

## Context

Today's only Layer 2 pack (`spring-java`, US-07) is hardcoded end to end:
`spring_java_pack_applies()` and `classify_role_spring_java()` are named
functions, and `index_project.py` calls them by name:
```python
if spring_java_pack_applies(chunks):
    chunks = [replace(c, role=classify_role_spring_java(c)) for c in chunks]
```
Adding `react-typescript` (US-34) this way would mean copying this shape —
another named `_applies`/`_classify` pair, another `if` block in
`index_project.py`. That doesn't scale past two packs, and it gives a
project owner with unusual conventions (US-35) no way to add their own
without forking `crm`'s source.

Reading `spring-java`'s actual rules (`_classify_interface_role_spring_java`,
`_classify_class_role_spring_java`) shows every one of them is a combination
of a handful of simple checks: annotation present, `kind`, `layer` (already
computed by Layer 1 before Layer 2 runs), a path segment, a supertype
substring, a symbol suffix. None of it needs arbitrary code — it's data.
This story extracts that vocabulary into a small, closed set of conditions,
and re-expresses `spring-java` using it, with **zero change in classification
outcomes** (every existing US-07 test must keep passing).

## Acceptance criteria

- [ ] `domain/classification.py::chunk_matches(chunk: CodeChunk, condition: dict) -> bool`:
      every key present in `condition` must match (AND semantics). Supported
      keys:

      | Key | Checks |
      |---|---|
      | `language` / `language_in` | `chunk.language` equals / is one of |
      | `kind` / `kind_in` | `chunk.kind` equals / is one of |
      | `layer` | `chunk.layer` equals |
      | `annotation_in` | any of `chunk.metadata.get("annotations", ())` is in the list |
      | `supertype_contains` | any of `chunk.metadata.get("supertypes", ())` contains any given substring |
      | `path_segment` / `path_segment_in` | any single path segment (case-insensitive) equals / is one of |
      | `path_contains_segments` | an ordered list of segments (case-insensitive) appears **consecutively** anywhere in the path — ports today's `_in_ports_segment` |
      | `symbol_prefix` / `symbol_suffix` | `chunk.symbol` starts/ends with the given string |

- [ ] A pack is a plain `dict`: `{"name": str, "activates_when": dict, "rules": [{"when": dict, "role": str}, ...]}`.
      Deliberately not a dataclass/`Protocol` — the same shape must work
      whether it's written by hand in Python or parsed from YAML (needed by
      US-35), with no (de)serialization step in between.
- [ ] `domain/classification.py::pack_applies(pack: dict, chunks: Iterable[CodeChunk]) -> bool`:
      `True` if any chunk matches `pack["activates_when"]`.
- [ ] `domain/classification.py::classify_role_by_pack(chunk: CodeChunk, pack: dict) -> str | None`:
      evaluates `pack["rules"]` in order, returns the first matching rule's
      `role`, or `None` if none match. Rule order is significant and must be
      preserved exactly as today's Python did (see below).
- [ ] `domain/classification.py::CLASSIFICATION_PACKS: list[dict]` — the new
      registry, containing exactly one entry: `SPRING_JAVA_PACK`. Its
      `activates_when` and `rules` reproduce every documented nuance of
      US-07 exactly:
      - `activates_when`: `language == "java"` and `annotation_in` one of
        `RestController, Controller, Service, Entity, Repository, Mapper,
        ControllerAdvice, RestControllerAdvice, Configuration` (the last two,
        `Repository`/`Configuration`, activate the pack but map to no rule —
        preserved as-is from US-07).
      - Rule order preserved: on interfaces, `Mapper` beats the
        `Repository`-supertype check; `port-in`/`port-out`/`UseCase`-suffix/
        `Port`-suffix rules all require `layer == "domain"`. On classes,
        `RestController`/`Controller` beats `Service`; `Service` yields
        `use-case` only when `layer == "application"`, `service` otherwise
        (two ordered rules: `{annotation_in: [Service], layer: application} → use-case`
        before `{annotation_in: [Service]} → service`).
- [ ] `application/index_project.py`'s Layer 2 block becomes pack-agnostic —
      no pack name appears in it anymore:
      ```python
      for pack in CLASSIFICATION_PACKS:
          if not pack_applies(pack, chunks):
              continue
          chunks = [
              c if c.role is not None else _with_pack_role(c, pack)
              for c in chunks
          ]
      ```
      A pack never reclassifies a chunk an earlier pack (or Layer 1) already
      assigned a role to — same non-clobbering rule already used between
      layers 1→2→3.
- [ ] `classify_role_spring_java`, `spring_java_pack_applies`,
      `_classify_interface_role_spring_java`, `_classify_class_role_spring_java`
      are removed, superseded by `SPRING_JAVA_PACK` + the generic engine.
- [ ] Every existing Spring-Java test in `tests/domain/test_classification.py`
      keeps passing with the same expected outcomes, updated only to call
      `classify_role_by_pack(chunk, SPRING_JAVA_PACK)` /
      `pack_applies(SPRING_JAVA_PACK, chunks)` instead of the removed named
      functions — this is the acceptance bar for "pure refactor, no behavior
      change".
- [ ] `tests/application/test_index_project.py`'s existing Spring-Java
      integration tests (fixtures, expected roles) keep passing unchanged.

## Out of scope

- Any new pack beyond the ported `spring-java` one — that's US-34.
- Loading packs from project-local config — that's US-35.
- Changing any of `spring-java`'s actual classification outcomes.

## Files likely touched

- `src/coderagmanager/domain/classification.py`
- `src/coderagmanager/application/index_project.py`
- `tests/domain/test_classification.py`
- `tests/application/test_index_project.py`
