# US-20 — Project-local, git-committed include/exclude config (retires the Maven/Gradle-only `auto_include` heuristic)

**Tier:** Indexing scope / DX (cross-cutting) · **Depends on:** —
**Design reference:** none in `PLAN-MEJORA-CODE-RAG-MANAGER.md` — raised
during onboarding while comparing against `code-rag-mcp`'s `FileScopes.java`
(confirmed to have no configurable ignore/include mechanism at all — this is
new ground, not a ported pattern). Also touches the discovery rules
described in `docs_es/FINAL-DESIGN.md` §198/242 and
`docs_es/04-diseno-multi-proyecto.md`, which will need updating once this
lands.

## Story

As a `crm` user, I want to control exactly which files get indexed —
excluding git-tracked noise (`.github/`, `.claude/`, vendored files...) and
force-including generated files, however each project's build tooling
happens to produce them — through **one file committed inside the indexed
repo**, so that my local indexing and CI's indexing are guaranteed to match,
and a teammate cloning the repo gets the same scoping without re-typing any
flags or relying on a hardcoded, language-specific guess about where
generated code lives.

## Context

Today `crm` has two scoping mechanisms and they both live in the wrong
place, plus a third mechanism that this story removes outright:

- `--include <glob>` (stored as `extra_index_paths`) and `--no-auto-include`
  (stored as `auto_include`) are set once, at `crm project add` time, and
  persisted **only** in `~/.crm/projects.yaml` — a per-machine file, never
  committed, never seen by a teammate or by CI.
- There is **no exclude mechanism** at all for files `git ls-files` already
  returns (i.e. tracked, not gitignored) but that the user doesn't want
  indexed as code — e.g. `.github/workflows/`, `.claude/`. `file_discovery.py`
  has no hook for this today.
- **`auto_include`'s actual detection logic (`AUTO_INCLUDE_MARKERS` in
  `file_discovery.py:26-28`) is hardcoded to exactly two Java build-tool
  conventions**: `target/generated-sources` (Maven) and `build/generated`
  (Gradle). It has no equivalent for Python (protobuf `_pb2.py`,
  OpenAPI-generated clients) or JS/TS (GraphQL codegen, OpenAPI generators),
  despite the same "contract-first project" motivation applying equally to
  those ecosystems. Extending it language-by-language means shipping and
  maintaining a new hardcoded heuristic per ecosystem forever.

**Decision this story makes**: retire the auto-detection heuristic entirely
rather than relocate it. `include`/`exclude` glob patterns, declared once by
the user and committed, already solve the exact problem `auto_include`
solves (not having to remember/retype a flag every time) — generalized to
any language's generated-code convention, with no new code in `crm` required
per ecosystem. A user who wants Maven's `generated-sources` indexed writes
`target/generated-sources/**` under `include:` once, same as they would for
a Python or TS equivalent — no special-cased detection logic behind it.

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
      be committed to git) with **two** keys — no `auto_include` key:
      ```yaml
      include:            # same glob syntax file_discovery.py already uses for --include
        - "internal-docs/**"
        - "target/generated-sources/**"   # generated code is just another include pattern now
      exclude:             # NEW — same glob syntax, applied to git-tracked files
        - ".github/**"
        - ".claude/**"
      ```
- [ ] `application/file_discovery.py` reads `.crm.yaml` from `root_path` and
      applies `exclude` as a filter over the `"git"`-origin file list (files
      already excluded by `.gitignore` are irrelevant to `exclude` — a
      different axis, see below). `include` continues to source the
      `"extra"` origin exactly as today.
- [ ] **`AUTO_INCLUDE_MARKERS`, `_auto_generated_dirs()`, and
      `_auto_generated_paths()` are deleted from `file_discovery.py`**, along
      with the `"auto"` source/origin in `discover_files()`. The
      `auto_include` field is removed from `Project`
      (`domain/models.py`), `YamlProjectRegistry`, and `IndexProject`'s
      constructor.
- [ ] Precedence rule, tested explicitly: `include` and `exclude` never
      conflict with each other (`include` only ever adds gitignored paths
      back in; `exclude` only ever removes git-tracked paths — disjoint by
      construction, no marker-vs-exclude precedence question remains once
      `auto_include` is gone).
- [ ] `~/.crm/projects.yaml` keeps only what's genuinely per-machine:
      `root_path`, `last_indexed_commit`, `last_indexed_at`.
