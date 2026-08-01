"""Utilidades compartidas por los parsers tree-sitter."""

from __future__ import annotations

from collections.abc import Iterator

from tree_sitter import Node


def walk(node: Node) -> Iterator[Node]:
    """Recorrido en profundidad de todos los nodos del árbol."""
    yield node
    for child in node.children:
        yield from walk(child)


def node_text(source_bytes: bytes, node: Node) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def enclosing_of_types(node: Node, types: set[str]) -> Node | None:
    """El ancestro más cercano cuyo tipo esté en `types` (sin contar el propio nodo)."""
    current = node.parent
    while current is not None:
        if current.type in types:
            return current
        current = current.parent
    return None
