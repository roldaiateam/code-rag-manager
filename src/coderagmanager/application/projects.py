"""Casos de uso de gestión del registro de proyectos (solo CLI, no MCP)."""

from __future__ import annotations

from coderagmanager.domain.models import Project
from coderagmanager.ports.project_registry import ProjectRegistry


class RegisterProject:
    def __init__(self, registry: ProjectRegistry):
        self._registry = registry

    def execute(
        self,
        name: str,
        root_path: str,
        languages: list[str],
        extra_index_paths: list[str] | None = None,
        auto_include: bool = True,
    ) -> Project:
        return self._registry.register(
            name, root_path, languages,
            extra_index_paths=extra_index_paths,
            auto_include=auto_include,
        )


class ListProjects:
    def __init__(self, registry: ProjectRegistry):
        self._registry = registry

    def execute(self) -> list[Project]:
        return self._registry.list()


class RemoveProject:
    def __init__(self, registry: ProjectRegistry):
        self._registry = registry

    def execute(self, project_id: str) -> None:
        self._registry.remove(project_id)
