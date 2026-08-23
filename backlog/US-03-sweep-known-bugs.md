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
unit in `next_steps/`; the authoritative description stays in `TODO.md`.

## Acceptance criteria

- [ ] `crm mcp install` resolves an absolute path for the `command` field
      (via `sysconfig.get_path("scripts")`, falling back to
      `shutil.which("crm")`, then the bare string) instead of always writing
      the literal `"crm"` — see `TODO.md` for the exact location
      (`adapters/mcp/client_configs/writers.py:19-20`) and the stderr warning
      required in `mcp_install()` when no absolute path could be resolved.
- [ ] `crm mcp serve` prints a one-line stderr message on startup confirming
      it's up and waiting for a client (never stdout, reserved for
      JSON-RPC) — see `TODO.md` for the exact location
      (`adapters/mcp/server.py:123-124`).
- [ ] `README.md`'s Usage section is updated to clarify `mcp serve` is meant
      to be launched *by* an MCP client, not run standalone in a terminal to
      test it (per `TODO.md`'s note).
- [ ] Once both are fixed, remove the corresponding entries from
      `TODO.md`'s "5. Known bugs" section.

## Out of scope

- Any other item in `TODO.md` (license, CI, packaging, etc.) — unrelated to
  this improvement round.

## Files likely touched

- `src/coderagmanager/adapters/mcp/client_configs/writers.py`
- `src/coderagmanager/adapters/mcp/server.py`
- `src/coderagmanager/adapters/cli/main.py` (`mcp_install()` warning)
- `README.md`
- `TODO.md` (remove closed items)
