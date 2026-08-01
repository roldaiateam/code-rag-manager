from __future__ import annotations

from collections import Counter

from coderagmanager.application.manifest import read_manifest
from coderagmanager.ports.vector_store import VectorStore


class GetIndexStats:
    def __init__(self, project_id: str, root_path: str, vector_store: VectorStore):
        self._project_id = project_id
        self._root_path = root_path
        self._vector_store = vector_store

    def execute(self) -> dict:
        manifest = read_manifest(self._root_path)
        chunks = self._vector_store.list(self._project_id)
        return {
            "project_id": self._project_id,
            "indexed": manifest is not None,
            "last_indexed_commit": manifest.last_indexed_commit if manifest else None,
            "last_indexed_at": manifest.last_indexed_at if manifest else None,
            "total_chunks": len(chunks),
            "total_edges": manifest.total_edges if manifest else 0,
            "by_language": dict(Counter(c.language for c in chunks)),
            "by_kind": dict(Counter(c.kind for c in chunks)),
        }
