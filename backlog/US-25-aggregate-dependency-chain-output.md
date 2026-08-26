# US-25 — Aggregate `get_dependency_chain` output instead of a flat edge dump

**Tier:** Dependency graph UX (cross-cutting) · **Depends on:** US-23
**Design reference:** none — raised while auditing what an agent actually
receives from `get_dependency_chain` on a heavily-used symbol.

## Story

As an agent calling `get_dependency_chain` on a widely-used symbol, I want
the result grouped and counted by file/edge type instead of one line per
edge with no summary, so that I can understand the shape of the dependency
chain without having to mentally aggregate dozens of loose lines myself.

## Context

`format_chain()` (`adapters/formatting.py:36-45`) prints exactly one line
per `DependencyEdge` returned by `GraphStore.dependency_chain()`, with no cap
and no grouping — unlike `list_chunks`/`format_chunks`, which caps at 200
rows and tells the caller how to page (US-21). A symbol with many callers at
`max_depth=3, direction="both"` can return a very long, unstructured list
that the agent has to summarize itself in its own context window.

**Second, separate problem confirmed in the same area**:
`JsonGraphStore.dependency_chain()` (`adapters/storage/json_graph_store.py:79-88`)
resolves the query's `symbol` argument by collecting **every** node whose
`symbol` matches — `start_ids = [node_id for node_id, info in
data["nodes"].items() if info["symbol"] == symbol]` — and runs the BFS from
all of them at once, into one merged, undifferentiated result. If two chunks
in the same project share a symbol name (e.g. a `validate` method in two
unrelated classes — not exotic), `get_dependency_chain("validate")` silently
interleaves both dependency graphs with no indication that two distinct
symbols were matched. This is a query-time counterpart to US-23's
index-time edge-resolution ambiguity, in a different code path (the BFS
start-node lookup, not `resolve_edges`) — US-23 doesn't cover it.

## Acceptance criteria

- [ ] `GetDependencyChain.execute()` (`application/get_dependency_chain.py`)
      returns edges grouped by `(direction, edge_type, file_path)` with a
      count per group, alongside the existing flat per-edge detail (detail
      retained for when an agent needs it, not removed).
- [ ] `format_chain()` renders a summary block first (e.g. `"12 incoming
      'calls' edges across 5 files (3 from OrderService.java, ...)"`), then
      the existing per-edge lines below it, capped at 200 rows with a note on
      how to narrow via `direction`/`max_depth` (same convention as US-21).
- [ ] Edges marked `resolution="ambiguous"` (US-23) are counted and called
      out separately in the summary (e.g. `"2 of these are ambiguous — see
      below"`), never silently folded into the confident count.
- [ ] Unit test: a synthetic edge set across multiple files produces the
      expected per-file/per-type counts; an edge set containing an ambiguous
      edge is reported separately from exact ones.
- [ ] `GetDependencyChain.execute()` detects multiple distinct start nodes
      for the given `symbol` **without changing `GraphStore`'s port
      signature**: it already fetches `graph_store.nodes(project_id)` for
      `describe()` — reuse that same call to compute
      `matching = [nid for nid, info in nodes.items() if info["symbol"] ==
      symbol]` before calling `dependency_chain()`. When `len(matching) > 1`,
      the summary block leads with an explicit warning naming every match's
      `file_path`/`kind`, e.g. `"⚠ 'validate' matches 2 distinct symbols —
      results below are merged across OrderService.java:42 and
      UserService.java:110."` This is app-layer only; `JsonGraphStore`
      itself is untouched.
- [ ] Unit test: two fixture nodes sharing a symbol name trigger the
      multi-match warning naming both locations; a symbol matching exactly
      one node produces no such warning.

## Out of scope

- Any breaking-change classification or consumer-impact judgment — that's a
  separate, more targeted story (US-26).
- Changing `direction`/`max_depth` semantics or defaults.

## Files likely touched

- `src/coderagmanager/application/get_dependency_chain.py`
- `src/coderagmanager/adapters/formatting.py`
- `tests/application/test_get_dependency_chain.py`
