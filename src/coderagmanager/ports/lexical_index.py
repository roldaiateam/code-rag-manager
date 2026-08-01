from __future__ import annotations

from typing import Protocol

from coderagmanager.domain.models import CodeChunk, SearchResult


class LexicalIndex(Protocol):
    def index(self, project_id: str, chunks: list[CodeChunk]) -> None: ...

    def search(self, project_id: str, text: str, top_k: int) -> list[SearchResult]: ...
