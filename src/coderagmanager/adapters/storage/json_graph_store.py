from __future__ import annotations

import json
import os
from collections import deque

from coderagmanager.domain.models import CodeChunk, DependencyEdge, EdgeType

GRAPH_FILE = "graph.json"


class JsonGraphStore:
    """Un fichero graph.json por proyecto, cargado en memoria con listas de
    adyacencia (outEdges/inEdges) y BFS para dependency_chain()."""

    def __init__(self, base_dir: str):
        self._base_dir = base_dir

    def _path(self) -> str:
        return os.path.join(self._base_dir, GRAPH_FILE)

    def _load(self) -> dict:
        if not os.path.exists(self._path()):
            return {"nodes": {}, "edges": []}
        with open(self._path(), encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, data: dict) -> None:
        os.makedirs(self._base_dir, exist_ok=True)
        with open(self._path(), "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    def drop(self, project_id: str) -> None:
        self._save({"nodes": {}, "edges": []})

    def upsert_nodes(self, project_id: str, chunks: list[CodeChunk]) -> None:
        data = self._load()
        for chunk in chunks:
            data["nodes"][chunk.id] = {
                "symbol": chunk.symbol,
                "kind": chunk.kind,
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }
        self._save(data)

    def upsert_edges(self, project_id: str, edges: list[DependencyEdge]) -> None:
        data = self._load()
        data["edges"].extend(
            {
                "source_chunk_id": e.source_chunk_id,
                "target_chunk_id": e.target_chunk_id,
                "edge_type": e.edge_type.value,
            }
            for e in edges
        )
        self._save(data)

    def nodes(self, project_id: str) -> dict[str, dict]:
        return self._load()["nodes"]

    def edges(self, project_id: str) -> list[DependencyEdge]:
        return [
            DependencyEdge(
                e["source_chunk_id"], e["target_chunk_id"], EdgeType(e["edge_type"])
            )
            for e in self._load()["edges"]
        ]

    def dependency_chain(
        self, project_id: str, symbol: str, max_depth: int, direction: str
    ) -> list[DependencyEdge]:
        data = self._load()
        edges = self.edges(project_id)
        out_edges: dict[str, list[DependencyEdge]] = {}
        in_edges: dict[str, list[DependencyEdge]] = {}
        for edge in edges:
            out_edges.setdefault(edge.source_chunk_id, []).append(edge)
            in_edges.setdefault(edge.target_chunk_id, []).append(edge)

        start_ids = [
            node_id
            for node_id, info in data["nodes"].items()
            if info["symbol"] == symbol
        ]

        result: list[DependencyEdge] = []
        seen_edges: set[tuple[str, str, str]] = set()
        visited: set[str] = set(start_ids)
        queue: deque[tuple[str, int]] = deque((nid, 0) for nid in start_ids)

        while queue:
            node_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            neighbors: list[tuple[DependencyEdge, str]] = []
            if direction in ("out", "both"):
                neighbors += [(e, e.target_chunk_id) for e in out_edges.get(node_id, [])]
            if direction in ("in", "both"):
                neighbors += [(e, e.source_chunk_id) for e in in_edges.get(node_id, [])]
            for edge, next_id in neighbors:
                key = (edge.source_chunk_id, edge.target_chunk_id, edge.edge_type.value)
                if key not in seen_edges:
                    seen_edges.add(key)
                    result.append(edge)
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, depth + 1))
        return result
