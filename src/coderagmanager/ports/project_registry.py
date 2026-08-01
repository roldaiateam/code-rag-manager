from __future__ import annotations

from typing import Protocol

from coderagmanager.domain.models import Project


class ProjectRegistry(Protocol):
    def register(
        self,
        name: str,
        root_path: str,
        languages: list[str],
        extra_index_paths: list[str] | None = None,
        auto_include: bool = True,
    ) -> Project: ...

    def get(self, project_id: str) -> Project: ...

    def list(self) -> list[Project]: ...

    def remove(self, project_id: str) -> None: ...

    def mark_indexed(self, project_id: str, commit: str | None) -> None: ...
