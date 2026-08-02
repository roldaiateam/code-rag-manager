# FINAL-DESIGN · CodeRagManager (`crm`)

## 0. Purpose of this document

`code-rag-guide` (chapters `00`-`13`) teaches **how to think about** each piece of a code-RAG manager and deliberately leaves several decisions open ("you choose based on your case"). This document takes **each of those open decisions** and settles it, so you can start writing code without further reading or pending design decisions.

It does not replace the guide: for the *why* of each piece (what an embedding is, why hexagonal architecture, etc.) it still links to the corresponding chapters. This document is the **concrete final snapshot**, not the reasoning.

Project name: **CodeRagManager**. CLI command: **`crm`**. Replaces the `codehex` placeholder used in the guide.

## 1. Decision table

| Open point in the guide | Decision made | Reason / reference |
|---|---|---|
| Reindexing (chapter [07](07-indexacion-incremental.md)) | **Always full** (drop-and-rebuild), no incremental diff | Simplicity for v1, local, single developer. Consistent with milestones M0-M5 of the original guide, where incremental doesn't appear until M6 |
| Scope of the MCP server (chapter [04](04-diseno-multi-proyecto.md) §4 vs [08](08-servidor-mcp.md) §5) | **One MCP server per project**, started with `--project <id>` | Real precedent: `kairosai/src/kairosai/coderag.py` already registers a `code-rag-<repo>` server per cloned repo. The agent never chooses a project — there's only one in the session |
| Embedding provider (chapter [06](06-embeddings-vector-store.md) §1) | **Lightweight local model** (`sentence-transformers`, `all-MiniLM-L6-v2`), only adapter in v1 | Free, no network, no API key — get started tomorrow |
| Languages v1 (chapter [05](05-parsing-multilenguaje.md)) | **Python + JavaScript + Java** (tree-sitter) + `GenericTextParser` fallback | Full coverage of the trio the guide uses by default |
| GitHub Actions (chapter [10](10-github-actions.md)) | **Included in v1**, greatly simplified (section 13) | Since there's no incremental mode, there's no need for `fetch-depth:0`, restoring a previous index, or API secrets |
| Layer/role classification (chapter [02](02-code-rag-particularidades.md) §5, [05](05-parsing-multilenguaje.md) §5) | **Omitted in v1** | Explicit optional enrichment in the guide; deferred |
| `get_source` (chapter [01](01-fundamentos-rag.md) §4, [06](06-embeddings-vector-store.md)) | **Full `source_text` is stored in the index** | No re-reading from disk; the index is self-contained |
| Lexical retrieval (chapter [01](01-fundamentos-rag.md) §6, [06](06-embeddings-vector-store.md) §3) | **Simple substring lexical match** over `symbol`/`file_path`, no BM25 | Micro-decision not explicitly covered before; resolved with the same "start simple" criterion as the rest of the table |

## 2. Name and conventions

| Element | Value |
|---|---|
| Python package (import) | `coderagmanager` |
| CLI command | `crm` |
| Global project registry | `~/.crm/projects.yaml` |
| Per-project state | `<project_root>/.crm/` (LanceDB table + `graph.json` + `manifest.json`) |
| CI publishing branch | `crm-index` |
| MCP server entry name | `crm-<project_id>` (e.g. `crm-backend-java`) |
| Package entry point | `crm = "coderagmanager.adapters.cli.main:app"` |

## 3. Domain model

`src/coderagmanager/domain/models.py` — no external dependencies, adapted from chapter [03](03-arquitectura-hexagonal.md) §3:

