"""Resolución "por nombre" de aristas emitidas por los parsers.

Un parser trabaja fichero a fichero y no conoce los chunks del resto del
proyecto, así que emite aristas cuyo destino es una referencia simbólica
(`unresolved:<nombre>`). Esta función de dominio (pura) las resuelve contra
el conjunto completo de chunks: si hay un único símbolo con ese nombre se
enlaza; si hay varios se prioriza el del mismo fichero; si no se resuelve,
la arista se descarta.
"""

from __future__ import annotations

from coderagmanager.domain.models import CodeChunk, DependencyEdge

UNRESOLVED_PREFIX = "unresolved:"


def unresolved_ref(symbol_name: str) -> str:
    return f"{UNRESOLVED_PREFIX}{symbol_name}"


def resolve_edges(
    chunks: list[CodeChunk], edges: list[DependencyEdge]
) -> list[DependencyEdge]:
    by_id = {c.id: c for c in chunks}
    by_symbol: dict[str, list[CodeChunk]] = {}
    for chunk in chunks:
        by_symbol.setdefault(chunk.symbol, []).append(chunk)

    resolved: list[DependencyEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        target_id = edge.target_chunk_id
        if target_id.startswith(UNRESOLVED_PREFIX):
            name = target_id[len(UNRESOLVED_PREFIX):]
            candidates = by_symbol.get(name, [])
            if not candidates:
                continue
            source = by_id.get(edge.source_chunk_id)
            same_file = [
                c for c in candidates
                if source is not None and c.file_path == source.file_path
            ]
            target = (same_file or candidates)[0]
            target_id = target.id
        if edge.source_chunk_id == target_id:
            continue
        key = (edge.source_chunk_id, target_id, edge.edge_type.value)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(
            DependencyEdge(edge.source_chunk_id, target_id, edge.edge_type)
        )
    return resolved
