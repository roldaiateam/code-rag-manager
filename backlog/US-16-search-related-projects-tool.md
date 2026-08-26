# US-16 — `search_related_projects` MCP tool

**Tier:** Nivel 3 · **Depends on:** US-15
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §9.3`, §12 points 7 and 8

## Story

As an agent working in one project of a related group (e.g. a microservice
whose frontend lives in a sibling repo), I want a tool that searches across
only the group's members and tells me which project each result came from,
so that I can answer questions that genuinely span more than one repo
without needing to know in advance which repo holds the answer.

## Context

**No `--workspace` server mode.** The existing `crm mcp serve --project
<id>` process reads its own registry entry at startup and conditionally
exposes this tool **only if `group` is set** (US-15) — exactly the pattern
`code-rag-mcp` already validated for its Obsidian vault bridge ("these tools
appear only when the server starts with a vault configured"). If `group` is
unset, this tool simply does not exist on that server — zero behavior change
for today's single-project use case.

**Isolation stays structural, not a filter.** Even within a group, each
project keeps its own separate `VectorStore` table, `graph.json`, and
lexical index — grouping only decides what gets queried together at request
time, never merges storage.

## Acceptance criteria

- [ ] `application/search_related_projects.py`: new use case. Resolves the
      active project's `group` via `ProjectRegistry`, calls
      `ProjectRegistry.list_by_group(group)` (US-15), instantiates each
      member project's own `SearchCode` use case (own `VectorStore`/
      `LexicalIndex` instances — never shared), runs the query against each,
      merges with `merge_and_rerank`, tagging every result with its
      `project_id` (already free on `CodeChunk`).
- [ ] MCP tool `search_related_projects(query: str, top_k: int = 10)`
      registered **conditionally**: only added to the `FastMCP`/`MCPServer`
      instance when `build_use_cases()` finds a non-null `group` for the
      active project.
- [ ] Tool docstring includes explicit "when to use / when NOT to use"
      guidance, same discipline `code-rag-mcp`'s tools already use: *"Use
      ONLY when the question explicitly spans more than one service/repo
      (e.g. an end-to-end flow across frontend and backend). For anything
      scoped to the current repo, use `search_code` instead."*
- [ ] Every result in the formatted output is headed by a visible
      `[project_id]` tag in the text itself (not just a metadata field a
      reader could skim past).
- [ ] The formatted output always states, in one line, which member projects
      of the group were actually queried and which were skipped (and why —
      e.g. "not indexed yet", "index failed to load"), e.g. `"Queried:
      mic-clients, mic-inventory. Skipped: mic-notifications (not indexed
      yet)."` This line is present even when every member was queried
      successfully — an agent must be able to tell "searched all 3 of 3
      group members" from the response text itself, never by inferring it
      from an empty result set or an absent line.
- [ ] `crm search "<query>" --related` CLI equivalent, for debugging outside
      MCP.
- [ ] **`get_source` and `get_dependency_chain` are NOT modified by this
      story** — they remain bound to the active project only. When a
      `search_related_projects` result comes from a different project than
      the active one, the tool's own output text says so explicitly, e.g.:
      *"This result is from `mic-clients`; to read its full source, do so in
      a session with `crm mcp serve --project mic-clients`."* Never a
      silent attempt to resolve a foreign-project symbol against the active
      project's index.
- [ ] Integration test: two fixture projects in the same group, a query
      whose answer only exists in one of them returns it labeled correctly;
      a project with no group exposes no such tool at all.
- [ ] Integration test: a group with a member whose index can't be loaded
      (or that has no manifest yet) still returns results from the other
      members, and the "queried/skipped" line names that member explicitly
      instead of the search silently returning fewer results than expected.

## Out of scope

- Symbol-collision warning when the same name exists in more than one
  member project — that's US-17 (kept separate since it's a distinct,
  independently testable safeguard).
- 3a (single process serving many `project_id`s) — remains parked, unrelated
  to this story.

## Files likely touched

- `src/coderagmanager/application/search_related_projects.py` (new)
- `src/coderagmanager/adapters/mcp/server.py` (conditional tool registration)
- `src/coderagmanager/adapters/cli/main.py` (`--related` flag)
- `src/coderagmanager/composition_root.py`
- `tests/application/`, `tests/adapters/` (fixtures: 2+ grouped projects)
