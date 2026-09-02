from __future__ import annotations

from collections.abc import Callable

from coderagmanager.domain.models import CodeChunk, SearchResult


class SubstringLexicalIndex:
    """Retrieval léxico simple: puntúa por coincidencias de substring de los
    términos de la consulta en `symbol` y `file_path` (sin BM25).

    No persiste nada propio: lee los chunks del vector store (única fuente de
    verdad del índice), por lo que index() no necesita hacer trabajo.
    """

    def __init__(self, chunk_provider: Callable[[str], list[CodeChunk]]):
        self._chunk_provider = chunk_provider

    def index(self, project_id: str, chunks: list[CodeChunk]) -> None:
        pass  # los chunks ya quedan persistidos por el vector store

    def search(self, project_id: str, text: str, top_k: int) -> list[SearchResult]:
        terms = [t for t in text.lower().split() if len(t) >= 2]
        if not terms:
            return []
        scored: list[SearchResult] = []
        for chunk in self._chunk_provider(project_id):
            symbol = chunk.symbol.lower()
            path = chunk.file_path.lower()
            source = chunk.source_text.lower()
            score = 0.0
            for term in terms:
                if term in symbol:
                    score += 2.0  # coincidencia en el símbolo pesa más que en la ruta
                if term in path:
                    score += 1.0
                if term in source:
                    score += 0.5  # señal más débil: el término solo vive en el cuerpo
            if score > 0:
                scored.append(
                    SearchResult(chunk=chunk, score=score, match_reason="lexical")
                )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]
