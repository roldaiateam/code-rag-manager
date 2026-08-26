# US-23 — Flag ambiguous symbol resolution instead of guessing

**Tier:** Index reliability (cross-cutting) · **Depends on:** —
**Design reference:** none — raised while auditing how `DependencyEdge`
targets get resolved from parser-emitted name references.

## Story

As an agent reading `get_dependency_chain` output, I want an edge that
couldn't be resolved to a single unambiguous symbol to say so, instead of
silently pointing at whichever same-named chunk happened to be first in the
list, so that I don't mistake a guess for a confirmed dependency.

## Context

`domain/resolution.py:36-45` — when `resolve_edges()` has more than one
same-named candidate outside the source chunk's own file, it takes
`(same_file or candidates)[0]`: the first candidate in whatever order chunks
were parsed in, with no signal that a choice was made. There is currently no
test asserting which candidate wins in that case — the behavior is an
accident of iteration order, not a decided rule, and nothing downstream (not
`get_dependency_chain`, not its formatting) can currently tell an exact match
from a guess.

## Acceptance criteria

- [ ] `DependencyEdge` gains a field, e.g. `resolution: str = "exact"` with
      values `"exact"` (single candidate, or a same-file match narrowed it
      down) and `"ambiguous"` (more than one cross-file candidate and no
      same-file match to prefer). The existing drop-when-no-candidate case is
      untouched by this story.
- [ ] `resolve_edges()` sets `resolution="ambiguous"` in that case; the edge
      still resolves to a target (today's choice: first candidate) so nothing
      downstream breaks — only the label changes.
- [ ] `format_chain()` (`adapters/formatting.py`) renders ambiguous edges
      distinctly, e.g. appending `" (ambiguous: 3 candidates, showing 1)"` to
      the line, so an agent reading the output doesn't treat it as
      equivalent to an exact match.
- [ ] Unit test: two candidates in different files, neither matching the
      source's file → edge marked `ambiguous`; one candidate in the source's
      own file among several → edge marked `exact` (today's disambiguation
      rule still wins first); a single candidate anywhere → `exact`.

## Out of scope

- Actually improving resolution accuracy (e.g. import-aware resolution,
  per-language scoping rules) — this story only makes today's known
  limitation visible, it doesn't fix the underlying imprecision.
- Applying the same flag to lexical/semantic search results — scoped to
  `DependencyEdge` resolution only.

## Files likely touched

- `src/coderagmanager/domain/models.py`
- `src/coderagmanager/domain/resolution.py`
- `src/coderagmanager/adapters/formatting.py`
- `tests/domain/test_resolution.py`
