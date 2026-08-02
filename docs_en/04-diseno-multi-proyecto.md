# 04 · Multi-project design

## 1. The problem

You want a single `codehex` installation (one `pip install`, one MCP server running) that can move between several indexed repositories — your Java backend, your JS frontend, your Python library — without having to spin up a separate instance for each one.

This implies two distinct levels of state, which are better kept separate:

| Level | What it stores | Where it lives | Versioned in git? |
|---|---|---|---|
| **Global registry** | Which projects exist, where each one is, its configuration | `~/.codehex/projects.yaml` (outside any repo) | No — it's local to your machine |
| **Per-project state** | The index itself: vectors, graph, manifest with the indexed commit | `<project_root>/.codehex/` (inside each indexed repo) | Depends (chapter 10) — usually not on `main`, but is synced via CI |

## 2. The global registry

```yaml
# ~/.codehex/projects.yaml
projects:
  backend-java:
    root_path: /home/user/repos/mi-backend
    languages: [java]
    embedding_provider: voyage        # optional override; otherwise uses the global default
    last_indexed_commit: a3f9c21
    last_indexed_at: "2026-07-30T18:04:00Z"

  frontend-web:
    root_path: /home/user/repos/mi-frontend
    languages: [javascript, typescript]
    embedding_provider: local
    last_indexed_commit: null         # not indexed yet
    last_indexed_at: null

defaults:
  embedding_provider: local
  vector_store: lancedb
  top_k: 10
```

The `ProjectRegistry` port (chapter 03) is the only piece that reads/writes this file. The use cases (`RegisterProject`, `ListProjects`, `RemoveProject`, `GetProject`) depend on the port, never directly on the YAML format — so if in the future you switch to SQLite for the registry (for example, if it grows to hundreds of projects), you only touch the `YamlProjectRegistry` → `SqliteProjectRegistry` adapter.

```python
# ports/project_registry.py
from typing import Protocol
from domain.models import Project

class ProjectRegistry(Protocol):
    def register(self, name: str, root_path: str, languages: list[str]) -> Project: ...
    def get(self, project_id: str) -> Project: ...
    def list(self) -> list[Project]: ...
    def remove(self, project_id: str) -> None: ...
    def mark_indexed(self, project_id: str, commit: str) -> None: ...
```

## 3. Isolation between projects

Each project needs its own space within the vector store and the dependency graph — results from two different repos should never mix in the same search unless explicitly requested. This is solved with `project_id` as the partition key:

- **Vector store**: one collection/table per project (LanceDB and Chroma support this natively — see chapter 06), named deterministically from the `project_id`.
- **Graph**: one index file per project (`<root>/.codehex/graph.json`), or a table filtered by `project_id` if you use a single shared store.
- **Global registry**: one entry per project, as shown above.

This partitioning is precisely why every method of `VectorStore`/`GraphStore` in chapter 03 takes `project_id` as its first parameter — it's not a minor detail, it's the design seam that makes multi-project support possible without each port having to "know" about projects (the port only operates "within a named space"; who that space belongs to is always decided by the application layer).

## 4. Management commands (preview of chapter 11)

```bash
codehex project add backend-java /home/user/repos/my-backend
codehex project list
codehex project remove backend-java
codehex index --project backend-java
codehex search "credit card validation" --project backend-java
```

The MCP server (chapter 08) exposes the equivalent of `project list` as a tool (`list_projects`) and, if the client doesn't specify a project on each call, can set an "active" project for the session (`use_project`) — or, simpler for a first version, require `project_id` as a mandatory parameter on every tool, leaving it to the LLM agent to state it explicitly (more explicit, less state to manage).

## 5. The pattern that already solves this: `kairosai`'s multi-repo registry

`kairosai` doesn't do RAG, but it already solved exactly this problem for an adjacent use case: each **workspace** in `kairosai` registers a list of `repos` (name, source URL) in its `manifest.yaml`, and when the workspace is "installed," each repo is cloned/updated in `runtimes/<workspace>/repos/<name>/` independently.

The correspondence with this chapter's design:

| kairosai | codehex |
|---|---|
| `workspace` with a list of `repos` in `manifest.yaml` | global registry `~/.codehex/projects.yaml` with a list of projects |
| per-repo clone/update in `install.py` | per-project indexing/reindexing (chapter 07) |
| each cloned repo is independent of the rest | each indexed project (vector store collection + graph) is independent of the rest |

The deliberate design difference: `kairosai` ties the repo registry to a *workspace* with inheritance and shared configuration (appropriate for its use case, managing Claude configuration). `codehex` doesn't need that level — a flat project registry is enough because there's no "inheritance" of index between projects: each one is indexed and queried completely independently. If in the future you want to group projects (e.g. "all services in the same domain") you can add a label/tag to the registry without needing to reintroduce the full workspace concept.

## Reusable ideas from the existing projects

- **From `kairosai`**: the register-by-name pattern with sync state (`last_indexed_commit` here, equivalent to tracking what's cloned/updated there) and the project-root discovery pattern (`find_project_root()` walking up directories looking for a marker folder) — reusable so that `codehex` can automatically detect whether the current directory belongs to an already-registered project, without the user always having to pass `--project`.

## Next step

[05 · Multi-language parsing](05-parsing-multilenguaje.md): how the `LanguageParser` is implemented in practice for Python, JavaScript, Java, and any future language.
