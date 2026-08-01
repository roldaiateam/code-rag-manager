# FINAL-DESIGN · CodeRagManager (`crm`)

## 0. Propósito de este documento

`code-rag-guide` (capítulos `00`-`13`) enseña **cómo pensar** cada pieza de un gestor de code-RAGs y deja deliberadamente varias decisiones abiertas ("elige tú según tu caso"). Este documento toma **cada una de esas decisiones abiertas** y la deja fijada, para que se pueda empezar a escribir código sin más lectura ni más decisiones de diseño pendientes.

No sustituye a la guía: para el *porqué* de cada pieza (qué es un embedding, por qué arquitectura hexagonal, etc.) se sigue enlazando a los capítulos correspondientes. Este documento es la **foto final concreta**, no el razonamiento.

Nombre del proyecto: **CodeRagManager**. Comando CLI: **`crm`**. Sustituye al `codehex` usado como placeholder en la guía.

## 1. Tabla de decisiones

| Punto abierto en la guía | Decisión tomada | Motivo / referencia |
|---|---|---|
| Reindexado (cap. [07](07-indexacion-incremental.md)) | **Siempre completo** (drop-and-rebuild), sin diff incremental | Simplicidad para v1, local, un solo desarrollador. Coherente con milestones M0-M5 de la guía original, donde el incremental no aparece hasta M6 |
| Alcance del servidor MCP (cap. [04](04-diseno-multi-proyecto.md) §4 vs [08](08-servidor-mcp.md) §5) | **Un servidor MCP por proyecto**, arrancado con `--project <id>` | Precedente real: `kairosai/src/kairosai/coderag.py` ya registra un servidor `code-rag-<repo>` por repo clonado. El agente nunca elige proyecto — solo hay uno en la sesión |
| Proveedor de embeddings (cap. [06](06-embeddings-vector-store.md) §1) | **Modelo local ligero** (`sentence-transformers`, `all-MiniLM-L6-v2`), único adaptador en v1 | Gratis, sin red, sin API key — arranca mañana mismo |
| Lenguajes v1 (cap. [05](05-parsing-multilenguaje.md)) | **Python + JavaScript + Java** (tree-sitter) + `GenericTextParser` fallback | Cobertura completa del trío que usa la guía por defecto |
| GitHub Actions (cap. [10](10-github-actions.md)) | **Incluido en v1**, muy simplificado (sección 13) | Al no haber incremental, no hace falta `fetch-depth:0`, restaurar índice previo, ni secrets de API |
| Clasificación capa/rol (cap. [02](02-code-rag-particularidades.md) §5, [05](05-parsing-multilenguaje.md) §5) | **Omitida en v1** | Enriquecimiento opcional explícito en la guía; se difiere |
| `get_source` (cap. [01](01-fundamentos-rag.md) §4, [06](06-embeddings-vector-store.md)) | **Se guarda `source_text` completo en el índice** | No releer del disco; el índice es autocontenido |
| Retrieval léxico (cap. [01](01-fundamentos-rag.md) §6, [06](06-embeddings-vector-store.md) §3) | **Léxico simple por substring** sobre `symbol`/`file_path`, sin BM25 | Micro-decisión no cubierta explícitamente antes; se resuelve con el mismo criterio de "empezar simple" que el resto de la tabla |

## 2. Nombre y convenciones

| Elemento | Valor |
|---|---|
| Paquete Python (import) | `coderagmanager` |
| Comando CLI | `crm` |
| Registro global de proyectos | `~/.crm/projects.yaml` |
| Estado por proyecto | `<root_del_proyecto>/.crm/` (tabla LanceDB + `graph.json` + `manifest.json`) |
| Rama de publicación CI | `crm-index` |
| Nombre de entrada de servidor MCP | `crm-<project_id>` (p.ej. `crm-backend-java`) |
| Entry point del paquete | `crm = "coderagmanager.adapters.cli.main:app"` |

## 3. Modelo de dominio

`src/coderagmanager/domain/models.py` — sin dependencias externas, adaptado del capítulo [03](03-arquitectura-hexagonal.md) §3:

