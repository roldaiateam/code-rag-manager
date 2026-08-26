# US-29 — Dedicated CSS parser (selectors/rules as structured chunks)

**Tier:** Language coverage (cross-cutting) · **Depends on:** —
**Design reference:** none — raised while confirming `.css` gets identical
treatment to any unstructured text file.

## Story

As an agent searching a frontend codebase, I want CSS rules to be indexed as
named, structural chunks (by selector) instead of arbitrary 60-line text
windows, so that I can find "where is `.button` styled" the same way I can
find a function by name.

## Context

Empirically confirmed: parsing a `.css` file through the real
`CompositeLanguageParser` (with the current Python/JS/Java/generic stack)
produces `language="text"`, `kind="block"` chunks — `.css` isn't claimed by
any dedicated parser, so it falls straight to `GenericTextParser`. Chunk
boundaries come from a fixed line count with no relationship to the file's
actual rule boundaries; there's no selector, no `@media`/`@keyframes`
structure, and no `@import` relationship extraction.

## Acceptance criteria

- [ ] New dependency `tree-sitter-css` in `pyproject.toml`.
- [ ] New adapter `adapters/parsers/tree_sitter_css.py`: `TreeSitterCssParser`.
      `supports()` claims `.css` only (see Out of scope for SCSS/LESS).
- [ ] Each top-level `rule_set` becomes a chunk: `symbol` = the selector text
      as written (e.g. `.button:hover`), `kind="rule"`, `language="css"`.
- [ ] Each top-level `media_statement`/`keyframes_statement` becomes its own
      chunk (`kind="media"` / `kind="keyframes"` respectively), containing
      its nested rules as its `source_text` rather than exploding each
      nested rule into its own chunk — keeps an `@media` block readable as a
      unit, consistent with how a class isn't split into "half a class"
      elsewhere in the codebase.
- [ ] `@import` statements extracted as `EdgeType.IMPORTS` edges. CSS
      imports reference a file path, not a symbol name, so this is
      recorded as an edge whose target is the literal imported path (not
      run through `resolve_edges`'s by-name resolution, which doesn't apply
      here) — document this distinction where the edge is built.
- [ ] Unit test: a fixture with 2+ selectors, one `@media` block, and one
      `@import` produces the expected chunk count/kinds and the import edge.
- [ ] `composition_root.build_parser()` registers the new parser.

## Out of scope

- SCSS/LESS/Sass — different grammars, nesting semantics, and (for Sass) an
  indentation-based syntax; no evidence gathered here on `tree-sitter-scss`'s
  maturity or exact node shapes. Follow-on story if this one proves useful.
- CSS Modules class-name-to-component linking, or any cross-referencing
  between a `.css` selector and the component that uses it — no such edge
  exists in the codebase today for any language; out of scope here.
- CSS-in-JS (styled-components, emotion, Tailwind utility strings) — those
  live inside `.js`/`.tsx` files and are a `TreeSitterTypeScriptParser`/
  `TreeSitterJavaScriptParser` concern if ever tackled, not this parser's.

## Files likely touched

- `pyproject.toml`
- `src/coderagmanager/adapters/parsers/tree_sitter_css.py` (new)
- `src/coderagmanager/composition_root.py`
- `tests/fixtures/sample_repo/src/*.css` (new)
- `tests/adapters/test_tree_sitter_css.py` (new)
