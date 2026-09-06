from __future__ import annotations

import lancedb

from coderagmanager.domain.models import CodeChunk, SearchResult


class LanceDbVectorStore:
    """Una tabla por proyecto (`project_<id>`), cada fila con source_text completo."""

    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._db = None

    def _connect(self):
        if self._db is None:
            self._db = lancedb.connect(self._base_dir)
        return self._db

    @staticmethod
    def _table_name(project_id: str) -> str:
        return f"project_{project_id}"

    def drop(self, project_id: str) -> None:
        db = self._connect()
        name = self._table_name(project_id)
        if name in db.table_names():
            db.drop_table(name)

    def upsert(self, project_id: str, chunks: list[CodeChunk]) -> None:
        if not chunks:
            return
        db = self._connect()
        rows = [
            {
                "id": c.id,
                "vector": c.embedding,
                "symbol": c.symbol,
                "language": c.language,
                "kind": c.kind,
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "source_text": c.source_text,
                "layer": c.layer,
                "role": c.role,
                "role_confidence": c.role_confidence,
            }
            for c in chunks
        ]
        name = self._table_name(project_id)
        if name in db.table_names():
            db.open_table(name).add(rows)
        else:
            db.create_table(name, data=rows)

    def search(
        self, project_id: str, query_embedding: list[float], top_k: int
    ) -> list[SearchResult]:
        db = self._connect()
        name = self._table_name(project_id)
        if name not in db.table_names():
            return []
        table = db.open_table(name)
        rows = (
            table.search(query_embedding)
            .metric("cosine")
            .limit(top_k)
            .to_list()
        )
        results = []
        for row in rows:
            # métrica cosine: _distance = 1 - similitud → score en [-1, 1]
            score = 1.0 - row.get("_distance", 1.0)
            results.append(
                SearchResult(
                    chunk=self._to_chunk(project_id, row),
                    score=score,
                    match_reason="semantic",
                )
            )
        return results

    def list(
        self,
        project_id: str,
        language: str | None = None,
        kind: str | None = None,
        role: str | None = None,
        layer: str | None = None,
    ) -> list[CodeChunk]:
        db = self._connect()
        name = self._table_name(project_id)
        if name not in db.table_names():
            return []
        rows = db.open_table(name).to_arrow().to_pylist()
        chunks = [self._to_chunk(project_id, row) for row in rows]
        if language is not None:
            chunks = [c for c in chunks if c.language == language]
        if kind is not None:
            chunks = [c for c in chunks if c.kind == kind]
        if role is not None:
            chunks = [c for c in chunks if c.role == role]
        if layer is not None:
            chunks = [c for c in chunks if c.layer == layer]
        return sorted(chunks, key=lambda c: (c.file_path, c.start_line))

    @staticmethod
    def _to_chunk(project_id: str, row: dict) -> CodeChunk:
        return CodeChunk(
            id=row["id"],
            project_id=project_id,
            language=row["language"],
            symbol=row["symbol"],
            kind=row["kind"],
            file_path=row["file_path"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            source_text=row["source_text"],
            layer=row.get("layer"),
            role=row.get("role"),
            role_confidence=row.get("role_confidence"),
        )
