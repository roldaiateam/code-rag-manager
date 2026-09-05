"""Único caso de uso de indexado: siempre completo (drop-and-rebuild).

Vaciar los almacenes antes de reconstruir es lo que hace que "sin lógica de
diff" siga siendo correcto: los chunks de ficheros borrados o renombrados no
quedan huérfanos. `reindex` (CLI y tool MCP) llama a este mismo caso de uso.
"""

from __future__ import annotations

from dataclasses import replace

from coderagmanager.application.file_discovery import discover_files
from coderagmanager.application.manifest import now_iso, write_manifest
from coderagmanager.domain.classification import (
    SEMANTIC_ROLE_PROTOTYPES,
    classify_kind_by_path,
    classify_layer_by_path,
    classify_role_spring_java,
    nearest_role_prototype,
    spring_java_pack_applies,
)
from coderagmanager.domain.models import CodeChunk, IndexManifest, IndexStats
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
        extra_index_paths: list[str] | None = None,
        auto_include: bool = True,
    ):
        self._project_id, self._root_path = project_id, root_path
        self._parser, self._embedder = parser, embedder
        self._vector_store, self._graph_store = vector_store, graph_store
        self._lexical_index, self._git = lexical_index, git
        self._extra_index_paths = extra_index_paths or []
        self._auto_include = auto_include
        self._prototype_embeddings: dict[str, list[float]] | None = None

    def _semantic_prototypes(self) -> dict[str, list[float]]:
        if self._prototype_embeddings is None:
            names = list(SEMANTIC_ROLE_PROTOTYPES)
            vectors = self._embedder.embed_batch(
                [SEMANTIC_ROLE_PROTOTYPES[name] for name in names]
            )
            self._prototype_embeddings = dict(zip(names, vectors))
        return self._prototype_embeddings

    def execute(self) -> IndexStats:
        self._vector_store.drop(self._project_id)
        self._graph_store.drop(self._project_id)

        chunks, edges = [], []
        included: dict[str, int] = {}
        for file_path, source, origin in discover_files(
            self._root_path,
            extra_index_paths=self._extra_index_paths,
            auto_include=self._auto_include,
        ):
            if not self._parser.supports(file_path):
                continue
            file_chunks, file_edges = self._parser.parse(
                self._project_id, file_path, source
            )
            chunks.extend(file_chunks)
            edges.extend(file_edges)
            if origin != "git" and file_chunks:
                included[origin] = included.get(origin, 0) + len(file_chunks)

        edges = resolve_edges(chunks, edges)

        chunks = [
            replace(
                c,
                layer=classify_layer_by_path(c.file_path),
                kind=classify_kind_by_path(c.file_path) or c.kind,
            )
            for c in chunks
        ]
        if spring_java_pack_applies(chunks):
            chunks = [replace(c, role=classify_role_spring_java(c)) for c in chunks]

        embeddings = self._embedder.embed_batch([c.source_text for c in chunks])
        chunks = [replace(c, embedding=e) for c, e in zip(chunks, embeddings)]

        if any(c.role is None for c in chunks):
            prototypes = self._semantic_prototypes()
            chunks = [
                c if c.role is not None else _with_semantic_role(c, prototypes)
                for c in chunks
            ]

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
        return IndexStats(
            total_chunks=len(chunks), total_edges=len(edges), included=included
        )


def _with_semantic_role(
    chunk: CodeChunk, prototype_embeddings: dict[str, list[float]]
) -> CodeChunk:
    role, margin = nearest_role_prototype(chunk.embedding, prototype_embeddings)
    return replace(chunk, role=role, role_confidence=margin)
