# US-26 — Consumer summary for a symbol (who depends on this)

**Tier:** Dependency graph UX (cross-cutting) · **Depends on:** US-25
**Design reference:** none — raised while auditing what tooling exists to
answer "what depends on this before I change it".

## Story

As an agent about to modify or rename a symbol, I want a quick summary of
which files currently depend on it, so that I can gauge the blast radius of
a change without manually reading through a raw dependency-chain listing.

## Context

`get_dependency_chain` (`application/get_dependency_chain.py`) already
computes incoming edges given `direction="in"`, but nothing in `crm` packages
that into a "who uses this" summary today — an agent has to call the tool
and read/count the edges itself. This is a thin, deliberately-scoped read on
top of US-25's aggregation, not a new form of analysis: it never classifies
whether a change is "safe", it only reports who currently points at the
symbol.

## Acceptance criteria

- [ ] New MCP tool `get_consumers(symbol: str)` (and CLI `crm consumers
      <symbol>`), implemented as a thin wrapper: calls the existing
      dependency-chain use case with `direction="in"`, `max_depth=1` (direct
      callers only — no transitive walk, so the answer stays bounded and
      unambiguous about what "depends on this" means), and formats it as: a
      total count, grouped by file, with `resolution="ambiguous"` (US-23)
      entries listed separately and never counted toward the confident
      total.
- [ ] Tool docstring is explicit that this reports *current, direct*
      dependents only — not a safety judgment about whether changing the
      symbol is OK, and not a transitive/whole-graph impact analysis.
- [ ] When the symbol isn't found in the graph at all, the tool says so
      plainly (distinct message from "0 consumers", which would wrongly
      imply the symbol exists and is simply unused).
- [ ] Unit test: a symbol with 3 direct callers across 2 files reports the
      right grouped counts; a symbol absent from the graph gets the distinct
      "not found" message; an ambiguous incoming edge is listed separately,
      not folded into the count.

## Out of scope

- Breaking-change classification, semantic versioning judgments, or anything
  claiming a change "is safe" — deliberately not this story's job.
- Transitive impact (depth > 1) — direct callers only; an agent who wants
  more can still call `get_dependency_chain` directly with a larger
  `max_depth`.
- Cross-project consumers — once `group`/`search_related_projects` (US-15,
  US-16) exist, extending this tool to mention them is a natural follow-up,
  but it is not part of this story.

## Files likely touched

- `src/coderagmanager/application/get_consumers.py` (new, thin wrapper over
  `GetDependencyChain`)
- `src/coderagmanager/adapters/mcp/server.py`
- `src/coderagmanager/adapters/cli/main.py`
- `src/coderagmanager/adapters/formatting.py`
- `tests/application/test_get_consumers.py`
