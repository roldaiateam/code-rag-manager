"""Único caso de uso de indexado: siempre completo (drop-and-rebuild).

Vaciar los almacenes antes de reconstruir es lo que hace que "sin lógica de
diff" siga siendo correcto: los chunks de ficheros borrados o renombrados no
quedan huérfanos. `reindex` (CLI y tool MCP) llama a este mismo caso de uso.
"""

from __future__ import annotations

from dataclasses import replace

from coderagmanager.application.file_discovery import discover_files
from coderagmanager.application.manifest import now_iso, write_manifest
from coderagmanager.domain.models import IndexManifest, IndexStats
from coderagmanager.domain.resolution import resolve_edges
from coderagmanager.ports.embedding_provider import EmbeddingProvider
from coderagmanager.ports.git_provider import GitProvider
from coderagmanager.ports.graph_store import GraphStore
from coderagmanager.ports.language_parser import LanguageParser
from coderagmanager.ports.lexical_index import LexicalIndex
from coderagmanager.ports.vector_store import VectorStore


class IndexProject:
    def __init__(
        self,
        project_id: str,
        root_path: str,
        parser: LanguageParser,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        graph_store: GraphStore,
        lexical_index: LexicalIndex,
        git: GitProvider,
    ):
        self._project_id, self._root_path = project_id, root_path
        self._parser, self._embedder = parser, embedder
        self._vector_store, self._graph_store = vector_store, graph_store
        self._lexical_index, self._git = lexical_index, git

    def execute(self) -> IndexStats:
        self._vector_store.drop(self._project_id)
        self._graph_store.drop(self._project_id)

        chunks, edges = [], []
        for file_path, source in discover_files(self._root_path):
            if not self._parser.supports(file_path):
                continue
            file_chunks, file_edges = self._parser.parse(
                self._project_id, file_path, source
            )
            chunks.extend(file_chunks)
            edges.extend(file_edges)

        edges = resolve_edges(chunks, edges)

        embeddings = self._embedder.embed_batch([c.source_text for c in chunks])
        chunks = [replace(c, embedding=e) for c, e in zip(chunks, embeddings)]

        self._vector_store.upsert(self._project_id, chunks)
        self._graph_store.upsert_nodes(self._project_id, chunks)
        self._graph_store.upsert_edges(self._project_id, edges)
        self._lexical_index.index(self._project_id, chunks)

        # El manifest se escribe al final, nunca antes: si el proceso se corta
        # a mitad, el siguiente indexado parte de un estado no marcado como "al día".
        write_manifest(
            self._root_path,
            IndexManifest(
                project_id=self._project_id,
                last_indexed_commit=self._git.head(self._root_path),
                last_indexed_at=now_iso(),
                total_chunks=len(chunks),
                total_edges=len(edges),
            ),
        )
        return IndexStats(total_chunks=len(chunks), total_edges=len(edges))
