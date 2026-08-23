# US-09 — `--role`/`--layer` filters (CLI + MCP tools)

**Tier:** Nivel 1 · **Depends on:** US-06, US-07, US-08
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §6.4`, §12 points 4 and 7

## Story

As a developer or agent, I want to filter `search_code`/`chunks` results by
architectural role or layer, so that I can narrow an exploratory query the
same way `--language`/`--kind` already let me.

## Story (kill switch)

As a maintainer of a project with no useful architectural convention, I want
to disable classification entirely for that project, so that `crm` doesn't
spend effort producing noisy `role`/`layer` values nobody will use.

## Acceptance criteria

- [ ] `crm project add` gains `--no-role-classification` (bool, default
      `False`), same style as `--no-auto-include`
      (`adapters/cli/main.py:88-92`). Help text: *"Do not classify chunks by
      architectural layer/role (domain/controller/entity...)"*. Disables
      **all three** classification layers (US-06, 07, 08) for that project.
- [ ] `crm search` and `crm chunks` gain `--role <value>` and `--layer <value>`
      (`typer.Option(None, "--role")` / `"--layer"`, same style as the
      existing `--language`/`--kind`).
- [ ] `SearchQuery`/`list_chunks` use case gain `role`/`layer` optional
      filter fields, applied the same way `language`/`kind` already are in
      `application/search_code.py`/`list_chunks.py`.
- [ ] MCP tools `search_code` and `list_chunks` gain `role: str | None = None`
      and `layer: str | None = None` parameters, alongside the existing
      `language`/`kind`.
- [ ] Docstrings of `search`, `chunks` CLI commands updated (Typer surfaces
      them in `--help`).
- [ ] Unit/integration test: filtering by a known `role` on a fixture with
      classified chunks returns only matching chunks; filtering on a project
      indexed with `--no-role-classification` returns no matches for any
      `role` value (since all are `None`) rather than erroring.

## Out of scope

- The classification logic itself (US-06/07/08) — this story only wires the
  already-produced `layer`/`role` fields into filters.

## Files likely touched

- `src/coderagmanager/adapters/cli/main.py`
- `src/coderagmanager/application/search_code.py`, `list_chunks.py`
- `src/coderagmanager/adapters/mcp/server.py`
- `src/coderagmanager/domain/models.py` (`SearchQuery` fields, `Project.auto_include`-style flag for classification)
- `tests/application/`, `tests/adapters/`
