from __future__ import annotations

from coderagmanager.domain.errors import ChunkNotFoundError
from coderagmanager.domain.models import CodeChunk
from coderagmanager.ports.vector_store import VectorStore


class GetSource:
    """Devuelve el código fuente real desde el índice (source_text persistido),
    nunca releyendo el repositorio: el índice es autocontenido."""

    def __init__(self, project_id: str, vector_store: VectorStore):
        self._project_id = project_id
        self._vector_store = vector_store

    def execute(
        self,
        symbol: str | None = None,
        file_path: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        if symbol is None and file_path is None:
            raise ValueError("Debes indicar 'symbol' o 'file_path'.")

        chunks = self._vector_store.list(self._project_id)
        if symbol is not None:
            chunks = [c for c in chunks if c.symbol == symbol]
        if file_path is not None:
            chunks = [c for c in chunks if c.file_path == file_path]
        if start_line is not None or end_line is not None:
            lo = start_line or 0
            hi = end_line or float("inf")
            chunks = [c for c in chunks if c.end_line >= lo and c.start_line <= hi]

        if not chunks:
            criteria = symbol or f"{file_path}:{start_line}-{end_line}"
            raise ChunkNotFoundError(
                f"No hay ningún chunk indexado que coincida con '{criteria}'. "
                "Usa search_code o list_chunks para localizarlo."
            )
        return "\n\n".join(self._format(c) for c in chunks)

    @staticmethod
    def _format(chunk: CodeChunk) -> str:
        header = f"# {chunk.file_path}:{chunk.start_line}-{chunk.end_line} ({chunk.kind} {chunk.symbol})"
        return f"{header}\n{chunk.source_text}"
