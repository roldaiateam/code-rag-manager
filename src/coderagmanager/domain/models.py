"""Modelo de dominio de CodeRagManager.

Sin dependencias externas de infraestructura: solo dataclasses y stdlib.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"


@dataclass(frozen=True)
class CodeChunk:
    id: str                      # hash estable (ruta + símbolo + línea inicio)
    project_id: str
    language: str                # "python" | "javascript" | "java" | "text"
    symbol: str
    kind: str                    # "function" | "class" | "method" | "block" | ...
    file_path: str
    start_line: int
    end_line: int
    source_text: str             # siempre se persiste completo
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)
    layer: str | None = None
    role: str | None = None
    role_confidence: float | None = None


@dataclass(frozen=True)
class DependencyEdge:
    source_chunk_id: str
    target_chunk_id: str
    edge_type: EdgeType


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    root_path: str
    languages: list[str]
    last_indexed_commit: str | None = None
    last_indexed_at: str | None = None
    extra_index_paths: list[str] = field(default_factory=list)
    auto_include: bool = True    # detectar código generado (Maven/Gradle) aunque esté gitignorado


@dataclass(frozen=True)
class SearchQuery:
    text: str                    # sin project_id: lo fija el servidor MCP al arrancar
    top_k: int = 10
    language: str | None = None
    kind: str | None = None


@dataclass(frozen=True)
class SearchResult:
    chunk: CodeChunk
    score: float
    match_reason: str            # "semantic" | "lexical" | "hybrid"


@dataclass(frozen=True)
class SearchOutcome:
    """Resultado de SearchCode.execute(): resultados + señal de confianza (US-02)."""
    results: list[SearchResult]
    low_confidence: bool = False


@dataclass(frozen=True)
class IndexStats:
    total_chunks: int
    total_edges: int
    # chunks aportados por fuentes fuera de git ls-files: {"auto": n, "extra": m}
    included: dict = field(default_factory=dict)


@dataclass(frozen=True)
class IndexManifest:
    project_id: str
    last_indexed_commit: str | None
    last_indexed_at: str
    total_chunks: int
    total_edges: int


def stable_id(file_path: str, symbol: str, start_line: int) -> str:
    """Identificador estable de un chunk: hash de "ruta:símbolo:línea"."""
    raw = f"{file_path}:{symbol}:{start_line}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
