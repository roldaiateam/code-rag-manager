"""Clasificación de chunks por vocabulario de rutas: pura coincidencia de
segmentos de carpeta, sin conocer lenguaje ni framework — generaliza igual
sobre Python, Java, JS... Calla (`None`) cuando la ruta no sigue ninguna
convención reconocida, en vez de adivinar.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from coderagmanager.domain.models import CodeChunk

_LAYER_BY_SEGMENT = {
    "domain": "domain",
    "application": "application",
    "services": "application",
    "ports": "ports",
    "infrastructure": "infrastructure",
    "adapters": "infrastructure",
    "controllers": "infrastructure",
    "repositories": "infrastructure",
}
_TEST_SEGMENTS = {"tests", "test"}
_TEST_FILENAME_MARKERS = ("test", "spec")


def classify_layer_by_path(file_path: str) -> str | None:
    for segment in file_path.split("/"):
        layer = _LAYER_BY_SEGMENT.get(segment.lower())
        if layer:
            return layer
    return None


def classify_kind_by_path(file_path: str) -> str | None:
    segments = file_path.split("/")
    directories, filename = segments[:-1], segments[-1].lower()
    if any(d.lower() in _TEST_SEGMENTS for d in directories):
        return "test"
    if any(marker in filename for marker in _TEST_FILENAME_MARKERS):
        return "test"
    return None


_SPRING_JAVA_ANNOTATIONS = frozenset({
    "RestController",
    "Controller",
    "Service",
    "Entity",
    "Repository",
    "Mapper",
    "ControllerAdvice",
    "RestControllerAdvice",
    "Configuration",
})


def spring_java_pack_applies(chunks: Iterable[CodeChunk]) -> bool:
    return any(
        chunk.language == "java"
        and _SPRING_JAVA_ANNOTATIONS.intersection(
            chunk.metadata.get("annotations", ())
        )
        for chunk in chunks
    )


def _in_ports_segment(file_path: str, sub: str) -> bool:
    segments = [s.lower() for s in file_path.split("/")]
    return any(
        segment == "ports" and segments[i + 1] == sub
        for i, segment in enumerate(segments[:-1])
    )


def _classify_interface_role_spring_java(chunk: CodeChunk, annotations: set) -> str | None:
    if "Mapper" in annotations:
        return "mapper"
    if any("Repository" in name for name in chunk.metadata.get("supertypes", ())):
        return "repository"
    if chunk.layer != "domain":
        return None
    if _in_ports_segment(chunk.file_path, "in"):
        return "port-in"
    if _in_ports_segment(chunk.file_path, "out"):
        return "port-out"
    if chunk.symbol.endswith("UseCase"):
        return "port-in"
    if chunk.symbol.endswith("Port"):
        return "port-out"
    return None


def _classify_class_role_spring_java(chunk: CodeChunk, annotations: set) -> str | None:
    if "RestController" in annotations or "Controller" in annotations:
        return "controller"
    if "Service" in annotations:
        return "use-case" if chunk.layer == "application" else "service"
    if "Entity" in annotations:
        return "jpa-entity"
    if "ControllerAdvice" in annotations or "RestControllerAdvice" in annotations:
        return "exception-handler"
    if "Mapper" in annotations:
        return "mapper"
    return None


def classify_role_spring_java(chunk: CodeChunk) -> str | None:
    annotations = set(chunk.metadata.get("annotations", ()))
    if chunk.kind == "interface":
        return _classify_interface_role_spring_java(chunk, annotations)
    if chunk.kind == "class":
        return _classify_class_role_spring_java(chunk, annotations)
    return None


SEMANTIC_ROLE_PROTOTYPES: dict[str, str] = {
    "entity": "a domain entity or data model representing a core business concept, without external I/O",
    "controller": "a handler that receives an external request (HTTP, CLI, or event) and delegates it to application logic",
    "adapter": "an adapter that reads or writes to an external system such as a database, message queue, or API",
    "use_case": "an application service that orchestrates business logic by coordinating several components",
    "mapper": "a converter that transforms data between two representations, such as a DTO and a domain object",
    "config": "configuration or setup code that wires dependencies, with no business logic",
    "utility": "a generic helper function with no specific architectural role",
}

# Valor de partida para "confianza baja" en la Capa 3; pendiente de calibrar
# contra los 3 proyectos reales del banco de benchmarks una vez haya código
# ejecutable — ver PLAN-MEJORA-CODE-RAG-MANAGER.md §12 punto 5.
SEMANTIC_LOW_CONFIDENCE_MARGIN = 0.05


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def nearest_role_prototype(
    chunk_embedding: list[float],
    prototype_embeddings: dict[str, list[float]],
) -> tuple[str, float]:
    ranked = sorted(
        (
            (role, _cosine_similarity(chunk_embedding, vector))
            for role, vector in prototype_embeddings.items()
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )
    best_role, best_similarity = ranked[0]
    second_similarity = ranked[1][1] if len(ranked) > 1 else best_similarity
    return best_role, best_similarity - second_similarity
