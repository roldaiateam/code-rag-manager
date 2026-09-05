"""Clasificación de chunks por vocabulario de rutas: pura coincidencia de
segmentos de carpeta, sin conocer lenguaje ni framework — generaliza igual
sobre Python, Java, JS... Calla (`None`) cuando la ruta no sigue ninguna
convención reconocida, en vez de adivinar.
"""

from __future__ import annotations

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
