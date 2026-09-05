from __future__ import annotations

from collections.abc import Callable

from coderagmanager.domain.lexical_scoring import ChunkTokens, rank, tokenize_chunk
from coderagmanager.domain.models import CodeChunk, EdgeType, SearchResult
from coderagmanager.domain.tokenizer import expand_query
from coderagmanager.ports.graph_store import GraphStore


class MultiFieldLexicalIndex:
    """Retrieval léxico multi-campo (US-05): delega el scoring en
    `domain/lexical_scoring.py` (symbol, file_path, source_text, calls,
    role, layer), comparando conjuntos de tokens en vez de substrings.

    No persiste nada propio: los chunks siguen viviendo en el vector store
    (única fuente de verdad del índice). Lo que sí cachea es la
    tokenización — se recalcula solo cuando `index()` reconstruye el
    proyecto (tras un reindex) o, si el proceso arranca sin pasar por ahí,
    la primera vez que `search()` se llama para ese proyecto.
    """

    def __init__(
        self,
        chunk_provider: Callable[[str], list[CodeChunk]],
        graph_store: GraphStore,
    ):
        self._chunk_provider = chunk_provider
        self._graph_store = graph_store
        self._cache: dict[str, list[ChunkTokens]] = {}

    def index(self, project_id: str, chunks: list[CodeChunk]) -> None:
        self._cache[project_id] = self._tokenize_all(project_id, chunks)

    def search(self, project_id: str, text: str, top_k: int) -> list[SearchResult]:
        if project_id not in self._cache:
            self._cache[project_id] = self._tokenize_all(
                project_id, self._chunk_provider(project_id)
            )
        query_tokens = expand_query(text)
        if not query_tokens:
            return []
        return rank(query_tokens, self._cache[project_id], top_k)

    def _tokenize_all(
        self, project_id: str, chunks: list[CodeChunk]
    ) -> list[ChunkTokens]:
        calls_by_source = self._calls_by_source(project_id)
        return [
            tokenize_chunk(
                chunk,
                called_symbols=calls_by_source.get(chunk.id, []),
                role=chunk.role,
                layer=chunk.layer,
            )
            for chunk in chunks
        ]

    def _calls_by_source(self, project_id: str) -> dict[str, list[str]]:
        nodes = self._graph_store.nodes(project_id)
        calls_by_source: dict[str, list[str]] = {}
        for edge in self._graph_store.edges(project_id):
            if edge.edge_type != EdgeType.CALLS:
                continue
            target = nodes.get(edge.target_chunk_id)
            if target:
                calls_by_source.setdefault(edge.source_chunk_id, []).append(
                    target["symbol"]
                )
        return calls_by_source
