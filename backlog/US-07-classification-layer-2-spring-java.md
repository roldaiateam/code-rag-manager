# US-07 — Classification layer 2: `spring-java` pack

**Tier:** Nivel 1 · **Depends on:** — (independent of US-06, both feed US-09)
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §6.3` (Capa 2), §12 point 4

## Story

As an agent working in a Java/Spring hexagonal project, I want chunks
classified by role (`controller`, `use-case`, `jpa-entity`, `repository`,
`mapper`, `exception-handler`, `port-in`, `port-out`) from their annotations
and package conventions, so that I can filter searches by architectural role
the same way `code-rag-mcp` already lets its users do.

## Context

Two of the three real projects in `benchmarks/bank/*.yaml`
(`mic-inventory`, `mic-clients`) are Java/Maven hexagonal + Spring — the same
family `code-rag-mcp`'s `Classifiers.java` already targets, validated in
production. This is the **only** convention pack shipped initially — no
React/JS or Python framework pack is in scope (no real project in the bank
uses those yet; see design doc §12 point 4 for why this is deliberately
minimal, not an oversight).

**Prerequisite baked into this story, not a separate one:**
`tree_sitter_java.py` currently builds every chunk with `metadata={}` — it
extracts no annotations at all. This story must add that extraction before
the pack has anything to classify.

## Acceptance criteria

- [x] `tree_sitter_java.py` extracts class/interface-level annotations (e.g.
      `@RestController`, `@Service`, `@Entity`, `@Repository`, `@Mapper`,
      `@ControllerAdvice`/`@RestControllerAdvice`, `@Configuration`) into
      `chunk.metadata["annotations"]`, plus `extends`/`implements` type names
      into `chunk.metadata["supertypes"]` (a dedicated, shallow extraction
      that stops at `generic_type` — separate from the existing edge-building
      walk, which is untouched and still over-collects generic type
      arguments as `EXTENDS` edges; that's pre-existing behavior, not part of
      this story).
- [x] `domain/classification.py` gains a `spring-java` pack: a static
      rule table + `classify_role_spring_java(chunk) -> str | None`, ported
      from `code-rag-mcp`'s `Classifiers.classifyRole`/`classifyInterface`/
      `classifyClass` logic: `@RestController`/`@Controller`→`controller`,
      `@Service`→`use-case` (if layer=`application`) or `service`,
      `@Entity`→`jpa-entity`, extends `*Repository`/`JpaRepository`/
      `CrudRepository`→`repository`, `@Mapper`→`mapper`,
      `@ControllerAdvice`/`@RestControllerAdvice`→`exception-handler`,
      interface in `ports.in`/ending `UseCase`→`port-in`, interface in
      `ports.out`/ending `Port`→`port-out`. Three details ported from
      `Classifiers.java` (read in full) but not spelled out in this story:
      (1) `port-in`/`port-out` only apply when `chunk.layer == "domain"` —
      matches the real bank projects, where ports always live under
      `domain/ports/in|out/`; (2) `@Repository` and `@Configuration` are
      extracted (useful metadata) but have no rule of their own — faithful
      to the original, where `repository` is 100% structural and
      `Configuration`→`config` falls outside this story's 8-role scope;
      (3) rule order matters and is preserved (e.g. `Mapper` beats the
      `Repository`-supertype check on interfaces, `Controller` beats
      `Service` on classes).
- [x] Pack activation is automatic and cheap: applies only when a project's
      Java chunks contain any of the recognized Spring annotations — no
      project-level opt-in needed beyond the general
      `--no-role-classification` kill switch (US-09). Implemented as
      `spring_java_pack_applies(chunks)`, checked once in
      `IndexProject.execute()` before the (separate, second) `role=`
      classification pass — `@Service` needs `layer` already set, so `role`
      is computed after `layer`/`kind`, not in the same `replace()` call.
- [x] Unit tests using representative Java fixtures (annotated
      class/interface examples) covering each rule above.
- [x] Verified end-to-end against the two real Java/Spring projects in the
      bank (`mic-inventory`, `mic-clients`, both present on disk): parsed
      real files and confirmed `role` matches expectations for
      `ProductsControllerApi`→`controller`, `ProductsUseCaseImpl`→`use-case`,
      `ProductDb`→`jpa-entity`, `ProductsRepository`→`repository`,
      `RestSearchProductsMapper`→`mapper`, `GlobalExceptionHandler`→
      `exception-handler`, `ProductsUseCase`/`AuthUseCase`/`TenantsUseCase`→
      `port-in`, `ProductsPort`/`TokenParserPort`→`port-out` — and confirmed
      (via `git stash` of the source changes) that before this story every
      one of those files produced `metadata == {}` and no role at all.

## Out of scope

- Any pack for JS/React or Python frameworks — explicitly deferred, no real
  project to calibrate against yet.
- Layer classification (that's US-06, independent).

## Files likely touched

- `src/coderagmanager/adapters/parsers/tree_sitter_java.py`
- `src/coderagmanager/domain/classification.py`
- `src/coderagmanager/application/index_project.py` (wires the pack's
  activation + the `role=` classification pass — not in the original list,
  but without it `role` stays `None` forever, same reasoning US-09 relies on)
- `tests/adapters/test_tree_sitter_java.py` (new),
  `tests/fixtures/sample_repo/src/SpringExamples.java` (new),
  `tests/domain/test_classification.py`, `tests/application/test_index_project.py`
