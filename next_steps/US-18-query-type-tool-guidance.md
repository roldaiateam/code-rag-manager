# US-18 — Query-type-aware tool guidance (docstrings + README)

**Tier:** Documentation / agent guidance (cross-cutting) · **Depends on:** —
(soft dependency: revisit once US-02 lands to reference its low-confidence
notice)
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §2.2`

## Story

As an agent deciding which MCP tool to call for a given question, I want
each tool's own description to tell me explicitly which kind of question it
resolves best (and which it doesn't), so that I pick the right tool for
localización/conceptual/estructural/trampa questions without having to infer
it from a generic "search first, then explore" ordering.

## Context

Two things get conflated easily, and this story is only about the second
one:

- **Semantic vs. lexical, inside `search_code`** — this is **not** an agent
  decision and needs no guidance: `search_code` always runs both channels
  and merges them via `merge_and_rerank` (§2.1, and the worked example in
  this conversation). There is no tool-choice problem here because the
  system already resolves it internally.
- **Which of the ~5-6 MCP tools to call at all** (`search_code` vs.
  `get_dependency_chain` vs. `get_source` vs. `list_chunks` vs., once built,
  `search_related_projects`) — **this is a real, currently underserved gap.**
  Today `crm`'s tool docstrings (per the `FINAL-DESIGN.md §10` sketch) are
  fairly generic ("Searches for relevant code by meaning and by lexical
  match... use it as the FIRST step"), and `README.md` only offers a single
  generic ordering (`get_index_stats` → `search_code` →
  `get_dependency_chain` → `get_source`) — it never explicitly says
  *"a question about who implements/calls something is structural, not
  semantic — `search_code` won't resolve it well, use
  `get_dependency_chain`"*.

`code-rag-mcp`'s README already has the pattern to copy: every tool is
documented with an explicit **"Cuándo usarlo" / "Cuándo NO usarlo"** pair,
plus worked end-to-end examples (e.g. "investigar un bug en la creación de
productos"). `crm` has never ported this documentation pattern — this story
does that, anchored to the 4 query categories from the design doc instead of
being generic.

## Acceptance criteria

- [ ] Each MCP tool's docstring (`search_code`, `get_dependency_chain`,
      `get_source`, `list_chunks`, `get_index_stats`, `reindex`, and — once
      it exists — `search_related_projects`) is rewritten with an explicit
      "When to use it / When NOT to use it" pair, each one naming which of
      the 4 categories (localización / conceptual / estructural / trampa) it
      resolves, e.g.:
      - `search_code`: *"Use for localización and conceptual questions —
        combines semantic and lexical search internally, you don't need to
        choose between them. Do NOT use for 'who implements/calls X'
        questions (structural) — use `get_dependency_chain` instead."*
      - `get_dependency_chain`: *"Use for estructural questions (who
        implements/calls/depends on X). Do NOT use for keyword search — use
        `search_code`."*
      - `list_chunks`: *"Use for a full inventory of a category (all
        controllers, all entities...). Results have no relevance
        scoring — do NOT use it as a substitute for `search_code`."*
- [ ] Once US-02 (confidence threshold) lands, `search_code`'s docstring is
      updated to state explicitly: a low-confidence notice is evidence
      toward "this may not exist" (trampa category) — the agent should not
      treat it as "keep searching harder," and should say so to the user
      when relevant.
- [ ] `README.md` gains a decision table mirroring
      `PLAN-MEJORA-CODE-RAG-MANAGER.md §2.2` (category → example → which
      tool resolves it → why), operationalizing that section instead of
      leaving it only in the internal design document.
- [ ] `README.md`'s existing generic ordering
      (`get_index_stats → search_code → get_dependency_chain → get_source`)
      is kept as the *default exploration path*, but the new table makes
      clear when to deviate from it (e.g. jump straight to
      `get_dependency_chain` for a structural question).
- [ ] At least one worked example per category added to `README.md`, same
      spirit as `code-rag-mcp`'s "Ejemplo: investigar un bug..." section,
      adapted to `crm`'s own tool set.

## Out of scope

- Any change to `merge_and_rerank`, `search_code`'s internal semantic/lexical
  combination, or any scoring logic — this story is documentation/docstrings
  only, no behavior change.
- Tool selection automation (e.g. `crm` itself routing the query to a tool)
  — out of scope; the goal is better-informed agent decision-making via
  documentation, not a new routing layer.

## Files likely touched

- `src/coderagmanager/adapters/mcp/server.py` (tool docstrings)
- `README.md` (decision table + worked examples)