```python
from dataclasses import dataclass, field
from enum import Enum

class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"

@dataclass(frozen=True)
class CodeChunk:
    id: str                      # stable hash (path + symbol + start line)
    project_id: str
    language: str                 # "python" | "javascript" | "java" | "text"
    symbol: str
    kind: str                     # "function" | "class" | "method" | "block" | ...
    file_path: str
    start_line: int
    end_line: int
    source_text: str              # ALWAYS persisted in full (fixed decision)
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)   # signature/docstring; no layer/role in v1

@dataclass(frozen=True)
class DependencyEdge:
    source_chunk_id: str
    target_chunk_id: str
    edge_type: EdgeType

@dataclass(frozen=True)
class Project:
    id: str
    name: str
    root_path: str
    languages: list[str]
    last_indexed_commit: str | None = None
    last_indexed_at: str | None = None

@dataclass(frozen=True)
class SearchQuery:
    text: str                     # WITHOUT project_id: set by the MCP server at startup
    top_k: int = 10
    language: str | None = None
    kind: str | None = None

@dataclass(frozen=True)
class SearchResult:
    chunk: CodeChunk
    score: float
    match_reason: str            # "semantic" | "lexical" | "hybrid"
```

`project_id` **disappears from `SearchQuery`** (from the MCP user's perspective) but **remains in the port signatures** (`VectorStore`, `GraphStore`, `LexicalIndex` — section 6) to preserve multi-project isolation in storage. See section 11 for how this is reconciled in the MCP adapter.

## 4. Folder layout

Adapted from chapter [03](03-arquitectura-hexagonal.md) §7:

```
coderagmanager/
├── pyproject.toml
├── src/coderagmanager/
│   ├── domain/
│   │   └── models.py
│   ├── ports/
│   │   ├── language_parser.py
│   │   ├── embedding_provider.py
│   │   ├── vector_store.py
│   │   ├── graph_store.py
│   │   ├── lexical_index.py
│   │   ├── git_provider.py
│   │   └── project_registry.py
│   ├── application/
│   │   ├── index_project.py       # the only indexing use case (full, always)
│   │   ├── search_code.py
│   │   ├── get_dependency_chain.py
│   │   ├── get_source.py
│   │   ├── list_chunks.py
│   │   ├── get_index_stats.py
│   │   ├── register_project.py
│   │   ├── list_projects.py
│   │   └── remove_project.py
│   ├── adapters/
│   │   ├── parsers/
│   │   │   ├── tree_sitter_python.py
│   │   │   ├── tree_sitter_javascript.py
│   │   │   ├── tree_sitter_java.py
│   │   │   └── generic_text.py
│   │   ├── embeddings/
│   │   │   └── local_provider.py       # only adapter in v1
│   │   ├── storage/
│   │   │   ├── lancedb_vector_store.py
│   │   │   ├── json_graph_store.py
│   │   │   └── substring_lexical_index.py
│   │   ├── git/git_cli_provider.py     # only head()
│   │   ├── registry/yaml_project_registry.py
│   │   ├── cli/
│   │   └── mcp/
│   │       ├── server.py
│   │       └── client_configs/         # ClaudeConfigWriter, CodexConfigWriter, CopilotConfigWriter
│   └── composition_root.py
├── .github/workflows/reindex.yml
└── tests/
    ├── domain/
    ├── application/
    └── adapters/
```

## 5. Ports

Adapted from chapter [03](03-arquitectura-hexagonal.md) §4, with fixed trims:

```python
# ports/language_parser.py
class LanguageParser(Protocol):
    def supports(self, file_path: str) -> bool: ...
    def parse(self, project_id: str, file_path: str, source: str) -> tuple[list[CodeChunk], list[DependencyEdge]]: ...

# ports/embedding_provider.py
class EmbeddingProvider(Protocol):
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def dimensions(self) -> int: ...

# ports/vector_store.py — drop() replaces delete() by ids: no need for selective deletion
class VectorStore(Protocol):
    def drop(self, project_id: str) -> None: ...
    def upsert(self, project_id: str, chunks: list[CodeChunk]) -> None: ...
    def search(self, project_id: str, query_embedding: list[float], top_k: int) -> list[SearchResult]: ...

# ports/graph_store.py
class GraphStore(Protocol):
    def drop(self, project_id: str) -> None: ...
    def upsert_edges(self, project_id: str, edges: list[DependencyEdge]) -> None: ...
    def dependency_chain(self, project_id: str, symbol: str, max_depth: int, direction: str) -> list[DependencyEdge]: ...

# ports/lexical_index.py — NEW compared to the original guide: explicitly resolves section 6 §3
class LexicalIndex(Protocol):
    def index(self, project_id: str, chunks: list[CodeChunk]) -> None: ...
    def search(self, project_id: str, text: str, top_k: int) -> list[SearchResult]: ...

# ports/git_provider.py — TRIMMED: no diff_since or working_tree_changes (no incremental)
class GitProvider(Protocol):
    def head(self, repo_path: str) -> str: ...

# ports/project_registry.py — same as chapter 04
class ProjectRegistry(Protocol):
    def register(self, name: str, root_path: str, languages: list[str]) -> Project: ...
    def get(self, project_id: str) -> Project: ...
    def list(self) -> list[Project]: ...
    def remove(self, project_id: str) -> None: ...
    def mark_indexed(self, project_id: str, commit: str) -> None: ...
```

## 6. Indexing — always full (drop-and-rebuild)

**Why drop-and-rebuild and not just "reparse everything without a diff":** if you only reparse and `upsert`, chunks from files deleted or renamed since the last index would remain orphaned forever (never deleted). Emptying the project's table and graph before rebuilding is what makes "no diff logic" still **correct**, not a leaky shortcut.

**File discovery**: use `git ls-files --cached --others --exclude-standard` over the project's `root_path` — it respects `.gitignore` automatically without reimplementing its parser, and we already use `git` as a dependency. If the directory isn't a git repo, fall back to a directory walk with a minimal exclusion list (`.git`, `node_modules`, `target`, `build`, `dist`, `venv`, `.venv`, `__pycache__`).

```python
# application/index_project.py
class IndexProject:
    def __init__(self, project_id: str, root_path: str,
                 parser: LanguageParser, embedder: EmbeddingProvider,
                 vector_store: VectorStore, graph_store: GraphStore,
                 lexical_index: LexicalIndex, git: GitProvider):
        self._project_id, self._root_path = project_id, root_path
        self._parser, self._embedder = parser, embedder
        self._vector_store, self._graph_store = vector_store, graph_store
        self._lexical_index, self._git = lexical_index, git

    def execute(self) -> IndexStats:
        self._vector_store.drop(self._project_id)
        self._graph_store.drop(self._project_id)

        chunks, edges = [], []
        for file_path, source in discover_files(self._root_path):
            if not self._parser.supports(file_path):
                continue
            file_chunks, file_edges = self._parser.parse(self._project_id, file_path, source)
            chunks.extend(file_chunks)
            edges.extend(file_edges)

        embeddings = self._embedder.embed_batch([c.source_text for c in chunks])
        chunks = [replace(c, embedding=e) for c, e in zip(chunks, embeddings)]

        self._vector_store.upsert(self._project_id, chunks)
        self._graph_store.upsert_edges(self._project_id, edges)
        self._lexical_index.index(self._project_id, chunks)

        write_manifest(self._root_path, IndexManifest(
            project_id=self._project_id,
            last_indexed_commit=self._git.head(self._root_path),
            last_indexed_at=now_iso(),
            total_chunks=len(chunks), total_edges=len(edges),
        ))
        return IndexStats(total_chunks=len(chunks), total_edges=len(edges))
```

**There is no `ReindexProject` as a separate use case.** The `reindex` command (CLI and MCP tool) calls this exact same `IndexProject.execute()`. It's idempotent by construction (drop + rebuild).

**Manifest** (`<root>/.crm/manifest.json`), same as chapter [07](07-indexacion-incremental.md) §4, informational only (it doesn't govern any diff logic):

```json
{
  "project_id": "backend-java",
  "last_indexed_commit": "a3f9c21",
  "last_indexed_at": "2026-07-31T10:15:00Z",
  "total_chunks": 1842,
  "total_edges": 3021
}
```

**Note on future evolution** (not implemented now): if a project grows enough that a full `reindex` becomes slow or expensive, that's the moment to revisit chapter [07](07-indexacion-incremental.md) and introduce the incremental algorithm based on `git diff` — today, deliberately, not.

## 7. Embeddings

Only adapter in v1 — chapter [06](06-embeddings-vector-store.md) §1:

```python
# adapters/embeddings/local_provider.py
from sentence_transformers import SentenceTransformer

class LocalSentenceTransformerProvider:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, batch_size=32, show_progress_bar=False).tolist()

    def dimensions(self) -> int:
        return self._model.get_sentence_embedding_dimension()
```

The `EmbeddingProvider` port continues to exist just as in chapter 06 so Voyage/Qwen3 can be added later without touching anything else — but **it is not implemented in v1**.

## 8. Storage

- **Vectors**: `LanceDbVectorStore` (chapter [06](06-embeddings-vector-store.md) §2), one table per project (`project_<id>`), with `drop()`/`upsert()`/`search()` per the trimmed port. Each row includes the full `source_text` (fixed decision, section 1).
- **Graph**: `JsonGraphStore`, one `<root>/.crm/graph.json` file per project, loaded into memory with `chunksByFqcn`/`outEdges`/`inEdges` maps (pattern from `code-rag-mcp/CodeSearcher.java`) and BFS for `dependency_chain()`. `drop()` simply empties the file before `upsert_edges()`.
- **Lexical**: `InMemorySubstringLexicalIndex` — scores by the number of substring matches of the query in `symbol` and `file_path` (no BM25). It's fully rebuilt on every `index()`, just like the other two.
- **Global registry**: `YamlProjectRegistry` over `~/.crm/projects.yaml`, same as chapter [04](04-diseno-multi-proyecto.md) §2.

All of them share the same lifecycle: **drop + full rebuild on every index run**, never a partial incremental update.

## 9. Parsers v1

Via tree-sitter, chapter [05](05-parsing-multilenguaje.md) §2, without layer/role classification (fixed decision):

| Language | Extension(s) | Node types → chunk |
|---|---|---|
| Python | `.py` | `function_definition`, `class_definition` |
| JavaScript/TypeScript | `.js`, `.ts`, `.jsx`, `.tsx` | `function_declaration`, `class_declaration`, `arrow_function` assigned to `const` |
| Java | `.java` | `method_declaration`, `class_declaration`, `interface_declaration`, `record_declaration` |

Relationships extracted by all of them (chapter 05 §3): `import_statement`/`import_from_statement` → `IMPORTS`; `call` → `CALLS`; `extends_clause`/superclasses → `EXTENDS`; `implements_clause` → `IMPLEMENTS`.

`GenericTextParser` (chapter 05 §4) as the always-last fallback in `CompositeLanguageParser`, for any text file without a dedicated adapter (60-line window, overlap of 10, no edges).

## 10. MCP server — one server per project

Resolves the tension found between chapters [04](04-diseno-multi-proyecto.md) §4 and [08](08-servidor-mcp.md) §5: **the `project_id` is fixed once when the process starts** (`--project <id>`), it isn't requested on every call. Internally, the `composition_root` builds the use cases already bound to that `project_id`; the MCP tools don't expose it.

```python
# adapters/mcp/server.py
from mcp.server.fastmcp import FastMCP
import argparse
from coderagmanager.composition_root import build_use_cases

parser = argparse.ArgumentParser()
parser.add_argument("--project", required=True)
args, _ = parser.parse_known_args()

mcp = FastMCP(f"crm-{args.project}")
uc = build_use_cases(project_id=args.project)   # binds project_id across all use cases

@mcp.tool()
def search_code(query: str, top_k: int = 10, language: str | None = None, kind: str | None = None) -> str:
    """Searches for relevant code by meaning and by lexical match in THIS project.
    Use it as the FIRST step when exploring the code, before reading files directly."""
    result = uc["search_code"].execute(SearchQuery(text=query, top_k=top_k, language=language, kind=kind))
    return format_search_results(result)

@mcp.tool()
def get_dependency_chain(symbol: str, max_depth: int = 3, direction: str = "both") -> str:
    """Walks the dependency graph from `symbol` (what it implements, what calls it...)."""
    return format_chain(uc["get_dependency_chain"].execute(symbol, max_depth, direction))

@mcp.tool()
def get_source(symbol: str | None = None, file_path: str | None = None,
                start_line: int | None = None, end_line: int | None = None) -> str:
    """Reads the actual source code of a chunk. Use AFTER search_code/get_dependency_chain."""
    if symbol is None and file_path is None:
        raise ValueError("You must provide 'symbol' or 'file_path'.")
    return uc["get_source"].execute(symbol, file_path, start_line, end_line)

@mcp.tool()
def list_chunks(language: str | None = None, kind: str | None = None) -> str:
    """Filtered inventory of chunks indexed in this project."""
    return format_chunks(uc["list_chunks"].execute(language, kind))

@mcp.tool()
def get_index_stats() -> str:
    """Index size and indexed commit for this project. Recommended first contact."""
    return format_stats(uc["get_index_stats"].execute())

@mcp.tool()
def reindex() -> str:
    """Rebuilds the full index for this project (picks up local uncommitted changes)."""
    stats = uc["index_project"].execute()
    return f"Reindexed: {stats.total_chunks} chunks, {stats.total_edges} edges"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**Final tool surface (6 tools, no `project_id`, no `list_projects`/`use_project` as MCP tools)**: `search_code`, `get_dependency_chain`, `get_source`, `list_chunks`, `get_index_stats`, `reindex`. `list_projects`/`project add`/`project remove` remain **CLI-only** commands (section 12) — they don't make sense as MCP tools when the server is already bound to a single project.

## 11. Client integration

One `.mcp.json` (or equivalent) **per repo**, versioned inside that repo, always pointing to that project. No API key environment variable (local model, section 7):

```json
{
  "mcpServers": {
    "crm-backend-java": {
      "type": "stdio",
      "command": "crm",
      "args": ["mcp", "serve", "--project", "backend-java"]
    }
  }
}
```

`crm mcp install --client claude|codex|copilot --project <id>` generates this entry (named `crm-<id>`) in the corresponding format (`.mcp.json`, `.codex/config.toml`, `.github/mcp.json` or `~/.copilot/mcp-config.json`), following the pattern from chapter [09](09-integracion-clientes.md) §5.

## 12. GitHub Actions (simplified)

No incremental → no `fetch-depth: 0`, no "restore previous index". No paid embeddings → no secrets.

```yaml
# .github/workflows/reindex.yml
name: Reindex code-RAG

on:
  push:
    branches: [main]
  workflow_dispatch: {}

jobs:
  reindex:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install coderagmanager
        run: pip install coderagmanager

      - name: Index (full rebuild)
        run: crm index --project . --root .

      - name: Publish updated index
        run: |
          git config user.name "crm-bot"
          git config user.email "crm-bot@users.noreply.github.com"
          git checkout -B crm-index
          git add .crm
          git commit -m "chore: reindex $(git rev-parse --short HEAD)" || echo "no changes"
          git push origin crm-index --force
```

Local sync: `crm index pull --project <id>` runs `git fetch origin crm-index` and copies `.crm/` from that branch into the local working tree (chapter [10](10-github-actions.md) §5) — then, if there are local uncommitted changes, the `reindex` MCP tool picks them up with a full local rebuild.

The `schedule` (cron) trigger from the original guide is deliberately removed: its only reason for existing was to correct desynchronization from an incremental reindex, which doesn't exist in this v1.

## 13. Full CLI

```bash
crm init                                       # creates ~/.crm/ if it doesn't exist

crm project add <name> <path>
crm project list
crm project remove <name>

crm index --project <name>                     # index/reindex: ALWAYS full
crm reindex --project <name>                   # alias for index, for familiarity
crm index pull --project <name>                # fetches the index published by CI

crm search "<query>" --project <name>          # debug search without going through MCP
crm stats --project <name>

crm mcp serve --project <name>
crm mcp install --client claude|codex|copilot --project <name>

crm config show
crm config set embedding.provider local
```

## 14. Packaging

```toml
# pyproject.toml
[project]
name = "coderagmanager"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12",
    "mcp>=1.0",
    "tree-sitter>=0.23",
    "tree-sitter-python", "tree-sitter-javascript", "tree-sitter-java",
    "lancedb",
    "sentence-transformers",
    "pyyaml",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov"]

[project.scripts]
crm = "coderagmanager.adapters.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

No `voyageai` dependency (not applicable in v1). Recommended installation: `pipx install coderagmanager` (or `pipx install -e .` for development).

## 15. Explicitly out of scope for v1

To make it clear it was decided **not to do it yet**, not that it was forgotten:

- Incremental reindexing based on `git diff` (all of chapter 07).
- Alternative embedding providers (Voyage AI, Qwen3-Embedding).
- Other vector stores (ChromaDB, Qdrant).
- Architectural layer/role classification.
- Multi-project MCP server with explicit `project_id` per call, and a `use_project` tool.
- Lexical retrieval with real BM25 (simple substring is used instead).
- `schedule`/cron trigger in GitHub Actions.

## 16. Milestone roadmap (adapted from chapter 12)

| Milestone | What to build | Definition of done |
|---|---|---|
| **M0** | Layout, `domain/models.py`, ports (no implementation), `pyproject.toml` | `pip install -e .` works; a test in `tests/domain/` passes |
| **M1** | `TreeSitterPythonParser` + `IndexProject` (drop-and-rebuild) + minimal `VectorStore`/`GraphStore` (plain JSON) | `crm index --project <x>` on a test Python repo produces inspectable chunks |
| **M2** | Real `LanceDbVectorStore` + `LocalSentenceTransformerProvider` + `search_code` (semantic only) | A search by meaning returns the correct function even if the literal name doesn't match |
| **M3** | MCP server (section 10) bound to a project via `--project`, connected to Claude Code | The agent successfully invokes `search_code`/`get_source` from a real session |
| **M4** | `YamlProjectRegistry`, `crm project add/list/remove`, `project_id` isolation in storage | Two projects registered, queryable without cross results |
| **M5** | `TreeSitterJavaScriptParser`, `TreeSitterJavaParser`, `GenericTextParser` | A repo with Python+JS+Java is indexed correctly without touching `IndexProject` or the domain |
| **M6** | GitHub Actions (section 12) + `crm index pull` | Push to `main` triggers the workflow; `crm index pull` fetches the index without errors |
| **M7** | `LexicalIndex` (substring) combined into `search_code` + `crm mcp install` for the 3 clients | Both an exact-symbol search and a conceptual one return good results; all 3 clients end up configured with a single command each |

(The incremental milestone from the original chapter 12 is removed — it doesn't apply to this v1.)

## 17. Where to start tomorrow

1. `mkdir -p coderagmanager/src/coderagmanager/{domain,ports,application,adapters}` + `pyproject.toml` (section 14, without the M2+ dependencies yet if you prefer to go incrementally).
2. Write `domain/models.py` exactly as in section 3.
3. A trivial test in `tests/domain/test_models.py` that builds a `CodeChunk` and asserts its fields — just to confirm the package and `pytest` are wired up (M0's definition of done).
4. From there, follow the roadmap in section 16 in order.