```python
from dataclasses import dataclass, field
from enum import Enum

class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"

@dataclass(frozen=True)
class CodeChunk:
    id: str                      # hash estable (ruta + símbolo + línea inicio)
    project_id: str
    language: str                 # "python" | "javascript" | "java" | "text"
    symbol: str
    kind: str                     # "function" | "class" | "method" | "block" | ...
    file_path: str
    start_line: int
    end_line: int
    source_text: str              # SIEMPRE se persiste completo (decisión fijada)
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)   # firma/docstring; sin layer/role en v1

@dataclass(frozen=True)
class DependencyEdge:
    source_chunk_id: str
    target_chunk_id: str
    edge_type: EdgeType

@dataclass(frozen=True)
class Project:
    id: str
    name: str
    root_path: str
    languages: list[str]
    last_indexed_commit: str | None = None
    last_indexed_at: str | None = None

@dataclass(frozen=True)
class SearchQuery:
    text: str                     # SIN project_id: lo fija el servidor MCP al arrancar
    top_k: int = 10
    language: str | None = None
    kind: str | None = None

@dataclass(frozen=True)
class SearchResult:
    chunk: CodeChunk
    score: float
    match_reason: str            # "semantic" | "lexical" | "hybrid"
```

`project_id` **desaparece de `SearchQuery`** (de cara al usuario del MCP) pero **se mantiene en las firmas de los puertos** (`VectorStore`, `GraphStore`, `LexicalIndex` — sección 6) para conservar el aislamiento multi-proyecto en el almacenamiento. Ver sección 11 para cómo se reconcilia esto en el adaptador MCP.

## 4. Layout de carpetas

Adaptado de capítulo [03](03-arquitectura-hexagonal.md) §7:

```
coderagmanager/
├── pyproject.toml
├── src/coderagmanager/
│   ├── domain/
│   │   └── models.py
│   ├── ports/
│   │   ├── language_parser.py
│   │   ├── embedding_provider.py
│   │   ├── vector_store.py
│   │   ├── graph_store.py
│   │   ├── lexical_index.py
│   │   ├── git_provider.py
│   │   └── project_registry.py
│   ├── application/
│   │   ├── index_project.py       # único caso de uso de indexado (full, siempre)
│   │   ├── search_code.py
│   │   ├── get_dependency_chain.py
│   │   ├── get_source.py
│   │   ├── list_chunks.py
│   │   ├── get_index_stats.py
│   │   ├── register_project.py
│   │   ├── list_projects.py
│   │   └── remove_project.py
│   ├── adapters/
│   │   ├── parsers/
│   │   │   ├── tree_sitter_python.py
│   │   │   ├── tree_sitter_javascript.py
│   │   │   ├── tree_sitter_java.py
│   │   │   └── generic_text.py
│   │   ├── embeddings/
│   │   │   └── local_provider.py       # único adaptador en v1
│   │   ├── storage/
│   │   │   ├── lancedb_vector_store.py
│   │   │   ├── json_graph_store.py
│   │   │   └── substring_lexical_index.py
│   │   ├── git/git_cli_provider.py     # solo head()
│   │   ├── registry/yaml_project_registry.py
│   │   ├── cli/
│   │   └── mcp/
│   │       ├── server.py
│   │       └── client_configs/         # ClaudeConfigWriter, CodexConfigWriter, CopilotConfigWriter
│   └── composition_root.py
├── .github/workflows/reindex.yml
└── tests/
    ├── domain/
    ├── application/
    └── adapters/
```

## 5. Puertos

Adaptados de capítulo [03](03-arquitectura-hexagonal.md) §4, con recortes fijados:

