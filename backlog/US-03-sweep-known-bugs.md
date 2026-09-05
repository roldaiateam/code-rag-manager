# US-03 — Sweep the 2 known CLI/MCP bugs from `TODO.md`

**Tier:** Nivel 0 (bundled — cheap, already diagnosed) · **Depends on:** —
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §5.3`, §10

## Story

As a maintainer bundling the Nivel 0 fixes into one release, I want the two
already-diagnosed CLI/MCP bugs fixed in the same pass, so that the release
closes known rough edges instead of leaving them for later with no clear
owner.

## Context

**This story does not duplicate the bug descriptions** — they are already
fully diagnosed, with exact file and line, in `code-rag-manager/TODO.md`
section "5. Known bugs". This story exists only so the sweep has a trackable
unit in `backlog/`; the authoritative description stays in `TODO.md`.

## Acceptance criteria

- [x] `crm mcp install` resolves an absolute path for the `command` field
      (via `sysconfig.get_path("scripts")`, falling back to
      `shutil.which("crm")`, then the bare string) instead of always writing
      the literal `"crm"` — see `TODO.md` for the exact location
      (`adapters/mcp/client_configs/writers.py:19-20`) and the stderr warning
      required in `mcp_install()` when no absolute path could be resolved.
- [x] `crm mcp serve` prints a one-line stderr message on startup confirming
      it's up and waiting for a client (never stdout, reserved for
      JSON-RPC) — see `TODO.md` for the exact location
      (`adapters/mcp/server.py:123-124`).
- [x] `README.md`'s Usage section is updated to clarify `mcp serve` is meant
      to be launched _by_ an MCP client, not run standalone in a terminal to
      test it (per `TODO.md`'s note).
- [x] Once both are fixed, remove the corresponding entries from
      `TODO.md`'s "5. Known bugs" section.

## Verification notes (2026-09-05)

- New `resolve_crm_executable()` in `writers.py` resolves, in order:
  `sysconfig.get_path("scripts")` (checked with `os.path.isfile` +
  `os.access(X_OK)`) → `shutil.which("crm")` → the bare `"crm"` string.
  `server_command()` now uses it, fixing all three writers (Claude, Codex,
  Copilot) at once since they share it.
- `mcp_install()` now warns on stderr (yellow, non-fatal) when
  `resolve_crm_executable()` couldn't resolve an absolute path.
- `serve()` prints a one-line stderr confirmation right before blocking on
  `run(transport="stdio")`, once the server is actually built (so the
  message is truthful, not printed before construction finishes).
- `README.md` Usage section now explains `mcp serve` is meant to be
  launched by a client, and what the stderr line + blocking behavior look
  like if run manually.
- Tests: 4 new (`tests/adapters/test_client_config_writers.py` — 3 for
  `resolve_crm_executable()`'s three branches, using real files/`PATH` via
  `tmp_path`/`monkeypatch`, no mocking; `tests/adapters/test_mcp_server.py`
  — 1 verifying the stderr message via a fake server, asserting stdout
  stays empty). The 2 pre-existing writer tests that asserted a literal
  `"crm"` command were updated to compare against
  `resolve_crm_executable()`'s real result instead.
- Manually verified in this dev venv: `mcp install` against a project
  registered in an isolated temp registry wrote an absolute path
  (`.venv/bin/crm`); with `PATH` cleared and no resolvable scripts dir,
  `resolve_crm_executable()` falls back to `"crm"`, confirming the warning
  condition in `mcp_install()` fires correctly.
- Full suite: `pytest` — 83 passed.

## Out of scope

- Any other item in `TODO.md` (license, CI, packaging, etc.) — unrelated to
  this improvement round.

## Files likely touched

- `src/coderagmanager/adapters/mcp/client_configs/writers.py`
- `src/coderagmanager/adapters/mcp/server.py`
- `src/coderagmanager/adapters/cli/main.py` (`mcp_install()` warning)
- `README.md`
- `TODO.md` (remove closed items)
