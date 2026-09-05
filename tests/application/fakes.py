"""Dobles de prueba (fakes) de los puertos: en memoria, sin mocks frágiles."""

from __future__ import annotations

from coderagmanager.domain.models import CodeChunk, DependencyEdge, SearchResult


class FakeEmbedder:
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # vector determinista y barato: longitud y nº de palabras del texto
        return [[float(len(t) % 97), float(len(t.split()))] for t in texts]

    def dimensions(self) -> int:
        return 2


class FakeVectorStore:
    def __init__(self):
        self.data: dict[str, list[CodeChunk]] = {}
        self.drops: list[str] = []

    def drop(self, project_id: str) -> None:
        self.drops.append(project_id)
        self.data.pop(project_id, None)

    def upsert(self, project_id: str, chunks: list[CodeChunk]) -> None:
        self.data.setdefault(project_id, []).extend(chunks)

    def search(self, project_id, query_embedding, top_k) -> list[SearchResult]:
        return [
            SearchResult(chunk=c, score=1.0 - i * 0.1, match_reason="semantic")
            for i, c in enumerate(self.data.get(project_id, [])[:top_k])
        ]

    def list(self, project_id, language=None, kind=None) -> list[CodeChunk]:
        chunks = self.data.get(project_id, [])
        if language is not None:
            chunks = [c for c in chunks if c.language == language]
        if kind is not None:
            chunks = [c for c in chunks if c.kind == kind]
        return chunks


class FakeGraphStore:
    def __init__(self):
        self.nodes_by_project: dict[str, dict] = {}
        self.edges_by_project: dict[str, list[DependencyEdge]] = {}
        self.drops: list[str] = []

    def drop(self, project_id: str) -> None:
        self.drops.append(project_id)
        self.nodes_by_project.pop(project_id, None)
        self.edges_by_project.pop(project_id, None)

    def upsert_nodes(self, project_id: str, chunks: list[CodeChunk]) -> None:
        nodes = self.nodes_by_project.setdefault(project_id, {})
        for c in chunks:
            nodes[c.id] = {"symbol": c.symbol, "kind": c.kind, "file_path": c.file_path}

    def upsert_edges(self, project_id: str, edges: list[DependencyEdge]) -> None:
        self.edges_by_project.setdefault(project_id, []).extend(edges)

    def dependency_chain(self, project_id, symbol, max_depth, direction):
        return self.edges_by_project.get(project_id, [])

    def nodes(self, project_id: str) -> dict[str, dict]:
        return self.nodes_by_project.get(project_id, {})

    def edges(self, project_id: str) -> list[DependencyEdge]:
        return list(self.edges_by_project.get(project_id, []))


class FakeLexicalIndex:
    def __init__(self):
        self.indexed: dict[str, list[CodeChunk]] = {}

    def index(self, project_id: str, chunks: list[CodeChunk]) -> None:
        self.indexed[project_id] = list(chunks)

    def search(self, project_id, text, top_k) -> list[SearchResult]:
        hits = [
            c for c in self.indexed.get(project_id, [])
            if text.lower() in c.symbol.lower()
        ]
        return [
            SearchResult(chunk=c, score=2.0, match_reason="lexical")
            for c in hits[:top_k]
        ]


class FakeGit:
    def head(self, repo_path: str) -> str | None:
        return "abc1234"
