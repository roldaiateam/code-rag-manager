from __future__ import annotations

from coderagmanager.domain.models import CodeChunk, stable_id


class GenericTextParser:
    """Fallback para cualquier fichero de texto sin adaptador dedicado:
    chunking por ventana deslizante, sin aristas. Debe registrarse SIEMPRE
    el último en el CompositeLanguageParser."""

    def __init__(self, window_lines: int = 60, overlap_lines: int = 10):
        self._window = window_lines
        self._overlap = overlap_lines

    def supports(self, file_path: str) -> bool:
        return True

    def parse(self, project_id: str, file_path: str, source: str):
        lines = source.splitlines()
        chunks: list[CodeChunk] = []
        step = self._window - self._overlap
        for start in range(0, len(lines), step):
            block = lines[start:start + self._window]
            if not block:
                break
            chunks.append(CodeChunk(
                id=stable_id(file_path, "block", start),
                project_id=project_id,
                language="text",
                symbol=f"L{start + 1}-L{start + len(block)}",
                kind="block",
                file_path=file_path,
                start_line=start + 1,
                end_line=start + len(block),
                source_text="\n".join(block),
                metadata={},
            ))
            if start + self._window >= len(lines):
                break
        return chunks, []
