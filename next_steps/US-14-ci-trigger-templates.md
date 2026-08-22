# US-14 — CI trigger templates catalog (always-full reindex)

**Tier:** Indexing automation · **Depends on:** —
**Design reference:** `PLAN-MEJORA-CODE-RAG-MANAGER.md §8`

## Story

As a maintainer of an indexed repo, I want a small menu of ready-made CI
trigger patterns (merge to `main`, merge to `develop`, manual-only,
scheduled) to copy from, so that I can automate *when* `crm index` runs for
my project's workflow without having to design a GitHub Actions workflow
from scratch.

## Context

**This story explicitly does not touch `crm`'s indexing engine.** The
project's decision (confirmed in this round) is to keep indexing always a
full drop-and-rebuild, permanently — no incremental `git diff` logic, ever.
This story only varies **when** the existing, unchanged `crm index` command
is invoked. Good first issue: no domain/application/port/adapter code
changes, just workflow YAML + a doc paragraph.

## Acceptance criteria

- [ ] At least 3 example workflow files alongside the existing
      `.github/workflows/reindex.yml` (which stays as the default
      "on push to main" template):
      - `reindex-on-develop.yml.example` — triggers `on: push: branches: [develop]`.
      - `reindex-manual.yml.example` — `on: workflow_dispatch` only, no
        automatic trigger.
      - `reindex-scheduled.yml.example` — `on: schedule: cron: ...` (e.g.
        nightly), for projects where nobody actively triggers reindexing.
- [ ] Every example still ends in the exact same action: `crm index
      --project . --root .` + publish to `crm-index` branch — **no variation
      in the "how"**, only in the "when" (trigger block).
- [ ] `README.md`'s CI section documents the menu and states explicitly:
      "whatever triggers it, the action is always the same full clean
      rebuild — never a partial diff."
- [ ] No changes to `IndexProject`, any port, or any adapter.

## Out of scope

- Any reindexing logic change of any kind — this is templates + one
  paragraph of documentation only.

## Files likely touched

- `.github/workflows/reindex-on-develop.yml.example` (new)
- `.github/workflows/reindex-manual.yml.example` (new)
- `.github/workflows/reindex-scheduled.yml.example` (new)
- `README.md` (CI section)
