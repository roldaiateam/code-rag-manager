# US-21 — Pagination for `crm chunks` / `list_chunks` (no scripts required to debug)

**Tier:** DX / debugging (cross-cutting) · **Depends on:** —
**Design reference:** none — raised while onboarding, hitting the existing
200-row hard cap with no way to see the rest through the CLI itself.

## Story

As a `crm` user debugging what got indexed, I want `crm chunks` (and the
`list_chunks` MCP tool) to support paging past the first 200 rows, so that
I can inspect the full inventory of a large project entirely through the
CLI — without writing a throwaway Python/LanceDB script just to see rows
201+.

## Context

`adapters/formatting.py:49` (`format_chunks(chunks, max_rows=200)`) hard-caps
the printed output at 200 rows, and `application/list_chunks.py` only
filters by `language`/`kind` — no `offset`/`limit`. For a project like
`mic-inventory` (2358 java chunks, 1956 of them `kind=method`), filtering by
`--language java --kind method` still leaves far more than 200 rows with no
way to see the rest — the CLI's own message ("filtra con language/kind para
acotar el listado") doesn't actually resolve it once a single filtered
category is itself bigger than the cap.

## Acceptance criteria

- [ ] `ListChunks.execute()` (`application/list_chunks.py`) accepts optional
      `offset: int = 0` and `limit: int | None = None` params, applied after
      the existing `language`/`kind` filtering and the existing sort
      (`file_path`, `start_line`).
- [ ] `crm chunks --project <id>` gains `--offset`/`--limit` (or `--page`/`--page-size`)
      CLI options, defaulting to today's behavior (`limit=200`) when unset,
      so existing usage doesn't change.
- [ ] Output tells the user there's more to see and exactly how to get the
      next page, e.g. `[mostrando 200 de 1956 — usa --offset 200 para ver más]`,
      replacing today's dead-end message that only suggests filtering
      further.
- [ ] `list_chunks` MCP tool (`adapters/mcp/server.py`) gets the same
      `offset`/`limit` parameters, with its docstring updated so the agent
      knows how to page through a large inventory instead of assuming 200
      is the whole answer.
- [ ] `LanceDbVectorStore.list()` (`adapters/storage/lancedb_vector_store.py`)
      applies offset/limit at the adapter level (slicing the already-sorted
      list is enough — no need to push this into the LanceDB query itself
      for v1).

## Out of scope

- Cursor-based pagination (stable across concurrent reindexes) — offset-based
  is enough; a reindex already invalidates any previous listing anyway
  (drop-and-rebuild).
- Changing the underlying LanceDB query/index (`search_code`'s `top_k` is
  unaffected — this story is only about `list_chunks`/`crm chunks`).

## Files likely touched

- `src/coderagmanager/application/list_chunks.py`
- `src/coderagmanager/adapters/formatting.py` (`format_chunks`)
- `src/coderagmanager/adapters/storage/lancedb_vector_store.py` (`list()`)
- `src/coderagmanager/adapters/cli/main.py` (`chunks` command)
- `src/coderagmanager/adapters/mcp/server.py` (`list_chunks` tool)
- `tests/application/test_list_chunks.py` (new, or extend existing test file)
