# CodeRagManager (`crm`)

Gestor multi-proyecto de code-RAGs con servidor MCP, implementación v1 de la
especificación fijada en [`../code-rag-guide/FINAL-DESIGN.md`](../code-rag-guide/FINAL-DESIGN.md).

Indexa repositorios de código (chunking estructural con tree-sitter, embeddings
locales, grafo de dependencias) y expone el índice como herramientas MCP para
Claude Code, Codex CLI y GitHub Copilot CLI. Arquitectura hexagonal: añadir un
lenguaje, un proveedor de embeddings o un cliente nuevo es añadir un adaptador.

## Instalación (desarrollo)

```bash
cd code-rag-manager
uv venv --python 3.12 .venv          # torch aún no publica wheels para 3.14
uv pip install -p .venv/bin/python -e ".[dev]"
source .venv/bin/activate
```

La primera indexación descarga el modelo de embeddings `all-MiniLM-L6-v2`
(~90 MB). No hay API keys: todo es local.

## Uso

```bash
crm init                                  # crea ~/.crm/projects.yaml
crm project add mi-backend ~/repos/backend
crm project add mi-api ~/repos/api --include "docs-internas/**"   # indexar rutas gitignoradas extra
crm project add mi-lib ~/repos/lib --no-auto-include              # sin detección de código generado
crm project list

crm index --project mi-backend            # indexado SIEMPRE completo (drop-and-rebuild)
crm reindex --project mi-backend          # alias de index
crm index pull --project mi-backend       # trae el índice publicado por CI (rama crm-index)

crm search "validación de email" --project mi-backend
crm stats --project mi-backend
crm chunks --project mi-backend --language python

crm mcp serve --project mi-backend        # servidor MCP por stdio (uno por proyecto)
crm mcp install --client claude --project mi-backend   # escribe .mcp.json en el repo
crm mcp install --client codex --project mi-backend    # .codex/config.toml
crm mcp install --client copilot --project mi-backend  # ~/.copilot/mcp-config.json
```

## Tools MCP (6, sin `project_id`: el servidor va atado a un proyecto)

`search_code` · `get_dependency_chain` · `get_source` · `list_chunks` ·
`get_index_stats` · `reindex`

Orden de uso recomendado para el agente: `get_index_stats` → `search_code` →
`get_dependency_chain` → `get_source`, de lo general a lo específico.

Respuestas acotadas: `get_source` devuelve las clases largas como **esqueleto**
(firmas + anotaciones, cuerpos elididos vía tree-sitter) y trunca el resto de
chunks largos — siempre con la llamada de continuación exacta
(`get_source(file_path=..., start_line=..., end_line=...)`) incluida en la
respuesta, nunca en silencio. `list_chunks` capa a 200 filas. Esto mantiene
pequeño el contexto que carga el agente (el coste dominante en repos con
código generado) sin impedirle pedir el fragmento completo cuando lo necesita.

## Arquitectura

```
src/coderagmanager/
├── domain/        # entidades + ranking híbrido + resolución de aristas (Python puro)
├── ports/         # interfaces: LanguageParser, EmbeddingProvider, VectorStore,
│                  # GraphStore, LexicalIndex, GitProvider, ProjectRegistry
├── application/   # casos de uso: IndexProject (drop-and-rebuild), SearchCode...
├── adapters/
│   ├── parsers/   # tree-sitter Python/JS/Java + GenericTextParser (fallback)
│   ├── embeddings/# sentence-transformers local (único en v1)
│   ├── storage/   # LanceDB (vectores+source_text), graph.json, léxico substring
│   ├── registry/  # ~/.crm/projects.yaml
│   ├── cli/       # Typer
│   └── mcp/       # FastMCP + writers de config por cliente
└── composition_root.py   # único sitio donde se conectan los cables
```

Estado por proyecto en `<repo>/.crm/` (tabla LanceDB + `graph.json` +
`manifest.json`) — es caché reconstruible, se puede borrar y regenerar.

### Código generado (proyectos contract-first)

El descubrimiento de ficheros respeta `.gitignore`, pero **auto-detecta e
indexa por convención** `**/target/generated-sources/` (Maven) y
`**/build/generated/` (Gradle) aunque estén gitignorados — en proyectos
OpenAPI contract-first ahí viven los DTOs/interfaces con las validaciones.
El resumen del indexado informa de lo añadido
(`(auto-incluido código generado: N chunks)`). Se desactiva con
`--no-auto-include`; rutas no convencionales se añaden con `--include <glob>`.
Regla práctica: *build primero, reindex después* (el índice refleja el
generado existente en disco).

## CI

`.github/workflows/reindex.yml` es una plantilla para copiar a cada repo
indexado: en cada push a `main` reindexa y publica `.crm/` a la rama
`crm-index`; en local, `crm index pull` lo sincroniza.

## Tests

```bash
pytest            # dominio (puro), aplicación (fakes de puertos), adaptadores (integración)
```

Fixture de prueba en `tests/fixtures/sample_repo/` (Python + JS + Java + markdown,
con relaciones CALLS/EXTENDS/IMPLEMENTS conocidas).

## Fuera de alcance v1 (decidido, no olvidado)

Reindexado incremental por `git diff`, Voyage/Qwen embeddings, otros vector
stores, clasificación capa/rol, BM25, cron en CI. Ver FINAL-DESIGN §15.