```python
# ports/language_parser.py
class LanguageParser(Protocol):
    def supports(self, file_path: str) -> bool: ...
    def parse(self, project_id: str, file_path: str, source: str) -> tuple[list[CodeChunk], list[DependencyEdge]]: ...

# ports/embedding_provider.py
class EmbeddingProvider(Protocol):
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def dimensions(self) -> int: ...

# ports/vector_store.py — drop() sustituye a delete() por ids: no hace falta borrado selectivo
class VectorStore(Protocol):
    def drop(self, project_id: str) -> None: ...
    def upsert(self, project_id: str, chunks: list[CodeChunk]) -> None: ...
    def search(self, project_id: str, query_embedding: list[float], top_k: int) -> list[SearchResult]: ...

# ports/graph_store.py
class GraphStore(Protocol):
    def drop(self, project_id: str) -> None: ...
    def upsert_edges(self, project_id: str, edges: list[DependencyEdge]) -> None: ...
    def dependency_chain(self, project_id: str, symbol: str, max_depth: int, direction: str) -> list[DependencyEdge]: ...

# ports/lexical_index.py — NUEVO respecto a la guía original: resuelve la sección 6 §3 de forma explícita
class LexicalIndex(Protocol):
    def index(self, project_id: str, chunks: list[CodeChunk]) -> None: ...
    def search(self, project_id: str, text: str, top_k: int) -> list[SearchResult]: ...

# ports/git_provider.py — RECORTADO: sin diff_since ni working_tree_changes (no hay incremental)
class GitProvider(Protocol):
    def head(self, repo_path: str) -> str: ...

# ports/project_registry.py — igual que capítulo 04
class ProjectRegistry(Protocol):
    def register(self, name: str, root_path: str, languages: list[str]) -> Project: ...
    def get(self, project_id: str) -> Project: ...
    def list(self) -> list[Project]: ...
    def remove(self, project_id: str) -> None: ...
    def mark_indexed(self, project_id: str, commit: str) -> None: ...
```

## 6. Indexado — siempre completo (drop-and-rebuild)

**Por qué drop-and-rebuild y no solo "reparsear todo sin diff":** si solo se reparsea y se hace `upsert`, los chunks de ficheros borrados o renombrados desde el último índice quedarían huérfanos para siempre (nunca se borran). Vaciar la tabla del proyecto y el grafo antes de reconstruir es lo que hace que "sin lógica de diff" siga siendo **correcto**, no un atajo con fugas.

**Descubrimiento de ficheros**: usar `git ls-files --cached --others --exclude-standard` sobre el `root_path` del proyecto — respeta `.gitignore` automáticamente sin reimplementar su parser, y ya usamos `git` como dependencia. Si el directorio no es un repo git, fallback a un recorrido de directorio con una lista de exclusión mínima (`.git`, `node_modules`, `target`, `build`, `dist`, `venv`, `.venv`, `__pycache__`).

```python
# application/index_project.py
class IndexProject:
    def __init__(self, project_id: str, root_path: str,
                 parser: LanguageParser, embedder: EmbeddingProvider,
                 vector_store: VectorStore, graph_store: GraphStore,
                 lexical_index: LexicalIndex, git: GitProvider):
        self._project_id, self._root_path = project_id, root_path
        self._parser, self._embedder = parser, embedder
        self._vector_store, self._graph_store = vector_store, graph_store
        self._lexical_index, self._git = lexical_index, git

    def execute(self) -> IndexStats:
        self._vector_store.drop(self._project_id)
        self._graph_store.drop(self._project_id)

        chunks, edges = [], []
        for file_path, source in discover_files(self._root_path):
            if not self._parser.supports(file_path):
                continue
            file_chunks, file_edges = self._parser.parse(self._project_id, file_path, source)
            chunks.extend(file_chunks)
            edges.extend(file_edges)

        embeddings = self._embedder.embed_batch([c.source_text for c in chunks])
        chunks = [replace(c, embedding=e) for c, e in zip(chunks, embeddings)]

        self._vector_store.upsert(self._project_id, chunks)
        self._graph_store.upsert_edges(self._project_id, edges)
        self._lexical_index.index(self._project_id, chunks)

        write_manifest(self._root_path, IndexManifest(
            project_id=self._project_id,
            last_indexed_commit=self._git.head(self._root_path),
            last_indexed_at=now_iso(),
            total_chunks=len(chunks), total_edges=len(edges),
        ))
        return IndexStats(total_chunks=len(chunks), total_edges=len(edges))
```

**No existe `ReindexProject` como caso de uso separado.** El comando `reindex` (CLI y tool MCP) llama exactamente a este mismo `IndexProject.execute()`. Es idempotente por construcción (drop + rebuild).

**Manifest** (`<root>/.crm/manifest.json`), igual que capítulo [07](07-indexacion-incremental.md) §4, solo informativo (no gobierna ninguna lógica de diff):

```json
{
  "project_id": "backend-java",
  "last_indexed_commit": "a3f9c21",
  "last_indexed_at": "2026-07-31T10:15:00Z",
  "total_chunks": 1842,
  "total_edges": 3021
}
```

