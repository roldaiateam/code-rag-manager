# US-27 — Copilot MCP install writes a global config, leaking tools into unrelated projects

**Tier:** MCP client integration (bug) · **Depends on:** —
**Design reference:** none — raised while investigating a real, reproduced
symptom (tools from a `crm`-indexed project still offered by Copilot while
working in a completely different, unindexed project).

## Story

As a Copilot CLI user who ran `crm mcp install --client copilot` for project
A, I want the `crm-<A>` server to stop being offered once I'm working in an
unrelated project B, so that the agent doesn't try to use tools bound to the
wrong codebase's index without any warning that it's doing so.

## Context

Confirmed root cause, in full chain:

- `CopilotConfigWriter` (`adapters/mcp/client_configs/writers.py:69-94`)
  always writes to `~/.copilot/mcp-config.json` (or `$COPILOT_HOME/...`) — a
  **user-global** file, unlike `ClaudeConfigWriter` (`.mcp.json` in the repo
  root) and `CodexConfigWriter` (`.codex/config.toml` in the repo root),
  which are both **project-scoped**. `CopilotConfigWriter` doesn't even take
  a `project_root` argument (line 72) — nowhere to write a project-scoped
  file even if it wanted to.
- Once registered there, the `crm-<project_id>` server (and, with the
  written `"tools": ["*"]`, every one of its tools) stays active in **every**
  Copilot CLI session on that machine — nothing in Copilot's global config
  is aware of which directory the user is currently working in, and the
  server process itself resolves `root_path` from `~/.crm/projects.yaml` by
  `project_id` (`adapters/registry/yaml_project_registry.py`), not from the
  cwd it happened to be spawned from. So it serves project A's index
  correctly, from inside project B's session, with no scope check anywhere.
- **The project's own design docs already identified the fix and it was
  never implemented.** `docs_en/09-integracion-clientes.md:68` states
  Copilot CLI "also discovers project-level configuration in
  `.github/mcp.json`", and the comparison table in the same chapter (line
  101) lists Copilot as having a "Version-controllable per-project config":
  **`.github/mcp.json`** — on par with `.mcp.json`/`.codex/config.toml`.
  Confirmed by grep: `.github/mcp.json` does not appear anywhere in `src/`.
  `CopilotConfigWriter` only ever targets the global file — §5 of the same
  doc chapter (line 113) already describes this actual (global-only)
  behavior, contradicting §3 two sections above it.
- Compounding factors, also confirmed: no tool docstring names the concrete
  bound project (`search_code`'s docstring says "en ESTE proyecto" without
  identifying which one — `adapters/mcp/server.py:39`), and there is no `crm
  mcp uninstall` command of any kind (confirmed by grep) — once an entry
  lands in the global file, there is no supported way to remove it short of
  hand-editing the JSON.

## Acceptance criteria

- [ ] New writer (or an extended `CopilotConfigWriter`) targets
      **`.github/mcp.json` in the project root by default**, written in the
      same shape already documented in `docs_en/09-integracion-clientes.md`
      §3 — bringing Copilot's default behavior in line with Claude/Codex
      (project-scoped, mergeable, doesn't step on other servers already
      configured there).
- [ ] `crm mcp install --client copilot` gains an explicit `--global` flag
      to opt into the old behavior (writing `~/.copilot/mcp-config.json`
      instead) for users who deliberately want the server available across
      every project — and the CLI echoes a one-line warning when `--global`
      is used, explaining that the server's tools will stay active in
      unrelated, unindexed projects too.
- [ ] `mcp_install()`'s echoed confirmation states which file was written
      (`.github/mcp.json` vs. the global path), not just "Configuración MCP
      ... escrita en `<path>`" as today — the scope should be legible
      without having to open the file.
- [ ] `crm mcp install --client copilot --project <id>`, run without
      `--global` when a global entry for that same `crm-<id>` already exists
      in `~/.copilot/mcp-config.json` (e.g. from before this fix, or from a
      previous deliberate `--global` install), warns about the leftover
      global entry and how to remove it manually — this story does not
      silently delete a file it didn't decide to own, but it must not leave
      the user newly confused about why the old cross-project behavior
      persists after "fixing" it.
- [ ] New `crm mcp uninstall --client <claude|codex|copilot> --project <id>`
      command removes the corresponding entry from whichever file that
      client's writer targets (including the global Copilot file, so users
      already affected by this bug have a supported way out without hand-
      editing JSON).
- [ ] `docs_en/09-integracion-clientes.md` §5 (and its `docs_es` counterpart)
      updated so the "convenience command" description matches §3 again —
      `crm mcp install --client copilot` documented as writing
      `.github/mcp.json` by default, with `--global` documented as the
      explicit opt-in.
- [ ] Unit test: installing for project A then B (different `project_id`s)
      via the default (project-scoped) path produces two independent
      `.github/mcp.json` files, each only containing its own project's
      entry — proving no cross-project leakage under the new default.
- [ ] Unit test: `--global` still merges into `~/.copilot/mcp-config.json`
      without clobbering unrelated servers already there (existing writer
      behavior, preserved).
- [ ] Unit test: `mcp uninstall` removes only the targeted entry, leaving
      other configured servers in the same file untouched.

## Out of scope

- Any change to how Claude/Codex writers work — both are already
  project-scoped by default, this story doesn't touch them beyond adding the
  shared `mcp uninstall` command.
- Detecting or fixing this at runtime from inside the MCP server process
  itself (e.g. the server refusing to answer if the cwd looks unrelated) —
  the server has no reliable way to know the client's cwd over stdio; the
  fix belongs entirely in what gets written at install time.
- Auto-migrating or auto-deleting existing global entries — flagged to the
  user, never silently rewritten out from under them.

## Files likely touched

- `src/coderagmanager/adapters/mcp/client_configs/writers.py`
- `src/coderagmanager/adapters/cli/main.py` (`mcp_install()`, new
  `mcp_uninstall()`)
- `docs_en/09-integracion-clientes.md`, `docs_es/09-integracion-clientes.md`
- `README.md` (Usage section, Copilot install example)
- `tests/adapters/` (new/updated tests for `CopilotConfigWriter` and
  `mcp_uninstall`)
