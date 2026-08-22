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

- [ ] `tree_sitter_java.py` extracts class/interface-level annotations (e.g.
      `@RestController`, `@Service`, `@Entity`, `@Repository`, `@Mapper`,
      `@ControllerAdvice`/`@RestControllerAdvice`, `@Configuration`) into
      `chunk.metadata["annotations"]`, plus `extends`/`implements` type names
      already available from existing edges.
- [ ] `domain/classification.py` gains a `spring-java` pack: a static
      rule table + `classify_role_spring_java(chunk) -> str | None`, ported
      from `code-rag-mcp`'s `Classifiers.classifyRole`/`classifyInterface`/
      `classifyClass` logic: `@RestController`/`@Controller`→`controller`,
      `@Service`→`use-case` (if layer=`application`) or `service`,
      `@Entity`→`jpa-entity`, extends `*Repository`/`JpaRepository`/
      `CrudRepository`→`repository`, `@Mapper`→`mapper`,
      `@ControllerAdvice`/`@RestControllerAdvice`→`exception-handler`,
      interface in `ports.in`/ending `UseCase`→`port-in`, interface in
      `ports.out`/ending `Port`→`port-out`.
- [ ] Pack activation is automatic and cheap: applies only when a project's
      Java chunks contain any of the recognized Spring annotations — no
      project-level opt-in needed beyond the general
      `--no-role-classification` kill switch (US-09).
- [ ] Unit tests using representative Java fixtures (annotated
      class/interface examples) covering each rule above.

## Out of scope

- Any pack for JS/React or Python frameworks — explicitly deferred, no real
  project to calibrate against yet.
- Layer classification (that's US-06, independent).

## Files likely touched

- `src/coderagmanager/adapters/parsers/tree_sitter_java.py`
- `src/coderagmanager/domain/classification.py`
- `tests/adapters/test_tree_sitter_java.py`, `tests/domain/test_classification.py`
