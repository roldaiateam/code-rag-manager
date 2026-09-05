"""Búsqueda híbrida: semántica (embeddings) + léxica (substring), combinadas
con merge_and_rerank. El project_id queda cerrado en el constructor."""

from __future__ import annotations

from coderagmanager.domain.models import SearchOutcome, SearchQuery
from coderagmanager.domain.ranking import is_low_confidence, merge_and_rerank
from coderagmanager.ports.embedding_provider import EmbeddingProvider
from coderagmanager.ports.lexical_index import LexicalIndex
from coderagmanager.ports.vector_store import VectorStore


class SearchCode:
    def __init__(
        self,
        project_id: str,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        lexical_index: LexicalIndex,
    ):
        self._project_id = project_id
        self._embedder = embedder
        self._vector_store = vector_store
        self._lexical_index = lexical_index

    def execute(self, query: SearchQuery) -> SearchOutcome:
        query_vector = self._embedder.embed_batch([query.text])[0]
        semantic = self._vector_store.search(
            self._project_id, query_vector, query.top_k * 2
        )
        lexical = self._lexical_index.search(
            self._project_id, query.text, query.top_k * 2
        )
        low_confidence = is_low_confidence(semantic, lexical)
        results = merge_and_rerank(semantic, lexical, top_k=query.top_k * 2)
        if query.language is not None:
            results = [r for r in results if r.chunk.language == query.language]
        if query.kind is not None:
            results = [r for r in results if r.chunk.kind == query.kind]
        results = results[: query.top_k]
        if low_confidence:
            results = results[:3]
        return SearchOutcome(results=results, low_confidence=low_confidence)
