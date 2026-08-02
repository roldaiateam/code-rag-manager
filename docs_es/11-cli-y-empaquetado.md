# 11 · CLI y empaquetado

## 1. Superficie de comandos

```bash
codehex init                                   # crea ~/.codehex/ si no existe (registro global)

codehex project add <nombre> <ruta>            # registra un proyecto (capítulo 04)
codehex project list
codehex project remove <nombre>

codehex index --project <nombre>               # indexado completo (capítulo 03)
codehex reindex --project <nombre>             # incremental si hay índice previo (capítulo 07)
codehex index pull --project <nombre>          # trae el índice publicado por CI (capítulo 10)

codehex search "<consulta>" --project <nombre> # búsqueda de depuración, sin pasar por MCP
codehex stats --project <nombre>               # equivalente CLI de get_index_stats

codehex mcp serve --project <nombre>           # arranca el servidor MCP por stdio (capítulo 08)
codehex mcp install --client claude|codex|copilot   # genera la configuración del cliente (capítulo 09)

codehex config show                            # ver configuración efectiva (defaults + overrides)
codehex config set embedding.provider voyage
```

Cada comando es una fachada delgada sobre un caso de uso de la capa de aplicación (capítulo 03) — el adaptador CLI (`adapters/cli/`) solo parsea argumentos, construye el caso de uso vía `composition_root`, lo ejecuta, y formatea la salida para terminal. No debería contener lógica de negocio en absoluto; si te encuentras escribiendo un `if` que decide *qué* hacer (no solo *cómo mostrarlo*), esa lógica pertenece a un caso de uso, no al comando CLI.

```python
# adapters/cli/main.py
import typer
from composition_root import build_use_cases

app = typer.Typer(name="codehex")
project_app = typer.Typer(name="project")
app.add_typer(project_app)

@project_app.command("add")
def project_add(name: str, path: str):
    uc = build_use_cases()
    project = uc["register_project"].execute(name, path)
    typer.echo(f"Proyecto '{project.name}' registrado en {project.root_path}")

@app.command()
def reindex(project: str = typer.Option(..., "--project")):
    uc = build_use_cases()
    stats = uc["reindex_project"].execute(project)
    typer.echo(f"Reindexado: {stats.reparsed} ficheros, {stats.new_chunks} chunks nuevos")
```

## 2. Empaquetado

```toml
# pyproject.toml
[project]
name = "codehex"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12",
    "mcp>=1.0",
    "tree-sitter>=0.23",
    "tree-sitter-python", "tree-sitter-javascript", "tree-sitter-java",
    "lancedb",
    "sentence-transformers",   # proveedor de embeddings local por defecto
    "pyyaml",
]

[project.optional-dependencies]
voyage = ["voyageai"]          # solo si se usa el proveedor de pago
dev = ["pytest>=8.0", "pytest-cov"]

[project.scripts]
codehex = "codehex.adapters.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Instalación como herramienta de línea de comandos aislada (recomendado sobre `pip install` global, para no mezclar sus dependencias con las de otros proyectos Python del desarrollador):

```bash
pipx install codehex
# o, para desarrollo local del propio codehex:
pipx install -e .
```

Este es el mismo patrón de distribución que ya usa `kairosai` (`pipx install .` / `pip install -e .`), por coherencia entre las herramientas de este mismo espacio de trabajo.

## 3. Estrategia de tests

Siguiendo la separación por capas del capítulo 03, cada capa se testea con un enfoque distinto y un coste distinto:

| Capa | Qué se testea | Cómo |
|---|---|---|
| `domain/` | Reglas puras (p.ej. `merge_and_rerank`, clasificadores) | Tests unitarios sin dobles de prueba — son funciones puras, entrada→salida |
| `application/` | Casos de uso orquestando puertos | Tests unitarios con **dobles de prueba (fakes) de los puertos**, no mocks frágiles acoplados a la implementación — un `FakeVectorStore` en memoria es más robusto ante refactors que un mock que verifica llamadas exactas |
| `adapters/` | Cada adaptador contra la librería real que envuelve | Tests de integración específicos por adaptador (p.ej. `TreeSitterPythonParser` contra un fragmento de código Python real y fijo) |
| End-to-end | El pipeline completo | Un test de integración con un **repositorio fixture** pequeño y controlado (unos pocos ficheros Python/JS/Java de ejemplo con relaciones conocidas) que corre `index` y verifica el resultado — este es el test que más confianza da con menos mantenimiento |

```python
# tests/application/test_search_code.py
class FakeVectorStore:
    def __init__(self):
        self._data: dict[str, list[CodeChunk]] = {}
    def upsert(self, project_id, chunks):
        self._data.setdefault(project_id, []).extend(chunks)
    def search(self, project_id, query_embedding, top_k):
        return [SearchResult(chunk=c, score=1.0, match_reason="semantic")
                for c in self._data.get(project_id, [])[:top_k]]

def test_search_code_returns_results_from_vector_store():
    fake_store = FakeVectorStore()
    fake_store.upsert("p1", [make_chunk(symbol="validar_email")])
    use_case = SearchCode(embedder=FakeEmbedder(), vector_store=fake_store, lexical_index=FakeLexicalIndex())

    results = use_case.execute(SearchQuery(project_id="p1", text="validación de email"))

    assert any(r.chunk.symbol == "validar_email" for r in results)
```

No hace falta un vector store real ni una llamada a un modelo de embeddings real para probar que `SearchCode` orquesta correctamente — eso es exactamente lo que compra la separación en puertos.

## 4. Versionado

Semver estándar (`MAJOR.MINOR.PATCH`). Ten en cuenta un matiz propio de este dominio: un cambio en el `inputSchema` de una tool MCP (renombrar un parámetro, hacer obligatorio algo que era opcional) es un cambio incompatible desde el punto de vista de los clientes ya configurados (Claude Code, Codex CLI, Copilot CLI con configuración existente) — trátalo como *breaking change* (bump de `MAJOR`) igual que tratarías un cambio de API pública, no como un detalle interno.

## Ideas reutilizables de los proyectos existentes

- **De `kairosai`**: la combinación CLI (Typer) + empaquetado vía `pyproject.toml` + `pipx` es exactamente el mismo patrón, reutilizable prácticamente sin cambios.

## Siguiente paso

[12 · Guía paso a paso](12-guia-paso-a-paso.md): el roadmap concreto de construcción, en el orden en que conviene abordarlo.
