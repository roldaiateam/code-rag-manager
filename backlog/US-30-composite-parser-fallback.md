# US-30 — `CompositeLanguageParser` falls back to generic text instead of silently indexing nothing

**Tier:** Language coverage (cross-cutting) · **Depends on:** —
**Design reference:** none — raised while diagnosing why a real-world
CommonJS-style `.js` file (`module.exports.handler = async (event) =>
{...}`) produces zero chunks with the current dispatch logic.

## Story

As a `crm` user indexing a file whose syntax isn't covered by its language's
`CHUNK_NODE_TYPES` (e.g. CommonJS-style exports in a `.js` file), I want
that file to still be searchable via the generic text fallback, so that a
parser's blind spot degrades search quality instead of making the file
invisible.

## Context

`CompositeLanguageParser.parse()` (`adapters/parsers/composite.py:16-20`)
returns the first matching parser's result as soon as `supports()` returns
`True` — even when that result is `([], [])` — and never tries
`GenericTextParser`. Confirmed concretely: `TreeSitterJavaScriptParser`'s
`CHUNK_NODE_TYPES` doesn't recognize `assignment_expression` (the
`module.exports.x = ...` / `exports.x = ...` CommonJS pattern, common in
Lambda handlers and older Express/Node code), so such a file is claimed by
extension and then returns nothing — not degraded to text blocks,
**completely absent from the index**, with no warning anywhere in the
indexing summary.

## Acceptance criteria

- [ ] `CompositeLanguageParser.parse()` falls back to `GenericTextParser`
      (its last registered entry) whenever the matched dedicated parser
      returns zero chunks for a non-empty `source` — reusing the
      already-registered instance, not a special case wired elsewhere.
- [ ] This applies uniformly to every dedicated parser (Python/Java/JS/TS/
      CSS), not just JS — a future parser's blind spot gets the same safety
      net for free, with no per-parser opt-in required.
- [ ] `IndexStats`/`format_included` (or a new counter alongside it) reports
      how many files fell back this way, e.g. `"3 files fell back to
      generic text chunking — a dedicated parser matched but found
      nothing"` — this doesn't silently mask a real parser bug either: a
      spike in fallback count across an otherwise well-formed codebase is
      itself a signal worth surfacing to whoever runs `reindex`.
- [ ] Unit test: a synthetic `.js` fixture using only
      `assignment_expression`-style exports (no `CHUNK_NODE_TYPES` match)
      produces `GenericTextParser`-shaped chunks (`kind="block"`,
      `language="text"`) instead of an empty list.
- [ ] Unit test: a normal `.py`/`.java`/`.js` file with real matches is
      unaffected — the fallback only triggers on a genuine zero-chunk
      result, never overrides a parser that found something.

## Out of scope

- Fixing `TreeSitterJavaScriptParser`'s `CHUNK_NODE_TYPES` to actually
  recognize `assignment_expression`-based exports — that's a targeted
  parser improvement; this story is only the dispatch-level safety net.
  Worth a follow-up story if CommonJS-style codebases turn out to be common
  in practice — the fallback here is the floor, not the fix.
- Any change to `GenericTextParser` itself.

## Files likely touched

- `src/coderagmanager/adapters/parsers/composite.py`
- `src/coderagmanager/application/index_project.py` (threading the fallback
  counter into `IndexStats`)
- `src/coderagmanager/adapters/formatting.py`
- `tests/adapters/test_other_parsers.py`
