# US-28 — Dedicated TypeScript/TSX parser (stop losing typed React components)

**Tier:** Language coverage (cross-cutting) · **Depends on:** —
**Design reference:** none — raised while empirically verifying how `.tsx`
files with typed props are parsed today.

## Story

As an agent searching a TypeScript/React codebase, I want interfaces, type
aliases, enums, and typed function/component declarations to be indexed as
real chunks, so that the majority of a typical TS+React codebase — which
types its props and return values — isn't silently invisible to search.

## Context

Empirical reproduction, not hypothetical. Parsing a representative `.tsx`
file through the real `TreeSitterJavaScriptParser.parse()`:

```tsx
interface Props { name: string; count?: number; }

export function Greeting(props: Props): JSX.Element {
  const [n, setN] = React.useState<number>(0);
  return <div className="x">{props.name}: {n}</div>;
}

export const Counter: React.FC<Props> = ({ name }) => {
  return <span>{name}</span>;
};

export function PlainComponent(props) {
  return <div>{props.label}</div>;
}
```

produces exactly **1 chunk out of 3 real declarations** — only
`PlainComponent`, the one untyped function, survives. `tree.root_node
.has_error` is `True`, with `ERROR` nodes wrapping exactly the parts with TS
syntax: `interface Props`, the `function Greeting(props: Props)` signature,
and the `const Counter: React.FC<Props>` declarator. Root cause: the JS
grammar (confirmed — `pyproject.toml` has no `tree-sitter-typescript`
dependency at all) doesn't understand TypeScript type syntax embedded in
otherwise-valid code, and corrupts the surrounding node instead of just
skipping the type annotation. This isn't an edge case: typing props/returns
is the standard, idiomatic way to write TypeScript React components. Every
chunk parsed from a `.ts`/`.tsx` file is also currently hardcoded
`language="javascript"` (`tree_sitter_javascript.py:58`), so `--language
typescript` never returns anything, in any project.

## Acceptance criteria

- [ ] New dependency `tree-sitter-typescript` in `pyproject.toml`, providing
      the dedicated `typescript` and `tsx` grammars (two distinct grammars
      from the same package — `.tsx` needs the TSX-aware one to parse JSX
      and TS types together; `.ts` doesn't need JSX support).
- [ ] New adapter `adapters/parsers/tree_sitter_typescript.py`:
      `TreeSitterTypeScriptParser`. `supports()` claims `.ts`/`.tsx` only,
      selecting the `typescript` vs. `tsx` grammar internally by extension.
      Every chunk it produces has `language="typescript"` (never
      `"javascript"`), regardless of whether the source file is `.ts` or
      `.tsx`.
- [ ] `TreeSitterJavaScriptParser.EXTENSIONS` (`tree_sitter_javascript.py:16`)
      narrowed to `(".js", ".jsx")` only — `.ts`/`.tsx` no longer dispatch
      there, removing the ambiguity of two parsers both claiming the same
      extension.
- [ ] `CHUNK_NODE_TYPES` for the new parser includes, at minimum, everything
      the JS parser already captures (function/class/method declarations,
      arrow function assigned to a `const`, typed or not) **plus** TS-only
      declarations: `interface_declaration`, `type_alias_declaration`,
      `enum_declaration` — each with an appropriate `kind` (`"interface"`,
      `"type"`, `"enum"`), mirroring the `KIND_BY_NODE_TYPE` mapping pattern
      already used in `tree_sitter_java.py`.
- [ ] `implements_clause` extraction (already a pattern in
      `tree_sitter_java.py`) ported for TS classes implementing interfaces,
      reusing the existing `EdgeType.IMPLEMENTS`.
- [ ] Regression test reproducing the exact fixture from this story's
      Context: a `.tsx` file with an interface, a typed function component,
      and a typed `React.FC` const must produce 3+ chunks (not 1), including
      one with `kind="interface"`, and every chunk's `language` field must
      read `"typescript"`.
- [ ] `composition_root.build_parser()` registers the new parser (ordering
      relative to the narrowed JS parser doesn't matter once their
      extensions are disjoint).
- [ ] `tests/fixtures/sample_repo/` gains a `.tsx` fixture file exercising
      typed props/interfaces — closes the "zero TypeScript test coverage"
      gap confirmed during this audit (today the fixture repo has Python,
      one `.js`, and one `.java` file, but no `.ts`/`.tsx` at all).

## Out of scope

- Plain `.jsx`/`.js` handling — untouched, stays on
  `TreeSitterJavaScriptParser` (already confirmed to parse untyped JSX
  correctly, `has_error: False`).
- The general "a claimed parser can return zero chunks with no fallback"
  dispatch-level safety net — that's US-30. This parser benefits from it
  once it lands, but US-30 isn't a prerequisite for this story.
- CSS-in-JS, styled-components, Tailwind utility strings, or any non-`.css`
  styling pattern embedded in TS/TSX — no evidence gathered on those, not
  addressed here.

## Files likely touched

- `pyproject.toml`
- `src/coderagmanager/adapters/parsers/tree_sitter_typescript.py` (new)
- `src/coderagmanager/adapters/parsers/tree_sitter_javascript.py`
  (`EXTENSIONS` narrowed)
- `src/coderagmanager/composition_root.py`
- `tests/fixtures/sample_repo/src/*.tsx` (new)
- `tests/adapters/test_tree_sitter_typescript.py` (new)
