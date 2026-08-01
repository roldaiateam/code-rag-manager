"""Vista esqueleto de un chunk de código: estructura completa (declaraciones,
campos, firmas, anotaciones) con los cuerpos de método elididos.

Conserva el ~100% de la señal estructural en una fracción de los tokens —
pensado para clases largas (típicamente código generado). Cualquier fallo
devuelve None: el esqueleto es una optimización, nunca un punto de fallo
(el llamador degrada a truncado por cabeza).
"""

from __future__ import annotations

from tree_sitter import Language, Parser

from coderagmanager.adapters.parsers.base import walk

_PARSERS: dict[str, Parser] = {}

# tipos de nodo cuyo campo `body` se elide, por lenguaje
_ELIDABLE = {
    "java": {"method_declaration", "constructor_declaration"},
    "javascript": {"method_definition", "function_declaration"},
    "python": {"function_definition"},
}
_BODY_PLACEHOLDER = {"java": "{ ... }", "javascript": "{ ... }", "python": "..."}


def skeletonize(language: str, source: str) -> str | None:
    if language not in _ELIDABLE:
        return None
    try:
        parser = _get_parser(language)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        if tree.root_node.has_error:
            return None
        replacements = _body_replacements(language, tree.root_node, source_bytes)
        if not replacements:
            return None
        return _splice(source_bytes, replacements)
    except Exception:
        return None


def _get_parser(language: str) -> Parser:
    if language not in _PARSERS:
        if language == "java":
            import tree_sitter_java as grammar
        elif language == "javascript":
            import tree_sitter_javascript as grammar
        else:
            import tree_sitter_python as grammar
        _PARSERS[language] = Parser(Language(grammar.language()))
    return _PARSERS[language]


def _body_replacements(language, root, source_bytes) -> list[tuple[int, int, str]]:
    placeholder = _BODY_PLACEHOLDER[language]
    replacements = []
    for node in walk(root):
        if node.type not in _ELIDABLE[language]:
            continue
        body = node.child_by_field_name("body")
        if body is None:  # métodos abstractos / de interfaz: nada que elidir
            continue
        if language == "python":
            replacements.append(_python_body_replacement(body, source_bytes))
        else:
            replacements.append((body.start_byte, body.end_byte, placeholder))
    return replacements


def _python_body_replacement(body, source_bytes) -> tuple[int, int, str]:
    """Elide el cuerpo conservando el docstring si es la primera sentencia."""
    first = body.children[0] if body.children else None
    if (
        first is not None
        and first.type == "expression_statement"
        and first.children
        and first.children[0].type == "string"
    ):
        indent = " " * first.start_point[1]
        return (first.end_byte, body.end_byte, f"\n{indent}...")
    return (body.start_byte, body.end_byte, "...")


def _splice(source_bytes: bytes, replacements: list[tuple[int, int, str]]) -> str:
    out, pos = [], 0
    for start, end, text in sorted(replacements):
        if start < pos:  # anidado dentro de un cuerpo ya elidido
            continue
        out.append(source_bytes[pos:start].decode("utf-8", errors="replace"))
        out.append(text)
        pos = end
    out.append(source_bytes[pos:].decode("utf-8", errors="replace"))
    return "".join(out)
