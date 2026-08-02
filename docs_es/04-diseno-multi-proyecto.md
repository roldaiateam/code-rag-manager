# 04 · Diseño multi-proyecto

## 1. El problema

Quieres una única instalación de `codehex` (un solo `pip install`, un solo servidor MCP corriendo) que sepa moverse entre varios repositorios indexados — tu backend en Java, tu frontend en JS, tu librería en Python — sin tener que levantar una instancia distinta por cada uno.

Esto implica dos niveles de estado distintos, que conviene no mezclar:

| Nivel | Qué guarda | Dónde vive | Se versiona en git? |
|---|---|---|---|
| **Registro global** | Qué proyectos existen, dónde está cada uno, su configuración | `~/.codehex/projects.yaml` (fuera de cualquier repo) | No — es local a tu máquina |
| **Estado por proyecto** | El índice en sí: vectores, grafo, manifest con el commit indexado | `<root_del_proyecto>/.codehex/` (dentro de cada repo indexado) | Depende (capítulo 10) — normalmente no en `main`, pero sí se sincroniza vía CI |

## 2. El registro global

```yaml
# ~/.codehex/projects.yaml
projects:
  backend-java:
    root_path: /home/user/repos/mi-backend
    languages: [java]
    embedding_provider: voyage        # override opcional; si no, usa el default global
    last_indexed_commit: a3f9c21
    last_indexed_at: "2026-07-30T18:04:00Z"

  frontend-web:
    root_path: /home/user/repos/mi-frontend
    languages: [javascript, typescript]
    embedding_provider: local
    last_indexed_commit: null         # aún no indexado
    last_indexed_at: null

defaults:
  embedding_provider: local
  vector_store: lancedb
  top_k: 10
```

El puerto `ProjectRegistry` (capítulo 03) es la única pieza que lee/escribe este fichero. Los casos de uso (`RegisterProject`, `ListProjects`, `RemoveProject`, `GetProject`) dependen del puerto, nunca del formato YAML directamente — así, si en el futuro cambias a SQLite para el registro (por ejemplo, si crece a cientos de proyectos), solo tocas el adaptador `YamlProjectRegistry` → `SqliteProjectRegistry`.

```python
# ports/project_registry.py
from typing import Protocol
from domain.models import Project

class ProjectRegistry(Protocol):
    def register(self, name: str, root_path: str, languages: list[str]) -> Project: ...
    def get(self, project_id: str) -> Project: ...
    def list(self) -> list[Project]: ...
    def remove(self, project_id: str) -> None: ...
    def mark_indexed(self, project_id: str, commit: str) -> None: ...
```

## 3. Aislamiento entre proyectos

Cada proyecto necesita su propio espacio dentro del vector store y del grafo de dependencias — nunca deben mezclarse resultados de dos repos distintos en una misma búsqueda salvo que se pida explícitamente. Esto se resuelve con el `project_id` como partición:

- **Vector store**: una colección/tabla por proyecto (LanceDB y Chroma soportan esto de forma nativa — ver capítulo 06), nombrada de forma determinista a partir del `project_id`.
- **Grafo**: un fichero de índice por proyecto (`<root>/.codehex/graph.json`), o una tabla filtrada por `project_id` si usas un único almacén compartido.
- **Registro global**: una entrada por proyecto, como se ve arriba.

Esta partición es precisamente por qué todos los métodos de `VectorStore`/`GraphStore` en el capítulo 03 llevan `project_id` como primer parámetro — no es un detalle menor, es la costura de diseño que hace posible el multi-proyecto sin que cada puerto tenga que "saber" de proyectos (el puerto solo opera "dentro de un espacio con nombre"; quién es ese espacio lo decide siempre la capa de aplicación).

## 4. Comandos de gestión (adelanto del capítulo 11)

```bash
codehex project add backend-java /home/user/repos/mi-backend
codehex project list
codehex project remove backend-java
codehex index --project backend-java
codehex search "validación de tarjeta de crédito" --project backend-java
```

El servidor MCP (capítulo 08) expone el equivalente de `project list` como una tool (`list_projects`) y, si el cliente no especifica proyecto en cada llamada, puede fijar un proyecto "activo" para la sesión (`use_project`) — o, más simple para una primera versión, exigir `project_id` como parámetro obligatorio en cada tool, delegando en el agente LLM la responsabilidad de indicarlo (más explícito, menos estado que gestionar).

## 5. El patrón que ya resuelve esto: registro multi-repo de `kairosai`

`kairosai` no hace RAG, pero ya resolvió exactamente este problema para un caso adyacente: cada **workspace** en `kairosai` registra una lista de `repos` (nombre, URL de origen) en su `manifest.yaml`, y al "instalar" el workspace, cada repo se clona/actualiza en `runtimes/<workspace>/repos/<nombre>/` de forma independiente.

La correspondencia con el diseño de este capítulo:

| kairosai | codehex |
|---|---|
| `workspace` con lista de `repos` en `manifest.yaml` | registro global `~/.codehex/projects.yaml` con lista de proyectos |
| clonado/actualización por repo en `install.py` | indexado/reindexado por proyecto (capítulo 07) |
| cada repo clonado es independiente del resto | cada proyecto indexado (colección de vector store + grafo) es independiente del resto |

La diferencia de diseño deliberada: `kairosai` ata el registro de repos a un *workspace* con herencia y configuración compartida (apropiado para su caso de uso, gestionar configuración de Claude). `codehex` no necesita ese nivel — un registro plano de proyectos es suficiente porque no hay "herencia" de índice entre proyectos: cada uno se indexa y consulta de forma completamente independiente. Si en el futuro quieres agrupar proyectos (p.ej. "todos los servicios de un mismo dominio") puedes añadir una etiqueta/tag al registro sin necesidad de reintroducir el concepto completo de workspace.

## Ideas reutilizables de los proyectos existentes

- **De `kairosai`**: el patrón de registro-por-nombre con estado de sincronización (`last_indexed_commit` aquí, equivalente al tracking de qué está clonado/actualizado allí) y el patrón de descubrimiento de raíz de proyecto (`find_project_root()` recorriendo directorios hacia arriba en busca de una carpeta marcador) — reutilizable para que `codehex` detecte automáticamente si el directorio actual pertenece a un proyecto ya registrado, sin que el usuario tenga que pasar `--project` siempre.

## Siguiente paso

[05 · Parsing multi-lenguaje](05-parsing-multilenguaje.md): cómo se implementa en la práctica el `LanguageParser` para Python, JavaScript, Java y cualquier lenguaje futuro.
