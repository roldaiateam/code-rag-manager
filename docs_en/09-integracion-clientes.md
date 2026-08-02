# 09 · Client integration

Once the MCP server from chapter 08 works over stdio, connecting it to a client is a matter of telling it **how to start the process** — each client stores that information in its own configuration file, with a slightly different format. This is the only part of the system that varies by client; the server itself doesn't change a single line.

> The configuration formats of these CLIs evolve fairly often. What's here is verified against the official documentation current as of this guide (2026); if something doesn't work, check the official documentation for each tool before assuming the problem is in your server.

## 1. Claude Code

Claude Code supports three MCP configuration scopes:

| Scope | Where it lives | When to use it |
|---|---|---|
| **Local** (default) | `~/.claude.json`, under the current project's entry | Personal configuration, not shared |
| **Project** | `.mcp.json` at the project root | Version-controlled in git — the whole team automatically gets the same server |
| **User** | `~/.claude.json`, global | Available across all your projects |

Via CLI (recommended — it separates Claude Code's own options from the server's arguments with `--`):

```bash
claude mcp add --env VOYAGE_API_KEY=your_key --transport stdio codehex \
  --scope project \
  -- codehex mcp serve --project backend-java
```

Or by editing `.mcp.json` directly:

```json
{
  "mcpServers": {
    "codehex": {
      "type": "stdio",
      "command": "codehex",
      "args": ["mcp", "serve", "--project", "backend-java"],
      "env": {
        "VOYAGE_API_KEY": "${VOYAGE_API_KEY}"
      }
    }
  }
}
```

If you use `--scope project` (version-controlled `.mcp.json` file), Claude Code will ask for approval the first time it detects it in a repo — that's an intentional security measure, not a bug. Ongoing management: `claude mcp list`, `claude mcp get codehex`, `claude mcp remove codehex`.

## 2. Codex CLI (OpenAI)

Codex CLI stores its MCP configuration in TOML, in `~/.codex/config.toml` (global) or `.codex/config.toml` at the project level (only for projects marked as trusted):

```toml
[mcp_servers.codehex]
command = "codehex"
args = ["mcp", "serve", "--project", "backend-java"]
startup_timeout_sec = 10

[mcp_servers.codehex.env]
VOYAGE_API_KEY = "your_key"
```

Or via CLI:

```bash
codex mcp add codehex --env VOYAGE_API_KEY=your_key -- codehex mcp serve --project backend-java
```

Management: `codex mcp list` to see the configured servers.

## 3. GitHub Copilot CLI

Copilot CLI stores its configuration in `~/.copilot/mcp-config.json` (the path can be redirected with the `COPILOT_HOME` environment variable), and also discovers project-level configuration in `.github/mcp.json`:

```json
{
  "mcpServers": {
    "codehex": {
      "type": "local",
      "command": "codehex",
      "args": ["mcp", "serve", "--project", "backend-java"],
      "env": {
        "VOYAGE_API_KEY": "your_key"
      },
      "tools": ["*"]
    }
  }
}
```

Or via CLI:

```bash
copilot mcp add codehex --env VOYAGE_API_KEY=your_key -- codehex mcp serve --project backend-java
```

The `"tools": ["*"]` field enables all of the server's tools; you can restrict it to a subset (`["search_code", "get_source"]`) if, for instance, you want a particular client to be unable to trigger `reindex`.

## 4. Quick comparison

| | Claude Code | Codex CLI | Copilot CLI |
|---|---|---|---|
| File | `.mcp.json` / `~/.claude.json` | `config.toml` | `mcp-config.json` |
| Format | JSON | TOML | JSON |
| Server key | `mcpServers.<name>` | `[mcp_servers.<name>]` | `mcpServers.<name>` |
| Version-controllable per-project config | Yes (`.mcp.json`) | Yes (`.codex/config.toml`, trusted projects only) | Yes (`.github/mcp.json`) |
| Add command | `claude mcp add` | `codex mcp add` | `copilot mcp add` |

The conceptual structure is the same across all three (name → command + args + environment variables) because they all speak the same underlying protocol; only the wrapper changes.

## 5. Convenience command: generating the configuration automatically

To avoid forcing anyone to memorize three different formats, `codehex` can include a command that generates (or inserts) the right configuration block for the chosen client:

```bash
codehex mcp install --client claude   # writes/updates .mcp.json
codehex mcp install --client codex    # writes/updates .codex/config.toml
codehex mcp install --client copilot  # writes/updates ~/.copilot/mcp-config.json
```

Implementation: a small per-client adapter (`ClaudeConfigWriter`, `CodexConfigWriter`, `CopilotConfigWriter`) that knows how to read the existing file (if any), merge in the `codehex` entry without stepping on other already-configured servers, and write it back in the corresponding format (JSON or TOML). Adding a future client is, again, a new adapter — the pattern repeats throughout the project by design (chapter 03).

## 6. Common troubleshooting

| Symptom | Likely cause |
|---|---|
| The client doesn't list any tool | The configured command doesn't start (relative path instead of absolute, or the package isn't installed in the `PATH` the client sees) — try running the same command by hand in a terminal |
| The server starts but closes immediately | Something was written to stdout that isn't valid JSON-RPC (e.g., a debug `print()`) — over stdio, stdout is **only** the protocol channel; any logging must go to stderr |
| `reindex` takes a long time the first time but is fast afterward | Expected behavior — the first time is a full index, subsequent ones are incremental (chapter 07) |
| The client asks for approval every time | Normal for project-scoped servers (`.mcp.json`, trusted `.codex/config.toml`) — it's a client-side security measure, not a server bug |

## Reusable ideas from existing projects

- **From `kairosai`**: the "materialization" of configuration (`install.py`, which writes `.claude/` + `.mcp.json` from an internal model) is exactly the pattern that section 5 proposes generalizing to three clients instead of one.

## Next step

[10 · GitHub Actions](10-github-actions.md): how to keep the index up to date automatically, without anyone having to remember to run `reindex`.