**Nota de evolución futura** (no se implementa ahora): si un proyecto crece lo suficiente como para que un `reindex` completo se vuelva lento o costoso, ese es el momento de revisar el capítulo [07](07-indexacion-incremental.md) e introducir el algoritmo incremental basado en `git diff` — hoy, deliberadamente, no.

## 7. Embeddings

Único adaptador en v1 — capítulo [06](06-embeddings-vector-store.md) §1:

```python
# adapters/embeddings/local_provider.py
from sentence_transformers import SentenceTransformer

class LocalSentenceTransformerProvider:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, batch_size=32, show_progress_bar=False).tolist()

    def dimensions(self) -> int:
        return self._model.get_sentence_embedding_dimension()
```

El puerto `EmbeddingProvider` sigue existiendo tal cual el capítulo 06 para poder añadir Voyage/Qwen3 más adelante sin tocar nada más — pero **no se implementa en v1**.

## 8. Almacenamiento

- **Vectores**: `LanceDbVectorStore` (capítulo [06](06-embeddings-vector-store.md) §2), una tabla por proyecto (`project_<id>`), con `drop()`/`upsert()`/`search()` según el puerto recortado. Cada fila incluye `source_text` completo (decisión fijada, sección 1).
- **Grafo**: `JsonGraphStore`, un fichero `<root>/.crm/graph.json` por proyecto, cargado en memoria con mapas `chunksByFqcn`/`outEdges`/`inEdges` (patrón de `code-rag-mcp/CodeSearcher.java`) y BFS para `dependency_chain()`. `drop()` simplemente vacía el fichero antes de `upsert_edges()`.
- **Léxico**: `InMemorySubstringLexicalIndex` — puntúa por número de coincidencias de substring de la consulta en `symbol` y `file_path` (sin BM25). Se reconstruye por completo en cada `index()`, igual que las otras dos.
- **Registro global**: `YamlProjectRegistry` sobre `~/.crm/projects.yaml`, igual que capítulo [04](04-diseno-multi-proyecto.md) §2.

Todos comparten el mismo ciclo de vida: **drop + rebuild completo en cada indexado**, nunca actualización incremental parcial.

## 9. Parsers v1

Vía tree-sitter, capítulo [05](05-parsing-multilenguaje.md) §2, sin clasificación de capa/rol (decisión fijada):

| Lenguaje | Extensión(es) | Tipos de nodo → chunk |
|---|---|---|
| Python | `.py` | `function_definition`, `class_definition` |
| JavaScript/TypeScript | `.js`, `.ts`, `.jsx`, `.tsx` | `function_declaration`, `class_declaration`, `arrow_function` asignada a `const` |
| Java | `.java` | `method_declaration`, `class_declaration`, `interface_declaration`, `record_declaration` |

Relaciones extraídas por todos (capítulo 05 §3): `import_statement`/`import_from_statement` → `IMPORTS`; `call` → `CALLS`; `extends_clause`/superclases → `EXTENDS`; `implements_clause` → `IMPLEMENTS`.

`GenericTextParser` (capítulo 05 §4) como fallback siempre-último en el `CompositeLanguageParser`, para cualquier fichero de texto sin adaptador dedicado (ventana de 60 líneas, solapamiento 10, sin aristas).

## 10. Servidor MCP — un servidor por proyecto

Resuelve la tensión detectada entre capítulos [04](04-diseno-multi-proyecto.md) §4 y [08](08-servidor-mcp.md) §5: **el `project_id` se fija una vez al arrancar el proceso** (`--project <id>`), no se pide en cada llamada. Internamente, el `composition_root` construye los casos de uso ya cerrados sobre ese `project_id`; las tools MCP no lo exponen.

