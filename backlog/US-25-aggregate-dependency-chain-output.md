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

## Out of scope

- Any breaking-change classification or consumer-impact judgment — that's a
  separate, more targeted story (US-26).
- Changing `direction`/`max_depth` semantics or defaults.

## Files likely touched

- `src/coderagmanager/application/get_dependency_chain.py`
- `src/coderagmanager/adapters/formatting.py`
- `tests/application/test_get_dependency_chain.py`