- [ ] `crm project add <name> <path> --include ... --no-auto-include` flags
      are removed from `project_add`'s signature entirely (`--include`
      support moves into `.crm.yaml`, `--no-auto-include` has no
      replacement flag — see migration below). On first registration, if
      `.crm.yaml` doesn't exist yet in the target repo, `crm project add`
      **scaffolds it** with both keys present but commented out, each with
      a one-line explanation and example values, plus a comment reminding
      the user to commit it.
- [ ] `crm project add`'s console output tells the user the file was
      scaffolded and that it needs to be committed for CI to see it, e.g.:
      `Creado .crm.yaml en <root> — recuerda commitearlo para que CI indexe igual que tú.`
      (skipped if the file already existed).
- [ ] **Migration path for projects already relying on `auto_include: true`**
      (e.g. the `mic-inventory` project used during onboarding, which has
      `auto_include: true` in today's `~/.crm/projects.yaml`): the next
      `crm index --project <id>` run, if `.crm.yaml` doesn't exist yet and
      the registry still has `auto_include: true`, scaffolds `.crm.yaml`
      with `include:` pre-populated with the **literal equivalent glob
      patterns** the old heuristic covered — `target/generated-sources/**`
      and `build/generated/**` — so the project keeps indexing the same
      generated code it did before, now as an explicit, visible,
      version-controlled declaration instead of implicit detection. Prints
      a one-line notice that the migration happened, where, and that the
      patterns can be edited/removed if not applicable to this project.
- [ ] New inspection command, `crm project config --project <id>`, prints
      the effective `include`/`exclude` resolved from `.crm.yaml` (or "no
      `.crm.yaml` found — defaults apply" if absent) — so a user can check
      what will happen **before** running a full index.
- [ ] The existing indexing summary line (`format_included`, today
      reporting `auto`/`extra` counts) drops the `auto` count and gains an
      **excluded** count, e.g. `(included via .crm.yaml: N files; excluded:
      M files)`, so a typo'd glob that matches nothing is visible
      immediately instead of silently doing nothing.
- [ ] `README.md`'s "Generated code (contract-first projects)" section is
      rewritten: no more "auto-detects by convention" promise — generated
      code is documented as "just declare its path under `include:` in
      `.crm.yaml`," with the Maven/Gradle paths kept as the worked example
      (now as sample glob values, not as hardcoded detection logic).
- [ ] While in `README.md` anyway: fix the broken link on line 4 —
      `[../code-rag-guide/FINAL-DESIGN.md](../code-rag-guide/FINAL-DESIGN.md)`
      resolves to `ai/code-rag-guide/`, which doesn't exist (confirmed —
      only `code-rag-manager/`, `code-rag-mcp/`, and `ideas/` exist at that
      level). Point it at the real location inside this repo instead:
      `[docs_en/FINAL-DESIGN.md](docs_en/FINAL-DESIGN.md)`.
- [ ] `docs_es/04-diseno-multi-proyecto.md` / `docs_en/04-diseno-multi-proyecto.md`
      and `FINAL-DESIGN.md` (both languages) are updated to describe
      `.crm.yaml`'s `include`/`exclude` instead of the old
      `--include`/`--no-auto-include`/auto-detection design, so the guide
      doesn't go stale against the real implementation.

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
- Building per-ecosystem generated-code detection for Python/JS/TS as a
  replacement for the retired Java-only heuristic — deliberately not
  replaced with new detection logic; `include:` globs are the replacement,
  for every ecosystem, without new code per language.

## Files likely touched

- `src/coderagmanager/application/file_discovery.py`
  (`AUTO_INCLUDE_MARKERS`/`_auto_generated_dirs`/`_auto_generated_paths`
  deleted, `"auto"` source removed)
- `src/coderagmanager/domain/models.py` (`Project` fields —
  `auto_include` removed, `extra_index_paths` relocated)
- `src/coderagmanager/adapters/registry/yaml_project_registry.py`
- `src/coderagmanager/application/index_project.py` (`auto_include`
  parameter removed)
- New: `src/coderagmanager/adapters/config/project_config.py` (or similar —
  reads/writes `.crm.yaml`)
- `src/coderagmanager/adapters/cli/main.py` (`project_add`, new `project
  config` command, migration logic)
- `src/coderagmanager/adapters/formatting.py` (`format_included` drops
  `auto`, gains `excluded` count)
- `README.md`
- `docs_es/04-diseno-multi-proyecto.md`, `docs_en/04-diseno-multi-proyecto.md`
- `docs_es/FINAL-DESIGN.md`, `docs_en/FINAL-DESIGN.md`
- `tests/application/test_file_discovery.py`
- `tests/adapters/test_yaml_project_registry.py`
