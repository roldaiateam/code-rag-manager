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
6. Once merged, delete the story file in the same PR or a prompt follow-up —
   only once the acceptance criteria are demonstrably true (tests passing,
   behavior confirmed), not merely once the PR merged. A checked box that
   doesn't match reality is worse than an unchecked one.

## Backlog

| ID                                                   | Title                                                                            | Tier                         | Depends on          | Status      |
| ---------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------- | ------------------- | ----------- |
| [US-01](US-01-lexical-source-text.md)                | Lexical search also over `source_text`                                           | Nivel 0                      | —                   | Implemented |
| [US-02](US-02-confidence-threshold.md)               | Confidence threshold in `search_code`                                            | Nivel 0                      | US-01               | Implemented |
| [US-03](US-03-sweep-known-bugs.md)                   | Sweep the 2 known CLI/MCP bugs from `TODO.md`                                    | Nivel 0                      | —                   | Implemented |
| [US-04](US-04-tokenizer.md)                          | Shared tokenizer (split + stemming + synonyms)                                   | Nivel 1                      | —                   | Implemented |
| [US-05](US-05-multi-field-lexical-scoring.md)        | Multi-field lexical scoring                                                      | Nivel 1                      | US-04               | Implemented |
| [US-06](US-06-classification-layer-1-path.md)        | Classification layer 1: path vocabulary                                          | Nivel 1                      | —                   |             |
| [US-07](US-07-classification-layer-2-spring-java.md) | Classification layer 2: `spring-java` pack                                       | Nivel 1                      | —                   |             |
| [US-08](US-08-classification-layer-3-semantic.md)    | Classification layer 3: semantic prototypes                                      | Nivel 1                      | US-06, US-07        |             |
| [US-09](US-09-role-layer-filters.md)                 | `--role`/`--layer` filters (CLI + MCP tools)                                     | Nivel 1                      | US-06, US-07, US-08 |             |
| [US-10](US-10-role-based-summaries.md)               | Role-based chunk summaries                                                       | Nivel 1 (2nd wave)           | US-06, US-07, US-08 |             |
| [US-11](US-11-bm25.md)                               | Real BM25 lexical index                                                          | Nivel 2                      | US-04               |             |
| [US-12](US-12-embedding-provider-voyage.md)          | Additional embedding provider (Voyage AI)                                        | Nivel 2                      | —                   |             |
| [US-13](US-13-vector-store-adapter.md)               | Additional vector store adapter                                                  | Nivel 2                      | —                   |             |
| [US-14](US-14-ci-trigger-templates.md)               | CI trigger templates catalog (always-full reindex)                               | Indexing automation          | —                   |             |
| [US-15](US-15-project-groups.md)                     | Project `group` field + `--group` + `project list` column                        | Nivel 3                      | —                   |             |
| [US-16](US-16-search-related-projects-tool.md)       | `search_related_projects` MCP tool                                               | Nivel 3                      | US-15               |             |
| [US-17](US-17-symbol-collision-warning.md)           | Symbol collision warning in federated results                                    | Nivel 3                      | US-16               |             |
| [US-18](US-18-query-type-tool-guidance.md)           | Query-type-aware tool guidance (docstrings + README)                             | Documentation                | —                   |             |
| [US-19](US-19-cli-i18n.md)                           | Internationalize CLI/MCP user-facing text (currently Spanish-only)               | Documentation / DX           | —                   |             |
| [US-20](US-20-project-local-scope-config.md)         | Project-local include/exclude config (`.crm.yaml`), retires `auto_include`       | Indexing scope / DX          | —                   |             |
| [US-21](US-21-chunks-pagination.md)                  | Pagination for `crm chunks` / `list_chunks` (past the 200-row cap)               | DX / debugging               | —                   |             |
| [US-22](US-22-index-staleness-signal.md)             | Index staleness signal across MCP tools/CLI                                      | Index reliability            | —                   |             |
| [US-23](US-23-ambiguous-symbol-resolution.md)        | Flag ambiguous symbol resolution instead of guessing                             | Index reliability            | —                   |             |
| [US-24](US-24-cross-store-consistency-check.md)      | Cross-store consistency check (vector vs. graph chunk counts)                    | Index reliability            | —                   |             |
| [US-25](US-25-aggregate-dependency-chain-output.md)  | Aggregate `get_dependency_chain` output instead of a flat edge dump              | Dependency graph UX          | US-23               |             |
| [US-26](US-26-consumer-summary-tool.md)              | Consumer summary tool (`get_consumers`)                                          | Dependency graph UX          | US-25               |             |
| [US-27](US-27-copilot-project-scoped-config.md)      | Copilot MCP install writes a global config, leaking tools cross-project          | MCP client integration (bug) | —                   |             |
| [US-28](US-28-typescript-tsx-parser.md)              | Dedicated TypeScript/TSX parser (stop losing typed React components)             | Language coverage            | —                   |             |
| [US-29](US-29-css-parser.md)                         | Dedicated CSS parser (selectors/rules as structured chunks)                      | Language coverage            | —                   |             |
| [US-30](US-30-composite-parser-fallback.md)          | `CompositeLanguageParser` falls back to generic text instead of indexing nothing | Language coverage            | —                   |             |
| [US-31](US-31-atomic-state-writes.md)                | Atomic writes for `graph.json`/`manifest.json`/`projects.yaml`                   | Index reliability            | —                   |             |

Tiers follow the roadmap in `PLAN-MEJORA-CODE-RAG-MANAGER.md §11`: Nivel 0 →
Nivel 1 → Nivel 2 → indexing automation → Nivel 3. Within a tier, stories
without a "depends on" entry can be picked up in any order. US-18 is
cross-cutting (documentation only) and can be picked up independently of
tier order, though it references US-02's behavior once that one lands.
US-22/23/24/31 (index reliability), US-25/26 (dependency graph UX), US-27
(MCP client integration bug), and US-28/29/30 (language coverage) are also
cross-cutting and outside that roadmap's tier order — none of them require
any Nivel 1/2/3 work to land first. See US-11's "Priority note" for a
possible resequencing worth revisiting once US-01 has shipped.
