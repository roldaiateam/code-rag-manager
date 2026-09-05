from __future__ import annotations

from typing import Protocol

from coderagmanager.domain.models import CodeChunk, DependencyEdge


class GraphStore(Protocol):
    """Guarda también los nodos (id → símbolo/ruta) para poder recorrer el
    grafo por símbolo, siguiendo el patrón chunksByFqcn/outEdges/inEdges."""

    def drop(self, project_id: str) -> None: ...

    def upsert_nodes(self, project_id: str, chunks: list[CodeChunk]) -> None: ...

    def upsert_edges(self, project_id: str, edges: list[DependencyEdge]) -> None: ...

    def dependency_chain(
        self, project_id: str, symbol: str, max_depth: int, direction: str
    ) -> list[DependencyEdge]: ...

    def nodes(self, project_id: str) -> dict[str, dict]: ...

    def edges(self, project_id: str) -> list[DependencyEdge]: ...
