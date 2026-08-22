# US-17 — Symbol collision warning in federated results

**Tier:** Nivel 3 · **Depends on:** US-16
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §9.4`, §12 point 8

## Story

As an agent reading `search_related_projects` results, I want to be warned
when the same symbol name exists in more than one project in the returned
batch, so that I don't silently conflate two different implementations that
happen to share a name.

## Context

**Real, confirmed case, not hypothetical**: both `mic-inventory` and
`mic-clients` have a class named `GlobalExceptionHandler` (each appears as
an expected answer in that project's own `benchmarks/bank/*.yaml`), with
different implementations. Per-result `[project_id]` labeling (US-16) helps
but a fast-reading LLM can still skim past it — this story adds an active,
impossible-to-miss signal on top of the passive label.

## Acceptance criteria

- [ ] In `application/search_related_projects.py`'s result formatting: group
      the batch of results actually being returned (not a full index scan)
      by exact `symbol` name; for any symbol appearing in more than one
      distinct `project_id`, prepend a warning line before the results,
      e.g.: `"⚠ 'GlobalExceptionHandler' exists in more than one project of
      this group (mic-clients, mic-inventory) — these are different
      implementations, do not conflate them."`
- [ ] Detection is exact-name-match only (no fuzzy/partial matching) and
      scoped to the current response's result set — not a standing,
      precomputed index-wide collision table.
- [ ] Each colliding result still carries its own `[project_id]` heading
      (US-16), so the warning and the labels reinforce each other rather
      than replacing one with the other.
- [ ] Unit test: a synthetic result set with `GlobalExceptionHandler` from
      two different `project_id`s triggers the warning; a result set with no
      name collisions produces no warning text at all.

## Out of scope

- Any change to `get_source`/`get_dependency_chain` (already decided against
  in US-16 — this story doesn't revisit that).
- Fuzzy/similar-name collision detection (e.g. `GlobalExceptionHandler` vs
  `GlobalExceptionHandlerV2`) — exact match only, keep it simple and
  predictable.

## Files likely touched

- `src/coderagmanager/application/search_related_projects.py`
- `src/coderagmanager/adapters/formatting.py`
- `tests/application/test_search_related_projects.py`
