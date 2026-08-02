# 08 · Servidor MCP

## 1. Qué es MCP, sin dar por hecho nada

**MCP (Model Context Protocol)** es un protocolo abierto, estandarizado por Anthropic y adoptado por el ecosistema, para que un agente LLM (el cliente: Claude Code, Codex CLI, Copilot CLI...) descubra y use herramientas externas de forma uniforme, sin que cada integración sea un caso especial.

Piezas del protocolo que necesitas conocer para diseñar el servidor:

- **Transporte**: cómo viajan los mensajes. Los dos relevantes para este proyecto son **stdio** (el servidor es un proceso local, el cliente le escribe por su entrada estándar y lee su salida estándar — sin red, sin puertos, arranca y muere con la sesión del cliente) y **HTTP** (streamable-http, para servidores remotos). Para un servidor que se ejecuta en la máquina del desarrollador junto a su código, **stdio es la elección natural** — es también lo que usa `code-rag-mcp` hoy.
- **Mensajes JSON-RPC 2.0**: cada petición/respuesta es un objeto JSON con `method`, `params`, `id` (para peticiones) y `result`/`error` (para respuestas). No necesitas implementarlo a mano — el SDK lo resuelve.
- **Capacidades**: al conectar, cliente y servidor negocian qué soporta cada uno. Este proyecto solo necesita anunciar la capacidad `tools` (herramientas invocables) — no hace falta `resources` ni `prompts` para el alcance de esta guía.
- **Tool**: una función expuesta con nombre, descripción y un `inputSchema` (JSON Schema) que describe sus parámetros. El cliente LLM decide cuándo llamarla según la descripción — por eso la calidad de la descripción importa tanto como la implementación (sección 3).

## 2. El SDK oficial de Python: FastMCP

El SDK oficial de MCP en Python incluye una capa de alto nivel, **FastMCP**, que convierte una función Python normal (con type hints y docstring) en una tool MCP completa — genera el `inputSchema` a partir de los tipos, valida la entrada, y gestiona el ciclo de vida del protocolo. Esto es lo que evita tener que escribir JSON-RPC a mano, como sí hace `code-rag-mcp` en Java (sin SDK oficial disponible en ese lenguaje).

```python
# adapters/mcp/server.py
from mcp.server.fastmcp import FastMCP
from composition_root import build_use_cases

mcp = FastMCP("codehex")
uc = build_use_cases()   # diccionario/objeto con todos los casos de uso ya inyectados

@mcp.tool()
def search_code(project_id: str, query: str, top_k: int = 10,
                 language: str | None = None, kind: str | None = None) -> str:
    """Busca código relevante por significado y por coincidencia léxica.

    Úsalo como PRIMER paso al explorar un proyecto: encuentra funciones, clases
    y métodos relevantes antes de leer el código fuente directamente.

    Args:
        project_id: identificador del proyecto registrado (ver list_projects).
        query: descripción en lenguaje natural o palabras clave de lo que buscas.
        top_k: número máximo de resultados (por defecto 10; sube a 20-30 para
            búsquedas exploratorias).
        language: filtra por lenguaje ("python", "javascript", "java"...).
        kind: filtra por tipo de chunk ("function", "class", "method"...).
    """
    query_obj = SearchQuery(project_id=project_id, text=query, top_k=top_k,
                             language=language, kind=kind)
    results = uc["search_code"].execute(query_obj)
    return format_search_results(results)   # texto legible, no un dict crudo

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Cada docstring cumple una doble función: es documentación para quien lee el código **y** es lo que el cliente LLM lee para decidir cuándo invocar la tool. Por eso, igual que hace `code-rag-mcp` en su README, conviene ser explícito sobre "cuándo usar esto" y, cuando aplique, "cuándo NO usarlo" (para evitar que el agente llame a `search_code` cuando lo que necesita es `list_chunks`, por ejemplo).

## 3. Diseño del tool surface

Superset directo del ya validado por `code-rag-mcp`, con las herramientas de la capa semántica y multi-proyecto añadidas:

| Tool | Qué hace | Caso de uso que invoca |
|---|---|---|
| `list_projects` | Lista los proyectos registrados y su estado de indexado | `ListProjects` |
| `search_code` | Búsqueda híbrida semántica+léxica | `SearchCode` |
| `get_dependency_chain` | Recorrido BFS del grafo de dependencias (`className`, `maxDepth`, `direction`) | `GetDependencyChain` |
| `get_source` | Lee código fuente real, por símbolo o por ruta+líneas | `GetSource` |
| `list_chunks` | Inventario filtrado (por lenguaje, kind, capa/rol si está clasificado) | `ListChunks` |
| `get_index_stats` | Tamaño del índice, distribución, commit indexado — primer contacto con un proyecto | `GetIndexStats` |
| `reindex` | Dispara `ReindexProject` (incremental si hay índice previo) | `ReindexProject` |

El orden recomendado de uso, para incluir en la descripción de las tools o en un prompt/documentación adicional (patrón que ya usa el README de `code-rag-mcp` con buenos resultados): `list_projects` → `get_index_stats` → `search_code` → `get_dependency_chain` → `get_source`, de lo general a lo específico, minimizando lectura de código innecesaria.

## 4. Manejo de errores

MCP distingue entre un **error de protocolo** (petición malformada, tool inexistente — gestionado por el SDK) y un **error de dominio** devuelto como resultado válido con `isError: true` (p.ej., "el proyecto `foo` no está registrado" no es un fallo del protocolo, es una respuesta legítima que el agente debe poder leer y corregir su siguiente llamada):

```python
@mcp.tool()
def get_source(project_id: str, symbol: str | None = None,
                file_path: str | None = None,
                start_line: int | None = None, end_line: int | None = None) -> str:
    """Lee código fuente real. Usar DESPUÉS de search_code o get_dependency_chain,
    cuando el resumen no basta y hace falta ver la implementación."""
    if symbol is None and file_path is None:
        raise ValueError("Debes indicar 'symbol' o 'file_path', no ninguno de los dos.")
    try:
        return uc["get_source"].execute(project_id, symbol, file_path, start_line, end_line)
    except ProjectNotFoundError as e:
        raise ValueError(f"Proyecto '{project_id}' no registrado. Usa list_projects para ver los disponibles.") from e
