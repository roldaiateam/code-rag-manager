# 08 · MCP Server

## 1. What MCP is, assuming nothing

**MCP (Model Context Protocol)** is an open protocol, standardized by Anthropic and adopted by the ecosystem, for an LLM agent (the client: Claude Code, Codex CLI, Copilot CLI...) to discover and use external tools uniformly, without every integration being a special case.

Protocol pieces you need to know to design the server:

- **Transport**: how messages travel. The two relevant ones for this project are **stdio** (the server is a local process, the client writes to its standard input and reads its standard output — no network, no ports, starts and dies with the client's session) and **HTTP** (streamable-http, for remote servers). For a server that runs on the developer's machine alongside their code, **stdio is the natural choice** — it's also what `code-rag-mcp` uses today.
- **JSON-RPC 2.0 messages**: each request/response is a JSON object with `method`, `params`, `id` (for requests) and `result`/`error` (for responses). You don't need to implement this by hand — the SDK handles it.
- **Capabilities**: on connecting, client and server negotiate what each supports. This project only needs to announce the `tools` capability (invocable tools) — `resources` and `prompts` aren't needed for the scope of this guide.
- **Tool**: a function exposed with a name, description, and an `inputSchema` (JSON Schema) that describes its parameters. The LLM client decides when to call it based on the description — which is why the quality of the description matters as much as the implementation (section 3).

## 2. The official Python SDK: FastMCP

The official MCP SDK for Python includes a high-level layer, **FastMCP**, that turns a regular Python function (with type hints and a docstring) into a complete MCP tool — it generates the `inputSchema` from the types, validates input, and manages the protocol lifecycle. This is what avoids having to write JSON-RPC by hand, unlike `code-rag-mcp` in Java (no official SDK available in that language).

```python
# adapters/mcp/server.py
from mcp.server.fastmcp import FastMCP
from composition_root import build_use_cases

mcp = FastMCP("codehex")
uc = build_use_cases()   # dictionary/object with all use cases already injected

@mcp.tool()
def search_code(project_id: str, query: str, top_k: int = 10,
                 language: str | None = None, kind: str | None = None) -> str:
    """Searches for relevant code by meaning and by lexical match.

    Use it as the FIRST step when exploring a project: it finds relevant
    functions, classes, and methods before reading the source code directly.

    Args:
        project_id: identifier of the registered project (see list_projects).
        query: natural-language description or keywords of what you're looking for.
        top_k: maximum number of results (default 10; raise to 20-30 for
            exploratory searches).
        language: filter by language ("python", "javascript", "java"...).
        kind: filter by chunk type ("function", "class", "method"...).
    """
    query_obj = SearchQuery(project_id=project_id, text=query, top_k=top_k,
                             language=language, kind=kind)
    results = uc["search_code"].execute(query_obj)
    return format_search_results(results)   # readable text, not a raw dict

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Each docstring serves a dual purpose: it's documentation for whoever reads the code **and** it's what the LLM client reads to decide when to invoke the tool. That's why, just as `code-rag-mcp` does in its README, it's worth being explicit about "when to use this" and, where applicable, "when NOT to use it" (to avoid the agent calling `search_code` when what it actually needs is `list_chunks`, for example).

## 3. Designing the tool surface

A direct superset of the one already validated by `code-rag-mcp`, with the semantic and multi-project layer tools added:

| Tool | What it does | Use case it invokes |
|---|---|---|
| `list_projects` | Lists registered projects and their indexing status | `ListProjects` |
| `search_code` | Hybrid semantic+lexical search | `SearchCode` |
| `get_dependency_chain` | BFS traversal of the dependency graph (`className`, `maxDepth`, `direction`) | `GetDependencyChain` |
| `get_source` | Reads actual source code, by symbol or by path+lines | `GetSource` |
| `list_chunks` | Filtered inventory (by language, kind, layer/role if classified) | `ListChunks` |
| `get_index_stats` | Index size, distribution, indexed commit — first contact with a project | `GetIndexStats` |
| `reindex` | Triggers `ReindexProject` (incremental if there's a prior index) | `ReindexProject` |

The recommended order of use, to include in the tool descriptions or in an additional prompt/documentation (a pattern already used by the `code-rag-mcp` README with good results): `list_projects` → `get_index_stats` → `search_code` → `get_dependency_chain` → `get_source`, from general to specific, minimizing unnecessary code reading.

## 4. Error handling

MCP distinguishes between a **protocol error** (malformed request, nonexistent tool — handled by the SDK) and a **domain error** returned as a valid result with `isError: true` (e.g., "project `foo` is not registered" is not a protocol failure, it's a legitimate response the agent must be able to read and use to correct its next call):

```python
@mcp.tool()
def get_source(project_id: str, symbol: str | None = None,
                file_path: str | None = None,
                start_line: int | None = None, end_line: int | None = None) -> str:
    """Reads actual source code. Use AFTER search_code or get_dependency_chain,
    when the summary isn't enough and you need to see the implementation."""
    if symbol is None and file_path is None:
        raise ValueError("You must provide 'symbol' or 'file_path', not neither.")
    try:
        return uc["get_source"].execute(project_id, symbol, file_path, start_line, end_line)
    except ProjectNotFoundError as e:
        raise ValueError(f"Project '{project_id}' not registered. Use list_projects to see available ones.") from e
```

FastMCP turns an uncaught exception into an MCP error response with the message included — enough for the agent to understand what to fix, without needing more elaborate error handling in a first version.

## 5. Multi-project on the server: stateless session vs. active project

Two valid ways to resolve "which project does this call refer to," with different costs:

- **Explicit `project_id` on every tool** (the design in the table above): more verbose per call, but with no state to manage on the server — each request is self-contained, and it's trivial to reason about and test. Recommended for a first version.
- **A `use_project` tool** that pins an active project for the rest of the session, and the other tools omit it: less verbose, but introduces mutable state on the server (what happens if two clients use the same server process? Over stdio this doesn't happen — each client launches its own process — so the risk is low, but it adds one more thing to explain and maintain).

This guide recommends starting with explicit `project_id` (simpler, easier to reason about) and adding `use_project` later only if real usage shows the verbosity is a problem.

## Reusable ideas from existing projects

- **From `code-rag-mcp`**: the full tool surface (`search_code`, `get_dependency_chain`, `get_source`, `list_chunks`, `get_index_stats`, `reindex`) is validated in production as-is, including the recommended order of use and the pattern of explicitly documenting "when to use it / when not to" in each description — copy it almost verbatim, adding `project_id` to each signature and `list_projects` as a new tool.
- **From `kairosai`**: the pattern of long-running operations with streaming progress (generators consumed by `StreamingResponse`) is applicable if you also expose `reindex` from an interface other than the MCP protocol itself (e.g., if you add a CLI or status UI, chapter 11) — MCP itself doesn't require progress streaming for simple synchronous tools.

## Next step

[09 · Client integration](09-integracion-clientes.md): how to register this server in Claude Code, Codex CLI, and GitHub Copilot CLI.
