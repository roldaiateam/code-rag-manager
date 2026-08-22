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

- [ ] `Project` domain model gains `group: str | None = None`, appended
      **as the last field** of the dataclass (after `auto_include`) — never
      inserted mid-sequence, to avoid shifting any positional (non-keyword)
      construction of `Project` elsewhere.
- [ ] `crm project add` gains `--group <name>` (`typer.Option(None,
      "--group")`). Help text: *"Name of the related-projects group (share
      the same name across multiple 'crm project add' calls to relate them);
      enables cross-project search scoped only to this group. Re-registering
      an existing project without repeating --group clears it (same
      overwrite-on-re-register behavior as the rest of this command)."*
- [ ] Persisted in `~/.crm/projects.yaml` alongside existing per-project
      fields (`extra_index_paths`, `auto_include`) — no new port change
      beyond the two below.
- [ ] `ProjectRegistry.register()` (both the `Protocol` in
      `ports/project_registry.py` and the `YamlProjectRegistry` adapter)
      gains an explicit `group: str | None = None` parameter, threaded
      through into the persisted dict — `YamlProjectRegistry.register()`
      builds its entry dict field-by-field (no `dataclasses.asdict()`), so
      `"group": group` must be added there explicitly or `--group` would be
      silently accepted by the CLI and never actually persisted.
- [ ] `YamlProjectRegistry.get()` reads the field as **`entry.get("group")`,
      never `entry["group"]`** — the confirmed backward-compatibility
      requirement: an existing `~/.crm/projects.yaml` written before this
      feature has no `"group"` key for any project, and `entry["group"]`
      would raise `KeyError` on every `crm project list`/`search`/etc. for
      those pre-existing entries. Unit test: load a hand-written registry
      fixture in the pre-this-feature format (no `group` key at all) and
      assert `.get()`/`.list()` succeed with `group=None`, no exception.
- [ ] Two projects with no `group`, or with different `group` values, are
      never included together by any future feature — this story's tests
      should assert `ProjectRegistry.list_by_group(name)` (new method)
      returns only exact matches, case-sensitive, no partial/fuzzy matching.
- [ ] `crm project list` output gains a `group` column, **appended at the
      end of the existing line** (`f"{p.id:<20} {p.root_path}  ({indexed})"`
      today) rather than inserted in the middle — minimizes disruption to
      any existing ad-hoc parsing of this plain-text (non-JSON) output.
- [ ] Docstrings/`--help` for `project_add` and `project_list` updated.
- [ ] Unit tests: registering 3 projects with the same `--group`, listing
      them, confirming `list_by_group` isolation from a 4th ungrouped
      project; re-registering one of them without `--group` and confirming
      its group is cleared (documented overwrite behavior, not a bug).

**Note for US-16 (not this story's concern):** `tests/application/fakes.py`
currently has no `FakeProjectRegistry` at all (only `FakeEmbedder`,
`FakeVectorStore`, `FakeGraphStore`, `FakeLexicalIndex`, `FakeGit`) — so this
story doesn't break any shared test fake. Whoever implements US-16 (which
does need to exercise `list_by_group` at the application layer) will need to
either add that fake or test against a real `YamlProjectRegistry` pointed at
a temp file.

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
