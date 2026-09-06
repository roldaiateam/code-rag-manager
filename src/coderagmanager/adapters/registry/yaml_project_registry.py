from __future__ import annotations

import os
import re

import yaml

from coderagmanager.domain.errors import ProjectNotFoundError
from coderagmanager.domain.models import Project

DEFAULT_REGISTRY_PATH = os.path.expanduser("~/.crm/projects.yaml")


class YamlProjectRegistry:
    def __init__(self, registry_path: str = DEFAULT_REGISTRY_PATH):
        self._path = registry_path

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {"projects": {}, "defaults": {"embedding_provider": "local"}}
        with open(self._path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        data.setdefault("projects", {})
        data.setdefault("defaults", {"embedding_provider": "local"})
        return data

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=True, allow_unicode=True)

    def register(
        self,
        name: str,
        root_path: str,
        languages: list[str],
        extra_index_paths: list[str] | None = None,
        auto_include: bool = True,
        role_classification: bool = True,
    ) -> Project:
        project_id = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
        if not project_id:
            raise ValueError(f"Nombre de proyecto inválido: '{name}'")
        root_path = os.path.abspath(os.path.expanduser(root_path))
        if not os.path.isdir(root_path):
            raise ValueError(f"La ruta '{root_path}' no existe o no es un directorio.")
        data = self._load()
        data["projects"][project_id] = {
            "name": name,
            "root_path": root_path,
            "languages": languages,
            "extra_index_paths": list(extra_index_paths or []),
            "auto_include": auto_include,
            "role_classification": role_classification,
            "last_indexed_commit": None,
            "last_indexed_at": None,
        }
        self._save(data)
        return self.get(project_id)

    def get(self, project_id: str) -> Project:
        entry = self._load()["projects"].get(project_id)
        if entry is None:
            raise ProjectNotFoundError(project_id)
        return Project(
            id=project_id,
            name=entry.get("name", project_id),
            root_path=entry["root_path"],
            languages=entry.get("languages", []),
            last_indexed_commit=entry.get("last_indexed_commit"),
            last_indexed_at=entry.get("last_indexed_at"),
            extra_index_paths=entry.get("extra_index_paths", []),
            auto_include=entry.get("auto_include", True),
            role_classification=entry.get("role_classification", True),
        )

    def list(self) -> list[Project]:
        return [self.get(pid) for pid in sorted(self._load()["projects"])]

    def remove(self, project_id: str) -> None:
        data = self._load()
        if project_id not in data["projects"]:
            raise ProjectNotFoundError(project_id)
        del data["projects"][project_id]
        self._save(data)

    def mark_indexed(self, project_id: str, commit: str | None) -> None:
        from coderagmanager.application.manifest import now_iso

        data = self._load()
        if project_id not in data["projects"]:
            raise ProjectNotFoundError(project_id)
        data["projects"][project_id]["last_indexed_commit"] = commit
        data["projects"][project_id]["last_indexed_at"] = now_iso()
        self._save(data)

    def defaults(self) -> dict:
        return self._load()["defaults"]

    def set_default(self, key: str, value: str) -> None:
        data = self._load()
        data["defaults"][key] = value
        self._save(data)