```

FastMCP convierte una excepción no capturada en una respuesta de error MCP con el mensaje incluido — suficiente para que el agente entienda qué corregir, sin necesidad de un manejo de errores más elaborado en una primera versión.

## 5. Multi-proyecto en el servidor: sesión sin estado vs. proyecto activo

Dos formas válidas de resolver "a qué proyecto se refiere esta llamada", con distinto coste:

- **`project_id` explícito en cada tool** (el diseño de la tabla de arriba): más verboso por llamada, pero sin estado que gestionar en el servidor — cada petición es autocontenida, y es trivial de razonar y testear. Recomendado para una primera versión.
- **Tool `use_project`** que fija un proyecto activo para el resto de la sesión, y el resto de tools lo omiten: menos verboso, pero introduce estado mutable en el servidor (¿qué pasa si dos clientes usan el mismo proceso servidor? En stdio esto no ocurre — cada cliente lanza su propio proceso — así que el riesgo es bajo, pero añade una pieza más a explicar y mantener).

Esta guía recomienda empezar con `project_id` explícito (más simple, más fácil de razonar) y añadir `use_project` después solo si el uso real demuestra que la verbosidad molesta.

## Ideas reutilizables de los proyectos existentes

- **De `code-rag-mcp`**: el tool surface completo (`search_code`, `get_dependency_chain`, `get_source`, `list_chunks`, `get_index_stats`, `reindex`) está validado en producción tal cual, incluyendo el orden de uso recomendado y el patrón de documentar explícitamente "cuándo usarlo / cuándo no" en cada descripción — cópialo casi literalmente, añadiendo `project_id` a cada firma y `list_projects` como tool nueva.
- **De `kairosai`**: el patrón de operaciones largas con progreso en streaming (generadores consumidos por `StreamingResponse`) es aplicable si expones `reindex` también desde una interfaz que no sea el propio protocolo MCP síncrono (p.ej. si añades una CLI o UI de estado, capítulo 11) — MCP en sí no requiere streaming de progreso para tools síncronas simples.

## Siguiente paso

[09 · Integración con clientes](09-integracion-clientes.md): cómo registrar este servidor en Claude Code, Codex CLI y GitHub Copilot CLI.
