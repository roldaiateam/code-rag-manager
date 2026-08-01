from __future__ import annotations

from coderagmanager.ports.graph_store import GraphStore


class GetDependencyChain:
    def __init__(self, project_id: str, graph_store: GraphStore):
        self._project_id = project_id
        self._graph_store = graph_store

    def execute(
        self, symbol: str, max_depth: int = 3, direction: str = "both"
    ) -> list[dict]:
        if direction not in ("in", "out", "both"):
            raise ValueError("direction debe ser 'in', 'out' o 'both'.")
        edges = self._graph_store.dependency_chain(
            self._project_id, symbol, max_depth, direction
        )
        nodes = self._graph_store.nodes(self._project_id)

        def describe(chunk_id: str) -> dict:
            info = nodes.get(chunk_id, {})
            return {
                "symbol": info.get("symbol", chunk_id),
                "file_path": info.get("file_path", "?"),
                "kind": info.get("kind", "?"),
            }

        return [
            {
                "source": describe(e.source_chunk_id),
                "edge_type": e.edge_type.value,
                "target": describe(e.target_chunk_id),
            }
            for e in edges
        ]
