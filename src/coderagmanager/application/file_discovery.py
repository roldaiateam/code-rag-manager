"""Descubrimiento de ficheros indexables de un proyecto.

Tres fuentes, unidas y deduplicadas por ruta relativa:

1. "git"   — `git ls-files --cached --others --exclude-standard` (respeta
             .gitignore sin reimplementar su parser). Si el directorio no es
             un repo git, degrada a un recorrido con exclusiones mínimas.
2. "auto"  — código generado por convención de ecosistema (Maven/Gradle),
             indexable aunque esté gitignorado: en proyectos contract-first
             ahí viven DTOs e interfaces esenciales para la búsqueda.
3. "extra" — patrones glob configurados por proyecto (`--include`), para
             rutas gitignoradas no cubiertas por la convención.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path

EXCLUDED_DIRS = {
    ".git", "node_modules", "target", "build", "dist",
    "venv", ".venv", "__pycache__", ".crm",
}
# (directorio_marcador, subdirectorio_generado): target/generated-sources (Maven),
# build/generated (Gradle)
AUTO_INCLUDE_MARKERS = (("target", "generated-sources"), ("build", "generated"))
MAX_FILE_BYTES = 1_000_000  # ficheros mayores se consideran no indexables


def discover_files(
    root_path: str,
    extra_index_paths: Iterable[str] = (),
    auto_include: bool = True,
) -> Iterator[tuple[str, str, str]]:
    """Genera triples (ruta_relativa, contenido, origen) con origen "git" | "auto" | "extra"."""
    seen: set[str] = set()
    sources: list[tuple[str, Iterable[str]]] = [("git", _candidate_paths(root_path))]
    if auto_include:
        sources.append(("auto", _auto_generated_paths(root_path)))
    if extra_index_paths:
        sources.append(("extra", _glob_paths(root_path, extra_index_paths)))

    for origin, rel_paths in sources:
        for rel_path in rel_paths:
            if rel_path in seen:
                continue
            seen.add(rel_path)
            if rel_path.startswith(".crm/") or "/.crm/" in rel_path:
                continue
            abs_path = os.path.join(root_path, rel_path)
            if not os.path.isfile(abs_path):
                continue
            try:
                if os.path.getsize(abs_path) > MAX_FILE_BYTES:
                    continue
                with open(abs_path, encoding="utf-8") as fh:
                    source = fh.read()
            except (UnicodeDecodeError, OSError):
                continue  # binario o ilegible: no indexable
            yield rel_path, source, origin


def _candidate_paths(root_path: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", root_path, "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return [line for line in result.stdout.splitlines() if line.strip()]
    return list(_walk_fallback(root_path))


def _walk_fallback(root_path: str) -> Iterator[str]:
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for filename in sorted(filenames):
            yield os.path.relpath(os.path.join(dirpath, filename), root_path)


def _auto_generated_paths(root_path: str) -> Iterator[str]:
    """Ficheros bajo directorios de código generado por convención (Maven/Gradle)."""
    for generated_dir in _auto_generated_dirs(root_path):
        yield from _walk_all(root_path, generated_dir)


def _auto_generated_dirs(root_path: str) -> Iterator[str]:
    for dirpath, dirnames, _ in os.walk(root_path):
        # comprobar los marcadores ANTES de podar: target/build están excluidos
        for marker, generated_subdir in AUTO_INCLUDE_MARKERS:
            candidate = os.path.join(dirpath, marker, generated_subdir)
            if marker in dirnames and os.path.isdir(candidate):
                yield candidate
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]


def _glob_paths(root_path: str, patterns: Iterable[str]) -> Iterator[str]:
    root = Path(root_path)
    for pattern in patterns:
        for match in sorted(root.glob(pattern)):
            if match.is_dir():
                yield from _walk_all(root_path, str(match))
            elif match.is_file():
                yield str(match.relative_to(root))


def _walk_all(root_path: str, directory: str) -> Iterator[str]:
    """Recorrido completo de un directorio incluido explícitamente (sin la
    lista de exclusión general — solo cachés de Python)."""
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            yield os.path.relpath(os.path.join(dirpath, filename), root_path)
