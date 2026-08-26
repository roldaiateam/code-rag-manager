# US-31 — Atomic writes for `crm`'s own state files (`graph.json`, `manifest.json`, `projects.yaml`)

**Tier:** Index reliability (cross-cutting) · **Depends on:** —
**Design reference:** none — raised while checking what happens when a
running MCP server and a concurrent `crm reindex` touch the same state.

## Story

As a `crm` user running `crm reindex --project X` while an MCP server for
that same project is actively answering tool calls — a normal workflow, not
an exotic one — I want reads of `graph.json`/`manifest.json`/
`~/.crm/projects.yaml` to never see a partially-written file, so that this
ordinary overlap doesn't produce an unhandled crash or a silently corrupted
read.

## Context

Grep across all of `src/` for `lock`, `fsync`, `atomic`, `tempfile`,
`NamedTemporaryFile`, `os.replace`: zero results. Confirmed by reading the
three write sites directly — all three use the same unsafe pattern,
`open(path, "w")` followed by `json.dump`/`yaml.safe_dump`, with no
temp-file-plus-rename step:

- `JsonGraphStore._save()` (`adapters/storage/json_graph_store.py:28-31`)
- `write_manifest()` (`application/manifest.py:24-27`)
- `YamlProjectRegistry._save()` (`adapters/registry/yaml_project_registry.py:27-30`)

None of the matching readers (`JsonGraphStore._load()`, `read_manifest()`,
`YamlProjectRegistry._load()`) catch a parse error either — a reader that
opens the file mid-write today gets an unhandled `JSONDecodeError` (or
`yaml.YAMLError`) propagating straight up through whatever MCP tool call
triggered it.

**Checked and ruled out, for the record**: this is *not* about a stale
in-memory cache. A long-lived `LanceDbVectorStore` connection (simulating the
MCP server process) was verified empirically to see fresh data immediately
after an external process drops and rebuilds the same table — LanceDB's own
on-disk format handles this correctly, no bug there. The exposure is
specifically the three plain JSON/YAML files above, which have no such
protection.

**Why the exposure window is real and growing**: `~/.crm/projects.yaml` is a
single **global** file shared by every project and every `crm` process on the
machine, not one per project. And the set of code paths reading these three
files on every single tool call is expanding, not shrinking — US-22's
staleness check reads the manifest on every `search_code`/`get_dependency_chain`/
`get_source` call, and US-24's cross-store consistency check reads both the
vector store and `graph_store.nodes()` on every `get_index_stats` call. Both
widen the window in which a read can land mid-write during a concurrent
`reindex`.

## Acceptance criteria

- [ ] New shared helper, `adapters/storage/atomic_write.py`, exposing
      `atomic_write_json(path, data)` and `atomic_write_text(path, text)`:
      writes to a sibling temporary file in the same directory (so the
      final `os.replace()` stays on the same filesystem — required for
      atomicity), then `os.replace(tmp_path, path)`.
- [ ] `JsonGraphStore._save()`, `write_manifest()`, and
      `YamlProjectRegistry._save()` are switched to use this helper instead
      of their current direct `open(path, "w")` + dump.
- [ ] `JsonGraphStore._load()`, `read_manifest()`, and
      `YamlProjectRegistry._load()` wrap their parse call in a
      try/except for the relevant parse-error type, with **one** bounded
      retry (short fixed backoff, e.g. a few tens of milliseconds) before
      re-raising with a clear, actionable message (naming the file and that
      a concurrent write may be in progress) instead of the raw parser
      traceback. Documented explicitly as *not* a full transactional
      guarantee — closing the realistic gap given these files' actual
      sizes, not a substitute for real locking.
- [ ] Unit test: a deliberately truncated/invalid JSON file, written just
      before the loader runs, is either recovered by the retry (if a valid
      write lands within the backoff window) or fails with the new clear
      error message — never an unhandled traceback.
- [ ] Unit test: normal sequential save-then-load round trips for all three
      files are unaffected — no behavior change in the non-concurrent case.
- [ ] All three adapters (`JsonGraphStore`, `manifest.py`,
      `YamlProjectRegistry`) go through the one shared helper rather than
      three separate ad hoc implementations.

## Out of scope

- Real cross-process mutual exclusion (e.g. a lockfile preventing two
  concurrent `crm reindex` runs on the same project from racing each other)
  — this story only protects readers from torn reads of already-written
  files, not two writers racing. Worth a follow-up story if that scenario
  turns out to matter in practice.
- LanceDB's own on-disk consistency — verified empirically in this story's
  Context to already behave correctly; not touched here.

## Files likely touched

- `src/coderagmanager/adapters/storage/atomic_write.py` (new)
- `src/coderagmanager/adapters/storage/json_graph_store.py`
- `src/coderagmanager/application/manifest.py`
- `src/coderagmanager/adapters/registry/yaml_project_registry.py`
- `tests/adapters/test_atomic_write.py` (new)
- `tests/adapters/test_json_graph_store.py`,
  `tests/adapters/test_yaml_project_registry.py` (torn-read cases)
