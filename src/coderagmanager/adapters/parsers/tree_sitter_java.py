from __future__ import annotations

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from coderagmanager.adapters.parsers.base import enclosing_of_types, node_text, walk
from coderagmanager.domain.models import (
    CodeChunk,
    DependencyEdge,
    EdgeType,
    stable_id,
)
from coderagmanager.domain.resolution import unresolved_ref

TYPE_NODE_TYPES = {"class_declaration", "interface_declaration", "record_declaration"}
CHUNK_NODE_TYPES = TYPE_NODE_TYPES | {"method_declaration"}
ANNOTATION_NODE_TYPES = {"marker_annotation", "annotation"}
SUPERTYPE_CLAUSE_TYPES = {"superclass", "super_interfaces", "extends_interfaces"}

KIND_BY_NODE_TYPE = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "record_declaration": "record",
    "method_declaration": "method",
}


def _annotations_of(source_bytes: bytes, type_node) -> list[str]:
    modifiers = next(
        (child for child in type_node.children if child.type == "modifiers"), None
    )
    if modifiers is None:
        return []
    names = []
    for node in modifiers.children:
        if node.type not in ANNOTATION_NODE_TYPES:
            continue
        name_node = node.child_by_field_name("name")
        names.append(node_text(source_bytes, name_node).rsplit(".", 1)[-1])
    return names


def _shallow_type_names(source_bytes: bytes, node) -> list[str]:
    if node.type in ("type_identifier", "scoped_type_identifier"):
        return [node_text(source_bytes, node).rsplit(".", 1)[-1]]
    if node.type == "generic_type":
        return _shallow_type_names(source_bytes, node.children[0])
    names = []
    for child in node.children:
        names.extend(_shallow_type_names(source_bytes, child))
    return names


def _supertype_names(source_bytes: bytes, type_node) -> list[str]:
    names = []
    for child in type_node.children:
        if child.type in SUPERTYPE_CLAUSE_TYPES:
            names.extend(_shallow_type_names(source_bytes, child))
    return names


class TreeSitterJavaParser:
    def __init__(self):
        self._parser = Parser(Language(tsjava.language()))

    def supports(self, file_path: str) -> bool:
        return file_path.endswith(".java")

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
            symbol = node_text(source_bytes, name_node) if name_node else "<anonimo>"
            metadata = (
                {
                    "annotations": _annotations_of(source_bytes, node),
                    "supertypes": _supertype_names(source_bytes, node),
                }
                if node.type in TYPE_NODE_TYPES
                else {}
            )
            chunk = CodeChunk(
                id=stable_id(file_path, symbol, node.start_point[0]),
                project_id=project_id,
                language="java",
                symbol=symbol,
                kind=KIND_BY_NODE_TYPE[node.type],
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source_text=node_text(source_bytes, node),
                metadata=metadata,
            )
            chunks.append(chunk)
            chunk_id_by_node[node.id] = chunk.id

            if node.type in TYPE_NODE_TYPES:
                superclass = node.child_by_field_name("superclass")
                if superclass is not None:
                    for ident in walk(superclass):
                        if ident.type == "type_identifier":
                            edges.append(DependencyEdge(
                                chunk.id,
                                unresolved_ref(node_text(source_bytes, ident)),
                                EdgeType.EXTENDS,
                            ))
                for child in node.children:
                    if child.type in ("super_interfaces", "extends_interfaces"):
                        edge_type = (
                            EdgeType.IMPLEMENTS
                            if child.type == "super_interfaces"
                            else EdgeType.EXTENDS
                        )
                        for ident in walk(child):
                            if ident.type == "type_identifier":
                                edges.append(DependencyEdge(
                                    chunk.id,
                                    unresolved_ref(node_text(source_bytes, ident)),
                                    edge_type,
                                ))

        top_level_type_ids = [
            chunk_id_by_node[n.id]
            for n in walk(tree.root_node)
            if n.type in TYPE_NODE_TYPES and n.id in chunk_id_by_node
        ]

        for node in walk(tree.root_node):
            if node.type == "method_invocation":
                name_node = node.child_by_field_name("name")
                enclosing = enclosing_of_types(node, {"method_declaration"})
                if (
                    name_node is not None
                    and enclosing is not None
                    and enclosing.id in chunk_id_by_node
                ):
                    edges.append(DependencyEdge(
                        chunk_id_by_node[enclosing.id],
                        unresolved_ref(node_text(source_bytes, name_node)),
                        EdgeType.CALLS,
                    ))
            elif node.type == "import_declaration":
                for child in walk(node):
                    if child.type == "scoped_identifier":
                        name = node_text(source_bytes, child).split(".")[-1]
                        for source_id in top_level_type_ids:
                            edges.append(DependencyEdge(
                                source_id, unresolved_ref(name), EdgeType.IMPORTS
                            ))
                        break

        return chunks, edges
