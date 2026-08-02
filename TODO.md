# TODO

Tracked gaps between the current state of the repo and "ready to open up to
outside contributors." Organized by priority, not chronology. Items link back
to the audit that produced them (see conversation/PR history) rather than
duplicating rationale here.

## 0. Before making the repo public

- [ ] **Add a `LICENSE` file.** Currently none — legally nobody outside the
      maintainer can use, fork, or send PRs against this code today, no
      matter what the repo visibility is. Pick a license (MIT/Apache-2.0 are
      the common defaults for this kind of tool) and add it. Blocks
      everything else in this list in practice.
- [ ] **Decide GitHub repo visibility deliberately** (currently has an
      `origin` remote at `github.com:PauloFCO/code-rag-manager.git` — confirm
      its current visibility setting before/when flipping to public; not
      checkable from this environment).

## 1. Security audit — result: no leaked secrets found, but confirm before publishing

Full-history grep for API keys/tokens/passwords/private keys: clean. No
`.env`, credentials, or `.venv` ever committed (verified across all 6 commits
in history). `benchmarks/` (which contains real project names and local
paths from the maintainer's own repos, e.g. `benchmarks/bank/*.yaml`) has
**never** been tracked by git — `.gitignore` excluded it from the first
commit that introduced `.gitignore`. Code review of subprocess/YAML/JSON
usage found no `shell=True`, `eval`/`exec`, unsafe `yaml.load`, or path
traversal outside the tool's own single-user local trust model (crm is a
local CLI/MCP server run by its own user, not a multi-tenant service).

- [ ] **Add a `SECURITY.md`** with a real reporting contact/process —
      `CONTRIBUTING.md` already flags this as unset.
- [ ] Note for future review (not a current finding): the MCP server's
      `reindex` tool triggers a full filesystem read of the bound project on
      agent request. That's inherent to the tool's purpose, but worth a line
      in the README's trust-model section once this is public, since AI
      agents (not just humans) will be invoking these tools.

## 2. CI / contribution readiness

- [ ] **Add `.github/workflows/ci.yml` that runs `pytest` (and lint, once
      adopted) on pull requests to this repo.** The only existing workflow,
      `reindex.yml`, is explicitly a template meant to be copied into repos
      _indexed by_ crm — it does not test crm itself. Neither
      `docs_es/FINAL-DESIGN.md` nor `docs_es/10-github-actions.md` design a
      CI workflow for crm's own repo, so there's no existing spec to copy;
      this needs to be designed from scratch. `CONTRIBUTING.md` already
      states plainly that a green local test run is the only current signal
      before review — that's the gap this closes.
- [ ] **Adopt a linter/formatter/type-checker** (ruff + mypy are the
      conventional pairing) and wire it into the new CI workflow.
      `pyproject.toml` has no `[tool.ruff]` section today and no chapter of
      the design docs specifies one either — greenfield decision, not a
      remnant to migrate.
- [ ] **Add a `CODE_OF_CONDUCT.md`** — flagged as absent in `CONTRIBUTING.md`.
- [ ] **Add PR/issue templates** under `.github/` (bug report, feature
      request, PR checklist) — currently `.github/` only contains
      `workflows/`.
- [ ] **Add `pyproject.toml` metadata needed for a credible PyPI listing**:
      `classifiers`, `license`, `urls.repository`/`homepage`. None of this
      is currently set, and it isn't discussed in any design doc either.
- [ ] **Decide and document the actual PyPI publishing plan.** The package
      has never been published (`pyproject.toml` is still `0.1.0`), but both
      `docs_es/FINAL-DESIGN.md` §14 and the `reindex.yml` template already
      assume `pip install coderagmanager` / `pipx install coderagmanager`
      works. Until there's a `publish.yml` (e.g. trusted publishing on tag
      push), that template is non-functional for anyone who copies it.
      Needs either a release workflow or a README caveat that the template
      requires building from source until v1 is published.
- [ ] **Start a `CHANGELOG.md` and start tagging releases.** `docs_es/11-cli-y-empaquetado.md`
      already states the semver policy (MCP tool schema changes = breaking),
      but nothing enforces or records it in practice yet.

## 3. Documentation gaps

- [ ] `src/coderagmanager/adapters/parsers/skeleton.py` (the skeleton-view
      feature used by `get_source`) is a real, working, tested feature with
      no mention in `docs_es/FINAL-DESIGN.md` or any numbered chapter — add
      a section, or at least a pointer.
- [ ] `benchmarks/` (runner/scorer/report + dashboard) has no corresponding
      doc chapter or FINAL-DESIGN section. Worth at least a README pointer
      explaining what it's for and how to run it, since outside contributors
      won't have the context that produced it.
- [ ] `.github/workflows/reindex.yml` diverges slightly from the sample in
      `docs_es/FINAL-DESIGN.md` §12 (it adds a `crm project add ci .` step
      and uses `git add -f .crm`, since `.crm/` is gitignored in consumer
      repos too) — update the doc so it stays the authoritative reference.

## 4. Deferred features (decided, not forgotten — `docs_es/FINAL-DESIGN.md` §15)

Kept here as a visible public roadmap so contributors know these are known
gaps with a considered reason, not oversights:

- [ ] Incremental reindexing via `git diff` (today: always full drop-and-rebuild).
- [ ] Additional embedding providers (Voyage AI, Qwen3-Embedding) beyond the
      local sentence-transformers default.
- [ ] Additional vector stores (ChromaDB, Qdrant) beyond LanceDB.
- [ ] Layer/role architectural classification on chunks.
- [ ] Multi-project MCP server (one process serving several `project_id`s via
      a `use_project` tool) instead of one process per project.
- [ ] Real BM25 lexical retrieval instead of the current substring scorer.
- [ ] Scheduled/cron reindexing in the CI template.
