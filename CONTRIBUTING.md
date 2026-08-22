# Contributing to CodeRagManager

Thanks for your interest in contributing to **CodeRagManager** (`crm`) — a
multi-project code-RAG manager with an MCP server. This document explains how
to get set up, how the project is organized, and what to expect from the
contribution process.

CodeRagManager is an early-stage project (single maintainer, `v0.1.0`), so
some of the usual open-source scaffolding (license, code of conduct, CI
checks on pull requests) is still being put in place. This guide is
deliberately honest about what exists today versus what's still a
recommendation — see the "Maintainer decisions still required" note at the
end of the PR/repo for anything not yet settled.

## Ways to contribute

- **Planned improvements** — see [`next_steps/`](next_steps/) for a
  concrete, ready-to-implement backlog of user stories (see "Planned work"
  below).
- **Bug reports** — something doesn't behave as documented.
- **Feature work** — new language parsers, embedding providers, MCP clients,
  or other adapters (the hexagonal architecture is designed to make these
  additive).
- **Tests** — coverage for existing behavior, especially in `adapters/`.
- **Benchmark contributions** — new evaluation questions and results.
- **Documentation** — fixes or additions to `README.md` or the `docs_en/` /
  `docs_es/` guide.

## Planned work (`next_steps/`)

The [`next_steps/`](next_steps/) folder holds the current, concrete backlog:
`next_steps/PLAN-MEJORA-CODE-RAG-MANAGER.md` is the design document behind
it (rationale, theory, and every decision already made), and
`next_steps/README.md` indexes the individual `US-NN-*.md` user stories
derived from it — each one scoped, with acceptance criteria and a list of
files it's expected to touch, so you can pick one up without having to
reconstruct the design discussion yourself.

This is a **temporary staging area, not a permanent backlog or a
changelog**: once a story is implemented and merged, its `US-NN-*.md` file
is deleted from `next_steps/` in the same PR (or a prompt follow-up), and the
entry is removed from `next_steps/README.md`. If you're looking for
well-scoped contribution opportunities, start there before opening a new
issue from scratch.

## Development setup

Requirements: Python **3.10+** (the project is developed and tested against
**3.12**) and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone <repo-url>
cd code-rag-manager
uv venv --python 3.12 .venv          # torch doesn't publish 3.14 wheels yet
uv pip install -p .venv/bin/python -e ".[dev]"
source .venv/bin/activate
```

The first indexing run downloads the `all-MiniLM-L6-v2` embedding model
(~90 MB). No API keys are required — indexing and search run entirely
locally.

To try the CLI once installed:

```bash
crm init                                  # creates ~/.crm/projects.yaml
crm project add my-backend ~/repos/backend
crm index --project my-backend
crm search "email validation" --project my-backend
crm mcp serve --project my-backend        # MCP server over stdio
```

See the [README](README.md) for the full command reference and the
[architecture overview](README.md#architecture) (`domain/`, `ports/`,
`application/`, `adapters/`, `composition_root.py`).

## Running tests

```bash
pytest
```

Tests are organized to mirror `src/coderagmanager/`:

- `tests/domain/` — pure logic, no fakes or I/O.
- `tests/application/` — use cases exercised against port fakes
  (`tests/application/fakes.py`).
- `tests/adapters/` — integration tests against real adapters (parsers,
  storage, etc.).

A shared fixture repository lives at `tests/fixtures/sample_repo/` (Python +
JS + Java + Markdown, with known `CALLS`/`EXTENDS`/`IMPLEMENTS`
relationships) — reuse it instead of adding new fixture repos where
possible.

There is no `conftest.py` in the repo today; keep test setup local to each
test module unless you have a genuine cross-module need for one.

## Code style

The repository does not currently have an automated linter, formatter, or
type checker configured (no ruff, black, isort, flake8, mypy, or pyright
config, and no `.pre-commit-config.yaml`). Until that tooling is adopted:

- Match the style of the surrounding code (type hints are used throughout
  `domain/` and `ports/`; keep using them in new code).
- Keep modules aligned with the existing hexagonal layering — domain code
  stays free of I/O and framework dependencies; adapters implement `ports/`
  interfaces.
- Favor readability and small, focused functions, consistent with the
  existing codebase.

If you'd like to help close this gap, proposing a ruff/mypy configuration
(as its own PR, with rationale) is a welcome contribution.

## Pull request process

1. Fork the repository and branch off `main` (the only branch used today;
   no branch-naming convention is enforced, so pick something descriptive).
2. Make your change, keeping it focused and scoped to one concern.
3. Run `pytest` locally and make sure it passes. **There is currently no CI
   workflow that runs tests or lint on pull requests for this repository**
   (the only workflow, `.github/workflows/reindex.yml`, is a template meant
   to be copied into _indexed_ repos, not this project's own CI) — so a
   green local test run is the only signal before review.
4. Add or update tests for behavior you change.
5. Open a pull request describing what changed and why. Reference any
   related issue.
6. For larger or architectural changes, consider opening an issue first to
   discuss the approach before investing significant time.

## Commit message guidelines

The project's git history doesn't yet reflect a single established
convention. Going forward, please use
[Conventional Commits](https://www.conventionalcommits.org/) style prefixes
where practical (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`),
with a concise, descriptive subject line. This is a recommendation for
consistency going forward, not a rule enforced by tooling today.

## Documentation contributions

- `README.md` documents user-facing installation, usage, and architecture —
  keep it in sync with CLI/behavior changes.
- `docs_en/` and `docs_es/` are a bilingual, didactic "build this system from
  scratch" guide (numbered chapters plus `FINAL-DESIGN.md`). If you edit one
  language's content in a way that changes meaning, please keep the other in
  sync, or note in your PR that a translation update is still needed.

## Reporting bugs

Please open a GitHub issue. Include:

- What you expected to happen vs. what actually happened.
- Steps to reproduce (ideally against `tests/fixtures/sample_repo/` or a
  minimal example).
- Relevant environment details (Python version, OS).

There is no issue template in the repository yet, so a clear free-form
description is fine.

## Suggesting features

Open a GitHub issue describing the use case and, if relevant, how it fits
the existing hexagonal architecture (e.g., "new adapter" vs. "core behavior
change"). For anything that touches the domain/application layers or adds a
new port, a short discussion before implementation is appreciated.

## Security issues

The repository does not yet have a `SECURITY.md` or a published security
contact. Until that's in place, please avoid filing sensitive
vulnerability details in a public issue — use GitHub's private security
advisory feature on this repository if available, and check back here for
an updated contact once the maintainer has published one.

## Community expectations

There is no `CODE_OF_CONDUCT.md` in this repository yet. In the meantime,
please engage respectfully and assume good faith — the standard expectation
for any collaborative open-source project.

## License notice

This repository does not currently include a `LICENSE` file. Until one is
added, no explicit open-source license applies. Please check with the
maintainer before assuming you can redistribute or reuse this code, and
watch for a `LICENSE` file to be added (see the maintainer decisions note
below).

---

Thank you for contributing to CodeRagManager!