```python
# adapters/mcp/server.py
from mcp.server.fastmcp import FastMCP
import argparse
from coderagmanager.composition_root import build_use_cases

parser = argparse.ArgumentParser()
parser.add_argument("--project", required=True)
args, _ = parser.parse_known_args()

mcp = FastMCP(f"crm-{args.project}")
uc = build_use_cases(project_id=args.project)   # cierra project_id sobre todos los casos de uso

@mcp.tool()
def search_code(query: str, top_k: int = 10, language: str | None = None, kind: str | None = None) -> str:
    """Busca código relevante por significado y por coincidencia léxica en ESTE proyecto.
    Úsalo como PRIMER paso al explorar el código, antes de leer ficheros directamente."""
    result = uc["search_code"].execute(SearchQuery(text=query, top_k=top_k, language=language, kind=kind))
    return format_search_results(result)

@mcp.tool()
def get_dependency_chain(symbol: str, max_depth: int = 3, direction: str = "both") -> str:
    """Recorre el grafo de dependencias desde `symbol` (qué implementa, qué le llama...)."""
    return format_chain(uc["get_dependency_chain"].execute(symbol, max_depth, direction))

@mcp.tool()
def get_source(symbol: str | None = None, file_path: str | None = None,
                start_line: int | None = None, end_line: int | None = None) -> str:
    """Lee el código fuente real de un chunk. Usar DESPUÉS de search_code/get_dependency_chain."""
    if symbol is None and file_path is None:
        raise ValueError("Debes indicar 'symbol' o 'file_path'.")
    return uc["get_source"].execute(symbol, file_path, start_line, end_line)

@mcp.tool()
def list_chunks(language: str | None = None, kind: str | None = None) -> str:
    """Inventario filtrado de chunks indexados en este proyecto."""
    return format_chunks(uc["list_chunks"].execute(language, kind))

@mcp.tool()
def get_index_stats() -> str:
    """Tamaño del índice y commit indexado de este proyecto. Primer contacto recomendado."""
    return format_stats(uc["get_index_stats"].execute())

@mcp.tool()
def reindex() -> str:
    """Reconstruye el índice completo de este proyecto (recoge cambios locales sin commitear)."""
    stats = uc["index_project"].execute()
    return f"Reindexado: {stats.total_chunks} chunks, {stats.total_edges} aristas"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**Tool surface final (6 tools, sin `project_id`, sin `list_projects`/`use_project` como tools MCP)**: `search_code`, `get_dependency_chain`, `get_source`, `list_chunks`, `get_index_stats`, `reindex`. `list_projects`/`project add`/`project remove` quedan como comandos **solo de CLI** (sección 12) — no tienen sentido como tools MCP cuando el servidor ya está atado a un único proyecto.

## 11. Integración de clientes

Un `.mcp.json` (o equivalente) **por repo**, versionado dentro de ese repo, apuntando siempre a ese proyecto. Sin variable de entorno de API key (modelo local, sección 7):

```json
{
  "mcpServers": {
    "crm-backend-java": {
      "type": "stdio",
      "command": "crm",
      "args": ["mcp", "serve", "--project", "backend-java"]
    }
  }
}
```

`crm mcp install --client claude|codex|copilot --project <id>` genera esta entrada (nombrada `crm-<id>`) en el formato correspondiente (`.mcp.json`, `.codex/config.toml`, `.github/mcp.json` o `~/.copilot/mcp-config.json`), siguiendo el patrón de capítulo [09](09-integracion-clientes.md) §5.

## 12. GitHub Actions (simplificado)

Sin incremental → sin `fetch-depth: 0`, sin "restaurar índice previo". Sin embeddings de pago → sin secrets.

```yaml
# .github/workflows/reindex.yml
name: Reindex code-RAG

on:
  push:
    branches: [main]
  workflow_dispatch: {}

jobs:
  reindex:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Instalar coderagmanager
        run: pip install coderagmanager

      - name: Indexar (reconstrucción completa)
        run: crm index --project . --root .

      - name: Publicar índice actualizado
        run: |
          git config user.name "crm-bot"
          git config user.email "crm-bot@users.noreply.github.com"
          git checkout -B crm-index
          git add .crm
          git commit -m "chore: reindex $(git rev-parse --short HEAD)" || echo "sin cambios"
          git push origin crm-index --force
```

Sincronización local: `crm index pull --project <id>` hace `git fetch origin crm-index` y copia `.crm/` de esa rama al árbol de trabajo local (capítulo [10](10-github-actions.md) §5) — luego, si hay cambios locales sin commitear, la tool MCP `reindex` los recoge con un rebuild completo local.

Se elimina deliberadamente el disparador `schedule` (cron) de la guía original: su única razón de ser era corregir desincronización de un reindexado incremental, que no existe en esta v1.

## 13. CLI completo

```bash
crm init                                       # crea ~/.crm/ si no existe

