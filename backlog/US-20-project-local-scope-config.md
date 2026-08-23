# US-20 — Project-local, git-committed include/exclude config (replaces the per-machine `--include`/`--no-auto-include`)

**Tier:** Indexing scope / DX (cross-cutting) · **Depends on:** —
**Design reference:** none in `PLAN-MEJORA-CODE-RAG-MANAGER.md` — raised
during onboarding while comparing against `code-rag-mcp`'s `FileScopes.java`
(confirmed to have no configurable ignore/include mechanism at all — this is
new ground, not a ported pattern). Also touches the discovery rules
described in `docs_es/FINAL-DESIGN.md` §198/242 and `docs_es/04-diseno-multi-proyecto.md`,
which will need updating once this lands.

## Story

As a `crm` user, I want to control exactly which files get indexed —
excluding git-tracked noise (`.github/`, `.claude/`, vendored files...) and
force-including generated files that don't match the two hardcoded
conventions — through **one file committed inside the indexed repo**, so
that my local indexing and CI's indexing are guaranteed to match, and a
teammate cloning the repo gets the same scoping without re-typing any flags.

## Context

Today `crm` already has two of the three scoping mechanisms this story
needs, but both live in the wrong place:

- `--include <glob>` (stored as `extra_index_paths`) and `--no-auto-include`
  (stored as `auto_include`) are set once, at `crm project add` time, and
  persisted **only** in `~/.crm/projects.yaml` — a per-machine file, never
  committed, never seen by a teammate or by CI.
- There is **no exclude mechanism** at all for files `git ls-files` already
  returns (i.e. tracked, not gitignored) but that the user doesn't want
  indexed as code — e.g. `.github/workflows/`, `.claude/`. `file_discovery.py`
  has no hook for this today.

**Concrete, already-happening bug this fixes:** `.github/workflows/reindex.yml`
runs `crm project add ci .` with **no flags at all**:

```yaml
- run: |
    crm project add ci .
    crm index --project ci
```

Any developer who registered the same project locally with `--include` or
`--no-auto-include` gets a **silently different index** in CI than on their
own machine — there is no way for the workflow to know what flags to pass,
because that configuration was never in the repo it just checked out.

**This story does not add a second mechanism alongside the first** — it
relocates `extra_index_paths`/`auto_include` out of the global registry into
a project-local file, and adds the missing `exclude` key to the same file.
One place, one format, three keys.

### Where the new file must NOT live

`<repo>/.crm/` is documented (`README.md`) as "a rebuildable cache, safe to
delete and regenerate," and `reindex.yml` force-adds it (`git add -f .crm`)
specifically because it's expected to already be gitignored by the user. If
the new config file were placed inside `.crm/`, a project's own `.gitignore`
would very likely swallow it too — silently reintroducing the exact
CI-drift bug this story exists to close. **The config file must live at the
project root, alongside `.gitignore`, not inside `.crm/`.**

## Acceptance criteria

- [ ] New project-local file `.crm.yaml` (root of the indexed repo, meant to
      be committed to git) with three optional keys:
      ```yaml
      include:            # same glob syntax file_discovery.py already uses for --include
        - "internal-docs/**"
      exclude:            # NEW — same glob syntax, applied to git-tracked files
        - ".github/**"
        - ".claude/**"
      auto_include: true  # same meaning as today's registry field; default true
      ```
- [ ] `application/file_discovery.py` reads `.crm.yaml` from `root_path` and
      applies `exclude` as a filter over the `"git"`-origin file list (files
      already excluded by `.gitignore` are irrelevant to `exclude` — different
      axis, see below). No change to the `"auto"`/`"extra"` source logic
      besides sourcing their inputs from this file instead of from
      `Project`.
- [ ] Precedence rule, tested explicitly: an **`exclude` pattern wins over
      auto-detected generated-code conventions** — if a path both matches
      `AUTO_INCLUDE_MARKERS` and an `exclude` glob, it is excluded. `include`
      and `exclude` never conflict with each other (`include` only ever adds
      gitignored paths back in; `exclude` only ever removes git-tracked
      paths — disjoint by construction).
