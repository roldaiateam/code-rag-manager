# Next steps — user stories

This folder holds the **actionable backlog** derived from
[`PLAN-MEJORA-CODE-RAG-MANAGER.md`](PLAN-MEJORA-CODE-RAG-MANAGER.md) (the
design document — read it for the _why_ behind every decision referenced
here). Each `US-NN-*.md` file is a self-contained user story: a contributor
should be able to pick one up, implement it, and open a PR against it without
having to reverse-engineer the design discussion that produced it.

**Lifecycle:** once a story is implemented and merged, delete its file from
this folder (and update the table below). This folder is a temporary staging
area for planned work, not a permanent backlog or a changelog — see
`CONTRIBUTING.md` for the contributor-facing version of this note.

## How to use these

1. Pick a story whose dependencies are already satisfied (see each story's
   "Dependencias" section).
2. Read the linked section of `PLAN-MEJORA-CODE-RAG-MANAGER.md` for the full
   rationale if the story's own context isn't enough.
3. Implement against the acceptance criteria — they carry the concrete
   values (weights, thresholds, names) already decided, not just direction.
4. Add/update tests per the project's existing split (`tests/domain/`,
   `tests/application/`, `tests/adapters/`).
5. Open a PR referencing the story ID (e.g. "Implements US-01").
6. Once merged, delete the story file in the same PR or a prompt follow-up.

## Backlog

| ID                                                   | Title                                                              | Tier                | Depends on          | Status |
| ---------------------------------------------------- | ------------------------------------------------------------------ | ------------------- | ------------------- | ------ |
| [US-01](US-01-lexical-source-text.md)                | Lexical search also over `source_text`                             | Nivel 0             | —                   |        |
| [US-02](US-02-confidence-threshold.md)               | Confidence threshold in `search_code`                              | Nivel 0             | US-01               |        |
| [US-03](US-03-sweep-known-bugs.md)                   | Sweep the 2 known CLI/MCP bugs from `TODO.md`                      | Nivel 0             | —                   |        |
| [US-04](US-04-tokenizer.md)                          | Shared tokenizer (split + stemming + synonyms)                     | Nivel 1             | —                   |        |
| [US-05](US-05-multi-field-lexical-scoring.md)        | Multi-field lexical scoring                                        | Nivel 1             | US-04               |        |
| [US-06](US-06-classification-layer-1-path.md)        | Classification layer 1: path vocabulary                            | Nivel 1             | —                   |        |
| [US-07](US-07-classification-layer-2-spring-java.md) | Classification layer 2: `spring-java` pack                         | Nivel 1             | —                   |        |
| [US-08](US-08-classification-layer-3-semantic.md)    | Classification layer 3: semantic prototypes                        | Nivel 1             | US-06, US-07        |        |
| [US-09](US-09-role-layer-filters.md)                 | `--role`/`--layer` filters (CLI + MCP tools)                       | Nivel 1             | US-06, US-07, US-08 |        |
| [US-10](US-10-role-based-summaries.md)               | Role-based chunk summaries                                         | Nivel 1 (2nd wave)  | US-06, US-07, US-08 |        |
| [US-11](US-11-bm25.md)                               | Real BM25 lexical index                                            | Nivel 2             | US-04               |        |
| [US-12](US-12-embedding-provider-voyage.md)          | Additional embedding provider (Voyage AI)                          | Nivel 2             | —                   |        |
| [US-13](US-13-vector-store-adapter.md)               | Additional vector store adapter                                    | Nivel 2             | —                   |        |
| [US-14](US-14-ci-trigger-templates.md)               | CI trigger templates catalog (always-full reindex)                 | Indexing automation | —                   |        |
| [US-15](US-15-project-groups.md)                     | Project `group` field + `--group` + `project list` column          | Nivel 3             | —                   |        |
| [US-16](US-16-search-related-projects-tool.md)       | `search_related_projects` MCP tool                                 | Nivel 3             | US-15               |        |
| [US-17](US-17-symbol-collision-warning.md)           | Symbol collision warning in federated results                      | Nivel 3             | US-16               |        |
| [US-18](US-18-query-type-tool-guidance.md)           | Query-type-aware tool guidance (docstrings + README)               | Documentation       | —                   |        |
| [US-19](US-19-cli-i18n.md)                           | Internationalize CLI/MCP user-facing text (currently Spanish-only) | Documentation / DX  | —                   |        |
| [US-20](US-20-project-local-scope-config.md)         | Project-local, git-committed include/exclude config (`.crm.yaml`)  | Indexing scope / DX | —                   |        |

Tiers follow the roadmap in `PLAN-MEJORA-CODE-RAG-MANAGER.md §11`: Nivel 0 →
Nivel 1 → Nivel 2 → indexing automation → Nivel 3. Within a tier, stories
without a "depends on" entry can be picked up in any order. US-18 is
cross-cutting (documentation only) and can be picked up independently of
tier order, though it references US-02's behavior once that one lands.
