# US-24 — Cross-store consistency check for vector/graph indexes

**Tier:** Index reliability (cross-cutting) · **Depends on:** —
**Design reference:** none — raised while auditing what happens if `reindex`
is interrupted partway through.

## Story

As a `crm` user, I want `get_index_stats` to tell me if the vector store and
the graph store disagree on how many chunks are indexed, so that I notice a
half-finished or corrupted reindex instead of silently querying an
inconsistent index.

## Context

`index_project.py` writes to `vector_store`, `graph_store`, and
`lexical_index` as three separate, non-transactional steps
(`application/index_project.py:71-74`), and the manifest is deliberately
written last so an interrupted run leaves no manifest at all (comment at
lines 76-77 explains why). But if the process is interrupted *between* the
`vector_store.upsert` and `graph_store.upsert_nodes` calls — or a future
adapter swap has a bug — an old manifest can still exist while the two
stores hold different chunk counts, and nothing detects this today (confirmed
by grep: no integrity/consistency check exists anywhere in `src/`).

## Acceptance criteria

- [ ] `GetIndexStats.execute()` (`application/get_index_stats.py`)
      additionally calls `graph_store.nodes(project_id)` and compares
      `len(chunks)` (from `vector_store.list`) against `len(nodes)`.
- [ ] When the counts differ, the returned dict gains `"consistent": False`
      and a note naming both counts; when they match, `"consistent": True`.
      The field defaults to `True` when there's no manifest yet (nothing to
      be inconsistent about).
- [ ] `format_stats()` (`adapters/formatting.py`) surfaces the inconsistency
      as a leading warning line, e.g. `"⚠ vector store has 512 chunks but
      graph store has 498 — index may be corrupted or a reindex was
      interrupted. Run reindex."`
- [ ] Unit test with fake stores returning mismatched counts asserts
      `consistent=False` and the note names both numbers; matching counts
      assert `consistent=True`.

## Out of scope

- Automatic repair or re-indexing on detecting a mismatch — this story only
  surfaces the signal, the user still runs `reindex` manually.
- Checking the lexical index too — `SubstringLexicalIndex` (and any
  successor under US-05/US-11) reads chunks live from the vector store
  rather than persisting its own copy, so it structurally can't drift from
  it the same way (confirmed in `substring_lexical_index.py:19-20`).

## Files likely touched

- `src/coderagmanager/application/get_index_stats.py`
- `src/coderagmanager/adapters/formatting.py`
- `tests/application/test_get_index_stats.py`
