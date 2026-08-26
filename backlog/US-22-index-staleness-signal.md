# US-22 — Index staleness signal across MCP tools/CLI

**Tier:** Index reliability (cross-cutting) · **Depends on:** —
**Design reference:** none — raised while auditing whether search results carry
any signal that the index might be behind the repo's current state.

## Story

As an agent calling `search_code`, `get_dependency_chain`, or `get_source`, I
want to be told when the index was built against an older commit than the
repo's current `HEAD` (or when the working tree has uncommitted changes), so
that I don't trust a result that no longer matches the code on disk without
any warning.

## Context

`GetIndexStats.execute()` (`application/get_index_stats.py:16-27`) already
reads `IndexManifest.last_indexed_commit` but never compares it against the
repo's *current* `HEAD` — and no other tool (`search_code`,
`get_dependency_chain`, `get_source`, `list_chunks`) touches the manifest at
all. `GitProvider` (`ports/git_provider.py`) only exposes `head()`; its
docstring says so deliberately, because v1 never reindexes incrementally.
Comparing `HEAD` for a one-line staleness note is a read-only check and does
not reopen that decision — it never diffs file contents or drives reindexing.

## Acceptance criteria

- [ ] `GitProvider` gains `is_dirty(repo_path: str) -> bool` (`git status
      --porcelain` non-empty), alongside the existing `head()` — read-only,
      no content diffing, so it doesn't reintroduce incremental-reindex
      machinery.
- [ ] New application-level helper (e.g. `application/index_staleness.py`,
      `staleness_note(project, git, root_path) -> str | None`) reads the
      manifest, calls `git.head(root_path)`, and returns a one-line note
      when: (a) `git.head()` differs from `manifest.last_indexed_commit`, or
      (b) `git.is_dirty(root_path)` is true, or (c) no manifest exists yet.
      Returns `None` when the index is current and the tree is clean.
- [ ] `search_code`, `get_dependency_chain`, and `get_source` MCP tools
      prepend this note (when not `None`) to their formatted output, e.g.
      `"⚠ Index was built at a different commit than the repo's current
      HEAD — results may not reflect the current code. Run reindex to
      refresh."`, or, for a dirty tree, `"⚠ Working tree has uncommitted
      changes not reflected in the index."`
- [ ] The check costs at most one extra `git` subprocess call per tool
      invocation — no caching needed given `crm`'s single-process-per-project
      MCP server model.
- [ ] Unit test: manifest commit == `HEAD` and clean tree → no note;
      manifest commit != `HEAD` → note mentions staleness; dirty tree → note
      mentions uncommitted changes; no manifest → note says "not indexed
      yet".

## Out of scope

- Computing *how many* commits behind (`git rev-list` count) — a note that
  the commit differs is enough; no numeric distance in v1.
- Any change to reindex triggering or incremental indexing — this story only
  surfaces a warning, it never reindexes automatically.

## Files likely touched

- `src/coderagmanager/ports/git_provider.py`
- `src/coderagmanager/adapters/git/git_cli_provider.py`
- `src/coderagmanager/application/index_staleness.py` (new)
- `src/coderagmanager/adapters/mcp/server.py`
- `tests/application/`, `tests/adapters/` (fake `GitProvider` for the new
  method)