crm project add <nombre> <ruta>
crm project list
crm project remove <nombre>

crm index --project <nombre>                   # indexado/reindexado: SIEMPRE completo
crm reindex --project <nombre>                 # alias de index, por familiaridad
crm index pull --project <nombre>              # trae el índice publicado por CI

crm search "<consulta>" --project <nombre>     # búsqueda de depuración sin pasar por MCP
crm stats --project <nombre>

crm mcp serve --project <nombre>
crm mcp install --client claude|codex|copilot --project <nombre>

crm config show
crm config set embedding.provider local
```

## 14. Empaquetado

```toml
# pyproject.toml
[project]
name = "coderagmanager"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12",
    "mcp>=1.0",
    "tree-sitter>=0.23",
    "tree-sitter-python", "tree-sitter-javascript", "tree-sitter-java",
    "lancedb",
    "sentence-transformers",
    "pyyaml",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov"]

[project.scripts]
crm = "coderagmanager.adapters.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Sin dependencia `voyageai` (no aplica en v1). Instalación recomendada: `pipx install coderagmanager` (o `pipx install -e .` en desarrollo).

## 15. Explícitamente fuera de alcance de la v1

Para que quede claro que se decidió **no hacerlo todavía**, no que se olvidó:

- Reindexado incremental basado en `git diff` (capítulo 07 completo).
- Proveedores de embeddings alternativos (Voyage AI, Qwen3-Embedding).
- Otros vector stores (ChromaDB, Qdrant).
- Clasificación de capa/rol arquitectónico.
- Servidor MCP multi-proyecto con `project_id` explícito por llamada, y tool `use_project`.
- Retrieval léxico con BM25 real (se usa substring simple).
- Disparador `schedule`/cron en GitHub Actions.

## 16. Roadmap de milestones (adaptado del capítulo 12)

| Milestone | Qué construir | Definición de hecho |
|---|---|---|
| **M0** | Layout, `domain/models.py`, puertos (sin implementación), `pyproject.toml` | `pip install -e .` funciona; un test en `tests/domain/` pasa |
| **M1** | `TreeSitterPythonParser` + `IndexProject` (drop-and-rebuild) + `VectorStore`/`GraphStore` mínimos (JSON plano) | `crm index --project <x>` sobre un repo Python de prueba produce chunks inspeccionables |
| **M2** | `LanceDbVectorStore` real + `LocalSentenceTransformerProvider` + `search_code` (solo semántico) | Una búsqueda por significado devuelve la función correcta aunque no coincida el nombre literal |
| **M3** | Servidor MCP (sección 10) atado a un proyecto vía `--project`, conectado a Claude Code | El agente invoca `search_code`/`get_source` con éxito desde una sesión real |
| **M4** | `YamlProjectRegistry`, `crm project add/list/remove`, aislamiento por `project_id` en storage | Dos proyectos registrados, consultables sin resultados cruzados |
| **M5** | `TreeSitterJavaScriptParser`, `TreeSitterJavaParser`, `GenericTextParser` | Un repo con Python+JS+Java se indexa correctamente sin tocar `IndexProject` ni el dominio |
| **M6** | GitHub Actions (sección 12) + `crm index pull` | Push a `main` dispara el workflow; `crm index pull` trae el índice sin errores |
| **M7** | `LexicalIndex` (substring) combinado en `search_code` + `crm mcp install` para los 3 clientes | Una búsqueda por símbolo exacto y una conceptual devuelven ambas buen resultado; los 3 clientes quedan configurados con un comando cada uno |

(Se elimina el milestone de incremental del capítulo 12 original — no aplica a esta v1.)

## 17. Por dónde empezar mañana

1. `mkdir -p coderagmanager/src/coderagmanager/{domain,ports,application,adapters}` + `pyproject.toml` (sección 14, sin las dependencias de M2+ todavía si prefieres ir progresivo).
2. Escribir `domain/models.py` tal cual la sección 3.
3. Un test trivial en `tests/domain/test_models.py` que construya un `CodeChunk` y afirme sus campos — solo para confirmar que el paquete y `pytest` están conectados (definición de hecho de M0).
4. A partir de ahí, seguir el roadmap de la sección 16 en orden.
