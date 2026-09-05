# CodeRagManager (`crm`)

Multi-project code-RAG manager with an MCP server, v1 implementation of the
spec fixed in [`../code-rag-guide/FINAL-DESIGN.md`](../code-rag-guide/FINAL-DESIGN.md).

Indexes code repositories (structural chunking with tree-sitter, local
embeddings, dependency graph) and exposes the index as MCP tools for
Claude Code, Codex CLI, and GitHub Copilot CLI. Hexagonal architecture: adding
a language, an embedding provider, or a new client just means adding an adapter.

## Installation (development)

```bash
cd code-rag-manager
uv venv --python 3.12 .venv          # torch doesn't publish 3.14 wheels yet
uv pip install -p .venv/bin/python -e ".[dev]"
source .venv/bin/activate
```

The first indexing run downloads the `all-MiniLM-L6-v2` embedding model
(~90 MB). No API keys: everything runs locally.

## Usage

```bash
crm init                                  # creates ~/.crm/projects.yaml
crm project add my-backend ~/repos/backend
crm project add my-api ~/repos/api --include "internal-docs/**"   # index extra gitignored paths
crm project add my-lib ~/repos/lib --no-auto-include              # disable generated-code detection
crm project list

crm index --project my-backend            # indexing is ALWAYS full (drop-and-rebuild)
crm reindex --project my-backend          # alias for index
crm index pull --project my-backend       # fetches the index published by CI (crm-index branch)

crm search "email validation" --project my-backend
crm stats --project my-backend
crm chunks --project my-backend --language python

crm mcp serve --project my-backend        # MCP server over stdio (one per project)
crm mcp install --client claude --project my-backend   # writes .mcp.json in the repo
crm mcp install --client codex --project my-backend    # .codex/config.toml
crm mcp install --client copilot --project my-backend  # ~/.copilot/mcp-config.json
```

`crm mcp serve` is meant to be launched **by** an MCP client (via
`crm mcp install`), not run by hand in a terminal to try it out. If you do
run it manually, you'll see a one-line confirmation on stderr and then
nothing else — the process is blocked reading stdin, waiting for a
client's MCP `initialize` handshake. That's expected behavior, not a
hang; press Ctrl-C to exit.

## MCP tools (6, no `project_id`: the server is bound to a single project)

`search_code` · `get_dependency_chain` · `get_source` · `list_chunks` ·
`get_index_stats` · `reindex`

Recommended usage order for the agent: `get_index_stats` → `search_code` →
`get_dependency_chain` → `get_source`, from general to specific.

Bounded responses: `get_source` returns long classes as a **skeleton**
(signatures + annotations, bodies elided via tree-sitter) and truncates other
long chunks — always including the exact continuation call
(`get_source(file_path=..., start_line=..., end_line=...)`) in the response,
never silently. `list_chunks` caps at 200 rows. This keeps the context the
agent has to load small (the dominant cost in repos with generated code)
without stopping it from requesting the full fragment when it needs it.

## Architecture

```
src/coderagmanager/
├── domain/        # entities + hybrid ranking + edge resolution (pure Python)
├── ports/         # interfaces: LanguageParser, EmbeddingProvider, VectorStore,
│                  # GraphStore, LexicalIndex, GitProvider, ProjectRegistry
├── application/   # use cases: IndexProject (drop-and-rebuild), SearchCode...
├── adapters/
│   ├── parsers/   # tree-sitter Python/JS/Java + GenericTextParser (fallback)
│   ├── embeddings/# local sentence-transformers (the only one in v1)
│   ├── storage/   # LanceDB (vectors+source_text), graph.json, substring lexical
│   ├── registry/  # ~/.crm/projects.yaml
│   ├── cli/       # Typer
│   └── mcp/       # FastMCP + per-client config writers
└── composition_root.py   # the one place where everything gets wired together
```

Per-project state lives in `<repo>/.crm/` (LanceDB table + `graph.json` +
`manifest.json`) — it's a rebuildable cache, safe to delete and regenerate.

### Generated code (contract-first projects)

File discovery respects `.gitignore`, but **auto-detects and indexes by
convention** `**/target/generated-sources/` (Maven) and
`**/build/generated/` (Gradle) even when gitignored — in OpenAPI
contract-first projects that's where the validated DTOs/interfaces live.
The indexing summary reports what was added
(`(auto-included generated code: N chunks)`). Disable with
`--no-auto-include`; non-conventional paths can be added with `--include <glob>`.
Rule of thumb: *build first, reindex after* (the index reflects whatever
generated code currently exists on disk).

## CI

`.github/workflows/reindex.yml` is a template to copy into each indexed repo:
on every push to `main` it reindexes and publishes `.crm/` to the
`crm-index` branch; locally, `crm index pull` syncs it back down.

## Tests

```bash
pytest            # domain (pure), application (port fakes), adapters (integration)
```

Test fixture in `tests/fixtures/sample_repo/` (Python + JS + Java + markdown,
with known CALLS/EXTENDS/IMPLEMENTS relationships).

## Out of scope for v1 (decided, not forgotten)

Incremental reindexing via `git diff`, Voyage/Qwen embeddings, other vector
stores, layer/role classification, BM25, CI cron. See FINAL-DESIGN §15.
