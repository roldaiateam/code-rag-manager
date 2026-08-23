# US-19 — Internationalize CLI/MCP user-facing text (currently Spanish-only)

**Tier:** Documentation / DX (cross-cutting) · **Depends on:** —
**Design reference:** none — raised ad-hoc while onboarding a new
contributor, not derived from `PLAN-MEJORA-CODE-RAG-MANAGER.md`. Flagged
explicitly as going _against_ the project's current convention (see
Context), so it needs a maintainer decision before anyone picks it up.

## Story

As a non-Spanish-speaking contributor or agent operator, I want `crm`'s
command help, CLI output, and MCP tool docstrings available in English (or
selectable via a locale setting), so that adopting the tool doesn't require
reading Spanish first.

## Context

Today every user-facing string in the runtime code is hardcoded in Spanish:

- All CLI docstrings (used by Typer as `--help` text) and `typer.echo(...)`
  messages in `adapters/cli/main.py` (e.g. "Indexando ... reconstrucción
  completa", "Error: ...").
- All 6 MCP tool docstrings in `adapters/mcp/server.py` — these are not just
  developer-facing, **they are the descriptions the LLM agent reads to
  decide which tool to call**, so this is also functional text, not just
  cosmetic.
- Shared output formatting in `adapters/formatting.py` ("Sin resultados.",
  "auto-incluido código generado: N chunks", etc.).
- Exception messages in `domain/errors.py` and `ValueError`s raised in
  `adapters/registry/yaml_project_registry.py`.

This is the **opposite** of `docs_es/`/`docs_en/`, which already exist in
parallel for the didactic guide — the guide is bilingual, the actual product
is not. That asymmetry is exactly what prompted this story.

**This is explicitly flagged as a debatable addition** (raised as a
deliberately contrarian suggestion, not a validated need): the project's
existing convention — commit messages, docstrings, `backlog/*` prose vs.
in-repo Spanish strings — is mixed already, and full i18n has a real
maintenance cost (every new string needs both locales kept in sync, tests
need to assert against a stable key rather than literal Spanish text). A
maintainer should confirm this is wanted (and choose a scope: hardcode to
English and drop Spanish entirely? support both via a locale file? env var
like `CRM_LANG`?) before implementation starts.

## Acceptance criteria (assuming "support both, default to current Spanish")

- [ ] User-facing strings in `adapters/cli/main.py`, `adapters/mcp/server.py`,
      and `adapters/formatting.py` are extracted to a small message catalog
      (e.g. `adapters/i18n/messages.py` with `es`/`en` dicts, or `gettext`
      `.po`/`.mo` if the dependency is judged worth it) instead of inline
      literals.
- [ ] A `CRM_LANG` environment variable (or `crm config set lang en`,
      mirroring the existing `embedding_provider` default in
      `~/.crm/projects.yaml`) selects the active locale; unset defaults to
      `es` to avoid a breaking change for existing users.
- [ ] MCP tool docstrings are translated with particular care to preserve
      the "when to use / when not to use" guidance verbatim in meaning
      (this is agent-facing behavior, not just UI text — see US-18, which
      touches the same docstrings for a different reason and should land
      first or be coordinated with this one to avoid merge conflicts).
- [ ] `domain/errors.py` exception messages are translatable without
      breaking anything that currently matches on exception _type_
      (`ProjectNotFoundError`) rather than message text — confirm no test
      or caller does string-matching on these messages today.
- [ ] `README.md` documents the `CRM_LANG` option next to the existing
      `crm config show`/`config set` usage.

## Out of scope

- Translating `docs_es/`/`docs_en/` — already bilingual, unaffected.
- Translating code comments or internal docstrings not shown to a user or
  agent (e.g. module-level `"""..."""` explaining design decisions to
  future contributors) — those stay Spanish, consistent with the rest of
  the codebase.
- Any new language beyond `es`/`en`.

## Files likely touched

- `src/coderagmanager/adapters/cli/main.py`
- `src/coderagmanager/adapters/mcp/server.py`
- `src/coderagmanager/adapters/formatting.py`
- `src/coderagmanager/domain/errors.py`
- `src/coderagmanager/adapters/registry/yaml_project_registry.py` (error messages)
- `README.md`
- New: `src/coderagmanager/adapters/i18n/` (or equivalent message catalog)