- [ ] `domain/models.py`'s `Project` and
      `adapters/registry/yaml_project_registry.py` **stop persisting**
      `extra_index_paths`/`auto_include`. `~/.crm/projects.yaml` keeps only
      what's genuinely per-machine: `root_path`, `last_indexed_commit`,
      `last_indexed_at`.
- [ ] `crm project add <name> <path> --include ... --no-auto-include` flags
      are removed from `project_add`'s signature; on first registration, if
      `.crm.yaml` doesn't exist yet in the target repo, `crm project add`
      **scaffolds it** with all three keys present but commented out, each
      with a one-line explanation and the same example values as this
      story, plus a comment reminding the user to commit it.
- [ ] `crm project add`'s console output tells the user the file was
      scaffolded and that it needs to be committed for CI to see it, e.g.:
      `Creado .crm.yaml en <root> — recuerda commitearlo para que CI indexe igual que tú.`
      (skipped if the file already existed).
- [ ] **Migration path** for projects already relying on the old fields
      (e.g. the `mic-inventory` project used during onboarding, which has
      `auto_include: true` in today's `~/.crm/projects.yaml`): the next
      `crm index --project <id>` run, if `.crm.yaml` doesn't exist yet and
      the registry still has non-default `extra_index_paths`/`auto_include`,
      writes those values into a freshly scaffolded `.crm.yaml` and prints a
      one-line notice that the migration happened and where.
- [ ] New inspection command, `crm project config --project <id>`,
      prints the effective `include`/`exclude`/`auto_include` resolved from
      `.crm.yaml` (or "no `.crm.yaml` found — defaults apply" if absent) —
      so a user can check what will happen **before** running a full index.
- [ ] The existing indexing summary line (`format_included`, today only
      reporting `auto`/`extra` counts) gains a matching **excluded count**,
      e.g. `(excluded via .crm.yaml: N files)`, so a typo'd glob that
      matches nothing is visible immediately instead of silently doing
      nothing.
- [ ] `README.md` gains a documented section for `.crm.yaml` (mirroring the
      existing "Generated code (contract-first projects)" section), with
      the full key reference and a worked example using the `.github/`/`.claude/`
      case from this conversation.
- [ ] `docs_es/04-diseno-multi-proyecto.md` / `docs_en/04-diseno-multi-proyecto.md`
      and `FINAL-DESIGN.md` (both languages) are updated to describe
      `.crm.yaml` instead of the old `--include`/`--no-auto-include`-in-registry
      design, so the guide doesn't go stale against the real implementation.

## Out of scope

- Any change to `.gitignore` handling itself (`git ls-files --exclude-standard`
  stays exactly as-is) — `exclude` is a layer on top, not a replacement.
- Gitignore-wildmatch syntax (`!`, nested negation, etc.) for `exclude` —
  reuses the same plain glob syntax `_glob_paths` already implements for
  `include`, for consistency and to avoid a new pattern-matching dependency.
- Any change to `EXCLUDED_DIRS` (the hardcoded structural exclusions —
  `node_modules`, `target`, `build`, `.git`, etc.) — those stay unconditional
  and out of user control, as today.
- Per-user override of a committed `.crm.yaml` (e.g. a local-only
  `.crm.local.yaml`) — not requested, not included; revisit only if a real
  need shows up.

## Files likely touched

- `src/coderagmanager/application/file_discovery.py`
- `src/coderagmanager/domain/models.py` (`Project` fields)
- `src/coderagmanager/adapters/registry/yaml_project_registry.py`
- New: `src/coderagmanager/adapters/config/project_config.py` (or similar —
  reads/writes `.crm.yaml`)
- `src/coderagmanager/adapters/cli/main.py` (`project_add`, new `project config` command)
- `src/coderagmanager/adapters/formatting.py` (`format_included` gains excluded count)
- `README.md`
- `docs_es/04-diseno-multi-proyecto.md`, `docs_en/04-diseno-multi-proyecto.md`
- `docs_es/FINAL-DESIGN.md`, `docs_en/FINAL-DESIGN.md`
- `tests/application/test_file_discovery.py`
- `tests/adapters/test_yaml_project_registry.py`
