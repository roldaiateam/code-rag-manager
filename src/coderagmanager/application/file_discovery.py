"""Descubrimiento de ficheros indexables de un proyecto.

Usa `git ls-files --cached --others --exclude-standard` (respeta .gitignore
sin reimplementar su parser). Si el directorio no es un repo git, degrada a
un recorrido de directorio con una lista de exclusión mínima.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator

EXCLUDED_DIRS = {
    ".git", "node_modules", "target", "build", "dist",
    "venv", ".venv", "__pycache__", ".crm",
}
MAX_FILE_BYTES = 1_000_000  # ficheros mayores se consideran no indexables


def discover_files(root_path: str) -> Iterator[tuple[str, str]]:
    """Genera pares (ruta_relativa, contenido) de los ficheros de texto del proyecto."""
    for rel_path in _candidate_paths(root_path):
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
        yield rel_path, source


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
