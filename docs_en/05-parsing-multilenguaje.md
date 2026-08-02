# 05 · Multi-language parsing

## 1. What tree-sitter is and why it's the natural choice here

**tree-sitter** is an incremental parser generator, with grammars already written and maintained for practically every popular language (Python, JavaScript/TypeScript, Java, Go, Rust, C#...). It converts source code into an **AST** (Abstract Syntax Tree): a structure of nodes where each node is a language construct (`function_definition`, `class_declaration`, `method_declaration`, `import_statement`...).

Why it's the natural choice for this project, against the alternatives:

| Option | Advantage | Why it's not the one chosen here |
|---|---|---|
| Dedicated per-language parser (e.g. JavaParser, used by `code-rag-mcp`) | Maximum semantic fidelity for that specific language | A different one per language, with different APIs — the cost of adding a new language is high and not reusable |
| **tree-sitter** | A uniform API across many languages; grammars maintained by the community; fast incremental parsing | Gives you the syntactic AST, not full type/semantic resolution (not needed for chunking) |
| Regex / text heuristics | Zero dependencies | Fragile: fails with nesting, comments containing example code, multiline strings, etc. — ruled out except as a fallback (section 4) |

For *chunking* (finding where a function/class starts and ends) you don't need type or cross-file symbol resolution — you need to know "this is a `function_definition` and spans from line 40 to 58." That's exactly what a syntactic AST gives you, and it's what tree-sitter resolves uniformly across languages.

## 2. The per-language `LanguageParser` adapter

Recalling the port from chapter 03:

```python
class LanguageParser(Protocol):
    def supports(self, file_path: str) -> bool: ...
    def parse(self, project_id: str, file_path: str, source: str) -> tuple[list[CodeChunk], list[DependencyEdge]]: ...
```

Each language adapter follows the same general shape:

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
        symbol = name_node.text.decode() if name_node else "<anonymous>"
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

`TreeSitterJavaScriptParser` and `TreeSitterJavaParser` follow exactly the same shape — what changes is the imported grammar (`tree_sitter_javascript`, `tree_sitter_java`) and which node types count as a "chunk" in each language (in Java: `method_declaration`, `class_declaration`, `interface_declaration`, `record_declaration`; in JS/TS: `function_declaration`, `class_declaration`, `arrow_function` assigned to a constant, since in JS a function can be declared in several different syntactic forms).

This uniformity is exactly what makes adding a new language cheap: **copy this file, change the grammar and the list of relevant node types**. You don't need to touch `IndexProject`, the domain, or the vector store — the port already defines the contract.

## 3. Extracting relationships (for the structural layer from chapter 02)

Besides the chunks, each parser extracts edges (`DependencyEdge`) by walking the same AST:

| Relationship | tree-sitter node (approx., varies by language) | Edge type |
|---|---|---|
| Module import / usage | `import_statement`, `import_from_statement` | `IMPORTS` |
| Function/method call | `call` | `CALLS` |
| Class inheritance | `class_definition` with `superclasses`/`extends_clause` | `EXTENDS` |
| Interface implementation (Java/TS) | `implements_clause` | `IMPLEMENTS` |

There's no need to resolve exactly which symbol each call points to with full type precision — for navigation purposes (chapter 02, `get_dependency_chain`) a reasonable "by name" resolution is enough (if `calcular_total` calls `validar_stock` and there's a single `validar_stock` symbol in the project, it's linked; if there are several with that name in different modules, the closest one in the same file/module is prioritized, the same way `code-rag-mcp` does with FQCN and simple name).

## 4. Generic fallback: "minimum viable" support for any language

The "flexible to other languages" requirement shouldn't mean "only works if someone writes a dedicated tree-sitter adapter first." That's why a **fallback parser** is worth having, applied to any text file without a dedicated adapter, using sliding-window chunking (the "fixed-size chunking" from chapter 02 — worse than structural, but better than not indexing at all):

```python
# adapters/parsers/generic_text.py
class GenericTextParser:
    def __init__(self, window_lines: int = 60, overlap_lines: int = 10):
        self._window = window_lines
        self._overlap = overlap_lines

    def supports(self, file_path: str) -> bool:
        return True   # always applicable — must be registered last in the CompositeLanguageParser

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
        return chunks, []   # no structural relationships — semantic/lexical layer only
```

The `CompositeLanguageParser` (seen in chapter 03) tries the parsers in order and uses the first one whose `supports()` returns `True` — with `GenericTextParser` always at the end of the list as a safety net.

## 5. Optional enrichment: layer/role classification

As previewed in chapter 02, classifying each chunk by architectural layer and role is an enrichment *on top of* the base model, not part of the core. If you want to implement it, follow `code-rag-mcp`'s pattern: pure, stateless functions that take the already-extracted chunk and return a label, based on ecosystem heuristics (package/folder, decorators or annotations):

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

Each ecosystem needs its own heuristics (Spring in Java uses annotations like `@RestController`/`@Entity`; a FastAPI project in Python would use decorators like `@app.get`/Pydantic models; a project without a recognizable convention simply doesn't classify, and the `layer`/`role` filter in the MCP tools has no effect for that project — nothing breaks).

## Reusable ideas from the existing projects

- **From `code-rag-mcp`**: `FileScopes` (which files are indexable — excluding `target/`, `build/`, tests if desired, generating exceptions for generated files like OpenAPI interfaces) is a directly transferable pattern, generalized to also respect each project's `.gitignore`. `Classifiers` as pure functions is the exact pattern from section 5.

## Next step

[06 · Embeddings and vector store](06-embeddings-vector-store.md): what to do with each `CodeChunk` once extracted — how to turn it into a vector and where to store it so it can be searched.
