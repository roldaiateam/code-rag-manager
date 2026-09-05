"""Único sitio del proyecto donde se "conectan los cables": elige adaptadores
concretos para cada puerto y construye los casos de uso ya cerrados sobre un
project_id (el servidor MCP y el CLI nunca instancian adaptadores)."""

from __future__ import annotations

import os

from coderagmanager.adapters.embeddings.local_provider import (
    LocalSentenceTransformerProvider,
)
from coderagmanager.adapters.git.git_cli_provider import GitCliProvider
from coderagmanager.adapters.parsers.composite import CompositeLanguageParser
from coderagmanager.adapters.parsers.generic_text import GenericTextParser
from coderagmanager.adapters.parsers.tree_sitter_java import TreeSitterJavaParser
from coderagmanager.adapters.parsers.tree_sitter_javascript import (
    TreeSitterJavaScriptParser,
)
from coderagmanager.adapters.parsers.skeleton import skeletonize
from coderagmanager.adapters.parsers.tree_sitter_python import TreeSitterPythonParser
from coderagmanager.adapters.registry.yaml_project_registry import (
    DEFAULT_REGISTRY_PATH,
    YamlProjectRegistry,
)
from coderagmanager.adapters.storage.json_graph_store import JsonGraphStore
from coderagmanager.adapters.storage.lancedb_vector_store import LanceDbVectorStore
from coderagmanager.adapters.storage.substring_lexical_index import (
    MultiFieldLexicalIndex,
)
from coderagmanager.application.get_dependency_chain import GetDependencyChain
from coderagmanager.application.get_index_stats import GetIndexStats
from coderagmanager.application.get_source import GetSource
from coderagmanager.application.index_project import IndexProject
from coderagmanager.application.list_chunks import ListChunks
from coderagmanager.application.manifest import CRM_DIR
from coderagmanager.application.projects import (
    ListProjects,
    RegisterProject,
    RemoveProject,
)
from coderagmanager.application.search_code import SearchCode


def build_registry(registry_path: str | None = None) -> YamlProjectRegistry:
    return YamlProjectRegistry(registry_path or DEFAULT_REGISTRY_PATH)


def build_parser() -> CompositeLanguageParser:
    return CompositeLanguageParser([
        TreeSitterPythonParser(),
        TreeSitterJavaScriptParser(),
        TreeSitterJavaParser(),
        GenericTextParser(),   # fallback: siempre el último
    ])


def build_registry_use_cases(registry_path: str | None = None) -> dict:
    registry = build_registry(registry_path)
    return {
        "registry": registry,
        "register_project": RegisterProject(registry),
        "list_projects": ListProjects(registry),
        "remove_project": RemoveProject(registry),
    }


def build_use_cases(project_id: str, registry_path: str | None = None) -> dict:
    registry = build_registry(registry_path)
    project = registry.get(project_id)
    index_dir = os.path.join(project.root_path, CRM_DIR)

    vector_store = LanceDbVectorStore(index_dir)
    graph_store = JsonGraphStore(index_dir)
    lexical_index = MultiFieldLexicalIndex(
        chunk_provider=vector_store.list, graph_store=graph_store
    )
    embedder = LocalSentenceTransformerProvider()
    git = GitCliProvider()

    return {
        "registry": registry,
        "project": project,
        "index_project": IndexProject(
            project_id=project.id,
            root_path=project.root_path,
            parser=build_parser(),
            embedder=embedder,
            vector_store=vector_store,
            graph_store=graph_store,
            lexical_index=lexical_index,
            git=git,
            extra_index_paths=project.extra_index_paths,
            auto_include=project.auto_include,
        ),
        "search_code": SearchCode(project.id, embedder, vector_store, lexical_index),
        "get_dependency_chain": GetDependencyChain(project.id, graph_store),
        "get_source": GetSource(project.id, vector_store, skeletonizer=skeletonize),
        "list_chunks": ListChunks(project.id, vector_store),
        "get_index_stats": GetIndexStats(project.id, project.root_path, vector_store),
    }
