# US-15 — Project `group` field + `--group` + `project list` column

**Tier:** Nivel 3 · **Depends on:** —
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §9.2`, §12 points 7 and 8

## Story

As a maintainer of several related repos (e.g. a microservices/micro-frontend
system split across separate repos), I want to explicitly declare which of
my registered `crm` projects belong together, so that a later federated
search (US-16) can be scoped to only those, never to unrelated projects on
the same machine.

## Context

**The core safety property of the whole Nivel 3 design**: the set of
projects that can ever be searched together is decided by a human, ahead of
time, at registration — never inferred or decided by the LLM at runtime.
This story is that declaration mechanism; it does not, by itself, add any
new search capability (that's US-16).

## Acceptance criteria

- [ ] `Project` domain model gains `group: str | None = None`.
- [ ] `crm project add` gains `--group <name>` (`typer.Option(None,
      "--group")`). Help text: *"Name of the related-projects group (share
      the same name across multiple 'crm project add' calls to relate them);
      enables cross-project search scoped only to this group."*
- [ ] Persisted in `~/.crm/projects.yaml` alongside existing per-project
      fields (`extra_index_paths`, `auto_include`) — no new port, same
      `ProjectRegistry`/`YamlProjectRegistry`.
- [ ] Two projects with no `group`, or with different `group` values, are
      never included together by any future feature — this story's tests
      should assert `ProjectRegistry.list_by_group(name)` (new method)
      returns only exact matches, case-sensitive, no partial/fuzzy matching.
- [ ] `crm project list` output gains a `group` column (blank/`—` when
      unset).
- [ ] Docstrings/`--help` for `project_add` and `project_list` updated.
- [ ] Unit tests: registering 3 projects with the same `--group`, listing
      them, confirming `list_by_group` isolation from a 4th ungrouped
      project.

## Out of scope

- Any search behavior — US-16 consumes this field, this story only produces
  and displays it.
- Renaming or merging groups after the fact (no `crm project group
  rename` command) — not requested, can be a future story if needed.

## Files likely touched

- `src/coderagmanager/domain/models.py` (`Project.group`)
- `src/coderagmanager/ports/project_registry.py` (`list_by_group` method)
- `src/coderagmanager/adapters/registry/yaml_project_registry.py`
- `src/coderagmanager/adapters/cli/main.py` (`project_add`, `project_list`)
- `tests/domain/`, `tests/adapters/test_yaml_project_registry.py`
