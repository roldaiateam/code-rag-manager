from __future__ import annotations

import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

from coderagmanager.adapters.parsers.base import node_text, walk
from coderagmanager.domain.models import (
    CodeChunk,
    DependencyEdge,
    EdgeType,
    stable_id,
)
from coderagmanager.domain.resolution import unresolved_ref

CHUNK_NODE_TYPES = {"function_declaration", "class_declaration", "method_definition"}
EXTENSIONS = (".js", ".jsx", ".ts", ".tsx")


class TreeSitterJavaScriptParser:
    def __init__(self):
        self._parser = Parser(Language(tsjavascript.language()))

    def supports(self, file_path: str) -> bool:
        return file_path.endswith(EXTENSIONS)

    def parse(self, project_id: str, file_path: str, source: str):
        source_bytes = source.encode("utf-8")
        tree = self._parser.parse(source_bytes)
        chunks: list[CodeChunk] = []
        edges: list[DependencyEdge] = []
        chunk_id_by_node: dict[int, str] = {}

        for node in walk(tree.root_node):
            symbol, kind, chunk_node = None, None, node
            if node.type in ("function_declaration", "class_declaration"):
                name_node = node.child_by_field_name("name")
                symbol = node_text(source_bytes, name_node) if name_node else "<anonimo>"
                kind = "class" if node.type == "class_declaration" else "function"
            elif node.type == "method_definition":
                name_node = node.child_by_field_name("name")
                symbol = node_text(source_bytes, name_node) if name_node else "<anonimo>"
                kind = "method"
            elif node.type == "variable_declarator":
                # const f = (...) => {...}  → función flecha asignada a constante
                value = node.child_by_field_name("value")
                if value is not None and value.type == "arrow_function":
                    name_node = node.child_by_field_name("name")
                    symbol = (
                        node_text(source_bytes, name_node) if name_node else "<anonimo>"
                    )
                    kind = "function"
            if symbol is None:
                continue

            chunk = CodeChunk(
                id=stable_id(file_path, symbol, chunk_node.start_point[0]),
                project_id=project_id,
                language="javascript",
                symbol=symbol,
                kind=kind,
                file_path=file_path,
                start_line=chunk_node.start_point[0] + 1,
                end_line=chunk_node.end_point[0] + 1,
                source_text=node_text(source_bytes, chunk_node),
                metadata={},
            )
            chunks.append(chunk)
            chunk_id_by_node[chunk_node.id] = chunk.id

            if node.type == "class_declaration":
                for child in node.children:
                    if child.type == "class_heritage":
                        for ident in walk(child):
                            if ident.type == "identifier":
                                edges.append(DependencyEdge(
                                    chunk.id,
                                    unresolved_ref(node_text(source_bytes, ident)),
                                    EdgeType.EXTENDS,
                                ))

        top_level_ids = list(chunk_id_by_node.values())

        for node in walk(tree.root_node):
            if node.type == "call_expression":
                callee = self._callee_name(source_bytes, node)
                # primer ancestro que sea un chunk (un variable_declarator
                # interno, p.ej. `const envio = ...`, no cuenta como chunk)
                enclosing = node.parent
                while enclosing is not None and enclosing.id not in chunk_id_by_node:
                    enclosing = enclosing.parent
                if callee and enclosing is not None:
                    edges.append(DependencyEdge(
                        chunk_id_by_node[enclosing.id],
                        unresolved_ref(callee),
                        EdgeType.CALLS,
                    ))
            elif node.type == "import_statement":
                for child in walk(node):
                    if child.type == "identifier":
                        name = node_text(source_bytes, child)
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
        if fn.type == "member_expression":
            prop = fn.child_by_field_name("property")
            if prop is not None:
                return node_text(source_bytes, prop)
        return None
