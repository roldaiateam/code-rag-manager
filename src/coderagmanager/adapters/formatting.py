"""Formateo de resultados a texto legible, compartido por CLI y servidor MCP."""

from __future__ import annotations

from coderagmanager.domain.models import CodeChunk, SearchResult

LOW_CONFIDENCE_NOTICE = (
    "⚠ Ningún resultado supera el umbral de confianza para esta consulta; "
    "se muestran los candidatos más cercanos, trátalos con cautela:"
)


def format_search_results(
    results: list[SearchResult], low_confidence: bool = False
) -> str:
    if not results:
        return "Sin resultados."
    lines = []
    if low_confidence:
        lines.append(LOW_CONFIDENCE_NOTICE)
    for i, r in enumerate(results, 1):
        c = r.chunk
        lines.append(
            f"{i}. {c.symbol} ({c.kind}, {c.language}) — "
            f"{c.file_path}:{c.start_line}-{c.end_line} "
            f"[score={r.score:.3f}, {r.match_reason}]"
        )
        preview = c.source_text.strip().splitlines()
        lines.extend(f"     {line}" for line in preview[:4])
        if len(preview) > 4:
            lines.append("     ...")
    return "\n".join(lines)


def format_included(included: dict) -> str:
    """Coletilla informativa sobre chunks indexados fuera de git ls-files."""
    parts = []
    if included.get("auto"):
        parts.append(f"auto-incluido código generado: {included['auto']} chunks")
    if included.get("extra"):
        parts.append(f"incluido por --include: {included['extra']} chunks")
    return f"  ({'; '.join(parts)})" if parts else ""


def format_chain(entries: list[dict]) -> str:
    if not entries:
        return "Sin dependencias encontradas para ese símbolo (¿está indexado?)."
    lines = []
    for e in entries:
        src, tgt = e["source"], e["target"]
        lines.append(
            f"{src['symbol']} ({src['file_path']}) "
            f"--{e['edge_type']}--> {tgt['symbol']} ({tgt['file_path']})"
        )
    return "\n".join(lines)


def format_chunks(chunks: list[CodeChunk], max_rows: int = 200) -> str:
    if not chunks:
        return "No hay chunks indexados con esos filtros."
    rows = [
        f"{c.file_path}:{c.start_line}-{c.end_line}  {c.kind:<9} {c.symbol} ({c.language})"
        for c in chunks[:max_rows]
    ]
    if len(chunks) > max_rows:
        rows.append(
            f"[mostrando {max_rows} de {len(chunks)} chunks; "
            "filtra con language/kind para acotar el listado]"
        )
    return "\n".join(rows)


def format_stats(stats: dict) -> str:
    lines = [
        f"Proyecto: {stats['project_id']}",
        f"Indexado: {'sí' if stats['indexed'] else 'no'}",
        f"Último commit indexado: {stats['last_indexed_commit'] or '(sin commit)'}",
        f"Indexado el: {stats['last_indexed_at'] or '-'}",
        f"Chunks: {stats['total_chunks']}   Aristas: {stats['total_edges']}",
    ]
    if stats["by_language"]:
        langs = ", ".join(f"{k}={v}" for k, v in sorted(stats["by_language"].items()))
        lines.append(f"Por lenguaje: {langs}")
    if stats["by_kind"]:
        kinds = ", ".join(f"{k}={v}" for k, v in sorted(stats["by_kind"].items()))
        lines.append(f"Por tipo: {kinds}")
    return "\n".join(lines)
