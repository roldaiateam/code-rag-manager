from __future__ import annotations

from coderagmanager.domain.models import CodeChunk
from coderagmanager.ports.vector_store import VectorStore


class ListChunks:
    def __init__(self, project_id: str, vector_store: VectorStore):
        self._project_id = project_id
        self._vector_store = vector_store

    def execute(
        self, language: str | None = None, kind: str | None = None
    ) -> list[CodeChunk]:
        return self._vector_store.list(self._project_id, language=language, kind=kind)
