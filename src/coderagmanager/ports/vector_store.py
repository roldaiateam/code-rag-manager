from __future__ import annotations

from typing import Protocol

from coderagmanager.domain.models import CodeChunk, SearchResult


class VectorStore(Protocol):
    """drop() sustituye a delete() por ids: el indexado es siempre drop-and-rebuild.

    list() existe porque el índice es autocontenido (get_source/list_chunks
    leen del índice, nunca del disco del repositorio).
    """

    def drop(self, project_id: str) -> None: ...

    def upsert(self, project_id: str, chunks: list[CodeChunk]) -> None: ...

    def search(
        self, project_id: str, query_embedding: list[float], top_k: int
    ) -> list[SearchResult]: ...

    def list(
        self,
        project_id: str,
        language: str | None = None,
        kind: str | None = None,
    ) -> list[CodeChunk]: ...
