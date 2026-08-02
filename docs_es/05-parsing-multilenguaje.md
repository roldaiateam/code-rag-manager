# 05 · Parsing multi-lenguaje

## 1. Qué es tree-sitter y por qué es la elección natural aquí

**tree-sitter** es un generador de parsers incremental, con gramáticas ya escritas y mantenidas para prácticamente todos los lenguajes populares (Python, JavaScript/TypeScript, Java, Go, Rust, C#...). Convierte código fuente en un **AST** (Abstract Syntax Tree — árbol de sintaxis abstracta): una estructura de nodos donde cada nodo es una construcción del lenguaje (`function_definition`, `class_declaration`, `method_declaration`, `import_statement`...).

Por qué es la elección natural para este proyecto, frente a alternativas:

| Opción | Ventaja | Por qué no es la elegida aquí |
|---|---|---|
| Parser dedicado por lenguaje (p.ej. JavaParser, que usa `code-rag-mcp`) | Máxima fidelidad semántica para ese lenguaje concreto | Uno distinto por lenguaje, con APIs distintas — el coste de añadir un lenguaje nuevo es alto y no reutilizable |
| **tree-sitter** | Una API uniforme para muchos lenguajes; gramáticas mantenidas por la comunidad; parseo incremental rápido | Da el AST sintáctico, no resolución de tipos/semántica completa (para chunking no hace falta) |
| Regex / heurísticas de texto | Cero dependencias | Fragil: falla con anidamiento, comentarios con código de ejemplo dentro, strings multilínea, etc. — descartado salvo como fallback (sección 4) |

Para *chunking* (encontrar dónde empieza y termina una función/clase) no necesitas resolución de tipos ni de símbolos entre ficheros — necesitas saber "esto es un `function_definition` y ocupa de la línea 40 a la 58". Eso es exactamente lo que da un AST sintáctico, y es lo que tree-sitter resuelve de forma uniforme entre lenguajes.

## 2. El adaptador `LanguageParser` por lenguaje

Recordando el puerto del capítulo 03:

```python
class LanguageParser(Protocol):
    def supports(self, file_path: str) -> bool: ...
    def parse(self, project_id: str, file_path: str, source: str) -> tuple[list[CodeChunk], list[DependencyEdge]]: ...
```

Cada adaptador de lenguaje sigue la misma forma general:

```python
# adapters/parsers/tree_sitter_python.py
from tree_sitter import Language, Parser
import tree_sitter_python as tspython

CHUNK_NODE_TYPES = {"function_definition", "class_definition"}

class TreeSitterPythonParser:
    def __init__(self):
        self._parser = Parser(Language(tspython.language()))

    def supports(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def parse(self, project_id, file_path, source):
        tree = self._parser.parse(source.encode("utf-8"))
        chunks, edges = [], []
        for node in walk(tree.root_node):
            if node.type in CHUNK_NODE_TYPES:
                chunk = self._to_chunk(project_id, file_path, source, node)
                chunks.append(chunk)
            if node.type == "import_statement":
                edges.append(self._to_import_edge(project_id, file_path, node))
        return chunks, edges

    def _to_chunk(self, project_id, file_path, source, node):
        text = source[node.start_byte:node.end_byte]
        name_node = node.child_by_field_name("name")
        symbol = name_node.text.decode() if name_node else "<anónimo>"
        return CodeChunk(
            id=stable_id(file_path, symbol, node.start_point[0]),
            project_id=project_id,
            language="python",
            symbol=symbol,
            kind="class" if node.type == "class_definition" else "function",
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            source_text=text,
            metadata={},
        )
```

`TreeSitterJavaScriptParser` y `TreeSitterJavaParser` siguen exactamente la misma forma — cambia la gramática importada (`tree_sitter_javascript`, `tree_sitter_java`) y qué tipos de nodo cuentan como "chunk" en cada lenguaje (en Java: `method_declaration`, `class_declaration`, `interface_declaration`, `record_declaration`; en JS/TS: `function_declaration`, `class_declaration`, `arrow_function` asignada a una constante, dado que en JS una función puede declararse de varias formas sintácticas distintas).

Esta uniformidad es exactamente lo que hace barato añadir un lenguaje nuevo: **copiar este fichero, cambiar la gramática y la lista de tipos de nodo relevantes**. No hay que tocar `IndexProject`, ni el dominio, ni el vector store — el puerto ya define el contrato.

## 3. Extracción de relaciones (para la capa estructural del capítulo 02)

Además de los chunks, cada parser extrae aristas (`DependencyEdge`) recorriendo el mismo AST:

| Relación | Nodo tree-sitter (aprox., varía por lenguaje) | Tipo de arista |
|---|---|---|
| Import / uso de módulo | `import_statement`, `import_from_statement` | `IMPORTS` |
| Llamada a función/método | `call` | `CALLS` |
| Herencia de clase | `class_definition` con `superclasses`/`extends_clause` | `EXTENDS` |
| Implementación de interfaz (Java/TS) | `implements_clause` | `IMPLEMENTS` |

No hace falta resolver a qué símbolo exacto apunta cada llamada con precisión total de tipo — para el propósito de navegación (capítulo 02, `get_dependency_chain`) basta con una resolución "por nombre" razonable (si `calcular_total` llama a `validar_stock` y hay un único símbolo `validar_stock` en el proyecto, se enlaza; si hay varios con ese nombre en módulos distintos, se prioriza el más cercano en el mismo fichero/módulo, igual que hace `code-rag-mcp` con FQCN y nombre simple).

## 4. Fallback genérico: soporte "de mínimos" para cualquier lenguaje

El requisito de "flexible a otros lenguajes" no debería significar "solo funciona si alguien escribe un adaptador tree-sitter dedicado primero". Por eso conviene un **parser de reserva** que se aplica a cualquier fichero de texto sin adaptador dedicado, usando chunking por ventana deslizante (el "chunking de tamaño fijo" del capítulo 02 — peor que el estructural, pero mejor que no indexar nada):

```python
# adapters/parsers/generic_text.py
class GenericTextParser:
    def __init__(self, window_lines: int = 60, overlap_lines: int = 10):
        self._window = window_lines
        self._overlap = overlap_lines

    def supports(self, file_path: str) -> bool:
        return True   # siempre es aplicable — debe registrarse último en el CompositeLanguageParser

    def parse(self, project_id, file_path, source):
        lines = source.splitlines()
        chunks = []
        step = self._window - self._overlap
        for start in range(0, len(lines), step):
            block = lines[start:start + self._window]
            if not block:
                break
            chunks.append(CodeChunk(
                id=stable_id(file_path, "block", start),
                project_id=project_id, language="text", symbol=f"L{start+1}-L{start+len(block)}",
                kind="block", file_path=file_path,
                start_line=start + 1, end_line=start + len(block),
                source_text="\n".join(block), metadata={},
            ))
        return chunks, []   # sin relaciones estructurales — solo capa semántica/léxica
```

El `CompositeLanguageParser` (visto en el capítulo 03) prueba los parsers en orden y usa el primero cuyo `supports()` devuelva `True` — con `GenericTextParser` siempre al final de la lista como red de seguridad.

## 5. Enriquecimiento opcional: clasificación de capa/rol

Como se adelantó en el capítulo 02, clasificar cada chunk por capa arquitectónica y rol es un enriquecimiento *sobre* el modelo base, no parte del núcleo. Si quieres implementarlo, sigue el patrón de `code-rag-mcp`: funciones puras, sin estado, que reciben el chunk ya extraído y devuelven una etiqueta, basándose en heurísticas del ecosistema (paquete/carpeta, decoradores o anotaciones):

```python
def classify_layer(chunk: CodeChunk) -> str | None:
    path = chunk.file_path
    if "/domain/" in path:
        return "domain"
    if "/application/" in path or "/use_cases/" in path:
        return "application"
    if "/adapters/" in path or "/infrastructure/" in path:
        return "infrastructure"
    return None
```

Cada ecosistema necesita sus propias heurísticas (Spring en Java usa anotaciones como `@RestController`/`@Entity`; un proyecto FastAPI en Python usaría decoradores como `@app.get`/modelos Pydantic; un proyecto sin convención reconocible simplemente no clasifica, y el filtro `layer`/`role` en las tools MCP queda sin efecto para ese proyecto — no rompe nada).

## Ideas reutilizables de los proyectos existentes

- **De `code-rag-mcp`**: `FileScopes` (qué ficheros son indexables — excluir `target/`, `build/`, tests si se desea, generar excepciones para ficheros generados como interfaces OpenAPI) es un patrón directamente trasladable, generalizado para respetar además `.gitignore` de cada proyecto. `Classifiers` como funciones puras es el patrón exacto de la sección 5.

## Siguiente paso

[06 · Embeddings y vector store](06-embeddings-vector-store.md): qué hacer con cada `CodeChunk` una vez extraído — cómo convertirlo en un vector y dónde guardarlo para poder buscarlo.
