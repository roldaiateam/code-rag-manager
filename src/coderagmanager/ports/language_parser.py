from __future__ import annotations

from typing import Protocol

from coderagmanager.domain.models import CodeChunk, DependencyEdge


class LanguageParser(Protocol):
    def supports(self, file_path: str) -> bool: ...

    def parse(
        self, project_id: str, file_path: str, source: str
    ) -> tuple[list[CodeChunk], list[DependencyEdge]]: ...
