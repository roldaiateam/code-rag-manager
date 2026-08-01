from __future__ import annotations

from collections.abc import Callable

from coderagmanager.domain.errors import ChunkNotFoundError
from coderagmanager.domain.models import CodeChunk
from coderagmanager.ports.vector_store import VectorStore

# Presupuesto de líneas por chunk en la respuesta. Los cortes NUNCA son
# silenciosos: siempre van acompañados de la invocación exacta para pedir más.
MAX_SOURCE_LINES = 120       # petición sin rango explícito
MAX_EXPLICIT_LINES = 300     # petición con start_line/end_line (paginación)
SKELETON_KINDS = {"class", "interface", "record"}


class GetSource:
    """Devuelve el código fuente real desde el índice (source_text persistido),
    nunca releyendo el repositorio: el índice es autocontenido.

    Chunks largos se devuelven acotados: vista esqueleto (firmas + anotaciones,
    sin cuerpos) para clases, o truncado por cabeza para el resto — en ambos
    casos con la llamada de continuación lista para copiar.
    """

    def __init__(
        self,
        project_id: str,
        vector_store: VectorStore,
        skeletonizer: Callable[[str, str], str | None] | None = None,
    ):
        self._project_id = project_id
        self._vector_store = vector_store
        self._skeletonizer = skeletonizer

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
        explicit_range = start_line is not None or end_line is not None
        if explicit_range:
            lo = start_line or 0
            hi = end_line or float("inf")
            chunks = [c for c in chunks if c.end_line >= lo and c.start_line <= hi]

        if not chunks:
            criteria = symbol or f"{file_path}:{start_line}-{end_line}"
            raise ChunkNotFoundError(
                f"No hay ningún chunk indexado que coincida con '{criteria}'. "
                "Usa search_code o list_chunks para localizarlo."
            )
        return "\n\n".join(
            self._render(c, start_line, end_line, explicit_range) for c in chunks
        )

    def _render(
        self,
        chunk: CodeChunk,
        start_line: int | None,
        end_line: int | None,
        explicit_range: bool,
    ) -> str:
        header = (
            f"# {chunk.file_path}:{chunk.start_line}-{chunk.end_line} "
            f"({chunk.kind} {chunk.symbol})"
        )
        lines = chunk.source_text.splitlines()

        if explicit_range:
            # recortar a la intersección con el rango pedido (líneas absolutas):
            # imprescindible para que la llamada de continuación avance de verdad
            lo = max(start_line or chunk.start_line, chunk.start_line)
            hi = min(end_line or chunk.end_line, chunk.end_line)
            selected = lines[lo - chunk.start_line : hi - chunk.start_line + 1]
            return header + "\n" + self._truncate(
                chunk, selected, shown_from=lo, cap=MAX_EXPLICIT_LINES
            )

        if (
            len(lines) > MAX_SOURCE_LINES
            and chunk.kind in SKELETON_KINDS
            and self._skeletonizer is not None
        ):
            skeleton = self._skeletonizer(chunk.language, chunk.source_text)
            if skeleton is not None and len(skeleton.splitlines()) < len(lines):
                notice = (
                    f"\n[ESQUELETO: firmas y anotaciones; cuerpos de método omitidos "
                    f"({len(lines)} líneas reales en "
                    f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}). "
                    f"Para ver un cuerpo concreto: "
                    f'get_source(file_path="{chunk.file_path}", '
                    f"start_line=<inicio>, end_line=<fin>)]"
                )
                return header + "\n" + skeleton + notice

        return header + "\n" + self._truncate(
            chunk, lines, shown_from=chunk.start_line, cap=MAX_SOURCE_LINES
        )

    @staticmethod
    def _truncate(
        chunk: CodeChunk, selected: list[str], shown_from: int, cap: int
    ) -> str:
        last_abs = shown_from + len(selected) - 1
        if len(selected) <= cap:
            return "\n".join(selected)
        shown_to = shown_from + cap - 1
        next_end = min(shown_to + cap, chunk.end_line)
        notice = (
            f"\n[TRUNCADO: mostradas líneas {shown_from}-{shown_to} de "
            f"{shown_from}-{last_abs} de {chunk.file_path}. Para continuar: "
            f'get_source(file_path="{chunk.file_path}", '
            f"start_line={shown_to + 1}, end_line={next_end})]"
        )
        return "\n".join(selected[:cap]) + notice
