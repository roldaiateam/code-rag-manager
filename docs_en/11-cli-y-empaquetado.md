# 11 · CLI and packaging

## 1. Command surface

```bash
codehex init                                   # creates ~/.codehex/ if it doesn't exist (global registry)

codehex project add <name> <path>              # registers a project (chapter 04)
codehex project list
codehex project remove <name>

codehex index --project <name>                 # full indexing (chapter 03)
codehex reindex --project <name>               # incremental if there's a prior index (chapter 07)
codehex index pull --project <name>            # fetches the index published by CI (chapter 10)

codehex search "<query>" --project <name>      # debugging search, bypassing MCP
codehex stats --project <name>                 # CLI equivalent of get_index_stats

codehex mcp serve --project <name>             # starts the MCP server over stdio (chapter 08)
codehex mcp install --client claude|codex|copilot   # generates the client configuration (chapter 09)

codehex config show                            # view effective configuration (defaults + overrides)
codehex config set embedding.provider voyage
```

Each command is a thin facade over an application-layer use case (chapter 03) — the CLI adapter (`adapters/cli/`) only parses arguments, builds the use case via `composition_root`, executes it, and formats the output for the terminal. It shouldn't contain any business logic at all; if you find yourself writing an `if` that decides *what* to do (not just *how to display it*), that logic belongs in a use case, not in the CLI command.

```python
# adapters/cli/main.py
import typer
from composition_root import build_use_cases

app = typer.Typer(name="codehex")
project_app = typer.Typer(name="project")
app.add_typer(project_app)

@project_app.command("add")
def project_add(name: str, path: str):
    uc = build_use_cases()
    project = uc["register_project"].execute(name, path)
    typer.echo(f"Project '{project.name}' registered at {project.root_path}")

@app.command()
def reindex(project: str = typer.Option(..., "--project")):
    uc = build_use_cases()
    stats = uc["reindex_project"].execute(project)
    typer.echo(f"Reindexed: {stats.reparsed} files, {stats.new_chunks} new chunks")
```

## 2. Packaging

```toml
# pyproject.toml
[project]
name = "codehex"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12",
    "mcp>=1.0",
    "tree-sitter>=0.23",
    "tree-sitter-python", "tree-sitter-javascript", "tree-sitter-java",
    "lancedb",
    "sentence-transformers",   # default local embedding provider
    "pyyaml",
]

[project.optional-dependencies]
voyage = ["voyageai"]          # only if using the paid provider
dev = ["pytest>=8.0", "pytest-cov"]

[project.scripts]
codehex = "codehex.adapters.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Installation as an isolated command-line tool (recommended over a global `pip install`, so as not to mix its dependencies with those of the developer's other Python projects):

```bash
pipx install codehex
# or, for local development of codehex itself:
pipx install -e .
```

This is the same distribution pattern already used by `kairosai` (`pipx install .` / `pip install -e .`), for consistency across the tools in this same workspace.

## 3. Testing strategy

Following the layer separation from chapter 03, each layer is tested with a different approach and a different cost:

| Layer | What gets tested | How |
|---|---|---|
| `domain/` | Pure rules (e.g., `merge_and_rerank`, classifiers) | Unit tests with no test doubles — they're pure functions, input→output |
| `application/` | Use cases orchestrating ports | Unit tests with **test doubles (fakes) for the ports**, not brittle mocks coupled to the implementation — an in-memory `FakeVectorStore` is more resilient to refactors than a mock that verifies exact calls |
| `adapters/` | Each adapter against the real library it wraps | Integration tests specific to each adapter (e.g., `TreeSitterPythonParser` against a real, fixed Python code snippet) |
| End-to-end | The full pipeline | An integration test with a small, controlled **fixture repository** (a handful of example Python/JS/Java files with known relationships) that runs `index` and verifies the result — this is the test that gives the most confidence for the least maintenance |

```python
# tests/application/test_search_code.py
class FakeVectorStore:
    def __init__(self):
        self._data: dict[str, list[CodeChunk]] = {}
    def upsert(self, project_id, chunks):
        self._data.setdefault(project_id, []).extend(chunks)
    def search(self, project_id, query_embedding, top_k):
        return [SearchResult(chunk=c, score=1.0, match_reason="semantic")
                for c in self._data.get(project_id, [])[:top_k]]

def test_search_code_returns_results_from_vector_store():
    fake_store = FakeVectorStore()
    fake_store.upsert("p1", [make_chunk(symbol="validate_email")])
    use_case = SearchCode(embedder=FakeEmbedder(), vector_store=fake_store, lexical_index=FakeLexicalIndex())

    results = use_case.execute(SearchQuery(project_id="p1", text="email validation"))

    assert any(r.chunk.symbol == "validate_email" for r in results)
```

No real vector store or real call to an embedding model is needed to test that `SearchCode` orchestrates correctly — that's exactly what the separation into ports buys you.

## 4. Versioning

Standard semver (`MAJOR.MINOR.PATCH`). Keep in mind one nuance specific to this domain: a change to an MCP tool's `inputSchema` (renaming a parameter, making something required that used to be optional) is a breaking change from the point of view of already-configured clients (Claude Code, Codex CLI, Copilot CLI with existing configuration) — treat it as a *breaking change* (bump `MAJOR`) just as you would a public API change, not as an internal detail.

## Reusable ideas from existing projects

- **From `kairosai`**: the combination of CLI (Typer) + packaging via `pyproject.toml` + `pipx` is exactly the same pattern, reusable with virtually no changes.

## Next step

[12 · Step-by-step guide](12-guia-paso-a-paso.md): the concrete build roadmap, in the order it's worth tackling it.
