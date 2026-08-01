from __future__ import annotations

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from coderagmanager.adapters.parsers.base import enclosing_of_types, node_text, walk
from coderagmanager.domain.models import (
    CodeChunk,
    DependencyEdge,
    EdgeType,
    stable_id,
)
from coderagmanager.domain.resolution import unresolved_ref

CHUNK_NODE_TYPES = {"function_definition", "class_definition"}


class TreeSitterPythonParser:
    def __init__(self):
        self._parser = Parser(Language(tspython.language()))

    def supports(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def parse(self, project_id: str, file_path: str, source: str):
        source_bytes = source.encode("utf-8")
        tree = self._parser.parse(source_bytes)
        chunks: list[CodeChunk] = []
        edges: list[DependencyEdge] = []
        chunk_id_by_node: dict[int, str] = {}

        for node in walk(tree.root_node):
            if node.type not in CHUNK_NODE_TYPES:
                continue
            name_node = node.child_by_field_name("name")
            symbol = (
                node_text(source_bytes, name_node) if name_node else "<anonimo>"
            )
            inside_class = enclosing_of_types(node, {"class_definition"}) is not None
            if node.type == "class_definition":
                kind = "class"
            else:
                kind = "method" if inside_class else "function"
            chunk = CodeChunk(
                id=stable_id(file_path, symbol, node.start_point[0]),
                project_id=project_id,
                language="python",
                symbol=symbol,
                kind=kind,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source_text=node_text(source_bytes, node),
                metadata={},
            )
            chunks.append(chunk)
            chunk_id_by_node[node.id] = chunk.id

            if node.type == "class_definition":
                superclasses = node.child_by_field_name("superclasses")
                if superclasses is not None:
                    for child in walk(superclasses):
                        if child.type == "identifier":
                            edges.append(DependencyEdge(
                                chunk.id,
                                unresolved_ref(node_text(source_bytes, child)),
                                EdgeType.EXTENDS,
                            ))

        top_level_ids = [
            chunk_id_by_node[n.id]
            for n in tree.root_node.children
            if n.id in chunk_id_by_node
        ]

        for node in walk(tree.root_node):
            if node.type == "call":
                callee = self._callee_name(source_bytes, node)
                enclosing = enclosing_of_types(node, CHUNK_NODE_TYPES)
                if callee and enclosing is not None and enclosing.id in chunk_id_by_node:
                    edges.append(DependencyEdge(
                        chunk_id_by_node[enclosing.id],
                        unresolved_ref(callee),
                        EdgeType.CALLS,
                    ))
            elif node.type in {"import_statement", "import_from_statement"}:
                for name in self._imported_names(source_bytes, node):
                    for source_id in top_level_ids:
                        edges.append(DependencyEdge(
                            source_id, unresolved_ref(name), EdgeType.IMPORTS
                        ))

        return chunks, edges

    @staticmethod
    def _callee_name(source_bytes: bytes, call_node) -> str | None:
        fn = call_node.child_by_field_name("function")
        if fn is None:
            return None
        if fn.type == "identifier":
            return node_text(source_bytes, fn)
        if fn.type == "attribute":
            attr = fn.child_by_field_name("attribute")
            if attr is not None:
                return node_text(source_bytes, attr)
        return None

    @staticmethod
    def _imported_names(source_bytes: bytes, import_node) -> list[str]:
        names = []
        for child in walk(import_node):
            if child.type == "dotted_name":
                # el último componente es el nombre utilizable ("a.b.c" -> "c")
                names.append(node_text(source_bytes, child).split(".")[-1])
            elif child.type == "aliased_import":
                alias = child.child_by_field_name("alias")
                if alias is not None:
                    names.append(node_text(source_bytes, alias))
        return list(dict.fromkeys(names))
