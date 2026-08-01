"""Bloque de adopción en el CLAUDE.md del repo indexado.

Los agentes leen CLAUDE.md en cada sesión: es la palanca más efectiva para
que usen las tools del MCP en vez de grep por defecto. El bloque va
delimitado por marcadores y el upsert es idempotente: crear si no existe,
añadir sin tocar el contenido ajeno, reemplazar si ya hay una versión previa.
"""

from __future__ import annotations

import os

BEGIN_MARKER = "<!-- crm:begin -->"
END_MARKER = "<!-- crm:end -->"


def _block(project_id: str) -> str:
    server = f"crm-{project_id}"
    return f"""{BEGIN_MARKER}
## Índice de código (crm) — OBLIGATORIO para explorar código

Este repositorio tiene un índice semántico+estructural expuesto como tools MCP
`mcp__{server}__*`. Cuando estén disponibles:

- **Toda búsqueda de código empieza por `search_code`** (por significado o por
  símbolo). NO uses Grep/Glob/Bash para localizar código antes de haber
  probado `search_code` — devuelve funciones/clases con fichero:líneas.
- "¿Quién llama a X?", "¿qué implementa/extiende X?" → `get_dependency_chain`
  (grafo real extraído del código, más fiable que inferir con greps).
- Leer la implementación de un símbolo → `get_source` (las clases largas
  llegan como esqueleto; la respuesta indica cómo pedir el cuerpo completo).
- Primer contacto con el repo → `get_index_stats`.

Grep/Read quedan para ficheros de configuración, texto exacto no-código, o si
`search_code` no encuentra lo que buscas (el índice puede estar desactualizado:
en ese caso dilo en tu respuesta).
{END_MARKER}"""


def upsert_claude_md_block(project_root: str, project_id: str) -> str:
    """Escribe/actualiza el bloque crm en <project_root>/CLAUDE.md. Devuelve la ruta."""
    path = os.path.join(project_root, "CLAUDE.md")
    block = _block(project_id)

    if not os.path.exists(path):
        content = block + "\n"
    else:
        with open(path, encoding="utf-8") as fh:
            existing = fh.read()
        if BEGIN_MARKER in existing and END_MARKER in existing:
            start = existing.index(BEGIN_MARKER)
            end = existing.index(END_MARKER) + len(END_MARKER)
            content = existing[:start] + block + existing[end:]
        else:
            separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
            content = existing + separator + block + "\n"

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path
